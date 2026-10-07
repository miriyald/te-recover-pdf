from pathlib import Path

from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.source import read_occurrences, shape_char, shape_id_of
from anu_unicode.scan.words import Band


def test_shape_ids_map_to_private_use_characters_and_back() -> None:
    assert shape_id_of(shape_char(1234)) == 1234
    assert ord(shape_char(0)) == 0xF0000


def test_occurrences_are_read_back_from_the_index_file(tmp_path: Path) -> None:
    path = tmp_path / "occurrences.tsv"
    header = "page\tline\tword\tposition\tshape_id\tband\tleft\ttop\tright\tbottom\n"
    path.write_text(header + "4\t1\t2\t3\t9\tbelow\t1\t2\t3\t4\n", encoding="utf-8")

    assert read_occurrences(path) == [Occurrence(4, 1, 2, 3, 9, Band.BELOW, (1, 2, 3, 4))]
