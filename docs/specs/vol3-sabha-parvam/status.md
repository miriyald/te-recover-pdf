# Status: convert Maha Bharatham Vol 3 Sabha Parvam with the Anu golds
_Last updated: 2026-10-01_

## Current state
blocked: waiting for the new codes to be named (step 3 hand-off)

## Completed
- Font analysis (findings in `design.md`).
- Step 2: `FontProfile.byte_encoding` / `byte_overrides`; glyph extraction turns U+F020–F0FF into Anu chars; `font_family` drops `,Style`.
  - New families are in `fonts/anu/profile.json`.
  - `EmbeddedFonts` (atlas, sheets) draws Anu text through a font's symbol codes.
  - 152 tests pass, lint clean.
  - Mahabharatamu: all 449 pages are byte-identical, `compare` finds 0 differences on 77,191 words, and page 6 matches the golden fixture.
- Step 3, Vol 3 (404 pages, 107,903 words):
  - Coverage: gold 2 98.54%, gold 1 98.48%.
  - Atlas: 216 codes, 205 already named.
  - `compare` (no OCR): 385 groups, but only 6 where both golds give full text. All 6 are gold 1 dropping the ZWNJ after the visible virama `±` before a consonant (`బ్లాక్మార్కెట్` for `బ్లాక్‌మార్కెట్`). Gold 2 is right. Every other group is a gold 1 gap that gold 2 composes (`ల్`, `ర్`, `స్`).
  - No sign that any code means something different in the Gowthami/Anupama designs.

## In progress
- Naming the 11 new codes: proposals in `docs/temp/vol3/new-names.draft.tsv`, sheet in `docs/temp/vol3/new-codes/sheet-01.png`.

## Blocked / open issues
- Unicode for the bar `I` / `II` (`|`/`||` or `।`/`॥`).
- `Ø` (1 occurrence) draws blank.
- Recipe `sub_tha sub_sa` → `్స్థ` (3 words).
- Gold 1: `±` entries need the ZWNJ, like gold 2's `virama`.
- Print quirks to keep or flag: `వేెంకటేశ్వరరావు` (`Õ≥`), `నరోత్తమవ్‌ు`.
- The 3 DingbitsThree ornaments come out as letters (`U`, `P`, `S`).

## Next steps
- After naming: `shapes`, then `compare` with `--ocr-missing` on sample pages, `quality`, and `learn` on Vol 3 for gold 1; bump to 0.6.0.
