from pathlib import Path

from anu_unicode.scan.conversion import Choice, ScanText, Written
from anu_unicode.scan.evaluation import Cause, Errors, Score, score_page, write_misses, write_scores


def _page(*words: tuple[str, Choice], overruled: tuple[int, ...] = ()) -> ScanText:
    written = [Written(((7, 1, number),), text, (choice,)) for number, (text, choice) in enumerate(words, 1)]
    return ScanText([written], disagreements=[((7, 1, number), "x", "y") for number in overruled])


def test_exact_words_are_counted_for_ours_and_for_ocr_and_an_unlabelled_fallback_is_tagged() -> None:
    page = _page(("కా", Choice.AGREED), ("=", Choice.EQUALS), ("మ", Choice.WORD_OCR))

    score = score_page(7, "కా = ము", page, "కా మ", {(7, 1, 3): "మ"})

    assert (score.words, score.letter_words, score.letter_errors) == (Score(3, 2, 1), Score(2, 1, 1), Errors(4, 1, 1))
    assert [(miss.gold, miss.ours, miss.ocr, miss.cause) for miss in score.misses] == [(("ము",), ("మ",), ("మ",), Cause.UNLABELLED)]


def test_punctuation_digits_and_placeholders_are_left_out_of_the_letter_scores() -> None:
    page = _page(("సాధు!", Choice.AGREED), ("సాధు□", Choice.GAP), ("౨౪", Choice.WORD_OCR))

    score = score_page(7, "సాధు। సాధు। ౨౪", page, "సాధు1 సాధు!", {})

    assert (score.letter_words, score.letter_errors) == (Score(2, 2, 2), Errors(8, 0, 0))
    assert not score.misses


def test_a_word_written_only_as_a_placeholder_is_an_unlabelled_miss_not_a_missing_word() -> None:
    page = _page(("కా", Choice.AGREED), ("□", Choice.GAP))

    score = score_page(7, "కా ము", page, "కా", {})

    assert [(miss.gold, miss.ours, miss.cause) for miss in score.misses] == [(("ము",), ("□",), Cause.UNLABELLED)]
    assert score.letter_errors == Errors(4, 2, 2)


def test_one_gold_word_read_as_two_is_a_grouping_miss() -> None:
    page = _page(("భోగాస", Choice.WORD_OCR), ("కియే", Choice.WORD_OCR))

    score = score_page(7, "భోగాసక్తియే", page, "భోగాస కియే", {})

    assert [miss.cause for miss in score.misses] == [Cause.GROUPING]


def test_a_gold_word_with_nothing_on_our_side_is_missing_and_an_unmatched_word_of_ours_is_extra() -> None:
    page = _page(("కా", Choice.AGREED), ("ఆ", Choice.WORD_OCR))

    missing = score_page(7, "కా ము", _page(("కా", Choice.AGREED)), "కా", {})
    extra = score_page(7, "కా", page, "కా ఆ", {})

    assert [miss.cause for miss in missing.misses] == [Cause.MISSING]
    assert [miss.cause for miss in extra.misses] == [Cause.EXTRA]


def test_a_complete_reading_that_lost_to_ocr_is_overruled() -> None:
    page = _page(("క్రవకాశము", Choice.WORD_OCR), overruled=(1,))

    score = score_page(7, "కవకాశము", page, "క్రవకాశము", {})

    assert [miss.cause for miss in score.misses] == [Cause.OCR_OVERRULED]


def test_our_own_reading_that_is_wrong_is_a_wrong_label() -> None:
    page = _page(("ఆనంత", Choice.REVIEWED))

    score = score_page(7, "అనంత", page, "అనంత", {})

    assert [miss.cause for miss in score.misses] == [Cause.WRONG_LABEL]
    assert score.letter_words.ocr == 1


def test_scores_are_written_one_row_per_page_with_a_count_per_cause(tmp_path: Path) -> None:
    score = score_page(7, "ము", _page(("మ", Choice.WORD_OCR)), "మ", {})

    write_scores(tmp_path / "out" / "scores.tsv", [score])

    header = ("page", "gold_words", "ours_exact", "ocr_exact", "letter_words", "ours_letter_exact", "ocr_letter_exact", "letters",
              "ours_letter_errors", "ocr_letter_errors", "grouping", "missing", "extra", "unlabelled", "ocr_overruled", "wrong_label")
    assert (tmp_path / "out" / "scores.tsv").read_text(encoding="utf-8").splitlines() == [
        "\t".join(header), "7\t1\t0\t0\t1\t0\t0\t2\t1\t1\t0\t0\t0\t1\t0\t0"]


def test_the_misses_page_lists_each_miss_with_its_crop(tmp_path: Path) -> None:
    score = score_page(7, "ము", _page(("మ", Choice.WORD_OCR)), "మ", {})

    write_misses(tmp_path / "misses.html", [score], lambda miss: "AAAA")

    page = (tmp_path / "misses.html").read_text(encoding="utf-8")
    assert "<title>" in page and "data:image/png;base64,AAAA" in page and "unlabelled" in page
