import base64
import html
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from anu_unicode.confirm import ConfirmationResult
from anu_unicode.learn import Occurrence, PageResult
from anu_unicode.mapping import Proposal, Suspicion

STYLE = (
    "body{font-family:sans-serif;margin:16px}td,th{border-bottom:1px solid #ddd;padding:4px;text-align:left;vertical-align:middle}"
    ".u,input.c{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}.g{font-family:monospace}input.c{width:14em}"
    "#export{position:sticky;top:0;background:#fffbe6;border:1px solid #e6d58c;padding:8px;margin-bottom:12px}"
    "textarea{width:100%;height:8em;font-family:'Noto Sans Telugu','Nirmala UI'}"
)
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
    if occurrence is None:
        return ""
    clip = pymupdf.Rect(occurrence.bbox) + (-3, -3, 3, 3)
    png = document[occurrence.page_number - 1].get_pixmap(dpi=150, clip=clip).tobytes("png")
    return f"<img src='data:image/png;base64,{base64.b64encode(png).decode('ascii')}'>"


def _table(title: str, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<h2>{title}</h2><table><tr>{''.join(f'<th>{header}' for header in headers)}</tr>{body}</table>"


def _glyphs(text: str) -> str:
    return f"<span class=g>{html.escape(text)}</span>"


def _telugu(text: str) -> str:
    return f"<span class=u>{html.escape(text)}</span>"


def _input(shown: str) -> str:
    return f"<input class=c data-shown=\"{html.escape(shown, quote=True)}\">"


def _occurrence_rows(document: pymupdf.Document, occurrences: Iterable[Occurrence]) -> list[list[str]]:
    grouped: dict[str, list[Occurrence]] = {}
    for item in occurrences:
        grouped.setdefault(item.converted, []).append(item)
    return [
        [", ".join(sorted({f"p{item.page_number}" for item in items})), str(len(items)), _crop(document, items[0]),
         _glyphs(items[0].glyphs), _telugu(converted), _telugu(items[0].ocr_text), _input(converted)]
        for converted, items in grouped.items()
    ]


def _confirmation_rows(results: Iterable[ConfirmationResult]) -> list[list[str]]:
    return [
        [_telugu(result.confirmation.shown), _telugu(result.confirmation.correct), html.escape(result.status),
         f"p{result.page_number}" if result.page_number else "",
         " ".join(f"{_glyphs(entry.glyphs)}→{_telugu(entry.unicode)}" for entry in result.added),
         f"<b>overrides {_telugu(result.overrides)}</b>" if result.overrides else ""]
        for result in results
    ]


SuspiciousRow = tuple[Suspicion, str, Sequence[Occurrence]]
SUSPICIOUS_EXAMPLES = 4


def _suspicious_rows(document: pymupdf.Document, rows: Iterable[SuspiciousRow]) -> list[list[str]]:
    return [
        [_glyphs(suspicion.glyphs), _telugu(current), _telugu(suspicion.suggested), html.escape(suspicion.status),
         html.escape(suspicion.reason), str(len(occurrences)),
         "".join(f"<div>{_crop(document, item)} {_telugu(item.converted)} p{item.page_number}</div>"
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
        _table("Suspicious mappings (mappings/suspicious.tsv)",
               ("glyphs", "current", "suggested", "status", "reason", "words in batch", "examples"),
               _suspicious_rows(document, suspicious)) if suspicious else "",
        _table("Applied confirmations", ("shown", "correct", "status", "page", "entries", "check"),
               _confirmation_rows(confirmation_results))
        if confirmation_results else "",
        _table("Pages", ("page", "glyphs", "unmapped before", "unmapped after", "new entries"), (
            [str(value) for value in (r.progress.page, r.progress.glyphs, r.progress.unmapped_before, r.progress.unmapped_after,
                                      r.progress.new_entries)]
            for r in results
        )),
        _table("New entries", ("glyphs", "unicode", "first page", "first word", "image"), (
            [_glyphs(entry.glyphs), _telugu(entry.unicode), str(entry.first_page), _telugu(entry.first_word), _crop(document, occurrence)]
            for r in results for entry, occurrence in r.accepted
        )),
        _table("Unresolved words (still unmapped)", occurrence_headers,
               _occurrence_rows(document, (item for r in results for item in r.unresolved))),
        _table("Suspect words (mapped, but OCR disagrees)", occurrence_headers,
               _occurrence_rows(document, (item for r in results for item in r.suspects))),
        _table("Pending (unconfirmed or conflicting)", ("glyphs", "unicode", "count", "first page", "first word", "contexts"), (
            [_glyphs(p.glyphs), _telugu(p.unicode), str(p.count), str(p.first_page), _telugu(p.first_word),
             _telugu(" ".join(sorted(p.contexts)))] for p in pending
        )),
    ]
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Batch report</title><style>{STYLE}</style>{''.join(sections)}<script>{SCRIPT}</script>",
        encoding="utf-8",
    )
