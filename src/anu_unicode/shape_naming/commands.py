import argparse
import logging
from collections import Counter
from pathlib import Path

import pymupdf

from anu_unicode.command_support import MATCH_OVERLAP, cached_pages, page_range, requested_pages
from anu_unicode.mapping import load_mapping, save_entries
from anu_unicode.shape_naming.atlas import collect_glyphs, load_fonts, write_atlas
from anu_unicode.shape_naming.compare import compare, page_words, write_comparison
from anu_unicode.shape_naming.shapes import ShapeError, compile_mapping, load_recipes, load_shapes

logger = logging.getLogger(__name__)
APPROACH = "[approach 2: shape naming]"


def _atlas(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    arguments.out.mkdir(parents=True, exist_ok=True)
    shapes = {shape.glyph: shape for shape in load_shapes(arguments.names)}
    write_atlas(arguments.out / "atlas.html", collect_glyphs(document, arguments.profile), shapes, load_fonts(document, arguments.profile))


def _shapes(arguments: argparse.Namespace) -> None:
    shapes = load_shapes(arguments.names)
    recipes = load_recipes(arguments.recipes)
    try:
        entries = compile_mapping(shapes, recipes)
    except ShapeError as error:
        logger.error("shapes do not compile", extra={"error": str(error)})
        raise SystemExit(1) from error
    save_entries(arguments.write, entries)
    logger.info("shapes compiled", extra={"names": len(shapes), "recipes": len(recipes), "entries": len(entries),
                                          "path": str(arguments.write)})


def _compare(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    cached = cached_pages(arguments.ocr_cache)
    words = []
    for number in requested_pages(arguments, document):
        page = document[number - 1]
        ocr = arguments.ocr(page) if arguments.ocr_missing or number in cached else None
        words.extend(page_words(page, arguments.profile, ocr, MATCH_OVERLAP))
    comparison = compare(words, load_mapping(arguments.candidate), load_mapping(arguments.mapping))
    out = arguments.out / "shapes-validation"
    write_comparison(out, comparison, document)
    verdicts = Counter(item.verdict for item in comparison.differences)
    logger.info("comparison written", extra={"words": comparison.words, "groups": len(comparison.differences), "verdicts": dict(verdicts),
                                             "candidate_coverage": round(comparison.candidate_coverage.ratio, 4),
                                             "report": str(out / "report.html"), "ocr_calls": arguments.ocr.calls})


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    atlas = commands.add_parser("atlas", help=f"{APPROACH} labelling sheet: every glyph code drawn from the embedded font")
    atlas.add_argument("--names", type=Path, help="shape names to pre-fill; default fonts/<font>/shape-naming/names.tsv")
    atlas.set_defaults(handler=_atlas)
    shapes = commands.add_parser("shapes", help=f"{APPROACH} compile shape names and recipes into a mapping file")
    shapes.add_argument("--names", type=Path, help="default fonts/<font>/shape-naming/names.tsv")
    shapes.add_argument("--recipes", type=Path, help="default fonts/<font>/shape-naming/recipes.tsv")
    shapes.add_argument("--write", type=Path, help="default fonts/<font>/shape-naming/mapping.tsv")
    shapes.set_defaults(handler=_shapes)
    compare_command = commands.add_parser("compare", help=f"{APPROACH} diff a candidate mapping against --mapping word by word")
    compare_command.add_argument("--candidate", type=Path, help="default fonts/<font>/shape-naming/mapping.tsv")
    compare_command.add_argument("--pages", type=page_range, help="1-based, e.g. 1-449; default whole PDF")
    compare_command.add_argument("--ocr-missing", action="store_true", help="run Tesseract on pages that have no cached OCR (slow)")
    compare_command.set_defaults(handler=_compare)
