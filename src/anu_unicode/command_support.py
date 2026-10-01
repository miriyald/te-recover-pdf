import argparse
from pathlib import Path

import pymupdf

MATCH_OVERLAP = 0.3


def page_range(text: str) -> list[int]:
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def requested_pages(arguments: argparse.Namespace, document: pymupdf.Document) -> list[int]:
    pages: list[int] = arguments.pages or list(range(1, document.page_count + 1))
    return pages


def cached_pages(ocr_cache: Path) -> set[int]:
    return {int(path.stem.split("-")[1]) for path in ocr_cache.glob("page-*.json")}
