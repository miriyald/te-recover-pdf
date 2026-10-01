from collections import Counter

import pytest

from anu_unicode.ocr import OcrWord
from anu_unicode.quality import (
    character_confusions,
    combine,
    compare_words,
    edit_distance,
    error_rate,
    ground_truth_quality,
    page_quality,
)


def test_edit_distance_counts_substitutions_insertions_and_deletions():
    assert edit_distance(list("kitten"), list("sitting")) == 3
    assert edit_distance([], ["a", "b"]) == 2
    assert edit_distance(["a"], ["a"]) == 0


def test_error_rate_is_relative_to_reference_length():
    assert error_rate(["a", "b", "c", "d"], ["a", "x", "c", "d"]) == pytest.approx(0.25)


def test_error_rate_of_empty_reference_is_zero():
    assert error_rate([], []) == 0.0


def test_compare_words_pairs_by_overlap_and_leaves_far_words_unmatched():
    converted = [((0, 0, 10, 10), "కాశీరాజ"), ((50, 0, 60, 10), "కన్యల")]
    ocr = [OcrWord("కాశీరాజు", 40.0, (0, 0, 10, 10))]

    comparisons = compare_words(converted, ocr, min_overlap=0.5)

    assert [(item.converted, item.ocr, item.confidence) for item in comparisons] == [
        ("కాశీరాజ", "కాశీరాజు", 40.0),
        ("కన్యల", None, None),
    ]


def test_compare_words_keeps_the_matched_ocr_box():
    comparisons = compare_words([((0, 0, 10, 10), "అ")], [OcrWord("అ", 90.0, (1, 1, 11, 11))], min_overlap=0.5)

    assert comparisons[0].ocr_bbox == (1, 1, 11, 11)


def test_doubled_single_quotes_are_the_same_word_as_a_double_quote():
    comparisons = compare_words([((0, 0, 10, 10), "‘‘అ’’")], [OcrWord("“అ”", 90.0, (0, 0, 10, 10))], min_overlap=0.5)

    assert not comparisons[0].disagrees


def test_zwnj_after_a_visible_virama_is_not_a_disagreement():
    comparisons = compare_words([((0, 0, 10, 10), "మరుక్‌")], [OcrWord("మరుక్", 90.0, (0, 0, 10, 10))], min_overlap=0.5)

    assert not comparisons[0].disagrees


def test_ground_truth_without_zwnj_matches_converted_text_with_zwnj():
    quality = ground_truth_quality(1, "మరుక్ అని", "మరుక్‌ అని", "మరుక్ అని")

    assert quality.converted_word_errors == 0
    assert quality.converted_character_error_rate == 0.0


def test_character_confusions_report_replaced_segments_only():
    assert character_confusions("చరిత్ర", "ఛరిత్ర") == Counter({("చ", "ఛ"): 1})


def test_page_quality_counts_agreements_disagreements_and_unresolved():
    comparisons = compare_words(
        [((0, 0, 10, 10), "అ"), ((20, 0, 30, 10), "ఆ"), ((40, 0, 50, 10), "⟦x⟧"), ((60, 0, 70, 10), "ఈ")],
        [OcrWord("అ", 90.0, (0, 0, 10, 10)), OcrWord("చ", 30.0, (20, 0, 30, 10)), OcrWord("ఇ", 50.0, (40, 0, 50, 10))],
        min_overlap=0.5,
    )

    result = page_quality(7, comparisons)

    assert (result.page, result.words, result.matched, result.disagreements, result.unresolved) == (7, 4, 3, 2, 1)
    assert result.unmatched == 1
    assert result.agreement_rate == pytest.approx(1 / 3)
    assert result.mean_confidence_agreeing == 90.0
    assert result.mean_confidence_disagreeing == 40.0
    assert result.confusions == Counter({("చ", "ఆ"): 1, ("ఇ", "⟦x⟧"): 1})


def test_combine_sums_page_rows():
    first = page_quality(1, compare_words([((0, 0, 1, 1), "అ")], [OcrWord("ఆ", 20.0, (0, 0, 1, 1))], 0.5))
    second = page_quality(2, compare_words([((0, 0, 1, 1), "అ")], [OcrWord("అ", 80.0, (0, 0, 1, 1))], 0.5))

    total = combine([first, second])

    assert (total.words, total.matched, total.disagreements) == (2, 2, 1)
    assert total.mean_confidence_agreeing == 80.0
    assert total.mean_confidence_disagreeing == 20.0


def test_ground_truth_quality_scores_converted_and_ocr_text_separately():
    result = ground_truth_quality(6, reference="అ ఆ ఇ", converted="అ ఆ ఈ", ocr="అ ఇ")

    assert result.reference_words == 3
    assert result.converted_word_errors == 1
    assert result.ocr_word_errors == 1
    assert result.converted_word_error_rate == pytest.approx(1 / 3)
    assert result.converted_character_error_rate == pytest.approx(1 / 5)
    assert result.ocr_character_error_rate == pytest.approx(2 / 5)
