import argparse
import logging
from pathlib import Path

import pymupdf

from anu_unicode.command_support import page_range, requested_pages
from anu_unicode.scan.ambiguity import Verdict, check_index, write_ambiguity
from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, load_catalog
from anu_unicode.scan.index import ShapeIndex, write_index
from anu_unicode.scan.merge import merge_duplicates
from anu_unicode.scan.page import ScanPage, scan_page
from anu_unicode.scan.split import frequent_alphabet, split_page

logger = logging.getLogger(__name__)
SCAN = "[scanned books]"


def _catalog(arguments: argparse.Namespace) -> ShapeCatalog:
    if arguments.catalog.exists() and not arguments.rebuild:
        return load_catalog(arguments.catalog)
    return ShapeCatalog(Thresholds(arguments.max_stray, arguments.max_height_drift, arguments.max_aspect_drift))


def _index(pages: list[ScanPage], catalog: ShapeCatalog) -> ShapeIndex:
    index = ShapeIndex(catalog)
    for page in pages:
        index.add(page)
    return index


def _report_ambiguity(arguments: argparse.Namespace, index: ShapeIndex, pages: list[ScanPage]) -> None:
    report = check_index(index, pages)
    out = arguments.layout.intermediate("scan-ambiguity")
    write_ambiguity(out, report, index.catalog, "../scan-index/shapes")
    verdicts = report.verdicts()
    logger.info("ambiguity report written", extra={**{verdict.value: verdicts[verdict] for verdict in Verdict},
                                                   "confusable_pairs": len(set(report.shared()) | report.prototype_pairs),
                                                   "report": str(out / "ambiguity.html")})


def _scan_index(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    pages = [scan_page(document[number - 1], number) for number in requested_pages(arguments, document)]
    index = _index(pages, _catalog(arguments))
    for split_pass in range(1, arguments.split_passes + 1):
        alphabet = frequent_alphabet(index.catalog, index.catalog.counts.copy(), arguments.split_min_count)
        pages = [split_page(page, alphabet) for page in pages]
        index = _index(pages, _catalog(arguments))
        logger.info("split pass done", extra={"pass": split_pass, "shapes": len(index.catalog), "occurrences": len(index.occurrences)})
    if arguments.merge:
        merged = merge_duplicates(index)
        logger.info("duplicate ids merged", extra={"merged_per_round": merged, "live_shapes": int((index.catalog.counts > 0).sum())})
    out = arguments.layout.intermediate("scan-index")
    stats = write_index(out, index)
    if arguments.write_catalog:
        index.catalog.save(arguments.catalog)
    if arguments.ambiguity:
        _report_ambiguity(arguments, index, pages)
    logger.info("scan index written", extra={"shapes": stats.shapes, "singletons": stats.singletons,
                                             "shapes_for_99_percent": stats.shapes_for_coverage, "occurrences": stats.occurrences,
                                             "sheet": str(out / "shapes.html"), "catalog_written": arguments.write_catalog})


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    index = commands.add_parser("scan-index", help=f"{SCAN} give every ink component of a scanned page a shape id")
    index.add_argument("--pages", type=page_range, help="1-based, e.g. 4-13; default whole PDF")
    index.add_argument("--catalog", type=Path, help="shape catalog to extend; default fonts/<font>/scan/catalog.npz")
    index.add_argument("--rebuild", action="store_true", help="ignore an existing catalog and cluster from scratch")
    index.add_argument("--write-catalog", action="store_true", help="save the catalog so later runs keep these shape ids")
    index.add_argument("--max-stray", type=float, default=0.2, help="pre-filter: share of ink further than 1 grid pixel from the prototype")
    index.add_argument("--max-height-drift", type=float, default=0.2, help="abs log height difference, in body heights")
    index.add_argument("--max-aspect-drift", type=float, default=0.25, help="abs log aspect-ratio difference")
    index.add_argument("--split-passes", type=int, default=0, help="passes that cut touching glyphs at a thin neck; 0 disables")
    index.add_argument("--split-min-count", type=int, default=50, help="a cut part must match a shape seen at least this often")
    index.add_argument("--merge", action=argparse.BooleanOptionalAction, default=False,
                       help="second round: merge an id into a larger one when most of its members match that id's prototype")
    index.add_argument("--ambiguity", action="store_true",
                       help="re-check every occurrence against the final shapes; report ambiguous and drifted ones separately")
    index.set_defaults(handler=_scan_index)
