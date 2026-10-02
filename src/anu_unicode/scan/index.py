import html
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from anu_unicode.scan.catalog import GRID, ShapeCatalog, shape_of
from anu_unicode.scan.ink import Bitmap, Box
from anu_unicode.scan.page import ScanPage
from anu_unicode.scan.words import Band

MEMBER_CROPS = 16
SAMPLE_SEED = 0
STRIP_HEIGHT = 64
COVERAGE = 0.99


@dataclass(frozen=True)
class Occurrence:
    page: int
    line: int
    word: int
    position: int
    shape_id: int
    band: Band
    bbox: Box


@dataclass
class ShapeIndex:
    catalog: ShapeCatalog
    occurrences: list[Occurrence] = field(default_factory=list)
    members: dict[int, list[Bitmap]] = field(default_factory=dict)
    pages: dict[int, set[int]] = field(default_factory=dict)
    new_per_page: dict[int, int] = field(default_factory=dict)
    random: np.random.Generator = field(default_factory=lambda: np.random.default_rng(SAMPLE_SEED))

    def add(self, page: ScanPage) -> None:
        before = len(self.catalog)
        for line_number, line in enumerate(page.lines, start=1):
            for word_number, word in enumerate(line, start=1):
                for position, placed in enumerate(word.glyphs, start=1):
                    shape_id = self.catalog.assign(shape_of(placed.component, placed.band, page.body_height))
                    self.occurrences.append(Occurrence(page.number, line_number, word_number, position, shape_id, placed.band,
                                                       placed.component.bbox))
                    self.pages.setdefault(shape_id, set()).add(page.number)
                    self._sample(shape_id, placed.component.mask)
        self.new_per_page[page.number] = len(self.catalog) - before

    def _sample(self, shape_id: int, mask: Bitmap) -> None:
        crops = self.members.setdefault(shape_id, [])
        if len(crops) < MEMBER_CROPS:
            crops.append(mask)
            return
        slot = int(self.random.integers(self.catalog.counts[shape_id]))
        if slot < MEMBER_CROPS:
            crops[slot] = mask

    def by_frequency(self) -> list[int]:
        return sorted(range(len(self.catalog)), key=lambda shape_id: (-self.catalog.counts[shape_id], shape_id))


@dataclass(frozen=True)
class AlphabetStats:
    shapes: int
    singletons: int
    shapes_for_coverage: int
    occurrences: int


def alphabet_stats(counts: Iterable[float]) -> AlphabetStats:
    ordered = np.sort(np.fromiter((count for count in counts if count > 0), dtype=np.float64))[::-1]
    covered = np.cumsum(ordered) / ordered.sum()
    return AlphabetStats(len(ordered), int((ordered == 1).sum()), int(np.searchsorted(covered, COVERAGE) + 1), int(ordered.sum()))


def member_strip(prototype: Bitmap, members: list[Bitmap]) -> Image.Image:
    tiles = [Image.fromarray(np.where(prototype, 0, 255).astype(np.uint8)).resize((GRID, GRID))]
    for mask in members:
        tile = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))
        tiles.append(tile.resize((max(1, round(tile.width * STRIP_HEIGHT / tile.height)), STRIP_HEIGHT)))
    strip = Image.new("L", (sum(tile.width + 6 for tile in tiles), STRIP_HEIGHT), 255)
    left = 0
    for tile in tiles:
        strip.paste(tile, (left, (STRIP_HEIGHT - tile.height) // 2))
        left += tile.width + 6
    return strip


def write_tsv(path: Path, header: str, rows: Iterable[str]) -> None:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8", newline="\n")


def write_index(out: Path, index: ShapeIndex) -> AlphabetStats:
    shutil.rmtree(out, ignore_errors=True)
    (out / "shapes").mkdir(parents=True)
    catalog = index.catalog
    write_tsv(out / "occurrences.tsv", "page\tline\tword\tposition\tshape_id\tband\tleft\ttop\tright\tbottom", (
        f"{item.page}\t{item.line}\t{item.word}\t{item.position}\t{item.shape_id}\t{item.band}\t" + "\t".join(map(str, item.bbox))
        for item in index.occurrences))
    ranked = [shape_id for shape_id in index.by_frequency() if catalog.counts[shape_id]]
    write_tsv(out / "shapes.tsv", "shape_id\tcount\tband\tholes\theight\taspect\tpages", (
        f"{shape_id}\t{int(catalog.counts[shape_id])}\t{tuple(Band)[catalog.bands[shape_id]]}\t{catalog.holes[shape_id]}\t"
        f"{catalog.heights[shape_id]:.2f}\t{catalog.aspects[shape_id]:.2f}\t{len(index.pages[shape_id])}" for shape_id in ranked))
    for shape_id in ranked:
        member_strip(catalog.prototype(shape_id), index.members[shape_id]).save(out / "shapes" / f"{shape_id}.png")
    rows = "".join(
        f"<tr><td>#{shape_id}</td><td>{int(catalog.counts[shape_id])}</td><td>{html.escape(str(tuple(Band)[catalog.bands[shape_id]]))}</td>"
        f"<td>{catalog.holes[shape_id]}</td><td><img src=\"shapes/{shape_id}.png\"></td></tr>" for shape_id in ranked)
    (out / "shapes.html").write_text(
        "<!doctype html><meta charset=\"utf-8\"><title>Scan shapes</title><style>body{font:14px sans-serif}td{padding:2px 8px;"
        "border-bottom:1px solid #ddd}img{height:40px}</style><table><tr><th>id</th><th>count</th><th>band</th><th>holes</th>"
        f"<th>prototype · members</th></tr>{rows}</table>\n", encoding="utf-8", newline="\n")
    stats = alphabet_stats(catalog.counts)
    write_tsv(out / "growth.tsv", "page\tnew_shapes", (f"{page}\t{count}" for page, count in index.new_per_page.items()))
    return stats
