import argparse
import json
from pathlib import Path

import pymupdf

from anu_unicode.cli import _clean, _convert, book_slug, resolve_paths
from anu_unicode.layout import BookLayout
from anu_unicode.profile import DEFAULT_PROFILE, load_profile

FONT = Path("fonts/anu")
STATE = Path("files/mahabharatamu/state")


def _arguments(command: str, **given: object) -> argparse.Namespace:
    unset = dict.fromkeys(("profile", "mapping", "pending", "progress", "suspicious", "ocr_cache"))
    return argparse.Namespace(**{"command": command, "font": "anu", "book": "mahabharatamu", **unset, **given})


def _book(tmp_path: Path) -> BookLayout:
    layout = BookLayout("tiny", tmp_path / "files", tmp_path / "archive")
    layout.input.mkdir(parents=True)
    with pymupdf.open() as document:
        for text in ("first page", "second page"):
            document.new_page().insert_text((72, 72), text)
        document.save(layout.input / "Tiny Book.pdf")
    return layout


def _convert_arguments(layout: BookLayout, **given: object) -> argparse.Namespace:
    arguments = _arguments("convert", **{"method": "ocr-learning", "pages": None, **given})
    resolve_paths(arguments)
    arguments.layout, arguments.pdf, arguments.profile = layout, layout.input_pdf(), DEFAULT_PROFILE
    return arguments


def test_book_slug_is_lowercase_and_hyphenated() -> None:
    assert book_slug(Path("files/Maha Bharatham Vol 3 Sabha Parvam.pdf")) == "maha-bharatham-vol-3-sabha-parvam"


def test_font_assets_and_book_state_resolve_to_their_folders() -> None:
    arguments = _arguments("learn")

    resolve_paths(arguments)

    assert arguments.profile == FONT / "profile.json"
    assert arguments.mapping == FONT / "ocr-learning" / "mapping.tsv"
    assert (arguments.progress, arguments.ocr_cache) == (STATE / "progress.tsv", STATE / "ocr-cache")
    assert not vars(arguments)["mapping_given"]


def test_a_book_with_its_own_profile_file_uses_it() -> None:
    arguments = _arguments("convert", book="maha-bharatham-vol-8-bheshma-parvam")

    resolve_paths(arguments)

    assert arguments.profile == FONT / "books" / "maha-bharatham-vol-8-bheshma-parvam.json"


def test_book_profiles_extend_the_anu_profile_with_the_type1_layout() -> None:
    for path in (FONT / "books").glob("*.json"):
        profile = load_profile(path)

        assert profile.anu_fonts == DEFAULT_PROFILE.anu_fonts
        assert profile.type1_layout_file == "fonts/anu/type1-layout.tsv" and len(profile.type1_codes) > 200


def test_explicit_paths_are_kept() -> None:
    arguments = _arguments("convert", mapping=Path("other.tsv"))

    resolve_paths(arguments)

    assert arguments.mapping == Path("other.tsv")
    assert vars(arguments)["mapping_given"]


def test_shapes_writes_the_generated_mapping_but_probe_write_stays_optional() -> None:
    shapes, probe = _arguments("shapes", book=None, names=None, recipes=None, write=None), _arguments("probe", write=None)

    resolve_paths(shapes)
    resolve_paths(probe)

    assert shapes.write == FONT / "shape-naming" / "mapping.tsv"
    assert shapes.names == FONT / "shape-naming" / "names.tsv"
    assert probe.write is None


def test_anu_profile_file_matches_the_built_in_default() -> None:
    assert load_profile(FONT / "profile.json") == DEFAULT_PROFILE


def test_whole_book_run_is_final_output_with_book_text_and_manifest(tmp_path: Path) -> None:
    layout = _book(tmp_path)

    _convert(_convert_arguments(layout))

    out = layout.output("ocr-learning")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert (out / "page-1.unicode.txt").read_text(encoding="utf-8") == "first page\n"
    assert (out / "book.txt").read_text(encoding="utf-8") == "first page\n\fsecond page\n"
    assert (manifest["book"], manifest["source"], manifest["method"]) == ("tiny", "Tiny Book.pdf", "ocr-learning")
    assert manifest["result"] == {"pages": 2, "coverage": 1.0, "unmapped_sequences": 0, "skipped_type3_pages": []}
    assert list(manifest["mapping_sources"]) == ["fonts/anu/ocr-learning/mapping.tsv"]


def test_rerun_archives_the_previous_final_output(tmp_path: Path) -> None:
    layout = _book(tmp_path)
    _convert(_convert_arguments(layout))
    stamp = json.loads((layout.output("ocr-learning") / "manifest.json").read_text(encoding="utf-8"))["created"]

    _convert(_convert_arguments(layout))

    assert (layout.archived_output("ocr-learning", stamp) / "book.txt").exists()
    assert (layout.output("ocr-learning") / "book.txt").exists()


def test_partial_run_goes_to_intermediate_and_leaves_final_output_alone(tmp_path: Path) -> None:
    layout = _book(tmp_path)

    _convert(_convert_arguments(layout, pages=[2]))

    out = layout.intermediate("convert", "ocr-learning")
    assert sorted(path.name for path in out.glob("page-*")) == ["page-2.unicode.txt"]
    assert not layout.output("ocr-learning").exists()


def test_shape_naming_compiles_the_gold_names_and_recipes(tmp_path: Path) -> None:
    layout = _book(tmp_path)

    _convert(_convert_arguments(layout, method="shape-naming"))

    manifest = json.loads((layout.output("shape-naming") / "manifest.json").read_text(encoding="utf-8"))
    assert list(manifest["mapping_sources"]) == ["fonts/anu/shape-naming/names.tsv", "fonts/anu/shape-naming/recipes.tsv"]


def test_clean_removes_only_intermediate_files(tmp_path: Path) -> None:
    layout = _book(tmp_path)
    _convert(_convert_arguments(layout))
    _convert(_convert_arguments(layout, pages=[1]))

    _clean(argparse.Namespace(all=False, layout=layout))

    assert not layout.intermediate_root.exists()
    assert (layout.output("ocr-learning") / "book.txt").exists() and layout.input_pdf().exists()
