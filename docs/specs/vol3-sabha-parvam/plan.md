# Plan: convert Maha Bharatham Vol 3 Sabha Parvam with the Anu golds

_Design: `design.md`. JIRA skipped._

## Scope
In: PUA symbol-code translation in the profile and glyph extraction, the new families in `fonts/anu/profile.json`, coverage and contact sheets for the new codes, then naming, learning and cross-checking on Vol 3.
Out: mapping the DingbitsThree ornaments; the hybrid bootstrap.

## Steps (ordered, checkable)
- [x] 1. Branch `vol3-sabha-parvam` from `approach-refactor`; write this spec; correct the stale Vol 3 notes in `docs/specs/approach-refactor/design.md` and `docs/specs/hybrid-bootstrap/plan.md`.
- [x] 2. `FontProfile.byte_encoding` / `byte_overrides` (JSON round trip, `DEFAULT_PROFILE` equal to `fonts/anu/profile.json`); `font_family` drops a `,Style` suffix; `_span_glyphs` translates U+F020–F0FF; new families in the profile; tests. Mahabharatamu: all 449 pages byte-identical, `compare` 0 differences, page 6 0 errors.
- [x] 3. Vol 3 coverage per font (expect about 1.9% unmapped); `sheets` and `atlas` for Vol 3. **Hand off to the user to name the new codes.**
- [ ] 4. After naming: `shapes`; `compare --pdf` Vol 3; `quality` on Gowthami-heavy and Anupama-heavy sample pages; `learn` on Vol 3 for gold 1; record results; bump to 0.6.0.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| A code means something different in the Gowthami design | `compare` with Tesseract votes and `quality` on per-font sample pages |
| The Anu ink band (`ascent`/`descent`) crops Gowthami badly | check the report crops; rerun `probe` on Vol 3 if needed |
| Mahabharatamu output drifts | its PUA characters are U+F8FF, outside the translated range; full 449-page diff |

## Verification / acceptance criteria
1. `lint.cmd` clean; `pytest` green with the new tests.
2. Mahabharatamu unchanged: 449 pages identical, `compare` 0 differences, page 6 0 errors.
3. Vol 3 unmapped glyphs fall from about 1.9% to near 0 after naming; the two golds agree on Vol 3, or every difference is triaged.
