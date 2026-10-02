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

## Open questions
- Whether to commit to the per-family decode table for the Type1 volumes, or to a content-stream-code decode (`fonts/anu/` would get an `encodings/` entry per scrambled family, chosen per book).
- Which volume to take next. The ready group is the cheapest: add the families, run `convert`, and review the rare codes.
