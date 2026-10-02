# Plan: Scanned Telugu → Unicode via image glyph ids (Prasaaskhara Padakosamu)

## Scope
In: steps 1–9 of `design.md` for one book, ending in a converted, compared sample of pages and a gate verdict. The
pipeline moves from `scripts/index_glyphs.py` into a package `anu_unicode/scan/` once the gate passes (spikes stay scripts).
Out: Tesseract model training, other scanned books, lexicon check, edits to the Anu gold.

## Steps
### Phase 0: spikes (scripts, no package change), to decide before building
- [ ] Pin `numpy`, `scipy` in requirements.txt, requirements-dev.txt, pyproject.toml (the POC already imports them). Bump version.
- [ ] Page triage: classify all 199 pages (front matter / body / blank) by component count and column layout. Pick 20 sample
      pages by new-id yield.
- [ ] Layout spike on 3 pages: deskew, columns, lines, word gaps. Overlay PNG with line and word boxes. Manual check.
- [ ] Touching-sort census: share of components wider than 1.6× median akshara width on the sample. Decides whether *fused split* is needed.
- [ ] IA text-layer spike: words matched to geometric words by box overlap. Akshara-count agreement rate, IA vs Tesseract.

### Phase 1: positions
- [ ] `layout` + `components` + `syllables` → `files/<book>/output/intermediate/scan/positions.tsv`
- [ ] Unit tests on synthetic bitmaps: band assignment, x-overlap grouping, word-gap split, canonical order
- [ ] Overlay: syllable boxes coloured by tuple

### Phase 2: alphabet
- [ ] Cluster v2: tight online pass, median prototypes, chamfer merge gated by relative height and band. `catalog.json` + `merges.tsv`
- [ ] Repairs: fused split (if the census says so), broken join. Recorded per occurrence
- [ ] Gate report `gate.md`: coverage curve, new-id rate per page, singleton mass, top-100 duplicate spot check
- [ ] Prāsa-block check: second-syllable tuple identical within a headword block (counts of violating blocks)
- [ ] Unit tests: same shape → same id under ±2 px shift and stroke noise; `ం` ≠ `౦` by relative size; merge keeps the older id;
      a synthetic fused pair is split; a re-run adds no ids
- [ ] **Review gate with the user.** On a fail, iterate Phase 2 only.

### Phase 3: bridge into the existing pipeline
- [ ] `scan_lines(layout, page) -> list[list[Glyph]]` (PUA `U+E000 + id`). `--book` with no text layer uses it
- [ ] `fonts/scan-prasaaskhara/` encoding folder: catalog, profile
- [ ] Unit test: a synthetic page round-trips through `split_words` → `convert_segments` with a toy `names.tsv`

### Phase 4: evidence and labelling
- [ ] Alignment: IA + Tesseract words → akshara split → votes per distinct context → `evidence.tsv`
- [ ] Atlas image source: prototype + member crops instead of `render_png`. Evidence columns pre-fill name/unicode
- [ ] Human names glyph ids (top-frequency first). Recipes for composites
- [ ] `shapes` compile → convert the 20 sample pages → `compare` vs OCR (verdict groups)

### Phase 5: quality and gold
- [ ] Hand-verify one golden body page. Add it to `quality`
- [ ] Convert the whole book. Quality report (gaps `⟦…⟧`, prāsa-block violations, OCR disagreements)

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Merge pass fuses look-alikes (ఘ/ధ, ఛ/చ, `ం`/`౦`) | relative-height + band gate; top-100 atlas spot check; prāsa-block check flags it |
| Touching sorts dominate the tail | census in Phase 0; fused split; syllable-tuple recipes as last resort |
| Layout errors (skew, headers, two columns) poison syllables | overlays per phase; triage excludes non-body pages first |
| OCR agreeing with itself on a wrong letter | OCR is evidence only; two sources plus distinct contexts; human names the glyph |
| Catalog ids drift between runs | append-only catalog, merges recorded as aliases, determinism test |
| 600 dpi × 199 pages is slow | process per page in parallel; cache components per page |

## Verification / acceptance criteria
- `lint.cmd` and `pytest` green at every phase.
- Gate in `design.md` met on the 20 sample pages, reviewed with the user.
- Deterministic: re-running a processed page adds no ids and changes no assignments.
- The golden page converts with 0 gaps and matches the hand-verified text (`telugu.comparable`).
- Book-wide: ≥ 99 % of words without gaps. Prāsa-block violations listed and explained.
