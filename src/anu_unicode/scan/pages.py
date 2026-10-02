from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from anu_unicode.scan.index import Occurrence


@dataclass(frozen=True)
class PageYield:
    page: int
    words: int
    shapes: int
    new_shapes: int
    covered_after: float


def rank_pages(occurrences: Iterable[Occurrence], excluded: frozenset[int]) -> list[PageYield]:
    shapes: dict[int, set[int]] = defaultdict(set)
    words: dict[int, set[tuple[int, int]]] = defaultdict(set)
    counts: dict[int, int] = defaultdict(int)
    for item in occurrences:
        if item.shape_id in excluded:
            continue
        shapes[item.page].add(item.shape_id)
        words[item.page].add((item.line, item.word))
        counts[item.shape_id] += 1
    total = sum(counts.values())
    seen: set[int] = set()
    covered = 0
    ranked = []
    remaining = set(shapes)
    while remaining:
        page = max(remaining, key=lambda number: (len(shapes[number] - seen), -number))
        new = shapes[page] - seen
        seen |= new
        covered += sum(counts[shape_id] for shape_id in new)
        ranked.append(PageYield(page, len(words[page]), len(shapes[page]), len(new), covered / total))
        remaining.remove(page)
    return ranked
