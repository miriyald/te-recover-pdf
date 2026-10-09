from dataclasses import dataclass

import numpy as np
import pymupdf
from scipy import ndimage

from anu_unicode.scan.ink import Component, find_components, render_ink
from anu_unicode.scan.profile import Grouping, ScanProfile, unit_height
from anu_unicode.scan.words import ScanWord, page_words

MIN_AREA = 40
MARGIN_ZONE = 0.15


@dataclass(frozen=True)
class ScanPage:
    number: int
    body_height: float
    lines: list[list[ScanWord]]


def _inside(inner: Component, outer: Component) -> bool:
    return inner is not outer and outer.bbox[0] <= inner.bbox[0] and outer.bbox[1] <= inner.bbox[1] \
        and inner.bbox[2] <= outer.bbox[2] and inner.bbox[3] <= outer.bbox[3]


def _text_area(rules: list[Component], page_height: int) -> tuple[int, int]:
    head = [rule.bbox[3] for rule in rules if rule.bbox[1] < MARGIN_ZONE * page_height]
    foot = [rule.bbox[1] for rule in rules if rule.bbox[3] > (1 - MARGIN_ZONE) * page_height]
    return max(head, default=0), min(foot, default=page_height)


def _in_hole(inner: Component, outer: Component) -> bool:
    background, _ = ndimage.label(np.pad(~outer.mask, 1, constant_values=True))
    row = (inner.bbox[1] + inner.bbox[3]) // 2 - outer.bbox[1] + 1
    column = (inner.bbox[0] + inner.bbox[2]) // 2 - outer.bbox[0] + 1
    return bool(background[row, column] > 1)


def _union_box(parts: list[Component]) -> tuple[int, int, int, int]:
    return (min(part.bbox[0] for part in parts), min(part.bbox[1] for part in parts),
            max(part.bbox[2] for part in parts), max(part.bbox[3] for part in parts))


def _canvas(box: tuple[int, int, int, int], parts: list[Component]) -> np.ndarray:
    mask = np.zeros((box[3] - box[1], box[2] - box[0]), dtype=bool)
    for part in parts:
        mask[part.bbox[1] - box[1]:part.bbox[3] - box[1], part.bbox[0] - box[0]:part.bbox[2] - box[0]] |= part.mask
    return mask


def _joined(parts: list[Component]) -> Component:
    box = _union_box(parts)
    return Component(box, _canvas(box, parts))


def _pixel_gap(fragment: Component, host: Component) -> float:
    box = _union_box([fragment, host])
    distance = ndimage.distance_transform_edt(~_canvas(box, [host]))
    top, left = fragment.bbox[1] - box[1], fragment.bbox[0] - box[0]
    return float(distance[top:top + fragment.height, left:left + fragment.width][fragment.mask].min())


def _box_gap(first: Component, second: Component) -> int:
    horizontal = max(second.bbox[0] - first.bbox[2], first.bbox[0] - second.bbox[2])
    return max(horizontal, second.bbox[1] - first.bbox[3], first.bbox[1] - second.bbox[3])


def repaired(components: list[Component], height: float, grouping: Grouping) -> list[Component]:
    size, gap = grouping.repair_size * height, grouping.repair_gap * height
    hosts = [index for index, component in enumerate(components) if max(component.width, component.height) >= size]
    attached: dict[int, list[Component]] = {}
    for fragment in components:
        if max(fragment.width, fragment.height) >= size:
            continue
        near = sorted((_pixel_gap(fragment, components[host]), host) for host in hosts if _box_gap(fragment, components[host]) <= gap)
        near = [candidate for candidate in near if candidate[0] <= gap]
        if near:
            attached.setdefault(near[0][1], []).append(fragment)
    joined = {id(fragment) for fragments in attached.values() for fragment in fragments}
    return [_joined([component, *attached[index]]) if attached.get(index) else component
            for index, component in enumerate(components) if id(component) not in joined]


def text_components(components: list[Component], height: float, page_height: int, grouping: Grouping) -> list[Component]:
    furniture = grouping.furniture_width * height
    rules = [component for component in components if component.width > furniture]
    top, bottom = _text_area(rules, page_height)
    text = [component for component in components
            if component.width <= furniture and top <= (component.bbox[1] + component.bbox[3]) / 2 <= bottom]
    hosts: dict[int, Component] = {}
    dropped: set[int] = set()
    for speck in (component for component in text if max(component.width, component.height) < grouping.speck_size * height):
        outer = next((other for other in text if _inside(speck, other)), None)
        if outer is not None:
            dropped.add(id(speck))
            if _in_hole(speck, outer):
                hosts[id(outer)] = _joined([hosts.get(id(outer), outer), speck])
    kept = [hosts.get(id(component), component) for component in text if id(component) not in dropped]
    return repaired(kept, height, grouping) if grouping.repair_gap > 0 else kept


def scan_page(page: pymupdf.Page, number: int, profile: ScanProfile) -> ScanPage:
    ink = render_ink(page)
    components = find_components(ink, MIN_AREA)
    if not components:
        return ScanPage(number, 0.0, [])
    height = unit_height(components, profile.grouping.grouping_unit)
    text = text_components(components, height, ink.shape[0], profile.grouping)
    return ScanPage(number, unit_height(components, profile.shape_unit), page_words(text, height, profile.grouping))
