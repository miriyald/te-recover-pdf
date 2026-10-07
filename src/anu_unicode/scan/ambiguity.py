import html
import shutil
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np

from anu_unicode.scan.catalog import MAX_THICK_BLOB, Shape, ShapeCatalog, shape_of, thick_blob
from anu_unicode.scan.index import EQUALS, Occurrence, ShapeIndex, member_strip, write_tsv
from anu_unicode.scan.ink import Bitmap
from anu_unicode.scan.page import ScanPage

WIDE_STRAY = 0.35
CANDIDATES = 16
PAIR_CROPS = 12

Match = tuple[int, int]
Pair = tuple[int, int]


class Verdict(StrEnum):
    CLEAN = "clean"
    AMBIGUOUS = "ambiguous"
    DRIFTED = "drifted"


@dataclass(frozen=True)
class Check:
    occurrence: Occurrence
    matches: tuple[Match, ...]

    @property
    def matched_ids(self) -> list[int]:
        return [shape_id for shape_id, _ in self.matches]

    @property
    def verdict(self) -> Verdict:
        if self.occurrence.shape_id not in self.matched_ids:
            return Verdict.DRIFTED
        return Verdict.AMBIGUOUS if len(self.matches) > 1 else Verdict.CLEAN

    @property
    def rivals(self) -> list[int]:
        return [shape_id for shape_id in self.matched_ids if shape_id != self.occurrence.shape_id]


@dataclass
class AmbiguityReport:
    checks: list[Check] = field(default_factory=list)
    pair_crops: dict[Pair, list[Bitmap]] = field(default_factory=dict)
    prototype_pairs: set[Pair] = field(default_factory=set)

    def verdicts(self) -> Counter[Verdict]:
        return Counter(check.verdict for check in self.checks)

    def shared(self) -> Counter[Pair]:
        return Counter(_pair(check.occurrence.shape_id, rival) for check in self.checks for rival in check.rivals)

    def pairs(self) -> list[Pair]:
        shared = self.shared()
        return sorted(set(shared) | self.prototype_pairs, key=lambda pair: (-shared[pair], pair))

    def by_id(self) -> dict[int, Counter[Verdict]]:
        verdicts: dict[int, Counter[Verdict]] = {}
        for check in self.checks:
            verdicts.setdefault(check.occurrence.shape_id, Counter())[check.verdict] += 1
        return verdicts

    def flagged(self) -> list[int]:
        by_id = self.by_id()
        troubled = {shape_id: verdicts[Verdict.AMBIGUOUS] + verdicts[Verdict.DRIFTED] for shape_id, verdicts in by_id.items()}
        return sorted((shape_id for shape_id, count in troubled.items() if count), key=lambda shape_id: (-troubled[shape_id], shape_id))


def _pair(first: int, second: int) -> Pair:
    return (first, second) if first < second else (second, first)


def matching_ids(catalog: ShapeCatalog, shape: Shape) -> tuple[Match, ...]:
    distances = catalog.distances(shape)
    candidates = [index for index in np.argsort(distances, kind="stable")[:CANDIDATES] if distances[index] <= WIDE_STRAY]
    blobs = [(int(index), thick_blob(shape.canvas, catalog.canvases.bitmaps[index])) for index in candidates]
    return tuple(sorted(((index, blob) for index, blob in blobs if blob <= MAX_THICK_BLOB), key=lambda match: (match[1], match[0])))


def _placed_glyphs(pages: list[ScanPage]) -> Iterator[tuple[ScanPage, Bitmap, Shape]]:
    for page in pages:
        for line in page.lines:
            for word in line:
                for placed in word.glyphs:
                    yield page, placed.component.mask, shape_of(placed.component, placed.band, page.body_height)


def check_index(index: ShapeIndex, pages: list[ScanPage]) -> AmbiguityReport:
    report = AmbiguityReport()
    for occurrence, (_, mask, shape) in zip(index.occurrences, _placed_glyphs(pages), strict=True):
        if occurrence.shape_id == EQUALS:
            continue
        check = Check(occurrence, matching_ids(index.catalog, shape))
        report.checks.append(check)
        for rival in check.rivals:
            crops = report.pair_crops.setdefault(_pair(occurrence.shape_id, rival), [])
            if len(crops) < PAIR_CROPS:
                crops.append(mask)
    catalog = index.catalog
    for shape_id in (int(shape_id) for shape_id in np.flatnonzero(catalog.counts)):
        for other, _ in matching_ids(catalog, catalog.prototype_shape(shape_id)):
            if other != shape_id and catalog.counts[other]:
                report.prototype_pairs.add(_pair(shape_id, other))
    return report


def _share(count: int, total: int) -> str:
    return f"{count / total * 100:.2f} %" if total else "0 %"


def write_ambiguity(out: Path, report: AmbiguityReport, catalog: ShapeCatalog, shapes_folder: str) -> None:
    shutil.rmtree(out, ignore_errors=True)
    (out / "pairs").mkdir(parents=True)
    write_tsv(out / "ambiguous.tsv", "page\tline\tword\tposition\tshape_id\tverdict\tmatches\tleft\ttop\tright\tbottom", (
        f"{check.occurrence.page}\t{check.occurrence.line}\t{check.occurrence.word}\t{check.occurrence.position}\t"
        f"{check.occurrence.shape_id}\t{check.verdict}\t{','.join(f'{shape_id}:{blob}' for shape_id, blob in check.matches)}\t"
        + "\t".join(map(str, check.occurrence.bbox)) for check in report.checks if check.verdict is not Verdict.CLEAN))
    shared = report.shared()
    write_tsv(out / "confusable.tsv", "shape_a\tshape_b\tcount_a\tcount_b\tshared_occurrences\tprototypes_match", (
        f"{first}\t{second}\t{int(catalog.counts[first])}\t{int(catalog.counts[second])}\t{shared[(first, second)]}\t"
        f"{(first, second) in report.prototype_pairs}" for first, second in report.pairs()))
    for pair, crops in report.pair_crops.items():
        member_strip(catalog.prototype(pair[0]), crops).save(out / "pairs" / f"{pair[0]}-{pair[1]}.png")
    by_id = report.by_id()
    write_tsv(out / "shapes.tsv", "shape_id\tcount\tambiguous\tdrifted", (
        f"{shape_id}\t{int(catalog.counts[shape_id])}\t{by_id[shape_id][Verdict.AMBIGUOUS]}\t{by_id[shape_id][Verdict.DRIFTED]}"
        for shape_id in report.flagged()))
    _write_html(out / "ambiguity.html", report, catalog, shapes_folder)


def _image(path: str) -> str:
    return f'<img src="{html.escape(path)}">'


def _write_html(path: Path, report: AmbiguityReport, catalog: ShapeCatalog, shapes_folder: str) -> None:
    verdicts, total, shared = report.verdicts(), len(report.checks), report.shared()
    pairs, flagged, by_id = report.pairs(), report.flagged(), report.by_id()
    summary = "".join(f"<tr><td>{verdict}</td><td>{verdicts[verdict]}</td><td>{_share(verdicts[verdict], total)}</td></tr>"
                      for verdict in Verdict)
    pair_rows = "".join(
        f"<tr><td>#{first} ({int(catalog.counts[first])})</td><td>#{second} ({int(catalog.counts[second])})</td>"
        f"<td>{shared[(first, second)]}</td>"
        f"<td>{'yes' if (first, second) in report.prototype_pairs else ''}</td>"
        f"<td>{_image(f'{shapes_folder}/{first}.png')}<br>{_image(f'{shapes_folder}/{second}.png')}</td>"
        f"<td>{_image(f'pairs/{first}-{second}.png') if (first, second) in report.pair_crops else ''}</td></tr>"
        for first, second in pairs)
    id_rows = "".join(
        f"<tr><td>#{shape_id}</td><td>{int(catalog.counts[shape_id])}</td><td>{by_id[shape_id][Verdict.AMBIGUOUS]}</td>"
        f"<td>{by_id[shape_id][Verdict.DRIFTED]}</td><td>{_image(f'{shapes_folder}/{shape_id}.png')}</td></tr>" for shape_id in flagged)
    path.write_text(
        "<!doctype html><meta charset=\"utf-8\"><title>Scan ambiguity</title><style>body{font:14px sans-serif;margin:16px}"
        "td,th{padding:2px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}img{height:40px}</style>"
        "<h1>Shape ambiguity</h1><p>Every occurrence re-checked against the final shape list. <b>ambiguous</b>: it also passes the "
        "thick test for another id. <b>drifted</b>: it no longer passes against its own id.</p>"
        f"<h2>Volume</h2><table><tr><th>verdict</th><th>occurrences</th><th>share</th></tr>{summary}</table>"
        f"<h2>Confusable pairs ({len(pairs)})</h2><table><tr><th>id a</th><th>id b</th><th>shared occurrences</th>"
        f"<th>prototypes match</th><th>prototypes</th><th>ambiguous members (prototype of a, then members)</th></tr>{pair_rows}</table>"
        f"<h2>Ids with ambiguous or drifted members ({len(flagged)})</h2><table><tr><th>id</th><th>count</th><th>ambiguous</th>"
        f"<th>drifted</th><th>members</th></tr>{id_rows}</table>\n", encoding="utf-8", newline="\n")
