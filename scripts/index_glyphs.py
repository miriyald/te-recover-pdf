import argparse
import colorsys
import html
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pymupdf
import pytesseract
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy import ndimage

logger = logging.getLogger(__name__)

GRID = 32
INK_THRESHOLD = 128
OVERLAY_FONT_SIZE = 18
MIN_CLUSTER_SIZE = 2
OCR_PADDING = 20
OCR_MIN_HEIGHT = 96
OCR_WORKERS = 8
TEMPLATE = Path(__file__).with_name("glyph_table.html.tmpl")

Bitmap = NDArray[np.bool_]
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Component:
    bbox: Box
    mask: Bitmap
    grid: Bitmap

    @property
    def aspect(self) -> float:
        left, top, right, bottom = self.bbox
        return (right - left) / (bottom - top)


@dataclass
class Glyph:
    representative: Component
    count: int = 0
    pages: set[int] = field(default_factory=set)
    ocr: str = ""


def page_range(text: str) -> list[int]:
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def render_ink(page: pymupdf.Page) -> Bitmap:
    scale = page.get_images(full=True)[0][2] / page.rect.width
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY)
    gray = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width)
    return gray < INK_THRESHOLD


def _normalise(mask: Bitmap) -> Bitmap:
    image = Image.fromarray(mask.astype(np.uint8) * 255).resize((GRID, GRID), Image.Resampling.BILINEAR)
    return np.asarray(image) > INK_THRESHOLD


def find_components(ink: Bitmap, min_area: int) -> list[Component]:
    labels, _ = ndimage.label(ink, structure=np.ones((3, 3)))
    components = []
    for index, region in enumerate(ndimage.find_objects(labels), start=1):
        mask = labels[region] == index
        if mask.size < min_area:
            continue
        box = (region[1].start, region[0].start, region[1].stop, region[0].stop)
        components.append(Component(box, mask, _normalise(mask)))
    return sorted(components, key=lambda component: (component.bbox[1], component.bbox[0]))


class GlyphCatalog:
    def __init__(self, max_mismatch: float, max_aspect_drift: float) -> None:
        self.max_mismatch = max_mismatch
        self.max_aspect_drift = max_aspect_drift
        self.glyphs: list[Glyph] = []

    def assign(self, component: Component, page: int) -> int:
        best_id, best_mismatch = -1, self.max_mismatch
        for glyph_id, glyph in enumerate(self.glyphs):
            if abs(np.log(component.aspect / glyph.representative.aspect)) > self.max_aspect_drift:
                continue
            mismatch = float((component.grid != glyph.representative.grid).mean())
            if mismatch < best_mismatch:
                best_id, best_mismatch = glyph_id, mismatch
        if best_id < 0:
            best_id = len(self.glyphs)
            self.glyphs.append(Glyph(component))
        self.glyphs[best_id].count += 1
        self.glyphs[best_id].pages.add(page)
        return best_id

    def by_frequency(self) -> list[tuple[int, Glyph]]:
        return sorted(enumerate(self.glyphs), key=lambda item: (-item[1].count, item[0]))


def _glyph_image(component: Component) -> Image.Image:
    return Image.fromarray(np.where(component.mask, 0, 255).astype(np.uint8))


def _colour(glyph_id: int) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb((glyph_id * 0.61803398875) % 1.0, 0.85, 0.85)
    return int(red * 255), int(green * 255), int(blue * 255)


def overlay_image(ink: Bitmap, assignments: list[tuple[Component, int]]) -> Image.Image:
    page = Image.fromarray(np.where(ink, 90, 255).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=OVERLAY_FONT_SIZE)
    for component, glyph_id in assignments:
        left, top, right, bottom = component.bbox
        colour = _colour(glyph_id)
        draw.rectangle((left, top, right, bottom), outline=colour, width=2)
        draw.text((left, bottom + 1), str(glyph_id), fill=colour, font=font)
    return page


def ocr_glyph(component: Component) -> str:
    image = ImageOps.expand(_glyph_image(component), border=OCR_PADDING, fill=255)
    if image.height < OCR_MIN_HEIGHT:
        factor = OCR_MIN_HEIGHT / image.height
        image = image.resize((round(image.width * factor), OCR_MIN_HEIGHT), Image.Resampling.LANCZOS)
    return pytesseract.image_to_string(image, lang="tel", config="--psm 10").strip()


def load_labels(path: Path | None) -> dict[int, str]:
    if path is None:
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    return {int(fields[0]): fields[2] for fields in (line.split("\t") for line in lines) if len(fields) >= 3}


def _sheet_rows(items: list[tuple[int, Glyph]], labels: dict[int, str]) -> str:
    return "".join(
        f'<tr data-id="{glyph_id}" data-count="{glyph.count}"><td>#{glyph_id}</td><td>{glyph.count}</td>'
        f'<td class="glyph"><img src="glyphs/{glyph_id}.png"></td><td class="ocr">{html.escape(glyph.ocr)}</td>'
        f'<td><input class="unicode" value="{html.escape(labels.get(glyph_id, glyph.ocr))}"></td><td class="codes"></td>'
        f'<td><input class="ok" type="checkbox"{" checked" if glyph_id in labels else ""}></td></tr>'
        for glyph_id, glyph in items
    )


def write_sheet(path: Path, repeated: list[tuple[int, Glyph]], singles: list[tuple[int, Glyph]], pages: list[int],
                labels: dict[int, str]) -> None:
    replacements = {
        "__PAGES__": f"{pages[0]}-{pages[-1]}",
        "__REPEATED_COUNT__": str(len(repeated)),
        "__SINGLES_COUNT__": str(len(singles)),
        "__REPEATED__": _sheet_rows(repeated, labels),
        "__SINGLES__": _sheet_rows(singles, labels),
    }
    document = TEMPLATE.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        document = document.replace(placeholder, value)
    path.write_text(document, encoding="utf-8", newline="\n")


def write_data(out: Path, catalog: GlyphCatalog, occurrences: list[tuple[int, Box, int]]) -> None:
    lines = ["page\tleft\ttop\tright\tbottom\tglyph_id"]
    lines += [f"{page}\t{box[0]}\t{box[1]}\t{box[2]}\t{box[3]}\t{glyph_id}" for page, box, glyph_id in occurrences]
    (out / "occurrences.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    table = ["glyph_id\tcount\tpages\tocr"]
    for glyph_id, glyph in catalog.by_frequency():
        table.append(f"{glyph_id}\t{glyph.count}\t{','.join(map(str, sorted(glyph.pages)))}\t{glyph.ocr}")
    (out / "glyph_table.tsv").write_text("\n".join(table) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign glyph ids to the ink components of scanned pages")
    parser.add_argument("--pdf", type=Path, default=Path("2015.395281.Prasaaskhara-Padakosamu.pdf"))
    parser.add_argument("--pages", type=page_range, default=[4], help="1-based, e.g. 4 or 4-12")
    parser.add_argument("--out", type=Path, default=Path("docs/temp/glyph-ids"))
    parser.add_argument("--max-mismatch", type=float, default=0.12, help="fraction of differing grid pixels")
    parser.add_argument("--max-aspect-drift", type=float, default=0.25, help="abs log aspect-ratio difference")
    parser.add_argument("--labels", type=Path, help="labels.tsv saved from glyph_table.html; its rows come back confirmed")
    parser.add_argument("--tesseract", default=os.environ.get("TESSERACT_CMD", "tesseract"))
    parser.add_argument("--min-area", type=int, default=40, help="smallest component bounding box in pixels")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    document = pymupdf.open(arguments.pdf)
    catalog = GlyphCatalog(arguments.max_mismatch, arguments.max_aspect_drift)
    occurrences: list[tuple[int, Box, int]] = []
    (arguments.out / "glyphs").mkdir(parents=True, exist_ok=True)
    for number in arguments.pages:
        ink = render_ink(document[number - 1])
        assignments = [(component, catalog.assign(component, number)) for component in find_components(ink, arguments.min_area)]
        occurrences += [(number, component.bbox, glyph_id) for component, glyph_id in assignments]
        overlay_image(ink, assignments).save(arguments.out / f"overlay-page-{number}.png")
        logger.info("page %d: components=%d glyphs so far=%d", number, len(assignments), len(catalog.glyphs))

    for glyph_id, glyph in enumerate(catalog.glyphs):
        _glyph_image(glyph.representative).save(arguments.out / "glyphs" / f"{glyph_id}.png")
    pytesseract.pytesseract.tesseract_cmd = arguments.tesseract
    with ThreadPoolExecutor(OCR_WORKERS) as pool:
        for glyph, text in zip(catalog.glyphs, pool.map(ocr_glyph, (glyph.representative for glyph in catalog.glyphs))):
            glyph.ocr = text
    ranked = catalog.by_frequency()
    repeated = [item for item in ranked if item[1].count >= MIN_CLUSTER_SIZE]
    singles = [item for item in ranked if item[1].count < MIN_CLUSTER_SIZE]
    write_sheet(arguments.out / "glyph_table.html", repeated, singles, arguments.pages, load_labels(arguments.labels))
    write_data(arguments.out, catalog, occurrences)
    logger.info("done: components=%d repeated=%d singletons=%d table=%s", len(occurrences), len(repeated), len(singles),
                arguments.out / "glyph_table.html")


if __name__ == "__main__":
    main()
