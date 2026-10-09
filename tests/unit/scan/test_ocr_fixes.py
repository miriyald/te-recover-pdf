from pathlib import Path

import pytest

from anu_unicode.scan.ocr_fixes import fix_text, load_fixes


def test_only_whole_tokens_are_replaced() -> None:
    fixes = {"1": "।", "2": ":"}

    assert fix_text("సాధు 1 సాధు 193 అతిథిసాత్ 2 1తవ", fixes) == "సాధు । సాధు 193 అతిథిసాత్ : 1తవ"


def test_a_book_without_a_fixes_file_has_no_fixes(tmp_path: Path) -> None:
    assert not load_fixes(tmp_path / "ocr-fixes.tsv")


def test_a_token_is_fixed_even_when_ocr_wrapped_the_text_in_quotes() -> None:
    assert fix_text("'1 తవ", {"1": "।"}) == "। తవ"


def test_two_fixes_for_the_same_token_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "ocr-fixes.tsv").write_text("ocr\ttext\n1\t।\n1\t॥\n", encoding="utf-8")

    with pytest.raises(ValueError, match="'1' is fixed twice"):
        load_fixes(tmp_path / "ocr-fixes.tsv")


def test_fixes_are_read_from_the_books_mapping_file(tmp_path: Path) -> None:
    (tmp_path / "ocr-fixes.tsv").write_text("ocr\ttext\tnote\n1\t।\tdanda\n|\t।\t\n", encoding="utf-8")

    assert load_fixes(tmp_path / "ocr-fixes.tsv") == {"1": "।", "|": "।"}
