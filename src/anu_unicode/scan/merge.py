import numpy as np

from anu_unicode.scan.catalog import MAX_THICK_BLOB, ShapeCatalog, thick_blob, to_canvas
from anu_unicode.scan.index import Member, ShapeIndex

WIDE_STRAY = 0.35
MERGE_CANDIDATES = 16
MERGE_SHARE = 0.8
MAX_ROUNDS = 5


def candidate_ids(catalog: ShapeCatalog, shape_id: int, limit: int) -> list[int]:
    distances = catalog.distances(catalog.prototype_shape(shape_id))
    distances[shape_id] = np.inf
    ranked = np.argsort(distances, kind="stable")[:limit]
    return [int(index) for index in ranked if distances[index] <= WIDE_STRAY]


def member_share(catalog: ShapeCatalog, members: list[Member], target: int) -> float:
    prototype = catalog.canvases.bitmaps[target]
    passing = [thick_blob(to_canvas(member.mask, member.body_height), prototype) <= MAX_THICK_BLOB for member in members]
    return sum(passing) / len(passing)


def _larger(catalog: ShapeCatalog, first: int, second: int) -> bool:
    return (catalog.counts[first], -first) > (catalog.counts[second], -second)


def _best_target(index: ShapeIndex, shape_id: int, merged: dict[int, int]) -> int | None:
    catalog = index.catalog
    bigger = [other for other in candidate_ids(catalog, shape_id, MERGE_CANDIDATES)
              if other not in merged and catalog.counts[other] and _larger(catalog, other, shape_id)]
    shares = {other: member_share(catalog, index.members[shape_id], other) for other in bigger}
    best = max(shares, key=lambda other: (shares[other], catalog.counts[other]), default=None)
    return best if best is not None and shares[best] >= MERGE_SHARE else None


def duplicate_targets(index: ShapeIndex) -> dict[int, int]:
    catalog = index.catalog
    targets: dict[int, int] = {}
    live = [int(shape_id) for shape_id in np.flatnonzero(catalog.counts) if shape_id >= catalog.frozen]
    for shape_id in sorted(live, key=lambda shape_id: (catalog.counts[shape_id], shape_id)):
        target = _best_target(index, shape_id, targets)
        if target is not None:
            targets[shape_id] = target
    return {source: _root(targets, source) for source in targets}


def _root(targets: dict[int, int], shape_id: int) -> int:
    while shape_id in targets:
        shape_id = targets[shape_id]
    return shape_id


def merge_duplicates(index: ShapeIndex) -> list[int]:
    merged_per_round = []
    for _ in range(MAX_ROUNDS):
        targets = duplicate_targets(index)
        if not targets:
            break
        index.merge(targets)
        merged_per_round.append(len(targets))
    return merged_per_round
