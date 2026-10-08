# Plan: Scan workflow v3

## Scope
Stages 1–5 of `design.md`, built and measured in order. Each stage ends with a gold measurement on Naishadamu and the Prasaaskhara page-51 check.

## Steps
- [x] **0. Measurement base.**
  - The user confirms two more gold pages, which Claude drafts from the scans: a verse page and a `సమాసములు` page.
  - Move `score_page.py` and `page_misses.py` from `docs/temp` into a `scan-evaluate` command, with cause tags. Tests included.
- [x] **1a.** Letter-height body: an upper-peak estimator, with Prasaaskhara thresholds kept by re-expressing the gap constants. Tests come first.
- [x] **1b.** Stroke repair before clustering (fragment → host). Measure one-off ids and coverage before and after.
- [x] **1c.** Drop loose specks.
- [~] **1d.** `scan-grouping-review`: a sheet of doubtful groupings, with an exported decisions file that grouping reads back. Skipped: the remaining grouping misses are mostly OCR artefacts (see status).
- [x] **1a′.** Per-book `profile.json` (`scan/profile.py`). The defaults reproduce Prasaaskhara, and Naishadamu sets letter units for both grouping and shapes. `=` words are marked when grouping forms them (`ScanWord.equals`).
- [x] **1e.** Tune Naishadamu's `word_gap` on gold pages 197 and 209, and check it on 201. Done: 0.85 (see status). A per-page adaptive gap is not needed for now.
- [x] **Gate 1.** Fresh index of 20 consecutive Naishadamu pages and the gold pages. Report grouping errors on gold, one-off ids, coverage and gold accuracy, then stop.
- [x] **2.** Per-book OCR fix table (`ocr-fixes.tsv`) feeding inference and conversion. Trust from support alone was tried and removed (see status). The confusion table also covers the recheck, since rechecks read the fixed text.
- [ ] **3.** Review ranking by words completed, and recipe drafts with evidence on the sheet.
- [ ] **Gate 2.** The user does one review round; measure.
- [ ] **4a.** `scan-train-ocr`: export confirmed word crops and their text (`.png` plus `.gt.txt`), held out from gold.
- [ ] **4b.** Fine-tune `tel_best` with `lstmtraining` (CPU), then plug the model in through `--ocr-model`.
- [ ] **Gate 3.** Score model n+1 against model n on gold, and keep it only if it is better.
- [ ] **4c.** Optional: a GPU PyTorch recognizer, if the Tesseract model plateaus.

## Risks & mitigations
- **Re-expressing the gap constants changes Prasaaskhara.** Mitigation: the page-51 check on every change, with its round-5 state archived at `files/<book>/archive/2026-10-07-round5/`.
- **Stroke repair could fuse neighbouring letters.** Mitigation: join only fragments well below letter size that sit within a few pixels; measure grouping errors on gold.
- **The model learns our mistakes.** Mitigation: train only on confirmed words, keep gold out of training, and gate every model on gold.
- **Too little training data in the first round.** Mitigation: use 20+ consecutive pages and corrections from the misses page.

## Verification / acceptance criteria
- `pytest` and `lint.cmd` are green, and `/code-review` runs before each commit.
- Each gate reports gold accuracy for ours, OCR model n and stock Tesseract, plus Prasaaskhara page 51.
- Target: Naishadamu gold accuracy of 90% or more after Gate 3, with Prasaaskhara page 51 at 95/99 or better.
