# Status: Scanned Telugu → Unicode via image glyph ids (Prasaaskhara Padakosamu)
_Last updated: 2026-10-02_
## Current state
in progress: Phases 1–2 built; clustering v3 verified by the user on pages 100–147. Next: labelling

## Completed
- Package `anu_unicode/scan/` + command `scan-index` (registered in `cli.py`):

  | Module | Role |
  |---|---|
  | `ink.py` | render at native resolution, 8-connected components |
  | `page.py` | drop ornament rules and everything outside them (running head, page number), drop specks enclosed by a letter |
  | `words.py` | words (side-by-side gap ≤ 0.45 body height, or stacked ≤ 0.3), band per glyph, drawing order (host, then its marks above, then below) |
  | `catalog.py` | shape ids: 48 px grid, stray-ink share ≤ 0.15 (ink further than 1 px from the other shape), gated by band, hole count, relative height, aspect; append-only save/load |
  | `index.py` | `occurrences.tsv`, `shapes.tsv`, `shapes.html` (prototype + 12 member crops), `growth.tsv` |
- numpy 2.5.3, scipy 1.18.1 pinned; version 0.8.0. 14 unit tests in `tests/unit/scan/`. `lint.cmd` and the full `pytest` suite (194) pass
- Word grouping checked visually on page 51: subscripts follow their host, `=` bars are kept, `ము` is one sort

## Findings (whole-book runs, pages 4–195)
| Step | ids | ids for 99 % | Body growth per page |
|---|---|---|---|
| POC metric (pixel XOR, first member), pages 4–13 | 617 | n/a | n/a |
| Mean chamfer distance | 241 on pages 4–13, but **clusters mix letters** (కు/తు/గు/ను) | | |
| Stray-ink share, 48 px, 1 px tolerance | still mixes న/వ, బ/జ, డు/రు | | |
| + hole-count gate | pure apart from rare mixes; **4,171 over the whole book** | 3,118 | 1.1–2.7 % |
| + drop title/accession pages (1–3, 196–199) and running head/footer | **2,341** | **1,366** | 1.0–2.3 % |

- Rejected: the densest-window stray gate (scan noise along stroke edges is dense too: 1,377–2,392 ids on 10 pages).
- 206 ids with ≥ 100 occurrences cover 79.8 %; 301 ids with 20–99 cover 14.5 %; 978 singletons cover 1.0 %.
- **The 20–99 band is mostly fused syllables, not noise**: `ా`, `ో`, `ూ` and `ె` touch their consonant (గా, బా, కా, రా, దో, తో, లో, మా, కూ, యా…). That is consonant × sign, the combinatorial alphabet the design warned about.
- A minority of mid-frequency ids are still mixed lookalikes (ర/ద/త, తె/జె/బె/లె, దా/తా/రా, ని/చి/లి).

## Component splitting (`split.py`, `scan-index --split-passes N`, opt-in)
- Cut only at a **neck**: a column with one run of ink, ≤ 0.3 body height, ≤ half the thickest column on either side (rings and bars have none)
- Accept a cut when both parts match shapes seen ≥ 50 times (any glyph), or, for a glyph the frequent alphabet cannot explain, when one part matches within 0.25
- Each pass splits the previous pass's pages with the alphabet that pass learned, so pieces such as "ా with stub" become ids and compose

| Pages 100–147 | ids | ids for 99 % | occurrences | time |
|---|---|---|---|---|
| no split | 982 | 735 | 24,759 | ~1 min |
| 1 pass | 974 | n/a | 26,312 | |
| 3 passes | 951 | **619** | 33,269 | ~9 min |

- Cuts land where they should (before `ా`/`ో`/`ూ`: గో, లో, దో, తూ, జా, భా, యా). But the alphabet barely shrinks, and later passes cut more and more glyphs into pieces
  that are frequent only because earlier passes created them (+34 % occurrences). **Splitting is not the root fix**; it stays opt-in.
- Conclusion: on this print the image alphabet is **not font-like**. It is unit-like (Anu: 601 units against 207 codes) plus print-variance duplicates.

## Clustering v3: thick-difference test (OCR: Tesseract only, not the IA layer)
Cause of mixed ids such as #171 (కూ / మా / నూ): the 48 px square grid squeezed wide shapes, and a *share* of ink lets a whole-stroke
difference in the base hide behind a large shared tail. Fix, as in JBIG2 pattern matching and substitution:
- the old stray-share measure (≤ 0.2) is only a **pre-filter** that finds 8 candidates
- **decision**: each shape on a 128×256 canvas scaled to its **own height = 64 px** (aspect kept; shapes under 0.6 body height
  are not enlarged), XOR with the candidate prototype at ±1 px shifts, 3×3 erosion. The shapes differ when the largest surviving blob
  exceeds **20 px** at every shift.

Calibration (pages 100–105, member against prototype):

| Scaling | Pure letters | Mixed ids |
|---|---|---|
| page body height | same letter leaves 20–120 px blobs (natural ±10 % size variation) | n/a |
| own height, 40 px | blobs 0–14 | చే/నే 0–12: **no gap** |
| own height, 64 px | blobs mostly 0–2 | చే/నే 0–7 against 38–82; లి/బి 0–11 against 23–131: **clear gap** |

| Pages 100–147 | ids | ids for 99 % |
|---|---|---|
| stray share only | 982 | 735 |
| + thick test, 40 px, blob 16 | 1,083 | 836 |
| + thick test, 64 px, blob 20 | **1,685** | 1,438 |

- More ids by design (purity first). The mid-frequency sheet no longer shows the #171 kind of mix; 595 (బ/చ) and 204 (చ/ఎ) still need a look
- Review output: `files/<book>/output/intermediate/scan-index/shapes.html` (16 members sampled uniformly over all occurrences, seeded)

## Ambiguity report (`scan-index --ambiguity`, `output/intermediate/scan-ambiguity/`)
Every occurrence re-checked against the **final** ids: gates + wide pre-filter (stray share ≤ 0.35, no top-8 cap) + thick test.
User check of the v3 clusters: near perfect (595 confirmed as a mix).

| Pages 100–147 (24,759 occurrences, 1,685 ids) | occurrences | share |
|---|---|---|
| clean (matches only its own id) | 5,556 | 22.4 % |
| ambiguous, all matches are ids whose prototypes match each other | 16,159 | 65.3 % |
| ambiguous, matches span ids whose prototypes do not match | 2,696 | 10.9 % |
| drifted (no longer matches its own id) | 348 | 1.4 % |

- 1,524 confusable pairs, 693 of them prototype-to-prototype. Grouping prototype matches: 1,685 ids → 1,265 groups (194 groups hold 614 ids)
- **The top pairs in both ambiguous classes are the same letter split across ids**: `=` bars (2/39/979/431, 3/123/68), ము (30/52/180),
  ర (41/741), న (8/587), త (4/606), క (40/1544), ం (14/432). Cause: one-pass, order-dependent clustering. An early, few-member prototype fails the
  thick test, so a new id is created; the two ids later converge
- Genuine lookalike ambiguity cannot be read off until those duplicates are merged
- Cost: the report took 18.5 min for 48 pages (wide candidate list × thick test); a whole-book run needs it faster

## Round two: duplicate merge (`merge.py`, `scan-index --merge`, off by default)
Rule: visit ids smallest first; merge an id into a larger candidate when ≥ 80 % of its sampled members pass the thick test against that
id's prototype; prototypes are combined from their sums; retired ids keep their numbers. Rounds repeat until nothing merges.

| Pages 100–147 | no merge | with merge |
|---|---|---|
| live ids | 1,685 | 1,380 (296 + 9 merged) |
| ids for 99 % | 1,438 | 1,133 |
| ambiguous occurrences | 18,855 | 18,627 |
| drifted occurrences | 348 | **1,181** |

Ambiguous or drifted share by kind (with merge): main letters 75 %, `=` bars/dashes 99 %, above marks 83 %, below marks 63 %.

**Diagnosis:** print variation forms a *continuum* wider than one thick-test neighbourhood. One letter's copies span several overlapping
neighbourhoods: neighbours match each other, the ends do not (ము: 30/52/180/852/890; bars of continuously varying length). Merging prototypes
fights this the wrong way: the merged prototype blurs, so drift triples. Ambiguity *between ids of the same letter* is harmless (several ids
may share a name). Only ambiguity *between different letters* matters, and that needs to be measured on families, not ids.

## Decisions (2026-10-02)
- **Duplicates are accepted**: several ids may hold the same shape, as long as each id is pure. Clustering v3 (no split, no merge) is the alphabet.
- Ambiguity is reframed around names: before naming, the match graph *suggests* names for ids of the same letter; after naming, an occurrence
  matching ids with *different* names is a conflict ("shape that needs care"). That conflict list is the separate-processing queue.
- OCR evidence comes from Tesseract only.
- Removed after the history commit (98d5a5c): `split.py`, `merge.py` (and their tests and options), `scripts/index_glyphs.py` + `glyph_table.html.tmpl`

- Naming: the name defaults to the Unicode text (`ము` / `ము`); real shape names only for pieces that mean nothing alone (ticks, bars)
- Atlas scope: ids seen ≥ 3 times (`--min-count`); rarer ids go to the gap/conflict queue
- Work stays on branch `set-ready-volumes`

## Built (Phases 3–4)
- `source.py` (bridge): id ↔ `U+F0000 + id` (Supplementary Private Use Area-A; `U+F000–F0FF` is taken by Anu symbol glyphs),
  `read_occurrences`, `scan_words` → `glyphs.Word` in drawing order with boxes in PDF points. Round trip through `compile_mapping` +
  `convert_anu` is tested
- `atlas.py` + `scan-atlas`: one row per id (count ≥ 3), prototype + member strip, two example words with the glyph boxed, Tesseract
  `--psm 10` on 5 spread member crops (majority vote, cached in `files/<book>/state/scan-ocr.tsv`), "looks the same" ids (≥ half of this
  id's crops pass the thick test against that id's prototype), name + Unicode inputs, *Download names.tsv* (font atlas STYLE/SCRIPT reused)
- Catalog: `files/<book>/state/scan-catalog.npz` (generated, > 100 KB, not in git). Risk: the committed `names.tsv` is keyed by ids that only
  this file defines, so the catalog must be kept (or archived) alongside it

- Whole body frozen: 4,870 ids over 97,502 components (2,239 singletons; 3,895 ids for 99 %). First atlas: 1,949 ids ≥ 3 (96.3 % of
  ink); Tesseract gave a ≥ 4/5 majority on 542 ids (35.5 % of ink) and is systematically wrong on క ("కిర")
- **Exclusion list** `fonts/scan-prasaaskhara/scan/excluded.tsv` (user-curated, committed): ids left out of every list (atlas rows and
  "looks the same", index sheet and statistics, ambiguity report). `occurrences.tsv` stays complete, so an exclusion can be undone.
  Round 1: 56 ids, all `=` bar halves above and below the line, 16,103 occurrences (16.5 %). Atlas after it: 1,893 ids, 77,796 occurrences
- Open: excluded ids drop out of the lists only; whether they also contribute nothing in conversion is decided at the convert step
  (`=` is the headword/meaning separator in this book)

## In progress
- User labels the atlas

## Blocked / open issues
- JIRA ID not given
- Where the catalog lives long-term (see risk above)

## Next steps
1. User labels the atlas, top-frequency first → `fonts/scan-prasaaskhara/shape-naming/names.tsv`
2. `shapes` compile → convert sample pages through `scan_words` → `compare` against Tesseract words
3. Conflict check after naming
