from pathlib import Path

from anu_unicode.ocr_learning.approve import approve_batch


def test_approve_copies_pages_to_verified_and_archives_batch(tmp_path: Path) -> None:
    batch = tmp_path / "temp" / "batch-6"
    batch.mkdir(parents=True)
    (batch / "page-6.unicode.txt").write_text("విషయసూచిక\n", encoding="utf-8")
    (batch / "page-10.unicode.txt").write_text("మహాభారతము\n", encoding="utf-8")
    (batch / "report.html").write_text("<html>", encoding="utf-8")

    pages = approve_batch(batch, tmp_path / "verified", tmp_path / "archive" / "batches")

    assert pages == [6, 10]
    assert (tmp_path / "verified" / "page-006.unicode.txt").read_text(encoding="utf-8") == "విషయసూచిక\n"
    assert (tmp_path / "verified" / "page-010.unicode.txt").exists()
    assert not batch.exists()
    assert (tmp_path / "archive" / "batches" / "batch-6" / "report.html").exists()
