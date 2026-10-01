import argparse
import logging
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import pymupdf

from anu_unicode.convert import UNMAPPED_OPEN, Coverage, convert_page, convert_segments, render
from anu_unicode.glyphs import page_lines, split_words
from anu_unicode.mapping import (
    Suspicion,
    append_progress,
    apply_accepted,
    load_entries,
    load_pending,
    load_suspicions,
    processed_pages,
    save_entries,
    save_pending,
)
from anu_unicode.ocr_learning.approve import approve_batch, batch_pages
from anu_unicode.ocr_learning.confirm import ConfirmationResult, apply_confirmations, parse_confirmations
from anu_unicode.ocr_learning.learn import LearningState, Occurrence, PageResult, review_page, run_batch
from anu_unicode.ocr_learning.report import BatchReport, SuspiciousRow, write_batch_report
from anu_unicode.profile import FontProfile

logger = logging.getLogger(__name__)
APPROACH = "[approach 1: OCR learning]"


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


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    learn = commands.add_parser("learn", help=f"{APPROACH} walk pages, OCR only unmapped glyphs, extend the mapping")
    learn.add_argument("--stop-after", type=int, required=True, help="stop after the page on which X new entries are reached")
    learn.add_argument("--start", type=int, default=1, help="1-based first page; pages in progress.tsv are skipped")
    learn.add_argument("--end", type=int, help="1-based last page; default last page of the PDF")
    learn.set_defaults(handler=_learn)
    confirm = commands.add_parser("confirm", help=f"{APPROACH} apply human-confirmed words to the mapping and rebuild the batch report")
    confirm.add_argument("--batch", type=int, required=True, help="first page of the batch, e.g. 1 for docs/temp/batch-1")
    confirm.add_argument("--file", type=Path, help="confirmations (shown<TAB or =>correct); default <batch>/confirmations.tsv")
    confirm.set_defaults(handler=_confirm)
    approve = commands.add_parser("approve", help=f"{APPROACH} copy a reviewed batch's pages to verified/ and archive the batch")
    approve.add_argument("--batch", type=int, required=True, help="first page of the batch, e.g. 6 for docs/temp/batch-6")
    approve.add_argument("--verified", type=Path, help="default books/<book>/verified")
    approve.add_argument("--archive", type=Path, default=Path("archive"))
    approve.set_defaults(handler=_approve)
