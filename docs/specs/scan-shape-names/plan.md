# Plan: Scan shape names and recipes

## Scope
Implement `design.md` on a new branch, `scan-shape-names`, cut from `scan-ocr-consensus`. Re-run on the whole book with the cached OCR, and compare with round 3, which is archived.

## Steps
1. [x] Archive the round-3 results by copy (`files/<book>/archive/2026-10-06-round3/`). The ids, catalog and caches stay in `state/`.
2. [ ] `scan/names.py` (TDD): `is_symbolic`; a speller built from shape → name plus recipes, using `convert_anu` over name characters; validation.
3. [ ] Decisions become `shape_id`, `name`. Read the old `unicode` column as `name` and migrate `decisions.tsv`. Labels gain the name.
4. [ ] Inference renders through the speller (TDD: a named piece plus a recipe solves the word; an uncovered symbolic name leaves a gap).
5. [ ] Pre-base `◌` form choice (TDD: a sign before its consonant becomes `◌s`, a sign after stays `s`).
6. [ ] `scan/recipes.py` proposals (TDD: `ె` + `ai_bottom` in వైపు-type words gives `ై`; a split vote gives no proposal).
7. [ ] Decision check (TDD: low agreement is flagged with its pattern; an ఁ-only difference is exempt).
8. [ ] Review sheet: three sections, rendered samples, name input, export of decisions and recipes.
9. [ ] Commands: `scan-label` writes the labels, proposals and checks; `scan-review` and `scan-convert` use the speller. Add `--recipes` (default `fonts/<font>/scan/recipes.tsv`) and bump the version to 0.14.0.
10. [ ] `lint.cmd` and `pytest` pass, then `/code-review`.
11. [ ] Run on the whole book with the cached OCR. Inspect the 12 dot cases.
12. [ ] Gate: report the before/after table. You review the sheet with names and recipes.

## Risks & mitigations
- **A symbolic name with no recipe silently loses ink.** It renders as a gap, so the word falls back to OCR and shows up as a recipe proposal.
- **Recipe proposals inherit Tesseract errors.** They are confirmed by a human, never applied automatically.
- **The `◌` auto-form flips correct labels.** It switches only when `◌s` has strictly higher agreement over at least 3 words.

## Verification / acceptance criteria
- Page 51 keeps at least 95/99.
- The decision check flags 2431 and at least one of the ఎ ids, and does not flag any ఁ id.
- After 2431 is renamed `ai_bottom`, a `ె ai_bottom → ై` recipe is proposed. Once confirmed, వైపు is restored in about 26 words.
- The 205/3918 `◌` corrections happen by themselves when the decisions say plain `ె`.
- Disagreements are at or below round 3's 1,070.
