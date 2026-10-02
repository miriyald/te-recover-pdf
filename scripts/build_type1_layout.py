import argparse
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment

from anu_unicode.cli import ExtraFormatter
from anu_unicode.layout import BookLayout
from anu_unicode.mapping import write_rows
from anu_unicode.profile import load_profile
from anu_unicode.shape_naming.shapes import load_shapes

logger = logging.getLogger(__name__)
FONT = Path("fonts/anu")
SIZE = 40
SURE_SCORE, SURE_MARGIN, DOUBTFUL_SCORE = 0.95, 0.04, 0.8
COLUMNS = ("char", "codepoint", "byte", "score", "margin", "status", "confirmed", "candidates")
ROWS_PER_SHEET = 12
ROW_HEIGHT = 70
CELL = 130

Bitmaps = dict[str, dict[int, np.ndarray]]


@dataclass(frozen=True)
class Match:
    char: str
    byte: int | None
    score: float
    margin: float
    status: str
    candidates: tuple[int, ...]


def family_of(font_name: str) -> str:
    return font_name.split("+")[-1].split(",")[0]


def glyph_bitmap(font: pymupdf.Font, char: str) -> np.ndarray | None:
    if not font.has_glyph(ord(char)):
        return None
    with pymupdf.open() as scratch:
        page = scratch.new_page(width=SIZE * 3, height=SIZE * 2)
        writer = pymupdf.TextWriter(page.rect)
        writer.append((SIZE, SIZE * 1.4), char, font=font, fontsize=SIZE)
        writer.write_text(page)
        pixels = np.frombuffer(page.get_pixmap(dpi=72, alpha=False, colorspace=pymupdf.csGRAY).samples, dtype=np.uint8)
    image = pixels.reshape(SIZE * 2, SIZE * 3) < 128
    return image if image.any() else None


def target_fonts(document: pymupdf.Document, anu_fonts: frozenset[str]) -> dict[str, pymupdf.Font]:
    found: dict[str, pymupdf.Font] = {}
    for page in document:
        for font in page.get_fonts(full=True):
            family = family_of(font[3])
            if family in anu_fonts and font[2] == "Type1" and family not in found:
                found[family] = pymupdf.Font(fontbuffer=document.extract_font(font[0])[3])
    return found


def reference_glyphs(slugs: list[str], families: frozenset[str]) -> Bitmaps:
    glyphs: Bitmaps = {family: {} for family in families}
    for slug in slugs:
        document = pymupdf.open(BookLayout(slug).input_pdf())
        seen: set[int] = set()
        for page in document:
            for font in page.get_fonts(full=True):
                family = family_of(font[3])
                if family not in families or font[2] != "Type0" or font[0] in seen:
                    continue
                seen.add(font[0])
                loaded = pymupdf.Font(fontbuffer=document.extract_font(font[0])[3])
                for code in loaded.valid_codepoints():
                    if 0xF020 <= code <= 0xF0FF and code - 0xF000 not in glyphs[family]:
                        image = glyph_bitmap(loaded, chr(code))
                        if image is not None:
                            glyphs[family][code - 0xF000] = image
        logger.info("reference read", extra={"book": slug, "bytes": {family: len(table) for family, table in glyphs.items()}})
    return glyphs


def iou(left: list[np.ndarray], right: list[np.ndarray]) -> np.ndarray:
    a = np.array([image.ravel() for image in left], dtype=np.float32)
    b = np.array([image.ravel() for image in right], dtype=np.float32)
    inter = a @ b.T
    return inter / np.maximum(a.sum(1)[:, None] + b.sum(1)[None, :] - inter, 1)


def score_matrix(targets: dict[str, dict[str, np.ndarray]], reference: Bitmaps, chars: list[str], bytes_: list[int]) -> np.ndarray:
    total = np.zeros((len(chars), len(bytes_)), dtype=np.float32)
    weight = np.zeros_like(total)
    for family in targets:
        rows = [i for i, char in enumerate(chars) if char in targets[family]]
        cols = [j for j, byte in enumerate(bytes_) if byte in reference[family]]
        if rows and cols:
            part = iou([targets[family][chars[i]] for i in rows], [reference[family][bytes_[j]] for j in cols])
            total[np.ix_(rows, cols)] += part
            weight[np.ix_(rows, cols)] += 1
    return total / np.maximum(weight, 1)


def classify(chars: list[str], bytes_: list[int], matrix: np.ndarray) -> list[Match]:
    rows, cols = linear_sum_assignment(-matrix)
    assigned = dict(zip(rows.tolist(), cols.tolist(), strict=True))
    matches = []
    for row, char in enumerate(chars):
        order = np.argsort(-matrix[row])
        candidates = tuple(bytes_[j] for j in order[:3])
        if row not in assigned:
            best = float(matrix[row, order[0]])
            matches.append(Match(char, candidates[0], best, 0.0, "duplicate" if best >= DOUBTFUL_SCORE else "doubtful", candidates))
            continue
        column = assigned[row]
        score = float(matrix[row, column])
        runner_up = float(matrix[row, next(j for j in order if j != column)])
        if order[0] != column or score < DOUBTFUL_SCORE:
            status = "doubtful"
        elif score >= SURE_SCORE and score - runner_up >= SURE_MARGIN:
            status = "sure"
        else:
            status = "likely"
        matches.append(Match(char, bytes_[column], score, score - runner_up, status, candidates))
    return matches


def type1_picture(font: pymupdf.Font, char: str) -> Image.Image:
    with pymupdf.open() as scratch:
        page = scratch.new_page(width=100, height=60)
        writer = pymupdf.TextWriter(page.rect)
        writer.append((30, 40), char, font=font, fontsize=36)
        writer.write_text(page)
        picture: Image.Image = page.get_pixmap(dpi=72, alpha=False).pil_image()
    return picture


def anu_picture(bitmap: np.ndarray) -> Image.Image:
    return Image.fromarray(np.where(bitmap, 0, 255).astype(np.uint8)).convert("RGB").crop((20, 20, 120, 80)).resize((100, 60))


def write_sheet(path: Path, matches: list[Match], fonts: dict[str, pymupdf.Font], reference: Bitmaps, names: dict[int, str]) -> None:
    label = ImageFont.load_default(14)
    image = Image.new("RGB", (CELL * 4 + 130, ROW_HEIGHT * len(matches)), "white")
    draw = ImageDraw.Draw(image)
    for row, match in enumerate(matches):
        top = row * ROW_HEIGHT
        draw.text((4, top + 6), f"{match.char!r} U+{ord(match.char):04X}", fill="black", font=label)
        draw.text((4, top + 26), f"{match.status} {match.score:.2f}/{match.margin:.2f}", fill="blue", font=label)
        family = next(f for f in fonts if fonts[f].has_glyph(ord(match.char)))
        image.paste(type1_picture(fonts[family], match.char), (130, top + 2))
        draw.text((130, top + 54), "this font", fill="red", font=label)
        for column, byte in enumerate(match.candidates, 1):
            source = next((f for f in reference if byte in reference[f]), None)
            if source is not None:
                image.paste(anu_picture(reference[source][byte]), (130 + column * CELL, top + 2))
            marker = "ASSIGNED " if byte == match.byte else ""
            draw.text((130 + column * CELL, top + 54), f"{marker}{byte:02X} {names.get(byte, '')}", fill="black", font=label)
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Match the glyphs of a Type1-layout book to the Anu glyph codes")
    parser.add_argument("--target", required=True, help="book folder whose Type1 fonts carry the new layout")
    parser.add_argument("--reference", nargs="+", required=True, help="book folders with symbol-coded Anu fonts")
    parser.add_argument("--out", type=Path, default=FONT / "type1-layout.tsv")
    parser.add_argument("--review", default="", help="characters to put on the review sheets, in order; default every glyph that is not sure")
    arguments = parser.parse_args()
    handler = logging.StreamHandler()
    handler.setFormatter(ExtraFormatter("%(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    layout = BookLayout(arguments.target)
    profile = load_profile(FONT / "profile.json")
    fonts = target_fonts(pymupdf.open(layout.input_pdf()), profile.anu_fonts)
    reference = reference_glyphs(arguments.reference, frozenset(fonts))
    fonts = {family: font for family, font in fonts.items() if reference[family]}
    targets = {family: {chr(code): image for code in font.valid_codepoints() if (image := glyph_bitmap(font, chr(code))) is not None}
               for family, font in fonts.items()}
    chars = sorted({char for table in targets.values() for char in table})
    bytes_ = sorted({byte for table in reference.values() for byte in table})
    matches = classify(chars, bytes_, score_matrix(targets, reference, chars, bytes_))
    write_rows(arguments.out, COLUMNS, (
        (m.char, f"{ord(m.char):04X}", "" if m.byte is None else f"{m.byte:02X}", f"{m.score:.3f}", f"{m.margin:.3f}", m.status, "", " ".join(f"{byte:02X}" for byte in m.candidates))
        for m in matches))
    logger.info("layout written", extra={"glyphs": len(matches), "statuses": dict(Counter(m.status for m in matches)), "path": str(arguments.out)})
    gold = {shape.glyph: shape.name for shape in load_shapes(FONT / "shape-naming" / "names.tsv")}
    names = {byte: gold.get(profile.byte_char(byte), "") for byte in bytes_}
    review = layout.intermediate("type1-layout")
    review.mkdir(parents=True, exist_ok=True)
    by_char = {m.char: m for m in matches}
    uncertain = [by_char[char] for char in arguments.review if char in by_char] if arguments.review else [m for m in matches if m.status != "sure"]
    for index, start in enumerate(range(0, len(uncertain), ROWS_PER_SHEET), 1):
        write_sheet(review / f"sheet-{index:02d}.png", uncertain[start:start + ROWS_PER_SHEET], fonts, reference, names)
    logger.info("review sheets written", extra={"uncertain": len(uncertain), "path": str(review)})


if __name__ == "__main__":
    main()
