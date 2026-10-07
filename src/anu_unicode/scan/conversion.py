import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import groupby

from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import Label, Source, clean_ocr, comparable_text, spell
from anu_unicode.scan.source import SHAPE_BASE, SHAPE_LIMIT, shape_id_of
from anu_unicode.scan.word_ocr import WordKey

SHAPE_CHAR = re.compile(f"[{chr(SHAPE_BASE)}-{chr(SHAPE_LIMIT)}]")


class Choice(StrEnum):
    AGREED = "agreed"
    REVIEWED = "reviewed"
    EQUALS = "equals"
    WORD_OCR = "word_ocr"
    GAP = "gap"


@dataclass
class ScanText:
    lines: list[str] = field(default_factory=list)
    choices: Counter[Choice] = field(default_factory=Counter)
    disagreements: list[tuple[WordKey, str, str]] = field(default_factory=list)


def readable(text: str) -> str:
    return SHAPE_CHAR.sub(lambda match: f"#{shape_id_of(match.group())}", text)


def _word(key: WordKey, items: list[Occurrence], labels: Mapping[int, Label], ocr: str, page: ScanText) -> str:
    shape_ids = [item.shape_id for item in items]
    if all(shape_id == EQUALS for shape_id in shape_ids):
        page.choices[Choice.EQUALS] += 1
        return "="
    ocr = clean_ocr(ocr)
    ours = spell(shape_ids, {shape_id: label.unicode for shape_id, label in labels.items()})
    complete = all(shape_id in labels for shape_id in shape_ids)
    if complete and comparable_text(ours) == comparable_text(ocr):
        page.choices[Choice.AGREED] += 1
        return ours
    if complete and any(labels[shape_id].source is Source.REVIEW for shape_id in shape_ids):
        page.choices[Choice.REVIEWED] += 1
        return ours
    if complete:
        page.disagreements.append((key, ours, ocr))
    if ocr:
        page.choices[Choice.WORD_OCR] += 1
        return ocr
    page.choices[Choice.GAP] += 1
    return readable(ours)


def convert_scan_page(words: Mapping[WordKey, list[Occurrence]], labels: Mapping[int, Label], texts: Mapping[WordKey, str]) -> ScanText:
    page = ScanText()
    for _, line in groupby(sorted(words), key=lambda key: key[:2]):
        page.lines.append(" ".join(_word(key, words[key], labels, texts.get(key, ""), page) for key in line))
    return page
