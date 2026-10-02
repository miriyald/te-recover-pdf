import argparse
import logging
from pathlib import Path

import pymupdf

from anu_unicode.command_support import page_range, requested_pages
from anu_unicode.scan.ambiguity import Verdict, check_index, write_ambiguity
from anu_unicode.scan.atlas import AtlasInput, Ocr, build_rows, tesseract_reading, write_scan_atlas
from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, load_catalog
from anu_unicode.scan.index import ShapeIndex, write_index
from anu_unicode.scan.page import ScanPage, scan_page
from anu_unicode.scan.source import read_excluded, read_occurrences
from anu_unicode.shape_naming.shapes import load_shapes

logger = logging.getLogger(__name__)
SCAN = "[scanned books]"


def _catalog(arguments: argparse.Namespace) -> ShapeCatalog:
    if arguments.catalog.exists() and not arguments.rebuild:
        return load_catalog(arguments.catalog)
    return ShapeCatalog(Thresholds(arguments.max_stray, arguments.max_height_drift, arguments.max_aspect_drift))


def _report_ambiguity(arguments: argparse.Namespace, index: ShapeIndex, pages: list[ScanPage]) -> None:
    report = check_index(index, pages, read_excluded(arguments.excluded))
    out = arguments.layout.intermediate("scan-ambiguity")
    write_ambiguity(out, report, index.catalog, "../scan-index/shapes")
    verdicts = report.verdicts()
    logger.info("ambiguity report written", extra={**{verdict.value: verdicts[verdict] for verdict in Verdict},
                                                   "confusable_pairs": len(set(report.shared()) | report.prototype_pairs),
                                                   "report": str(out / "ambiguity.html")})


def _scan_index(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    pages = [scan_page(document[number - 1], number) for number in requested_pages(arguments, document)]
    index = ShapeIndex(_catalog(arguments))
    for page in pages:
        index.add(page)
    out = arguments.layout.intermediate("scan-index")
    stats = write_index(out, index, read_excluded(arguments.excluded))
    if arguments.write_catalog:
        index.catalog.save(arguments.catalog)
    if arguments.ambiguity:
        _report_ambiguity(arguments, index, pages)
    logger.info("scan index written", extra={"shapes": stats.shapes, "singletons": stats.singletons,
                                             "shapes_for_99_percent": stats.shapes_for_coverage, "occurrences": stats.occurrences,
                                             "sheet": str(out / "shapes.html"), "catalog_written": arguments.write_catalog})


def _scan_atlas(arguments: argparse.Namespace) -> None:
    layout = arguments.layout
    occurrences = read_occurrences(layout.intermediate("scan-index") / "occurrences.tsv")
    out = layout.intermediate("scan-atlas")
    source = AtlasInput(pymupdf.open(arguments.pdf), occurrences, load_catalog(arguments.catalog), read_excluded(arguments.excluded))
    ocr = Ocr(lambda mask: tesseract_reading(mask, arguments.tesseract), layout.state / "scan-ocr.tsv")
    rows = build_rows(source, arguments.min_count, out, ocr)
    write_scan_atlas(out / "atlas.html", rows, {shape.glyph: shape for shape in load_shapes(arguments.names)}, "../scan-index/shapes")
    logger.info("scan atlas written", extra={"shapes": len(rows), "occurrences": sum(row.count for row in rows),
                                             "with_proposal": sum(bool(row.proposal) for row in rows), "path": str(out / "atlas.html")})


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    index = commands.add_parser("scan-index", help=f"{SCAN} give every ink component of a scanned page a shape id")
    index.add_argument("--pages", type=page_range, help="1-based, e.g. 4-13; default whole PDF")
    index.add_argument("--catalog", type=Path, help="shape catalog to extend; default files/<book>/state/scan-catalog.npz")
    index.add_argument("--rebuild", action="store_true", help="ignore an existing catalog and cluster from scratch")
    index.add_argument("--write-catalog", action="store_true", help="save the catalog so later runs keep these shape ids")
    index.add_argument("--max-stray", type=float, default=0.2, help="pre-filter: share of ink further than 1 grid pixel from the prototype")
    index.add_argument("--max-height-drift", type=float, default=0.2, help="abs log height difference, in body heights")
    index.add_argument("--max-aspect-drift", type=float, default=0.25, help="abs log aspect-ratio difference")
    index.add_argument("--excluded", type=Path, help="shape ids left out of every list; default fonts/<font>/scan/excluded.tsv")
    index.add_argument("--ambiguity", action="store_true",
                       help="re-check every occurrence against the final shapes; report ambiguous and drifted ones separately")
    index.set_defaults(handler=_scan_index)
    atlas = commands.add_parser("scan-atlas", help=f"{SCAN} labelling sheet: one row per shape id with crops and a Tesseract proposal")
    atlas.add_argument("--min-count", type=int, default=3, help="list ids seen at least this often")
    atlas.add_argument("--excluded", type=Path, help="shape ids left out of every list; default fonts/<font>/scan/excluded.tsv")
    atlas.add_argument("--names", type=Path, help="names to pre-fill; default fonts/<font>/shape-naming/names.tsv")
    atlas.set_defaults(handler=_scan_atlas)
