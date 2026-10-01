import argparse
import logging
import os
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import pymupdf

from anu_unicode.approve import approve_batch, batch_pages
from anu_unicode.atlas import collect_units, load_fonts, write_atlas
from anu_unicode.confirm import ConfirmationResult, apply_confirmations, parse_confirmations
from anu_unicode.convert import UNMAPPED_OPEN, Coverage, convert_anu, convert_page, convert_segments, render
from anu_unicode.glyphs import page_lines, split_words
from anu_unicode.learn import LearningState, Occurrence, PageResult, review_page, run_batch
from anu_unicode.mapping import (
    Suspicion,
    append_progress,
    apply_accepted,
    load_entries,
    load_mapping,
    load_pending,
    load_suspicions,
    processed_pages,
    save_entries,
    save_pending,
)
from anu_unicode.ocr import OcrCache
from anu_unicode.probe import SAMPLE_PAGES, probe_document
from anu_unicode.profile import DEFAULT_PROFILE, FontProfile, load_profile, save_profile
from anu_unicode.quality import GroundTruthQuality, PageQuality, compare_words, ground_truth_quality, page_quality
from anu_unicode.quality_report import QualityReport, write_quality_report
from anu_unicode.report import BatchReport, SuspiciousRow, write_batch_report

logger = logging.getLogger(__name__)
MATCH_OVERLAP = 0.3
STANDARD_RECORD_FIELDS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class ExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extra = {key: value for key, value in vars(record).items() if key not in STANDARD_RECORD_FIELDS}
        return f"{super().format(record)} {extra}" if extra else super().format(record)


def page_range(text: str) -> list[int]:
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def _write_page(out: Path, document: pymupdf.Document, number: int, mapping: dict[str, str], profile: FontProfile) -> None:
    text = convert_page(document[number - 1], mapping, Coverage(), profile)
    (out / f"page-{number}.unicode.txt").write_text(text + "\n", encoding="utf-8", newline="\n")


def _suspicious(document: pymupdf.Document, pages: Iterable[int], state: LearningState,
                suspicions: Iterable[Suspicion]) -> list[SuspiciousRow]:
    entries = state.entries
    mapping = state.mapping
    words = [(number, word) for number in pages for line in page_lines(document[number - 1], state.profile) for word in split_words(line)]
    rows: list[SuspiciousRow] = []
    for suspicion in suspicions:
        occurrences = [
            Occurrence(number, word.bbox, word.text, render(segments, Coverage()), "")
            for number, word in words
            for segments in [convert_segments(word.text, mapping)]
            if any(glyphs == suspicion.glyphs for glyphs, _ in segments)
        ]
        current = entries[suspicion.glyphs].unicode if suspicion.glyphs in entries else ""
        rows.append((suspicion, current, occurrences))
    return rows


def _still_unresolved(occurrences: Iterable[Occurrence], mapping: dict[str, str]) -> list[Occurrence]:
    current = [replace(item, converted=render(convert_segments(item.glyphs, mapping), Coverage())) for item in occurrences]
    return [item for item in current if UNMAPPED_OPEN in item.converted]


def _learn(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    state = LearningState(load_entries(arguments.mapping), load_pending(arguments.pending), arguments.profile)
    end = min(arguments.end or document.page_count, document.page_count)
    done = processed_pages(arguments.progress)
    numbers = [number for number in range(arguments.start, end + 1) if number not in done]
    if not numbers:
        logger.info("nothing to learn", extra={"start": arguments.start, "end": end})
        return
    start = numbers[0]
    out = arguments.out / f"batch-{start}"
    out.mkdir(parents=True, exist_ok=True)

    def checkpoint(result: PageResult) -> None:
        save_entries(arguments.mapping, state.entries)
        save_pending(arguments.pending, state.pending)
        append_progress(arguments.progress, result.progress)
        _write_page(out, document, result.progress.page, state.mapping, state.profile)

    results = run_batch(
        (document[number - 1] for number in numbers),
        state,
        arguments.ocr,
        arguments.stop_after,
        checkpoint,
    )
    learned_pages = [result.progress.page for result in results]
    for result in results:
        _write_page(out, document, result.progress.page, state.mapping, state.profile)
        result.unresolved = _still_unresolved(result.unresolved, state.mapping)
    suspicious = _suspicious(document, learned_pages, state, load_suspicions(arguments.suspicious))
    write_batch_report(out / "report.html", BatchReport(results, state.pending, suspicious=suspicious), document)
    logger.info("batch done", extra={
        "pages": f"{start}-{results[-1].progress.page}" if results else "none",
        "new_entries": sum(len(result.accepted) for result in results),
        "pending": len(state.pending),
        "ocr_calls": arguments.ocr.calls,
        "ocr_cache_hits": arguments.ocr.hits,
        "report": str(out / "report.html"),
    })


def _rebuild_pages(arguments: argparse.Namespace, document: pymupdf.Document, state: LearningState,
                   confirmation_results: Iterable[ConfirmationResult]) -> list[PageResult]:
    batch = arguments.out / f"batch-{arguments.batch}"
    confirmed_text = {result.confirmation.correct for result in confirmation_results if result.status in ("added", "already correct")}
    results = []
    for number in batch_pages(batch):
        _write_page(batch, document, number, state.mapping, state.profile)
        page_result = review_page(document[number - 1], state.entries, arguments.ocr, state.profile)
        page_result.suspects = [item for item in page_result.suspects if item.converted not in confirmed_text]
        results.append(page_result)
    return results


def _confirm(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    batch = arguments.out / f"batch-{arguments.batch}"
    pages = batch_pages(batch)
    state = LearningState(load_entries(arguments.mapping), load_pending(arguments.pending), arguments.profile)
    reviewed_mapping = state.mapping
    suspicions = load_suspicions(arguments.suspicious)
    logger.info("suspicious mappings applied", extra={"changes": apply_accepted(state.entries, suspicions)})
    words = [(number, word) for number in pages for line in page_lines(document[number - 1], state.profile) for word in split_words(line)]
    file = arguments.file or batch / "confirmations.tsv"
    confirmation_results = apply_confirmations(parse_confirmations(file.read_text(encoding="utf-8")), words, state, reviewed_mapping)
    save_entries(arguments.mapping, state.entries)
    save_pending(arguments.pending, state.pending)
    for result in confirmation_results:
        logger.info("confirmation", extra={"shown": result.confirmation.shown, "correct": result.confirmation.correct,
                                           "status": result.status, "added": [(e.glyphs, e.unicode) for e in result.added],
                                           "overrides": result.overrides})
    results = _rebuild_pages(arguments, document, state, confirmation_results)
    report = BatchReport(results, state.pending, confirmation_results, _suspicious(document, pages, state, suspicions))
    write_batch_report(batch / "report.html", report, document)
    logger.info("batch rebuilt", extra={"batch": arguments.batch, "pages": len(pages),
                                        "unresolved": sum(len(result.unresolved) for result in results),
                                        "ocr_calls": arguments.ocr.calls, "ocr_cache_hits": arguments.ocr.hits,
                                        "report": str(batch / "report.html")})


def _approve(arguments: argparse.Namespace) -> None:
    pages = approve_batch(arguments.out / f"batch-{arguments.batch}", arguments.verified, arguments.archive / "batches")
    logger.info("batch approved", extra={"batch": arguments.batch, "pages": pages, "verified": str(arguments.verified)})


def _convert(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    mapping = load_mapping(arguments.mapping)
    arguments.out.mkdir(parents=True, exist_ok=True)
    total = Coverage()
    for number in arguments.pages:
        coverage = Coverage()
        text = convert_page(document[number - 1], mapping, coverage, arguments.profile)
        (arguments.out / f"page-{number}.unicode.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
        total.glyphs += coverage.glyphs
        total.unmapped.update(coverage.unmapped)
        logger.info("page converted", extra={"page": number, "coverage": round(coverage.ratio, 4)})
    report = ["unmapped\tcount"] + [f"{glyphs}\t{count}" for glyphs, count in total.unmapped.most_common()]
    (arguments.out / "unmapped.tsv").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    logger.info("conversion done", extra={"coverage": round(total.ratio, 4), "unmapped_sequences": len(total.unmapped)})


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
    mapping = load_mapping(arguments.mapping)
    requested = arguments.pages or list(range(1, document.page_count + 1))
    cached = {int(path.stem.split("-")[1]) for path in arguments.ocr_cache.glob("page-*.json")}
    numbers = requested if arguments.ocr_missing else [number for number in requested if number in cached]
    pages = [_measure_page(document, number, mapping, arguments) for number in numbers]
    verified = sorted(arguments.verified.glob("page-*.unicode.txt"))
    ground_truth = [_measure_ground_truth(document, path, mapping, arguments) for path in verified]
    out = arguments.out / "quality"
    write_quality_report(out, QualityReport(arguments.pdf.name, document.page_count, pages, ground_truth))
    logger.info("quality report written", extra={"pages": len(pages), "verified_pages": len(ground_truth), "report": str(out / "report.md"),
                                                 "ocr_calls": arguments.ocr.calls})


def _atlas(arguments: argparse.Namespace) -> None:
    document = pymupdf.open(arguments.pdf)
    arguments.out.mkdir(parents=True, exist_ok=True)
    write_atlas(arguments.out / "atlas.html", collect_units(document, arguments.profile), load_mapping(arguments.mapping),
                load_fonts(document, arguments.profile), arguments.top)


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="anu-unicode")
    parser.add_argument("--profile", type=Path, help="font profile JSON (see the probe command); default: the built-in Anu profile")
    parser.add_argument("--pdf", type=Path, default=Path("Mahabharatamu.pdf"))
    parser.add_argument("--mapping", type=Path, default=Path("mappings/mapping.tsv"))
    parser.add_argument("--out", type=Path, default=Path("docs/temp"))
    parser.add_argument("--pending", type=Path, default=Path("mappings/pending.tsv"))
    parser.add_argument("--progress", type=Path, default=Path("mappings/progress.tsv"))
    parser.add_argument("--suspicious", type=Path, default=Path("mappings/suspicious.tsv"))
    parser.add_argument("--ocr-cache", type=Path, default=Path("docs/temp/ocr-cache"))
    parser.add_argument("--tesseract", default=os.environ.get("TESSERACT_CMD", "tesseract"))
    commands = parser.add_subparsers(dest="command", required=True)
    learn = commands.add_parser("learn", help="walk pages, OCR only unmapped glyphs, extend the mapping")
    learn.add_argument("--stop-after", type=int, required=True, help="stop after the page on which X new entries are reached")
    learn.add_argument("--start", type=int, default=1, help="1-based first page; pages in progress.tsv are skipped")
    learn.add_argument("--end", type=int, help="1-based last page; default last page of the PDF")
    learn.set_defaults(handler=_learn)
    confirm = commands.add_parser("confirm", help="apply human-confirmed words to the mapping and rebuild the batch report")
    confirm.add_argument("--batch", type=int, required=True, help="first page of the batch, e.g. 1 for docs/temp/batch-1")
    confirm.add_argument("--file", type=Path, help="confirmations (shown<TAB or =>correct); default <batch>/confirmations.tsv")
    confirm.set_defaults(handler=_confirm)
    approve = commands.add_parser("approve", help="copy a reviewed batch's pages to verified/ and archive the batch")
    approve.add_argument("--batch", type=int, required=True, help="first page of the batch, e.g. 6 for docs/temp/batch-6")
    approve.add_argument("--verified", type=Path, default=Path("verified"))
    approve.add_argument("--archive", type=Path, default=Path("archive"))
    approve.set_defaults(handler=_approve)
    convert = commands.add_parser("convert")
    convert.add_argument("--pages", type=page_range, required=True, help="1-based, e.g. 6-10")
    convert.set_defaults(handler=_convert)
    quality = commands.add_parser("quality", help="report where Tesseract and the conversion disagree, and accuracy against verified/")
    quality.add_argument("--pages", type=page_range, help="1-based, e.g. 1-449; default whole PDF")
    quality.add_argument("--ocr-missing", action="store_true", help="run Tesseract on requested pages that have no cached OCR (slow)")
    quality.add_argument("--verified", type=Path, default=Path("verified"))
    quality.set_defaults(handler=_quality)
    atlas = commands.add_parser("atlas", help="labelling sheet: every glyph unit drawn from the embedded font, most frequent first")
    atlas.add_argument("--top", type=int, default=300, help="number of most frequent units to show")
    atlas.set_defaults(handler=_atlas)
    probe = commands.add_parser("probe", help="inspect a PDF's fonts and propose a font profile")
    probe.add_argument("--pages", type=page_range, help="1-based sample pages; default ~10 spread across the PDF")
    probe.add_argument("--write", type=Path, help="write the proposed profile JSON here")
    probe.set_defaults(handler=_probe)
    handler = logging.StreamHandler()
    handler.setFormatter(ExtraFormatter("%(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    arguments = parser.parse_args()
    arguments.ocr = OcrCache(arguments.ocr_cache, arguments.tesseract)
    arguments.profile = load_profile(arguments.profile) if arguments.profile else DEFAULT_PROFILE
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
