from pathlib import Path

import pytest

from anu_unicode.layout import BookLayout, LayoutError, books


def test_book_folders_hold_input_output_state_and_intermediate() -> None:
    layout = BookLayout("vol-3", Path("files"), Path("archive"))

    assert layout.input == Path("files/vol-3/input")
    assert layout.output("shape-naming") == Path("files/vol-3/output/shape-naming")
    assert layout.intermediate("learn", "batch-1") == Path("files/vol-3/output/intermediate/learn/batch-1")
    assert layout.state == Path("files/vol-3/state")
    assert layout.archived_output("ocr-learning", "20261001T120000Z") == Path("archive/vol-3/ocr-learning/20261001T120000Z")
    assert layout.batches == Path("archive/vol-3/batches")


def test_input_pdf_is_the_only_pdf_in_input(tmp_path: Path) -> None:
    layout = BookLayout("book", tmp_path)
    layout.input.mkdir(parents=True)
    (layout.input / "Book.pdf").write_bytes(b"%PDF")

    assert layout.input_pdf() == layout.input / "Book.pdf"


def test_missing_or_ambiguous_input_is_an_error(tmp_path: Path) -> None:
    layout = BookLayout("book", tmp_path)
    layout.input.mkdir(parents=True)
    with pytest.raises(LayoutError, match="found 0"):
        layout.input_pdf()
    (layout.input / "a.pdf").write_bytes(b"%PDF")
    (layout.input / "b.pdf").write_bytes(b"%PDF")
    with pytest.raises(LayoutError, match="found 2"):
        layout.input_pdf()


def test_books_are_the_folders_with_an_input_folder(tmp_path: Path) -> None:
    (tmp_path / "one" / "input").mkdir(parents=True)
    (tmp_path / "stray").mkdir()

    assert [layout.slug for layout in books(tmp_path)] == ["one"]
