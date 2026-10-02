from collections.abc import Iterable
from itertools import groupby
from pathlib import Path

from anu_unicode.glyphs import Glyph, Word
from anu_unicode.mapping import read_rows
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.words import Band

SHAPE_BASE = 0xF0000
SHAPE_LIMIT = 0xFFFFD


def shape_char(shape_id: int) -> str:
    code = SHAPE_BASE + shape_id
    if code > SHAPE_LIMIT:
        raise ValueError(f"shape id {shape_id} is outside the private use plane")
    return chr(code)


def shape_id_of(char: str) -> int:
    return ord(char) - SHAPE_BASE


def read_excluded(path: Path) -> frozenset[int]:
    return frozenset(int(row["shape_id"]) for row in read_rows(path))


def read_occurrences(path: Path) -> list[Occurrence]:
    return [
        Occurrence(int(row["page"]), int(row["line"]), int(row["word"]), int(row["position"]), int(row["shape_id"]), Band(row["band"]),
                   (int(row["left"]), int(row["top"]), int(row["right"]), int(row["bottom"])))
        for row in read_rows(path)
    ]


def _glyph(item: Occurrence, points_per_pixel: float) -> Glyph:
    left, top, right, bottom = (value * points_per_pixel for value in item.bbox)
    return Glyph(shape_char(item.shape_id), (left, top, right, bottom), left, is_anu=True)


def scan_words(occurrences: Iterable[Occurrence], points_per_pixel: float) -> list[Word]:
    ordered = sorted(occurrences, key=lambda item: (item.line, item.word, item.position))
    return [Word(tuple(_glyph(item, points_per_pixel) for item in glyphs))
            for _, glyphs in groupby(ordered, key=lambda item: (item.line, item.word))]
