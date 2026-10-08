# Status: Scan-shape pipeline pilot on *Sriharsha Naishadamu*
_Last updated: 2026-10-07_

## Current state
Done. The pilot is closed and its findings carry into `docs/specs/scan-workflow-v3/`. The draft recipes still await the user's confirmation.

## Completed
- **Layout.**
  - One column with no header or footer rules; an Arabic-numeral folio sits at the top.
  - Verse labels (`శ్లో॥`, `ప॥వి॥`, `టీక॥`) hang in the left margin, and specks run along the left edge.
  - Page 51 is ordinary text; only the IA OCR failed on it.
- **Index** (6 pages):

  | Measure | Value |
  |---|---|
  | Ink pieces | 5,440 |
  | Ids | 2,112 |
  | Singletons | 1,483 (27%) |
  | New ids per page | 494, 321, 578, 286, 258, 175 |

  Prasaaskhara had fallen to about 40 new ids a page by page 6. The singletons are mostly ordinary letters in another type size (verse, bold) and pieces of broken strokes. They are not frame noise.
- **Labels:**
  - 1,126 words, 415 of 2,112 ids labelled;
  - **glyph coverage 53%** (Prasaaskhara: 94%);
  - 421 words complete, 342 of them agreeing with Tesseract.
- **Review sheet:** 50 rows, all flagged, covering 621 of the 5,440 pieces.
- **Conversion choices:**

  | Choice | Words |
  |---|---|
  | word_ocr | 704 |
  | agreed | 342 |
  | equals | 55 |
  | gap | 42 |
  | unread | 38 |
  | Disagreements | 41 |

- **Page 201, against the draft gold of 170 words:**

  | Source | Exact words |
  |---|---|
  | Ours | 80 (47.1%) |
  | Tesseract word crops | 80 (47.1%) |
  | IA text layer | 84 (49.4%) |

  Our output equals Tesseract's because almost every word falls back to it.

## Findings (root causes)
1. **The word band is pulled down by tall subscripts.**
   - `words.py` `_band` takes the median top and bottom of the pieces between 0.7 and 1.3 body heights.
   - In this typeface the conjunct subscripts reach that size, so a conjunct-heavy word gets a band below its line.
   - On page 201, `దృష్టియన్నట్లు` has band 1552–1583 while its line sits at about 1500–1545. `జ్ఞానదృష్టి` ends up below line 12.
   - Such words move to their own line or to the next one, which garbles the reading order.
   - Stray subscripts form one-piece "lines" (lines 8 and 9).
2. **Punctuation that Tesseract misreads and the pipeline doesn't model:**
   - `।` and `॥` are read as `1` (25 words);
   - lone `ః` is read as `8`;
   - the stacked dots of `:` are split into two words, read as `ఆ` or `అ`.

   These are systematic, so one review decision each should fix them across the book.
3. **Ids don't recur.** Several type sizes and broken strokes give 2,112 ids for 1,126 words. Word inference needs ids that repeat, so 6 scattered pages cannot reach Prasaaskhara's coverage.
4. **Tesseract is weak on this book** (47% on page 201, against 94% on Prasaaskhara page 51).
   - Sanskrit conjuncts come out as `(` or `[`: `(పశాధి` for ప్రశాధి, `ఇం[దు(డా` for ఇంద్రుఁడా.
   - Visarga comes out as `8`.

   With so little agreement, labels can't be learned from it. The review sheet carries more of the load than it did on Prasaaskhara.

- The user confirmed the gold for page 201 as correct, so the scores above are final.
- **Review round 1:** 44 decisions, no recipes.
  - Glyph coverage rose from 53% to 59%; 20 words now come from reviewed ids. Page 201 is unchanged at 80/170.
  - The most frequent reviewed names are symbolic: `slash` (66 pieces), `pipe` (63), `tick` (38), `right_top` (20), `dot` (12), and the `*_base` names.
  - No recipe proposals came out, because there are too few words where Tesseract agrees to vote with. Those words stay as gaps or Tesseract readings until recipes are written.
  - Two rechecks fire, and both are wrong: `ః` (`8→ః`) and `.` (`ఆ→.`).
    - In both, Tesseract misreads a mark that word grouping split off as its own word.
    - The check trusts Tesseract, so it flags our correct decision.

- **Grouping fixes** (in `scan/words.py`, uncommitted):
  - **Root cause:** the page body height is the median of all piece heights. On this book that comes out at 43 px, while letters are 59–67 px; there is a second peak at 35–44 px made of letter bases whose tick broke off. As a result, the word band picked out the subscripts.
  - `_band` no longer depends on body height. The band is now the run of rows shared by at least half the word's pieces at their deepest point, and when runs tie, the run with the most coverage wins. This also joins Prasaaskhara's two-column rows into one line, as printed (page 67: 33 → 27 lines).
  - Stacked bar pairs are taken out before grouping and always form their own `=` word. Glued `=` fell from 40 to 1 on the pilot, against 1 of 293 on Prasaaskhara.
  - `pytest`: 274 passed. `lint.cmd`: OK.
- **After the fixes:**

  | Book | Measure | Before | After |
  |---|---|---|---|
  | Naishadamu | Page 201 exact | 80/170 (47.1%) | **94/170 (55.3%)** |
  | Naishadamu | Tesseract word crops | 80/170 | 94/170 |
  | Naishadamu | IA layer | 84/170 | 84/170 |
  | Prasaaskhara | Page 51 | 95/99 | 95/99 |
  | Prasaaskhara | Same as Tesseract | 19,116 | 19,133 |
  | Prasaaskhara | `=` written | 9,429 | 9,463 |
  | Prasaaskhara | ఁ restored | 1,044 | 1,034 |
  | Prasaaskhara | ఱ restored | 264 | 260 |
  | Prasaaskhara | Other (mostly worse) | 263 | 262 |

  Prasaaskhara's round-5 state is archived at `files/<book>/archive/2026-10-07-round5/`.

- **Recipes for the symbolic names.** Recipe proposal can't fire here because no word containing a symbolic name has all its other ids labelled. So Claude drafted `fonts/scan-naishadamu/scan/recipes.tsv` from boxed word crops (`docs/temp/scan-naishadamu/symbolic/`):
  - `slash` and `right_top` are fragments broken off a letter → ∅;
  - `na_base tick` → స;
  - `ra_base` → ర, `pu_base` → పు, `ha_base` → హ, `త_base` → త;
  - `pipe` → । and `pipe pipe` → ॥;
  - `dot` → `.`.
  - With the draft: page 201 is **102/170 (60.0%)**, against Tesseract's 94/170. Coverage is 60.5%.
  - The 5 rechecks are all Tesseract-trust false alarms: `1→।`, `8→ః`, `→.`, `ఆ→.`, `→(`.

- **Dependent signs join the word before them** (`scan/conversion.py`). A word whose text starts with a combining sign (category Mn/Mc, such as ః, ం or a vowel sign) is appended to the previous word on its line. A `.` or `,` just before the join is dropped, because punctuation can't precede a dependent sign, so Tesseract must have invented it.
  - The user confirmed `తావకైః` and `రైః` as the right words.
  - Page 201: **108/170 (63.5%)**.
  - Prasaaskhara: page 51 stays at 95/99. Its book had 20 words starting with a dependent sign, all pieces of split words.
  - `pytest`: 276 passed.

- **`/code-review` fixes:**
  - a word with no row shared by 3 pieces takes the band of its tallest piece, so a tick that overlaps its letter stays ABOVE;
  - an earlier id is reused only when its catalog band matches; this was the cause of the 60 mixed-band ids;
  - the two bars of `=` must be aligned and of similar length;
  - a dependent sign joins only a word that ends in Telugu script, never `=` or a gap.
  - Not changed, with reasons: the `=` band (only used for line joining), stripping punctuation before a sign (it is never valid), and moving the join into grouping (grouping has no labels, and visarga and colon look the same). The last is a known limitation for v3.
  - `pytest`: 280 passed. `lint.cmd`: OK. Version 0.15.0.
  - Prasaaskhara after the fixes, against round 5:

    | Measure | Round 5 | After fixes |
    |---|---|---|
    | Page 51 | 95/99 | 95/99 |
    | Same as Tesseract | 19,116 | 19,113 |
    | `=` written | 9,429 | 9,452 |
    | ఁ restored | 1,044 | 1,026 |
    | Invented periods dropped | 357 | 374 |
    | ఱ restored | 264 | 268 |
    | Other (mostly worse) | 263 | 266 |
    | Disagreements | 1,162 | 1,159 |

- **Workflow discussion (2026-10-07):** carried forward into `docs/specs/scan-workflow-v3/`.
  - The goal is near-perfect results compared with OCR.
  - Fine-tune OCR on our own confirmed output.
  - The machine has an NVIDIA RTX 4000 Ada laptop GPU (CUDA 13.2); Tesseract training cannot use it.

## In progress
- The user confirms the draft recipes.
- The user's note ":. might be ః ." is not yet acted on.

## Blocked / open issues
- Recipes for the symbolic names have to be written by hand on this book. Word evidence cannot propose them.

- The underestimated body height still makes the stacking gap too small: 0.3 × 43 = 13 px. Colon dots 13 px apart, and some subscripts such as the ్త of క్తి, are left as separate words.
- Visarga printed after a gap becomes its own word (`రై ః`).

## Next steps
These are proposals, for the user to decide:
- Redefine body height as the letter height, and re-express the gap constants so Prasaaskhara's thresholds stay where they are.
- Write recipes for the symbolic names (`pipe`, `slash`, `tick`, `right_top`, `*_base`).
- Re-run on 20 contiguous pages to measure coverage with recurring ids.
