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

- **Per-book profiles (user direction: not a generic solution).**
  - `scan/profile.py`; `fonts/<scan-font>/scan/profile.json` is read by `scan-index` (`--scan-profile` overrides it).
  - The defaults are Prasaaskhara's validated values, so the step-1a rescaling was undone for books without a profile.
  - `=` words are marked by grouping (`ScanWord.equals`), so `ScanPage` carries a single height again: the shape height.
  - Prasaaskhara with no profile: page 51 stays at 95/99. Same as Tesseract 19,115 (19,113 post-review), `=` 9,450, ఁ 1,026, ఱ 268, periods 374, other 266. The post-review baseline is reproduced.
  - Naishadamu profile: letter units for grouping and shapes. Shapes in letter height gave 1,175 ids instead of 1,335, and 818 one-offs instead of 1,006.
  - **Word-gap sweep** (tuned on 197 + 209, held-out 201):

    | `word_gap` | Tuning (197 + 209) | Held-out 201 | Grouping misses |
    |---|---|---|---|
    | 0.38 | 184/313 | 93/170 | 37 |
    | 0.45 | 184/313 | 93/170 | 36 |
    | 0.55 | 184/313 | 99/170 | 30 |
    | 0.65 | 185/313 | 100/170 | 30 |
    | 0.75 | 190/313 | 103/170 | 28 |
    | **0.85** | **193/313** | **105/170** | **22** |
    | 1.0 | 189/313 | 106/170 | 21 |
    | 1.2 | 190/313 | 108/170 | 22 |

    0.85 was chosen as the tuning-page peak; the held-out page confirms it.
  - Naishadamu gold now: **298/483 (61.7%)**. Misses: unlabelled 82, grouping 22, wrong label 7, missing 3, extra 2, ocr overruled 1. Grouping is no longer the main cause.
  - Step 1e (per-page adaptive gap) is not needed for now: one book-level value fixes most splits.
  - **`/code-review` fixes:**
    - the catalog saves its `shape_unit`, and `scan-index` refuses a catalog scaled by another unit (older catalogs count as median);
    - `scan-split` scales shapes by the profile's shape unit;
    - a `--scan-profile` path given on the command line must exist;
    - profile numbers are converted when loading;
    - unit comparison is by value.

    Left: the defaults going back to median is the user's decision, and computing a height twice is trivial.
  - `pytest`: 301 passed. `lint.cmd`: OK. Version 0.18.0.
- **Step 1b: stroke repair** (`page.repaired`, profile `repair_size` and `repair_gap`, off by default).
  - **Evidence:** pixel gap to the nearest ink in the word, by the pilot's reviewed names.

    | Piece | Size | Median gap | p10 gap |
    |---|---|---|---|
    | `slash`, `right_top` | 16–21 px | ~3 px | 2 px |
    | `tick` | 43 px | 9 px | 5.3 px |
    | Real marks (`్య`, `ృ`, `(`, `pipe`, `ః`, `'`, `.`) | — | 7.5–13 px | ≥ 5.2 px |

    `tick` is printed as a separate piece, not broken off, so it stays separate and is handled by recipes.
  - Naishadamu: `repair_size` 0.4, `repair_gap` 0.08 (5 px). Ids 1,165 → 1,106, one-offs 810 → 784. Gold unchanged at 298/483.
  - **Finding:** the wider word gap (0.85) lowered label coverage from 34% to 20% on 3 pages. Labelled ids fell from 155 to 81, because whole words hold more unlabelled ids than inference can solve (it handles 1–2).
    - Grouping stays on true words, since gold accuracy rose from 277 to 298.
    - Re-measure at Gate 1 (20 consecutive pages, where ids recur more). If coverage stays low, the fix belongs in inference, not grouping.
  - **`/code-review` (run after the commit; fixed in a follow-up):**
    - each fragment is measured only against the original letters, so it can't chain through another fragment;
    - ties go to the earlier component instead of a memory address;
    - one join helper replaces `_with_dot`, and the sentinel was removed;
    - tests were added for nearest-of-two and for no chaining.
    - Left: pixel versus box gap conventions (the threshold uses the measured pixel distance, and the box check only prefilters); heights measured before repair (fragments sit below the median); speed (27 s for 3 pages, to revisit at Gate 1); JIRA (skipped by the user).
    - After the fixes: ids 1,109, one-offs 788, gold 298/483. `pytest`: 306 passed.
- **Step 1c: loose specks** (`words._loose_speck`, profile `loose_speck_size`, off by default).
  - **Evidence:**
    - after the 0.85 word gap, only 2 one-piece words under 20 px remained on the gold pages (7 px and 9 px, both read as `ఆ`; these were the 2 `extra` misses);
    - the pilot's full stops are about 15 px (0.24 letter).
  - Naishadamu: `loose_speck_size` 0.18 (11 px), below any full stop. extra 2 → 1; gold unchanged at 298/483. The remaining extra `ఆ` is a multi-piece word, probably colon dots.
  - `/code-review` fixes: the cutoff lowered from 0.25 to 0.18 on the evidence; a full-stop-sized boundary test; the threshold computed once; version 0.20.0.
  - Left: specks in clusters (none on gold); the separate inside-letter speck rule (a different job); bounding-box size only applies to pieces left alone. The dropped-speck trace is noted for 1d.
  - `pytest`: 308 passed.
- **Step 1d (grouping check sheet): skipped, on the evidence.** Of the 21 remaining `grouping` misses on gold, most are not segmentation errors:
  - spaces Tesseract puts inside one crop;
  - colon spacing;
  - dandas Tesseract misreads;
  - stray marks read as letters.

  A manual sheet would cost reviewer time and fix almost none of them.
- **Finding: at the 0.85 gap, units are phrases, not words.** 79 of 363 crops (22%) hold several real words. The gold gain came from Tesseract reading multi-word crops better.
  - **Experiment, rejected:** line-context OCR (`image_to_data --psm 7` on each line, mapped to our words by word boxes) scored 277/483 at every word gap, below the 298 for phrase crops.
  - Tesseract modes on the same phrase crops: psm 8 gave 241, psm 7 gave 196, psm 6 gave 176 (these counts include `=` bars read as text). The single-word mode on phrase-sized chunks is best, and only the line modes return word boxes. The line-OCR code was removed.
  - **Decision:** keep 0.85, with phrases as the unit for OCR and conversion.
    - Training data is unaffected, since `tesstrain` trains on line and phrase images.
    - Label coverage is the cost: 17–20% on 3 pages against 33% at 0.38, because inference solves only 1–2 unknowns per unit. Re-measure at Gate 1. If coverage stays low, widen inference (more unknowns per unit), not grouping.
- `ScanProfile` was split into `Grouping` (the grouping unit and thresholds) plus `shape_unit`, to satisfy lint. JSON profiles stay flat.
  - `/code-review` fixes: profile keys are checked against the known flat names, with an error that lists them; unit conversion is back to a simple set; a test constant was renamed. Left: field names as the JSON contract (now validated); the split kept rather than an inline lint disable; JIRA (skipped by the user).

- **Gate 1 (2026-10-08):** fresh index of pages 195–214 (20 consecutive pages, including the three gold pages), with no review.

  | Measure | 3 gold pages | 20 pages |
  |---|---|---|
  | Ink pieces | 2,661 | 15,193 |
  | Shape ids | 1,109 | 3,196 |
  | One-off ids | 788 | 1,995 (13% of pieces) |
  | **Glyph coverage** | 22% | **63%** |
  | Labelled ids | 80 | 503 |
  | Complete words | — | 505 of 1,770 |
  | Gold exact (ours = OCR) | 298/483 | 298/483 |

  - Gold misses: unlabelled 77, grouping 21, **ocr overruled 10** (was 1), wrong label 6, missing 1, extra 1.
  - The review sheet has 50 rows covering 3,126 of 15,193 pieces (21%).
  - Run time: 6 min 54 s for 20 pages.
  - **Reading:** coverage recovers with recurrence, as predicted, so grouping on phrases is fine. Gold doesn't move yet, because our complete readings still lose to Tesseract: 10 overruled. That is exactly what step 2 (trust from shape evidence) targets.

- **Step 2: OCR fixes and trust (2026-10-08).**
  - **Trust from shape evidence (`trust_support`): tried and removed.** On the Gate 1 state the tuning pages were best with it off: 193 at 0, against 188–189 at 2–5. Every setting raised wrong labels.
    - Cause: learned labels are not independent evidence. Tesseract's systematic misreading made the danda shape learn the label `1` (support 3–7), so trusting support wrote `1తవ1` where Tesseract alone had `। తవ`.
  - **Per-book OCR fix table** `fonts/<font>/scan/ocr-fixes.tsv` (`ocr`, `text`; whole tokens only; applied after cleaning, so `193` is untouched). It feeds inference, review, split and conversion. The `scan-evaluate` OCR-alone baseline stays raw.
    - **Evidence** from aligning raw OCR with gold: `1` → `।` (8 of 9), `|` → `।` (3 of 3), `2` → `:` (2 of 2). On 20 pages Tesseract wrote 67 standalone `1`, 34 `|` and 35 `2` tokens. `॥` → `।` was seen twice but left out, because `॥` is often correct.
    - The Naishadamu table is a **draft** for the user to confirm.
    - **Result** (Gate 1 state, no review): **319/483 (66.0%) against 298 for OCR alone**, the first time ours beats OCR on a fresh start. Tuning 193 → 205, held-out 201 105 → 114. Wrong label 6 → 2, coverage 63% → 64%. Caveat: the fix evidence used all three gold pages, so 201 is not strictly held out for the fixes. The 20-page counts support them independently.
    - Misses now: unlabelled 70, grouping 21, ocr overruled 9, missing 3, wrong label 2, extra 1.
  - Prasaaskhara (no table) reproduces its baseline exactly: page 51 at 95/99, same as Tesseract 19,115.
  - `_choose` was split into `_ours_wins`, to satisfy lint.
  - `/code-review` fixes: fixes run after cleaning, so quote-wrapped tokens are fixed; duplicate entries are rejected; `--ocr-fixes` option added; no table means texts are untouched; version 0.22.0.
    - Left: the fixes reaching inference (that is their purpose); the raw baseline (by design); the unreachable empty word; BOM handling (shared mapping convention).
  - `pytest`: 313 passed. `lint.cmd`: OK.

- **Step 3: review ranked by words completed (2026-10-09).**
  - **Evidence** (Gate 1 state, 1,770 units, 214 already readable): units made fully readable by deciding the top N shapes.

    | Decisions | Old ranking (flagged, then count) | Static words-completed | **Greedy, recounted after each pick** |
    |---|---|---|---|
    | 50 | 403 | 417 | **444** (+10%) |
    | 100 | 465 | 488 | **547** (+18%) |

  - `review_rows`: shapes without a confident label come first, ordered greedily by the words each decision completes, counted over the whole book and recounted after every pick. Picks come only from the sheet's pages. Confident undecided shapes follow by count. Ties keep the old order, flagged then count. Each row shows `+N with rows above`.
  - Real sheet: the top 50 rows add **230 readable units**, matching the simulation. It builds in 3 s.
  - **Deferred:** recipe drafts with evidence on the sheet. They need symbolic names from reviewed decisions, so they come after Gate 2.
  - `/code-review` fixes: the cumulative label (`+N with rows above`); single-meaning variables; a full-order test; version 0.23.0. Left: speed (fine at 20 pages); book-wide gains on page-limited sheets (a decision applies book-wide); confident undecided shapes counted as settled (matches what conversion reads).
  - `pytest`: 316 passed. `lint.cmd`: OK.

## In progress
- None.

## Blocked / open issues
- None.

## Next steps
- **Gate 2:** the user reviews `files/sriharsha-naishadamu/output/intermediate/scan-review/review.html` (50 rows) and saves `decisions.tsv` (and any `recipes.tsv`) to `fonts/scan-naishadamu/scan/`; then re-label and measure on gold.
