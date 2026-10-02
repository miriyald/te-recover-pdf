import logging
from pathlib import Path

import pytest

from anu_unicode.run_output import Manifest, archive_previous, read_manifest, write_manifest


def _manifest(pdf_sha256: str = "abc") -> Manifest:
    return Manifest(book="b", source="B.pdf", pdf_sha256=pdf_sha256, method="ocr-learning", mapping_sources={"m.tsv": "123"},
                    pages=2, coverage=1.0, unmapped_sequences=0, created="20261001T120000Z")


def test_manifest_round_trips(tmp_path: Path) -> None:
    write_manifest(tmp_path, _manifest())

    manifest = read_manifest(tmp_path)

    assert manifest is not None and manifest["created"] == "20261001T120000Z" and manifest["tool_version"]


def test_previous_output_moves_to_the_folder_named_by_its_creation_time(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    write_manifest(output, _manifest())

    target = archive_previous(output, lambda stamp: tmp_path / "archive" / stamp, "abc")

    assert target == tmp_path / "archive" / "20261001T120000Z"
    assert (target / "manifest.json").exists() and not output.exists()


def test_nothing_to_archive_on_a_first_run(tmp_path: Path) -> None:
    assert archive_previous(tmp_path / "missing", lambda stamp: tmp_path / stamp, "abc") is None


def test_a_changed_source_pdf_is_reported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    output = tmp_path / "output"
    output.mkdir()
    write_manifest(output, _manifest("old"))

    with caplog.at_level(logging.WARNING):
        archive_previous(output, lambda stamp: tmp_path / "archive" / stamp, "new")

    assert "source PDF changed" in caplog.text
