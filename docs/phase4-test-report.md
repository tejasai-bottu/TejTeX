# Phase 4 test report — Core DOCX backend (Milestone 1)

Date: 22 November 2026. Scope: Stages 4.1–4.6.

## Completion criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Stages 4.5 and 4.6 pass their own tests | Done (`test_bookmarks.py`, `test_hyperlinks.py`, `test_check.py`, `test_full.py`) |
| 2 | The integration corpus passes | Done (`tests/data/full`, 8 tests, plus validity, no-content-lost and LibreOffice checks) |
| 3 | All four CI jobs pass | Done (run 45093046008, commit `5fdc6b6`) |
| 4 | Microsoft Word checks recorded | Automated checks recorded below; the hands-on checks are listed at the end |
| 5 | LibreOffice validation passes | Done: 11 of 11 corpus documents |
| 6 | Known limitations documented | Done: [limitations.md](limitations.md) |
| 7 | Final test report | This document |

## Test suite

213 tests:

| File | Tests | File | Tests |
|---|---|---|---|
| test_backend | 8 | test_lists | 11 |
| test_bookmarks | 7 | test_media | 7 |
| test_caps | 6 | test_model | 5 |
| test_check | 12 | test_normalize | 4 |
| test_cli | 21 | test_output | 23 |
| test_corpus | 9 | test_paragraphs | 21 |
| test_frontend | 4 | test_source | 14 |
| test_full | 8 | test_tables | 11 |
| test_hyperlinks | 8 | test_tree | 4 |
| test_integration | 4 | test_ir | 26 |

| Environment | Result |
|---|---|
| Linux (Python 3.10.12, Pandoc 3.9, `TEJTEX_NO_SKIP=1`) | 213 passed |
| Windows 11 laptop (Python 3.14.0, Pandoc 3.9) | 212 passed, 1 skipped: symbolic links need administrator rights on this machine. The test runs in CI. |

Exit codes 0–6 are unchanged; `test_cli.py` and `test_integration.py` cover each of them.

## CI

GitHub Actions, four jobs: Ubuntu and Windows × Python 3.10 and 3.12, with `TEJTEX_NO_SKIP=1` (no skips allowed). Each job also builds the wheel, installs it into a clean virtual environment and compares its output with the development install's.

Run [45093046008](https://github.com/tejasai-bottu/TejTeX/actions/runs/45093046008) for commit `5fdc6b6`:

| Job | Smoke test | Tests | Clean install from the wheel | Time |
|---|---|---|---|---|
| ubuntu-latest / Python 3.10 | passed | passed | passed | 41 s |
| ubuntu-latest / Python 3.12 | passed | passed | passed | 38 s |
| windows-latest / Python 3.10 | passed | passed | passed | 120 s |
| windows-latest / Python 3.12 | passed | passed | passed | 69 s |

With `TEJTEX_NO_SKIP=1` a skip counts as a failure, so all 213 tests ran and passed in every job.

## Clean installation and determinism

- `pip wheel .` → `tejtex-0.1.0-py3-none-any.whl`, installed into a new virtual environment.
  - `tejtex --version` prints `tejtex 0.1.0 (pandoc 3.9)`.
  - Compiling the integration corpus gives a file byte-identical to the development install's.
  - A missing input still exits with 3.
- The same input compiles to byte-identical DOCX files, through the API and through the command line (`test_full.py::test_output_is_deterministic`, `test_backend.py`).

## PDF pipeline

TejTeX never writes into the LaTeX project. After a compile, the only new file is the `.docx`, and every other file has the same SHA-256 (`test_full.py::test_compiling_leaves_the_latex_sources_alone`). `pdflatex` (TeX Live 2022) was run on the integration corpus before and after a TejTeX compile, and the PDF text was identical. The only LaTeX error is the deliberate `\unknowncmd`.

## LibreOffice 26.2 (Linux)

`scripts/libreoffice_check.py` converts each document to ODT and PDF and compares structures and text:

| Document | Result | Tables | Spans (col/row) | Header rows | Pictures | List paragraphs | Bookmarks | Internal links | External links |
|---|---|---|---|---|---|---|---|---|---|
| full | OK | 2 | 1/1 | 2 | 4 | 10 | 16 | 16 | 2 |
| links | OK | 1 | — | — | 1 | 1 | 11 | 16 | 3 |
| refs | OK | 1 | — | 1 | 1 | 4 | 15 | 15 | 2 |
| lists | OK | — | — | — | — | 24 | 7 | 6 | — |
| tables | OK | 3 | 1/1 | 2 | — | 2 | 3 | 2 | — |
| media | OK | 1 | — | — | 6 | — | 3 | 2 | — |
| format | OK | — | — | — | — | 2 | 5 | — | — |
| sec63 | OK | 1 | — | — | 1 | 6 | 8 | 5 | — |
| unknown, includes, images | OK | — | — | — | 0–1 | — | 0–3 | — | — |

In every case:

- the PDF was produced;
- LibreOffice kept every bookmark and resolved every internal link (`#name`);
- every word of the DOCX text is in the LibreOffice document.

In the PDF of the integration corpus, the 60-row table spans pages, and its header row repeats on each page.

## Microsoft Word 16.0.20625 (Windows 11)

`scripts/word_check.ps1` opened six documents read-only in a separate, hidden Word instance:

- `phase4-full-sample.docx` (integration corpus)
- `stage-4.5-links-sample.docx`
- `stage-4.3-sample.docx`
- `stage-4.4-tables-sample.docx`
- `stage-4.4-images-sample.docx`
- `stage-4.2-sample.docx`

The script changed nothing on disk. Results:

| Check | Result |
|---|---|
| Documents open | 6 of 6 opened with alerts off and no error; no document protection |
| Navigation Pane headings | Every heading has its outline level. Integration corpus: seven level-1 headings, `1 Introduction` … `7 Results`. Links sample: levels 1 and 2 as in the source |
| List numbers Word renders | Same as LaTeX: `1.`, `2.`, `(a)`, `•`, `i.`, `(x)`, `3.`, `(a)` (integration), and all 24 items of the lists corpus, including `5.`, `C.` and the restarts at `1.` |
| Enter continues a list | Enter after "Third step." gives `4.` (integration and lists corpus) |
| Tab / Shift+Tab | The new item becomes `(a)` with Tab and `4.` again with Shift+Tab |
| Numbering restarts | `(a) Restarted list…`, `1. Restarted inside bullets`, `5. Starts at five`, `C. Starts at C` |
| Tables editable | All tables are Word tables with Word's row and column counts |
| Merged cells | The merged table reports 4 rows × 3 columns with 10 cells and is not uniform, as expected for one horizontal and one vertical merge |
| Header rows repeat | The 60-row table spans pages 1–3 and its first row is a heading row (`HeadingFormat = True`) |
| Images | All pictures are present at the sizes from the source (216×108 pt for `0.5\textwidth`, 28.3 pt for `1cm`, 432 pt for `\linewidth`, natural 180×90 pt) |
| Images resize and move | The first picture resized with its aspect ratio locked, and moved after conversion to a floating shape |
| Captions | Caption paragraphs: `Table 1: Scores with merged cells`, `Figure 1: A chart`, `Figure 2: A vector diagram`, and the stage samples' captions |
| Bookmarks | Word's bookmark list (the same collection as Insert ▸ Bookmark) has every bookmark: 16 in the integration corpus, 11 in the links sample with the normalised names, 7 in the lists corpus |
| Internal links | Every internal link was followed and landed on its bookmark: 16 of 16 (integration), 16 of 16 (links), 6 of 6 (lists), 2 of 2 (tables and images) |
| External links | Word reads the targets: `https://example.org/tejtex`, `https://www.ctan.org/`, `https://example.org/list`, `https://example.com/a?b=1&c=2`, `mailto:info@example.com` |
| Heading style change | Changing a heading to `heading 2` moves it to outline level 2 |

### Hands-on checks (Kiran, in Word)

These need a person at the screen and are not yet recorded:

- [ ] `phase4-full-sample.docx` opens visibly without a repair prompt.
- [ ] Navigation Pane shows the seven headings; clicking one jumps to it.
- [ ] Ctrl+click on `CTAN` opens https://www.ctan.org in the browser; Ctrl+click on `Figure 1` jumps to the figure caption.
- [ ] Insert ▸ Bookmark lists the bookmarks, and Go To works.
- [ ] The long table's header row is visible at the top of pages 2 and 3.
- [ ] A picture can be selected, resized and dragged.
- [ ] Caption text can be edited.

Phase 4 is complete once these are ticked.

## Known unresolved issues

See [limitations.md](limitations.md). In short:

- Mathematics as OMML, native footnotes, SEQ/REF fields and `.bib` bibliographies come in Phase 5.
- The renderer for TikZ and PDF, EPS and SVG images comes in Phase 6.
- Pandoc does not pass on per-table borders, caption position, `scale=`/`angle=` or `\pageref`.
- enumitem `resume` is not applied.
