# Plan: Scan-shape pipeline pilot on *Sriharsha Naishadamu*

## Scope
Run the pilot on 6 pages, score page 201, and stop at the gate. A review round and the whole-book run need a go-ahead.

## Steps
- [x] Branch `scan-naishadamu-pilot` off `scan-shape-names`.
- [x] Copy the PDF to `files/sriharsha-naishadamu/input/`.
- [x] Layout check: render the pilot pages and page 51 to `docs/temp/scan-naishadamu/pages/`.
- [x] `scan-index --pages 6,21,101,201,301,401 --write-catalog`
- [x] `scan-label`
- [x] `scan-review --top 50`
- [x] `scan-convert --pages 6,21,101,201,301,401`
- [x] Draft the page-201 gold in `docs/temp/scan-naishadamu/gold/page-201.txt`.
- [ ] The user corrects the gold.
- [x] Score page 201 for ours, Tesseract and the IA layer (`docs/temp/scan-naishadamu/score_page.py`). The score is provisional until the gold is corrected.
- [x] Gate report.

All commands take `--book sriharsha-naishadamu --font scan-naishadamu --tesseract "$LOCALAPPDATA/Programs/Tesseract-OCR/tesseract.exe"`.

## Risks & mitigations
- **6 pages is thin evidence for word inference.** Report the result as a pilot-size effect; don't loosen the thresholds.
- **Folio leakage** with no header rule. Record it; fix only from the root cause.
- **Errors in the gold.** The user corrects it before the scores are final.

## Verification / acceptance criteria
- The chain runs end to end on all 6 pages.
- Page 201 is scored for all three sources.
- Any code change gets a test and green `pytest` and `lint.cmd`, and Prasaaskhara page 51 stays at 95/99.
