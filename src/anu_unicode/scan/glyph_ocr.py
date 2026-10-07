from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageOps
from scipy import ndimage

from anu_unicode.mapping import read_rows, write_rows
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.ink import Bitmap, Box

OCR_SAMPLES = 5
OCR_WORKERS = 8
OCR_PADDING = 20
OCR_MIN_HEIGHT = 96

Proposal = tuple[str, int]


@dataclass(frozen=True)
class GlyphOcr:
    reader: Callable[[Bitmap], str]
    cache: Path


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


def tesseract_glyph(mask: Bitmap, tesseract_cmd: str) -> str:
    image = ImageOps.expand(Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)), border=OCR_PADDING, fill=255)
    if image.height < OCR_MIN_HEIGHT:
        image = image.resize((round(image.width * OCR_MIN_HEIGHT / image.height), OCR_MIN_HEIGHT), Image.Resampling.LANCZOS)
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    return str(pytesseract.image_to_string(image, lang="tel", config="--psm 10")).strip()


def majority(readings: Iterable[str]) -> Proposal:
    votes = Counter(reading for reading in readings if reading)
    return votes.most_common(1)[0] if votes else ("", 0)


def _crops(samples: dict[int, list[Occurrence]], render: Callable[[int], Bitmap]) -> dict[int, list[Bitmap]]:
    crops: dict[int, list[Bitmap]] = defaultdict(list)
    for page in sorted({item.page for items in samples.values() for item in items}):
        ink = render(page)
        for shape_id, items in samples.items():
            crops[shape_id].extend(largest_component(ink, item.bbox) for item in items if item.page == page)
    return crops


def propose(occurrences: Iterable[Occurrence], render: Callable[[int], Bitmap], ocr: GlyphOcr) -> dict[int, Proposal]:
    proposals = {int(row["shape_id"]): (row["proposal"], int(row["votes"])) for row in read_rows(ocr.cache)}
    members: dict[int, list[Occurrence]] = defaultdict(list)
    for item in occurrences:
        if item.shape_id != EQUALS:
            members[item.shape_id].append(item)
    missing = {shape_id: spread(items, OCR_SAMPLES) for shape_id, items in members.items() if shape_id not in proposals}
    if missing:
        crops = _crops(missing, render)
        with ThreadPoolExecutor(OCR_WORKERS) as pool:
            for shape_id, readings in zip(missing, pool.map(lambda shape_id: [ocr.reader(mask) for mask in crops[shape_id]], missing)):
                proposals[shape_id] = majority(" ".join(reading.split()) for reading in readings)
        ocr.cache.parent.mkdir(parents=True, exist_ok=True)
        write_rows(ocr.cache, ("shape_id", "proposal", "votes"), sorted((shape_id, *proposal) for shape_id, proposal in proposals.items()))
    return {shape_id: proposals[shape_id] for shape_id in members}
