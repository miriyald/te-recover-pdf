import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from anu_unicode.glyphs import Rect

DPI = 300


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float
    bbox: Rect


def ocr_page(image: Image.Image, scale: float, tesseract_cmd: str) -> list[OcrWord]:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    data = pytesseract.image_to_data(image, lang="tel", output_type=pytesseract.Output.DICT)
    return [
        OcrWord(
            text=text.strip(),
            confidence=float(confidence),
            bbox=(left / scale, top / scale, (left + width) / scale, (top + height) / scale),
        )
        for text, confidence, left, top, width, height in zip(
            data["text"], data["conf"], data["left"], data["top"], data["width"], data["height"]
        )
        if text.strip()
    ]


def ocr_pdf_page(page: pymupdf.Page, tesseract_cmd: str) -> list[OcrWord]:
    image = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY).pil_image()
    return ocr_page(image, DPI / 72, tesseract_cmd)


@dataclass
class OcrCache:
    directory: Path
    tesseract_cmd: str
    calls: int = 0
    hits: int = 0

    def __call__(self, page: pymupdf.Page) -> list[OcrWord]:
        path = self.directory / f"page-{page.number + 1:03d}.json"
        if path.exists():
            self.hits += 1
            return [OcrWord(item["text"], item["confidence"], tuple(item["bbox"])) for item in json.loads(path.read_text(encoding="utf-8"))]
        self.calls += 1
        words = ocr_pdf_page(page, self.tesseract_cmd)
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(word) for word in words], ensure_ascii=False), encoding="utf-8")
        return words


def _area(rect: Rect) -> float:
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def overlap_ratio(first: Rect, second: Rect) -> float:
    intersection = (max(first[0], second[0]), max(first[1], second[1]), min(first[2], second[2]), min(first[3], second[3]))
    union = _area(first) + _area(second) - _area(intersection)
    return _area(intersection) / union if union else 0.0


def best_match(bbox: Rect, words: list[OcrWord], min_overlap: float) -> OcrWord | None:
    scored = [(overlap_ratio(bbox, word.bbox), word) for word in words]
    score, word = max(scored, key=lambda item: item[0], default=(0.0, None))
    return word if score >= min_overlap else None
