from dataclasses import dataclass

import numpy as np
import pymupdf
from scipy import ndimage

from anu_unicode.scan.ink import Component, find_components, render_ink
from anu_unicode.scan.profile import ScanProfile, unit_height
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


def _with_dot(outer: Component, dot: Component) -> Component:
    mask = outer.mask.copy()
    top, left = dot.bbox[1] - outer.bbox[1], dot.bbox[0] - outer.bbox[0]
    mask[top:top + dot.height, left:left + dot.width] |= dot.mask
    return Component(outer.bbox, mask)


def _joined_mask(first: Component, second: Component) -> Component:
    left, top = min(first.bbox[0], second.bbox[0]), min(first.bbox[1], second.bbox[1])
    right, bottom = max(first.bbox[2], second.bbox[2]), max(first.bbox[3], second.bbox[3])
    mask = np.zeros((bottom - top, right - left), dtype=bool)
    for part in (first, second):
        mask[part.bbox[1] - top:part.bbox[3] - top, part.bbox[0] - left:part.bbox[2] - left] |= part.mask
    return Component((left, top, right, bottom), mask)


def _pixel_gap(fragment: Component, host: Component) -> float:
    joined = _joined_mask(host, Component(fragment.bbox, np.zeros_like(fragment.mask)))
    distance = ndimage.distance_transform_edt(~joined.mask)
    top, left = fragment.bbox[1] - joined.bbox[1], fragment.bbox[0] - joined.bbox[0]
    return float(distance[top:top + fragment.height, left:left + fragment.width][fragment.mask].min())


def _box_gap(first: Component, second: Component) -> int:
    horizontal = max(second.bbox[0] - first.bbox[2], first.bbox[0] - second.bbox[2])
    return max(horizontal, second.bbox[1] - first.bbox[3], first.bbox[1] - second.bbox[3])


def repaired(components: list[Component], height: float, profile: ScanProfile) -> list[Component]:
    size, gap = profile.repair_size * height, profile.repair_gap * height
    fragments = [component for component in components if max(component.width, component.height) < size]
    hosts = {id(component): component for component in components if max(component.width, component.height) >= size}
    joined: set[int] = set()
    for fragment in fragments:
        near = [(_pixel_gap(fragment, host), key) for key, host in hosts.items() if _box_gap(fragment, host) <= gap]
        distance, key = min(near, default=(gap + 1, 0))
        if distance <= gap:
            hosts[key] = _joined_mask(hosts[key], fragment)
            joined.add(id(fragment))
    return [hosts.get(id(component), component) for component in components if id(component) not in joined]


def text_components(components: list[Component], height: float, page_height: int, profile: ScanProfile) -> list[Component]:
    furniture = profile.furniture_width * height
    rules = [component for component in components if component.width > furniture]
    top, bottom = _text_area(rules, page_height)
    text = [component for component in components
            if component.width <= furniture and top <= (component.bbox[1] + component.bbox[3]) / 2 <= bottom]
    hosts: dict[int, Component] = {}
    dropped: set[int] = set()
    for speck in (component for component in text if max(component.width, component.height) < profile.speck_size * height):
        outer = next((other for other in text if _inside(speck, other)), None)
        if outer is not None:
            dropped.add(id(speck))
            if _in_hole(speck, outer):
                hosts[id(outer)] = _with_dot(hosts.get(id(outer), outer), speck)
    kept = [hosts.get(id(component), component) for component in text if id(component) not in dropped]
    return repaired(kept, height, profile) if profile.repair_gap > 0 else kept


def scan_page(page: pymupdf.Page, number: int, profile: ScanProfile) -> ScanPage:
    ink = render_ink(page)
    components = find_components(ink, MIN_AREA)
    if not components:
        return ScanPage(number, 0.0, [])
    height = unit_height(components, profile.grouping_unit)
    text = text_components(components, height, ink.shape[0], profile)
    return ScanPage(number, unit_height(components, profile.shape_unit), page_words(text, height, profile))
