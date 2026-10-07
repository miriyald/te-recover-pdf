# Plan: Scan OCR consensus

## Scope
Implement the design in `design.md` on branch `scan-ocr-consensus`. Then run the 5-page pilot and stop at the pilot gate. The whole book runs only after approval.

## Steps
1. [x] Spike on the pilot pages and settle the design (`docs/temp/scan-v2/word_infer.py`, throwaway).
2. [ ] Archive the old state.
   - Move `files/<book>/state/*` and `output/intermediate/scan-*` to `files/<book>/archive/2026-10-06/`.
   - `git mv` `fonts/scan-prasaaskhara/scan/excluded.tsv` to `fonts/scan-prasaaskhara/archive/excluded-2026-10-06.tsv`.
3. [ ] Detect `=` (TDD). Add `ScanWord.is_equals` and the `EQUALS` id in the index. Make the ambiguity check and the stats skip it.
4. [ ] Add word OCR, `scan/word_ocr.py` (TDD, Tesseract mocked). It crops each word and caches the readings by page and box.
5. [ ] Add glyph OCR seeds, `scan/glyph_ocr.py` (TDD). Move `tesseract_reading`, `majority` and the crop sampling out of `atlas.py`.
6. [ ] Add inference, `scan/inference.py` (TDD on synthetic sequences): solve, the band tie-break, accept, refine, and decisions held fixed.
7. [ ] Add the review sheet, `scan/review.py` (TDD): ranking, HTML, and the `decisions.tsv` export.
8. [ ] Change conversion (TDD): the merge policy, `=`, and `disagreements.tsv`.
9. [ ] Commands: `scan-index`, `scan-label` (OCR, inference, labels), `scan-review --top --pages` and `scan-convert`. Remove `scan-atlas`, `scan-pages`, `--excluded` and `read_excluded`, with their tests. Bump the version to 0.13.0.
10. [ ] `lint.cmd` and `pytest` pass.
11. [ ] Run the pilot: `scan-index` → `scan-label` → `scan-review` → `scan-convert` on pages 51, 67, 11, 103 and 175. Score against the page-51 truth.
12. [ ] **Pilot gate.** Report and wait for approval.
13. [ ] Whole book, after approval.

## Risks & mitigations
- **Inference is too slow on the whole book.** The candidate pool is pruned per word, and pairs are tried only for words with 2 unknowns. Measure on the pilot.
- **Word numbering is not a stable key across re-indexing.** Key the OCR cache by page and word box instead.
- **The automatic labels inherit Tesseract's systematic errors.** The review sheet flags unlabelled ids, `∅` on main-band pieces, and low agreement.

## Verification / acceptance criteria
- `pytest` and `lint.cmd` both pass.
- Pilot, page 51: merged exact words ≥ 94/99 with no review, and ≥ 96/99 after one review sheet.
- Pilot: no exclusion list is needed, the `=` words are emitted as `=`, and the review-sheet size is reported.
