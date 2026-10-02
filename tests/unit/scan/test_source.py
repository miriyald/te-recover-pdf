from pathlib import Path

from anu_unicode.convert import Coverage, convert_anu
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.source import read_occurrences, scan_words, shape_char, shape_id_of
from anu_unicode.scan.words import Band
from anu_unicode.shape_naming.shapes import Shape, compile_mapping


def _occurrence(line: int, word: int, position: int, shape_id: int, left: int) -> Occurrence:
    return Occurrence(4, line, word, position, shape_id, Band.MAIN, (left, 0, left + 40, 50))


def test_shape_ids_map_to_private_use_characters_and_back() -> None:
    assert shape_id_of(shape_char(1234)) == 1234
    assert ord(shape_char(0)) == 0xF0000


def test_occurrences_become_words_in_drawing_order_with_boxes_in_points() -> None:
    occurrences = [_occurrence(1, 2, 1, 7, 300), _occurrence(1, 1, 2, 5, 50), _occurrence(1, 1, 1, 3, 0)]

    words = scan_words(occurrences, points_per_pixel=0.5)

    assert [word.text for word in words] == [shape_char(3) + shape_char(5), shape_char(7)]
    assert words[0].glyphs[1].bbox == (25.0, 0.0, 45.0, 25.0)


def test_a_scanned_word_converts_through_the_shape_names_pipeline() -> None:
    word = scan_words([_occurrence(1, 1, 1, 3, 0), _occurrence(1, 1, 2, 5, 50)], points_per_pixel=1.0)[0]
    entries = compile_mapping([Shape(shape_char(3), "క", "క"), Shape(shape_char(5), "ా", "ా")], [])
    mapping = {glyphs: entry.unicode for glyphs, entry in entries.items()}

    assert convert_anu(word.text, mapping, Coverage()) == "కా"


def test_occurrences_are_read_back_from_the_index_file(tmp_path: Path) -> None:
    path = tmp_path / "occurrences.tsv"
    header = "page\tline\tword\tposition\tshape_id\tband\tleft\ttop\tright\tbottom\n"
    path.write_text(header + "4\t1\t2\t3\t9\tbelow\t1\t2\t3\t4\n", encoding="utf-8")

    assert read_occurrences(path) == [Occurrence(4, 1, 2, 3, 9, Band.BELOW, (1, 2, 3, 4))]
