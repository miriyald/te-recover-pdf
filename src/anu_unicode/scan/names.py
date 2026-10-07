import re
from collections.abc import Iterable, Mapping, Sequence

from anu_unicode.convert import Coverage, convert_anu
from anu_unicode.scan.source import shape_char
from anu_unicode.shape_naming.shapes import NOTHING, Recipe

NAME_BASE = 0x100000
SYMBOLIC = re.compile("[A-Za-z]")
NAME_CODE = re.compile(f"[{chr(NAME_BASE)}-{chr(0x10FFFD)}]")


class RecipeError(ValueError):
    pass


def is_symbolic(name: str) -> bool:
    return SYMBOLIC.search(name) is not None


def validate_recipes(recipes: Iterable[Recipe], symbolic_names: set[str]) -> None:
    seen: dict[tuple[str, ...], str] = {}
    for recipe in recipes:
        unknown = [name for name in recipe.names if is_symbolic(name) and name not in symbolic_names]
        if unknown:
            raise RecipeError(f"recipe {recipe.names} uses unknown names {unknown}")
        if seen.get(recipe.names, recipe.unicode) != recipe.unicode:
            raise RecipeError(f"recipe {recipe.names} maps to both {seen[recipe.names]!r} and {recipe.unicode!r}")
        seen[recipe.names] = recipe.unicode


class Speller:
    def __init__(self, recipes: Sequence[Recipe]) -> None:
        self.recipes = tuple(recipes)
        self._codes: dict[str, str] = {}
        self._names: dict[str, str] = {}

    def covers(self, names: tuple[str, ...]) -> bool:
        return any(recipe.names == names for recipe in self.recipes)

    def _code(self, name: str) -> str:
        if name not in self._codes:
            code = chr(NAME_BASE + len(self._codes))
            self._codes[name], self._names[code] = code, name
        return self._codes[name]

    def _mapping(self, present: set[str], recipes: Iterable[Recipe]) -> dict[str, str]:
        mapping = {self._code(name): "" if name == NOTHING else name for name in present if not is_symbolic(name)}
        for recipe in recipes:
            if set(recipe.names) <= present:
                mapping["".join(self._code(name) for name in recipe.names)] = recipe.contribution
        return mapping

    def spell(self, shape_ids: Sequence[int], names: Mapping[int, str], extra: Sequence[Recipe] = ()) -> str:
        tokens = "".join(self._code(names[shape_id]) if shape_id in names else shape_char(shape_id) for shape_id in shape_ids)
        present = {names[shape_id] for shape_id in shape_ids if shape_id in names}
        text = convert_anu(tokens, self._mapping(present, (*self.recipes, *extra)), Coverage())
        return NAME_CODE.sub(lambda match: self._names[match.group()], text)
