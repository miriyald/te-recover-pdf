import html
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from anu_unicode.mapping import Proposal, Suspicion
from anu_unicode.ocr_learning.confirm import ConfirmationResult
from anu_unicode.ocr_learning.learn import Occurrence, PageResult
from anu_unicode.review_html import STYLE, crop, glyphs_cell, table, telugu_cell

SCRIPT = """
function confirmations(){return [...document.querySelectorAll('input.c')].filter(i=>i.value.trim())
  .map(i=>i.dataset.shown+'\\t'+i.value.trim()).join('\\n');}
function refresh(){document.getElementById('tsv').value=confirmations();}
function download(){const blob=new Blob([confirmations()+'\\n'],{type:'text/tab-separated-values'});
  const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='confirmations.tsv';link.click();}
document.addEventListener('input',refresh);
"""
EXPORT_PANEL = (
    "<div id=export><b>Confirmations</b>: type the correct word next to any unresolved or suspect word, then "
    "<button onclick='download()'>Download confirmations.tsv</button> into this batch folder (or copy the text below) and run "
    "<code>anu-unicode confirm --batch N</code>.<textarea id=tsv readonly></textarea></div>"
)


def _crop(document: pymupdf.Document, occurrence: Occurrence | None) -> str:
    return crop(document, occurrence.page_number, occurrence.bbox) if occurrence else ""


def _input(shown: str) -> str:
    return f"<input class=c data-shown=\"{html.escape(shown, quote=True)}\">"


def _occurrence_rows(document: pymupdf.Document, occurrences: Iterable[Occurrence]) -> list[list[str]]:
    grouped: dict[str, list[Occurrence]] = {}
    for item in occurrences:
        grouped.setdefault(item.converted, []).append(item)
    return [
        [", ".join(sorted({f"p{item.page_number}" for item in items})), str(len(items)), _crop(document, items[0]),
         glyphs_cell(items[0].glyphs), telugu_cell(converted), telugu_cell(items[0].ocr_text), _input(converted)]
        for converted, items in grouped.items()
    ]


def _confirmation_rows(results: Iterable[ConfirmationResult]) -> list[list[str]]:
    return [
        [telugu_cell(result.confirmation.shown), telugu_cell(result.confirmation.correct), html.escape(result.status),
         f"p{result.page_number}" if result.page_number else "",
         " ".join(f"{glyphs_cell(entry.glyphs)}→{telugu_cell(entry.unicode)}" for entry in result.added),
         f"<b>overrides {telugu_cell(result.overrides)}</b>" if result.overrides else ""]
        for result in results
    ]


SuspiciousRow = tuple[Suspicion, str, Sequence[Occurrence]]
SUSPICIOUS_EXAMPLES = 4


def _suspicious_rows(document: pymupdf.Document, rows: Iterable[SuspiciousRow]) -> list[list[str]]:
    return [
        [glyphs_cell(suspicion.glyphs), telugu_cell(current), telugu_cell(suspicion.suggested), html.escape(suspicion.status),
         html.escape(suspicion.reason), str(len(occurrences)),
         "".join(f"<div>{_crop(document, item)} {telugu_cell(item.converted)} p{item.page_number}</div>"
                 for item in occurrences[:SUSPICIOUS_EXAMPLES])]
        for suspicion, current, occurrences in rows
    ]


@dataclass(frozen=True)
class BatchReport:
    results: Sequence[PageResult]
    pending: Sequence[Proposal]
    confirmations: Sequence[ConfirmationResult] = ()
    suspicious: Sequence[SuspiciousRow] = ()


def write_batch_report(path: Path, report: BatchReport, document: pymupdf.Document) -> None:
    results, pending, confirmation_results, suspicious = report.results, report.pending, report.confirmations, report.suspicious
    occurrence_headers = ("pages", "count", "image", "glyphs", "converted", "OCR", "correct")
    sections = [
        EXPORT_PANEL,
        table("Suspicious mappings (suspicious.tsv)",
              ("glyphs", "current", "suggested", "status", "reason", "words in batch", "examples"),
              _suspicious_rows(document, suspicious)) if suspicious else "",
        table("Applied confirmations", ("shown", "correct", "status", "page", "entries", "check"),
              _confirmation_rows(confirmation_results))
        if confirmation_results else "",
        table("Pages", ("page", "glyphs", "unmapped before", "unmapped after", "new entries"), (
            [str(value) for value in (r.progress.page, r.progress.glyphs, r.progress.unmapped_before, r.progress.unmapped_after,
                                      r.progress.new_entries)]
            for r in results
        )),
        table("New entries", ("glyphs", "unicode", "first page", "first word", "image"), (
            [glyphs_cell(entry.glyphs), telugu_cell(entry.unicode), str(entry.first_page), telugu_cell(entry.first_word),
             _crop(document, occurrence)]
            for r in results for entry, occurrence in r.accepted
        )),
        table("Unresolved words (still unmapped)", occurrence_headers,
              _occurrence_rows(document, (item for r in results for item in r.unresolved))),
        table("Suspect words (mapped, but OCR disagrees)", occurrence_headers,
              _occurrence_rows(document, (item for r in results for item in r.suspects))),
        table("Pending (unconfirmed or conflicting)", ("glyphs", "unicode", "count", "first page", "first word", "contexts"), (
            [glyphs_cell(p.glyphs), telugu_cell(p.unicode), str(p.count), str(p.first_page), telugu_cell(p.first_word),
             telugu_cell(" ".join(sorted(p.contexts)))] for p in pending
        )),
    ]
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Batch report</title><style>{STYLE}</style>{''.join(sections)}<script>{SCRIPT}</script>",
        encoding="utf-8",
    )
