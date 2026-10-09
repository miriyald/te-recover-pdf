import html
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import astuple, dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path

from anu_unicode.mapping import write_rows
from anu_unicode.scan.conversion import PLACEHOLDER, Choice, ScanText, Written
from anu_unicode.scan.inference import comparable_text
from anu_unicode.scan.word_ocr import WordKey

FALLBACKS = frozenset({Choice.WORD_OCR, Choice.GAP})
LETTERS = ("ఀ", "ౣ")


class Cause(StrEnum):
    GROUPING = "grouping"
    MISSING = "missing"
    EXTRA = "extra"
    UNLABELLED = "unlabelled"
    OCR_OVERRULED = "ocr overruled"
    WRONG_LABEL = "wrong label"


@dataclass(frozen=True)
class Miss:
    page: int
    gold: tuple[str, ...]
    ours: tuple[str, ...]
    ocr: tuple[str, ...]
    keys: tuple[WordKey, ...]
    cause: Cause


@dataclass(frozen=True)
class Score:
    total: int
    ours: int
    ocr: int


@dataclass(frozen=True)
class Errors:
    letters: int
    ours: int
    ocr: int


@dataclass(frozen=True)
class PageScore:
    page: int
    words: Score
    letter_words: Score
    letter_errors: Errors
    misses: tuple[Miss, ...]


def tokens(text: str) -> list[str]:
    return [token for token in (comparable_text(word) for word in text.split()) if token]


def letters(word: str) -> str:
    return "".join(char for char in comparable_text(word) if LETTERS[0] <= char <= LETTERS[1])


def letter_tokens(text: str) -> list[str]:
    return [token for token in (letters(word) for word in text.split()) if token]


def _scored(text: str) -> list[str]:
    return letter_tokens(text) or ([PLACEHOLDER] if PLACEHOLDER in text else [])


def _exact(gold: list[str], found: list[str]) -> int:
    return sum(block.size for block in SequenceMatcher(a=gold, b=found, autojunk=False).get_matching_blocks())


def edits(first: str, second: str) -> int:
    row = list(range(len(second) + 1))
    for index, char in enumerate(first, 1):
        previous, row[0] = row[0], index
        for column, other in enumerate(second, 1):
            previous, row[column] = row[column], min(row[column] + 1, row[column - 1] + 1, previous + (char != other))
    return row[-1]


def _cause(gold: int, found: int, involved: list[Written], overruled: set[WordKey]) -> Cause:
    if not found:
        return Cause.MISSING
    if not gold:
        return Cause.EXTRA
    if gold != found:
        return Cause.GROUPING
    fallbacks = [(key, choice) for word in involved for key, choice in zip(word.keys, word.choices) if choice in FALLBACKS]
    if any(key not in overruled for key, _ in fallbacks):
        return Cause.UNLABELLED
    return Cause.OCR_OVERRULED if fallbacks else Cause.WRONG_LABEL


def _misses(page: int, gold: list[str], ours: list[tuple[str, Written]], converted: ScanText,
            ocr_words: Mapping[WordKey, str]) -> tuple[Miss, ...]:
    overruled = {key for key, _, _ in converted.disagreements}
    misses = []
    for tag, first, last, start, end in SequenceMatcher(a=gold, b=[token for token, _ in ours], autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        involved = list({id(word): word for _, word in ours[start:end]}.values())
        keys = tuple(key for word in involved for key in word.keys)
        misses.append(Miss(page, tuple(gold[first:last]), tuple(token for token, _ in ours[start:end]),
                           tuple(ocr_words.get(key, "") for key in keys), keys, _cause(last - first, end - start, involved, overruled)))
    return tuple(misses)


def score_page(page: int, gold_text: str, converted: ScanText, ocr_text: str, ocr_words: Mapping[WordKey, str]) -> PageScore:
    written = [word for line in converted.written for word in line]
    gold, gold_letters = tokens(gold_text), letter_tokens(gold_text)
    ours = [(token, word) for word in written for token in _scored(word.text)]
    ours_letters, ocr_letters = [token for token, _ in ours if token != PLACEHOLDER], letter_tokens(ocr_text)
    words = Score(len(gold), _exact(gold, [token for word in written for token in tokens(word.text)]), _exact(gold, tokens(ocr_text)))
    letter_words = Score(len(gold_letters), _exact(gold_letters, ours_letters), _exact(gold_letters, ocr_letters))
    joined = "".join(gold_letters)
    letter_errors = Errors(len(joined), edits(joined, "".join(ours_letters)), edits(joined, "".join(ocr_letters)))
    return PageScore(page, words, letter_words, letter_errors, _misses(page, gold_letters, ours, converted, ocr_words))


COLUMNS = ("page", "gold_words", "ours_exact", "ocr_exact", "letter_words", "ours_letter_exact", "ocr_letter_exact",
           "letters", "ours_letter_errors", "ocr_letter_errors")


def write_scores(path: Path, scores: Sequence[PageScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [(score.page, *astuple(score.words), *astuple(score.letter_words), *astuple(score.letter_errors),
             *(sum(miss.cause is cause for miss in score.misses) for cause in Cause)) for score in scores]
    write_rows(path, (*COLUMNS, *(cause.value.replace(" ", "_") for cause in Cause)), rows)


STYLE = """
:root{--bg:#fbfaf7;--fg:#22201c;--muted:#6b665d;--line:#e2ddd2;--gold:#1f6b3a;--ocr:#8a4b12}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1b1a17;--fg:#ece8df;--muted:#a39d91;--line:#34312b;
--gold:#7fd39b;--ocr:#e3a568;color-scheme:dark}}
:root[data-theme=dark]{--bg:#1b1a17;--fg:#ece8df;--muted:#a39d91;--line:#34312b;--gold:#7fd39b;--ocr:#e3a568;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,'Noto Sans Telugu',sans-serif;
padding:24px 16px;max-width:1200px;margin:auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 4px}p{color:var(--muted);margin:0 0 12px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:middle;font-size:18px}
th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.n,.c{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
img{max-width:420px;background:#fff;border:1px solid var(--line)}.g{color:var(--gold)}.t{color:var(--ocr)}
"""


def _row(number: int, miss: Miss, crop: str | None) -> str:
    image = f"<img src='data:image/png;base64,{crop}'>" if crop else ""
    return (f"<tr><td class=n>{number}</td><td>{image}</td><td class=g>{html.escape(' '.join(miss.gold))}</td>"
            f"<td>{html.escape(' '.join(miss.ours))}</td><td class=t>{html.escape(' '.join(miss.ocr))}</td>"
            f"<td class=c>{miss.cause.value}</td></tr>")


def write_misses(path: Path, scores: Sequence[PageScore], crop: Callable[[Miss], str | None]) -> None:
    sections = []
    for score in scores:
        causes = Counter(miss.cause.value for miss in score.misses)
        rows = "".join(_row(number, miss, crop(miss)) for number, miss in enumerate(score.misses, 1))
        words, errors = score.letter_words, score.letter_errors
        sections.append(f"<h2>Page {score.page}</h2><p>letter words {words.ours}/{words.total} in our output, {words.ocr} in OCR alone · "
                        f"letter errors {errors.ours / max(errors.letters, 1):.1%} ours, {errors.ocr / max(errors.letters, 1):.1%} OCR · "
                        f"{', '.join(f'{cause} {count}' for cause, count in causes.most_common())}</p>"
                        "<div class=wrap><table><tr><th>#</th><th>Scan</th><th>Correct text</th><th>Our output</th>"
                        f"<th>OCR alone</th><th>Cause</th></tr>{rows}</table></div>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                    f"<title>Scan misses</title><style>{STYLE}</style><h1>Where our output differs from the correct text</h1>"
                    + "".join(sections), encoding="utf-8")
