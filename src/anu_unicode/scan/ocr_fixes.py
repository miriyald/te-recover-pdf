from collections.abc import Mapping
from pathlib import Path

from anu_unicode.mapping import read_rows
from anu_unicode.scan.inference import clean_ocr


def load_fixes(path: Path) -> dict[str, str]:
    fixes: dict[str, str] = {}
    for row in read_rows(path):
        if row["ocr"] in fixes:
            raise ValueError(f"{path}: {row['ocr']!r} is fixed twice")
        fixes[row["ocr"]] = row["text"]
    return fixes


def fix_text(text: str, fixes: Mapping[str, str]) -> str:
    return " ".join(fixes.get(token, token) for token in clean_ocr(text).split())
