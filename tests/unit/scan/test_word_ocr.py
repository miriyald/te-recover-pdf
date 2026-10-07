from pathlib import Path

import numpy as np
from PIL import Image

from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.ink import Bitmap
from anu_unicode.scan.word_ocr import WordOcr, read_words, word_box, word_image, words_of
from anu_unicode.scan.words import Band


def _occurrence(word: int, bbox: tuple[int, int, int, int], page: int = 4) -> Occurrence:
    return Occurrence(page, 1, word, 1, 7, Band.MAIN, bbox)


def test_a_word_box_spans_all_its_glyphs() -> None:
    assert word_box([_occurrence(1, (10, 20, 30, 60)), _occurrence(1, (35, 5, 50, 40))]) == (10, 5, 50, 60)


def test_occurrences_are_grouped_into_words_in_reading_order() -> None:
    first, second, third = _occurrence(1, (0, 0, 5, 5)), _occurrence(2, (9, 0, 12, 5)), _occurrence(1, (6, 0, 8, 5))

    assert list(words_of([second, first, third]).values()) == [[first, third], [second]]


def test_a_word_image_is_the_padded_crop_with_white_paper_and_black_ink() -> None:
    ink = np.zeros((100, 100), dtype=bool)
    ink[40:50, 40:60] = True

    image = word_image(ink, (40, 40, 60, 50))

    assert image.size == (20 + 2 * 10 + 2 * 20, 10 + 2 * 10 + 2 * 20)
    assert image.getpixel((0, 0)) == 255
    assert image.getpixel((image.width // 2, image.height // 2)) == 0


def test_words_are_read_once_and_then_come_from_the_cache(tmp_path: Path) -> None:
    calls: list[tuple[int, int]] = []
    rendered: list[int] = []

    def render(page: int) -> Bitmap:
        rendered.append(page)
        return np.zeros((100, 100), dtype=bool)

    def reader(image: Image.Image) -> str:
        calls.append(image.size)
        return " గోచి\n"

    words = words_of([_occurrence(1, (10, 10, 30, 30)), _occurrence(2, (40, 10, 60, 30))])
    ocr = WordOcr(reader, tmp_path / "word-ocr.tsv")

    first = read_words(words, render, ocr)
    second = read_words(words, render, ocr)

    assert list(first.values()) == ["గోచి", "గోచి"]
    assert second == first
    assert len(calls) == 2
    assert rendered == [4]
