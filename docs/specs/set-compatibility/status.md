# Status: compatibility of the 15-volume Maha Bharatham set (`files/set/`) with the Anu golds
_Last updated: 2026-10-02_

## Current state
sanity check done; no code changed. Vol 3 is complete (see `docs/specs/vol3-sabha-parvam/`).

## Method
Per volume: font families and how each stores its codes; conversion with both golds (families outside the profile treated as Anu to measure compatibility); glyph-shape matching against the same typeface in Vol 3. Scratch scripts and per-volume JSON are in the ignored `docs/temp/set-sanity/`.

## Result

| Group | Volumes | Gold coverage | What it needs |
|---|---|---|---|
| Ready | 2, 4, 5, 6, 7, 10, 11, 14, 15 (and 3, done) | 99.99–100% with both golds | add families to `fonts/anu/profile.json`; spot-check the rare codes |
| Front matter | 1 | 99.07% (gold 2), 98.79% (gold 1) | skip Type3 fonts (pages 1–22 use one Type3 font per page, with control-character codes); the body is Vol 3's encoding |
| Different encoding | 8, 9, 12, 13 | 93.4–93.8% (gold 2), about 75% (gold 1), but the text is garbled | decode the Type1 subset fonts (below) |

**Ready volumes.** Same U+F000 + byte symbol fonts as Vol 3. Families missing from the profile:
- `AnupamaThin`: 53,072 characters in Vol 15;
- `GowthamiNarrow`: 219 in Vol 6 and 35 in Vol 15;
- `PallaviMedium`: 76 in Vol 2.

`TeluguNumbers*` (hyphens), `Dingbits*`, `Wingdings`, `Perpetua`, `Jyothi` (2 characters per volume) and `Gautami0100~…` (Type1, a handful of characters in Vol 1) are not Anu text.

**Volumes 8, 9, 12 and 13 (Bheeshma, Drona, Shanti parts 1 and 2).**
- Headings in GowthamiThin, GowthamiBlack, GowthamiExtraBold and Priyaanka are symbol-coded and fine.
- The body fonts (`PallaviBold`, `AnupamaMedium`, and `GowthamiMedium` in Vols 8–9) are Type1 subsets, 9–11 per family per volume.
- They are not Mac Roman: `æ` is really Vol 3's byte 0xAC, `ü` is 0x5E, `ú` is 0x5F, and so on (found by exact glyph matching).
- Decoding every subset font gives 0 conflicts across subsets, so the encoding is fixed per family: PallaviBold 112 chars, AnupamaMedium 93, GowthamiMedium 75, identical across the four volumes.
- The decoding only reaches about 35% of uses. The remaining characters (`’ ç † ª ´ ® © í …`) are not in the embedded fonts' character lookup, so glyph matching through `has_glyph(char)` cannot reach them.
- Next spike: get the raw content-stream codes, or render each glyph from the page, and match those against Vol 3's glyphs.
- Three codes with different Unicode spellings of known Mac Roman bytes also need aliases: `∆` U+2206 (gold has `Δ` U+0394), `Ω` U+2126 (gold has U+03A9), and `–` U+2013 (byte 0xD0, gold has `-`).
- `˛` (about 10,000 uses per volume) is a new code.

## Run: the nine ready volumes (2, 4, 5, 6, 7, 10, 11, 14, 15)
- All 15 PDFs moved to `files/<slug>/input/`. The `files/set` copy of Vol 3 was byte-identical to the one already in the layout and went to `archive/legacy-2026-10-01/duplicates/`.
- Profile gains `AnupamaThin`, `GowthamiNarrow` and `PallaviMedium`.
- Final output for both methods in `files/<slug>/output/<method>/` (about 6,600 pages), coverage 99.99–100%.
- **Gold 2 (shape naming)** leaves 9 distinct unmapped sequences in 115 places:
  - `∏` 34: the top of ొ over హ (హొయలు);
  - `”` 23: drawn as `÷`, a word separator (ఇట్లు÷అనియెన్);
  - `&` 10: ఞ (భుఞ్జీత, చఛజఝఞ);
  - `˛` 7: drawn as `×`, between antonym pairs (రుచి×అరుచి);
  - stray strokes in 41 places: `è` 33, `î` 4, `ä` 2, `¶` 1, `ù` 1, as in అతిథి⟦è⟧.
- **Gold 1 (OCR learning)** leaves 59 distinct sequences in 811 places; it has not learned these volumes.
- The methods give identical text on 85–99% of pages per volume; 661 differing places are gold 1 gaps. Only 55 are real disagreements, and gold 2 is right in all those I checked:
  - gold 1 reads ఫ్యూడల్, ఫూత్కారము as ఘ్యాడల్, ఘాత్కారము;
  - gold 1 writes ే as ేె (Vols 2, 14, 15);
  - Vol 14 has ◌ె left over in gold 2, and an extra ె in gold 1, where the print reads కే / వారే.

## Gold 2 follow-up for the nine volumes (decision: stay with gold 2, no `learn` for these volumes)
- Names confirmed visually by the user:
  - `∏` `o_top`, part of ొ (హొయలు); recipe `ha_base tick_pa aa_long o_top` → హొ;
  - `”` `divide` ÷ (word separator);
  - `&` `nya_base` ఞ;
  - `˛` `times` ×.
- Recipes for the six leftover `◌` placeholders, from glyph orders seen in the print:
  - `e_hook_pre ee_hook_pre` → ◌ే (కే, వారే in Vol 14);
  - `ra_vattu anusvara da_base` → ంద్ర (ఇంద్రులు, మహేంద్ర) and `… dda_base` → ండ్ర (తండ్రి);
  - `e_hook_pre e_hook_pre` → ◌ె (a doubled pre-base e, పెదవుల).
- Effect: 78 word changes in the first rerun, all intended, plus 3 pages in Vols 6–7 for the last two recipes. Mahabharatamu and Vol 3 are byte-identical to before.
- User decisions on the last 45 places (visual review in `docs/temp/set-sanity/review.html`):
  - `è`, `î`, `ä`, `ù` are silent (`∅`); `è` followed by ే is silent too (recipe `stroke_low ee_hook` → `∅`);
  - `¶` is silent only before ్ణ (recipe `stroke_dot tick_pa sub_nna` → ్ణ);
  - `◌ెంండు` is రెండు (recipe `e_hook_pre anusvara anusvara` → `◌ెరం`: the ra is drawn as the anusvara circle);
  - `◌్రప్రే` is ప్రే (recipe `ka_base ra_vattu tick_ka` → క).
- A recipe's Unicode can now be `∅`, like a shape's (small change in `shape_naming/shapes.py`, with a test).
- Result: all 11 finished books have 0 unmapped sequences; Mahabharatamu and Vol 3 are unchanged. Two places remain:
  - a lone `„` (ra vattu) in Vol 7 p107, which leaves `◌్ర`;
  - `భైైక్షభో` in Vol 14: the same overstrike as `è` + ే, but with ై, not yet confirmed.

## Vol 1 and the last two decisions
- `భైైక్షభో` (Vol 14) is right as printed: no recipe.
- A lone `◌్ర` comes out as `్ర` (Vol 7 p107). The rule lives in `telugu.finish`, the last step of `convert.render`, so the learner and solver still see the `◌` placeholder.
- Vol 1: the body (p23 on) is the Vol 3 encoding and converts with 0 unmapped sequences and no leftovers.
  - Front matter pages 1, 3–19, 21 and 22 (foreword, preface, introduction) are set in Type3 fonts whose codes are arbitrary per page, so they cannot be decoded with an Anu mapping.
  - `page_lines` now skips Type3-font text instead of passing control characters through, and the manifest records those pages as `result.skipped_type3_pages`. A warning is logged on every run.
  - No other book has Type3 text.
  - These 20 pages still need another route (page OCR, or the glyph-id clustering POC); not done.
- Manifest layout: run results are nested under `result` (pages, coverage, unmapped sequences, skipped Type3 pages). All 12 finished books were regenerated with it.
- Status: Mahabharatamu and Vols 1–7, 10, 11, 14, 15 are finished (gold 2). Vols 8, 9, 12, 13 remain (Type1 subset fonts with a scrambled encoding).

## Why Volumes 8, 9, 12 and 13 differ (investigated, nothing converted yet)
- **Different build of the same typefaces.** The body fonts (`PallaviBold`, `AnupamaMedium`, and `GowthamiMedium` in Vols 8–9) are Type1/CFF fonts embedded in full (about 230 glyphs, 3–11 copies per volume, all identical). They have no `/Encoding` entry and no ToUnicode, so the text layer gets its characters from the glyph names inside the font.
  - The glyph designs are the same as the symbol-coded TrueType fonts of the other volumes (161 of 226 Pallavi glyphs match a known Anu glyph at IoU ≥ 0.9; many of the rest are glyphs Vol 3's subset fonts never contained).
  - The glyphs sit on different codes: Anu byte 0x41 is on `V`, 0x45 on `W`, 0x47 on `Y`, 0x49 on `I`. It is not cp1252, Latin-1, Mac Roman or the Adobe standard order, and the `/Widths` table does not match either, so there is no formula.
  - Within a volume all copies of a family's font have the same layout (226/226 glyphs). The layout is consistent across the four volumes and across the three families (154 characters decoded, 1 ambiguous glyph).
  - The headings (GowthamiThin, GowthamiBlack, GowthamiExtraBold, Priyaanka) in the same volumes are symbol-coded and fine. So each of these volumes mixes the two layouts, by font.
  - Today's conversion reads the Type1 characters as Anu characters, which gives garbled words that look 93% covered.
- **How far automatic matching goes.**
  - Exact pixel matching decodes about a third of the uses.
  - Best match against every finished volume's fonts is confident for 36–50% of uses; the rest have near-identical candidates (IoU 0.83–0.97).
  - Every Anu byte is used exactly once (226 glyphs against 214 known bytes), so the leftover glyphs must take the leftover bytes. An optimal assignment agrees with the best match on about 200 of 226 glyphs; hiding 25% of the unambiguous matches and solving them recovers 25 of 30 for Pallavi (10 of 10 each for the other two, from tiny samples).
  - So a translation table from shape matching plus assignment gets most of it; the doubtful glyphs need to be checked by eye.

## Open questions
- Whether to commit to the per-family decode table for the Type1 volumes, or to a content-stream-code decode (`fonts/anu/` would get an `encodings/` entry per scrambled family, chosen per book).
- Which volume to take next. The ready group is the cheapest: add the families, run `convert`, and review the rare codes.
