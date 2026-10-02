import argparse
import logging
import shutil
from collections import defaultdict
from pathlib import Path

import pymupdf

from anu_unicode.command_support import MATCH_OVERLAP, page_range, requested_pages
from anu_unicode.convert import Coverage
from anu_unicode.mapping import write_rows
from anu_unicode.quality import compare_words, page_quality
from anu_unicode.quality_report import QualityReport, write_quality_report
from anu_unicode.scan.ambiguity import Verdict, check_index, write_ambiguity
from anu_unicode.scan.atlas import AtlasInput, Ocr, build_rows, tesseract_reading, write_scan_atlas
from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, load_catalog
from anu_unicode.scan.conversion import convert_scan_page, unmapped_ids
from anu_unicode.scan.index import Occurrence, ShapeIndex, write_index
from anu_unicode.scan.ink import pixels_per_point
from anu_unicode.scan.page import ScanPage, scan_page
from anu_unicode.scan.source import read_excluded, read_occurrences
from anu_unicode.shape_naming.shapes import compile_mapping, load_recipes, load_shapes

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


def _occurrences_by_page(arguments: argparse.Namespace) -> dict[int, list[Occurrence]]:
    by_page: dict[int, list[Occurrence]] = defaultdict(list)
    for item in read_occurrences(arguments.layout.intermediate("scan-index") / "occurrences.tsv"):
        by_page[item.page].append(item)
    return by_page


def _mapping(arguments: argparse.Namespace) -> dict[str, str]:
    entries = compile_mapping(load_shapes(arguments.names), load_recipes(arguments.recipes))
    return {glyphs: entry.unicode for glyphs, entry in entries.items()}


def _scan_convert(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    by_page, mapping, excluded = _occurrences_by_page(arguments), _mapping(arguments), read_excluded(arguments.excluded)
    out = arguments.layout.intermediate("scan-convert")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    coverage, texts, pages = Coverage(), [], []
    for number in arguments.pages or sorted(by_page):
        page = document[number - 1]
        converted = convert_scan_page(by_page[number], excluded, mapping, 1 / pixels_per_point(page), coverage)
        text = "\n".join(converted.lines)
        (out / f"page-{number}.unicode.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
        texts.append(text)
        if arguments.quality:
            pages.append(page_quality(number, compare_words(converted.words, arguments.ocr(page), MATCH_OVERLAP)))
    (out / "book.txt").write_text("\n\f".join(texts) + "\n", encoding="utf-8", newline="\n")
    write_rows(out / "unmapped.tsv", ("shape_id", "count"), unmapped_ids(coverage).most_common())
    if arguments.quality:
        write_quality_report(out / "quality", QualityReport(arguments.pdf.name, document.page_count, pages, []))
    logger.info("scan conversion done", extra={"pages": len(texts), "coverage": round(coverage.ratio, 4), "mapped_entries": len(mapping),
                                               "out": str(out), "ocr_calls": arguments.ocr.calls})


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
    convert = commands.add_parser("scan-convert", help=f"{SCAN} convert scanned pages with the shape names and recipes")
    convert.add_argument("--pages", type=page_range, help="1-based, e.g. 100-105; default every indexed page")
    convert.add_argument("--names", type=Path, help="default fonts/<font>/shape-naming/names.tsv")
    convert.add_argument("--recipes", type=Path, help="default fonts/<font>/shape-naming/recipes.tsv")
    convert.add_argument("--excluded", type=Path, help="shape ids that contribute nothing; default fonts/<font>/scan/excluded.tsv")
    convert.add_argument("--quality", action="store_true", help="compare every word with Tesseract (cached per page) and write a report")
    convert.set_defaults(handler=_scan_convert)
