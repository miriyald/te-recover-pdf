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

- Round 4: 157 decisions, including six `e_top` names.
  - The proposal `ఎ e_top → ఏ` came from 72 words at 100%.
  - Disagreements fell to 1,012 and rechecks to 22. Page 51 is still 95/99.
- `scan-split` (commit 49dfb3b) found 10 candidates and split none; all 10 were the same look:
  - the ఁ ids (Tesseract reads them as ∅ or ం);
  - the పొ/పా ids, where Tesseract guesses about 50/50 on pixel-identical glyphs. The label is the reviewer's call.
- **Finding:** joined forms (ద్ద, డ్డి, ద్దు, గ్గు, జ్జ) are missing from the inference candidates, so 1741 and the rare joined or fused shapes can never be solved automatically.

- **Experiment rejected: drawing candidates from each word's own OCR text** (runs of 1–4 aksharas plus parts).
  - Unguarded: 328 labels gained, but they absorbed Tesseract's invented periods (`ది.`, `చు.`).
  - Guarded (runs need 3 votes, no punctuation in runs): no multi-akshara labels were learned, and disagreements rose from 1,012 to 1,038. Conjunct candidates made labels flip between host and subscript (క → క్ర at 0% agreement).
  - Fused shapes occur only 1–4 times each, so word evidence cannot label them safely; their words keep Tesseract's reading.
  - Reverted to commit 49dfb3b.

- Round 5: 157 decisions plus the recipe `ఎ e_top → ఏ`.
- Conversion trust fixes (commit c26267b):
  - agreement ignores ఁ and ఱ, and the periods Tesseract invents;
  - a reviewed id overrides Tesseract only when its neighbours agree at 0.8 or more;
  - a word Tesseract cannot read is written only from reviewed ids.
- Whole-book evaluation against Tesseract (30,616 words):

  | Change | Words |
  |---|---|
  | `=` written | 9,429 |
  | ఁ restored | 1,044 |
  | Invented periods left out | 357 |
  | ఱ restored | 264 |
  | Check against the page (పా/పొ 84, థ/ధ 11) | 95 |
  | Mostly worse | about 311 (about 580 before the fixes) |

  Page 51: 95/99. The evaluation page is `docs/temp/scan-v2/scan-evaluation.html`; it is not published because no claude.ai login was available.
- Draft PRs: #1 (`scan-ocr-consensus` → `main`) and #2 (`scan-shape-names` → `scan-ocr-consensus`).

## In progress
- None. Waiting for PR review.

## Blocked / open issues
- Recipe proposals need symbolic names. None exist yet; the reviewer adds them, for example `ee_tail`.
- The 12 word-final dots with ink after the word have not been inspected yet.

## Next steps
- The reviewer works through the sheet: the rechecks first, then names such as `ee_tail`. Re-run `scan-label` to get recipe proposals, confirm them, then measure.
