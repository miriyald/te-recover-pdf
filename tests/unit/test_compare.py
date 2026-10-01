from pathlib import Path

import pymupdf

from anu_unicode.compare import CANDIDATE_GAP, HUMAN, NEW_WRONG, OLD_WRONG, Difference, PageWord, compare, page_words, write_comparison
from anu_unicode.ocr import OcrWord
from anu_unicode.profile import FontProfile

CANDIDATE = {"=": "వ", "∞": "ు", "=∞": "మ", "#": "న"}
REFERENCE = {"=": "వ", "∞": "ు", "#": "న"}


def _word(glyphs: str, ocr: str | None = None, page: int = 1) -> PageWord:
    return PageWord(page, (0, 0, 10, 10), glyphs, ocr)


def test_identical_words_are_not_reported() -> None:
    comparison = compare([_word("#∞"), _word("=")], CANDIDATE, REFERENCE)

    assert not comparison.differences
    assert comparison.words == 2


def test_differences_are_grouped_with_counts_and_ocr_votes() -> None:
    words = [_word("=∞", "మ"), _word("=∞", "వు", page=2), _word("=∞", None, page=3)]

    [difference] = compare(words, CANDIDATE, REFERENCE).differences

    assert (difference.glyphs, difference.candidate, difference.reference) == ("=∞", "మ", "వు")
    assert (difference.count, difference.candidate_votes, difference.reference_votes) == (3, 1, 1)
    assert difference.first == _word("=∞", "మ")


def test_verdict_follows_the_ocr_vote() -> None:
    assert Difference("=∞", "మ", "వు", 1, candidate_votes=1).verdict == OLD_WRONG
    assert Difference("=∞", "మ", "వు", 1, reference_votes=1).verdict == NEW_WRONG
    assert Difference("=∞", "మ", "వు", 2, candidate_votes=1, reference_votes=1).verdict == HUMAN
    assert Difference("=∞", "మ", "వు", 1).verdict == HUMAN


def test_ocr_curly_double_quote_votes_for_two_single_quotes() -> None:
    candidate, reference = {**CANDIDATE, "'": "‘"}, {**REFERENCE, "'": "‘"}

    [difference] = compare([_word("''=∞", "“మ")], candidate, reference).differences

    assert difference.verdict == OLD_WRONG


def test_candidate_gaps_are_reported_separately() -> None:
    [difference] = compare([_word("%")], CANDIDATE, {"%": "క"}).differences

    assert difference.verdict == CANDIDATE_GAP
    assert compare([_word("%")], CANDIDATE, {"%": "క"}).candidate_coverage.ratio == 0.0


def test_page_words_take_the_ocr_text_of_the_overlapping_box() -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 72), "Hi there", fontname="helv", fontsize=12)
    profile = FontProfile(frozenset({"Helvetica"}), ascent=0.75, descent=0.35)
    ocr = [OcrWord("హాయ్", 90.0, (50.0, 60.0, 62.0, 76.0))]

    words = page_words(page, profile, ocr, min_overlap=0.3)

    assert [(word.page, word.glyphs, word.ocr) for word in words] == [(1, "Hi", "హాయ్"), (1, "there", None)]


def test_page_words_without_ocr_have_no_vote() -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 72), "Hi", fontname="helv", fontsize=12)

    words = page_words(page, FontProfile(frozenset({"Helvetica"}), 0.75, 0.35), None, min_overlap=0.3)

    assert [word.ocr for word in words] == [None]


def test_report_lists_every_group_and_crops_only_human_rows(tmp_path: Path) -> None:
    document = pymupdf.open()
    document.new_page()
    words = [_word("=∞", "మ"), _word("#=∞#")]

    write_comparison(tmp_path, compare(words, CANDIDATE, REFERENCE), document)

    tsv = (tmp_path / "diff.tsv").read_text(encoding="utf-8").splitlines()
    assert tsv[0] == "verdict\tcount\tglyphs\tcandidate\treference\tcandidate_votes\treference_votes\tfirst_page"
    assert sorted(line.split("\t")[0] for line in tsv[1:]) == [HUMAN, OLD_WRONG]
    assert (tmp_path / "report.html").read_text(encoding="utf-8").count("<img") == 1
