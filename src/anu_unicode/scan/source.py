from pathlib import Path

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


def read_occurrences(path: Path) -> list[Occurrence]:
    return [
        Occurrence(int(row["page"]), int(row["line"]), int(row["word"]), int(row["position"]), int(row["shape_id"]), Band(row["band"]),
                   (int(row["left"]), int(row["top"]), int(row["right"]), int(row["bottom"])), int(row.get("ink", 0)))
        for row in read_rows(path)
    ]
