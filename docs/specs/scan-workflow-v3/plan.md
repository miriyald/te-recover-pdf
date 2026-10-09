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
- [x] **3.** Review ranking by words completed (greedy). Recipe drafts are deferred to after Gate 2, when symbolic names exist.
- [ ] **Gate 2.** The user does one review round; measure.
- [x] **4a.** (round 1 via throwaway scripts; command still to build) `scan-train-ocr`: export confirmed word crops and their text (`.png` plus `.gt.txt`), held out from gold.
- [x] **4b.** Fine-tune `tel_best` with `lstmtraining` (CPU), then plug the model in through `--ocr-model`.
- [x] **Gate 3.** Round 1: 8.7% → 7.5% letter error rate on gold. Score model n+1 against model n on gold, and keep it only if it is better.
- [x] **Round 3.** Whole book, 20,497 lines: `tel_ns3` scored 6.2% against `tel_ns2`'s 6.3%, so it plateaued. Causes: training lines only repeat the current model's own readings, and `ఁ` cannot be encoded (see status).
- [x] **5 (C). Faster labelling.** Done: an exact letter-count filter in `solve` (3 h 20 min → 8.4 min, identical output) and a resumable page-by-page word cache.
  - `read_words` reads and caches page by page, so memory holds one page and an interrupted run resumes.
  - Profile `infer` on the whole book and fix the root cause.
  - Results must stay identical (`scan-labels.tsv` unchanged).
- [ ] **6 (A). Extended character set.**
  - `scan-train-ocr` adds letters that confirmed lines need but the base model lacks (`ఁ`).
  - Steps: build a new unicharset with `unicharset_extractor` and `merge_unicharsets`, make a starter model with `combine_lang_model`, then `lstmtraining --old_traineddata`.
  - Fresh model `tel_ns4`, kept only if it beats `tel_ns2` on gold.
- [~] **7 (B). Disagreement review.** Sheet built (`scan-disagreements`), waiting for the user's corrections.
  - A sheet of complete words where our reading and the OCR reading differ, grouped by their difference pattern and ranked by count.
  - The user corrects words. The corrected words feed conversion (as human-confirmed) and become training lines for the next model (`tel_ns5`).
- [ ] **Gate 4.** Score `tel_ns4` and `tel_ns5` on gold against `tel_ns2`.
- [ ] **4c.** Optional: a GPU PyTorch recognizer. It only helps once the training data carries errors (step 7), because the model is not the limit.

## Risks & mitigations
- **Re-expressing the gap constants changes Prasaaskhara.** Mitigation: the page-51 check on every change, with its round-5 state archived at `files/<book>/archive/2026-10-07-round5/`.
- **Stroke repair could fuse neighbouring letters.** Mitigation: join only fragments well below letter size that sit within a few pixels; measure grouping errors on gold.
- **The model learns our mistakes.** Mitigation: train only on confirmed words, keep gold out of training, and gate every model on gold.
- **Too little training data in the first round.** Mitigation: use 20+ consecutive pages and corrections from the misses page.

## Verification / acceptance criteria
- `pytest` and `lint.cmd` are green, and `/code-review` runs before each commit.
- Each gate reports gold accuracy for ours, OCR model n and stock Tesseract, plus Prasaaskhara page 51.
- Target: Naishadamu gold accuracy of 90% or more after Gate 3, with Prasaaskhara page 51 at 95/99 or better.
