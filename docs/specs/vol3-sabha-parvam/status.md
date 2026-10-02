# Status: convert Maha Bharatham Vol 3 Sabha Parvam with the Anu golds
_Last updated: 2026-10-01_

## Current state
in progress: gold 2 covers Vol 3; gold 1 still has to learn the new codes

## Completed
- Font analysis (findings in `design.md`).
- Step 2: `FontProfile.byte_encoding` / `byte_overrides`; glyph extraction turns U+F020–F0FF into Anu chars; `font_family` drops `,Style`.
  - New families are in `fonts/anu/profile.json`.
  - `EmbeddedFonts` (atlas, sheets) draws Anu text through a font's symbol codes.
- Step 3, Vol 3 (404 pages, 107,903 words): coverage before naming was 98.5% with either gold; atlas 216 codes, 205 named.
- Naming, with the user's decisions:
  - **Gold 2:** 11 new names, all visually verified by the user:
    - `equals =`, `arasunna ఁ`, `u_hook_sub ు`, `sub_lla ్ళ`, `sub_pa_u ్పు`;
    - `π`/`∑` as `virama`;
    - `bar |` (so `II` gives `||`, e.g. `డా||`);
    - `slash`, `percent`;
    - `Ø` as `blank` (a space; it draws as a blank with width).
  - **Gold 2 recipes:** `rii inner_dot` → ఠీ (కంఠీరవ); `ra_base jha_tail` → ఝ (Gowthami draws ఝ without the tick).
  - **No recipe for `÷û`:** the user confirmed the థ-first order (వక్షస్థలం) is right.
  - **Gold 1:** the visible-virama entries `±`, `<£`, `<£û` and `^£` now end with a ZWNJ, like `ò` already did.
- Results:
  - Gold 2 converts Vol 3 at 100% coverage; 1 unmapped sequence is left (see below).
  - Where both golds give full text on Vol 3, they now agree on every word.
  - Mahabharatamu: all 449 pages byte-identical; `compare` 0 differences.
  - 152 tests pass, lint clean.

- Gold 1 on Vol 3, batch 1 (`learn` over all 404 pages, 340 OCR calls):
  - 11 entries learned; 9 were right and 2 were Tesseract misreads (`II` → `!`, `ñ` → `(`).
  - With OCR votes, all 513 words where OCR voted against gold 2 were the same two misreads; gold 2 was right.
  - `confirm` with the user's confirmations added `´` =, `ü` ్‌, `Ñ¶π` ఫ్‌, `Õ` ే, `á¶È` ఫొ, `ãπ` స్‌, `"£∞` మ్‌, `` `«Êù `` త్ఫ.
  - Hand fixes for the held overrides: `II` → `||`, `ñ` → ఁ. Visible-virama entries carry the ZWNJ.
- Two `confirm` fixes found on the way:
  - `=` attached to tab-separated text was taken as a separator;
  - the solver gave up when the only difference between two answers was a ZWNJ; it now keeps the one that reproduces the confirmed text exactly.
- Gold 2 recipe `va_base virama u_hook` → మ్‌ (నరోత్తమమ్, వాల్యూమ్): the user's తన్ముఖమ్ confirmation showed gold 2 rendered వ్‌ు.
- Result: Vol 3 `compare` fell from 7,265 difference groups to 37; Mahabharatamu still has 0 and is byte-identical to the baseline.

## In progress
- Gold 1 batch 2: the remaining gaps (`I` alone 827, `చ.` 34, `ఆంధ్రప్రదేశ్‌` 6, a few single words).

## Blocked / open issues
- A stray `è` (stroke_low + tick, drawn over a complete థ/ధ) is left as an unmapped gap in ప్రథ⟦è⟧మ and దుర్యోధ⟦è⟧నాది. It looks like a typist's overstrike.
- `నిరఝరము` is converted faithfully from the glyphs; the dictionary form is నిర్ఝరము.
- Print quirks are kept as printed: `వేెంకటేశ్వరరావు`, `నరోత్తమవ్‌ు`.
- The 3 DingbitsThree ornaments come out as letters (`U`, `P`, `S`).

## Next steps
- Gold 1: `learn` on Vol 3, then `confirm` / `approve`.
- `compare --ocr-missing` and `quality` on Gowthami-heavy and Anupama-heavy sample pages; bump to 0.6.0.
