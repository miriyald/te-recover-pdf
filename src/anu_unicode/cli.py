import argparse
import logging
import os
import re
import shutil
from pathlib import Path

import pymupdf

from anu_unicode.command_support import MATCH_OVERLAP, cached_pages, page_range, requested_pages
from anu_unicode.convert import Coverage, convert_anu, convert_page
from anu_unicode.glyphs import page_lines, split_words, type3_families
from anu_unicode.layout import METHODS, OCR_LEARNING, SHAPE_NAMING, BookLayout, LayoutError, books
from anu_unicode.mapping import load_mapping
from anu_unicode.ocr import OcrCache
from anu_unicode.ocr_learning import commands as ocr_learning
from anu_unicode.probe import SAMPLE_PAGES, probe_document
from anu_unicode.profile import DEFAULT_PROFILE, load_profile, save_profile
from anu_unicode.quality import GroundTruthQuality, PageQuality, compare_words, ground_truth_quality, page_quality
from anu_unicode.quality_report import QualityReport, write_quality_report
from anu_unicode.run_output import Manifest, RunResult, archive_previous, now_stamp, sha256, write_manifest
from anu_unicode.scan import commands as scan
from anu_unicode.shape_naming import commands as shape_naming
from anu_unicode.shape_naming.shapes import compile_mapping, load_recipes, load_shapes

logger = logging.getLogger(__name__)
FONTS = Path("fonts")
BOOK_FREE_COMMANDS = frozenset({"shapes"})
STANDARD_RECORD_FIELDS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
DESCRIPTION = (
    "Convert Anu-font Telugu PDFs to Unicode. Approach 1 (OCR learning) grows a stack mapping from word OCR; "
    "approach 2 (shape naming) names each glyph code by its shape and compiles recipes. Both share convert, quality and probe."
)


class ExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extra = {key: value for key, value in vars(record).items() if key not in STANDARD_RECORD_FIELDS}
        return f"{super().format(record)} {extra}" if extra else super().format(record)


def book_slug(pdf: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", pdf.stem.lower()).strip("-")


def resolve_paths(arguments: argparse.Namespace) -> None:
    font = FONTS / arguments.font
    shape_naming_dir = font / SHAPE_NAMING
    arguments.mapping_given = getattr(arguments, "mapping", None) is not None
    defaults = {
        "profile": font / "profile.json", "mapping": font / OCR_LEARNING / "mapping.tsv",
        "excluded": font / "scan" / "excluded.tsv",
        "names": shape_naming_dir / "names.tsv", "recipes": shape_naming_dir / "recipes.tsv", "candidate": shape_naming_dir / "mapping.tsv",
    }
    if arguments.book:
        arguments.layout = BookLayout(arguments.book)
        state = arguments.layout.state
        book_profile = font / "books" / f"{arguments.book}.json"
        if book_profile.exists():
            defaults["profile"] = book_profile
        defaults |= {"pending": state / "pending.tsv", "progress": state / "progress.tsv", "suspicious": state / "suspicious.tsv",
                     "ocr_cache": state / "ocr-cache", "verified": state / "verified", "catalog": state / "scan-catalog.npz"}
    if arguments.command == "shapes":
        defaults["write"] = shape_naming_dir / "mapping.tsv"
    for name, path in defaults.items():
        if getattr(arguments, name, None) is None:
            setattr(arguments, name, path)


def method_mapping(arguments: argparse.Namespace) -> tuple[dict[str, str], dict[str, Path]]:
    if arguments.mapping_given or arguments.method == OCR_LEARNING:
        return load_mapping(arguments.mapping), {"mapping": arguments.mapping}
    entries = compile_mapping(load_shapes(arguments.names), load_recipes(arguments.recipes))
    return {glyphs: entry.unicode for glyphs, entry in entries.items()}, {"names": arguments.names, "recipes": arguments.recipes}


def _convert(arguments: argparse.Namespace) -> None:
    layout: BookLayout = arguments.layout
    document = pymupdf.open(arguments.pdf)
    mapping, sources = method_mapping(arguments)
    final = not arguments.mapping_given and arguments.pages is None
    pdf_sha256 = sha256(arguments.pdf)
    out = layout.output(arguments.method) if final else layout.intermediate("convert", arguments.method)
    if final:
        archive_previous(out, lambda stamp: layout.archived_output(arguments.method, stamp), pdf_sha256)
    else:
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    total = Coverage()
    texts = []
    skipped = []
    for number in requested_pages(arguments, document):
        coverage = Coverage()
        text = convert_page(document[number - 1], mapping, coverage, arguments.profile)
        (out / f"page-{number}.unicode.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
        texts.append(text)
        if type3_families(document[number - 1]):
            skipped.append(number)
        total.glyphs += coverage.glyphs
        total.unmapped.update(coverage.unmapped)
        logger.info("page converted", extra={"page": number, "coverage": round(coverage.ratio, 4)})
    (out / "book.txt").write_text("\n\f".join(texts) + "\n", encoding="utf-8", newline="\n")
    report = ["unmapped\tcount"] + [f"{glyphs}\t{count}" for glyphs, count in total.unmapped.most_common()]
    (out / "unmapped.tsv").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    write_manifest(out, Manifest(
        book=layout.slug, source=arguments.pdf.name, pdf_sha256=pdf_sha256, method=arguments.method,
        mapping_sources={path.as_posix(): sha256(path) for path in sources.values()},
        result=RunResult(len(texts), round(total.ratio, 6), len(total.unmapped), tuple(skipped)), created=now_stamp(),
    ))
    if skipped:
        logger.warning("Type3-font text cannot be decoded and was skipped", extra={"pages": skipped})
    logger.info("conversion done", extra={"coverage": round(total.ratio, 4), "unmapped_sequences": len(total.unmapped),
                                          "final": final, "out": str(out)})


def _measure_page(document: pymupdf.Document, number: int, mapping: dict[str, str], arguments: argparse.Namespace) -> PageQuality:
    page = document[number - 1]
    converted = [
        (word.bbox, convert_anu(word.text, mapping, Coverage()))
        for line in page_lines(page, arguments.profile) for word in split_words(line)
    ]
    return page_quality(number, compare_words(converted, arguments.ocr(page), MATCH_OVERLAP))


def _measure_ground_truth(document: pymupdf.Document, path: Path, mapping: dict[str, str],
                          arguments: argparse.Namespace) -> GroundTruthQuality:
    number = int(path.name.split("-")[1].split(".")[0])
    page = document[number - 1]
    ocr_text = " ".join(word.text for word in arguments.ocr(page))
    reference = path.read_text(encoding="utf-8")
    return ground_truth_quality(number, reference, convert_page(page, mapping, Coverage(), arguments.profile), ocr_text)


def _quality(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    mapping, _ = method_mapping(arguments)
    cached = cached_pages(arguments.ocr_cache)
    numbers = [number for number in requested_pages(arguments, document) if arguments.ocr_missing or number in cached]
    pages = [_measure_page(document, number, mapping, arguments) for number in numbers]
    verified = sorted(arguments.verified.glob("page-*.unicode.txt"))
    ground_truth = [_measure_ground_truth(document, path, mapping, arguments) for path in verified]
    out = arguments.layout.intermediate("quality", arguments.method)
    write_quality_report(out, QualityReport(arguments.pdf.name, document.page_count, pages, ground_truth))
    logger.info("quality report written", extra={"pages": len(pages), "verified_pages": len(ground_truth), "report": str(out / "report.md"),
                                                 "ocr_calls": arguments.ocr.calls})


def _probe(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    step = max(1, document.page_count // SAMPLE_PAGES)
    result = probe_document(document, arguments.pages or list(range(1, document.page_count + 1, step)))
    for usage in result.fonts:
        logger.info("font", extra={"family": usage.family, "pages": usage.pages, "glyphs": usage.glyphs,
                                   "candidate": usage.family in result.profile.anu_fonts})
    logger.info("zero-width glyphs (marks)", extra={"glyphs": "".join(char for char, _ in result.zero_width.most_common(40))})
    if arguments.write:
        save_profile(arguments.write, result.profile)
        logger.info("profile written", extra={"path": str(arguments.write)})


def _clean(arguments: argparse.Namespace) -> None:
    layouts = books() if arguments.all else [arguments.layout]
    for layout in layouts:
        if layout.intermediate_root.exists():
            shutil.rmtree(layout.intermediate_root)
            logger.info("intermediate files removed", extra={"path": str(layout.intermediate_root)})


def _add_core_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    convert = commands.add_parser("convert", help="convert the book with a method's gold; final output unless --pages/--mapping")
    convert.add_argument("--method", choices=METHODS, required=True)
    convert.add_argument("--pages", type=page_range, help="1-based, e.g. 6-10; a partial run goes to output/intermediate/convert/")
    convert.set_defaults(handler=_convert)
    quality = commands.add_parser("quality", help="report where Tesseract and the conversion disagree, and accuracy against verified/")
    quality.add_argument("--method", choices=METHODS, required=True)
    quality.add_argument("--pages", type=page_range, help="1-based, e.g. 1-449; default whole PDF")
    quality.add_argument("--ocr-missing", action="store_true", help="run Tesseract on requested pages that have no cached OCR (slow)")
    quality.add_argument("--verified", type=Path, help="default files/<book>/state/verified")
    quality.set_defaults(handler=_quality)
    clean = commands.add_parser("clean", help="delete a book's output/intermediate/ (or every book's with --all)")
    clean.add_argument("--all", action="store_true", help="every book under files/")
    clean.set_defaults(handler=_clean)
    probe = commands.add_parser("probe", help="inspect a PDF's fonts and propose a font profile")
    probe.add_argument("--pages", type=page_range, help="1-based sample pages; default ~10 spread across the PDF")
    probe.add_argument("--write", type=Path, help="write the proposed profile JSON here")
    probe.set_defaults(handler=_probe)


def main() -> None:
    parser = argparse.ArgumentParser(prog="anu-unicode", description=DESCRIPTION)
    parser.add_argument("--font", default="anu", help="font encoding folder under fonts/ holding the profile and both approaches' gold")
    parser.add_argument("--book", help="book folder under files/ (its PDF is the one in input/), e.g. mahabharatamu")
    parser.add_argument("--profile", type=Path, help="default fonts/<font>/books/<book>.json if present, else fonts/<font>/profile.json")
    parser.add_argument("--mapping", type=Path, help="approach 1 mapping; default fonts/<font>/ocr-learning/mapping.tsv")
    parser.add_argument("--pending", type=Path, help="default files/<book>/state/pending.tsv")
    parser.add_argument("--progress", type=Path, help="default files/<book>/state/progress.tsv")
    parser.add_argument("--suspicious", type=Path, help="default files/<book>/state/suspicious.tsv")
    parser.add_argument("--ocr-cache", type=Path, help="default files/<book>/state/ocr-cache")
    parser.add_argument("--tesseract", default=os.environ.get("TESSERACT_CMD", "tesseract"))
    commands = parser.add_subparsers(dest="command", required=True)
    _add_core_commands(commands)
    ocr_learning.add_commands(commands)
    shape_naming.add_commands(commands)
    scan.add_commands(commands)
    handler = logging.StreamHandler()
    handler.setFormatter(ExtraFormatter("%(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    arguments = parser.parse_args()
    if not arguments.book and arguments.command not in BOOK_FREE_COMMANDS and not getattr(arguments, "all", False):
        parser.error(f"--book is required for {arguments.command}; books: {', '.join(layout.slug for layout in books())}")
    resolve_paths(arguments)
    if arguments.book:
        try:
            arguments.pdf = arguments.layout.input_pdf()
        except LayoutError as error:
            parser.error(str(error))
    arguments.ocr = OcrCache(arguments.ocr_cache, arguments.tesseract) if arguments.book else None
    arguments.profile = load_profile(arguments.profile) if arguments.profile.exists() else DEFAULT_PROFILE
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
