import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import groupby

from anu_unicode.convert import UNMAPPED_OPEN
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import OCR_NOISE, Label, Source, clean_ocr, comparable_text
from anu_unicode.scan.names import Speller
from anu_unicode.scan.source import SHAPE_BASE, SHAPE_LIMIT, shape_id_of
from anu_unicode.scan.word_ocr import WordKey

STRONG_AGREEMENT = 0.8
DEPENDENT_SIGNS = frozenset({"Mn", "Mc"})
TELUGU = ("ఀ", "౿")
SHAPE_CHAR = re.compile(f"[{chr(SHAPE_BASE)}-{chr(SHAPE_LIMIT)}]")


class Choice(StrEnum):
    AGREED = "agreed"
    REVIEWED = "reviewed"
    EQUALS = "equals"
    WORD_OCR = "word_ocr"
    GAP = "gap"
    UNREAD = "unread"


@dataclass(frozen=True)
class Written:
    keys: tuple[WordKey, ...]
    text: str
    choices: tuple[Choice, ...]


@dataclass
class ScanText:
    written: list[list[Written]] = field(default_factory=list)
    choices: Counter[Choice] = field(default_factory=Counter)
    disagreements: list[tuple[WordKey, str, str]] = field(default_factory=list)

    @property
    def lines(self) -> list[str]:
        return [" ".join(word.text for word in line) for line in self.written]


def readable(text: str) -> str:
    return SHAPE_CHAR.sub(lambda match: f"#{shape_id_of(match.group())}", text)


@dataclass(frozen=True)
class Reading:
    labels: Mapping[int, Label]
    names: Mapping[int, str]
    speller: Speller


def equals_word(items: list[Occurrence]) -> bool:
    return all(item.shape_id == EQUALS for item in items)


def _choose(key: WordKey, items: list[Occurrence], reading: Reading, ocr: str, page: ScanText) -> tuple[str, Choice]:
    if equals_word(items):
        return "=", Choice.EQUALS
    shape_ids = [item.shape_id for item in items]
    ocr = clean_ocr(ocr)
    labels = reading.labels
    ours = reading.speller.spell(shape_ids, reading.names)
    complete = UNMAPPED_OPEN not in ours
    if complete and comparable_text(ours) == comparable_text(ocr):
        return ours, Choice.AGREED
    reviewed = [labels[shape_id].source is Source.REVIEW for shape_id in shape_ids] if complete else []
    if reviewed and (all(reviewed) or (any(reviewed) and ocr and _strong_neighbours(shape_ids, labels))):
        return ours, Choice.REVIEWED
    if complete and ocr:
        page.disagreements.append((key, ours, ocr))
    if ocr:
        return ocr, Choice.WORD_OCR
    if complete:
        return "", Choice.UNREAD
    return readable(ours), Choice.GAP


def _word(key: WordKey, items: list[Occurrence], reading: Reading, ocr: str, page: ScanText) -> Written:
    text, choice = _choose(key, items, reading, ocr, page)
    page.choices[choice] += 1
    return Written((key,), text, (choice,))


def _strong_neighbours(shape_ids: list[int], labels: Mapping[int, Label]) -> bool:
    return all(labels[shape_id].source is Source.REVIEW or labels[shape_id].agreement >= STRONG_AGREEMENT for shape_id in shape_ids)


def _starts_dependent(text: str) -> bool:
    return unicodedata.category(text[0]) in DEPENDENT_SIGNS


def _ends_telugu(text: str) -> bool:
    return bool(text) and TELUGU[0] <= text[-1] <= TELUGU[1]


def _joined(line: list[Written]) -> list[Written]:
    words: list[Written] = []
    for word in line:
        host = words[-1].text.rstrip("".join(OCR_NOISE)) if words else ""
        if _starts_dependent(word.text) and _ends_telugu(host):
            words[-1] = Written(words[-1].keys + word.keys, host + word.text, words[-1].choices + word.choices)
        else:
            words.append(word)
    return words


def convert_scan_page(words: Mapping[WordKey, list[Occurrence]], labels: Mapping[int, Label], texts: Mapping[WordKey, str],
                      speller: Speller) -> ScanText:
    reading = Reading(labels, {shape_id: label.name for shape_id, label in labels.items()}, speller)
    page = ScanText()
    for _, line in groupby(sorted(words), key=lambda key: key[:2]):
        written = (_word(key, words[key], reading, texts.get(key, ""), page) for key in line)
        page.written.append(_joined([word for word in written if word.text]))
    return page
