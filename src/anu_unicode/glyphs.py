from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pymupdf

from anu_unicode.profile import DEFAULT_PROFILE, FontProfile

BASELINE_TOLERANCE = 2.0
ZERO_WIDTH = 0.5
SYMBOL_BASE = 0xF000
SYMBOL_CODES = range(0xF020, 0xF100)

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Glyph:
    char: str
    bbox: Rect
    origin_x: float
    is_anu: bool

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]


@dataclass(frozen=True)
class Word:
    glyphs: tuple[Glyph, ...]

    @property
    def text(self) -> str:
        return "".join(glyph.char for glyph in self.glyphs)

    @property
    def units(self) -> list[str]:
        units: list[str] = []
        for glyph in self.glyphs:
            if glyph.width < ZERO_WIDTH and units:
                units[-1] += glyph.char
            else:
                units.append(glyph.char)
        return units

    @property
    def bbox(self) -> Rect:
        return (
            min(glyph.bbox[0] for glyph in self.glyphs),
            min(glyph.bbox[1] for glyph in self.glyphs),
            max(glyph.bbox[2] for glyph in self.glyphs),
            max(glyph.bbox[3] for glyph in self.glyphs),
        )


def font_family(font_name: str) -> str:
    return font_name.split("+")[-1].split(",")[0]


def _char(char: str, decode: Callable[[int], str]) -> str:
    return decode(ord(char) - SYMBOL_BASE) if ord(char) in SYMBOL_CODES else char


def symbol_text(text: str, profile: FontProfile) -> str | None:
    codes = [profile.char_byte(char) for char in text]
    return None if None in codes else "".join(chr(SYMBOL_BASE + code) for code in codes if code is not None)


def _anu_bbox(char: dict[str, Any], size: float, profile: FontProfile) -> Rect:
    baseline = char["origin"][1]
    return (char["bbox"][0], baseline - profile.ascent * size, char["bbox"][2], baseline + profile.descent * size)


def _anu_char(char: str, profile: FontProfile, translated: bool) -> str:
    if ord(char) in SYMBOL_CODES:
        return profile.byte_char(ord(char) - SYMBOL_BASE)
    if translated and char in profile.type1_codes:
        return profile.byte_char(profile.type1_codes[char])
    return profile.canonical(char)


def _span_glyphs(span: dict[str, Any], profile: FontProfile, type1: frozenset[str]) -> list[Glyph]:
    family = font_family(span["font"])
    if family not in profile.anu_fonts:
        return [Glyph(_char(char["c"], chr), tuple(char["bbox"]), char["origin"][0], is_anu=False) for char in span["chars"]]
    translated = family in type1
    return [Glyph(_anu_char(char["c"], profile, translated), _anu_bbox(char, span["size"], profile), char["origin"][0], is_anu=True)
            for char in span["chars"]]


def font_families(page: pymupdf.Page, kind: str) -> frozenset[str]:
    return frozenset(font_family(font[3]) for font in page.get_fonts() if font[2] == kind)


def type3_families(page: pymupdf.Page) -> frozenset[str]:
    return font_families(page, "Type3")


def page_lines(page: pymupdf.Page, profile: FontProfile = DEFAULT_PROFILE) -> list[list[Glyph]]:
    undecodable = type3_families(page)
    type1 = font_families(page, "Type1") if profile.type1_codes and page.number + 1 not in profile.type1_plain_pages else frozenset()
    raw_lines = [
        (spans[0]["origin"][1], line["bbox"][0], [glyph for span in spans for glyph in _span_glyphs(span, profile, type1)])
        for block in page.get_text("rawdict")["blocks"]
        for line in block.get("lines", [])
        if (spans := [span for span in line["spans"] if font_family(span["font"]) not in undecodable])
    ]
    raw_lines.sort(key=lambda item: item[0])
    rows: list[list[tuple[float, float, list[Glyph]]]] = []
    for raw_line in raw_lines:
        if rows and raw_line[0] - rows[-1][0][0] <= BASELINE_TOLERANCE:
            rows[-1].append(raw_line)
        else:
            rows.append([raw_line])
    return [_join_pieces(sorted(row, key=lambda item: item[1])) for row in rows]


def _join_pieces(pieces: list[tuple[float, float, list[Glyph]]]) -> list[Glyph]:
    joined: list[Glyph] = []
    for _, _, glyphs in pieces:
        if joined:
            joined.append(Glyph(" ", glyphs[0].bbox, glyphs[0].origin_x, is_anu=False))
        joined.extend(glyphs)
    return joined


def split_words(line: list[Glyph]) -> list[Word]:
    words: list[Word] = []
    current: list[Glyph] = []
    for glyph in line + [Glyph(" ", (0, 0, 0, 0), 0, is_anu=False)]:
        if glyph.is_anu and glyph.char != " ":
            current.append(glyph)
        elif current:
            words.append(Word(tuple(current)))
            current = []
    return words
