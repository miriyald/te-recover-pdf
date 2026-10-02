from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from anu_unicode.scan.catalog import Shape, ShapeCatalog, shape_of
from anu_unicode.scan.ink import Bitmap, Component
from anu_unicode.scan.page import ScanPage
from anu_unicode.scan.words import Placed, ScanWord, classify

MIN_PART = 0.2
CUT_CANDIDATES = 6
NECK = 0.3
NECK_SHARE = 0.5
SPLIT_DISTANCE = 0.25


@dataclass(frozen=True)
class Alphabet:
    catalog: ShapeCatalog
    frequent: NDArray[np.bool_]

    def nearest(self, shape: Shape) -> float:
        distances = self.catalog.distances(shape)[self.frequent]
        return float(distances.min()) if distances.size else float("inf")

    def explains(self, shape: Shape) -> bool:
        return self.nearest(shape) <= self.catalog.thresholds.distance


def frequent_alphabet(catalog: ShapeCatalog, counts: NDArray[np.float64], min_count: int) -> Alphabet:
    return Alphabet(catalog, counts >= min_count)


def _trimmed(mask: Bitmap, left: int, top: int) -> Component | None:
    rows, columns = np.flatnonzero(mask.any(axis=1)), np.flatnonzero(mask.any(axis=0))
    if not rows.size:
        return None
    first_row, last_row, first_column, last_column = int(rows[0]), int(rows[-1]) + 1, int(columns[0]), int(columns[-1]) + 1
    return Component((left + first_column, top + first_row, left + last_column, top + last_row),
                     mask[first_row:last_row, first_column:last_column])


def _is_neck(mask: Bitmap, profile: NDArray[np.int64], column: int, body_height: float) -> bool:
    runs = int(np.count_nonzero(np.diff(mask[:, column].astype(np.int8)) == 1) + mask[0, column])
    thinner_than_sides = profile[column] <= NECK_SHARE * min(profile[:column].max(), profile[column + 1:].max())
    return runs == 1 and profile[column] <= NECK * body_height and bool(thinner_than_sides)


def neck_columns(mask: Bitmap, body_height: float) -> list[int]:
    width = mask.shape[1]
    low, high = max(1, round(MIN_PART * width)), min(width - 1, round((1 - MIN_PART) * width))
    if low >= high:
        return []
    profile = mask.sum(axis=0)
    thinnest = np.argsort(profile[low:high], kind="stable")[:CUT_CANDIDATES] + low
    return sorted(int(column) for column in thinnest if _is_neck(mask, profile, int(column), body_height))


def split_fused(placed: Placed, band: tuple[int, int], body_height: float, alphabet: Alphabet,
                explained: bool) -> tuple[Placed, Placed] | None:
    component = placed.component
    candidates: list[tuple[bool, float, tuple[Placed, Placed]]] = []
    for column in neck_columns(component.mask, body_height):
        left = _trimmed(component.mask[:, :column], component.bbox[0], component.bbox[1])
        right = _trimmed(component.mask[:, column:], component.bbox[0] + column, component.bbox[1])
        if left is None or right is None:
            continue
        parts = Placed(left, classify(left, band)), Placed(right, classify(right, band))
        distances = [alphabet.nearest(shape_of(part.component, part.band, body_height)) for part in parts]
        if max(distances) <= alphabet.catalog.thresholds.distance:
            candidates.append((False, max(distances), parts))
        elif not explained and min(distances) <= SPLIT_DISTANCE:
            candidates.append((True, min(distances), parts))
    return min(candidates, key=lambda candidate: candidate[:2])[2] if candidates else None


def _split_word(word: ScanWord, body_height: float, alphabet: Alphabet) -> ScanWord:
    glyphs: list[Placed] = []
    for placed in word.glyphs:
        explained = alphabet.explains(shape_of(placed.component, placed.band, body_height))
        glyphs.extend(split_fused(placed, word.band, body_height, alphabet, explained) or (placed,))
    return ScanWord(tuple(glyphs), word.band)


def split_page(page: ScanPage, alphabet: Alphabet) -> ScanPage:
    lines = [[_split_word(word, page.body_height, alphabet) for word in line] for line in page.lines]
    return ScanPage(page.number, page.body_height, lines)
