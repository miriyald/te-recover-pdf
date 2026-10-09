from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.ink import Bitmap
from anu_unicode.scan.word_ocr import WordOcr, ocr_cache_name, read_words, tesseract_word, word_box, word_image, words_of
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


def test_pages_read_before_an_interruption_stay_cached_and_are_not_read_again(tmp_path: Path) -> None:
    words = words_of([_occurrence(1, (10, 10, 30, 30), page=4), _occurrence(1, (10, 10, 30, 30), page=5)])
    pages: list[int] = []

    def render(page: int) -> Bitmap:
        pages.append(page)
        if page == 5 and len(pages) == 2:
            raise KeyboardInterrupt
        return np.zeros((100, 100), dtype=bool)

    ocr = WordOcr(lambda image: "కా", tmp_path / "word-ocr.tsv")
    with pytest.raises(KeyboardInterrupt):
        read_words(words, render, ocr)

    texts = read_words(words, render, ocr)

    assert pages == [4, 5, 5]
    assert list(texts.values()) == ["కా", "కా"]


def test_a_row_cut_off_by_a_kill_is_dropped_and_its_word_read_again(tmp_path: Path) -> None:
    cache = tmp_path / "word-ocr.tsv"
    cache.write_text("page\tleft\ttop\tright\tbottom\ttext\n4\t10\t10\t30\t30\tకా\n5\t10\t10\t30\t30\tక", encoding="utf-8")
    words = words_of([_occurrence(1, (10, 10, 30, 30), page=4), _occurrence(1, (10, 10, 30, 30), page=5)])
    read: list[int] = []

    def render(page: int) -> Bitmap:
        read.append(page)
        return np.zeros((100, 100), dtype=bool)

    texts = read_words(words, render, WordOcr(lambda image: "కాము", cache))

    assert list(texts.values()) == ["కా", "కాము"]
    assert read == [5]
    assert cache.read_text(encoding="utf-8").endswith("4\t10\t10\t30\t30\tకా\n5\t10\t10\t30\t30\tకాము\n")


def test_a_cache_cut_off_inside_its_header_starts_again_with_a_header(tmp_path: Path) -> None:
    cache = tmp_path / "word-ocr.tsv"
    cache.write_text("page\tleft\tto", encoding="utf-8")
    words = words_of([_occurrence(1, (10, 10, 30, 30))])
    ocr = WordOcr(lambda image: "కా", cache)

    read_words(words, lambda page: np.zeros((100, 100), dtype=bool), ocr)

    assert cache.read_text(encoding="utf-8") == "page\tleft\ttop\tright\tbottom\ttext\n4\t10\t10\t30\t30\tకా\n"
    assert list(read_words(words, lambda page: np.zeros((100, 100), dtype=bool), ocr).values()) == ["కా"]


def test_a_word_is_read_with_the_stock_telugu_model_unless_a_book_model_is_given(tmp_path: Path) -> None:
    image = Image.new("L", (10, 10), 255)
    with patch("anu_unicode.scan.word_ocr.pytesseract.image_to_string", return_value="కా") as read:
        tesseract_word(image, "tesseract", None)
        tesseract_word(image, "tesseract", tmp_path / "ocr" / "tel_ns.traineddata")

    assert [(call.kwargs["lang"], call.kwargs["config"]) for call in read.call_args_list] == [
        ("tel", "--psm 8"), ("tel_ns", f"--psm 8 --tessdata-dir {(tmp_path / 'ocr').as_posix()}")]


def test_each_model_has_its_own_cache_and_a_retrained_model_gets_a_new_one(tmp_path: Path) -> None:
    model = tmp_path / "tel_ns.traineddata"
    model.write_bytes(b"first")
    first = ocr_cache_name(model)
    model.write_bytes(b"second")

    assert ocr_cache_name(None) == "scan-word-ocr.tsv"
    assert first.startswith("scan-word-ocr-tel_ns-") and first.endswith(".tsv")
    assert ocr_cache_name(model) != first
