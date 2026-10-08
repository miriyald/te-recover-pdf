import argparse
from pathlib import Path

import numpy as np
import pytest

from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, shape_of
from anu_unicode.scan.commands import CatalogUnitError, checked_catalog, existing_file, gold_folder
from anu_unicode.scan.ink import Component
from anu_unicode.scan.profile import HeightUnit, ScanProfile
from anu_unicode.scan.words import Band


def test_gold_folder_reads_numbered_pages_and_ignores_other_files(tmp_path: Path) -> None:
    (tmp_path / "page-201.txt").write_text("అతిథిసాత్", encoding="utf-8")
    (tmp_path / "page-51-draft.txt").write_text("draft", encoding="utf-8")
    (tmp_path / "p201-0.png").write_bytes(b"")

    assert gold_folder(str(tmp_path)) == {201: "అతిథిసాత్"}


def test_a_profile_path_given_on_the_command_line_must_exist(tmp_path: Path) -> None:
    (tmp_path / "profile.json").write_text("{}", encoding="utf-8")

    assert existing_file(str(tmp_path / "profile.json")) == tmp_path / "profile.json"
    with pytest.raises(argparse.ArgumentTypeError, match="no such file"):
        existing_file(str(tmp_path / "profle.json"))


def test_a_catalog_scaled_by_another_unit_than_the_profile_is_refused(tmp_path: Path) -> None:
    catalog = ShapeCatalog(Thresholds(0.2, 0.2, 0.25))
    catalog.assign(shape_of(Component((0, 0, 50, 50), np.ones((50, 50), dtype=bool)), Band.MAIN, 50.0))
    catalog.save(tmp_path / "catalog.npz")

    with pytest.raises(CatalogUnitError, match="--rebuild"):
        checked_catalog(tmp_path / "catalog.npz", ScanProfile(shape_unit=HeightUnit.LETTER))


def test_a_gold_folder_without_pages_is_an_argument_error(tmp_path: Path) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="no page-<number>.txt files"):
        gold_folder(str(tmp_path))
