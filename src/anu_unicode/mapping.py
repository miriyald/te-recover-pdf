from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

MAPPING_COLUMNS = ("glyphs", "unicode", "first_page", "first_word")
PENDING_COLUMNS = ("glyphs", "unicode", "count", "first_page", "first_word", "contexts")
PROGRESS_COLUMNS = ("page", "glyphs", "unmapped_before", "unmapped_after", "new_entries")
SUSPICION_COLUMNS = ("glyphs", "suggested", "status", "reason", "page", "word")
ACCEPTED = "accepted"


@dataclass(frozen=True)
class MappingEntry:
    glyphs: str
    unicode: str
    first_page: int | None = None
    first_word: str = ""


@dataclass
class Proposal:
    glyphs: str
    unicode: str
    count: int
    first_page: int
    first_word: str
    contexts: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Suspicion:
    glyphs: str
    suggested: str
    status: str
    reason: str
    page: int | None = None
    word: str = ""


@dataclass(frozen=True)
class PageProgress:
    page: int
    glyphs: int
    unmapped_before: int
    unmapped_after: int
    new_entries: int


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    header, *lines = path.read_text(encoding="utf-8").splitlines()
    columns = header.split("\t")
    return [dict(zip(columns, line.split("\t"))) for line in lines if line.strip()]


def _write_rows(path: Path, columns: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> None:
    lines = ["\t".join(columns)] + ["\t".join("" if value is None else str(value) for value in row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _entry(row: dict[str, str]) -> MappingEntry:
    first_page = int(row["first_page"]) if row.get("first_page") else None
    return MappingEntry(row["glyphs"], row["unicode"], first_page, row.get("first_word", ""))


def load_entries(path: Path) -> dict[str, MappingEntry]:
    return {row["glyphs"]: _entry(row) for row in _read_rows(path)}


def save_entries(path: Path, entries: Mapping[str, MappingEntry]) -> None:
    rows = ((entry.glyphs, entry.unicode, entry.first_page, entry.first_word) for _, entry in sorted(entries.items()))
    _write_rows(path, MAPPING_COLUMNS, rows)


def load_mapping(path: Path) -> dict[str, str]:
    return {glyphs: entry.unicode for glyphs, entry in load_entries(path).items()}


def load_pending(path: Path) -> list[Proposal]:
    return [
        Proposal(row["glyphs"], row["unicode"], int(row["count"]), int(row["first_page"]), row["first_word"],
                 set(row.get("contexts", "").split()))
        for row in _read_rows(path)
    ]


def save_pending(path: Path, proposals: Iterable[Proposal]) -> None:
    rows = sorted(proposals, key=lambda proposal: (proposal.glyphs, proposal.unicode))
    _write_rows(path, PENDING_COLUMNS, (
        (p.glyphs, p.unicode, p.count, p.first_page, p.first_word, " ".join(sorted(p.contexts))) for p in rows
    ))


def load_suspicions(path: Path) -> list[Suspicion]:
    return [
        Suspicion(row["glyphs"], row["suggested"], row["status"], row["reason"], int(row["page"]) if row.get("page") else None,
                  row.get("word", ""))
        for row in _read_rows(path)
    ]


def apply_accepted(entries: dict[str, MappingEntry], suspicions: Iterable[Suspicion]) -> list[tuple[str, str, str]]:
    changes = []
    for suspicion in suspicions:
        current = entries.get(suspicion.glyphs)
        if suspicion.status == ACCEPTED and suspicion.suggested and (current is None or current.unicode != suspicion.suggested):
            changes.append((suspicion.glyphs, current.unicode if current else "", suspicion.suggested))
            entries[suspicion.glyphs] = MappingEntry(suspicion.glyphs, suspicion.suggested, suspicion.page, suspicion.word)
    return changes


def processed_pages(path: Path) -> set[int]:
    return {int(row["page"]) for row in _read_rows(path)}


def append_progress(path: Path, progress: PageProgress) -> None:
    rows: list[tuple[object, ...]] = [tuple(row[column] for column in PROGRESS_COLUMNS) for row in _read_rows(path)]
    rows.append((progress.page, progress.glyphs, progress.unmapped_before, progress.unmapped_after, progress.new_entries))
    _write_rows(path, PROGRESS_COLUMNS, rows)
