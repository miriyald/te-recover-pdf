import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

import pymupdf

from anu_unicode.convert import Coverage, Segment, convert_segments, gaps, render
from anu_unicode.glyphs import Rect, Word, page_lines, split_words
from anu_unicode.mapping import MappingEntry, PageProgress, Proposal
from anu_unicode.ocr import OcrWord, best_match
from anu_unicode.profile import DEFAULT_PROFILE, FontProfile
from anu_unicode.solve import gap_candidates
from anu_unicode.telugu import comparable, is_telugu_word

MIN_DISTINCT_CONTEXTS = 2
MIN_OVERLAP = 0.5
MIN_SUSPECT_CONFIDENCE = 60.0

OcrFunction = Callable[[pymupdf.Page], list[OcrWord]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Occurrence:
    page_number: int
    bbox: Rect
    glyphs: str
    converted: str
    ocr_text: str


@dataclass
class PageResult:
    progress: PageProgress
    accepted: list[tuple[MappingEntry, Occurrence | None]] = field(default_factory=list)
    suspects: list[Occurrence] = field(default_factory=list)
    unresolved: list[Occurrence] = field(default_factory=list)


@dataclass
class LearningState:
    entries: dict[str, MappingEntry]
    pending: list[Proposal]
    profile: FontProfile = DEFAULT_PROFILE

    @property
    def mapping(self) -> dict[str, str]:
        return {glyphs: entry.unicode for glyphs, entry in self.entries.items()}

    def vote(self, glyphs: str, unicode: str, context: str, page_number: int, ocr_text: str) -> None:
        for proposal in self.pending:
            if (proposal.glyphs, proposal.unicode) == (glyphs, unicode):
                proposal.count += 1
                proposal.contexts.add(context)
                return
        self.pending.append(Proposal(glyphs, unicode, 1, page_number, ocr_text, {context}))

    def accept_consistent(self) -> list[MappingEntry]:
        by_glyphs: dict[str, list[Proposal]] = {}
        for proposal in self.pending:
            by_glyphs.setdefault(proposal.glyphs, []).append(proposal)
        accepted = [
            MappingEntry(proposals[0].glyphs, proposals[0].unicode, proposals[0].first_page, proposals[0].first_word)
            for glyphs, proposals in by_glyphs.items()
            if len(proposals) == 1 and len(proposals[0].contexts) >= MIN_DISTINCT_CONTEXTS and glyphs not in self.entries
        ]
        for entry in accepted:
            self.entries[entry.glyphs] = entry
        accepted_glyphs = {entry.glyphs for entry in accepted}
        self.pending = [proposal for proposal in self.pending if proposal.glyphs not in accepted_glyphs]
        return accepted


def _gap_index(segments: Sequence[Segment]) -> int | None:
    gap_indices = [index for index, (_, unicode) in enumerate(segments) if unicode is None]
    return gap_indices[0] if len(gap_indices) == 1 else None


def gap_context(segments: Sequence[Segment]) -> str:
    index = _gap_index(segments)
    if index is None:
        raise ValueError("context requires exactly one gap")
    before = segments[index - 1][1] if index > 0 else ""
    after = segments[index + 1][1] if index + 1 < len(segments) else ""
    return f"{before}|{after}"


def _converted(word: Word, mapping: dict[str, str]) -> str:
    return render(convert_segments(word.text, mapping), Coverage())


def _occurrence(page_number: int, word: Word, mapping: dict[str, str], ocr_text: str) -> Occurrence:
    return Occurrence(page_number, word.bbox, word.text, _converted(word, mapping), ocr_text)


def _unmapped_glyphs(words: Iterable[Word], mapping: dict[str, str]) -> int:
    return sum(len(gap) for word in words for gap in gaps(convert_segments(word.text, mapping)))


def _observe(page: pymupdf.Page, words: Iterable[Word], ocr: OcrFunction) -> list[tuple[Word, OcrWord]]:
    ocr_words = ocr(page)
    return [
        (word, match)
        for word in words
        for match in [best_match(word.bbox, ocr_words, MIN_OVERLAP)]
        if match is not None and is_telugu_word(match.text)
    ]


Accepted = list[tuple[MappingEntry, Occurrence | None]]


def _learn_until_stable(observed: Sequence[tuple[Word, OcrWord]], state: LearningState, page_number: int) -> Accepted:
    learned: Accepted = []
    voted: set[int] = set()
    while True:
        mapping = state.mapping
        word_segments = [convert_segments(word.text, mapping) for word, _ in observed]
        word_gaps = [gaps(segments) for segments in word_segments]
        for index, (segments, (_, ocr_word)) in enumerate(zip(word_segments, observed)):
            candidates = gap_candidates(segments, ocr_word.text)
            if index not in voted and len(candidates) == 1:
                voted.add(index)
                state.vote(word_gaps[index][0], candidates.pop(), gap_context(segments), page_number, ocr_word.text)
        accepted = state.accept_consistent()
        if not accepted:
            return learned
        for entry in accepted:
            trigger = next((word for (word, _), found in zip(observed, word_gaps) if entry.glyphs in found), None)
            learned.append((entry, _occurrence(page_number, trigger, state.mapping, entry.first_word) if trigger else None))


def _page_words(page: pymupdf.Page, profile: FontProfile) -> list[Word]:
    return [word for line in page_lines(page, profile) for word in split_words(line)]


def _classify(page: pymupdf.Page, words: Sequence[Word], mapping: dict[str, str], ocr: OcrFunction, result: PageResult) -> None:
    page_number = page.number + 1
    observed = {id(word): ocr_word for word, ocr_word in _observe(page, words, ocr)}
    for word in words:
        ocr_word = observed.get(id(word))
        occurrence = _occurrence(page_number, word, mapping, ocr_word.text if ocr_word else "")
        if gaps(convert_segments(word.text, mapping)):
            result.unresolved.append(occurrence)
        elif ocr_word and comparable(occurrence.converted) != comparable(ocr_word.text) and ocr_word.confidence >= MIN_SUSPECT_CONFIDENCE:
            result.suspects.append(occurrence)


def learn_page(page: pymupdf.Page, state: LearningState, ocr: OcrFunction) -> PageResult:
    page_number = page.number + 1
    words = _page_words(page, state.profile)
    glyph_count = sum(len(word.text) for word in words)
    unmapped_before = _unmapped_glyphs(words, state.mapping)
    if not unmapped_before:
        return PageResult(PageProgress(page_number, glyph_count, 0, 0, 0))
    observed = _observe(page, words, ocr)
    result = PageResult(PageProgress(page_number, glyph_count, unmapped_before, 0, 0), _learn_until_stable(observed, state, page_number))
    mapping = state.mapping
    _classify(page, words, mapping, lambda _: [ocr_word for _, ocr_word in observed], result)
    result.progress = PageProgress(page_number, glyph_count, unmapped_before, _unmapped_glyphs(words, mapping), len(result.accepted))
    logger.info("page learned", extra={"page": page_number, "unmapped_before": unmapped_before,
                                       "unmapped_after": result.progress.unmapped_after, "accepted": len(result.accepted)})
    return result


def review_page(page: pymupdf.Page, entries: dict[str, MappingEntry], ocr: OcrFunction,
                profile: FontProfile = DEFAULT_PROFILE) -> PageResult:
    page_number = page.number + 1
    words = _page_words(page, profile)
    mapping = {glyphs: entry.unicode for glyphs, entry in entries.items()}
    unmapped = _unmapped_glyphs(words, mapping)
    learned = [entry for entry in entries.values() if entry.first_page == page_number]
    result = PageResult(PageProgress(page_number, sum(len(word.text) for word in words), unmapped, unmapped, len(learned)))
    for entry in learned:
        trigger = next((word for word in words if entry.glyphs in (g for g, _ in convert_segments(word.text, mapping))), None)
        result.accepted.append((entry, _occurrence(page_number, trigger, mapping, entry.first_word) if trigger else None))
    if unmapped or learned:
        _classify(page, words, mapping, ocr, result)
    return result


def run_batch(pages: Iterable[pymupdf.Page], state: LearningState, ocr: OcrFunction, stop_after: int,
              on_page: Callable[[PageResult], None]) -> list[PageResult]:
    results: list[PageResult] = []
    for page in pages:
        results.append(learn_page(page, state, ocr))
        on_page(results[-1])
        if sum(len(result.accepted) for result in results) >= stop_after:
            break
    return results
