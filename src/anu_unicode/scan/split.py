from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from anu_unicode.scan.catalog import MAX_THICK_BLOB, thick_blob
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import Label, Source, WordEvidence, comparable_text, solve
from anu_unicode.scan.ink import Bitmap
from anu_unicode.scan.names import Speller
from anu_unicode.scan.word_ocr import WordKey

SPLIT_AGREEMENT = 0.8
SPLIT_WORDS = 5
SPLIT_SHARE = 0.25


@dataclass(frozen=True)
class Mixed:
    shape_id: int
    keep: str
    other: str
    kept: int
    other_count: int


@dataclass(frozen=True)
class Division:
    mixed: Mixed
    move: tuple[Occurrence, ...]


def readings(words: Mapping[WordKey, list[Occurrence]], texts: Mapping[WordKey, str], labels: Mapping[int, Label], speller: Speller,
             marks: frozenset[int]) -> dict[int, dict[Occurrence, str]]:
    names = {shape_id: label.name for shape_id, label in labels.items()}
    candidates = {shape_id for shape_id, label in labels.items() if label.agreement < SPLIT_AGREEMENT}
    found: dict[int, dict[Occurrence, str]] = defaultdict(dict)
    for key, items in words.items():
        text = comparable_text(texts.get(key, ""))
        shape_ids = tuple(item.shape_id for item in items)
        if not text or EQUALS in shape_ids or not all(shape_id in names for shape_id in shape_ids):
            continue
        for item in items:
            if item.shape_id in candidates:
                solution = solve(WordEvidence(shape_ids, text), names, [item.shape_id], speller, marks)
                if solution:
                    found[item.shape_id][item] = solution[0]
    return dict(found)


def find_mixed(by_id: Mapping[int, Mapping[Occurrence, str]], labels: Mapping[int, Label]) -> list[Mixed]:
    mixed = []
    for shape_id, read in sorted(by_id.items()):
        top = Counter(read.values()).most_common(2)
        if len(top) < 2 or top[1][1] < SPLIT_WORDS or top[1][1] < SPLIT_SHARE * len(read):
            continue
        decided = labels[shape_id].source is Source.REVIEW and labels[shape_id].name in (top[0][0], top[1][0])
        keep = labels[shape_id].name if decided else top[0][0]
        (kept, kept_count), (other, other_count) = top if top[0][0] == keep else top[::-1]
        mixed.append(Mixed(shape_id, kept, other, kept_count, other_count))
    return mixed


def _template(canvases: Sequence[Bitmap]) -> Bitmap:
    return np.asarray(np.mean(canvases, axis=0) >= 0.5, dtype=np.bool_)


def divide(mixed: Mixed, canvases: Mapping[Occurrence, Bitmap], read: Mapping[Occurrence, str]) -> Division | None:
    keep = _template([canvas for item, canvas in canvases.items() if read.get(item) == mixed.keep])
    other = _template([canvas for item, canvas in canvases.items() if read.get(item) == mixed.other])
    if thick_blob(other, keep) <= MAX_THICK_BLOB:
        return None
    return Division(mixed, tuple(item for item, canvas in canvases.items() if thick_blob(canvas, other) < thick_blob(canvas, keep)))
