import argparse
from pathlib import Path

import pytest

from anu_unicode.scan.commands import gold_folder


def test_gold_folder_reads_numbered_pages_and_ignores_other_files(tmp_path: Path) -> None:
    (tmp_path / "page-201.txt").write_text("అతిథిసాత్", encoding="utf-8")
    (tmp_path / "page-51-draft.txt").write_text("draft", encoding="utf-8")
    (tmp_path / "p201-0.png").write_bytes(b"")

    assert gold_folder(str(tmp_path)) == {201: "అతిథిసాత్"}


def test_a_gold_folder_without_pages_is_an_argument_error(tmp_path: Path) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="no page-<number>.txt files"):
        gold_folder(str(tmp_path))
