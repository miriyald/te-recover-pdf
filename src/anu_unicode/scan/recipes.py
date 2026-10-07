from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from anu_unicode.mapping import write_rows
from anu_unicode.scan.inference import ACCEPT_SHARE, WordEvidence, candidates_for, comparable_text
from anu_unicode.scan.names import Speller, is_symbolic
from anu_unicode.shape_naming.shapes import Recipe

PROPOSAL_VOTES = 3

Pair = tuple[str, str]


@dataclass(frozen=True)
class RecipeProposal:
    names: Pair
    unicode: str
    votes: int
    share: float


def _fits(word: WordEvidence, names: Mapping[int, str], speller: Speller) -> list[tuple[Pair, str]]:
    fits: list[tuple[Pair, str]] = []
    for first, second in set(zip(word.shape_ids, word.shape_ids[1:])):
        pair = (names[first], names[second])
        if speller.covers(pair) or not any(map(is_symbolic, pair)):
            continue
        fits.extend((pair, unicode) for unicode in candidates_for(word.text)
                    if comparable_text(speller.spell(word.shape_ids, names, extra=[Recipe(pair, unicode)])) == word.text)
    return fits


def propose_recipes(words: Sequence[WordEvidence], names: Mapping[int, str], speller: Speller) -> list[RecipeProposal]:
    votes: dict[Pair, Counter[str]] = defaultdict(Counter)
    for word in words:
        if not word.text or not all(shape_id in names for shape_id in word.shape_ids):
            continue
        if not any(is_symbolic(names[shape_id]) for shape_id in word.shape_ids):
            continue
        if comparable_text(speller.spell(word.shape_ids, names)) == word.text:
            continue
        fits = _fits(word, names, speller)
        if len(fits) == 1:
            votes[fits[0][0]][fits[0][1]] += 1
    proposals = []
    for pair, tally in votes.items():
        unicode, count = tally.most_common(1)[0]
        share = count / sum(tally.values())
        if count >= PROPOSAL_VOTES and share >= ACCEPT_SHARE:
            proposals.append(RecipeProposal(pair, unicode, count, round(share, 3)))
    return sorted(proposals, key=lambda proposal: (-proposal.votes, proposal.names))


def write_proposals(path: Path, proposals: Sequence[RecipeProposal]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(path, ("names", "unicode", "votes", "share"),
               ((" ".join(proposal.names), proposal.unicode, proposal.votes, proposal.share) for proposal in proposals))
