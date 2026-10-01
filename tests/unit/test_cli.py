import argparse
from pathlib import Path

from anu_unicode.cli import book_slug, resolve_paths
from anu_unicode.profile import DEFAULT_PROFILE, load_profile

FONT = Path("fonts/anu")
BOOK = Path("books/mahabharatamu")


def _arguments(command: str, **given: object) -> argparse.Namespace:
    unset = dict.fromkeys(("profile", "mapping", "pending", "progress", "suspicious", "ocr_cache"))
    return argparse.Namespace(command=command, font="anu", pdf=Path("files/Mahabharatamu.pdf"), **{**unset, **given})


def test_book_slug_is_lowercase_and_hyphenated() -> None:
    assert book_slug(Path("files/Maha Bharatham Vol 3 Sabha Parvam.pdf")) == "maha-bharatham-vol-3-sabha-parvam"


def test_font_assets_and_book_state_resolve_to_their_folders() -> None:
    arguments = _arguments("learn")

    resolve_paths(arguments)

    assert arguments.profile == FONT / "profile.json"
    assert arguments.mapping == FONT / "ocr-learning" / "mapping.tsv"
    assert (arguments.progress, arguments.ocr_cache) == (BOOK / "progress.tsv", BOOK / "ocr-cache")


def test_explicit_paths_are_kept() -> None:
    arguments = _arguments("convert", mapping=Path("other.tsv"))

    resolve_paths(arguments)

    assert arguments.mapping == Path("other.tsv")


def test_shapes_writes_the_generated_mapping_but_probe_write_stays_optional() -> None:
    shapes, probe = _arguments("shapes", names=None, recipes=None, write=None), _arguments("probe", write=None)

    resolve_paths(shapes)
    resolve_paths(probe)

    assert shapes.write == FONT / "shape-naming" / "mapping.tsv"
    assert shapes.names == FONT / "shape-naming" / "names.tsv"
    assert probe.write is None


def test_anu_profile_file_matches_the_built_in_default() -> None:
    assert load_profile(FONT / "profile.json") == DEFAULT_PROFILE
