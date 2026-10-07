# Status: Scan shape names and recipes
_Last updated: 2026-10-06_

## Current state
In progress: implementation is done and waiting for the reviewer's names and recipes.

## Completed
- Round 3 archived to `files/<book>/archive/2026-10-06-round3/`.
- "Lost periods" root-caused: 356 of 368 are periods Tesseract invents. They are not a regression.
- `scan/names.py`: names (Unicode or symbolic), a `Speller` that uses name-level private-use codes in Plane 16 together with `convert_anu`, and `validate_recipes`.
- Inference works on names and the speller. The pre-base `◌` form is chosen by agreement (`settle_forms`).
- `scan/recipes.py`: recipe proposals keyed by name pairs, at 3 or more votes and a share of at least 60%.
- `scan/checks.py`: decision check over significant differences only. Ignored differences:
  - periods and commas Tesseract adds;
  - differences that contain a letter Tesseract cannot read (ఁ, ఱ).
- Review sheet: rechecks, recipe proposals, rows of names with words rendered next to their OCR, and exports of `decisions.tsv` (`shape_id`, `name`) and `recipes.tsv`.
- Decisions migrated to the `name` column. Version 0.14.0. `pytest`: 262 passed. `lint.cmd`: OK.
- Whole-book run with round-3 decisions and no recipes:

  | Measure | Result |
  |---|---|
  | Page 51 | 95/99 |
  | Glyph coverage | 95.7% |
  | Disagreements | 1,070 (same as round 3, as expected) |
  | Rechecks | **24** (89 before the noise filter) |

  The rechecks cover:
  - పొ/సొ ids that are really పా/సా (about 65 words);
  - 2431 ∅, which should be ౖ;
  - **1974 and 1650 ∅: the ఏ tail, the real cause of ఏ→ఎ**;
  - 1741 ద్ద, which should be డ్డ;
  - the థ/ధ decisions.

## In progress
- `/code-review`, then commit.

## Blocked / open issues
- Recipe proposals need symbolic names. None exist yet; the reviewer adds them, for example `ee_tail`.
- The 12 word-final dots with ink after the word have not been inspected yet.

## Next steps
- The reviewer works through the sheet: the rechecks first, then names such as `ee_tail`. Re-run `scan-label` to get recipe proposals, confirm them, then measure.
