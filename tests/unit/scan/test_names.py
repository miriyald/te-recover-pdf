import pytest

from anu_unicode.scan.names import RecipeError, Speller, is_symbolic, validate_recipes
from anu_unicode.scan.source import shape_char
from anu_unicode.shape_naming.shapes import NOTHING, Recipe


def test_a_name_with_latin_letters_is_symbolic_and_telugu_or_nothing_is_not() -> None:
    assert is_symbolic("ai_bottom")
    assert not is_symbolic("ై")
    assert not is_symbolic(NOTHING)
    assert not is_symbolic("(")


def test_unicode_names_spell_themselves_and_nothing_adds_nothing() -> None:
    speller = Speller([])

    assert speller.spell([1, 2, 3], {1: "క", 2: "ా", 3: NOTHING}) == "కా"


def test_a_recipe_turns_a_name_sequence_into_text() -> None:
    speller = Speller([Recipe(("ె", "ai_bottom"), "ై")])

    assert speller.spell([1, 2, 3, 4], {1: "వ", 2: "ె", 3: "ai_bottom", 4: "పు"}) == "వైపు"


def test_a_symbolic_name_no_recipe_covers_shows_as_a_named_gap() -> None:
    assert Speller([]).spell([1, 2], {1: "వ", 2: "ai_bottom"}) == "వ⟦ai_bottom⟧"


def test_an_unlabelled_shape_shows_as_a_numbered_gap() -> None:
    assert Speller([]).spell([1, 77], {1: "క"}) == f"క⟦{shape_char(77)}⟧"


def test_an_extra_recipe_applies_to_one_spelling_only() -> None:
    speller = Speller([])
    names = {1: "గ", 2: "o_tick"}

    assert speller.spell([1, 2], names, extra=[Recipe(("గ", "o_tick"), "గో")]) == "గో"
    assert speller.spell([1, 2], names) == "గ⟦o_tick⟧"


def test_recipes_must_use_known_symbolic_names_and_must_not_conflict() -> None:
    validate_recipes([Recipe(("ె", "ai_bottom"), "ై")], {"ai_bottom"})

    with pytest.raises(RecipeError, match="unknown"):
        validate_recipes([Recipe(("ె", "ai_tail"), "ై")], {"ai_bottom"})
    with pytest.raises(RecipeError, match="both"):
        validate_recipes([Recipe(("ె", "ai_bottom"), "ై"), Recipe(("ె", "ai_bottom"), "ే")], {"ai_bottom"})
