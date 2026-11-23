# Changelog

All dates are 2026. Version 0.1.0 is not released yet.

## Phase 4 — Core DOCX backend (Milestone 1)

### Stage 4.6 — Integration and compatibility

- Theorems (bold head), bibliography entries, code blocks, quotations and labelled environments are written natively. Footnote texts follow at the end of the document with their bookmarks.
- Integration corpus `tests/data/full` with every Phase 4 feature, and `tests/test_full.py`.
- The checker also validates hyperlink targets and schemes, picture relationships, drawing ids, style and numbering identifiers, bookmark order and table structure. Each check has a deliberately broken package in `tests/test_check.py`.
- `scripts/libreoffice_check.py` and `scripts/word_check.ps1` for the compatibility checks; the CI installs the built wheel into a clean environment.
- Docs: `docs/limitations.md`, `docs/testing.md`, `docs/phase4-test-report.md`.

### Stage 4.5 — Bookmarks and hyperlinks

- Bookmarks on headings, captions, equations, theorems, bibliography entries, list items, footnotes and other labelled environments.
- `\ref`, `\eqref`, `\autoref`, `\cref`, `\hyperref` and `\cite` are internal links. `\href` and `\url` are external links.
- Only `http`, `https`, `ftp` and `mailto` targets become links; anything else keeps its text and is reported.
- An undefined `\eqref` shows `(??)`, as in LaTeX.

### Stage 4.4 — Tables and images (`fa20feb`)

- Native tables with merged cells, repeating header rows, alignment, relative widths and captions; the `Table` style is based on `Table Grid`.
- Images in `word/media/` with the model's relationship ids, each file stored once, sized from `\includegraphics` options.
- PNG, JPEG, GIF, BMP and TIFF are recognised by content. Other formats get a `render` diagnostic and a placeholder.

### Stage 4.3 — Lists and numbering (`dfa610a`)

- Native list numbering with independent restarts, nesting, LaTeX's label formats per depth, custom `\item[…]` labels and description lists.
- `\item[…]` labels are no longer lost, and enumitem `label=` and `start=` are mapped. Item references match LaTeX, including with enumitem.

### Stage 4.2 — Paragraphs and formatting (`41d7f66`)

- Model styles on paragraphs, built-in heading styles (Navigation Pane), native character formatting, title block, placeholder styles.

### Stage 4.1 — Backend foundation (`83db7bc`)

- Clean, byte-for-byte reproducible DOCX package, routing for every model node, OOXML checker on every output.

## Phase 3 — Semantic document model (`8e03458`)

- Word-independent content tree and document context. Covers styles, list numbering, relationships, references, the source map, and LaTeX numbering rules.
- Project root rule for included files (ADR 0002).

## Phase 2 — LaTeX frontend (`003a756`)

- Pandoc 3.9 with `--sandbox`, a time and memory limit and a JSON log.
- Include resolution, the capability registry and diagnostics with file, line and column; marker pass for skipped content (ADR 0001).

## Phase 1 — Foundation (`698951c`)

- Command line, configuration, exit codes, Pandoc version check, CI on Linux and Windows, MIT licence.
