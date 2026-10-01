import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from anu_unicode.convert import Coverage, Segment, convert_segments, render
from anu_unicode.glyphs import Word
from anu_unicode.learn import LearningState
from anu_unicode.mapping import MappingEntry
from anu_unicode.solve import solve_confirmed
from anu_unicode.telugu import comparable

GAP = re.compile("⟦(.*?)⟧")
SEPARATOR = re.compile(r"\s*=\s*|\t+")
MAX_PASSES = 3
CORRECTION = "correction of mapped text: needs review"


@dataclass(frozen=True)
class Confirmation:
    shown: str
    correct: str


@dataclass
class ConfirmationResult:
    confirmation: Confirmation
    status: str
    page_number: int | None = None
    added: tuple[MappingEntry, ...] = ()
    overrides: str = ""


def _split(line: str) -> list[str]:
    gaps = iter(GAP.findall(line))
    masked = GAP.sub("⟦⟧", line)
    parts = [part.strip() for part in SEPARATOR.split(masked.strip()) if part.strip()]
    return [re.sub("⟦⟧", lambda _: f"⟦{next(gaps)}⟧", part) for part in parts]


def parse_confirmations(text: str) -> list[Confirmation]:
    confirmations = []
    for line in text.splitlines():
        parts = _split(line)
        if len(parts) == 2:
            confirmations.append(Confirmation(parts[0], unicodedata.normalize("NFC", parts[1])))
    return confirmations


def _rendered(word: Word, mapping: dict[str, str]) -> str:
    return render(convert_segments(word.text, mapping), Coverage())


def _overrides(segments: Sequence[Segment], glyph_keys: Iterable[str]) -> str:
    absorbed: list[str] = []
    for key in glyph_keys:
        for start in range(len(segments)):
            end = next((end for end in range(start + 1, len(segments) + 1)
                        if "".join(glyphs for glyphs, _ in segments[start:end]) == key), None)
            if end is not None:
                absorbed.extend(unicode for _, unicode in segments[start:end] if unicode is not None)
                break
    return " ".join(absorbed)


def _apply_one(confirmation: Confirmation, words: Sequence[tuple[int, Word]], state: LearningState,
               reviewed_mapping: dict[str, str]) -> ConfirmationResult:
    gap_glyphs = GAP.findall(confirmation.shown)
    candidates = [(page, word) for page, word in words if all(glyphs in word.text for glyphs in gap_glyphs)]
    for page, word in candidates:
        if comparable(_rendered(word, state.mapping)) == comparable(confirmation.correct):
            return ConfirmationResult(confirmation, "already correct", page)
    shown = [(page, word) for page, word in candidates if comparable(_rendered(word, reviewed_mapping)) == comparable(confirmation.shown)]
    if not gap_glyphs:
        return ConfirmationResult(confirmation, CORRECTION if shown else "not found", shown[0][0] if shown else None)
    for page, word in shown:
        segments = convert_segments(word.text, state.mapping)
        solution = solve_confirmed(segments, confirmation.correct)
        if solution is None:
            continue
        conflicts = [glyphs for glyphs, unicode in solution.items() if glyphs in state.entries and state.entries[glyphs].unicode != unicode]
        if conflicts:
            return ConfirmationResult(confirmation, f"conflicts with existing {' '.join(conflicts)}", page)
        added = tuple(MappingEntry(glyphs, unicode, page, confirmation.correct) for glyphs, unicode in solution.items())
        for entry in added:
            state.entries[entry.glyphs] = entry
        state.pending = [proposal for proposal in state.pending if proposal.glyphs not in solution]
        return ConfirmationResult(confirmation, "added", page, added, _overrides(segments, solution))
    return ConfirmationResult(confirmation, "not found" if not shown else "unsolved")


def apply_confirmations(confirmations: Iterable[Confirmation], words: Sequence[tuple[int, Word]],
                        state: LearningState, reviewed_mapping: dict[str, str] | None = None) -> list[ConfirmationResult]:
    results = {confirmation: ConfirmationResult(confirmation, "unsolved") for confirmation in confirmations}
    reviewed_mapping = reviewed_mapping or state.mapping
    for _ in range(MAX_PASSES):
        open_items = [item for item, result in results.items() if result.status in ("unsolved", "not found")]
        for confirmation in open_items:
            results[confirmation] = _apply_one(confirmation, words, state, reviewed_mapping)
        if all(results[item].status in ("unsolved", "not found") for item in open_items):
            break
    return list(results.values())
