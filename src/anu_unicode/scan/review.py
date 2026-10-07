import html
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from anu_unicode.mapping import read_rows
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import Label
from anu_unicode.scan.word_ocr import WordKey
from anu_unicode.shape_naming.atlas import STYLE
from anu_unicode.shape_naming.shapes import NOTHING

FLAG_AGREEMENT = 0.6
EXAMPLES = 3

REVIEW_SCRIPT = """
function rows(){return [...document.querySelectorAll('tr[data-id]')].map(row=>[row.dataset.id,row.querySelector('input').value.trim()]);}
function download(){const decided=Object.assign({},EARLIER);rows().forEach(([id,value])=>{if(value){decided[id]=value;}});
  const tsv='shape_id\\tunicode\\n'+Object.keys(decided).sort((a,b)=>a-b).map(id=>id+'\\t'+decided[id]).join('\\n')+'\\n';
  const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([tsv],{type:'text/tab-separated-values'}));
  link.download='decisions.tsv';link.click();}
"""


@dataclass(frozen=True)
class ReviewInput:
    occurrences: Sequence[Occurrence]
    labels: Mapping[int, Label]
    decisions: Mapping[int, str] = field(default_factory=dict)
    marks: frozenset[int] = frozenset()
    texts: Mapping[WordKey, str] = field(default_factory=dict)
    pages: frozenset[int] = frozenset()


@dataclass(frozen=True)
class ReviewRow:
    shape_id: int
    count: int
    label: Label | None
    flagged: bool
    examples: tuple[str, ...]


def read_decisions(path: Path) -> dict[int, str]:
    return {int(row["shape_id"]): row["unicode"] for row in read_rows(path)}


def _flagged(shape_id: int, label: Label | None, marks: frozenset[int]) -> bool:
    if label is None:
        return True
    return (label.unicode == NOTHING and shape_id not in marks) or label.agreement < FLAG_AGREEMENT


def review_rows(source: ReviewInput, top: int) -> list[ReviewRow]:
    counts: Counter[int] = Counter()
    examples: dict[int, list[str]] = defaultdict(list)
    on_pages: set[int] = set()
    for item in source.occurrences:
        if item.shape_id == EQUALS:
            continue
        counts[item.shape_id] += 1
        text = source.texts.get((item.page, item.line, item.word), "")
        if text and len(examples[item.shape_id]) < EXAMPLES and text not in examples[item.shape_id]:
            examples[item.shape_id].append(text)
        if not source.pages or item.page in source.pages:
            on_pages.add(item.shape_id)
    rows = [ReviewRow(shape_id, counts[shape_id], source.labels.get(shape_id),
                      _flagged(shape_id, source.labels.get(shape_id), source.marks), tuple(examples[shape_id]))
            for shape_id in on_pages if shape_id not in source.decisions]
    return sorted(rows, key=lambda row: (not row.flagged, -row.count, row.shape_id))[:top]


def _row(row: ReviewRow, strips: str) -> str:
    label = row.label
    value = html.escape(label.unicode if label else "", quote=True)
    evidence = f"{label.source} · {label.support} words · {label.agreement:.0%}" if label else "unlabelled"
    words = " · ".join(html.escape(text) for text in row.examples)
    flag = " class=flag" if row.flagged else ""
    return (f"<tr data-id={row.shape_id}{flag}><td>#{row.shape_id}</td><td>{row.count}</td>"
            f"<td><img class=strip src='{strips}/{row.shape_id}.png'></td><td><input value=\"{value}\"></td>"
            f"<td>{evidence}</td><td class=p>{words}</td></tr>")


def write_review(path: Path, rows: Sequence[ReviewRow], earlier: Mapping[int, str], strips: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flagged = sum(row.flagged for row in rows)
    style = (STYLE + "img.strip{height:40px}.p,input{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}"
             "tr.flag td{background:#fff3e0}")
    intro = (f"<p>{len(rows)} shape ids, {flagged} flagged (shaded). Correct a label or leave it to confirm it; "
             f"use <code>{NOTHING}</code> for a piece that adds nothing and <code>◌ె</code> for a sign drawn before its consonant. "
             "<button onclick='download()'>Download decisions.tsv</button></p>")
    body = "".join(_row(row, strips) for row in rows)
    earlier_json = json.dumps({str(shape_id): value for shape_id, value in sorted(earlier.items())}, ensure_ascii=False)
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Scan review</title><style>{style}</style>{intro}"
        f"<table><tr><th>id<th>count<th>prototype · members<th>label<th>evidence<th>in words (OCR)</tr>{body}</table>"
        f"<script>const EARLIER={earlier_json};{REVIEW_SCRIPT}</script>",
        encoding="utf-8", newline="\n",
    )
