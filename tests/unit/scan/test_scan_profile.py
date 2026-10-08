import json
from pathlib import Path

import numpy as np
import pytest

from anu_unicode.scan.ink import Component
from anu_unicode.scan.profile import Grouping, HeightUnit, ScanProfile, load_scan_profile, unit_height


def _tall(height: int) -> Component:
    return Component((0, 0, 10, height), np.ones((height, 10), dtype=bool))


def test_a_book_without_a_profile_gets_the_validated_defaults(tmp_path: Path) -> None:
    assert load_scan_profile(tmp_path / "profile.json") == ScanProfile()


def test_a_profile_overrides_only_what_it_names(tmp_path: Path) -> None:
    (tmp_path / "profile.json").write_text(json.dumps({"grouping_unit": "letter", "word_gap": 0.38}), encoding="utf-8")

    profile = load_scan_profile(tmp_path / "profile.json")

    assert profile == ScanProfile(Grouping(grouping_unit=HeightUnit.LETTER, word_gap=0.38))


def test_numbers_and_units_are_converted_when_the_profile_is_loaded(tmp_path: Path) -> None:
    (tmp_path / "profile.json").write_text(json.dumps({"word_gap": "0.85", "shape_unit": "letter"}), encoding="utf-8")

    profile = load_scan_profile(tmp_path / "profile.json")

    assert (profile.grouping.word_gap, profile.shape_unit) == (0.85, HeightUnit.LETTER)


def test_a_badly_typed_number_fails_when_the_profile_is_loaded(tmp_path: Path) -> None:
    (tmp_path / "profile.json").write_text(json.dumps({"word_gap": "wide"}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_scan_profile(tmp_path / "profile.json")


def test_an_unknown_profile_setting_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "profile.json").write_text(json.dumps({"wordgap": 0.38, "grouping": {"word_gap": 0.85}}), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown settings: grouping, wordgap"):
        load_scan_profile(tmp_path / "profile.json")


def test_the_unit_height_is_the_median_or_the_letter_height() -> None:
    pieces = [_tall(height) for height in (10, 12, 40, 60, 62, 64)]

    assert (unit_height(pieces, HeightUnit.MEDIAN), unit_height(pieces, HeightUnit.LETTER)) == (50.0, 62.0)
