# The DOCX backend

Phase 4. Package `tejtex.backend`. It writes the document model (`tejtex.ir`, see [ir.md](ir.md)) as a DOCX package.

## Rule: the model owns meaning, the backend owns representation

The backend does not decide anything the model already knows. It takes numbers, bookmark names, relationship ids, list instances and levels, style ids and placeholder texts from the model and writes them as Word structures. It never computes a figure number, resolves a label or chooses a list's restart behaviour.

This is enforced: the backend may import only `tejtex.ir.nodes`, `tejtex.errors` and its own modules from TejTeX (`tests/test_backend.py::test_backend_imports_only_the_model`).

## Contract

```
data = backend.render(doc)        # bytes of a .docx package
backend.write(doc, out)           # render, then write the file
```

- Every model node type is routed (`writer.BLOCKS`, `writer.INLINES`; `ListItem`, `Row`, `Cell`, `BibEntry`, `Meta` and `Document` are handled by their parents). A test fails if a node type is added to the model without a route. A node of an unknown type is an internal error (exit code 1).
- A node type with a native handler is written as Word structures. A node type without one goes through the **text fallback**, so no content is lost while the stages below are built:
  - a container whose own structure is not native yet (`Theorem`, `Quote`, `Container`) writes its child blocks through the normal routing, so their paragraphs and runs are native;
  - a block without children (`Bibliography`, `CodeBlock`, `Rule`) is written as plain `Normal` paragraphs with its text;
  - an inline node without a handler (`Math`, `Citation`, `CrossReference`, `Hyperlink`, `Footnote`) is written as a plain run with its text or resolved number; footnote texts follow at the end of the document.
- Every package is checked before it is written (below). A package that fails is an internal error, and no file is written.

## Package

The backend starts from python-docx's default template and removes what does not belong to the document:

| Removed or replaced | Why |
|---|---|
| `docProps/thumbnail.jpeg` | python-docx's own preview image |
| `customXml/*` | template leftovers |
| `word/stylesWithEffects.xml` | Word 2010 compatibility copy of the styles, 430 KB |
| `docProps/app.xml` | claimed "Microsoft Macintosh Word"; now `Application: TejTeX` |
| `docProps/core.xml` | creator "python-docx", a 2013 timestamp; now title and authors from the document, no timestamps |

The ZIP is rewritten with a fixed timestamp (1980-01-01) and a stable entry order, so the same input gives a byte-identical file.

## Paragraphs, headings and runs (Stage 4.2)

- `Paragraph` → `w:p` with the model's style (`BodyText`, `Compact`, `BlockText`, `Caption`, …).
- `Heading` → `w:p` with Word's built-in `heading 1`–`heading 6` style (outline levels 0–5), which puts it in Word's Navigation Pane and LibreOffice's Navigator. The paragraph carries no direct formatting, so changing its style in Word behaves normally. The number from the model is written as a plain run followed by a tab (`2.1⇥Results`); native heading numbering linked to the heading styles is Phase 5 (RQ2).
- `TextRun` → `w:r` with only the properties the model sets: `w:b`, `w:i`, `w:u`, `w:strike`, `w:vertAlign` (superscript/subscript), `w:smallCaps`; code uses the `Verbatim Char` character style. Italic is whatever the model says, so `\emph` inside italic text is upright, as in LaTeX.
- `Break` → `w:br`. Characters that XML 1.0 does not allow (control characters, lone surrogates) are removed.
- Placeholders: inline → run with the `TejTeX Placeholder Char` style, block → paragraph with the `TejTeX Placeholder` style (both red italic), so unsupported content stays visible.
- Title block from the metadata: `Title`, one `Author` paragraph per author, `Date`, then the abstract paragraphs (`Abstract` style). The document properties carry the title and authors as well.

### Styles (`backend/styles.py`)

The model decides which styles a document uses (`StyleRegistry`); the backend makes sure each exists. Styles already in the template are reused (`Normal`, `Body Text`, `heading 1`–`6`, `Title`, `caption`). Missing ones are created with the model's id, name and base style and a simple look:

| Style | Type | Look |
|---|---|---|
| Compact | paragraph, based on Body Text | 2 pt before and after |
| Author, Date | paragraph | centred |
| Abstract | paragraph | indented 0.5 in on both sides, 10 pt |
| Figure | paragraph | centred, keep with next |
| Block Text (built-in) | paragraph | indented 0.5 in on both sides |
| Source Code | paragraph | Consolas 10 pt |
| Bibliography (built-in) | paragraph | 0.5 in hanging indent |
| footnote text (built-in) | paragraph | 10 pt |
| TejTeX Placeholder | paragraph | red italic |
| Hyperlink (built-in) | character | blue, underlined |
| Verbatim Char | character | Consolas |
| footnote reference (built-in) | character | superscript |
| TejTeX Placeholder Char | character | red italic |
| Table | table, based on Table Grid | single 0.5 pt borders on every cell (inherited) |

Word's own style names are used for built-in styles, so Word treats them as its built-in styles.

## Lists and numbering (Stage 4.3)

The model gives every list its numbering instance (abstract definition, level, start value) and every custom `\item[...]` label its own instance. The backend writes them to `word/numbering.xml` and puts `w:numPr` on the paragraphs (`backend/numbering.py`).

- **Ids.** The template's definitions stay (abstract 0–8 and instances 1–9, used by Word's `List Bullet` and `List Number` styles). The model's abstract definitions are added after them (`w:abstractNumId` 9, 10, …) and its instances after the template's (`w:numId` 10, 11, …), so ids never clash.
- **Levels.** Each abstract definition is `hybridMultilevel` with nine levels, each with the model's format and text (`decimal` `%1.`, `lowerLetter` `(%2)`, `bullet` `•`, …), a left indent of 0.5 in per level and a 0.25 in hanging indent, like Word's own lists.
- **Restarts.** Every instance has `w:lvlOverride`/`w:startOverride` for its level with the model's start value. Lists that share an abstract definition therefore restart independently, the way LaTeX starts every `enumerate` at 1, or at the value set with `\setcounter{enumi}`.
- **Items.** The first paragraph of an item gets `w:numPr` (`w:numId`, and `w:ilvl` = the list's level). The number is not text in the paragraph, so pressing Enter at the end of an item in Word gives the next number, and Tab and Shift+Tab change the level.
  - Further paragraphs of the item are indented to the item's text (`w:ind w:left`) without a number.
  - A nested list uses its own instance at its own level.
  - An item that starts with a nested list, and an empty item, get an empty numbered paragraph, so the number is not lost.
- **Custom labels.** `\item[(x)]` uses the label's instance, which has format `none` and the label as level text. The label does not step the counter, so the next ordinary item continues the count, as in LaTeX.
- **Description lists.** The term is bold at the start of the item's first paragraph, which has a 0.5 in hanging indent; further paragraphs are indented by 0.5 in. Nested lists inside use the next level.

`tests/data/lists` covers nesting to four levels, mixed `itemize`/`enumerate`, custom labels, restarts, `\setcounter`, enumerate-package and enumitem formats, multi-paragraph and empty items, description lists and item references. `tests/test_lists.py` replays Word's numbering rules on the generated `numbering.xml` and checks that every label matches what LaTeX prints.

Limitations:

- One paragraph holds one number, so an item that starts with a nested list shows its number on its own line; LaTeX puts both on one line.
- Math in a custom label is shown as its TeX source (`\star`) until Phase 5.
- enumitem `resume` is reported and not applied; the list restarts.

## Tables (Stage 4.4, part 1)

`Table` → a native `w:tbl` (`backend/tables.py`):

- **Grid.** The cells are placed on the grid the way Word expects: a cell is put in the first free column of its row, skipping columns that a row span from above still covers. A row with fewer cells than the table is padded with empty cells.
- **Merged cells.** A column span becomes `w:gridSpan`. A row span becomes `w:vMerge` (`restart`, then `continue` in the rows below), with the text centred vertically, as `\multirow` does.
- **Header rows.** The model's header rows (`\hline` or `\midrule` after the first row) get `w:tblHeader`, so Word repeats them on every page.
- **Alignment.** A cell's own alignment (`\multicolumn{2}{c}{…}`) or its column's (`l`, `c`, `r`) is written as paragraph alignment in the cell. Left is Word's default and is not written.
- **Widths.** Columns with a relative width from the model (`p{0.4\linewidth}`) get that share of the text width. The other columns share the rest equally, at least 0.5 in each. The table spans the text width, like a table inserted in Word.
- **Borders.** The table uses the `Table` style, which is based on Word's built-in `Table Grid`, so every cell has a thin border. Changing the `Table` style in Word restyles every table at once.
- **Cells.** Cell content goes through the normal routing, so paragraphs, runs, lists, images and nested tables in a cell are native. A nested table is followed by an empty paragraph, which Word requires. Two tables in a row are separated by an empty paragraph, because Word joins adjacent tables into one.
- **Captions.** The caption goes above the table, as `Table 1: Scores by group`, in Word's `caption` style, and is kept with the table. The number and the word "Table" come from the model.

Limitations:

- Pandoc does not keep the source's rules (`|`, `\hline`, `\toprule`), so every table gets the same grid borders.
- Pandoc does not keep the caption's position either, so a caption written below a table in LaTeX goes above it.
- Fixed widths (`p{3cm}`) arrive without a size and are treated like automatic columns.

## Images and figures (Stage 4.4, part 2)

`Image` → a DrawingML inline picture (`wp:inline`) in a run (`backend/media.py`):

- **Parts.** Each relationship from the model becomes one part, `word/media/image<n>.<ext>`, related to the document with the model's id (`rTej1`, …). An image used several times is stored once and every use points to the same part. Content types come from the file.
- **Formats.** The model accepts PNG, JPEG, GIF, BMP and TIFF, recognised by their first bytes, not by their names. PDF, EPS, SVG and anything else get a `render` diagnostic with the source location and a visible placeholder (`[image: figs/plot.pdf]`). A missing file gets a warning (Phase 2) and the same placeholder.
- **Size.** `width` and `height` from `\includegraphics` in `%`, `in`, `cm`, `mm`, `pt`, `bp`, `pc`, `px`, `em`, `ex` or as a multiple of `\linewidth`, `\textwidth`, `\columnwidth` or `\textheight`. With one of them the aspect ratio is kept. With neither, the image's own size and resolution are used. An image wider than the text is scaled down to the text width.
- **Alt text.** Alt text from the source is written to `wp:docPr/@descr`; Pandoc's default text `image` is not. Every picture has a unique `docPr` id.
- **Figures.** A `Figure` writes its blocks (`Figure` style: centred, kept with the caption), then the caption below, as `Figure 2: Two plots`.

Limitations:

- `scale=` and `angle=` are dropped by Pandoc without a report.
- Vector images need the renderer (a later phase).
- A file with a valid header but broken content is shown as a placeholder without a diagnostic.

## Validation (`backend/check.py`)

`check(data)` returns a list of problems; empty means the package passed.

- The file is a ZIP without duplicate entries, and every `.xml` and `.rels` part is well-formed (parsed without entity expansion or network access).
- `[Content_Types].xml` declares a content type for every part, and every declared override exists.
- `_rels/.rels` and every other relationship file: ids are unique, every internal target exists.
- The main document is WordprocessingML with a body, and every `r:id`, `r:embed` and `r:link` in it has a relationship.
- Every paragraph, character and table style used is defined in `styles.xml`.
- Every `w:numId` used is defined in `numbering.xml`, and every numbering instance has its abstract definition.
- Bookmarks: unique ids, start and end paired, names follow Word's rules (letter or `_` first, letters, digits and `_`, at most 40 characters) and are unique ignoring case; every internal hyperlink (`w:anchor`) targets an existing bookmark.

Opening the output in Microsoft Word and LibreOffice is the final check (Stage 4.6). Stage 4.1 output converts with `soffice --headless --convert-to pdf`.

## Stages

| Stage | Work | Native node types | Status |
|---|---|---|---|
| 4.1 | Package foundation, contract, validation, determinism | — (text fallback for all) | Done |
| 4.2 | Styles and paragraphs | `Paragraph`, `Heading`, `TextRun`, `Break`, `Placeholder`, metadata | Done |
| 4.3 | Numbering and lists | `List`, `ListItem` (`numbering.xml`, `w:numPr`), custom item labels, description lists | Done |
| 4.4 | Tables and images | `Table`, `Row`, `Cell` (`w:tbl`, spans, header rows, widths), `Figure`, `Image` (`word/media`, DrawingML inline), captions | Done |
| 4.5 | Bookmarks and hyperlinks | `Anchor`, `CrossReference`, `Hyperlink`, bookmarks on headings, figures, tables, equations, theorems, bibliography entries | Planned |
| 4.6 | Integration and compatibility | `Bibliography`, `CodeBlock`, `Rule`, `Theorem`, `Quote`, `Container`, `Math`, `Citation`, `Footnote`; Word and LibreOffice open checks | Planned |
