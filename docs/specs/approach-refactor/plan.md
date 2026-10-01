# Plan: make the two conversion approaches visible in the code

_Status: done 2026-10-01. Design: `design.md`._

## Scope
In:
- package split (`ocr_learning`, `shape_naming`, shared core) and per-package CLI registration;
- data layout per font encoding (`fonts/anu/` with both golds) and per book (`books/mahabharatamu/`), plus a `--font` option;
- `review_html.py` to break the `compare` → `learn`/`report` coupling;
- promoting `sheets`, `compare --names` and `scripts/compare_outputs.py`;
- `docs/approaches.md`.

Out: conversion behaviour changes, renamed commands, mixed-encoding conversion (follow-up for Vol 3, see design), and the hybrid bootstrap (`docs/specs/hybrid-bootstrap/plan.md`).

## Steps (ordered, checkable)
- [x] 1. Branch from `shape-names-recipes`; confirm `git status` is clean; record a baseline: `pytest`, `lint.cmd`, `anu-unicode --help`, `compare` (0 differences), `quality --pages 6` (0 errors).
- [x] 2. Create `src/anu_unicode/ocr_learning/` and `src/anu_unicode/shape_naming/` with empty `__init__.py`; `git mv` the modules per the design table; fix imports; move the tests into the mirror layout. Commit as a pure move.
- [x] 3. Data layout, as `git mv` so history is kept:
  - `mappings/mapping.tsv` → `fonts/anu/ocr-learning/mapping.tsv` (gold 1);
  - `shapes/names.tsv` and `shapes/recipes.tsv` → `fonts/anu/shape-naming/` (gold 2);
  - `DEFAULT_PROFILE` → `fonts/anu/profile.json`;
  - `git rm --cached shapes/mapping.tsv` and ignore `fonts/*/shape-naming/mapping.tsv` (generated);
  - `mappings/{progress,pending,suspicious}.tsv` and the OCR cache → `books/mahabharatamu/` (untracked state, ignored).

  Add `--font` (default `anu`) to resolve the default paths. Check the sha256 of both golds before and after the move.
- [x] 4. Add core `review_html.py` (STYLE, table, glyph and Telugu cells, `crop(page, bbox)`); switch `report.py` and `compare.py` to it; remove `compare.py`'s imports of `learn` and `report`.
- [x] 5. Move CLI registration into `add_commands(subparsers)` per package; `cli.py` keeps the global options and core commands; check that `--help` groups commands by approach.
- [x] 6. Promote the tools:
  - `shape_naming/sheets.py` + `sheets` command (from `make_sheets.py`, reusing `atlas.glyph_stats` / `load_fonts`), with tests;
  - `compare --names` shape-name column (from `show_words.py`), with tests;
  - `scripts/compare_outputs.py` (from `compare_batches.py`, page list and directories as arguments).
- [x] 7. Write `docs/approaches.md`; update paths in `new-font-playbook.md`; bump `pyproject.toml` to 0.5.0; update `status.md`.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Broken imports after the move | pure-move commit first, then fix-ups; `pytest` + `lint.cmd` after every step |
| CLI behaviour change | diff `anu-unicode --help` and each command's `--help` against the step-1 baseline |
| Output drift | rerun `shapes` + `compare` and `quality --pages 6` against the baseline |
| Promoted tools drag in throwaway code | `sheets` reuses `atlas` helpers; only `make_sheets`, `show_words` (as a flag) and `compare_batches` come across |

## Verification / acceptance criteria
1. `lint.cmd` clean; all existing tests pass in their new locations, plus new tests for `sheets` and `compare --names`.
2. `compare` reports 0 differences on all 77,191 words; gold page 6 has 0 errors.
3. `grep -r "ocr_learning" src/anu_unicode/shape_naming` and the reverse both return nothing.
4. Command names are unchanged against the baseline `--help`; the only new option is `--font`.
5. Both golds are byte-identical before and after the move (sha256); the generated `fonts/anu/shape-naming/mapping.tsv` is not tracked and is rebuilt by `anu-unicode shapes`.
6. Running with no path options uses `fonts/anu/` and `books/mahabharatamu/`.
