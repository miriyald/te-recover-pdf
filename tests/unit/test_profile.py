import json
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
    assert {"Priyaanka", "GowthamiThin", "AnupamaMedium"} <= DEFAULT_PROFILE.anu_fonts
    assert page_lines(_page("ABCDEF+Priyaanka"))[0][0].is_anu


def test_byte_decoding_round_trips_through_json(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    profile = FontProfile(frozenset({"Foo"}), 0.7, 0.3, byte_encoding="mac_roman", byte_overrides={0xC6: "Δ"})

    save_profile(path, profile)

    assert load_profile(path) == profile


def test_anu_bytes_decode_as_mac_roman_except_the_overrides() -> None:
    assert [DEFAULT_PROFILE.byte_char(byte) for byte in (0x3D, 0xB0, 0xC6, 0xD0, 0xDB)] == ["=", "∞", "Δ", "-", "¤"]


def test_type1_layout_loads_confirmed_bytes_over_matched_ones(tmp_path: Path) -> None:
    layout = tmp_path / "layout.tsv"
    layout.write_text("char\tcodepoint\tbyte\tscore\tmargin\tstatus\tconfirmed\n"
                      "V\t0056\t41\t0.9\t0.1\tsure\t\nW\t0057\t45\t0.9\t0.1\tlikely\t46\n%\t0025\t\t0.5\t0\tnone\t\n", encoding="utf-8")
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"anu_fonts": ["Foo"], "ascent": 0.7, "descent": 0.3, "type1_layout": str(layout),
                                "type1_plain_pages": [425]}), encoding="utf-8")

    profile = load_profile(path)

    assert profile.type1_codes == {"V": 0x41, "W": 0x46}
    assert profile.type1_plain_pages == {425}
    save_profile(tmp_path / "again.json", profile)
    assert load_profile(tmp_path / "again.json") == profile


def test_alternate_spellings_of_a_known_byte_become_its_anu_character() -> None:
    spellings = ["∆", "Ω", "–", "=", "క"]

    assert [DEFAULT_PROFILE.canonical(char) for char in spellings] == ["Δ", "Ω", "-", "=", "క"]


def test_char_byte_inverts_byte_char() -> None:
    assert [DEFAULT_PROFILE.char_byte(char) for char in ("=", "∞", "Δ", "-", "క")] == [0x3D, 0xB0, 0xC6, 0xD0, None]
