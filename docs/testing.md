# Testing

## Running the tests

```
pip install -e ".[dev]"
pytest                     # everything
pytest tests/test_lists.py # one area
TEJTEX_NO_SKIP=1 pytest    # turn every skip into a failure (CI does this)
```

Tests that need the real Pandoc 3.9 use the `real_pandoc` fixture and are skipped when it is not on PATH; all other tests use a fake Pandoc (`tests/conftest.py`). With `TEJTEX_NO_SKIP=1` a missing Pandoc, a missing console script or a platform limit (symbolic links on Windows without administrator rights) fails instead of skipping.

## Layout

| File | Covers |
|---|---|
| `test_cli.py`, `test_integration.py` | Command line, options, exit codes 0–6, examples, paths with spaces and non-ASCII characters |
| `test_source.py`, `test_frontend.py`, `test_caps.py`, `test_normalize.py`, `test_tree.py`, `test_corpus.py` | Phase 2: includes and the project root, Pandoc runs and limits, the capability registry, markers and placeholders |
| `test_ir.py`, `test_model.py` | Phase 3: the document model, numbering rules, references, styles, relationships |
| `test_backend.py`, `test_check.py` | Stage 4.1: package, routing, determinism, import rule; the checker against deliberately broken packages |
| `test_paragraphs.py` | Stage 4.2: styles, headings, character formatting |
| `test_lists.py` | Stage 4.3: numbering, nesting, restarts, custom labels, enumitem |
| `test_tables.py`, `test_media.py` | Stage 4.4: tables (part 1) and images (part 2) |
| `test_bookmarks.py`, `test_hyperlinks.py` | Stage 4.5: bookmarks, internal and external links, unsafe targets |
| `test_full.py`, `test_output.py` | Stage 4.6: the integration corpus; every corpus is a valid package with no content lost; deterministic output; the LaTeX sources stay untouched |

`tests/helpers.py` builds model documents (`make`) and reads packages back: `paras`, `labels` (replays Word's numbering rules on `numbering.xml` to get the numbers Word shows), `marks` (the text inside each bookmark), `links`, `home` (the paragraph that holds a bookmark), `png` (a small image of a given size).

## Corpus

Each folder under `tests/data` is a small LaTeX project:

| Corpus | Purpose |
|---|---|
| `sec63`, `unknown`, `includes`, `images`, `refs` | Phase 2 and 3: skipped constructs, includes and the project root, image checks, numbering and references |
| `format` | Headings and character formatting |
| `lists` | Lists, labels, restarts, item references |
| `tables` | Merged cells, header rows, widths, lists in cells, adjacent tables |
| `media` | Image sizes, reuse, PDF and missing images, figures |
| `links` | Bookmark names, forward and backward references, external and unsafe links |
| `full` | Integration: every Phase 4 feature in one document, including a 60-row table that spans pages and unsupported content |

The expected numbers and references in the tests were checked against `pdflatex`.

## Checks outside pytest

**LibreOffice.** `scripts/libreoffice_check.py` converts DOCX files to ODT and PDF with LibreOffice and compares, file by file:

- tables, column spans, row spans and header rows;
- pictures and numbered paragraphs;
- bookmarks, internal and external links;
- every word of the text.

```
tejtex compile tests/data/full/main.tex -o full.docx
python scripts/libreoffice_check.py full.docx
```

**Microsoft Word (Windows).** `scripts/word_check.ps1` opens a temporary copy of each DOCX file read-only in a new, hidden Word instance through COM (so a file you have open in Word is not touched) and writes a JSON report. If Word attaches to an instance that was already running, the script stops without touching it. The report covers:

- the window caption, so a file opened in Compatibility Mode or as repaired shows up, and the page count;
- headings by outline level (what the Navigation Pane shows);
- the numbers Word renders for each list paragraph, and pressing Enter after "Third step.", then Tab and Shift+Tab;
- tables, merged cells, header rows and the pages a table spans;
- picture sizes, and resizing and moving the first picture;
- captions, and adding text to the first caption;
- bookmarks, and going to each one;
- every internal link followed to its bookmark;
- external link addresses, and restyling a heading.

The script changes nothing on disk. Word refuses a file with malformed XML, but it opens some structurally broken files without any message, so the checker is still needed (see the negative controls in the test report).

```
powershell -ExecutionPolicy Bypass -File scripts\word_check.ps1 -Out word-check.json full.docx
```

Checked by hand: the repair prompt, the Navigation Pane, Ctrl+click on an external link, the Insert ▸ Bookmark dialog, header rows on later pages, dragging a picture and saving after a caption edit. The checklist is in [phase4-test-report.md](phase4-test-report.md).

## Continuous integration

GitHub Actions runs four jobs: Ubuntu and Windows, Python 3.10 and 3.12. Each job:

1. installs Pandoc 3.9 and TejTeX;
2. runs a CLI smoke test, including exit code 3 for a missing file;
3. runs all tests with `TEJTEX_NO_SKIP=1`;
4. builds a wheel, installs it into a new virtual environment, and checks that the installed package compiles the integration corpus to a file byte-identical to the development install's.
