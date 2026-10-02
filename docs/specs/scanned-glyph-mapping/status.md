# Status: Scanned Telugu → Unicode via image glyph ids (Prasaaskhara Padakosamu)
_Last updated: 2026-10-02_
## Current state
not started (design + plan written, awaiting review)
## Completed
- Facts gathered: 199 pages, 1-bit CCITT, 2645×4290 px (≈600 dpi), no text layer
- Internet Archive twin (`…-text/…_text.pdf`) has a GlyphLessFont OCR layer: a usable word-box and weak-label source
- POC baseline (pages 4–13, archived): 617 ids, 294 singletons, top 300 = 91.8 % coverage. Duplicate ids for one shape seen
- design.md, plan.md
## In progress
- none
## Blocked / open issues
- JIRA ID not yet given
- Overlaps the untracked `docs/specs/glyph-id-clustering/` POC spec; it becomes Phase 2's starting point once confirmed
## Next steps
- Review the design (especially the challenge to syllable-first clustering and the gate thresholds)
- Phase 0 spikes
