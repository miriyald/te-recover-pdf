import argparse
import base64
import io
import logging
import re
import shutil
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import astuple, dataclass, replace
from functools import cache
from itertools import groupby
from pathlib import Path

import pymupdf
from PIL import Image

from anu_unicode.command_support import page_range, requested_pages
from anu_unicode.convert import UNMAPPED_OPEN
from anu_unicode.mapping import write_rows
from anu_unicode.scan.ambiguity import Verdict, check_index, write_ambiguity
from anu_unicode.scan.catalog import Shape, ShapeCatalog, Thresholds, load_catalog, shape_of
from anu_unicode.scan.checks import check_decisions, write_rechecks
from anu_unicode.scan.conversion import Choice, ScanText, convert_scan_page, equals_word
from anu_unicode.scan.evaluation import Errors, Miss, Score, score_page, write_misses, write_scores
from anu_unicode.scan.glyph_ocr import GlyphOcr, largest_component, propose, tesseract_glyph
from anu_unicode.scan.index import Occurrence, ShapeIndex, previous_assignments, write_index, write_occurrences
from anu_unicode.scan.inference import Label, WordEvidence, infer, marks_of, read_labels, render, seed_labels, word_evidence, write_labels
from anu_unicode.scan.ink import Bitmap, Component, find_components, render_ink
from anu_unicode.scan.names import Speller, is_symbolic, validate_recipes
from anu_unicode.scan.ocr_fixes import fix_text, load_fixes
from anu_unicode.scan.ocr_training import Tools, Training, confirmed_lines, make_lstmf, model_entries, train, write_lines
from anu_unicode.scan.page import MIN_AREA, ScanPage, scan_page
from anu_unicode.scan.profile import ScanProfile, load_scan_profile, unit_height
from anu_unicode.scan.recipes import propose_recipes, write_proposals
from anu_unicode.scan.review import ReviewInput, Sheet, read_decisions, review_rows, write_review
from anu_unicode.scan.source import read_occurrences
from anu_unicode.scan.split import MIXED, Division, Mixed, divide, find_mixed, readings, subclusters
from anu_unicode.scan.word_ocr import WordKey, WordOcr, ocr_cache_name, read_words, tesseract_word, word_box, word_image, words_of
from anu_unicode.shape_naming.shapes import load_recipes

logger = logging.getLogger(__name__)
SCAN = "[scanned books]"
ASSIGNMENTS = "scan-occurrences.tsv"
GLYPH_OCR = "scan-glyph-ocr.tsv"
LABELS = "scan-labels.tsv"
GOLD_FILE = re.compile(r"page-(\d+)\.txt")
CROP_SIZE = (900, 140)


class CatalogUnitError(ValueError):
    pass


def existing_file(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"no such file: {path}")
    return path


def checked_catalog(path: Path, profile: ScanProfile) -> ShapeCatalog:
    catalog = load_catalog(path)
    if catalog.shape_unit != profile.shape_unit:
        raise CatalogUnitError(f"{path} holds shapes scaled by {catalog.shape_unit} height but the profile says {profile.shape_unit};"
                               " run scan-index with --rebuild")
    return catalog


def _catalog(arguments: argparse.Namespace, profile: ScanProfile) -> ShapeCatalog:
    if arguments.catalog.exists() and not arguments.rebuild:
        return checked_catalog(arguments.catalog, profile)
    thresholds = Thresholds(arguments.max_stray, arguments.max_height_drift, arguments.max_aspect_drift)
    return ShapeCatalog(thresholds, shape_unit=profile.shape_unit)


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
    profile = load_scan_profile(arguments.scan_profile)
    pages = [scan_page(document[number - 1], number, profile) for number in requested_pages(arguments, document)]
    assigned = arguments.layout.state / ASSIGNMENTS
    previous = previous_assignments(read_occurrences(assigned)) if not arguments.rebuild else {}
    index = ShapeIndex(_catalog(arguments, profile), previous)
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


def _raw_texts(arguments: argparse.Namespace, words: dict[WordKey, list[Occurrence]], ink: Callable[[int], Bitmap]) -> dict[WordKey, str]:
    model = _ocr_model(arguments)
    stored = arguments.layout.state / ocr_cache_name(model)
    return read_words(words, ink, WordOcr(lambda image: tesseract_word(image, arguments.tesseract, model), stored))


def _ocr_model(arguments: argparse.Namespace) -> Path | None:
    name = load_scan_profile(arguments.scan_profile).ocr_model
    if not name:
        return None
    model: Path = arguments.layout.state / "ocr" / f"{name}.traineddata"
    if not model.is_file():
        raise FileNotFoundError(f"the scan profile names OCR model {name!r}, but {model} does not exist")
    return model


def _fixed(arguments: argparse.Namespace, texts: dict[WordKey, str]) -> dict[WordKey, str]:
    fixes = load_fixes(arguments.ocr_fixes)
    return {key: fix_text(text, fixes) for key, text in texts.items()} if fixes else texts


def _texts(arguments: argparse.Namespace, words: dict[WordKey, list[Occurrence]], ink: Callable[[int], Bitmap]) -> dict[WordKey, str]:
    return _fixed(arguments, _raw_texts(arguments, words, ink))


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


def _member_shapes(arguments: argparse.Namespace, items: list[Occurrence]) -> dict[Occurrence, Shape]:
    document = pymupdf.open(arguments.pdf)
    shape_unit = load_scan_profile(arguments.scan_profile).shape_unit
    shapes: dict[Occurrence, Shape] = {}
    for page, on_page in groupby(sorted(items, key=lambda item: item.page), key=lambda item: item.page):
        ink = render_ink(document[page - 1])
        body_height = unit_height(find_components(ink, MIN_AREA), shape_unit)
        for item in on_page:
            shapes[item] = shape_of(Component(item.bbox, largest_component(ink, item.bbox)), item.band, body_height)
    return shapes


def _apply_moves(arguments: argparse.Namespace, groups: list[Sequence[Occurrence]], shapes: dict[Occurrence, Shape]) -> list[int]:
    catalog = load_catalog(arguments.catalog)
    new_ids = [catalog.add_shapes([shapes[item] for item in group]) for group in groups]
    moved = {(item.page, item.bbox): new_id for group, new_id in zip(groups, new_ids) for item in group}
    assigned = arguments.layout.state / ASSIGNMENTS
    write_occurrences(assigned, [replace(item, shape_id=moved.get((item.page, item.bbox), item.shape_id))
                                 for item in read_occurrences(assigned)])
    catalog.save(arguments.catalog)
    return new_ids


SplitPlan = tuple[list[tuple[Mixed, Division | None]], dict[int, list[list[Occurrence]]], dict[Occurrence, Shape]]


def _split_plan(arguments: argparse.Namespace, occurrences: list[Occurrence]) -> SplitPlan:
    words = words_of(occurrences)
    decisions, labels = read_decisions(arguments.decisions), read_labels(arguments.layout.state / LABELS)
    by_id = readings(words, _texts(arguments, words, _renderer(arguments)), labels, _speller(arguments, decisions), marks_of(occurrences))
    marked = sorted(shape_id for shape_id, name in decisions.items() if name == MIXED)
    mixed = [candidate for candidate in find_mixed(by_id, labels) if candidate.shape_id not in marked]
    wanted = {candidate.shape_id for candidate in mixed} | set(marked)
    shapes = _member_shapes(arguments, [item for item in occurrences if item.shape_id in wanted])
    outcomes = [(candidate, divide(candidate, {item: shape.canvas for item, shape in shapes.items() if item.shape_id == candidate.shape_id},
                                   by_id[candidate.shape_id])) for candidate in mixed]
    found = {shape_id: subclusters({item: shape for item, shape in shapes.items() if item.shape_id == shape_id}) for shape_id in marked}
    return outcomes, {shape_id: groups for shape_id, groups in found.items() if len(groups) > 1}, shapes


def _scan_split(arguments: argparse.Namespace) -> None:
    outcomes, regrouped, shapes = _split_plan(arguments, read_occurrences(arguments.layout.intermediate("scan-index") / "occurrences.tsv"))
    divisions = [division for _, division in outcomes if division and division.move]
    groups: list[Sequence[Occurrence]] = [division.move for division in divisions]
    groups += [group for found in regrouped.values() for group in found]
    assigned: list[int | str] = [*_apply_moves(arguments, groups, shapes)] if arguments.apply else [""] * len(groups)
    new_ids = iter(assigned)
    split_ids = {division.mixed.shape_id: next(new_ids) for division in divisions}
    regrouped_ids = {shape_id: [next(new_ids) for _ in found] for shape_id, found in regrouped.items()}
    _split_report(arguments, [(candidate, division, split_ids.get(candidate.shape_id, "")) for candidate, division in outcomes],
                  {shape_id: (found, regrouped_ids[shape_id]) for shape_id, found in regrouped.items()})


def _split_report(arguments: argparse.Namespace, outcomes: list[tuple[Mixed, Division | None, int | str]],
                  regrouped: dict[int, tuple[list[list[Occurrence]], list[int | str]]]) -> None:
    out = arguments.layout.intermediate("scan-split")
    out.mkdir(parents=True, exist_ok=True)
    rows = [(candidate.shape_id, candidate.keep, candidate.other, candidate.kept, candidate.other_count,
             "split" if division else "same_look", len(division.move) if division else 0, new_id)
            for candidate, division, new_id in outcomes]
    rows += [(shape_id, MIXED, "", len(found[0]), sum(len(group) for group in found[1:]), f"regrouped into {len(found)}",
              sum(len(group) for group in found), ",".join(str(new_id) for new_id in new_ids))
             for shape_id, (found, new_ids) in regrouped.items()]
    write_rows(out / "splits.tsv", ("shape_id", "keep", "other", "kept_words", "other_words", "outcome", "moved", "new_id"), rows)
    divisions = [division for _, division, _ in outcomes if division]
    moved = sum(len(division.move) for division in divisions) + sum(len(group) for found, _ in regrouped.values() for group in found)
    logger.info("mixed shape ids checked", extra={
        "mixed": len(outcomes), "split": len(divisions), "same_look": len(outcomes) - len(divisions), "marked_mixed": len(regrouped),
        "groups": sum(len(found) for found, _ in regrouped.values()), "moved": moved, "applied": arguments.apply,
        "report": str(out / "splits.tsv")})


@dataclass(frozen=True)
class Conversion:
    words: dict[WordKey, list[Occurrence]]
    raw_texts: dict[WordKey, str]
    texts: dict[WordKey, str]
    ink: Callable[[int], Bitmap]
    pages: list[tuple[int, dict[WordKey, list[Occurrence]], ScanText]]


def _conversion(arguments: argparse.Namespace, pages: list[int] | None) -> Conversion:
    words = words_of(_occurrences(arguments, pages))
    ink = _renderer(arguments)
    raw_texts = _raw_texts(arguments, words, ink)
    texts = _fixed(arguments, raw_texts)
    labels = read_labels(arguments.layout.state / LABELS)
    speller = _speller(arguments, read_decisions(arguments.decisions))
    space_gap = load_scan_profile(arguments.scan_profile).space_gap
    converted = []
    for number in sorted({key[0] for key in words}):
        page_words = {key: items for key, items in words.items() if key[0] == number}
        converted.append((number, page_words, convert_scan_page(page_words, labels, texts, speller, space_gap)))
    return Conversion(words, raw_texts, texts, ink, converted)


def _scan_convert(arguments: argparse.Namespace) -> None:
    conversion = _conversion(arguments, arguments.pages)
    out = arguments.layout.intermediate("scan-convert")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    choices: Counter[Choice] = Counter()
    pages: list[str] = []
    disagreements: list[tuple[int, int, int, str, str]] = []
    gaps: list[tuple[int, int, int, str]] = []
    for number, _, page in conversion.pages:
        text = "\n".join(page.lines)
        (out / f"page-{number}.unicode.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
        pages.append(text)
        choices.update(page.choices)
        disagreements.extend((*key, ours, ocr) for key, ours, ocr in page.disagreements)
        gaps.extend((*key, missing) for key, missing in page.gaps)
    (out / "book.txt").write_text("\n\f".join(pages) + "\n", encoding="utf-8", newline="\n")
    write_rows(out / "disagreements.tsv", ("page", "line", "word", "ours", "word_ocr"), disagreements)
    write_rows(out / "gaps.tsv", ("page", "line", "word", "missing"), gaps)
    logger.info("scan conversion done", extra={"pages": len(pages), "choices": {choice.value: count for choice, count in choices.items()},
                                               "disagreements": len(disagreements), "gaps": len(gaps), "out": str(out)})


def gold_folder(value: str) -> dict[int, str]:
    folder = Path(value)
    pages = {int(match.group(1)): path.read_text(encoding="utf-8")
             for path in sorted(folder.glob("page-*.txt")) if (match := GOLD_FILE.fullmatch(path.name))}
    if not pages:
        raise argparse.ArgumentTypeError(f"no page-<number>.txt files in {folder}")
    return pages


def _crop(ink: Bitmap, boxes: list[tuple[int, int, int, int]]) -> str:
    merged = min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)
    image = word_image(ink, merged)
    image.thumbnail(CROP_SIZE)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _ocr_alone(words: dict[WordKey, list[Occurrence]], texts: dict[WordKey, str]) -> str:
    return " ".join("=" if equals_word(words[key]) else texts.get(key, "") for key in sorted(words))


def _totals(name: str, scores: Sequence[Score | Errors]) -> dict[str, int]:
    return {f"{name}_total": sum(astuple(score)[0] for score in scores), f"{name}_ours": sum(score.ours for score in scores),
            f"{name}_ocr": sum(score.ocr for score in scores)}


def _scan_evaluate(arguments: argparse.Namespace) -> None:
    golds: dict[int, str] = arguments.gold
    conversion = _conversion(arguments, sorted(golds))
    scores = [score_page(number, golds[number], converted, _ocr_alone(page_words, conversion.raw_texts), conversion.raw_texts)
              for number, page_words, converted in conversion.pages]
    out = arguments.layout.intermediate("scan-evaluate")
    write_scores(out / "scores.tsv", scores)

    def miss_crop(miss: Miss) -> str | None:
        return _crop(conversion.ink(miss.page), [word_box(conversion.words[key]) for key in miss.keys]) if miss.keys else None
    write_misses(out / "misses.html", scores, miss_crop)
    logger.info("scan evaluation done", extra={
        "pages": [score.page for score in scores], "missing_pages": sorted(set(golds) - {score.page for score in scores}),
        **_totals("words", [score.words for score in scores]), **_totals("letter_words", [score.letter_words for score in scores]),
        **_totals("letter_errors", [score.letter_errors for score in scores]),
        "causes": dict(Counter(miss.cause.value for score in scores for miss in score.misses)), "out": str(out)})


def _training_lines(arguments: argparse.Namespace, entries: set[str]) -> list[tuple[str, Image.Image, str]]:
    conversion = _conversion(arguments, None)
    lines = []
    for number, page_words, page in conversion.pages:
        if number in arguments.gold:
            continue
        for line in confirmed_lines(page, entries):
            box = word_box([item for key in line.keys for item in page_words[key]])
            lines.append((f"p{number}-{line.keys[0][1]:02}-{line.keys[0][2]:02}", word_image(conversion.ink(number), box), line.text))
    return lines


def _scan_train_ocr(arguments: argparse.Namespace) -> None:
    tesseract = Path(shutil.which(arguments.tesseract) or arguments.tesseract)
    base = arguments.base_model or tesseract.parent / "tessdata" / "tel.traineddata"
    if not base.is_file():
        raise FileNotFoundError(f"no base model at {base}; pass --base-model")
    folder = arguments.layout.state / "ocr" / "train" / arguments.name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    training = Training(Tools(tesseract), base, folder)
    lines = _training_lines(arguments, model_entries(training))
    images = write_lines(folder, lines)
    lstmf = make_lstmf(training, images)
    output = train(training, lstmf, arguments.layout.state / "ocr" / f"{arguments.name}.traineddata", arguments.iterations)
    logger.info("scan OCR model trained", extra={
        "lines": len(lines), "dropped": len(images) - len(lstmf), "held_out_pages": sorted(arguments.gold), "base": str(base),
        "iterations": arguments.iterations, "model": str(output), "log": str(folder / "training.log")})


def _pages_option(parser: argparse.ArgumentParser, default: str) -> None:
    parser.add_argument("--pages", type=page_range, help=f"1-based, e.g. 51 or 4-13; default {default}")


def _decisions_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--decisions", type=Path, help="reviewed shape names; default fonts/<font>/scan/decisions.tsv")
    parser.add_argument("--recipes", dest="scan_recipes", type=Path, help="name sequences to text; default fonts/<font>/scan/recipes.tsv")
    parser.add_argument("--ocr-fixes", type=Path, help="whole-token OCR fixes; default fonts/<font>/scan/ocr-fixes.tsv")


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    index = commands.add_parser("scan-index", help=f"{SCAN} give every ink component of a scanned page a shape id")
    _pages_option(index, "whole PDF")
    index.add_argument("--catalog", type=Path, help="shape catalog to extend; default files/<book>/state/scan-catalog.npz")
    index.add_argument("--rebuild", action="store_true", help="ignore an existing catalog and cluster from scratch")
    index.add_argument("--scan-profile", type=existing_file, help="grouping units and thresholds; default fonts/<font>/scan/profile.json")
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
    evaluate = commands.add_parser("scan-evaluate", help=f"{SCAN} score indexed pages against gold text; write cause-tagged misses")
    evaluate.add_argument("--gold", type=gold_folder, required=True, help="folder of page-<number>.txt files holding the correct text")
    _decisions_option(evaluate)
    evaluate.set_defaults(handler=_scan_evaluate)
    train_ocr = commands.add_parser("scan-train-ocr", help=f"{SCAN} fine-tune Tesseract on confirmed words, gold pages held out")
    train_ocr.add_argument("--name", required=True, help="model name; written to files/<book>/state/ocr/<name>.traineddata")
    train_ocr.add_argument("--gold", type=gold_folder, required=True, help="folder of page-<number>.txt gold pages, kept out of training")
    train_ocr.add_argument("--iterations", type=int, default=3000, help="lstmtraining iterations")
    train_ocr.add_argument("--base-model", type=existing_file, help="traineddata to start from; default tessdata/tel.traineddata")
    _decisions_option(train_ocr)
    train_ocr.set_defaults(handler=_scan_train_ocr)
    split = commands.add_parser("scan-split", help=f"{SCAN} find shape ids that hold two shapes and split them (report unless --apply)")
    _decisions_option(split)
    split.add_argument("--catalog", type=Path, help="default files/<book>/state/scan-catalog.npz")
    split.add_argument("--apply", action="store_true", help="add the new ids to the catalog and move their occurrences; re-run scan-index")
    split.set_defaults(handler=_scan_split)
