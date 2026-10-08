import html
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from anu_unicode.mapping import read_rows
from anu_unicode.scan.checks import Recheck
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import Label
from anu_unicode.scan.names import Speller
from anu_unicode.scan.recipes import RecipeProposal
from anu_unicode.scan.word_ocr import WordKey, words_of
from anu_unicode.shape_naming.atlas import STYLE
from anu_unicode.shape_naming.shapes import NOTHING, Recipe

FLAG_AGREEMENT = 0.6
EXAMPLES = 3

REVIEW_SCRIPT = """
function save(name,text){const link=document.createElement('a');
  link.href=URL.createObjectURL(new Blob([text],{type:'text/tab-separated-values'}));link.download=name;link.click();}
function downloadDecisions(){const decided=Object.assign({},EARLIER);
  document.querySelectorAll('tr[data-id]').forEach(row=>{
    const value=row.querySelector('input').value.trim();if(value){decided[row.dataset.id]=value;}});
  save('decisions.tsv','shape_id\\tname\\n'+Object.keys(decided).sort((a,b)=>a-b).map(id=>id+'\\t'+decided[id]).join('\\n')+'\\n');}
function downloadRecipes(){const recipes=RECIPES.slice();
  document.querySelectorAll('tr[data-names]').forEach(row=>{if(row.querySelector('input').checked){recipes.push([row.dataset.names,row.dataset.unicode,'proposed']);}});
  save('recipes.tsv','names\\tunicode\\tnote\\n'+recipes.map(([names,unicode,note])=>names+'\\t'+unicode+'\\t'+note).join('\\n')+'\\n');}
"""

Example = tuple[str, str]


@dataclass(frozen=True)
class ReviewInput:
    occurrences: Sequence[Occurrence]
    labels: Mapping[int, Label]
    decisions: Mapping[int, str] = field(default_factory=dict)
    marks: frozenset[int] = frozenset()
    texts: Mapping[WordKey, str] = field(default_factory=dict)
    pages: frozenset[int] = frozenset()
    speller: Speller = field(default_factory=lambda: Speller([]))


@dataclass(frozen=True)
class ReviewRow:
    shape_id: int
    count: int
    label: Label | None
    flagged: bool
    examples: tuple[Example, ...]
    completes: int = 0


@dataclass(frozen=True)
class Sheet:
    rows: Sequence[ReviewRow]
    rechecks: Sequence[Recheck] = ()
    proposals: Sequence[RecipeProposal] = ()
    decisions: Mapping[int, str] = field(default_factory=dict)
    recipes: Sequence[Recipe] = ()


def read_decisions(path: Path) -> dict[int, str]:
    return {int(row["shape_id"]): row["name"] for row in read_rows(path)}


def _flagged(shape_id: int, label: Label | None, marks: frozenset[int]) -> bool:
    if label is None:
        return True
    return (label.name == NOTHING and shape_id not in marks) or label.agreement < FLAG_AGREEMENT


def _examples(source: ReviewInput, wanted: set[int]) -> dict[int, list[Example]]:
    names = {shape_id: label.name for shape_id, label in source.labels.items()}
    examples: dict[int, list[Example]] = defaultdict(list)
    for key, items in words_of(source.occurrences).items():
        text = source.texts.get(key, "")
        if not text:
            continue
        shape_ids = [item.shape_id for item in items]
        for shape_id in wanted.intersection(shape_ids):
            if len(examples[shape_id]) < EXAMPLES and text not in (ocr for _, ocr in examples[shape_id]):
                examples[shape_id].append((source.speller.spell(shape_ids, names), text))
    return examples


def _greedy(pickable: set[int], open_ids: set[int], words: list[set[int]], order: Callable[[int], tuple[bool, int, int]],
            top: int) -> list[tuple[int, int]]:
    remaining = [word & open_ids for word in words]
    chosen: list[tuple[int, int]] = []
    left = set(pickable)
    while left and len(chosen) < top:
        gains = Counter(next(iter(missing)) for missing in remaining if len(missing) == 1)
        pick = min(left, key=lambda shape_id: (-gains[shape_id], *order(shape_id)))
        chosen.append((pick, gains[pick]))
        left.discard(pick)
        remaining = [missing - {pick} for missing in remaining]
    return chosen


def review_rows(source: ReviewInput, top: int) -> list[ReviewRow]:
    counts = Counter(item.shape_id for item in source.occurrences if item.shape_id != EQUALS)
    on_pages = {item.shape_id for item in source.occurrences if item.shape_id != EQUALS and (not source.pages or item.page in source.pages)}
    candidates = {shape_id for shape_id in on_pages if shape_id not in source.decisions}

    def flagged(shape_id: int) -> bool:
        return _flagged(shape_id, source.labels.get(shape_id), source.marks)

    def order(shape_id: int) -> tuple[bool, int, int]:
        return not flagged(shape_id), -counts[shape_id], shape_id

    unsettled = {shape_id for shape_id in counts if shape_id not in source.decisions and flagged(shape_id)}
    words = [{item.shape_id for item in items if item.shape_id != EQUALS} for items in words_of(source.occurrences).values()]
    picks = _greedy(candidates & unsettled, unsettled, words, order, top)
    ranked = (picks + [(shape_id, 0) for shape_id in sorted(candidates - unsettled, key=order)])[:top]
    examples = _examples(source, {shape_id for shape_id, _ in ranked})
    return [ReviewRow(shape_id, counts[shape_id], source.labels.get(shape_id), flagged(shape_id), tuple(examples[shape_id]), gain)
            for shape_id, gain in ranked]


def _words(examples: Sequence[Example]) -> str:
    return "<br>".join(f"{html.escape(ours)} <span class=g>· OCR {html.escape(ocr)}</span>" for ours, ocr in examples)


def _row(row: ReviewRow, strips: str) -> str:
    label = row.label
    value = html.escape(label.name if label else "", quote=True)
    evidence = f"{label.source} · {label.support} words · {label.agreement:.0%}" if label else "unlabelled"
    flag = " class=flag" if row.flagged else ""
    completes = f" · +{row.completes} with rows above" if row.completes else ""
    return (f"<tr data-id={row.shape_id}{flag}><td>#{row.shape_id}</td><td>{row.count}{completes}</td>"
            f"<td><img class=strip src='{strips}/{row.shape_id}.png'></td><td><input value=\"{value}\"></td>"
            f"<td>{evidence}</td><td class=p>{_words(row.examples)}</td></tr>")


def _recheck(recheck: Recheck, strips: str) -> str:
    return (f"<tr data-id={recheck.shape_id} class=flag><td>#{recheck.shape_id}</td><td>{recheck.words}</td>"
            f"<td><img class=strip src='{strips}/{recheck.shape_id}.png'></td>"
            f"<td><input value=\"{html.escape(recheck.name, quote=True)}\"></td><td>{recheck.agreement:.0%} agree</td>"
            f"<td class=p>OCR→ours {html.escape(recheck.pattern)} in {recheck.pattern_words} words</td></tr>")


def _proposal(proposal: RecipeProposal) -> str:
    names = html.escape(" ".join(proposal.names), quote=True)
    return (f"<tr data-names=\"{names}\" data-unicode=\"{html.escape(proposal.unicode, quote=True)}\">"
            f"<td><input type=checkbox></td><td class=p>{names} → {html.escape(proposal.unicode)}</td>"
            f"<td>{proposal.votes} words · {proposal.share:.0%}</td></tr>")


def write_review(path: Path, sheet: Sheet, strips: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flagged = sum(row.flagged for row in sheet.rows)
    style = (STYLE + "img.strip{height:40px}.p,input{font-family:'Noto Sans Telugu','Nirmala UI';font-size:20px}"
             "tr.flag td{background:#fff3e0}")
    intro = (f"<p>{len(sheet.rows)} shape ids, {flagged} flagged (shaded). Type the Unicode a piece stands for, "
             f"<code>{NOTHING}</code> if it adds nothing, or a name such as <code>o_tick</code> when it only means something with "
             "its neighbour (a recipe then gives the result). Every value left on the sheet is saved as a decision. "
             "<button onclick='downloadDecisions()'>Download decisions.tsv</button> "
             "<button onclick='downloadRecipes()'>Download recipes.tsv</button></p>")
    header = "<tr><th>id<th>count<th>prototype · members<th>name<th>evidence<th>"
    rechecks = "".join(_recheck(recheck, strips) for recheck in sheet.rechecks)
    proposals = "".join(_proposal(proposal) for proposal in sheet.proposals)
    earlier = json.dumps({str(shape_id): name for shape_id, name in sorted(sheet.decisions.items())}, ensure_ascii=False)
    recipes = json.dumps([[" ".join(recipe.names), recipe.unicode, recipe.note] for recipe in sheet.recipes], ensure_ascii=False)
    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Scan review</title><style>{style}</style>{intro}"
        f"<h3>Decisions to recheck ({len(sheet.rechecks)})</h3><table>{header}what OCR keeps reading</tr>{rechecks}</table>"
        f"<h3>Recipe proposals ({len(sheet.proposals)}): tick to keep</h3><table>{proposals}</table>"
        f"<h3>Shape ids</h3><table>{header}in words: ours · OCR</tr>{''.join(_row(row, strips) for row in sheet.rows)}</table>"
        f"<script>const EARLIER={earlier};const RECIPES={recipes};{REVIEW_SCRIPT}</script>",
        encoding="utf-8", newline="\n",
    )
