from pathlib import Path

from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import (
    Label,
    Source,
    WordEvidence,
    comparable_text,
    infer,
    marks_of,
    read_labels,
    render,
    seed_labels,
    word_evidence,
    write_labels,
)
from anu_unicode.scan.words import Band
from anu_unicode.shape_naming.shapes import NOTHING

BOX = (0, 0, 10, 10)


def test_a_sequence_renders_through_the_converter_with_nothing_for_empty_pieces() -> None:
    assert render((1, 2, 3), {1: "క", 2: "ి", 3: NOTHING}) == "కి"


def test_ocr_text_is_compared_without_quotes_spaces_or_joiners() -> None:
    assert comparable_text(" ‘గోచి’\n") == comparable_text("గోచి") == "గోచి"


def test_an_unknown_piece_takes_the_only_label_that_reproduces_the_word() -> None:
    words = [WordEvidence((1, 2), "కా"), WordEvidence((3, 2), "గా")]

    labels = infer(words, seeds={1: "క", 3: "గ"}, decisions={}, marks=frozenset())

    assert labels[2].unicode == "ా"
    assert labels[2].source is Source.WORDS


def test_of_two_unknown_pieces_only_a_mark_may_mean_nothing() -> None:
    words = [WordEvidence((5, 6), "స"), WordEvidence((5, 6), "స")]

    labels = infer(words, seeds={}, decisions={}, marks=frozenset({6}))

    assert (labels[5].unicode, labels[6].unicode) == ("స", NOTHING)


def test_a_split_vote_leaves_the_piece_unlabelled() -> None:
    words = [WordEvidence((1, 2), "కా"), WordEvidence((1, 2), "కి")]

    assert 2 not in infer(words, seeds={1: "క"}, decisions={}, marks=frozenset())


def test_a_wrong_seed_is_corrected_by_the_words_it_appears_in() -> None:
    words = [WordEvidence((1, 2), "గోచి"), WordEvidence((1, 3), "గోడ")]

    labels = infer(words, seeds={1: "గ", 2: "చి", 3: "డ"}, decisions={}, marks=frozenset())

    assert labels[1].unicode == "గో"
    assert labels[1].agreement == 1.0
    assert labels[1].support == 2


def test_a_human_decision_is_never_overruled() -> None:
    words = [WordEvidence((1, 2), "గోచి"), WordEvidence((1, 3), "గోడ")]

    labels = infer(words, seeds={2: "చి", 3: "డ"}, decisions={1: "గ"}, marks=frozenset())

    assert labels[1] == Label("గ", Source.REVIEW, support=0, agreement=0.0)


def test_only_confident_glyph_readings_that_are_known_pieces_become_seeds() -> None:
    assert seed_labels({1: ("క", 5), 2: ("గ", 3), 3: ("ఓటము", 5)}) == {1: "క"}


def test_marks_are_ids_found_above_or_below_the_line() -> None:
    occurrences = [Occurrence(4, 1, 1, 1, 1, Band.MAIN, BOX), Occurrence(4, 1, 1, 2, 2, Band.ABOVE, BOX)]

    assert marks_of(occurrences) == {2}


def test_word_evidence_skips_equals_signs_and_compares_cleaned_ocr_text() -> None:
    words = {(4, 1, 1): [Occurrence(4, 1, 1, 1, 7, Band.MAIN, BOX)], (4, 1, 2): [Occurrence(4, 1, 2, 1, EQUALS, Band.MAIN, BOX)]}

    assert word_evidence(words, {(4, 1, 1): " ‘కా’", (4, 1, 2): "="}) == [WordEvidence((7,), "కా")]


def test_labels_are_written_and_read_back(tmp_path: Path) -> None:
    labels = {3: Label("గో", Source.WORDS, 12, 0.917), 9: Label("ఁ", Source.REVIEW, 0, 0.0)}

    write_labels(tmp_path / "labels.tsv", labels)

    assert read_labels(tmp_path / "labels.tsv") == labels


def test_words_without_ocr_text_give_no_evidence() -> None:
    assert not infer([WordEvidence((1,), "")], seeds={}, decisions={}, marks=frozenset())
