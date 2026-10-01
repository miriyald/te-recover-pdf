import re
from collections.abc import Sequence

from anu_unicode.convert import Segment
from anu_unicode.telugu import anu_orders, comparable, normalise

WIDENINGS = ((0, 1), (1, 0), (1, 1), (0, 2), (2, 0))

Solution = dict[str, str]


def _pattern(segments: Sequence[Segment], gap_names: dict[str, str]) -> re.Pattern[str]:
    parts: list[str] = []
    defined: set[str] = set()
    for glyphs, unicode in segments:
        if unicode is not None:
            parts.append(re.escape(unicode))
        elif glyphs in defined:
            parts.append(f"(?P={gap_names[glyphs]})")
        else:
            defined.add(glyphs)
            parts.append(f"(?P<{gap_names[glyphs]}>.+?)")
    return re.compile("".join(parts))


def _renders(segments: Sequence[Segment], solution: Solution, target: str) -> bool:
    rendered = normalise("".join(solution[glyphs] if unicode is None else unicode for glyphs, unicode in segments))
    return comparable(rendered) == comparable(target)


def _substrings(texts: set[str]) -> set[str]:
    return {normalise(text[start:end]) for text in texts for start in range(len(text)) for end in range(start + 1, len(text) + 1)}


def gap_solutions(segments: Sequence[Segment], target: str) -> list[Solution]:
    gap_names = {glyphs: f"g{index}" for index, glyphs in enumerate(dict.fromkeys(g for g, u in segments if u is None))}
    if len(gap_names) == 1:
        glyphs = next(iter(gap_names))
        return [{glyphs: value} for value in sorted(_substrings(anu_orders(target))) if _renders(segments, {glyphs: value}, target)]
    if not gap_names:
        return []
    pattern = _pattern(segments, gap_names)
    solutions: list[Solution] = []
    for variant in anu_orders(target):
        match = pattern.fullmatch(variant)
        if not match:
            continue
        solution = {glyphs: normalise(match.group(name)) for glyphs, name in gap_names.items()}
        if _renders(segments, solution, target) and solution not in solutions:
            solutions.append(solution)
    return solutions


def gap_candidates(segments: Sequence[Segment], target: str) -> set[str]:
    if sum(unicode is None for _, unicode in segments) != 1:
        return set()
    return {next(iter(solution.values())) for solution in gap_solutions(segments, target)}


def _is_letter(unicode: str | None) -> bool:
    return unicode is not None and any("ఀ" <= char <= "౿" for char in unicode)


def _widen(segments: Sequence[Segment], index: int, left: int, right: int) -> list[Segment] | None:
    start, end = index - left, index + right + 1
    if start < 0 or end > len(segments):
        return None
    if not all(_is_letter(unicode) for _, unicode in [*segments[start:index], *segments[index + 1:end]]):
        return None
    if not any(unicode is not None for _, unicode in [*segments[:start], *segments[end:]]):
        return None
    merged = ("".join(glyphs for glyphs, _ in segments[start:end]), None)
    return [*segments[:start], merged, *segments[end:]]


def _is_silent(segments: Sequence[Segment], target: str) -> bool:
    gap_glyphs = [glyphs for glyphs, unicode in segments if unicode is None]
    return len(gap_glyphs) == 1 and _renders(segments, {gap_glyphs[0]: ""}, target)


def solve_confirmed(segments: Sequence[Segment], target: str) -> Solution | None:
    widenings = [(0, right) for left, right in WIDENINGS if left == 0] if _is_silent(segments, target) else list(WIDENINGS)
    gap_indices = [index for index, (_, unicode) in enumerate(segments) if unicode is None]
    attempts: list[Sequence[Segment]] = [segments]
    attempts += [widened for index in gap_indices for left, right in widenings if (widened := _widen(segments, index, left, right))]
    for attempt in attempts:
        solutions = gap_solutions(attempt, target)
        if len(solutions) == 1:
            return solutions[0]
        if solutions:
            return None
    return None
