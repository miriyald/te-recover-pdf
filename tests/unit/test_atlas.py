from pathlib import Path

import pymupdf

from anu_unicode.atlas import UnitStats, render_png, write_atlas


def test_unit_is_drawn_from_the_first_font_that_has_all_its_glyphs() -> None:
    data = render_png([pymupdf.Font("helv")], "Hi", 40)

    assert data is not None and data.startswith(b"\x89PNG")


def test_unit_missing_from_every_font_is_not_drawn() -> None:
    assert render_png([pymupdf.Font("helv")], "క", 40) is None


def test_atlas_prefills_known_labels_and_exports_only_changes(tmp_path: Path) -> None:
    path = tmp_path / "atlas.html"
    units = [UnitStats("H", 30, ("Hi",)), UnitStats("o", 10, ())]

    write_atlas(path, units, {"H": "క"}, [pymupdf.Font("helv")], top=1)

    page = path.read_text(encoding="utf-8")
    assert 'data-glyphs="H" data-original="క" value="క"' in page
    assert 'data-glyphs="o"' not in page
    assert "1 of 2 units shown, covering 30 of 40 occurrences" in page
    assert "U+0048" in page
    assert "i.value.trim()!==i.dataset.original" in page
