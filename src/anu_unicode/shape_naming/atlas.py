import base64
import html
import io
import logging
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import ImageOps

from anu_unicode.glyphs import ZERO_WIDTH, Word, font_family, page_lines, split_words
from anu_unicode.profile import FontProfile
from anu_unicode.shape_naming.shapes import Shape

GLYPH_SIZE = 44
WORD_SIZE = 30
PADDING = 8
RENDER_DPI = 144
EXAMPLES = 2

logger = logging.getLogger(__name__)

STYLE = (
    "body{font-family:sans-serif;margin:16px}td,th{border-bottom:1px solid #ddd;padding:4px;text-align:left;vertical-align:middle}"
    "input.c{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px;width:6em}input.n{font-family:monospace;width:10em}"
    ".g{font-family:monospace;font-size:12px}td div{display:inline-block;margin-right:6px}"
    "#export{position:sticky;top:0;background:#fffbe6;border:1px solid #e6d58c;padding:8px;margin-bottom:12px}"
    "textarea{width:100%;height:6em;font-family:'Noto Sans Telugu','Nirmala UI'}"
)
SCRIPT = """
function names(){const rows=[...document.querySelectorAll('tr[data-glyph]')]
  .map(r=>[r.dataset.glyph,r.querySelector('input.n').value.trim(),r.querySelector('input.c').value.trim()])
  .filter(cells=>cells[1]).map(cells=>cells.join('\\t'));
  return ['glyph\\tname\\tunicode',...rows].join('\\n')+'\\n';}
function refresh(){document.getElementById('tsv').value=names();}
function download(){const blob=new Blob([names()],{type:'text/tab-separated-values'});
  const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='names.tsv';link.click();}
document.addEventListener('input',refresh);
document.addEventListener('DOMContentLoaded',refresh);
"""


@dataclass(frozen=True)
class GlyphStats:
    glyph: str
    count: int
    zero_width: bool
    units: tuple[str, ...]
    words: tuple[str, ...]


def _top(counter: Counter[str]) -> tuple[str, ...]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], len(item[0])))
    return tuple(text for text, _ in ranked[:EXAMPLES])


def glyph_stats(words: Iterable[Word]) -> list[GlyphStats]:
    counts: Counter[str] = Counter()
    zero_width: Counter[str] = Counter()
    units: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, Counter[str]] = defaultdict(Counter)
    for word in words:
        for glyph in word.glyphs:
            counts[glyph.char] += 1
            zero_width[glyph.char] += glyph.width < ZERO_WIDTH
        for unit in word.units:
            for char in set(unit) if len(unit) > 1 else ():
                units[char][unit] += 1
        for char in set(word.text):
            examples[char][word.text] += 1
    return [
        GlyphStats(glyph, count, 2 * zero_width[glyph] > count, _top(units[glyph]), _top(examples[glyph]))
        for glyph, count in counts.most_common()
    ]


def collect_glyphs(document: pymupdf.Document, profile: FontProfile) -> list[GlyphStats]:
    return glyph_stats(word for page in document for line in page_lines(page, profile) for word in split_words(line))


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
        page = scratch.new_page(width=font.text_length(text, fontsize=size) + 2 * size, height=size * 2)
        writer = pymupdf.TextWriter(page.rect)
        writer.append((size, size * 1.4), text, font=font, fontsize=size)
        writer.write_text(page)
        image = page.get_pixmap(dpi=RENDER_DPI, alpha=False).pil_image()
    ink = ImageOps.invert(image.convert("L")).getbbox()
    if ink:
        image = image.crop((max(0, ink[0] - PADDING), 0, min(image.width, ink[2] + PADDING), image.height))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image(fonts: Sequence[pymupdf.Font], text: str, size: float) -> str:
    data = render_png(fonts, text, size)
    return f"<img src='data:image/png;base64,{base64.b64encode(data).decode('ascii')}'>" if data else "<i>not in font</i>"


def _input(css_class: str, value: str) -> str:
    return f"<input class={css_class} value=\"{html.escape(value, quote=True)}\">"


def _row(stats: GlyphStats, fonts: Sequence[pymupdf.Font], shape: Shape | None) -> str:
    units = "".join(f"<div>{_image(fonts, unit, WORD_SIZE)}</div>" for unit in stats.units)
    words = "".join(f"<div>{_image(fonts, text, WORD_SIZE)}</div>" for text in stats.words)
    return (
        f"<tr data-glyph=\"{html.escape(stats.glyph, quote=True)}\"><td>{_image(fonts, stats.glyph, GLYPH_SIZE)}</td>"
        f"<td class=g>U+{ord(stats.glyph):04X}</td><td>{stats.count}</td><td>{'mark' if stats.zero_width else ''}</td>"
        f"<td>{_input('n', shape.name if shape else '')}</td><td>{_input('c', shape.unicode if shape else '')}</td>"
        f"<td>{units}</td><td>{words}</td></tr>"
    )


def write_atlas(path: Path, stats: Sequence[GlyphStats], shapes: Mapping[str, Shape], fonts: Sequence[pymupdf.Font]) -> None:
    rows = "".join(_row(item, fonts, shapes.get(item.glyph)) for item in stats)
    named = sum(item.glyph in shapes for item in stats)
    export = (
        "<div id=export><b>Shape names</b>: name each glyph by its shape (e.g. <code>va_base</code>, <code>u_hook</code>) "
        "and type the Unicode it contributes on its own; leave Unicode empty if it means nothing alone. "
        "<button onclick='download()'>Download names.tsv</button> saves every named row.<textarea id=tsv readonly></textarea></div>"
    )
    summary = f"<p>{len(stats)} glyph codes in {sum(item.count for item in stats)} occurrences, {named} named.</p>"
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Glyph atlas</title><style>{STYLE}</style>{export}{summary}"
        f"<table><tr><th>glyph<th>code<th>count<th>kind<th>name<th>Unicode<th>in units<th>in words</tr>{rows}</table>"
        f"<script>{SCRIPT}</script>",
        encoding="utf-8", newline="\n",
    )
    logger.info("atlas written", extra={"glyphs": len(stats), "named": named, "path": str(path)})
