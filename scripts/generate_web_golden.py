import json
from itertools import groupby
from pathlib import Path

import pymupdf

from anu_unicode.convert import Coverage, convert_line
from anu_unicode.glyphs import page_lines
from anu_unicode.mapping import load_mapping

PDF = Path("files/mahabharatamu/input/Mahabharatamu.pdf")
MAPPING = Path("fonts/anu/ocr-learning/mapping.tsv")
OUTPUT = Path("web/tests/golden.json")
PAGES = range(5, 12)
MAX_CASES = 120


def main() -> None:
    mapping = load_mapping(MAPPING)
    cases: list[dict[str, object]] = []
    with pymupdf.open(PDF) as document:
        for page_number in PAGES:
            for line in page_lines(document[page_number]):
                runs = [{"text": "".join(glyph.char for glyph in group), "isAnu": is_anu}
                        for is_anu, group in groupby(line, key=lambda glyph: glyph.is_anu)]
                expected = convert_line(line, mapping, Coverage())
                cases.append({"runs": runs, "expected": expected})
    cases = cases[:MAX_CASES]
    OUTPUT.write_text(json.dumps(cases, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
