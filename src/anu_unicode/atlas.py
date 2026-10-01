import base64
import html
import logging
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from anu_unicode.glyphs import font_family, page_lines, split_words
from anu_unicode.profile import FontProfile

UNIT_SIZE = 44
WORD_SIZE = 30
PADDING = 8
RENDER_DPI = 144
EXAMPLE_WORDS = 2

logger = logging.getLogger(__name__)

STYLE = (
    "body{font-family:sans-serif;margin:16px}td,th{border-bottom:1px solid #ddd;padding:4px;text-align:left;vertical-align:middle}"
    ".u,input.c{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}.g{font-family:monospace;font-size:12px}input.c{width:10em}"
    "#export{position:sticky;top:0;background:#fffbe6;border:1px solid #e6d58c;padding:8px;margin-bottom:12px}"
    "textarea{width:100%;height:6em;font-family:'Noto Sans Telugu','Nirmala UI'}"
)
SCRIPT = """
function labels(){return [...document.querySelectorAll('input.c')]
  .filter(i=>i.value.trim() && i.value.trim()!==i.dataset.original)
  .map(i=>i.dataset.glyphs+'\\t'+i.value.trim()).join('\\n');}
function refresh(){document.getElementById('tsv').value=labels();}
function download(){const blob=new Blob(['glyphs\\tunicode\\n'+labels()+'\\n'],{type:'text/tab-separated-values'});
  const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='labels.tsv';link.click();}
document.addEventListener('input',refresh);
"""


@dataclass(frozen=True)
class UnitStats:
    unit: str
    count: int
    examples: tuple[str, ...]


def collect_units(document: pymupdf.Document, profile: FontProfile) -> list[UnitStats]:
    counts: Counter[str] = Counter()
    words: dict[str, Counter[str]] = defaultdict(Counter)
    for page in document:
        for line in page_lines(page, profile):
            for word in split_words(line):
                for unit in set(word.units):
                    words[unit][word.text] += 1
                counts.update(word.units)
    return [UnitStats(unit, count, _examples(words[unit])) for unit, count in counts.most_common()]


def _examples(words: Counter[str]) -> tuple[str, ...]:
    ranked = sorted(words.items(), key=lambda item: (-item[1], len(item[0])))
    return tuple(text for text, _ in ranked[:EXAMPLE_WORDS])


def load_fonts(document: pymupdf.Document, profile: FontProfile) -> list[pymupdf.Font]:
    pages: Counter[int] = Counter()
    for page in document:
        for font in page.get_fonts():
            if font_family(font[3]) in profile.anu_fonts:
                pages[font[0]] += 1
    fonts = []
    for xref, _ in pages.most_common():
        buffer = document.extract_font(xref)[3]
        if buffer:
            fonts.append(pymupdf.Font(fontbuffer=buffer))
    return fonts


def render_png(fonts: Sequence[pymupdf.Font], text: str, size: float) -> bytes | None:
    font = next((candidate for candidate in fonts if all(candidate.has_glyph(ord(char)) for char in text)), None)
    if font is None:
        return None
    with pymupdf.open() as scratch:
        page = scratch.new_page(width=font.text_length(text, fontsize=size) + 2 * PADDING, height=size * 2)
        writer = pymupdf.TextWriter(page.rect)
        writer.append((PADDING, size * 1.4), text, font=font, fontsize=size)
        writer.write_text(page)
        data: bytes = page.get_pixmap(dpi=RENDER_DPI, alpha=False).tobytes("png")
    return data


def _image(fonts: Sequence[pymupdf.Font], text: str, size: float) -> str:
    data = render_png(fonts, text, size)
    return f"<img src='data:image/png;base64,{base64.b64encode(data).decode('ascii')}'>" if data else "<i>not in font</i>"


def _codepoints(text: str) -> str:
    return " ".join(f"U+{ord(char):04X}" for char in text)


def _row(stats: UnitStats, fonts: Sequence[pymupdf.Font], current: str) -> str:
    examples = "".join(f"<div>{_image(fonts, text, WORD_SIZE)}</div>" for text in stats.examples)
    attributes = f"data-glyphs=\"{html.escape(stats.unit, quote=True)}\" data-original=\"{html.escape(current, quote=True)}\""
    return (
        f"<tr><td>{_image(fonts, stats.unit, UNIT_SIZE)}</td><td class=g>{_codepoints(stats.unit)}</td><td>{stats.count}</td>"
        f"<td><input class=c {attributes} value=\"{html.escape(current, quote=True)}\"></td><td>{examples}</td></tr>"
    )


def write_atlas(path: Path, all_units: Sequence[UnitStats], mapping: Mapping[str, str], fonts: Sequence[pymupdf.Font], top: int) -> None:
    units = all_units[:top]
    total = sum(stats.count for stats in all_units)
    rows = "".join(_row(stats, fonts, mapping.get(stats.unit, "")) for stats in units)
    export = (
        "<div id=export><b>Labels</b>: type the Unicode for a unit (a letter, matra, or conjunct piece). "
        "Rows you change are listed below, and <button onclick='download()'>Download labels.tsv</button> saves them as a mapping file."
        "<textarea id=tsv readonly></textarea></div>"
    )
    shown = sum(stats.count for stats in units)
    summary = f"<p>{len(units)} of {len(all_units)} units shown, covering {shown} of {total} occurrences. Pre-filled = already mapped.</p>"
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Glyph atlas</title><style>{STYLE}</style>{export}{summary}"
        f"<table><tr><th>glyph<th>codes<th>count<th>Unicode<th>in words</tr>{rows}</table><script>{SCRIPT}</script>",
        encoding="utf-8", newline="\n",
    )
    logger.info("atlas written", extra={"units": len(units), "path": str(path)})
