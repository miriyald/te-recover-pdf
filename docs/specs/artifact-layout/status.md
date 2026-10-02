# Status: one place per book for inputs, final outputs, run state, scratch and archives
_Last updated: 2026-10-02_

## Current state
done

## Completed
- Design revised by the user: intermediate files live in `files/<book>/output/intermediate/` instead of a top-level `temp/`.
- Code:
  - `layout.py` (`BookLayout`, `books`) and `run_output.py` (manifest, `archive_previous`).
  - `--book` replaces `--pdf`, and `--out` is gone.
  - `convert --method` writes a whole-book gold run to `output/<method>/` (`book.txt`, `manifest.json`, previous run archived); `--pages` / `--mapping` runs go to `output/intermediate/convert/<method>/`.
  - `quality --method`; atlas, sheets, compare and learn batches write to `output/intermediate/`; `approve` archives to `archive/<book>/batches/`; new `clean` command.
  - Scripts take `--book`; `.gitignore` has `files/` instead of `books/`.
- Tests: 165 pass (13 new for the layout, manifest, archive, final vs intermediate and clean); lint clean.
- Migration (moves only; file counts match before and after: `files/` 4 + `books/` 82 = 86, `archive/` 34 + `docs/temp` 5,398 = 5,432):

  | From | To |
  |---|---|
  | `files/Mahabharatamu.pdf` | `files/mahabharatamu/input/` |
  | `files/Maha Bharatham Vol 3 Sabha Parvam.pdf` | `files/maha-bharatham-vol-3-sabha-parvam/input/` |
  | `files/2015.395281.Prasaaskhara-Padakosamu.pdf` | `files/2015-395281-prasaaskhara-padakosamu/input/` |
  | `files/2015.395281.Prasaaskhara-Padakosamu_text.pdf` | `files/2015-395281-prasaaskhara-padakosamu-text/input/` |
  | `books/mahabharatamu/*` (ocr-cache, pending, progress, suspicious) | `files/mahabharatamu/state/` |
  | `archive/*` (replay test, v0.1 bulk discovery, batches, two PNGs) | `archive/legacy-2026-10-01/archive/` |
  | `docs/temp/*` | `archive/legacy-2026-10-01/docs-temp/` |

- Final outputs regenerated for both books × both methods.
  - Mahabharatamu: all 449 pages byte-identical to the baseline (`archive/legacy-2026-10-01/docs-temp/vol3-baseline`) for both methods.
  - Vol 3: shape-naming coverage 100% (1 unmapped sequence, the stray overstrike); ocr-learning 98.48% (gold 1 still lacks the new codes).
- Checked on real data:
  - a rerun archives the previous output to `archive/<book>/<method>/<created>/` (those test copies were then removed);
  - a `--pages` run lands in `intermediate/`;
  - `clean` removes only `intermediate/`.
- Version 0.6.0; `docs/approaches.md` updated.

## Blocked / open issues
- `compare --candidate` still reads the generated `fonts/anu/shape-naming/mapping.tsv` (rebuilt by `shapes`); only `convert` / `quality` compile the names and recipes in memory.
- `verified/` does not exist yet for any book.

## Next steps
- `learn` on Vol 3 to grow gold 1.
