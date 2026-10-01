from pathlib import Path
from unittest.mock import MagicMock, patch

from anu_unicode.ocr import OcrCache, OcrWord


def test_each_page_is_ocred_once_then_served_from_cache(tmp_path: Path) -> None:
    page = MagicMock()
    page.number = 5
    words = [OcrWord("మహాభారతము", 94.0, (1.0, 2.0, 3.0, 4.0))]
    cache = OcrCache(tmp_path, "tesseract")
    with patch("anu_unicode.ocr.ocr_pdf_page", return_value=words) as ocr:

        first = cache(page)
        second = OcrCache(tmp_path, "tesseract")(page)

    ocr.assert_called_once()
    assert first == second == words
    assert (cache.calls, cache.hits) == (1, 0)
    assert (tmp_path / "page-006.json").exists()
