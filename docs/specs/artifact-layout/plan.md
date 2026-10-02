# Plan: one place per book for inputs, final outputs, run state, scratch and archives

_Design: `design.md`. JIRA skipped._

## Scope
In: `layout.py`, `--book`, `convert --method` with final output, `book.txt`, manifest and archive-on-rerun; intermediate paths for every command; `approve` per-book batches; `clean`; script defaults; `.gitignore`; migrating the existing files; regenerating finals for both books.
Out: changes to conversion; `learn` on Vol 3 (next task).

## Steps (ordered, checkable)
- [x] 1. Baseline: `pytest`, `lint.cmd`; the Mahabharatamu 449-page conversion from `docs/temp/vol3-baseline` is kept as the reference before it is archived.
- [x] 2. `layout.py` (`BookLayout`) with tests; `cli.resolve_paths` uses it; `--book` replaces `--pdf`; `--out` removed; book state comes from `files/<book>/state/`.
- [x] 3. `convert --method`: final vs intermediate, compiled shape mapping, `book.txt`, `manifest.json`, archive-on-rerun; tests for each.
- [x] 4. Intermediate paths for `quality`, `compare`, `atlas`, `sheets`, `learn`/`confirm`; `approve` archives to `archive/<book>/batches/`; `clean` command; tests.
- [x] 5. Scripts (`compare_outputs`, `tesseract_evidence`, `index_glyphs`) take `--book`; `.gitignore` gets `files/` and `archive/` (drops `books/`).
- [x] 6. Migration: PDFs → `files/<slug>/input/`; `books/<slug>/*` → `files/<slug>/state/`; `docs/temp/*` and `archive/*` → `archive/legacy-2026-10-01/`. List every move first and keep the listing in `status.md`.
- [x] 7. Regenerate final output for both books × both methods; check Mahabharatamu pages against the baseline; update `docs/approaches.md` and `README`-level usage; bump to 0.6.0.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Losing state (OCR cache, progress) in the move | moves, never deletes; count files before and after |
| Output drift | page-by-page diff against the baseline for Mahabharatamu |
| A PDF accidentally staged | `files/` is ignored; check `git status` before each commit |
| `clean` removing something valuable | it only touches `output/intermediate/`; tested on a temporary root |

## Verification / acceptance criteria
1. `lint.cmd` clean; `pytest` green with tests for the layout, final vs intermediate, manifest, archive-on-rerun and `clean`.
2. `anu-unicode --book mahabharatamu convert --method ocr-learning` produces pages byte-identical to the baseline, plus `book.txt` and `manifest.json`.
3. Running it twice leaves one `output/ocr-learning/` and one archived copy under `archive/mahabharatamu/ocr-learning/`.
4. `docs/temp/` is empty, `books/` is gone, and every former file is under `archive/legacy-2026-10-01/` or `files/<book>/`.
