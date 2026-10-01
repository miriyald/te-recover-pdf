from typing import Any
from unittest.mock import MagicMock

from anu_unicode.convert import convert_segments
from anu_unicode.glyphs import page_lines, split_words
from anu_unicode.mapping import MappingEntry, Proposal
from anu_unicode.ocr import OcrWord
from anu_unicode.ocr_learning.learn import LearningState, gap_candidates, learn_page, run_batch

SEED = {"`å": "తా", "Hõ": "క", "}": "ణ", "[": "జ", "~°": "ర", "~°∞": "రు", "x": "ని", "=Ú": "ము"}


def _state(seed: dict[str, str] | None = None, pending: list[Proposal] | None = None) -> LearningState:
    return LearningState({glyphs: MappingEntry(glyphs, unicode) for glyphs, unicode in (seed or SEED).items()}, pending or [])


def _page(number: int, words: list[str]) -> MagicMock:
    lines = []
    for row, word in enumerate(words):
        baseline = 100.0 + row * 20
        chars = [{"c": char, "bbox": (80 + index * 5, baseline - 15, 85 + index * 5, baseline), "origin": (80 + index * 5, baseline)}
                 for index, char in enumerate(word)]
        lines.append({"bbox": (80, 0, 85 + len(word) * 5, 0), "spans": [{"font": "X+Priyaanka", "size": 15.0, "origin": chars[0]["origin"],
                                                                         "chars": chars}]})
    page = MagicMock()
    page.number = number - 1
    page.get_text.return_value = {"blocks": [{"lines": lines}]}
    return page


def _ocr(readings: list[str], confidence: float = 95.0) -> Any:
    def ocr(page: MagicMock) -> list[OcrWord]:
        words = [word for line in page_lines(page) for word in split_words(line)]
        return [OcrWord(text, confidence, word.bbox) for word, text in zip(words, readings)]
    return ocr


def test_gap_candidates_reads_plain_gap_between_known_neighbours() -> None:
    segments = convert_segments("Hõ}ﬁ", SEED)

    assert gap_candidates(segments, "కణ్వ") == {"్వ"}


def test_gap_candidates_handles_subscript_drawn_after_vowel_sign() -> None:
    segments = convert_segments("[~°`å¯~°∞x", SEED)

    assert gap_candidates(segments, "జరత్కారుని") == {"్క"}


def test_gap_candidates_rejects_ocr_that_contradicts_known_neighbours() -> None:
    segments = convert_segments("Hõ}ﬁ", SEED)

    assert not gap_candidates(segments, "పణ్వ")


def test_gap_candidates_skips_words_with_more_than_one_gap() -> None:
    segments = convert_segments("Hõ¯}ﬁ", SEED)

    assert not gap_candidates(segments, "కక్కణ్వ")


def test_two_agreeing_occurrences_are_accepted_with_first_occurrence() -> None:
    state = _state()
    page = _page(9, ["Hõ}ﬁ", "}ﬁ=Ú"])

    result = learn_page(page, state, _ocr(["కణ్వ", "ణ్వము"]))

    assert state.entries["ﬁ"] == MappingEntry("ﬁ", "్వ", 9, "కణ్వ")
    assert [entry.glyphs for entry, _ in result.accepted] == ["ﬁ"]
    assert result.progress.unmapped_before == 2
    assert result.progress.unmapped_after == 0
    assert not state.pending


def test_different_words_with_same_surrounding_letters_count_once() -> None:
    state = _state({**SEED, "n": "దీ", "`«": "త", "_»∞": "డు", "_»": "డ", "#∞": "ను"})

    learn_page(_page(11, ["n~°…`«=Ú_»#∞", "n~°…`«=Ú_»∞"]), state, _ocr(["దీర్ధతముడను", "దీర్ధతముడు"]))

    assert "…" not in state.entries
    assert state.pending == [Proposal("…", "్ధ", 2, 11, "దీర్ధతముడను", {"ర|త"})]


def test_single_occurrence_stays_pending_across_pages() -> None:
    state = _state()

    learn_page(_page(9, ["Hõ}ﬁ"]), state, _ocr(["కణ్వ"]))
    learn_page(_page(10, ["}ﬁ=Ú"]), state, _ocr(["ణ్వము"]))

    assert state.entries["ﬁ"] == MappingEntry("ﬁ", "్వ", 9, "కణ్వ")


def test_conflicting_proposals_are_not_accepted() -> None:
    state = _state(pending=[Proposal("ﬁ", "్మ", 1, 8, "కణ్మ", {"ణ|"})])

    learn_page(_page(9, ["Hõ}ﬁ", "}ﬁ=Ú"]), state, _ocr(["కణ్వ", "ణ్వము"]))

    assert "ﬁ" not in state.entries
    assert {(proposal.unicode, proposal.count) for proposal in state.pending} == {("్మ", 1), ("్వ", 2)}


def test_accepted_entry_resolves_multi_gap_word_on_same_page() -> None:
    state = _state()

    result = learn_page(_page(9, ["Hõ}ﬁ", "}ﬁ=Ú", "Hõ¯}ﬁ"]), state, _ocr(["కణ్వ", "ణ్వము", "క్కణ్వ"]))

    assert state.pending == [Proposal("¯", "్క", 1, 9, "క్కణ్వ", {"క|ణ"})]
    assert not result.unresolved[0].converted.count("ﬁ")


def test_page_without_gaps_is_not_ocred_and_existing_entries_are_kept() -> None:
    state = _state()
    ocr = MagicMock()

    result = learn_page(_page(6, ["Hõ}", "=Ú"]), state, ocr)

    ocr.assert_not_called()
    assert result.progress.unmapped_before == 0
    assert state.entries["}"] == MappingEntry("}", "ణ")


def test_suspect_words_are_reported_but_mapping_is_unchanged() -> None:
    state = _state()

    result = learn_page(_page(9, ["Hõ}ﬁ", "}ﬁ=Ú", "Hõ}"]), state, _ocr(["కణ్వ", "ణ్వము", "కడ"]))

    assert [(item.converted, item.ocr_text) for item in result.suspects] == [("కణ", "కడ")]
    assert state.entries["}"].unicode == "ణ"


def test_low_confidence_ocr_still_teaches_but_is_not_a_suspect() -> None:
    state = _state()

    result = learn_page(_page(9, ["Hõ}ﬁ", "}ﬁ=Ú", "Hõ}"]), state, _ocr(["కణ్వ", "ణ్వము", "కడ"], confidence=21.0))

    assert state.entries["ﬁ"].unicode == "్వ"
    assert not result.suspects


def test_run_batch_stops_after_page_reaching_new_entry_target() -> None:
    state = _state()
    pages = [_page(9, ["Hõ}ﬁ", "}ﬁ=Ú"]), _page(10, ["Hõ¯=Ú", "`å¯"]), _page(11, ["Hõ"])]
    readings = {9: ["కణ్వ", "ణ్వము"], 10: ["క్కము", "త్కా"], 11: ["క"]}
    seen: list[int] = []

    results = run_batch(pages, state, lambda page: _ocr(readings[page.number + 1])(page), 1, lambda r: seen.append(r.progress.page))

    assert seen == [9]
    assert [result.progress.page for result in results] == [9]
