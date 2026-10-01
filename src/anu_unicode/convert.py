from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pymupdf

from anu_unicode.glyphs import Glyph, page_lines
from anu_unicode.profile import DEFAULT_PROFILE, FontProfile
from anu_unicode.telugu import normalise

UNMAPPED_OPEN = "⟦"
UNMAPPED_CLOSE = "⟧"

Segment = tuple[str, str | None]


@dataclass
class Coverage:
    glyphs: int = 0
    unmapped: Counter[str] = field(default_factory=Counter)

    @property
    def ratio(self) -> float:
        unmapped_glyphs = sum(len(glyphs) * count for glyphs, count in self.unmapped.items())
        return 1 - unmapped_glyphs / self.glyphs if self.glyphs else 1.0


def _longest_key(text: str, position: int, mapping: Mapping[str, str], longest: int) -> str | None:
    for end in range(min(len(text), position + longest), position, -1):
        if text[position:end] in mapping:
            return text[position:end]
    return None


def convert_segments(text: str, mapping: Mapping[str, str]) -> list[Segment]:
    table = {**mapping, " ": " "}
    longest = max(map(len, table))
    segments: list[Segment] = []
    position = 0
    while position < len(text):
        key = _longest_key(text, position, table, longest)
        if key is not None:
            segments.append((key, table[key]))
            position += len(key)
        elif segments and segments[-1][1] is None:
            segments[-1] = (segments[-1][0] + text[position], None)
            position += 1
        else:
            segments.append((text[position], None))
            position += 1
    return segments


def gaps(segments: Sequence[Segment]) -> list[str]:
    return [glyphs for glyphs, unicode in segments if unicode is None]


def render(segments: Sequence[Segment], coverage: Coverage) -> str:
    coverage.glyphs += sum(len(glyphs) for glyphs, _ in segments if glyphs != " ")
    coverage.unmapped.update(gaps(segments))
    return normalise("".join(UNMAPPED_OPEN + glyphs + UNMAPPED_CLOSE if unicode is None else unicode for glyphs, unicode in segments))


def convert_anu(text: str, mapping: Mapping[str, str], coverage: Coverage) -> str:
    return render(convert_segments(text, mapping), coverage)


def convert_line(line: list[Glyph], mapping: Mapping[str, str], coverage: Coverage) -> str:
    output: list[str] = []
    start = 0
    for end in range(1, len(line) + 1):
        if end == len(line) or line[end].is_anu != line[start].is_anu:
            text = "".join(glyph.char for glyph in line[start:end])
            output.append(convert_anu(text, mapping, coverage) if line[start].is_anu else text)
            start = end
    return "".join(output)


def convert_page(page: pymupdf.Page, mapping: Mapping[str, str], coverage: Coverage, profile: FontProfile = DEFAULT_PROFILE) -> str:
    return "\n".join(convert_line(line, mapping, coverage) for line in page_lines(page, profile))
