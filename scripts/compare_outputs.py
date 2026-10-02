import argparse
import difflib
import logging
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import pymupdf

from anu_unicode.cli import ExtraFormatter
from anu_unicode.command_support import page_range
from anu_unicode.convert import Coverage, convert_page
from anu_unicode.layout import BookLayout
from anu_unicode.mapping import load_mapping, write_rows
from anu_unicode.profile import DEFAULT_PROFILE, load_profile
from anu_unicode.quality import error_rate
from anu_unicode.telugu import comparable

logger = logging.getLogger(__name__)
PAGE_COLUMNS = ("page", "saved_words", "word_error_rate", "character_error_rate")
CHANGE_COLUMNS = ("count", "saved", "converted")


def saved_pages(directories: Sequence[Path]) -> dict[int, Path]:
    pages: dict[int, Path] = {}
    for directory in directories:
        for path in directory.glob("page-*.unicode.txt"):
            pages.setdefault(int(path.name.split("-")[1].split(".")[0]), path)
    return pages


def word_changes(saved: list[str], converted: list[str]) -> list[tuple[str, str]]:
    matcher = difflib.SequenceMatcher(None, saved, converted, autojunk=False)
    return [(" ".join(saved[a1:a2]), " ".join(converted[b1:b2])) for op, a1, a2, b1, b2 in matcher.get_opcodes() if op != "equal"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff a mapping's conversion against page texts saved by an earlier run")
    parser.add_argument("--book", required=True, help="book folder under files/, e.g. mahabharatamu")
    parser.add_argument("--mapping", type=Path, default=Path("fonts/anu/ocr-learning/mapping.tsv"))
    parser.add_argument("--profile", type=Path, default=Path("fonts/anu/profile.json"))
    parser.add_argument("--against", type=Path, nargs="+", required=True, help="directories holding page-N.unicode.txt files")
    parser.add_argument("--pages", type=page_range, help="1-based, e.g. 6-10; default every saved page")
    parser.add_argument("--exact", action="store_true", help="count ZWNJ and quote style as differences")
    arguments = parser.parse_args()
    handler = logging.StreamHandler()
    handler.setFormatter(ExtraFormatter("%(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    layout = BookLayout(arguments.book)
    arguments.out = layout.intermediate("compare-outputs")
    document = pymupdf.open(layout.input_pdf())
    mapping = load_mapping(arguments.mapping)
    profile = load_profile(arguments.profile) if arguments.profile.exists() else DEFAULT_PROFILE
    saved = saved_pages(arguments.against)
    numbers = [number for number in (arguments.pages or sorted(saved)) if number in saved]
    normalise = (lambda text: text) if arguments.exact else comparable
    page_rows: list[tuple[object, ...]] = []
    changes: Counter[tuple[str, str]] = Counter()
    for number in numbers:
        before = normalise(saved[number].read_text(encoding="utf-8")).split()
        after = normalise(convert_page(document[number - 1], mapping, Coverage(), profile)).split()
        character_rate = error_rate(list("".join(before)), list("".join(after)))
        page_rows.append((number, len(before), f"{error_rate(before, after):.4f}", f"{character_rate:.4f}"))
        changes.update(word_changes(before, after))
    arguments.out.mkdir(parents=True, exist_ok=True)
    write_rows(arguments.out / "pages.tsv", PAGE_COLUMNS, page_rows)
    write_rows(arguments.out / "changes.tsv", CHANGE_COLUMNS, ((count, old, new) for (old, new), count in changes.most_common()))
    logger.info("outputs compared", extra={"pages": len(numbers), "changed_words": sum(changes.values()), "out": str(arguments.out)})


if __name__ == "__main__":
    main()
