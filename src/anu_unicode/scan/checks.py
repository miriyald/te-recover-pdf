from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from anu_unicode.convert import UNMAPPED_OPEN
from anu_unicode.mapping import write_rows
from anu_unicode.scan.inference import Label, Source, WordEvidence, comparable_text, differences, significant
from anu_unicode.scan.names import Speller

RECHECK_AGREEMENT = 0.6
RECHECK_WORDS = 5


@dataclass(frozen=True)
class Recheck:
    shape_id: int
    name: str
    words: int
    agreement: float
    pattern: str
    pattern_words: int


def check_decisions(words: Sequence[WordEvidence], labels: Mapping[int, Label], speller: Speller) -> list[Recheck]:
    names = {shape_id: label.name for shape_id, label in labels.items()}
    rechecks = []
    for shape_id, label in sorted(labels.items()):
        if label.source is not Source.REVIEW:
            continue
        spelled = [(word.text, speller.spell(word.shape_ids, names)) for word in words if shape_id in word.shape_ids]
        complete = [(ocr, ours) for ocr, ours in spelled if UNMAPPED_OPEN not in ours]
        if len(complete) < RECHECK_WORDS:
            continue
        patterns = Counter(" ".join(f"{before}→{after}" for before, after in changes) for changes in
                           (significant(differences(ocr, comparable_text(ours))) for ocr, ours in complete) if changes)
        agreement = 1 - sum(patterns.values()) / len(complete)
        if patterns and agreement < RECHECK_AGREEMENT:
            pattern, count = patterns.most_common(1)[0]
            rechecks.append(Recheck(shape_id, label.name, len(complete), round(agreement, 3), pattern, count))
    return sorted(rechecks, key=lambda recheck: -recheck.pattern_words)


def write_rechecks(path: Path, rechecks: Sequence[Recheck]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(path, ("shape_id", "name", "words", "agreement", "pattern", "pattern_words"),
               ((recheck.shape_id, recheck.name, recheck.words, f"{recheck.agreement:.3f}", recheck.pattern, recheck.pattern_words)
                for recheck in rechecks))
