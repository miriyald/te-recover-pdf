from pathlib import Path

import pytest

from anu_unicode.convert import Coverage, convert_anu
from anu_unicode.shapes import MAX_VARIANTS, NOTHING, Recipe, Shape, ShapeError, compile_mapping, load_recipes, load_shapes

SHAPES = [Shape("=", "va_base", "వ"), Shape("∞", "u_hook", "ు"), Shape("#", "na_base", "న"), Shape("‰", "u_hook", "ు")]
MA = Recipe(("va_base", "u_hook"), "మ", "ma drawn as va + hook")


def _mapping(shapes: list[Shape], recipes: list[Recipe]) -> dict[str, str]:
    return {glyphs: entry.unicode for glyphs, entry in compile_mapping(shapes, recipes).items()}


def test_each_shape_with_a_contribution_becomes_a_single_glyph_entry() -> None:
    mapping = _mapping([Shape("=", "va_base", "వ"), Shape("Ú", "tail", "")], [])

    assert mapping == {"=": "వ"}


def test_shape_that_contributes_nothing_maps_to_an_empty_string() -> None:
    mapping = _mapping([Shape("`", "ta_base", "త"), Shape("«", "tick", NOTHING)], [])

    assert mapping == {"`": "త", "«": ""}
    assert convert_anu("`«", mapping, Coverage()) == "త"


def test_recipe_expands_over_every_glyph_variant_of_its_names() -> None:
    mapping = _mapping(SHAPES, [MA])

    assert mapping["=∞"] == "మ"
    assert mapping["=‰"] == "మ"


def test_recipe_beats_concatenation_in_the_converter() -> None:
    mapping = _mapping(SHAPES, [MA])

    assert convert_anu("#∞=∞", mapping, Coverage()) == "నుమ"


def test_glyph_listed_twice_is_an_error() -> None:
    with pytest.raises(ShapeError, match="listed twice"):
        compile_mapping([Shape("=", "va_base", "వ"), Shape("=", "other", "వ")], [])


def test_name_with_two_unicode_values_is_an_error() -> None:
    with pytest.raises(ShapeError, match="u_hook"):
        compile_mapping([Shape("∞", "u_hook", "ు"), Shape("‰", "u_hook", "ూ")], [])


def test_recipe_with_unknown_name_is_an_error() -> None:
    with pytest.raises(ShapeError, match="unknown"):
        compile_mapping(SHAPES, [Recipe(("va_base", "missing"), "మ")])


def test_recipe_expanding_beyond_the_variant_cap_is_an_error() -> None:
    shapes = [Shape(chr(0x100 + index), "dot", "ం") for index in range(9)]

    with pytest.raises(ShapeError, match="variants"):
        compile_mapping(shapes, [Recipe(("dot", "dot"), "ః")])
    assert 9 * 9 > MAX_VARIANTS


def test_recipe_with_a_single_name_is_an_error() -> None:
    with pytest.raises(ShapeError, match="at least two"):
        compile_mapping(SHAPES, [Recipe(("va_base",), "వ")])


def test_recipe_that_changes_how_its_neighbours_split_is_not_redundant() -> None:
    shapes = [Shape("a", "a", "అ"), Shape("b", "b", "బ"), Shape("c", "c", "చ")]

    mapping = _mapping(shapes, [Recipe(("a", "b"), "అబ"), Recipe(("b", "c"), "ఝ")])

    assert convert_anu("abc", mapping, Coverage()) == "అబచ"


def test_recipe_equal_to_concatenation_is_an_error() -> None:
    with pytest.raises(ShapeError, match="redundant"):
        compile_mapping(SHAPES, [Recipe(("na_base", "u_hook"), "ను")])


def test_recipe_that_overrides_a_shorter_recipe_is_not_redundant() -> None:
    mapping = _mapping(SHAPES, [MA, Recipe(("va_base", "u_hook", "na_base"), "వున")])

    assert convert_anu("=∞#", mapping, Coverage()) == "వున"


def test_glyph_string_with_two_outputs_is_an_error() -> None:
    with pytest.raises(ShapeError, match="maps to both"):
        compile_mapping(SHAPES, [MA, Recipe(("va_base", "u_hook"), "మా")])


def test_names_and_recipes_load_from_tsv(tmp_path: Path) -> None:
    names = tmp_path / "names.tsv"
    recipes = tmp_path / "recipes.tsv"
    names.write_text("glyph\tname\tunicode\n=\tva_base\tవ\nÚ\ttail\t\n", encoding="utf-8")
    recipes.write_text("names\tunicode\tnote\nva_base tail\tమ\tma\n", encoding="utf-8")

    assert load_shapes(names) == [Shape("=", "va_base", "వ"), Shape("Ú", "tail", "")]
    assert load_recipes(recipes) == [Recipe(("va_base", "tail"), "మ", "ma")]
