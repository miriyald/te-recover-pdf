# Status: Anu (ASCII) Telugu PDF → Unicode
_Last updated: 2026-10-01_

## Current state
in progress: batch 1 and batch 83 both at 0 gaps; awaiting approve

## Completed
- v0.1 (bulk EM) produced the seed; page 6 confirmed clean (`tests/fixtures/page-6.golden.txt`); user-confirmed fixes ్క ్ఛ ్వ ఢ
- Fresh design: page-by-page anchored gap extraction (see design.md)
- Seed migrated: `mappings/mapping.tsv`, 548 entries, empty audit columns
- `progress.tsv` seeded with pages 6–10 (all 0 unmapped, so no OCR was needed)
- 41 unit tests green, `lint.cmd` clean; regression page 6 identical, pages 6–10 at 100 %
- Replay (seed minus `¯ ﬁ _è»`, pages 6–11):
  - `¯ → ్క` relearned on p7 (`first_word` జరత్కారుని); page 8 then needed no OCR
  - `_è»` held in pending (single occurrence, OCR read ధ; correct is ఢ)
  - `ﬁ` not learned on p9: its only occurrence had OCR బుషి for ఋషి, so verification rejected it (as designed)
  - Resume from `progress.tsv` and `--stop-after` verified
- **Batch 6 (pages 6–10) approved** by user → `verified/page-006 … 010.unicode.txt`; page 6 byte-identical to golden
- `approve` command added; `docs/temp/` cleaned: v0.1 outputs → `archive/2026-10-01-v0.1-bulk-discovery/`,
  replay → `archive/2026-10-01-replay-test/`, batch-6 → `archive/batches/batch-6/`. Page outputs now written with LF.
- Found and fixed: the Tesseract confidence gate rejected correct rare conjuncts (conf 21/50), so it now gates only suspects. CRLF in state files fixed to LF.

- **Distinct-context rule** (user decision): accept only when ≥ 2 distinct gap contexts (known letter before|after) agree.
  Distinct word strings alone would not have caught దీర్ఘతముడను / దీర్ఘతముడు.
- `learn` now starts at page 1 and skips pages in `progress.tsv`.
- **Pre-base rule:** `„ → ◌్ర`; `normalise` moves it after the next consonant cluster (త్రెంపు, శతభ్రాతల).
- Seed corrections, each confirmed by an image: `K«Ûù→చ్ఛ`, `KåÛù→చ్ఛా`, `=Úﬂ→మ్ను`, `„→◌్ర`.
  This fixed 3 errors in verified pages 7 and 10 (పృచ్ఛ, కచ్ఛప, త్రెంపుకొనుట), and those files were updated.
- **Batch 1** (pages 1–5, 11–82): 11 new entries, 35 pending. `…` (correct ్ఘ) was blocked by 4 conflicting OCR readings.
- After the batch: removed seed entries `` `«ˆ→త ``, `Oˆ→ం`, `Åˆ→ల` (they swallow the next letter's pre-base sign `ˆ`) and the
  compensating learned `H→కే`. Batch-1 page outputs were regenerated.

- **Confirmations loop:** report rows have "correct" boxes and a Download confirmations.tsv button, and `confirm --batch N` applies them.
  Batch 1: 23 user confirmations gave 14 new entries (incl. `…→్ఘ`, `¢→◌్ర`, `·→ౖ`, `ÔH·→కై`, `ˆQ→గే`); 9 were already
  correct. All 23 words verified in the rebuilt pages; verified pages 6–10 unchanged. 175 gap occurrences remain in batch 1.
- Found and fixed while solving: widening must keep an anchor (it could otherwise re-map a whole word); right-first widening
  (otherwise `Ô`/`ˆ` become silent inside the previous letter); NFC dedupe of candidates.

- **Suspicious-mappings register** `mappings/suspicious.tsv` (glyphs, suggested, status, reason, page, word):
  `accepted` rows are applied by `confirm`; `open` rows are only listed in the report with every affected word in the batch.
  `B → ఔ` accepted (v0.1 seed had జె; OCR misreads ఔ as జె, 24 occurrences, 6 images checked). `Q`, `Ò` open.
- Batch 1: rounds 3–4 of confirmations brought gaps from 34 to **0**. చతుర్థ→చతుర్ధ held back (same glyph `÷` is confirmed థ in
  ప్రార్థించగా). The ఘూర్జిక typo is corrected to ఘూర్ణిక (image). Overrides are now shown per confirmation.
- **Batch 83** (pages 83–449, end of book): only 2 new OCR entries, so the stop-after limit was never reached. 118 gap occurrences
  remain in 72 distinct words. Fixed: pages written before a later acceptance were stale; the batch now rewrites all pages at the end.

- **OCR cache** `docs/temp/ocr-cache/page-NNN.json`: each page is OCR'd at most once. Runs log `ocr_calls` / `ocr_cache_hits`.
  First rebuild: batch 83 = 31 calls (of 367 pages), batch 1 = 43 (of 77). Second rebuild: 0 calls (29 s and 13 s).
- Batch 83 confirmations: 16 added, 9 already correct, 3 not found (`+‘` already learned). Held: ఝుంగ (same glyph `~°≠` is ఝ in
  ఝామున). Image-corrected: పరాఙ్ముఖుడవు. `⟦U+00A0⟧ → &`. Batch 83 gaps 118 → **14**; batch 1 stays 0.

- Batch 83 round 3: 6 confirmations (5 added, 1 already correct via `‹ → ె`); gaps 14 → **2**. Both batches re-ran with 0 OCR calls
  (all pages cached). Remaining: స్పు⟦ù⟧రణకు, హర్షోత్పు⟦ù⟧ల్ల (aspiration stroke `ù` after పు; expected ఫు).

- Final confirmations: `Êù → ్ఫ` added (హర్షోత్ఫుల్ల); స్ఫురణకు became correct through it. **Both batches at 0 gaps**, 0 OCR calls.

- **v0.3.0, new-font tooling** (see `new-font-playbook.md`): `profile` (font families + ink band as JSON, threaded through
  `page_lines`/`convert_page`/`LearningState`; default = the Anu profile, so this book's output is unchanged), `probe`
  (fonts, mark glyphs, ink band measured from the font outlines), `atlas` (every glyph unit drawn from the embedded font, with
  label boxes and a downloadable `labels.tsv` that is already a mapping file). 89 tests green.
  Findings: 601 distinct units in the book, the top 300 cover 99.65% of occurrences; probe ink band 0.66/0.34 matches 69.7% of words
  to OCR vs 61.8% for the hand-picked 0.75/0.35 (not adopted as default yet).

## Blocked / open issues
- Decide whether to adopt the probe's ink band (0.66/0.34) as the default profile. It only affects word↔OCR matching, not the mapping.
- Not built yet: lexicon check in the suspect report; coverage-driven page order.
- `ˆ` and `Ô` behave as **pre-base vowel signs** (ే / ె) like `„`. The seed still has compensation entries (e.g. `Q→గే`).
  Proposed: model them like `„` (`ˆ→◌ే`, `Ô→◌ె`) after an image check. Awaiting decision.
- **Correlated OCR error:** replay accepted `… → ్ధ` from two occurrences of దీర్ఘతము (correct ్ఘ). The same would happen live.
  Proposed fix: require ≥ 2 distinct words. Awaiting decision.
- Seed contains suspicious learned entries, e.g. `„ → (`, `K«Ûù → చ్చ` and `KåÛù → చ్చా` (should be చ్ఛ / చ్ఛా)

## Next steps
1. Decide the distinct-word rule
2. Fix suspicious seed entries
3. `anu-unicode learn --stop-after 10`, review `docs/temp/batch-11/report.html`, then `anu-unicode approve --batch 11`; repeat
4. `docs/temp/_deps/` (numpy/scipy, ~190 MB) and `docs/temp/page4.png` were not created by this work; owner to decide
