from pathlib import Path

from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import Label, Source
from anu_unicode.scan.review import ReviewInput, read_decisions, review_rows, write_review
from anu_unicode.scan.words import Band
from anu_unicode.shape_naming.shapes import NOTHING


def _occurrence(shape_id: int, page: int = 4, word: int = 1) -> Occurrence:
    return Occurrence(page, 1, word, 1, shape_id, Band.MAIN, (0, 0, 10, 10))


def _label(unicode: str, agreement: float = 1.0) -> Label:
    return Label(unicode, Source.WORDS, 5, agreement)


def test_flagged_ids_come_first_then_the_rest_by_count() -> None:
    occurrences = [_occurrence(1)] * 5 + [_occurrence(2)] * 3 + [_occurrence(3)] * 2 + [_occurrence(4)] * 4 + [_occurrence(EQUALS)]
    labels = {1: _label("క"), 2: _label("ి", agreement=0.5), 4: _label(NOTHING)}

    rows = review_rows(ReviewInput(occurrences, labels), top=10)

    assert [(row.shape_id, row.flagged) for row in rows] == [(4, True), (2, True), (3, True), (1, False)]


def test_a_mark_meaning_nothing_is_not_flagged() -> None:
    rows = review_rows(ReviewInput([_occurrence(4)], {4: _label(NOTHING)}, marks=frozenset({4})), top=10)

    assert not rows[0].flagged


def test_decided_ids_are_left_out_and_the_sheet_is_cut_to_the_top_rows() -> None:
    occurrences = [_occurrence(1)] * 3 + [_occurrence(2)] * 2 + [_occurrence(3)]

    rows = review_rows(ReviewInput(occurrences, {}, decisions={1: "క"}), top=1)

    assert [row.shape_id for row in rows] == [2]


def test_only_ids_on_the_chosen_pages_are_listed_with_their_book_counts_and_example_words() -> None:
    occurrences = [_occurrence(1, page=4), _occurrence(1, page=5, word=2), _occurrence(2, page=5, word=2)]

    rows = review_rows(ReviewInput(occurrences, {}, pages=frozenset({4}), texts={(4, 1, 1): "కాకి", (5, 1, 2): "కోడి"}), top=10)

    assert [(row.shape_id, row.count, row.examples) for row in rows] == [(1, 2, ("కాకి", "కోడి"))]


def test_the_sheet_prefills_labels_and_its_export_keeps_earlier_decisions(tmp_path: Path) -> None:
    rows = review_rows(ReviewInput([_occurrence(7)], {7: _label("గో")}, texts={(4, 1, 1): "గోడ"}), top=10)

    write_review(tmp_path / "review.html", rows, {3: "ఁ"}, "../scan-index/shapes")

    page = (tmp_path / "review.html").read_text(encoding="utf-8")
    assert 'value="గో"' in page
    assert "../scan-index/shapes/7.png" in page
    assert '{"3": "ఁ"}' in page
    assert "decisions.tsv" in page


def test_decisions_are_read_by_shape_id(tmp_path: Path) -> None:
    path = tmp_path / "decisions.tsv"
    path.write_text("shape_id\tunicode\n3\tఁ\n9\t∅\n", encoding="utf-8")

    assert read_decisions(path) == {3: "ఁ", 9: NOTHING}
    assert not read_decisions(tmp_path / "missing.tsv")
