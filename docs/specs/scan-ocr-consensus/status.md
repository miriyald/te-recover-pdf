# Status: Scan OCR consensus
_Last updated: 2026-10-06_

## Current state
In progress: implementation is done and the pilot run is next.

## Completed
- Exploration and root cause: the shape spike comes from fused glyphs and the two bars of `=`, not from the page border.
- Spike on pilot pages 51, 67, 11, 103 and 175. The revised design was approved.
- Archived the old state to `files/<book>/archive/2026-10-06/` and `fonts/scan-prasaaskhara/archive/excluded-2026-10-06.tsv`. The page-51 gold word boxes are saved as `docs/temp/scan-spike/gold/page-51-occurrences.tsv`.
- Plan steps 3–10:
  - `=` detection (`words.is_equals`, `index.EQUALS`);
  - `word_ocr.py`, `glyph_ocr.py`, `inference.py`, `review.py`;
  - the conversion merge;
  - the commands `scan-label` and `scan-review`;
  - removed `scan-atlas`, `scan-pages` and the exclusion list;
  - `--pages` accepts comma lists;
  - version 0.13.0.
- `pytest`: 242 passed. `lint.cmd`: OK.

- Fixed two defects the pilot found:
  - an `=` lower on a skewed line started a line of its own (`_lines` now compares each word with the whole line's band);
  - Tesseract's stray quotes reached the output (`clean_ocr`).
- Pilot run (pages 11, 51, 67, 103, 175):

  | Measure | Result |
  |---|---|
  | Shape ids | 617 (350 seen once) |
  | `=` words found by geometry | 248 |
  | Glyph coverage of the automatic labels | 86.9% (389 ids labelled: 43 seeds, 346 from words) |
  | Words choosing our reading (it agreed with OCR) | 391 |
  | Words using word OCR | 123 |
  | Disagreements | 9 |
  | Page 51 exact words, pipeline | **94/99**, with no review |
  | Page 51 exact words, Tesseract word crops | 94/99 |
  | Review sheet | 50 rows covering 196 occurrences: 26 unlabelled, 21 low agreement, 3 `∅` on a main-band piece |
  | Flagged ids seen at least twice | 55 |

  - The page-51 misses are all systematic Tesseract errors: ఁ ×2, ద/ధ, జ్జ and ఱ→జీ.
  - Of the ids behind them, only ఁ (#236) is on the sheet. The rest are seen only once in 5 pages.

- Pilot gate: the user approved the whole-book run.
- Inference speed-up for book scale:
  - `_solve` builds only the word's local mapping;
  - refinement samples 40 words per id.
- Whole book (198 pages with text):

  | Measure | Result |
  |---|---|
  | Shape ids | 6,034 (3,118 seen once), over 83,761 glyphs |
  | `=` words | 9,442 |
  | Labelled ids | 3,563 (418 seeds, 3,145 from words) |
  | Glyph coverage | **94.3%** |
  | Words agreeing (ours used) | 15,592 of 21,174 (74%) |
  | Words using word OCR | 5,372 |
  | Words with a gap | 210 |
  | Disagreements | 2,524 |
  | Page 51 exact words | 94/99, unchanged; the misses are the same 5 Tesseract errors |

- Review flag calibrated from the data. Agreement of frequent ids has a median of 0.86 and a 5th percentile of 0.62, so the line moved from 0.9 to 0.6. The flagged ids seen at least 5 times dropped from 1,124 to 244.
  - First sheet: 50 rows covering 4,688 occurrences.
  - It includes ఁ (#236, 452 occurrences, unlabelled), `(` (#1994, agreement 0.07), చు/డు/పొ at about 0.5, and ప #36 at 0.0.
- The page-51 misses ఱ, జ్జ and ద are fused shapes seen 1–4 times. Top-X review does not reach them; they keep Tesseract's reading.

- Review round 1: 44 decisions in `fonts/scan-prasaaskhara/scan/decisions.tsv`. Corrections agreed with the user:
  - The crescent ids 236, 410, 1994, 2285, 2934 and 3087 are ఁ, not `(`. They appear mid-word about 1,240 times, and Tesseract reads them as `(`.
  - `ppu` became `్పు`.
  - The shape names `blob`, `dot`, `e_top` and `ai_bottom` were dropped, so the words label those ids.
- Results after round 1:

  | Measure | Result |
  |---|---|
  | Glyph coverage | **95.3%** |
  | Words agreeing with OCR | 15,664 |
  | Words read through a decided id (our reading kept over OCR) | 1,747 |
  | Words using word OCR | 3,583 |
  | Words with a gap | 180 |
  | Disagreements | 1,395 (down from 2,524) |
  | **Page 51** | **95/99**, above Tesseract's 94/99. The fixed word is గోఁచి. |

  - A sample of the decision-backed words shows that ఁ is restored throughout: డోఁగు, తెలుఁగు, మేఁక, తాఁకు.

## Blocked / open issues
- A word-final period is lost when it is smaller than `MIN_AREA` (40 px): it is dropped before words are formed, although Tesseract sees it.
- The ఱ, జ్జ and ద misses on page 51 are fused shapes seen 1–4 times, so top-X review does not reach them.

- Review round 2: 87 decisions in total.
  - Id 205 (the ె hook drawn before its consonant) was changed from `ె` to `◌ె`, because the plain form gave ెపడతల.
  - The review sheet now explains the `◌` convention.
- Results after round 2:

  | Measure | Result |
  |---|---|
  | Glyph coverage | 95.4% |
  | Words agreeing with OCR | 15,718 |
  | Words read through a decided id | 2,051 |
  | Words using word OCR | 3,228 |
  | Disagreements | 1,137 |
  | Page 51 | 95/99 |

- The round-3 sheet covers 744 occurrences (round 1 covered 4,688 and round 2 covered 1,884), so returns are falling off.

- Review round 3: 125 decisions in total. Id 3918 was changed from `ె` to `◌ె`, the same pre-base case as 205. Glyph coverage 95.7%, 1,070 disagreements, page 51 at 95/99.
- Compared with Tesseract over 30,616 word positions:

  | Change | Words | Note |
  |---|---|---|
  | `=` written as `=` | 9,429 | better; Tesseract never reads it |
  | ఁ restored | about 770 | better |
  | ఱ restored | about 113 | better |
  | Final period lost | about 400 | worse; specks below `MIN_AREA` |
  | ొ for ా | 79 | worse; one id has a wrong label |
  | ఎ for ఏ | 26 | worse; decisions 491, 1794 and 3889 look too broad |
  | ె for ై | 26 | worse; decision 2431 `∅` should be `ౖ` |
  | ద్ద for డ్డ | 16 | worse; one id has a wrong label |

- `/code-review` (medium) found three bugs, now fixed with tests:
  - `scan-label --pages` overwrote the book-wide labels, so `scan-label` no longer takes `--pages`;
  - multi-line glyph readings broke the cache;
  - repeated pages in `--pages` were indexed twice.
- `pytest`: 244 passed. `lint.cmd`: OK.

## Blocked / open issues
- Specks below `MIN_AREA` are dropped, so the final period is lost.
- Some decisions need correcting: 2431 → `ౖ`, and the ఎ/ఏ ids 491, 1794 and 3889. The ా→ొ id and the డ్డ→ద్ద id still have to be traced.
- Rare fused shapes (ఱ, జ్జ, ర్ద) are out of reach of the top-X review; a small classifier is a possible follow-up.
- The review sheet should warn when a plain vowel sign is given to a piece drawn before its consonant.

## In progress
- Commit, push and a draft PR.

## Blocked / open issues
- No JIRA ticket (the user chose to skip it).
- Systematic Tesseract errors on rare letters (ఱ) are labelled with high agreement, so they are not flagged. They need either more pages or a human glance at confirmed rows.

## Next steps
- The user reviews the pilot sheet, or approves the whole-book run.
