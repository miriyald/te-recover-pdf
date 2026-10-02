import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from itertools import groupby

from anu_unicode.convert import Coverage, convert_anu
from anu_unicode.glyphs import Rect
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.source import SHAPE_BASE, SHAPE_LIMIT, scan_words, shape_id_of

SHAPE_CHAR = re.compile(f"[{chr(SHAPE_BASE)}-{chr(SHAPE_LIMIT)}]")


@dataclass
class ScanText:
    lines: list[str] = field(default_factory=list)
    words: list[tuple[Rect, str]] = field(default_factory=list)


def readable(text: str) -> str:
    return SHAPE_CHAR.sub(lambda match: f"#{shape_id_of(match.group())}", text)


def unmapped_ids(coverage: Coverage) -> Counter[int]:
    counts: Counter[int] = Counter()
    for glyphs, count in coverage.unmapped.items():
        for char in glyphs:
            counts[shape_id_of(char)] += count
    return counts


def convert_scan_page(occurrences: Iterable[Occurrence], excluded: frozenset[int], mapping: Mapping[str, str], points_per_pixel: float,
                      coverage: Coverage) -> ScanText:
    kept = sorted((item for item in occurrences if item.shape_id not in excluded), key=lambda item: (item.line, item.word, item.position))
    page = ScanText()
    for _, line in groupby(kept, key=lambda item: item.line):
        texts = []
        for word in scan_words(line, points_per_pixel):
            text = convert_anu(word.text, mapping, coverage)
            texts.append(readable(text))
            page.words.append((word.bbox, text))
        page.lines.append(" ".join(texts))
    return page
