from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

from anu_unicode.scan.ink import Bitmap, Component
from anu_unicode.scan.profile import HeightUnit
from anu_unicode.scan.words import Band

GRID = 48
CANVAS = (128, 256)
CANVAS_HEIGHT = 64
MIN_SCALED_HEIGHT = 0.6
PROTOTYPE_SHARE = 0.5
SHIFT_TOLERANCE = 1.0
MIN_HOLE_AREA = 0.005
CANDIDATES = 8
SHIFTS = tuple(sorted(((rows, columns) for rows in (-1, 0, 1) for columns in (-1, 0, 1)), key=lambda shift: abs(shift[0]) + abs(shift[1])))
THICK = np.ones((3, 3), dtype=bool)
MAX_THICK_BLOB = 20
BANDS = tuple(Band)
PACKED = GRID * GRID // 64

Floats = NDArray[np.float64]
Integers = NDArray[np.int64]
Canvases = NDArray[np.uint16]
Words = NDArray[np.uint64]


@dataclass(frozen=True)
class Shape:
    grid: Bitmap
    canvas: Bitmap
    height: float
    aspect: float
    band: Band
    holes: int


def count_holes(mask: Bitmap, min_area: float) -> int:
    background, count = ndimage.label(np.pad(~mask, 1, constant_values=True))
    areas = np.bincount(background.ravel(), minlength=count + 1)[2:]
    return int((areas >= min_area).sum())


def _resized(mask: Bitmap, size: tuple[int, int]) -> Bitmap:
    image = Image.fromarray(mask.astype(np.uint8) * 255).resize(size, Image.Resampling.BILINEAR)
    return np.asarray(image) >= 128


def to_canvas(mask: Bitmap, body_height: float) -> Bitmap:
    height, width = mask.shape
    scale = min(CANVAS_HEIGHT / max(height, MIN_SCALED_HEIGHT * body_height), (CANVAS[0] - 4) / height, (CANVAS[1] - 4) / width)
    scaled = _resized(mask, (max(1, round(width * scale)), max(1, round(height * scale))))
    canvas = np.zeros(CANVAS, dtype=bool)
    top, left = (CANVAS[0] - scaled.shape[0]) // 2, (CANVAS[1] - scaled.shape[1]) // 2
    canvas[top:top + scaled.shape[0], left:left + scaled.shape[1]] = scaled
    return canvas


def shape_of(component: Component, band: Band, body_height: float) -> Shape:
    return Shape(_resized(component.mask, (GRID, GRID)), to_canvas(component.mask, body_height), component.height / body_height,
                 component.width / component.height, band, count_holes(component.mask, MIN_HOLE_AREA * body_height ** 2))


def _largest_blob(thick: Bitmap) -> int:
    labels, count = ndimage.label(thick)
    return int(np.bincount(labels.ravel())[1:].max()) if count else 0


def _thick_layers(canvas: Bitmap, prototype: Bitmap) -> Iterator[Bitmap]:
    ink = canvas | prototype
    rows, columns = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    region = (slice(max(rows[0] - 2, 0), rows[-1] + 3), slice(max(columns[0] - 2, 0), columns[-1] + 3))
    for shift in SHIFTS:
        difference = np.roll(prototype, shift, axis=(0, 1))[region] ^ canvas[region]
        yield np.asarray(ndimage.binary_erosion(difference, structure=THICK), dtype=bool)


def thick_blob(canvas: Bitmap, prototype: Bitmap) -> int:
    return min(_largest_blob(layer) for layer in _thick_layers(canvas, prototype))


def thick_difference(canvas: Bitmap, prototype: Bitmap) -> bool:
    return all(layer.sum() > MAX_THICK_BLOB and _largest_blob(layer) > MAX_THICK_BLOB for layer in _thick_layers(canvas, prototype))


def _far(grid: Bitmap) -> Bitmap:
    if not grid.any():
        return np.ones(grid.shape, dtype=bool)
    return np.asarray(ndimage.distance_transform_edt(~grid) > SHIFT_TOLERANCE, dtype=bool)


def _packed(grid: Bitmap) -> Words:
    return np.packbits(grid.ravel()).view(np.uint64)


def _overlap(rows: Words, query: Words) -> Integers:
    return np.bitwise_count(rows & query).sum(axis=1, dtype=np.int64)


@dataclass(frozen=True)
class Thresholds:
    distance: float
    height_drift: float
    aspect_drift: float


def _grown(rows: NDArray[Any], capacity: int) -> NDArray[Any]:
    grown = np.zeros((capacity, *rows.shape[1:]), dtype=rows.dtype)
    grown[:len(rows)] = rows
    return grown


@dataclass
class GridPrototypes:
    size: int = 0
    _ink: Words = field(default_factory=lambda: np.zeros((0, PACKED), dtype=np.uint64))
    _far: Words = field(default_factory=lambda: np.zeros((0, PACKED), dtype=np.uint64))
    _inked: Integers = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    sums: dict[int, Floats] = field(default_factory=dict)

    @classmethod
    def frozen(cls, grids: Sequence[Bitmap]) -> "GridPrototypes":
        prototypes = cls()
        for grid in grids:
            prototypes.add(grid)
        return prototypes

    @property
    def ink(self) -> Words:
        return self._ink[:self.size]

    @property
    def far(self) -> Words:
        return self._far[:self.size]

    @property
    def inked(self) -> Integers:
        return self._inked[:self.size]

    def add(self, grid: Bitmap) -> None:
        if self.size == len(self._ink):
            capacity = max(2 * self.size, 64)
            self._ink = _grown(self._ink, capacity)
            self._far = _grown(self._far, capacity)
            self._inked = _grown(self._inked, capacity)
        self.size += 1
        self._store(self.size - 1, grid)

    def update(self, index: int, grid: Bitmap, count: float) -> None:
        total = self.sums.setdefault(index, np.zeros(grid.shape))
        total += grid
        self._store(index, total / count >= PROTOTYPE_SHARE)

    def _store(self, index: int, grid: Bitmap) -> None:
        self.ink[index], self.far[index], self.inked[index] = _packed(grid), _packed(_far(grid)), int(grid.sum())

    def stray_share(self, grid: Bitmap, indices: Integers) -> Floats:
        own_stray = _overlap(self.far[indices], _packed(grid))
        their_stray = _overlap(self.ink[indices], _packed(_far(grid)))
        return np.asarray((own_stray + their_stray) / (int(grid.sum()) + self.inked[indices]), dtype=np.float64)

    def bitmap(self, index: int) -> Bitmap:
        return np.unpackbits(self.ink[index].view(np.uint8)).reshape(GRID, GRID).astype(bool)


@dataclass
class CanvasPrototypes:
    bitmaps: list[Bitmap] = field(default_factory=list)
    sums: dict[int, Canvases] = field(default_factory=dict)

    def add(self, canvas: Bitmap) -> None:
        self.bitmaps.append(canvas)

    def update(self, index: int, canvas: Bitmap, count: float) -> None:
        total = self.sums.setdefault(index, np.zeros(CANVAS, dtype=np.uint16))
        total += canvas
        self.bitmaps[index] = total / count >= PROTOTYPE_SHARE


@dataclass
class ShapeCatalog:
    thresholds: Thresholds
    frozen: int = 0
    counts: Floats = field(default_factory=lambda: np.zeros(0))
    heights: Floats = field(default_factory=lambda: np.zeros(0))
    aspects: Floats = field(default_factory=lambda: np.zeros(0))
    bands: Integers = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    holes: Integers = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    grids: GridPrototypes = field(default_factory=GridPrototypes)
    canvases: CanvasPrototypes = field(default_factory=CanvasPrototypes)
    shape_unit: HeightUnit = HeightUnit.MEDIAN

    def __len__(self) -> int:
        return len(self.counts)

    def distances(self, shape: Shape) -> Floats:
        result = np.full(len(self), np.inf)
        allowed = np.flatnonzero((self.bands == BANDS.index(shape.band)) & (self.holes == shape.holes)
                                 & (np.abs(np.log(shape.height / self.heights)) <= self.thresholds.height_drift)
                                 & (np.abs(np.log(shape.aspect / self.aspects)) <= self.thresholds.aspect_drift))
        if allowed.size and shape.grid.any():
            result[allowed] = self.grids.stray_share(shape.grid, allowed)
        return result

    def match(self, shape: Shape) -> int | None:
        distances = self.distances(shape)
        candidates = [int(index) for index in np.argsort(distances, kind="stable")[:CANDIDATES]
                      if distances[index] <= self.thresholds.distance]
        return next((index for index in candidates if not thick_difference(shape.canvas, self.canvases.bitmaps[index])), None)

    def keep(self, shape_id: int, shape: Shape) -> int:
        self._count(shape_id, shape)
        return shape_id

    def assign(self, shape: Shape) -> int:
        shape_id = self.match(shape)
        if shape_id is None:
            shape_id = self._add(shape)
        self._count(shape_id, shape)
        return shape_id

    def add_shapes(self, shapes: Sequence[Shape]) -> int:
        shape_id = self._add(shapes[0])
        for shape in shapes:
            self._count(shape_id, shape)
        return shape_id

    def _add(self, shape: Shape) -> int:
        self.counts = np.append(self.counts, 0.0)
        self.heights = np.append(self.heights, shape.height)
        self.aspects = np.append(self.aspects, shape.aspect)
        self.bands = np.append(self.bands, BANDS.index(shape.band))
        self.holes = np.append(self.holes, shape.holes)
        self.grids.add(shape.grid)
        self.canvases.add(shape.canvas)
        return len(self) - 1

    def _count(self, shape_id: int, shape: Shape) -> None:
        self.counts[shape_id] += 1
        if shape_id < self.frozen:
            return
        count = self.counts[shape_id]
        self.heights[shape_id] += (shape.height - self.heights[shape_id]) / count
        self.aspects[shape_id] += (shape.aspect - self.aspects[shape_id]) / count
        self.grids.update(shape_id, shape.grid, count)
        self.canvases.update(shape_id, shape.canvas, count)

    def prototype(self, shape_id: int) -> Bitmap:
        return self.grids.bitmap(shape_id)

    def prototype_shape(self, shape_id: int) -> Shape:
        return Shape(self.grids.bitmap(shape_id), self.canvases.bitmaps[shape_id], float(self.heights[shape_id]),
                     float(self.aspects[shape_id]), BANDS[self.bands[shape_id]], int(self.holes[shape_id]))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        canvases = np.packbits(np.array(self.canvases.bitmaps).reshape((-1, *CANVAS)), axis=2)
        np.savez_compressed(path, prototypes=self.grids.ink.view(np.uint8), canvases=canvases,
                            heights=self.heights, aspects=self.aspects, bands=self.bands, holes=self.holes,
                            thresholds=np.array([self.thresholds.distance, self.thresholds.height_drift, self.thresholds.aspect_drift]),
                            shape_unit=np.array(self.shape_unit.value))


def load_catalog(path: Path) -> ShapeCatalog:
    names = ("prototypes", "canvases", "heights", "aspects", "bands", "holes", "thresholds")
    with np.load(path) as data:
        arrays = {name: np.array(data[name]) for name in names}
        shape_unit = HeightUnit(str(data["shape_unit"])) if "shape_unit" in data.files else HeightUnit.MEDIAN
    grids = np.unpackbits(arrays["prototypes"], axis=1)[:, :GRID * GRID].reshape(-1, GRID, GRID).astype(bool)
    canvases = list(np.unpackbits(arrays["canvases"], axis=2)[:, :, :CANVAS[1]].astype(bool))
    return ShapeCatalog(Thresholds(*(float(value) for value in arrays["thresholds"].tolist())), frozen=len(grids),
                        counts=np.zeros(len(grids)), heights=arrays["heights"], aspects=arrays["aspects"], bands=arrays["bands"],
                        holes=arrays["holes"], grids=GridPrototypes.frozen(list(grids)), canvases=CanvasPrototypes(canvases),
                        shape_unit=shape_unit)
