import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageOps

from anu_unicode.mapping import read_rows, write_rows
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.ink import Bitmap, Box

WORD_PADDING = 10
OCR_BORDER = 20
OCR_WORKERS = 8
CACHE = "scan-word-ocr.tsv"

WordKey = tuple[int, int, int]
CacheKey = tuple[int, Box]


@dataclass(frozen=True)
class WordOcr:
    reader: Callable[[Image.Image], str]
    cache: Path


def word_box(items: Sequence[Occurrence]) -> Box:
    return (min(item.bbox[0] for item in items), min(item.bbox[1] for item in items),
            max(item.bbox[2] for item in items), max(item.bbox[3] for item in items))


def words_of(occurrences: Iterable[Occurrence]) -> dict[WordKey, list[Occurrence]]:
    words: dict[WordKey, list[Occurrence]] = defaultdict(list)
    for item in sorted(occurrences, key=lambda item: (item.page, item.line, item.word, item.position)):
        words[(item.page, item.line, item.word)].append(item)
    return dict(words)


def word_image(ink: Bitmap, box: Box) -> Image.Image:
    left, top = max(box[0] - WORD_PADDING, 0), max(box[1] - WORD_PADDING, 0)
    right, bottom = box[2] + WORD_PADDING, box[3] + WORD_PADDING
    crop = Image.fromarray(np.where(ink[top:bottom, left:right], 0, 255).astype(np.uint8))
    return ImageOps.expand(crop, border=OCR_BORDER, fill=255)


def ocr_cache_name(model: Path | None) -> str:
    if model is None:
        return CACHE
    return f"scan-word-ocr-{model.stem}-{hashlib.md5(model.read_bytes()).hexdigest()[:8]}.tsv"


def tesseract_word(image: Image.Image, tesseract_cmd: str, model: Path | None) -> str:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    lang, config = ("tel", "--psm 8") if model is None else (model.stem, f"--psm 8 --tessdata-dir {model.parent.as_posix()}")
    return str(pytesseract.image_to_string(image, lang=lang, config=config))


def _load(path: Path) -> dict[CacheKey, str]:
    return {(int(row["page"]), (int(row["left"]), int(row["top"]), int(row["right"]), int(row["bottom"]))): row.get("text", "")
            for row in read_rows(path)}


def read_words(words: Mapping[WordKey, list[Occurrence]], render: Callable[[int], Bitmap], ocr: WordOcr) -> dict[WordKey, str]:
    cache = _load(ocr.cache)
    boxes = {key: (key[0], word_box(items)) for key, items in words.items()}
    missing = sorted({box for box in boxes.values() if box not in cache})
    images: list[tuple[CacheKey, Image.Image]] = []
    for page in sorted({page for page, _ in missing}):
        ink = render(page)
        images.extend(((page, box), word_image(ink, box)) for number, box in missing if number == page)
    with ThreadPoolExecutor(OCR_WORKERS) as pool:
        for cache_key, text in zip((key for key, _ in images), pool.map(lambda item: ocr.reader(item[1]), images)):
            cache[cache_key] = " ".join(text.split())
    if missing:
        ocr.cache.parent.mkdir(parents=True, exist_ok=True)
        write_rows(ocr.cache, ("page", "left", "top", "right", "bottom", "text"),
                   ((page, *box, text) for (page, box), text in sorted(cache.items())))
    return {key: cache[box] for key, box in boxes.items()}
