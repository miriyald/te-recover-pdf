import html
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from anu_unicode.mapping import read_rows
from anu_unicode.scan.inference import comparable_text, differences
from anu_unicode.scan.ink import Box
from anu_unicode.scan.word_ocr import WordKey
from anu_unicode.shape_naming.atlas import STYLE

PER_PATTERN = 5
NO_PATTERN = "spacing or OCR noise"
COLUMNS = ("page", "left", "top", "right", "bottom", "text")

CORRECTION_SCRIPT = """
function fill(button,text){button.closest('tr').querySelector('input').value=text;}
function downloadCorrections(){const corrected=Object.assign({},EARLIER);
  document.querySelectorAll('tr[data-key]').forEach(row=>{
    const value=row.querySelector('input').value.trim();if(value){corrected[row.dataset.key]=value;}});
  const rows=Object.keys(corrected).sort().map(key=>key.split('-').join('\\t')+'\\t'+corrected[key]);
  const link=document.createElement('a');
  link.href=URL.createObjectURL(new Blob([HEADER+'\\n'+rows.join('\\n')+'\\n'],{type:'text/tab-separated-values'}));
  link.download='corrections.tsv';link.click();}
"""

CorrectionKey = tuple[int, Box]


@dataclass(frozen=True)
class Disagreement:
    key: WordKey
    box: Box
    ours: str
    ocr: str
    pattern: str

    @property
    def place(self) -> CorrectionKey:
        return self.key[0], self.box


def read_corrections(path: Path) -> dict[CorrectionKey, str]:
    return {(int(row["page"]), (int(row["left"]), int(row["top"]), int(row["right"]), int(row["bottom"]))): row["text"]
            for row in read_rows(path) if row.get("text")}


def place_name(place: CorrectionKey) -> str:
    return "-".join(str(part) for part in (place[0], *place[1]))


def pattern_of(ours: str, ocr: str) -> str:
    changes = differences(comparable_text(ocr), comparable_text(ours))
    return " · ".join(f"{ocr_part or '∅'}→{ours_part or '∅'}" for ocr_part, ours_part in changes) or NO_PATTERN


def ranked(disagreements: Sequence[tuple[WordKey, str, str]], boxes: Mapping[WordKey, Box], top: int) -> list[tuple[Disagreement, int]]:
    by_pattern: dict[str, list[Disagreement]] = defaultdict(list)
    for key, ours, ocr in sorted(disagreements):
        pattern = pattern_of(ours, ocr)
        by_pattern[pattern].append(Disagreement(key, boxes[key], ours, ocr, pattern))
    patterns = sorted(by_pattern, key=lambda pattern: (pattern == NO_PATTERN, -len(by_pattern[pattern]), pattern))
    chosen = [(word, len(by_pattern[pattern])) for pattern in patterns for word in by_pattern[pattern][:PER_PATTERN]]
    return chosen[:top]


def _row(word: Disagreement, count: int, crops: str) -> str:
    ours, ocr = json.dumps(word.ours, ensure_ascii=False), json.dumps(word.ocr, ensure_ascii=False)
    name = place_name(word.place)
    return (f"<tr data-key={name}><td>p{word.key[0]} l{word.key[1]} w{word.key[2]}</td>"
            f"<td class=p>{html.escape(word.pattern)}<br><span class=g>{count} words</span></td>"
            f"<td><img class=word src='{crops}/{name}.png'></td>"
            f"<td class=p><button onclick='fill(this,{html.escape(ours, quote=True)})'>ours</button> {html.escape(word.ours)}<br>"
            f"<button onclick='fill(this,{html.escape(ocr, quote=True)})'>OCR</button> {html.escape(word.ocr)}</td>"
            "<td><input></td></tr>")


def write_disagreements(path: Path, rows: Sequence[tuple[Disagreement, int]], earlier: Mapping[CorrectionKey, str], crops: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    style = STYLE + "img.word{height:56px}.p,input{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}input{width:16em}"
    intro = (f"<p>{len(rows)} words where our reading and the OCR reading differ, grouped by what differs (OCR→ours). "
             "Click <b>ours</b> or <b>OCR</b> when one is right, or type the word as printed. Words left empty are not saved. "
             "<button onclick='downloadCorrections()'>Download corrections.tsv</button></p>")
    earlier_json = json.dumps({place_name(place): text for place, text in sorted(earlier.items())}, ensure_ascii=False)
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Scan disagreements</title><style>{style}</style>{intro}"
        f"<table><tr><th>word<th>OCR→ours<th>print<th>readings<th>correct text</tr>"
        f"{''.join(_row(word, count, crops) for word, count in rows)}</table>"
        f"<script>const EARLIER={earlier_json};const HEADER={json.dumps(chr(9).join(COLUMNS))};{CORRECTION_SCRIPT}</script>",
        encoding="utf-8", newline="\n",
    )
