from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

from anu_unicode.scan.ink import Bitmap, Component
from anu_unicode.scan.words import Band

GRID = 48
CANVAS = (128, 256)
CANVAS_HEIGHT = 64
MIN_SCALED_HEIGHT = 0.6
PROTOTYPE_SHARE = 0.5
SHIFT_TOLERANCE = 1.0
MIN_HOLE_AREA = 0.005
CANDIDATES = 8
SHIFTS = tuple((rows, columns) for rows in (-1, 0, 1) for columns in (-1, 0, 1))
THICK = np.ones((1, 3, 3), dtype=bool)
MAX_THICK_BLOB = 20
BANDS = tuple(Band)

Floats = NDArray[np.float64]
Integers = NDArray[np.int64]
Canvases = NDArray[np.uint16]


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


def thick_blob(canvas: Bitmap, prototype: Bitmap) -> int:
    ink = canvas | prototype
    rows, columns = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    region = (slice(max(rows[0] - 2, 0), rows[-1] + 3), slice(max(columns[0] - 2, 0), columns[-1] + 3))
    shifted = np.stack([np.roll(prototype, shift, axis=(0, 1))[region] for shift in SHIFTS])
    thick = ndimage.binary_erosion(shifted ^ canvas[region], structure=THICK)
    return min(_largest_blob(layer) for layer in thick)


def thick_difference(canvas: Bitmap, prototype: Bitmap) -> bool:
    return thick_blob(canvas, prototype) > MAX_THICK_BLOB


def _distance_map(grid: Bitmap) -> Floats:
    return np.asarray(ndimage.distance_transform_edt(~grid), dtype=np.float64).ravel() if grid.any() else np.full(GRID * GRID, float(GRID))


@dataclass(frozen=True)
class Thresholds:
    distance: float
    height_drift: float
    aspect_drift: float


@dataclass
class GridPrototypes:
    sums: Floats = field(default_factory=lambda: np.zeros((0, GRID * GRID)))
    bitmaps: Floats = field(default_factory=lambda: np.zeros((0, GRID * GRID)))
    distance_maps: Floats = field(default_factory=lambda: np.zeros((0, GRID * GRID)))

    @classmethod
    def frozen(cls, bitmaps: Floats) -> "GridPrototypes":
        distance_maps = np.array([_distance_map(bitmap.reshape(GRID, GRID) > 0) for bitmap in bitmaps]).reshape(-1, GRID * GRID)
        return cls(np.zeros_like(bitmaps), bitmaps, distance_maps)

    def add(self, grid: Bitmap) -> None:
        self.sums = np.vstack([self.sums, np.zeros(GRID * GRID)])
        self.bitmaps = np.vstack([self.bitmaps, grid.ravel().astype(np.float64)])
        self.distance_maps = np.vstack([self.distance_maps, _distance_map(grid)])

    def update(self, index: int, grid: Bitmap, count: float) -> None:
        self.sums[index] += grid.ravel()
        self.bitmaps[index] = self.sums[index] / count >= PROTOTYPE_SHARE
        self.distance_maps[index] = _distance_map(self.bitmaps[index].reshape(GRID, GRID) > 0)

    def stray_share(self, grid: Bitmap, indices: Integers) -> Floats:
        pixels = grid.ravel().astype(np.float64)
        bitmaps = self.bitmaps[indices]
        own_stray = (self.distance_maps[indices] > SHIFT_TOLERANCE) @ pixels
        their_stray = bitmaps @ (_distance_map(grid) > SHIFT_TOLERANCE)
        return np.asarray((own_stray + their_stray) / (pixels.sum() + bitmaps.sum(axis=1)), dtype=np.float64)

    def bitmap(self, index: int) -> Bitmap:
        return np.asarray(self.bitmaps[index].reshape(GRID, GRID) > 0, dtype=np.bool_)


@dataclass
class CanvasPrototypes:
    sums: list[Canvases] = field(default_factory=list)
    bitmaps: list[Bitmap] = field(default_factory=list)

    @classmethod
    def frozen(cls, bitmaps: list[Bitmap]) -> "CanvasPrototypes":
        return cls([np.zeros(CANVAS, dtype=np.uint16) for _ in bitmaps], bitmaps)

    def add(self, canvas: Bitmap) -> None:
        self.sums.append(np.zeros(CANVAS, dtype=np.uint16))
        self.bitmaps.append(canvas)

    def update(self, index: int, canvas: Bitmap, count: float) -> None:
        self.sums[index] += canvas
        self.bitmaps[index] = self.sums[index] / count >= PROTOTYPE_SHARE


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

    def assign(self, shape: Shape) -> int:
        shape_id = self.match(shape)
        if shape_id is None:
            shape_id = self._add(shape)
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
        np.savez_compressed(path, prototypes=np.packbits(self.grids.bitmaps > 0, axis=1), canvases=canvases,
                            heights=self.heights, aspects=self.aspects, bands=self.bands, holes=self.holes,
                            thresholds=np.array([self.thresholds.distance, self.thresholds.height_drift, self.thresholds.aspect_drift]))


def load_catalog(path: Path) -> ShapeCatalog:
    names = ("prototypes", "canvases", "heights", "aspects", "bands", "holes", "thresholds")
    with np.load(path) as data:
        arrays = {name: np.array(data[name]) for name in names}
    grids = np.unpackbits(arrays["prototypes"], axis=1)[:, :GRID * GRID].astype(np.float64)
    canvases = list(np.unpackbits(arrays["canvases"], axis=2)[:, :, :CANVAS[1]].astype(bool))
    return ShapeCatalog(Thresholds(*(float(value) for value in arrays["thresholds"].tolist())), frozen=len(grids),
                        counts=np.zeros(len(grids)), heights=arrays["heights"], aspects=arrays["aspects"], bands=arrays["bands"],
                        holes=arrays["holes"], grids=GridPrototypes.frozen(grids), canvases=CanvasPrototypes.frozen(canvases))
