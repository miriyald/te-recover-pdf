from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from anu_unicode.glyphs import page_lines
from anu_unicode.profile import DEFAULT_PROFILE, FontProfile, load_profile, save_profile


def _page(font: str) -> MagicMock:
    chars = [{"c": "=", "bbox": (80, 85, 86, 100), "origin": (80, 100.0)}]
    line: dict[str, Any] = {"bbox": (80, 0, 86, 0), "spans": [{"font": font, "size": 20.0, "origin": (80, 100.0), "chars": chars}]}
    page = MagicMock()
    page.get_text.return_value = {"blocks": [{"lines": [line]}]}
    return page


def test_profile_round_trips_through_json(tmp_path: Path) -> None:
    path = tmp_path / "profiles" / "other.json"
    profile = FontProfile(frozenset({"Foo", "FooBold"}), 0.66, 0.34)

    save_profile(path, profile)

    assert load_profile(path) == profile
    assert path.read_bytes().endswith(b"}\n")


def test_profile_decides_which_fonts_are_telugu_and_how_tall_their_boxes_are() -> None:
    profile = FontProfile(frozenset({"Foo"}), ascent=0.5, descent=0.1)

    glyph = page_lines(_page("ABCDEF+Foo"), profile)[0][0]
    other = page_lines(_page("ABCDEF+Priyaanka"), profile)[0][0]

    assert glyph.is_anu and not other.is_anu
    assert (glyph.bbox[1], glyph.bbox[3]) == (90.0, 102.0)


def test_default_profile_is_the_anu_family() -> None:
    assert "Priyaanka" in DEFAULT_PROFILE.anu_fonts
    assert page_lines(_page("ABCDEF+Priyaanka"))[0][0].is_anu
