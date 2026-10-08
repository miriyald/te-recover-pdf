import numpy as np

from anu_unicode.scan.ink import Component, find_components
from anu_unicode.scan.words import Band, Placed, ScanWord, is_equals, page_words

BODY = 50.0


def _block(left: int, top: int, width: int, height: int) -> Component:
    return Component((left, top, left + width, top + height), np.ones((height, width), dtype=bool))


def test_ink_is_split_into_eight_connected_components() -> None:
    ink = np.zeros((20, 20), dtype=bool)
    ink[2:8, 2:8] = True
    ink[8:12, 8:12] = True
    ink[15:19, 15:19] = True

    components = find_components(ink, min_area=4)

    assert sorted(component.bbox for component in components) == [(2, 2, 12, 12), (15, 15, 19, 19)]


def test_close_neighbours_form_one_word_and_a_wide_gap_starts_another() -> None:
    letters = [_block(0, 0, 40, 50), _block(45, 0, 40, 50), _block(200, 0, 40, 50)]

    lines = page_words(letters, BODY, word_gap=0.45, stack_gap=0.3)

    assert [len(word.glyphs) for word in lines[0]] == [2, 1]


def test_a_mark_below_follows_its_host_and_precedes_the_next_letter() -> None:
    host, below, after = _block(0, 0, 40, 50), _block(5, 55, 30, 20), _block(45, 0, 40, 50)

    word = page_words([after, below, host], BODY, word_gap=0.45, stack_gap=0.3)[0][0]

    assert [placed.component for placed in word.glyphs] == [host, below, after]
    assert [placed.band for placed in word.glyphs] == [Band.MAIN, Band.BELOW, Band.MAIN]


def test_a_vowel_piece_resting_on_its_consonant_follows_it_even_when_it_starts_further_left() -> None:
    tall, sign, consonant = _block(150, 0, 40, 60), _block(198, 2, 27, 25), _block(200, 18, 45, 41)

    word = page_words([tall, sign, consonant], BODY, word_gap=0.45, stack_gap=0.3)[0][0]

    assert [placed.component for placed in word.glyphs] == [tall, consonant, sign]


def test_a_hook_hanging_left_of_its_consonant_keeps_coming_first() -> None:
    tall, hook, consonant = _block(140, 0, 40, 60), _block(185, 2, 30, 25), _block(205, 18, 45, 41)

    word = page_words([tall, hook, consonant], BODY, word_gap=0.45, stack_gap=0.3)[0][0]

    assert [placed.component for placed in word.glyphs] == [tall, hook, consonant]


def test_a_mark_above_is_classified_above_the_band() -> None:
    host, tick = _block(0, 20, 40, 50), _block(10, 0, 15, 15)

    word = page_words([host, tick], BODY, word_gap=0.45, stack_gap=0.3)[0][0]

    assert [placed.band for placed in word.glyphs] == [Band.MAIN, Band.ABOVE]


def test_the_band_follows_the_letters_when_body_sized_subscripts_hang_below_them() -> None:
    letters = [_block(0, 0, 50, 65), _block(55, 2, 50, 64), _block(110, 1, 50, 66)]
    subscripts = [_block(10, 70, 40, 32), _block(65, 72, 40, 31)]

    word = page_words([*letters, *subscripts], 43.0, word_gap=0.45, stack_gap=0.3)[0][0]

    assert word.band[0] <= 2 and word.band[1] >= 64
    assert {placed.component.bbox: placed.band for placed in word.glyphs} == (
        {letter.bbox: Band.MAIN for letter in letters} | {subscript.bbox: Band.BELOW for subscript in subscripts})


def test_a_tick_overlapping_its_letter_in_a_two_piece_word_stays_above() -> None:
    host, tick = _block(0, 20, 40, 50), _block(10, 0, 15, 22)

    word = page_words([host, tick], BODY, word_gap=0.45, stack_gap=0.3)[0][0]

    assert [placed.band for placed in word.glyphs] == [Band.MAIN, Band.ABOVE]


def test_words_on_separate_rows_are_separate_lines_in_reading_order() -> None:
    second_line, first_line = _block(0, 200, 40, 50), _block(0, 0, 40, 50)

    lines = page_words([second_line, first_line], BODY, word_gap=0.45, stack_gap=0.3)

    assert [line[0].glyphs[0].component for line in lines] == [first_line, second_line]


def test_a_thin_word_lower_on_a_skewed_line_still_joins_that_line() -> None:
    letters = [_block(0, 0, 40, 50), _block(100, 20, 60, 6), _block(100, 32, 60, 6), _block(400, 6, 40, 50),
               _block(500, 26, 60, 6), _block(500, 38, 60, 6)]

    lines = page_words(letters, BODY, word_gap=0.45, stack_gap=0.3)

    assert [len(line) for line in lines] == [4]


def _placed(*components: Component) -> ScanWord:
    return ScanWord(tuple(Placed(component, Band.MAIN) for component in components), (0, 50))


def test_two_stacked_bars_are_an_equals_sign() -> None:
    assert is_equals(_placed(_block(0, 10, 60, 10), _block(0, 30, 60, 10)), BODY)


def test_an_equals_sign_printed_tight_against_words_is_its_own_word() -> None:
    before, upper, lower, after = _block(0, 0, 40, 50), _block(45, 15, 40, 6), _block(45, 29, 40, 6), _block(90, 0, 40, 50)

    line = page_words([before, upper, lower, after], BODY, word_gap=0.45, stack_gap=0.3)[0]

    assert [[placed.component for placed in word.glyphs] for word in line] == [[before], [upper, lower], [after]]
    assert is_equals(line[1], BODY)


def test_bars_of_different_lengths_stacked_in_a_word_are_not_pulled_out_as_equals() -> None:
    letter, mark, rule = _block(0, 0, 60, 50), _block(10, 52, 40, 6), _block(0, 64, 120, 6)

    lines = page_words([letter, mark, rule], BODY, word_gap=0.45, stack_gap=0.3)

    assert not any(is_equals(word, BODY) for line in lines for word in line)


def test_a_single_bar_or_a_letter_beside_a_bar_is_not_an_equals_sign() -> None:
    assert not is_equals(_placed(_block(0, 10, 60, 10)), BODY)
    assert not is_equals(_placed(_block(0, 10, 60, 10), _block(70, 0, 40, 50)), BODY)
