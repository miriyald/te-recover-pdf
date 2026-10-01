from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product
from math import prod
from pathlib import Path

from anu_unicode.convert import Coverage, convert_segments, render
from anu_unicode.mapping import MappingEntry, read_rows
from anu_unicode.telugu import mark_visible_virama, normalise

MAX_VARIANTS = 64
NOTHING = "∅"


class ShapeError(ValueError):
    pass


@dataclass(frozen=True)
class Shape:
    glyph: str
    name: str
    unicode: str

    @property
    def contribution(self) -> str:
        return "" if self.unicode == NOTHING else self.unicode


@dataclass(frozen=True)
class Recipe:
    names: tuple[str, ...]
    unicode: str
    note: str = ""


def load_shapes(path: Path) -> list[Shape]:
    return [Shape(row["glyph"], row["name"], row.get("unicode", "")) for row in read_rows(path)]


def load_recipes(path: Path) -> list[Recipe]:
    return [Recipe(tuple(row["names"].split()), row["unicode"], row.get("note", "")) for row in read_rows(path)]


def _groups(shapes: Sequence[Shape]) -> dict[str, list[Shape]]:
    groups: dict[str, list[Shape]] = defaultdict(list)
    seen: set[str] = set()
    for shape in shapes:
        if shape.glyph in seen:
            raise ShapeError(f"glyph {shape.glyph!r} is listed twice")
        seen.add(shape.glyph)
        groups[shape.name].append(shape)
    for name, members in groups.items():
        values = sorted({member.unicode for member in members})
        if len(values) > 1:
            raise ShapeError(f"name {name!r} has several unicode values: {values}")
    return groups


def _expand(recipe: Recipe, groups: dict[str, list[Shape]]) -> list[str]:
    if len(recipe.names) < 2:
        raise ShapeError(f"recipe {recipe.names} needs at least two names; give a single shape its unicode in names.tsv")
    unknown = [name for name in recipe.names if name not in groups]
    if unknown:
        raise ShapeError(f"recipe {recipe.names} uses unknown names {unknown}")
    variants = prod(len(groups[name]) for name in recipe.names)
    if variants > MAX_VARIANTS:
        raise ShapeError(f"recipe {recipe.names} expands to {variants} variants (limit {MAX_VARIANTS})")
    return ["".join(glyphs) for glyphs in product(*([shape.glyph for shape in groups[name]] for name in recipe.names))]


def _straddles(glyphs: str, key: str) -> bool:
    return any(glyphs.endswith(key[:cut]) or glyphs.startswith(key[cut:]) for cut in range(1, len(key)))


def _check_needed(recipe: Recipe, glyph_strings: Sequence[str], entries: dict[str, MappingEntry]) -> None:
    others = {glyphs: entry.unicode for glyphs, entry in entries.items() if glyphs not in glyph_strings}
    expected = mark_visible_virama(normalise(recipe.unicode))
    same_output = all(render(convert_segments(glyphs, others), Coverage()) == expected for glyphs in glyph_strings)
    if same_output and not any(_straddles(glyphs, key) for glyphs in glyph_strings for key in others if len(key) > 1):
        raise ShapeError(f"recipe {recipe.names} is redundant: the other entries already give {recipe.unicode!r}")


def _add(entries: dict[str, MappingEntry], glyphs: str, unicode: str) -> None:
    current = entries.get(glyphs)
    if current is not None and current.unicode != unicode:
        raise ShapeError(f"{glyphs!r} maps to both {current.unicode!r} and {unicode!r}")
    entries[glyphs] = MappingEntry(glyphs, unicode)


def compile_mapping(shapes: Sequence[Shape], recipes: Sequence[Recipe]) -> dict[str, MappingEntry]:
    groups = _groups(shapes)
    entries: dict[str, MappingEntry] = {}
    for shape in shapes:
        if shape.unicode:
            _add(entries, shape.glyph, shape.contribution)
    expansions = [(recipe, _expand(recipe, groups)) for recipe in recipes]
    for recipe, glyph_strings in expansions:
        for glyphs in glyph_strings:
            _add(entries, glyphs, recipe.unicode)
    for recipe, glyph_strings in expansions:
        _check_needed(recipe, glyph_strings, entries)
    return entries
