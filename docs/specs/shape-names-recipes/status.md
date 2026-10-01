# Status: shape names + recipes
_Last updated: 2026-10-01_

## Current state
done (pending commit; nothing committed)

## Completed
- Steps 0–7 of the plan; branch `shape-names-recipes` (JIRA skipped by the user).
- Iterations against the original reference:

| Iteration | Recipes | Coverage | Difference groups |
|---|---|---|---|
| first labels | 14 | 99.08% | 8,614 |
| pre-base signs, ai = ె + ౖ via NFC, మ/య hook family | 23 | 99.96% | 2,866 |
| హ tail, థ vs ధ strokes, యి | 27 | 99.95% | 1,212 |
| ra-vattu last, ఘ/ఠ/ఢ, ticks named by host | 40 | 99.98% | 368 |
| ఛ/ధీ/ఠి, ఝ tail, visible virama = ్ + ZWNJ | 48 | 100% | 178 |
| హై, వ్యూ, ఘూ, ్ర before ్య, `&`, redundancy rule fixed | 51 | 100% | 170 |

- Code review: four findings fixed (canonical subscript order, straddle-aware redundancy, OCR quote translation, single-name recipes rejected).
- Round 2, after the owner corrected `mappings/mapping.tsv` (now 655 lines, sha256 `83e2d177…d51a6a`):
  - `∂` split out as `hook_aa`; the వ్యూ recipe was removed (ధౌమ్యాదులు fixed).
  - Visible virama moves after the subscripts drawn after it (పబ్లికేషన్స్‌).
  - Result: 50 recipes, 517 entries, **10 differing words**, none a known shape-mapping error. 126 tests, lint clean.

- Committed as `8dd1fb3` (the user's `mappings/mapping.tsv` left unstaged).
- 10-page check against old batch outputs: 11 of 1,418 words changed, all corrections.
- Round 3: ZWNJ after a virama not followed by a consonant is now a pipeline rule (`mark_visible_virama` in `render`), and every comparison with outside text uses `comparable`. Whole book: 2 differing words. 136 tests, lint clean.

- Round 4: reference fixed for the `Ô` / `~` compensating pair (−6 entries, 1 changed, 1 added). Shape mapping and reference agree on all 77,191 words.

## Decisions taken
- పంచయజ్ఞ (p. 410) is a PDF typo; no mapping change. A word-level errata list would be the place for it if wanted.
- ZWNJ is mainstream: every mapping's output gets it; comparisons ignore it.
- Keep the canonical subscript order in the shared `normalise` (corrects 7 reference words).
- Visible virama keeps ZWNJ.
- పంచయజ్ఞ (p. 410) is left as a print glyph slip; there is no rule for one occurrence.

## Blocked / open issues
- `verified/` location unknown (gold check used page 6 only).
- Reference still lacks ZWNJ on 8 words and ె in మనకెట్టి (see `validation.md`, round 2).

## Next steps
- Commit and open a draft PR (ship workflow) when the user asks.
