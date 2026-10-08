import json
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import Any

from anu_unicode.scan.ink import Component, letter_height, median_height


class HeightUnit(StrEnum):
    MEDIAN = "median"
    LETTER = "letter"


@dataclass(frozen=True)
class Grouping:
    grouping_unit: HeightUnit = HeightUnit.MEDIAN
    furniture_width: float = 8.0
    speck_size: float = 0.3
    word_gap: float = 0.45
    stack_gap: float = 0.3
    bar_height: float = 0.35
    repair_size: float = 0.0
    repair_gap: float = 0.0
    loose_speck_size: float = 0.0


@dataclass(frozen=True)
class ScanProfile:
    grouping: Grouping = Grouping()
    shape_unit: HeightUnit = HeightUnit.MEDIAN


CHOICES = {"grouping_unit": HeightUnit, "shape_unit": HeightUnit}
GROUPING = {field.name for field in fields(Grouping)}


def load_scan_profile(path: Path) -> ScanProfile:
    if not path.exists():
        return ScanProfile()
    settings: dict[str, Any] = {name: CHOICES[name](value) if name in CHOICES else float(value)
                                for name, value in json.loads(path.read_text(encoding="utf-8")).items()}
    grouping = Grouping(**{name: value for name, value in settings.items() if name in GROUPING})
    return ScanProfile(grouping, **{name: value for name, value in settings.items() if name not in GROUPING})


def unit_height(components: list[Component], unit: HeightUnit) -> float:
    return letter_height(components) if unit == HeightUnit.LETTER else median_height(components)
