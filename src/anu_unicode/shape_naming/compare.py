from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from anu_unicode.convert import UNMAPPED_OPEN, Coverage, convert_anu
from anu_unicode.glyphs import Rect, page_lines, split_words
from anu_unicode.mapping import write_rows
from anu_unicode.ocr import OcrWord, best_match
from anu_unicode.ocr_learning.learn import Occurrence
from anu_unicode.ocr_learning.report import STYLE, _crop, _glyphs, _table, _telugu
from anu_unicode.profile import FontProfile
from anu_unicode.telugu import comparable

CANDIDATE_GAP = "candidate_gap"
NEW_WRONG = "new_wrong"
OLD_WRONG = "old_wrong"
HUMAN = "human"
VERDICTS = (NEW_WRONG, CANDIDATE_GAP, HUMAN, OLD_WRONG)
DIFF_COLUMNS = ("verdict", "count", "glyphs", "candidate", "reference", "candidate_votes", "reference_votes", "first_page")


@dataclass(frozen=True)
class PageWord:
    page: int
    bbox: Rect
    glyphs: str
    ocr: str | None


@dataclass
class Difference:
    glyphs: str
    candidate: str
    reference: str
    count: int = 0
    candidate_votes: int = 0
    reference_votes: int = 0
    first: PageWord | None = None

    @property
    def verdict(self) -> str:
        if UNMAPPED_OPEN in self.candidate:
            return CANDIDATE_GAP
        if self.candidate_votes and not self.reference_votes:
            return OLD_WRONG
        if self.reference_votes and not self.candidate_votes:
            return NEW_WRONG
        return HUMAN


@dataclass
class Comparison:
    words: int = 0
    differences: list[Difference] = field(default_factory=list)
    candidate_coverage: Coverage = field(default_factory=Coverage)
    reference_coverage: Coverage = field(default_factory=Coverage)


def page_words(page: pymupdf.Page, profile: FontProfile, ocr: list[OcrWord] | None, min_overlap: float) -> list[PageWord]:
    words = [word for line in page_lines(page, profile) for word in split_words(line)]
    return [
        PageWord(page.number + 1, word.bbox, word.text, match.text if (match := best_match(word.bbox, ocr or [], min_overlap)) else None)
        for word in words
    ]


def compare(words: Iterable[PageWord], candidate: Mapping[str, str], reference: Mapping[str, str]) -> Comparison:
    comparison = Comparison()
    groups: dict[tuple[str, str, str], Difference] = {}
    for word in words:
        comparison.words += 1
        new = convert_anu(word.glyphs, candidate, comparison.candidate_coverage)
        old = convert_anu(word.glyphs, reference, comparison.reference_coverage)
        if new == old:
            continue
        difference = groups.setdefault((word.glyphs, new, old), Difference(word.glyphs, new, old, first=word))
        difference.count += 1
        ocr = comparable(word.ocr) if word.ocr is not None else None
        difference.candidate_votes += ocr == comparable(new)
        difference.reference_votes += ocr == comparable(old)
    comparison.differences = sorted(groups.values(), key=lambda item: (VERDICTS.index(item.verdict), -item.count, item.glyphs))
    return comparison


def _crop_cell(document: pymupdf.Document, difference: Difference) -> str:
    first = difference.first
    if difference.verdict != HUMAN or first is None:
        return ""
    return _crop(document, Occurrence(first.page, first.bbox, first.glyphs, difference.candidate, first.ocr or ""))


def write_comparison(out: Path, comparison: Comparison, document: pymupdf.Document) -> None:
    out.mkdir(parents=True, exist_ok=True)
    differences = comparison.differences
    write_rows(out / "diff.tsv", DIFF_COLUMNS, (
        (item.verdict, item.count, item.glyphs, item.candidate, item.reference, item.candidate_votes, item.reference_votes,
         item.first.page if item.first else "")
        for item in differences
    ))
    summary = [
        [verdict, str(len(group)), str(sum(item.count for item in group))]
        for verdict in VERDICTS
        for group in [[item for item in differences if item.verdict == verdict]]
    ]
    rows = [
        [item.verdict, str(item.count), _glyphs(item.glyphs), _telugu(item.candidate), _telugu(item.reference),
         f"{item.candidate_votes} / {item.reference_votes}", str(item.first.page if item.first else ""), _crop_cell(document, item)]
        for item in differences
    ]
    coverage = (
        f"<p>{comparison.words} words compared. Coverage: candidate {comparison.candidate_coverage.ratio:.4%}, "
        f"reference {comparison.reference_coverage.ratio:.4%}.</p>"
    )
    body = (
        _table("Verdicts", ["verdict", "groups", "words"], summary)
        + _table("Differences", ["verdict", "count", "glyphs", "candidate", "reference", "OCR votes new / old", "page", "crop"], rows)
    )
    (out / "report.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>Shape mapping comparison</title><style>{STYLE}</style>{coverage}{body}",
        encoding="utf-8", newline="\n",
    )
