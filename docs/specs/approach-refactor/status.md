# Status: make the two conversion approaches visible in the code
_Last updated: 2026-10-01_

## Current state
done

## Completed
Branch `approach-refactor` (from `shape-names-recipes`), one commit per step:

| Step | Commit | What |
|---|---|---|
| 1 | — | Baseline: 136 tests, lint, every `--help`, gold sha256, `compare` 0 differences, page 6 0 errors, all 449 pages converted |
| 2 | `9b1a4f4` | Pure move into `ocr_learning` / `shape_naming`, tests mirrored |
| 3 | `ddc124d` | `fonts/anu/` (profile + both golds, generated mapping untracked), `books/mahabharatamu/` (state), `--font` |
| 4 | `9337b49` | Core `review_html`; neither approach imports the other |
| 5 | `ce9f9d8` | `add_commands` per package; `--help` tags each command with its approach |
| 6 | `8385b3a` | `sheets` command, `compare` shapes column, `scripts/compare_outputs.py` |
| 7 | this commit | `docs/approaches.md`, version 0.5.0 |

Verification after the refactor:
- 145 tests pass (136 existing + 9 new); lint clean.
- Gold sha256 unchanged; the generated mapping is byte-identical to the previously committed one.
- All 449 converted pages are identical to the baseline; `compare` reports 0 differences; page 6 has 0 errors.
- Every command keeps its options; `--font` is the only new global option.
- No imports between `ocr_learning` and `shape_naming` in either direction.

## Deviations
- `DEFAULT_PROFILE` stays as the library default; the CLI reads `fonts/anu/profile.json`, and a test keeps the two equal.
- `new-font-playbook.md` paths were updated, but it lives in the untracked `docs/specs/anu-telugu-to-unicode/` folder, so it is not committed.

## Blocked / open issues
- Mixed-encoding books (Vol 3) need per-glyph encoding selection; recorded as a follow-up in `design.md`.

## Next steps
- `docs/specs/hybrid-bootstrap/plan.md` when wanted.
