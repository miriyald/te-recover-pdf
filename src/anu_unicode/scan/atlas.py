import html
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pymupdf
import pytesseract
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage

from anu_unicode.mapping import read_rows, write_rows
from anu_unicode.scan.catalog import MAX_THICK_BLOB, ShapeCatalog, thick_blob, to_canvas
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.ink import Bitmap, Box, find_components, median_height, render_ink
from anu_unicode.scan.page import MIN_AREA
from anu_unicode.scan.source import shape_char
from anu_unicode.shape_naming.atlas import SCRIPT, STYLE
from anu_unicode.shape_naming.shapes import Shape

OCR_SAMPLES = 5
EXAMPLE_WORDS = 2
SUGGEST_CANDIDATES = 16
SUGGEST_STRAY = 0.35
SUGGEST_SHARE = 0.5
OCR_WORKERS = 8
OCR_PADDING = 20
OCR_MIN_HEIGHT = 96
WORD_PADDING = 8
WORD_HEIGHT = 48

WordKey = tuple[int, int, int]
Request = tuple[bool, int, Occurrence]

SCAN_SCRIPT = """
function useValue(row,value){const unicode=row.querySelector('input.c'),name=row.querySelector('input.n');
  if(!name.value||name.value===unicode.value){name.value=value;}unicode.value=value;refresh();}
function useProposal(button){const row=button.closest('tr');useValue(row,row.dataset.proposal);}
function copyToSame(button){const row=button.closest('tr'),name=row.querySelector('input.n').value,value=row.querySelector('input.c').value;
  row.dataset.same.split(' ').filter(Boolean).forEach(id=>{const other=document.getElementById('s'+id);
    if(other&&!other.querySelector('input.n').value){other.querySelector('input.n').value=name;other.querySelector('input.c').value=value;}});
  refresh();}
document.addEventListener('input',event=>{const row=event.target.closest('tr');
  if(row&&event.target.matches('input.c')){const name=row.querySelector('input.n');
    if(!name.dataset.typed){name.value=event.target.value;}}
  if(row&&event.target.matches('input.n')){event.target.dataset.typed='1';}refresh();});
"""


@dataclass(frozen=True)
class Crop:
    mask: Bitmap
    body_height: float


@dataclass(frozen=True)
class AtlasRow:
    shape_id: int
    count: int
    band: str
    proposal: str
    votes: int
    same: tuple[int, ...]
    words: tuple[str, ...]


def ranked_ids(occurrences: Iterable[Occurrence], min_count: int) -> list[tuple[int, int, str]]:
    counts: Counter[int] = Counter()
    bands: dict[int, str] = {}
    for item in occurrences:
        counts[item.shape_id] += 1
        bands[item.shape_id] = str(item.band)
    return [(shape_id, count, bands[shape_id]) for shape_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            if count >= min_count]


def spread(items: list[Occurrence], limit: int) -> list[Occurrence]:
    if len(items) <= limit:
        return items
    return [items[int(index)] for index in np.linspace(0, len(items) - 1, limit)]


def largest_component(ink: Bitmap, bbox: Box) -> Bitmap:
    left, top, right, bottom = bbox
    labels, count = ndimage.label(ink[top:bottom, left:right], structure=np.ones((3, 3)))
    if not count:
        return np.zeros((bottom - top, right - left), dtype=bool)
    return np.asarray(labels == np.bincount(labels.ravel())[1:].argmax() + 1, dtype=bool)


def word_image(ink: Bitmap, word: list[Occurrence], highlight: Occurrence) -> Image.Image:
    left = max(min(item.bbox[0] for item in word) - WORD_PADDING, 0)
    top = max(min(item.bbox[1] for item in word) - WORD_PADDING, 0)
    right, bottom = max(item.bbox[2] for item in word) + WORD_PADDING, max(item.bbox[3] for item in word) + WORD_PADDING
    image = Image.fromarray(np.where(ink[top:bottom, left:right], 0, 255).astype(np.uint8)).convert("RGB")
    box = highlight.bbox
    outline = (box[0] - left - 2, box[1] - top - 2, box[2] - left + 1, box[3] - top + 1)
    ImageDraw.Draw(image).rectangle(outline, outline=(220, 0, 0), width=3)
    return image.resize((max(1, round(image.width * WORD_HEIGHT / image.height)), WORD_HEIGHT))


def tesseract_reading(mask: Bitmap, tesseract_cmd: str) -> str:
    image = ImageOps.expand(Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)), border=OCR_PADDING, fill=255)
    if image.height < OCR_MIN_HEIGHT:
        image = image.resize((round(image.width * OCR_MIN_HEIGHT / image.height), OCR_MIN_HEIGHT), Image.Resampling.LANCZOS)
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    return str(pytesseract.image_to_string(image, lang="tel", config="--psm 10")).strip()


def majority(readings: Iterable[str]) -> tuple[str, int]:
    votes = Counter(reading for reading in readings if reading)
    return votes.most_common(1)[0] if votes else ("", 0)


def _passing(catalog: ShapeCatalog, canvases: list[Bitmap], other: int) -> int:
    return sum(thick_blob(canvas, catalog.canvases.bitmaps[other]) <= MAX_THICK_BLOB for canvas in canvases)


def same_shape_ids(catalog: ShapeCatalog, shape_id: int, crops: list[Crop]) -> tuple[int, ...]:
    distances = catalog.distances(catalog.prototype_shape(shape_id))
    distances[shape_id] = np.inf
    candidates = [int(index) for index in np.argsort(distances, kind="stable")[:SUGGEST_CANDIDATES] if distances[index] <= SUGGEST_STRAY]
    canvases = [to_canvas(crop.mask, crop.body_height) for crop in crops]
    return tuple(other for other in candidates if _passing(catalog, canvases, other) >= SUGGEST_SHARE * len(canvases))


@dataclass(frozen=True)
class AtlasInput:
    document: pymupdf.Document
    occurrences: list[Occurrence]
    catalog: ShapeCatalog


@dataclass(frozen=True)
class Ocr:
    reader: Callable[[Bitmap], str]
    cache: Path


@dataclass
class Samples:
    crops: dict[int, list[Crop]] = field(default_factory=lambda: defaultdict(list))
    words: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))


def _by_word(occurrences: Iterable[Occurrence]) -> dict[WordKey, list[Occurrence]]:
    words: dict[WordKey, list[Occurrence]] = defaultdict(list)
    for item in occurrences:
        words[(item.page, item.line, item.word)].append(item)
    return words


def _by_page(wanted: Mapping[int, list[Occurrence]], examples: Mapping[int, list[Occurrence]]) -> dict[int, list[Request]]:
    requests: dict[int, list[Request]] = defaultdict(list)
    for is_crop, chosen in ((True, wanted), (False, examples)):
        for shape_id, items in chosen.items():
            for item in items:
                requests[item.page].append((is_crop, shape_id, item))
    return requests


def collect_samples(source: AtlasInput, wanted: Mapping[int, list[Occurrence]], examples: Mapping[int, list[Occurrence]],
                    out: Path) -> Samples:
    words, samples = _by_word(source.occurrences), Samples()
    (out / "words").mkdir(parents=True, exist_ok=True)
    for page, requests in sorted(_by_page(wanted, examples).items()):
        ink = render_ink(source.document[page - 1])
        body_height = median_height(find_components(ink, MIN_AREA))
        for is_crop, shape_id, item in requests:
            if is_crop:
                samples.crops[shape_id].append(Crop(largest_component(ink, item.bbox), body_height))
                continue
            name = f"words/{shape_id}-{len(samples.words[shape_id])}.png"
            word_image(ink, words[(item.page, item.line, item.word)], item).save(out / name)
            samples.words[shape_id].append(name)
    return samples


def cached_proposals(path: Path) -> dict[int, tuple[str, int]]:
    return {int(row["shape_id"]): (row["proposal"], int(row["votes"])) for row in read_rows(path)}


def propose_all(crops: Mapping[int, list[Crop]], ocr: Ocr) -> dict[int, tuple[str, int]]:
    proposals = cached_proposals(ocr.cache)
    missing = [shape_id for shape_id in crops if shape_id not in proposals]
    with ThreadPoolExecutor(OCR_WORKERS) as pool:
        for shape_id, readings in zip(missing, pool.map(lambda shape_id: [ocr.reader(crop.mask) for crop in crops[shape_id]], missing)):
            proposals[shape_id] = majority(readings)
    write_rows(ocr.cache, ("shape_id", "proposal", "votes"), sorted((shape_id, *proposal) for shape_id, proposal in proposals.items()))
    return proposals


def build_rows(source: AtlasInput, min_count: int, out: Path, ocr: Ocr) -> list[AtlasRow]:
    ranked = ranked_ids(source.occurrences, min_count)
    members: dict[int, list[Occurrence]] = defaultdict(list)
    for item in source.occurrences:
        members[item.shape_id].append(item)
    wanted = {shape_id: spread(members[shape_id], OCR_SAMPLES) for shape_id, _, _ in ranked}
    examples = {shape_id: spread(members[shape_id], EXAMPLE_WORDS) for shape_id, _, _ in ranked}
    samples = collect_samples(source, wanted, examples, out)
    proposals = propose_all(samples.crops, ocr)
    return [AtlasRow(shape_id, count, band, *proposals[shape_id], same_shape_ids(source.catalog, shape_id, samples.crops[shape_id]),
                     tuple(samples.words[shape_id])) for shape_id, count, band in ranked]


def _input(css_class: str, value: str) -> str:
    return f"<input class={css_class} value=\"{html.escape(value, quote=True)}\">"


def _row(row: AtlasRow, shape: Shape | None, strips: str) -> str:
    glyph = html.escape(shape_char(row.shape_id), quote=True)
    proposal = html.escape(row.proposal, quote=True)
    use = "<button onclick='useProposal(this)'>use</button>" if row.proposal else ""
    same = " ".join(f"<a href='#s{other}'>#{other}</a>" for other in row.same)
    copy = "<button onclick='copyToSame(this)'>copy to these</button>" if row.same else ""
    words = "".join(f"<div><img src='{html.escape(path, quote=True)}'></div>" for path in row.words)
    return (
        f"<tr id=s{row.shape_id} data-glyph=\"{glyph}\" data-proposal=\"{proposal}\" data-same=\"{' '.join(map(str, row.same))}\">"
        f"<td class=g>#{row.shape_id}</td><td>{row.count}</td><td>{row.band}</td>"
        f"<td><img class=strip src='{strips}/{row.shape_id}.png'></td>"
        f"<td>{words}</td><td class=p>{html.escape(row.proposal)} <span class=g>({row.votes}/{OCR_SAMPLES})</span> {use}</td>"
        f"<td>{_input('n', shape.name if shape else '')}</td><td>{_input('c', shape.unicode if shape else '')}</td>"
        f"<td>{same} {copy}</td></tr>"
    )


def write_scan_atlas(path: Path, rows: list[AtlasRow], shapes: Mapping[str, Shape], strips: str) -> None:
    body = "".join(_row(row, shapes.get(shape_char(row.shape_id)), strips) for row in rows)
    named = sum(shape_char(row.shape_id) in shapes for row in rows)
    export = (
        "<div id=export><b>Scan shape names</b>: type the Unicode each id stands for; the name follows it unless you type a shape name "
        "(for pieces that mean nothing alone, e.g. <code>bar_top</code>, with Unicode empty or <code>∅</code>). <i>use</i> takes "
        "Tesseract's proposal; <i>copy to these</i> fills the ids that look the same and are still empty. "
        "<button onclick='download()'>Download names.tsv</button><textarea id=tsv readonly></textarea></div>"
    )
    summary = f"<p>{len(rows)} shape ids in {sum(row.count for row in rows)} occurrences, {named} named.</p>"
    style = STYLE + "img.strip{height:40px}.p{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}"
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Scan atlas</title><style>{style}</style>{export}{summary}"
        f"<table><tr><th>id<th>count<th>band<th>prototype · members<th>in words<th>Tesseract<th>name<th>Unicode<th>looks the same</tr>"
        f"{body}</table><script>{SCRIPT}{SCAN_SCRIPT}</script>",
        encoding="utf-8", newline="\n",
    )
