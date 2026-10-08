# Status: Scan workflow v3
_Last updated: 2026-10-07_

## Current state
In progress. Step 0 (measurement base) is done; the new gold pages wait for the user's check.

## Completed
- The pilot work was committed and opened as draft PR #3, stacked on #2.
- Branch `scan-workflow-v3` was created off `scan-naishadamu-pilot`. The Naishadamu pilot state was archived to `files/sriharsha-naishadamu/archive/2026-10-07-pilot/`.
- The pilot's decisions and recipes were moved to `fonts/scan-naishadamu/archive/`. They were keyed by the archived catalog's ids, so on a fresh catalog they would label the wrong shapes.
- **Decision: trainer.** Tesseract LSTM fine-tuning from `tel_best` first, on CPU. A GPU PyTorch recognizer is used only if Tesseract plateaus on gold.
- **Step 0: measurement base.**
  - Gold pages 197 (verse) and 209 (`సమాసములు`) were drafted in `docs/temp/scan-naishadamu/gold/`, next to the confirmed page 201.
  - `scan-evaluate --gold <folder>` scores every gold page for our output and for OCR alone, and writes `scores.tsv` and a cause-tagged `misses.html` with scan crops.
    - Causes: `grouping` (split or merge), `missing`, `extra`, `unlabelled`, `ocr overruled`, `wrong label`.
  - Conversion now keeps, for each output word, the word keys and choices behind it (`Written`). `scan-convert` and `scan-evaluate` share one conversion helper.
  - `pytest`: 289 passed. `lint.cmd`: OK. `/code-review`: 7 findings fixed and 1 left with its reason: the OCR-alone baseline doesn't get our joining, by design.
- **Baseline:** fresh index of pages 197, 201 and 209, with no review.

  | Measure | Value |
  |---|---|
  | Ours = OCR | 272/482 (56.4%) |
  | grouping | 55 |
  | unlabelled | 42 |
  | wrong label | 11 |
  | extra | 6 |
  | missing | 4 |
  | ocr overruled | 3 |

## In progress
- The user checks gold pages 197 and 209. One doubtful word: `అదికాదరదం` on page 197, which may be `అధికాదరదం`.

## Blocked / open issues
- None.

## Next steps
- Step 1a: letter-height body.
