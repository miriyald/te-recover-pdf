from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage

from anu_unicode.scan.catalog import (
    CANVAS,
    GRID,
    SHIFT_TOLERANCE,
    GridPrototypes,
    ShapeCatalog,
    Thresholds,
    count_holes,
    load_catalog,
    shape_of,
    thick_difference,
)
from anu_unicode.scan.ink import Component
from anu_unicode.scan.profile import HeightUnit
from anu_unicode.scan.words import Band

BODY = 50.0
THRESHOLDS = Thresholds(distance=0.15, height_drift=0.2, aspect_drift=0.25)


def _ring(size: int = 50, stroke: int = 6) -> np.ndarray:
    mask = np.ones((size, size), dtype=bool)
    mask[stroke:-stroke, stroke:-stroke] = False
    return mask


def _bar(size: int = 50, stroke: int = 6) -> np.ndarray:
    mask = np.zeros((size, size), dtype=bool)
    mask[:, :stroke] = True
    mask[:stroke, :] = True
    mask[-stroke:, :] = True
    return mask


def _component(mask: np.ndarray) -> Component:
    return Component((0, 0, mask.shape[1], mask.shape[0]), mask)


def test_holes_are_counted_ignoring_pinholes() -> None:
    ring = _ring()
    ring[2, 2] = False

    assert count_holes(ring, min_area=10) == 1
    assert count_holes(_bar(), min_area=10) == 0


def test_same_shape_with_a_one_pixel_shift_gets_the_same_id() -> None:
    catalog = ShapeCatalog(THRESHOLDS)
    shifted = np.roll(_ring(), 1, axis=1)

    first = catalog.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    second = catalog.assign(shape_of(_component(shifted), Band.MAIN, BODY))

    assert first == second
    assert len(catalog) == 1


def test_open_and_closed_shapes_never_share_an_id() -> None:
    catalog = ShapeCatalog(THRESHOLDS)

    closed = catalog.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    open_shape = catalog.assign(shape_of(_component(_bar()), Band.MAIN, BODY))

    assert closed != open_shape


def test_same_shape_at_a_different_size_or_band_gets_a_new_id() -> None:
    catalog = ShapeCatalog(THRESHOLDS)
    small = _ring(size=25, stroke=3)

    base = catalog.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    smaller = catalog.assign(shape_of(_component(small), Band.MAIN, BODY))
    above = catalog.assign(shape_of(_component(_ring()), Band.ABOVE, BODY))

    assert len({base, smaller, above}) == 3


def _letter(extra_stroke: bool = False, thicker: bool = False) -> np.ndarray:
    canvas = np.zeros(CANVAS, dtype=bool)
    stroke = 6 if thicker else 5
    canvas[20:60, 40:40 + stroke] = True
    canvas[20:20 + stroke, 40:100] = True
    if extra_stroke:
        canvas[40:40 + stroke, 70:100] = True
    return canvas


def test_a_missing_stroke_is_a_thick_difference() -> None:
    assert thick_difference(_letter(extra_stroke=True), _letter())


def test_a_one_pixel_shift_or_a_heavier_stroke_is_not_a_difference() -> None:
    assert not thick_difference(np.roll(_letter(), 1, axis=1), _letter())
    assert not thick_difference(_letter(thicker=True), _letter())


def test_wide_shapes_that_differ_only_in_their_base_get_different_ids() -> None:
    tail = np.zeros((50, 200), dtype=bool)
    tail[:, 60:200] = True
    first, second = tail.copy(), tail.copy()
    first[:, :8] = True
    second[:8, :60] = True
    catalog = ShapeCatalog(Thresholds(distance=0.3, height_drift=0.2, aspect_drift=0.25))

    ids = {catalog.assign(shape_of(_component(mask), Band.MAIN, BODY)) for mask in (first, second)}

    assert len(ids) == 2


def test_saved_catalog_keeps_ids_and_freezes_their_prototypes(tmp_path: Path) -> None:
    catalog = ShapeCatalog(THRESHOLDS)
    ring_id = catalog.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    catalog.save(tmp_path / "catalog.npz")

    loaded = load_catalog(tmp_path / "catalog.npz")
    again = loaded.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    new = loaded.assign(shape_of(_component(_bar()), Band.MAIN, BODY))

    assert (again, new) == (ring_id, 1)
    assert loaded.frozen == 1
    assert np.array_equal(loaded.prototype(ring_id), catalog.prototype(ring_id))


def test_a_catalog_grown_past_its_capacity_keeps_every_prototype_through_save_and_load(tmp_path: Path) -> None:
    catalog = ShapeCatalog(THRESHOLDS)
    random = np.random.default_rng(3)
    blocks = [np.kron(random.random((10, 10)) > 0.5, np.ones((5, 5), dtype=bool)) for _ in range(100)]
    shapes = [shape_of(_component(mask), Band.MAIN, BODY) for mask in blocks]
    ids = [catalog.assign(shape) for shape in shapes]
    catalog.save(tmp_path / "catalog.npz")

    loaded = load_catalog(tmp_path / "catalog.npz")

    assert len(set(ids)) > 64
    assert all(np.array_equal(loaded.prototype(shape_id), catalog.prototype(shape_id)) for shape_id in set(ids))
    assert [loaded.match(shape) for shape in shapes] == [catalog.match(shape) for shape in shapes]
    with pytest.raises(IndexError):
        catalog.prototype(len(catalog))


def _reference_stray_share(grid: np.ndarray, prototypes: list[np.ndarray]) -> np.ndarray:
    def far(mask: np.ndarray) -> np.ndarray:
        return ndimage.distance_transform_edt(~mask).ravel() > SHIFT_TOLERANCE if mask.any() else np.ones(mask.size, dtype=bool)
    pixels = grid.ravel().astype(np.float64)
    bitmaps = np.array([prototype.ravel() for prototype in prototypes], dtype=np.float64)
    own = np.array([far(prototype) for prototype in prototypes], dtype=np.float64) @ pixels
    return np.asarray((own + bitmaps @ far(grid)) / (pixels.sum() + bitmaps.sum(axis=1)))


def test_stray_share_matches_the_float_distance_map_formula() -> None:
    random = np.random.default_rng(5)
    blank = np.zeros((GRID, GRID), dtype=bool)
    prototypes = [random.random((GRID, GRID)) > threshold for threshold in np.linspace(0.3, 0.97, 70)] + [blank]
    grids = GridPrototypes.frozen(prototypes)
    query = random.random((GRID, GRID)) > 0.8

    shares = grids.stray_share(query, np.arange(len(prototypes)))

    assert np.array_equal(shares, _reference_stray_share(query, prototypes))


def test_shapes_split_off_an_id_become_a_new_id_after_the_frozen_ones(tmp_path: Path) -> None:
    catalog = ShapeCatalog(Thresholds(0.2, 0.2, 0.25))
    catalog.assign(shape_of(_component(_bar()), Band.MAIN, 50.0))
    catalog.save(tmp_path / "catalog.npz")
    frozen = load_catalog(tmp_path / "catalog.npz")

    new_id = frozen.add_shapes([shape_of(_component(_ring()), Band.MAIN, 50.0)] * 3)

    assert new_id == 1
    assert frozen.match(shape_of(_component(_ring()), Band.MAIN, 50.0)) == 1


def test_a_saved_catalog_remembers_the_height_unit_its_shapes_were_scaled_by(tmp_path: Path) -> None:
    catalog = ShapeCatalog(THRESHOLDS, shape_unit=HeightUnit.LETTER)
    catalog.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    catalog.save(tmp_path / "catalog.npz")

    assert load_catalog(tmp_path / "catalog.npz").shape_unit == HeightUnit.LETTER


def test_a_catalog_saved_before_units_were_recorded_is_median_scaled(tmp_path: Path) -> None:
    catalog = ShapeCatalog(THRESHOLDS)
    catalog.assign(shape_of(_component(_ring()), Band.MAIN, BODY))
    catalog.save(tmp_path / "catalog.npz")
    with np.load(tmp_path / "catalog.npz") as data:
        np.savez(tmp_path / "old.npz", **{name: data[name] for name in data.files if name != "shape_unit"})

    assert load_catalog(tmp_path / "old.npz").shape_unit == HeightUnit.MEDIAN
