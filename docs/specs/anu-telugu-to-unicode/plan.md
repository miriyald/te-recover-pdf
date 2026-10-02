# Plan: Anu (ASCII) Telugu PDF → Unicode, incremental mapping discovery

## Scope
Page-by-page learning loop seeded with the working mapping, OCR only for unmapped glyph sequences, auto-acceptance with
an audit trail, batches that stop after X new entries, and a review report. Out of scope: DOCX/PDF output.

## Steps  (ordered, checkable)
- [x] 1. Migrate seed (548 entries) to `mappings/mapping.tsv` with empty `first_page` / `first_word`
- [x] 2. `telugu.denormalise`; `convert.convert_segments` + `render`
- [x] 3. `mapping.py`: entries, pending, progress state files (LF)
- [x] 4. `learn.py`: anchored gap extraction, voting, page fixpoint, batch with stop-after
- [x] 5. `report.py` batch HTML; `cli learn` / `convert`; remove `align.py`, `discover.py`; version 0.2.0
- [x] 6. Unit tests (42) green; `lint.cmd` clean
- [x] 7. Regression: page 6 equals golden; pages 6–10 at 100 %
- [x] 8. Replay with `¯ ﬁ _è»` removed: `¯` relearned on p7, `_è»` held in pending, resume + stop-after work
- [x] 9. `progress.tsv` seeded with pages 6–10
- [ ] 10. Decide on the distinct-word agreement rule (open question in design.md)
- [x] 11. `approve` command; batch 6 (pages 6–10) approved into `verified/`; `docs/temp/` archived
- [ ] 12. Live batches from page 11: learn → review → approve

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Systematic OCR confusions (ఛ/చ, ఢ/ధ, ఘ/ధ) | Batch stops after X entries; report shows every new entry with its crop and first word |
| Correlated votes from repeated words | Proposed: require ≥ 2 distinct words |
| Neighbour mapping wrong → no candidates | Word shows up as unresolved/suspect in the report |
| Seed contains wrong learned entries | Suspect-word report; manual correction in `mapping.tsv` |

## Verification / acceptance criteria
- `lint.cmd` clean, `pytest` green
- `anu-unicode convert --pages 6` equals `tests/fixtures/page-6.golden.txt`
- Each batch: `report.html` reviewed, `mapping.tsv` corrected where needed before the next batch
