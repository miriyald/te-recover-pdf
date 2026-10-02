# Plan: Image-portion to glyph-id clustering (POC)

## Scope
One standalone script, `scripts/index_glyphs.py`, run on one page (page 4 of the Prasaaskhara scan). No package or CLI change.

## Steps
- [ ] Add pinned `numpy`, `scipy` to requirements.txt, requirements-dev.txt, pyproject.toml; bump version
- [ ] Script: render page, binarise, label components, normalise, catalog with assign()
- [ ] Write `occurrences.tsv` and `catalog.json` under `--out` (docs/temp/glyph-ids/)
- [ ] Visual validation, produced as one self-contained `clusters.html`:
  - cluster view: one row per glyph id, with count and up to 12 actual member crops at original resolution, so a wrong
    member stands out; rows ordered by count; the most mixed clusters (highest mean member mismatch) flagged
  - page overlay: the page image with every component boxed and labelled by glyph id, colour per id, so you can check
    clusters in context and spot letters split or fused across ids
- [ ] Unit test (synthetic bitmaps): same shape same id, different shape new id, speck dropped
- [ ] Run on page 4, review clusters.html with you, tune thresholds

## Risks & mitigations
- Over-splitting one letter into many ids: expose thresholds, judge on contact sheet.
- Fused conjuncts become unique ids: expected; long tail is handled by labelling by frequency later.

## Verification / acceptance criteria
- `lint.cmd` and `pytest` green.
- Page 4 run is deterministic (same ids on re-run) and re-running adds no new ids.
- Contact sheet shows visually coherent clusters (manual review).
