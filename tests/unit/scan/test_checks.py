from anu_unicode.scan.checks import Recheck, check_decisions
from anu_unicode.scan.inference import Label, Source, WordEvidence
from anu_unicode.scan.names import Speller
from anu_unicode.shape_naming.shapes import NOTHING


def _labels(decided: str) -> dict[int, Label]:
    return {1: Label("వె", Source.WORDS, 9, 1.0), 2: Label(decided, Source.REVIEW, 0, 0.0), 3: Label("పు", Source.WORDS, 9, 1.0)}


def test_a_decision_its_words_keep_contradicting_is_flagged_with_the_pattern() -> None:
    words = [WordEvidence((1, 2, 3), "వైపు")] * 5

    rechecks = check_decisions(words, _labels(NOTHING), Speller([]))

    assert rechecks == [Recheck(2, NOTHING, words=5, agreement=0.0, pattern="ై→ె", pattern_words=5)]


def test_a_decision_that_restores_what_tesseract_cannot_read_is_not_flagged() -> None:
    misread = [WordEvidence((1, 2, 3), "వెయపు")] * 5
    dropped = [WordEvidence((1, 2, 3), "వెపు.")] * 5

    assert not check_decisions(misread, _labels("ఁ"), Speller([]))
    assert not check_decisions(dropped, _labels("ఁ"), Speller([]))


def test_periods_tesseract_adds_do_not_count_against_a_decision() -> None:
    assert not check_decisions([WordEvidence((1, 2, 3), "వెపు.")] * 5, _labels(NOTHING), Speller([]))


def test_a_symbolic_name_still_waiting_for_its_recipe_is_not_flagged() -> None:
    assert not check_decisions([WordEvidence((1, 2, 3), "వైపు")] * 5, _labels("ai_bottom"), Speller([]))


def test_a_decision_seen_in_few_words_is_not_flagged() -> None:
    assert not check_decisions([WordEvidence((1, 2, 3), "వైపు")] * 4, _labels(NOTHING), Speller([]))
