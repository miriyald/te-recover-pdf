# Plan: OCR quality report
## Scope
New `quality.py`, `quality_report.py`, CLI `quality` subcommand, unit tests, version bump to 0.3.0.
## Steps
- [ ] Tests for edit distance, WER/CER, word comparison, confusions, aggregation
- [ ] `quality.py`
- [ ] `quality_report.py` (json, csv, md)
- [ ] CLI wiring
- [ ] Run on the real PDF, sanity-check totals
- [ ] `lint.cmd`, `pytest`, `/code-review`
## Risks & mitigations
- Converted text is a reference, not truth in Section A: label it; Section B validates.
- Unmatched words are never counted as disagreements.
- Only 5 verified pages: show the sample size next to Section B.
## Verification / acceptance criteria
- Tests and lint green; totals equal sum of page rows; page 6 converted WER 0 against the golden file.
