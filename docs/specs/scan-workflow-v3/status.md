# Status: Scan workflow v3
_Last updated: 2026-10-07_

## Current state
In progress. Step 0 (measurement base) is done. All three gold pages are confirmed by the user; next is step 1a.

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

- **Gold confirmed (2026-10-07).**
  - The user kept `అదికాదరదం` as printed and corrected `తత్యథాభవతి` to `తత్ యథాభవతి` on page 197.
  - Final baseline: **271/483 (56.1%)** for both ours and OCR. Misses: grouping 56, unlabelled 42, wrong label 11, extra 6, missing 4, ocr overruled 3.

- **Step 1a: letter-height grouping.**
  - **Evidence:** on Prasaaskhara the median piece height is the noisy unit. Over 198 pages it averages 50.1 px with an sd of 7.2, while letter height (the median of pieces at or above the median) averages 58.9 px with an sd of 3.9. On Naishadamu letter height is a steady 63 px against a median of 43–48.
  - Grouping now uses letter height: the text-area rules, specks, word and stacking gaps, and `=` bars. The constants were restated at Prasaaskhara's mean ratio of 0.85: `FURNITURE_WIDTH` 6.8, `SPECK_SIZE` 0.25, `WORD_GAP` 0.38, `STACK_GAP` 0.25 and `BAR_HEIGHT` 0.3.
  - **Decision:** shape normalisation keeps the median. Changing it would re-cluster Prasaaskhara and orphan its 157 reviewed decisions.
  - Naishadamu gold, fresh index: **277/483** (was 271). grouping 36 (was 56), extra 2 (was 6), unlabelled 62 (was 42; words that are now whole but still unlabelled), wrong label 13, missing 4, ocr overruled 4.
  - Prasaaskhara: page 51 stays at 95/99. Same as Tesseract 19,113 → 19,160; `=` 9,452; ఁ 1,026; ఱ 268; invented periods dropped 374 → 376; other 266 → 264.
  - Remaining grouping misses:
    - dandas that Tesseract drops; the tagger counts these as grouping;
    - real splits inside words (`చి త్తమ్`, `దై. వము`, `వరు డు`). These call for a per-page word gap taken from that page's own gap distribution (new step 1e).
    - a lone ః that Tesseract read as `క`.
  - `/code-review`: 3 of 9 findings fixed:
    - the word tests use the shipped gap constants;
    - a blank scanned page returns an empty page instead of NaN heights;
    - version 0.17.0.
  - Left, with reasons: thresholds that differ by book are intended; letter height is robust to furniture; the two height units are the recorded decision; 82 of 83,800 kept ids were lost and page 51 is unchanged; median computed twice (trivial).
  - Pre-existing and noted: `_member_shapes` rebuilds shapes without dot merging.
  - `pytest`: 291 passed. `lint.cmd`: OK.

## In progress
- None.

## Blocked / open issues
- None.

## Next steps
- Step 1b: stroke repair before clustering.
