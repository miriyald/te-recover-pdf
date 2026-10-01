import argparse
import csv
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image

from anu_unicode.convert import Coverage, convert_anu, convert_page
from anu_unicode.glyphs import page_lines, split_words
from anu_unicode.mapping import load_mapping
from anu_unicode.ocr import DPI, OcrCache
from anu_unicode.quality import character_confusions, compare_words

logger = logging.getLogger(__name__)
MATCH_OVERLAP = 0.3
CROP_PADDING = 12
FIELDS = ("id", "page", "tesseract", "truth", "tesseract_code_points", "truth_code_points", "confidence", "crop")


@dataclass(frozen=True)
class Evidence:
    identifier: str
    page: int
    tesseract: str
    truth: str
    confidence: float
    crop: str


def code_points(text: str) -> str:
    return " ".join(f"U+{ord(char):04X}" for char in text)


def _crop(image: Image.Image, bbox: tuple[float, float, float, float]) -> Image.Image:
    scale = DPI / 72
    left, top, right, bottom = (round(value * scale) for value in bbox)
    return image.crop((max(left - CROP_PADDING, 0), max(top - CROP_PADDING, 0), right + CROP_PADDING, bottom + CROP_PADDING))


def collect_page(document: pymupdf.Document, verified: Path, mapping: dict[str, str], ocr: OcrCache, out: Path) -> list[Evidence]:
    number = int(verified.name.split("-")[1].split(".")[0])
    page = document[number - 1]
    if convert_page(page, mapping, Coverage()).split() != verified.read_text(encoding="utf-8").split():
        raise SystemExit(f"page {number}: converted text differs from verified text, so it is not usable as ground truth")
    words = [(word.bbox, convert_anu(word.text, mapping, Coverage())) for line in page_lines(page) for word in split_words(line)]
    image = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY).pil_image()
    image.save(out / "pages" / f"page-{number:03d}.png")
    evidence: list[Evidence] = []
    for comparison in compare_words(words, ocr(page), MATCH_OVERLAP):
        if comparison.disagrees and comparison.ocr_bbox and comparison.confidence is not None and comparison.ocr:
            identifier = f"p{number:03d}-{len(evidence) + 1:03d}"
            crop = f"crops/{identifier}.png"
            _crop(image, comparison.ocr_bbox).save(out / crop)
            evidence.append(Evidence(identifier, number, comparison.ocr, comparison.converted, comparison.confidence, crop))
    return evidence


def write_evidence(out: Path, items: list[Evidence]) -> None:
    with (out / "evidence.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows((item.identifier, item.page, item.tesseract, item.truth, code_points(item.tesseract), code_points(item.truth),
                          round(item.confidence), item.crop) for item in items)
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in items:
        for pair in character_confusions(item.tesseract, item.truth):
            examples[pair].append(item.identifier)
    lines = ["| Tesseract read | Correct | Count | Code points (read -> correct) | Example ids |", "|---|---|---|---|---|"]
    lines += [
        f"| {read} | {truth} | {len(ids)} | {code_points(read)} -> {code_points(truth)} | {', '.join(ids[:3])} |"
        for (read, truth), ids in sorted(examples.items(), key=lambda entry: -len(entry[1]))
    ]
    (out / "confusions.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Tesseract misreads on human-verified pages as reportable evidence")
    parser.add_argument("--pdf", type=Path, default=Path("files/Mahabharatamu.pdf"))
    parser.add_argument("--mapping", type=Path, default=Path("fonts/anu/ocr-learning/mapping.tsv"))
    parser.add_argument("--verified", type=Path, default=Path("books/mahabharatamu/verified"))
    parser.add_argument("--ocr-cache", type=Path, default=Path("books/mahabharatamu/ocr-cache"))
    parser.add_argument("--out", type=Path, default=Path("docs/temp/tesseract-evidence"))
    parser.add_argument("--tesseract", default=os.environ.get("TESSERACT_CMD", "tesseract"))
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    for folder in ("crops", "pages"):
        (arguments.out / folder).mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(arguments.pdf)
    mapping = load_mapping(arguments.mapping)
    ocr = OcrCache(arguments.ocr_cache, arguments.tesseract)
    items = [item for path in sorted(arguments.verified.glob("page-*.unicode.txt"))
             for item in collect_page(document, path, mapping, ocr, arguments.out)]
    write_evidence(arguments.out, items)
    logger.info("evidence written", extra={"items": len(items), "out": str(arguments.out)})


if __name__ == "__main__":
    main()
