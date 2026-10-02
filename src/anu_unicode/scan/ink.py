from dataclasses import dataclass

import numpy as np
import pymupdf
from numpy.typing import NDArray
from scipy import ndimage

INK_THRESHOLD = 128

Bitmap = NDArray[np.bool_]
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Component:
    bbox: Box
    mask: Bitmap

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


def pixels_per_point(page: pymupdf.Page) -> float:
    return float(page.get_images(full=True)[0][2] / page.rect.width)


def render_ink(page: pymupdf.Page) -> Bitmap:
    scale = pixels_per_point(page)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY)
    gray = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width)
    return gray < INK_THRESHOLD


def find_components(ink: Bitmap, min_area: int) -> list[Component]:
    labels, _ = ndimage.label(ink, structure=np.ones((3, 3)))
    components = []
    for index, region in enumerate(ndimage.find_objects(labels), start=1):
        mask = labels[region] == index
        if mask.size >= min_area:
            components.append(Component((region[1].start, region[0].start, region[1].stop, region[0].stop), mask))
    return components


def median_height(components: list[Component]) -> float:
    return float(np.median([component.height for component in components]))
