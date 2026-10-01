from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from anu_unicode.convert import UNMAPPED_OPEN
from anu_unicode.glyphs import Rect
from anu_unicode.ocr import OcrWord, best_match

QUOTES = str.maketrans({"“": "‘‘", "”": "’’"})


def edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, expected in enumerate(reference, start=1):
        current = [row]
        for column, actual in enumerate(hypothesis, start=1):
            current.append(min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def error_rate(reference: Sequence[str], hypothesis: Sequence[str]) -> float:
    return edit_distance(reference, hypothesis) / len(reference) if reference else 0.0


@dataclass(frozen=True)
class WordComparison:
    converted: str
    ocr: str | None
    confidence: float | None
    ocr_bbox: Rect | None = None

    @property
    def disagrees(self) -> bool:
        return self.ocr is not None and self.ocr.translate(QUOTES) != self.converted.translate(QUOTES)


def compare_words(converted: Iterable[tuple[Rect, str]], ocr: list[OcrWord], min_overlap: float) -> list[WordComparison]:
    comparisons = []
    for bbox, text in converted:
        match = best_match(bbox, ocr, min_overlap)
        comparisons.append(WordComparison(text, match.text, match.confidence, match.bbox) if match else WordComparison(text, None, None))
    return comparisons


def character_confusions(ocr: str, converted: str) -> Counter[tuple[str, str]]:
    ocr, converted = ocr.translate(QUOTES), converted.translate(QUOTES)
    matcher = SequenceMatcher(None, ocr, converted, autojunk=False)
    return Counter((ocr[a0:a1], converted[b0:b1]) for tag, a0, a1, b0, b1 in matcher.get_opcodes() if tag == "replace")


@dataclass
class PageQuality:
    page: int
    words: int = 0
    matched: int = 0
    disagreements: int = 0
    unresolved: int = 0
    agreeing_confidence_total: float = 0.0
    disagreeing_confidence_total: float = 0.0
    confusions: Counter[tuple[str, str]] = field(default_factory=Counter)

    @property
    def unmatched(self) -> int:
        return self.words - self.matched

    @property
    def agreements(self) -> int:
        return self.matched - self.disagreements

    @property
    def agreement_rate(self) -> float:
        return self.agreements / self.matched if self.matched else 1.0

    @property
    def mean_confidence_agreeing(self) -> float:
        return self.agreeing_confidence_total / self.agreements if self.agreements else 0.0

    @property
    def mean_confidence_disagreeing(self) -> float:
        return self.disagreeing_confidence_total / self.disagreements if self.disagreements else 0.0


def page_quality(page: int, comparisons: Iterable[WordComparison]) -> PageQuality:
    result = PageQuality(page)
    for item in comparisons:
        result.words += 1
        result.unresolved += UNMAPPED_OPEN in item.converted
        if item.ocr is None or item.confidence is None:
            continue
        result.matched += 1
        if item.disagrees:
            result.disagreements += 1
            result.disagreeing_confidence_total += item.confidence
            result.confusions.update(character_confusions(item.ocr, item.converted))
        else:
            result.agreeing_confidence_total += item.confidence
    return result


def combine(pages: Iterable[PageQuality]) -> PageQuality:
    total = PageQuality(0)
    for item in pages:
        total.words += item.words
        total.matched += item.matched
        total.disagreements += item.disagreements
        total.unresolved += item.unresolved
        total.agreeing_confidence_total += item.agreeing_confidence_total
        total.disagreeing_confidence_total += item.disagreeing_confidence_total
        total.confusions.update(item.confusions)
    return total


@dataclass(frozen=True)
class GroundTruthQuality:
    page: int
    reference_words: int
    converted_word_errors: int
    ocr_word_errors: int
    converted_word_error_rate: float
    ocr_word_error_rate: float
    converted_character_error_rate: float
    ocr_character_error_rate: float


def ground_truth_quality(page: int, reference: str, converted: str, ocr: str) -> GroundTruthQuality:
    reference_words, converted_words, ocr_words = reference.split(), converted.split(), ocr.split()
    reference_text, converted_text, ocr_text = " ".join(reference_words), " ".join(converted_words), " ".join(ocr_words)
    return GroundTruthQuality(
        page,
        len(reference_words),
        edit_distance(reference_words, converted_words),
        edit_distance(reference_words, ocr_words),
        error_rate(reference_words, converted_words),
        error_rate(reference_words, ocr_words),
        error_rate(reference_text, converted_text),
        error_rate(reference_text, ocr_text),
    )
