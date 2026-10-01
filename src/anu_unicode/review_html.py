import base64
import html
from collections.abc import Iterable, Sequence

import pymupdf

from anu_unicode.glyphs import Rect

STYLE = (
    "body{font-family:sans-serif;margin:16px}td,th{border-bottom:1px solid #ddd;padding:4px;text-align:left;vertical-align:middle}"
    ".u,input.c{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}.g{font-family:monospace}input.c{width:14em}"
    "#export{position:sticky;top:0;background:#fffbe6;border:1px solid #e6d58c;padding:8px;margin-bottom:12px}"
    "textarea{width:100%;height:8em;font-family:'Noto Sans Telugu','Nirmala UI'}"
)


def crop(document: pymupdf.Document, page_number: int, bbox: Rect) -> str:
    clip = pymupdf.Rect(bbox) + (-3, -3, 3, 3)
    png = document[page_number - 1].get_pixmap(dpi=150, clip=clip).tobytes("png")
    return f"<img src='data:image/png;base64,{base64.b64encode(png).decode('ascii')}'>"


def table(title: str, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<h2>{title}</h2><table><tr>{''.join(f'<th>{header}' for header in headers)}</tr>{body}</table>"


def glyphs_cell(text: str) -> str:
    return f"<span class=g>{html.escape(text)}</span>"


def telugu_cell(text: str) -> str:
    return f"<span class=u>{html.escape(text)}</span>"
