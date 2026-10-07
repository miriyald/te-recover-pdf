from anu_unicode.scan.inference import WordEvidence
from anu_unicode.scan.names import Speller
from anu_unicode.scan.recipes import RecipeProposal, propose_recipes
from anu_unicode.shape_naming.shapes import Recipe

NAMES = {1: "గ", 2: "o_tick", 3: "డ", 11: "గ"}


def test_words_with_a_named_piece_propose_the_recipe_that_reproduces_them() -> None:
    words = [WordEvidence((1, 2), "గో"), WordEvidence((11, 2, 3), "గోడ"), WordEvidence((1, 2), "గో")]

    assert propose_recipes(words, NAMES, Speller([])) == [RecipeProposal(("గ", "o_tick"), "గో", votes=3, share=1.0)]


def test_too_few_or_split_votes_propose_nothing() -> None:
    few = [WordEvidence((1, 2), "గో"), WordEvidence((1, 2), "గో")]
    split = [*few, WordEvidence((1, 2), "గొ"), WordEvidence((1, 2), "గొ")]

    assert not propose_recipes(few, NAMES, Speller([]))
    assert not propose_recipes(split, NAMES, Speller([]))


def test_a_pair_already_covered_by_a_recipe_is_not_proposed_again() -> None:
    words = [WordEvidence((1, 2), "గో")] * 3

    assert not propose_recipes(words, NAMES, Speller([Recipe(("గ", "o_tick"), "గో")]))
