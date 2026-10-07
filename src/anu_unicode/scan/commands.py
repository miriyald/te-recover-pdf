import argparse
import logging
import shutil
from collections import Counter
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pymupdf

from anu_unicode.command_support import page_range, requested_pages
from anu_unicode.convert import UNMAPPED_OPEN
from anu_unicode.mapping import write_rows
from anu_unicode.scan.ambiguity import Verdict, check_index, write_ambiguity
from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, load_catalog
from anu_unicode.scan.checks import check_decisions, write_rechecks
from anu_unicode.scan.conversion import Choice, convert_scan_page
from anu_unicode.scan.glyph_ocr import GlyphOcr, propose, tesseract_glyph
from anu_unicode.scan.index import Occurrence, ShapeIndex, previous_assignments, write_index, write_occurrences
from anu_unicode.scan.inference import Label, WordEvidence, infer, marks_of, read_labels, render, seed_labels, word_evidence, write_labels
from anu_unicode.scan.ink import Bitmap, render_ink
from anu_unicode.scan.names import Speller, is_symbolic, validate_recipes
from anu_unicode.scan.page import ScanPage, scan_page
from anu_unicode.scan.recipes import propose_recipes, write_proposals
from anu_unicode.scan.review import ReviewInput, Sheet, read_decisions, review_rows, write_review
from anu_unicode.scan.source import read_occurrences
from anu_unicode.scan.word_ocr import WordKey, WordOcr, read_words, tesseract_word, words_of
from anu_unicode.shape_naming.shapes import load_recipes

logger = logging.getLogger(__name__)
SCAN = "[scanned books]"
ASSIGNMENTS = "scan-occurrences.tsv"
WORD_OCR = "scan-word-ocr.tsv"
GLYPH_OCR = "scan-glyph-ocr.tsv"
LABELS = "scan-labels.tsv"


def _catalog(arguments: argparse.Namespace) -> ShapeCatalog:
    if arguments.catalog.exists() and not arguments.rebuild:
        return load_catalog(arguments.catalog)
    return ShapeCatalog(Thresholds(arguments.max_stray, arguments.max_height_drift, arguments.max_aspect_drift))


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
    assigned = arguments.layout.state / ASSIGNMENTS
    previous = previous_assignments(read_occurrences(assigned)) if not arguments.rebuild else {}
    index = ShapeIndex(_catalog(arguments), previous)
    for page in pages:
        index.add(page)
    out = arguments.layout.intermediate("scan-index")
    stats = write_index(out, index)
    if arguments.write_catalog:
        index.catalog.save(arguments.catalog)
        write_occurrences(assigned, index.occurrences)
    if arguments.ambiguity:
        _report_ambiguity(arguments, index, pages)
    logger.info("scan index written", extra={"shapes": stats.shapes, "singletons": stats.singletons, "kept_assignments": index.kept,
                                             "shapes_for_99_percent": stats.shapes_for_coverage, "occurrences": stats.occurrences,
                                             "sheet": str(out / "shapes.html"), "catalog_written": arguments.write_catalog})


def _occurrences(arguments: argparse.Namespace, pages: list[int] | None = None) -> list[Occurrence]:
    occurrences = read_occurrences(arguments.layout.intermediate("scan-index") / "occurrences.tsv")
    return [item for item in occurrences if not pages or item.page in pages]


def _renderer(arguments: argparse.Namespace) -> Callable[[int], Bitmap]:
    document = pymupdf.open(arguments.pdf)

    @cache
    def page_ink(page: int) -> Bitmap:
        return render_ink(document[page - 1])
    return page_ink


def _texts(arguments: argparse.Namespace, words: dict[WordKey, list[Occurrence]], ink: Callable[[int], Bitmap]) -> dict[WordKey, str]:
    ocr = WordOcr(lambda image: tesseract_word(image, arguments.tesseract), arguments.layout.state / WORD_OCR)
    return read_words(words, ink, ocr)


def _speller(arguments: argparse.Namespace, decisions: dict[int, str]) -> Speller:
    recipes = load_recipes(arguments.scan_recipes)
    validate_recipes(recipes, {name for name in decisions.values() if is_symbolic(name)})
    return Speller(recipes)


def _scan_label(arguments: argparse.Namespace) -> None:
    occurrences, ink = _occurrences(arguments), _renderer(arguments)
    words = words_of(occurrences)
    texts = _texts(arguments, words, ink)
    glyph_ocr = GlyphOcr(lambda mask: tesseract_glyph(mask, arguments.tesseract), arguments.layout.state / GLYPH_OCR)
    evidence = word_evidence(words, texts)
    decisions = read_decisions(arguments.decisions)
    speller = _speller(arguments, decisions)
    labels = infer(evidence, seed_labels(propose(occurrences, ink, glyph_ocr)), decisions, marks_of(occurrences), speller)
    write_labels(arguments.layout.state / LABELS, labels)
    out = arguments.layout.intermediate("scan-label")
    recipes = propose_recipes(evidence, {shape_id: label.name for shape_id, label in labels.items()}, speller)
    rechecks = check_decisions(evidence, labels, speller)
    write_proposals(out / "recipe-proposals.tsv", recipes)
    write_rechecks(out / "rechecks.tsv", rechecks)
    logger.info("scan labels inferred", extra={**_label_stats(evidence, labels, speller), "recipe_proposals": len(recipes),
                                               "rechecks": len(rechecks), "labels": str(arguments.layout.state / LABELS)})


def _label_stats(evidence: list[WordEvidence], labels: dict[int, Label], speller: Speller) -> dict[str, object]:
    names = {shape_id: label.name for shape_id, label in labels.items()}
    complete = [word for word in evidence if UNMAPPED_OPEN not in speller.spell(word.shape_ids, names)]
    glyphs = [shape_id for word in evidence for shape_id in word.shape_ids]
    return {"words": len(evidence), "labelled_ids": len(labels), "ids": len(set(glyphs)),
            "glyph_coverage": round(sum(shape_id in labels for shape_id in glyphs) / len(glyphs), 4) if glyphs else 0.0,
            "complete_words": len(complete),
            "agreeing_words": sum(render(word.shape_ids, names, speller) == word.text for word in complete),
            "sources": dict(Counter(label.source.value for label in labels.values()))}


def _scan_review(arguments: argparse.Namespace) -> None:
    occurrences = read_occurrences(arguments.layout.intermediate("scan-index") / "occurrences.tsv")
    words = words_of(occurrences)
    decisions, labels = read_decisions(arguments.decisions), read_labels(arguments.layout.state / LABELS)
    speller = _speller(arguments, decisions)
    texts = _texts(arguments, words, _renderer(arguments))
    source = ReviewInput(occurrences, labels, decisions=decisions, marks=marks_of(occurrences), texts=texts,
                         pages=frozenset(arguments.pages or ()), speller=speller)
    evidence = word_evidence(words, texts)
    names = {shape_id: label.name for shape_id, label in labels.items()}
    sheet = Sheet(review_rows(source, arguments.top), check_decisions(evidence, labels, speller), propose_recipes(evidence, names, speller),
                  decisions, speller.recipes)
    name = f"review-pages-{arguments.pages[0]}-{arguments.pages[-1]}.html" if arguments.pages else "review.html"
    path = arguments.layout.intermediate("scan-review") / name
    write_review(path, sheet, "../scan-index/shapes")
    logger.info("scan review sheet written", extra={"rows": len(sheet.rows), "flagged": sum(row.flagged for row in sheet.rows),
                                                    "occurrences": sum(row.count for row in sheet.rows), "rechecks": len(sheet.rechecks),
                                                    "recipe_proposals": len(sheet.proposals), "path": str(path),
                                                    "save_exports_as": [str(arguments.decisions), str(arguments.scan_recipes)]})


def _scan_convert(arguments: argparse.Namespace) -> None:
    occurrences = _occurrences(arguments, arguments.pages)
    words = words_of(occurrences)
    texts = _texts(arguments, words, _renderer(arguments))
    labels = read_labels(arguments.layout.state / LABELS)
    speller = _speller(arguments, read_decisions(arguments.decisions))
    out = arguments.layout.intermediate("scan-convert")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    choices: Counter[Choice] = Counter()
    pages: list[str] = []
    disagreements: list[tuple[int, int, int, str, str]] = []
    for number in sorted({key[0] for key in words}):
        page = convert_scan_page({key: items for key, items in words.items() if key[0] == number}, labels, texts, speller)
        text = "\n".join(page.lines)
        (out / f"page-{number}.unicode.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
        pages.append(text)
        choices.update(page.choices)
        disagreements.extend((*key, ours, ocr) for key, ours, ocr in page.disagreements)
    (out / "book.txt").write_text("\n\f".join(pages) + "\n", encoding="utf-8", newline="\n")
    write_rows(out / "disagreements.tsv", ("page", "line", "word", "ours", "word_ocr"), disagreements)
    logger.info("scan conversion done", extra={"pages": len(pages), "choices": {choice.value: count for choice, count in choices.items()},
                                               "disagreements": len(disagreements), "out": str(out)})


def _pages_option(parser: argparse.ArgumentParser, default: str) -> None:
    parser.add_argument("--pages", type=page_range, help=f"1-based, e.g. 51 or 4-13; default {default}")


def _decisions_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--decisions", type=Path, help="reviewed shape names; default fonts/<font>/scan/decisions.tsv")
    parser.add_argument("--recipes", dest="scan_recipes", type=Path, help="name sequences to text; default fonts/<font>/scan/recipes.tsv")


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    index = commands.add_parser("scan-index", help=f"{SCAN} give every ink component of a scanned page a shape id")
    _pages_option(index, "whole PDF")
    index.add_argument("--catalog", type=Path, help="shape catalog to extend; default files/<book>/state/scan-catalog.npz")
    index.add_argument("--rebuild", action="store_true", help="ignore an existing catalog and cluster from scratch")
    index.add_argument("--write-catalog", action="store_true", help="save the catalog so later runs keep these shape ids")
    index.add_argument("--max-stray", type=float, default=0.2, help="pre-filter: share of ink further than 1 grid pixel from the prototype")
    index.add_argument("--max-height-drift", type=float, default=0.2, help="abs log height difference, in body heights")
    index.add_argument("--max-aspect-drift", type=float, default=0.25, help="abs log aspect-ratio difference")
    index.add_argument("--ambiguity", action="store_true",
                       help="re-check every occurrence against the final shapes; report ambiguous and drifted ones separately")
    index.set_defaults(handler=_scan_index)
    label = commands.add_parser("scan-label", help=f"{SCAN} label every shape id from Tesseract word readings and reviewed decisions")
    _decisions_option(label)
    label.set_defaults(handler=_scan_label)
    review = commands.add_parser("scan-review", help=f"{SCAN} one sheet of the top undecided shape ids, pre-filled, flagged ones first")
    _pages_option(review, "every indexed page")
    _decisions_option(review)
    review.add_argument("--top", type=int, default=50, help="rows on the sheet")
    review.set_defaults(handler=_scan_review)
    convert = commands.add_parser("scan-convert", help=f"{SCAN} write Unicode text: our reading where it holds, else Tesseract's word")
    _pages_option(convert, "every indexed page")
    _decisions_option(convert)
    convert.set_defaults(handler=_scan_convert)
