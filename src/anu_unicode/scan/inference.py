import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import product
from math import ceil
from pathlib import Path

from anu_unicode.convert import Coverage, convert_anu
from anu_unicode.mapping import read_rows, write_rows
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.source import shape_char
from anu_unicode.scan.word_ocr import WordKey
from anu_unicode.scan.words import Band
from anu_unicode.shape_naming.shapes import NOTHING
from anu_unicode.telugu import PRE_BASE, VIRAMA, comparable

SEED_VOTES = 4
ACCEPT_SHARE = 0.6
RELABEL_VOTES = 2
REFINE_SAMPLE = 40
MAX_UNKNOWN = 2
MAX_ROUNDS = 30
QUOTES = "'\"‘’“”"


def _letters(first: int, last: int) -> list[str]:
    return [chr(code) for code in range(first, last + 1) if unicodedata.category(chr(code)) == "Lo"]


CONSONANTS = _letters(0x0C15, 0x0C39)
VOWELS = _letters(0x0C05, 0x0C14)
SIGNS = list("ాిీుూృెేైొోౌ")
CANDIDATES = (
    [NOTHING, VIRAMA, *CONSONANTS, *VOWELS, *SIGNS, *"ంఃఁ", *"=-.,;:!?()", *"0123456789"]
    + [VIRAMA + consonant for consonant in CONSONANTS] + [PRE_BASE + VIRAMA + consonant for consonant in CONSONANTS]
    + [consonant + sign for consonant in CONSONANTS for sign in SIGNS] + [consonant + VIRAMA for consonant in CONSONANTS]
    + [PRE_BASE + sign for sign in SIGNS]
)


class Source(StrEnum):
    SEED = "seed"
    WORDS = "words"
    REVIEW = "review"


@dataclass(frozen=True)
class WordEvidence:
    shape_ids: tuple[int, ...]
    text: str


@dataclass(frozen=True)
class Label:
    unicode: str
    source: Source
    support: int
    agreement: float


def seed_labels(proposals: Mapping[int, tuple[str, int]]) -> dict[int, str]:
    return {shape_id: text for shape_id, (text, votes) in proposals.items() if votes >= SEED_VOTES and text in CANDIDATES}


def marks_of(occurrences: Iterable[Occurrence]) -> frozenset[int]:
    return frozenset(item.shape_id for item in occurrences if item.band is not Band.MAIN)


def word_evidence(words: Mapping[WordKey, list[Occurrence]], texts: Mapping[WordKey, str]) -> list[WordEvidence]:
    return [WordEvidence(tuple(item.shape_id for item in items), comparable_text(texts.get(key, "")))
            for key, items in words.items() if all(item.shape_id != EQUALS for item in items)]


def write_labels(path: Path, labels: Mapping[int, Label]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(path, ("shape_id", "unicode", "source", "support", "agreement"),
               ((shape_id, label.unicode, label.source, label.support, f"{label.agreement:.3f}")
                for shape_id, label in sorted(labels.items())))


def read_labels(path: Path) -> dict[int, Label]:
    return {int(row["shape_id"]): Label(row["unicode"], Source(row["source"]), int(row["support"]), float(row["agreement"]))
            for row in read_rows(path)}


def clean_ocr(text: str) -> str:
    return " ".join(text.split()).strip(QUOTES).strip()


def comparable_text(text: str) -> str:
    return comparable(unicodedata.normalize("NFC", clean_ocr(text))).strip(QUOTES).strip()


def spell(shape_ids: Sequence[int], labels: Mapping[int, str]) -> str:
    mapping = {shape_char(shape_id): "" if labels[shape_id] == NOTHING else labels[shape_id]
               for shape_id in set(shape_ids) if shape_id in labels}
    return convert_anu("".join(shape_char(shape_id) for shape_id in shape_ids), mapping, Coverage())


def render(shape_ids: Sequence[int], labels: Mapping[int, str]) -> str:
    return comparable_text(spell(shape_ids, labels))


def _pool(text: str) -> list[str]:
    allowed = set(text) | {PRE_BASE}
    return [candidate for candidate in CANDIDATES if candidate == NOTHING or set(candidate) <= allowed]


def _solve(word: WordEvidence, labels: Mapping[int, str], unknown: Sequence[int], marks: frozenset[int]) -> tuple[str, ...] | None:
    known = {shape_id: labels[shape_id] for shape_id in set(word.shape_ids) if shape_id not in unknown}
    fits = [option for option in product(_pool(word.text), repeat=len(unknown))
            if render(word.shape_ids, {**known, **dict(zip(unknown, option))}) == word.text]
    if len(fits) > 1:
        fits = [option for option in fits if all(label != NOTHING or shape_id in marks for shape_id, label in zip(unknown, option))]
    return fits[0] if len(fits) == 1 else None


def _winner(tally: Counter[str]) -> tuple[str, int] | None:
    best, count = tally.most_common(1)[0]
    return (best, count) if count >= ACCEPT_SHARE * sum(tally.values()) else None


@dataclass
class _State:
    words: Sequence[WordEvidence]
    marks: frozenset[int]
    labels: dict[int, str]
    sources: dict[int, Source]
    fixed: frozenset[int]

    def containing(self) -> dict[int, list[WordEvidence]]:
        by_id: dict[int, list[WordEvidence]] = defaultdict(list)
        for word in self.words:
            for shape_id in set(word.shape_ids):
                by_id[shape_id].append(word)
        return by_id

    def unknown(self, word: WordEvidence) -> list[int]:
        return sorted({shape_id for shape_id in word.shape_ids if shape_id not in self.labels})

    def learn(self) -> int:
        votes: dict[int, Counter[str]] = defaultdict(Counter)
        for word in self.words:
            unknown = self.unknown(word)
            if 1 <= len(unknown) <= MAX_UNKNOWN:
                solution = _solve(word, self.labels, unknown, self.marks)
                for shape_id, label in zip(unknown, solution or ()):
                    votes[shape_id][label] += 1
        learned = 0
        for shape_id, tally in votes.items():
            winner = _winner(tally)
            if winner:
                self.labels[shape_id], self.sources[shape_id] = winner[0], Source.WORDS
                learned += 1
        return learned

    def _leave_one_out(self, shape_id: int, words: list[WordEvidence]) -> Iterator[str]:
        for word in words[::ceil(len(words) / REFINE_SAMPLE)] if words else ():
            if not self.unknown(word) or self.unknown(word) == [shape_id]:
                solution = _solve(word, self.labels, [shape_id], self.marks)
                if solution:
                    yield solution[0]

    def refine(self, by_id: dict[int, list[WordEvidence]]) -> int:
        changed = 0
        for shape_id in [shape_id for shape_id in self.labels if shape_id not in self.fixed]:
            tally = Counter(self._leave_one_out(shape_id, by_id[shape_id]))
            winner = _winner(tally) if tally else None
            if winner and winner[0] != self.labels[shape_id] and winner[1] >= RELABEL_VOTES:
                self.labels[shape_id], self.sources[shape_id] = winner[0], Source.WORDS
                changed += 1
        return changed

    def label(self, shape_id: int, words: list[WordEvidence]) -> Label:
        complete = [word for word in words if not self.unknown(word)]
        agreeing = sum(render(word.shape_ids, self.labels) == word.text for word in complete)
        source = self.sources[shape_id]
        if source is Source.REVIEW:
            return Label(self.labels[shape_id], source, 0, 0.0)
        return Label(self.labels[shape_id], source, agreeing, agreeing / len(complete) if complete else 0.0)


def infer(words: Sequence[WordEvidence], seeds: Mapping[int, str], decisions: Mapping[int, str], marks: frozenset[int]) -> dict[int, Label]:
    evidence = [word for word in words if word.text]
    state = _State(evidence, marks, {**seeds, **decisions},
                   {**{shape_id: Source.SEED for shape_id in seeds}, **{shape_id: Source.REVIEW for shape_id in decisions}},
                   frozenset(decisions))
    by_id = state.containing()
    for _ in range(MAX_ROUNDS):
        if not state.learn() + state.refine(by_id):
            break
    return {shape_id: state.label(shape_id, by_id[shape_id]) for shape_id in state.labels if shape_id in by_id or shape_id in decisions}
