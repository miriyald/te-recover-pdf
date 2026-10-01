from pathlib import Path

from anu_unicode.mapping import (
    MappingEntry,
    PageProgress,
    Proposal,
    append_progress,
    apply_accepted,
    load_entries,
    load_mapping,
    load_pending,
    load_suspicions,
    processed_pages,
    save_entries,
    save_pending,
)


def test_entries_round_trip_with_empty_and_filled_audit_columns(tmp_path: Path) -> None:
    path = tmp_path / "mapping.tsv"
    entries = {"=∞": MappingEntry("=∞", "మ"), "¯": MappingEntry("¯", "్క", 7, "జరత్కారుని"), ",": MappingEntry(",", ",")}

    save_entries(path, entries)

    assert load_entries(path) == entries
    assert load_mapping(path) == {"=∞": "మ", "¯": "్క", ",": ","}


def test_pending_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "pending.tsv"
    proposals = [Proposal("_è»", "ఢ", 2, 7, "డుంఢుబోపాఖ్యానము", {"ం|ు", "డ|ా"})]

    save_pending(path, proposals)

    assert load_pending(path) == proposals


def test_only_accepted_suspicions_change_the_mapping(tmp_path: Path) -> None:
    path = tmp_path / "suspicious.tsv"
    path.write_text("glyphs\tsuggested\tstatus\treason\tpage\tword\nB\tఔ\taccepted\tocr\t63\tఔర్ఖ్యుడు.\nQ\t\topen\tmaybe\t\t\n",
                    encoding="utf-8")
    entries = {"B": MappingEntry("B", "జె"), "Q": MappingEntry("Q", "గే")}

    changes = apply_accepted(entries, load_suspicions(path))

    assert changes == [("B", "జె", "ఔ")]
    assert entries["B"] == MappingEntry("B", "ఔ", 63, "ఔర్ఖ్యుడు.")
    assert entries["Q"].unicode == "గే"
    assert not apply_accepted(entries, load_suspicions(path))


def test_missing_state_files_are_empty(tmp_path: Path) -> None:
    assert not load_pending(tmp_path / "pending.tsv")
    assert not processed_pages(tmp_path / "progress.tsv")


def test_progress_appends_and_reports_processed_pages(tmp_path: Path) -> None:
    path = tmp_path / "progress.tsv"

    append_progress(path, PageProgress(6, 400, 0, 0, 0))
    append_progress(path, PageProgress(7, 500, 9, 0, 2))

    assert processed_pages(path) == {6, 7}
    assert path.read_bytes().endswith(b"\n7\t500\t9\t0\t2\n")
