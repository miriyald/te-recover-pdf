from unittest.mock import MagicMock, patch

from anu_unicode.ocr import OcrWord, best_match, ocr_page, overlap_ratio


def test_overlap_ratio_is_intersection_over_union() -> None:
    ratio = overlap_ratio((0, 0, 10, 10), (5, 0, 15, 10))

    assert ratio == 50 / 150


def test_best_match_ignores_words_below_threshold() -> None:
    words = [OcrWord("మ", 90, (0, 0, 10, 10)), OcrWord("న", 90, (50, 0, 60, 10))]

    assert best_match((1, 0, 11, 10), words, 0.5) == words[0]
    assert best_match((30, 0, 40, 10), words, 0.5) is None


def test_ocr_page_scales_boxes_and_drops_empty_text() -> None:
    data = {"text": ["", "మము"], "conf": [-1, 95], "left": [0, 30], "top": [0, 60], "width": [0, 60], "height": [0, 30]}
    with patch("anu_unicode.ocr.pytesseract") as tesseract:
        tesseract.image_to_data.return_value = data

        words = ocr_page(MagicMock(), scale=3.0, tesseract_cmd="tesseract")

    assert words == [OcrWord("మము", 95.0, (10.0, 20.0, 30.0, 30.0))]
