# The DOCX backend

Phase 4. Package `tejtex.backend`. It writes the document model (`tejtex.ir`, see [ir.md](ir.md)) as a DOCX package.

## Rule: the model owns meaning, the backend owns representation

The backend does not decide anything the model already knows. It takes numbers, bookmark names, relationship ids, list instances and levels, style ids and placeholder texts from the model and writes them as Word structures. It never computes a figure number, resolves a label or chooses a list's restart behaviour.

This is enforced: the backend may import only `tejtex.ir.nodes` and `tejtex.errors` from TejTeX (`tests/test_backend.py::test_backend_imports_only_the_model`).

## Contract

```
data = backend.render(doc)        # bytes of a .docx package
backend.write(doc, out)           # render, then write the file
```

- Every model node type is routed (`writer.BLOCKS`, `writer.INLINES`; `ListItem`, `Row`, `Cell`, `BibEntry`, `Meta` and `Document` are handled by their parents). A test fails if a node type is added to the model without a route. A node of an unknown type is an internal error (exit code 1).
- A node type with a native handler is written as Word structures. A node type without one goes through the **text fallback**: its text, numbers, resolved references, placeholders, image paths and footnote markers are written as plain paragraphs, so no content is lost while the stages below are built. Metadata (title, authors, date, abstract) is written first and footnote texts last, also through the fallback for now.
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
| 4.2 | Styles and paragraphs | `Paragraph`, `Heading`, `TextRun`, `Break`, metadata | Planned |
| 4.3 | Numbering and lists | `List` (`numbering.xml`, `w:numPr`) | Planned |
| 4.4 | Tables and images | `Table`, `Figure`, `Image` (`word/media`, DrawingML) | Planned |
| 4.5 | Bookmarks and hyperlinks | `Anchor`, `CrossReference`, `Hyperlink`, bookmarks on headings, figures, tables, equations, theorems, bibliography entries | Planned |
| 4.6 | Integration and compatibility | remaining types; Word and LibreOffice open checks | Planned |
