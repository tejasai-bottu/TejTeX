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
- A node type with a native handler is written as Word structures. A node type without one goes through the **text fallback**, so no content is lost while the stages below are built:
  - a container whose own structure is not native yet (`List`, `Table`, `Figure`, `Theorem`, `Quote`, `Container`) writes its child blocks through the normal routing, so their paragraphs and runs are native; only the container's own structure (numbering, table grid, …) is still missing;
  - a block without children (`Bibliography`, `CodeBlock`, `Rule`) is written as plain `Normal` paragraphs with its text;
  - an inline node without a handler (`Math`, `Citation`, `CrossReference`, `Hyperlink`, `Image`, `Footnote`) is written as a plain run with its text, resolved number or `[image: path]`; footnote texts follow at the end of the document.
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
| Table | table | template default |

Word's own style names are used for built-in styles, so Word treats them as its built-in styles.

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
| 4.3 | Numbering and lists | `List` (`numbering.xml`, `w:numPr`) | Planned |
| 4.4 | Tables and images | `Table`, `Figure`, `Image` (`word/media`, DrawingML) | Planned |
| 4.5 | Bookmarks and hyperlinks | `Anchor`, `CrossReference`, `Hyperlink`, bookmarks on headings, figures, tables, equations, theorems, bibliography entries | Planned |
| 4.6 | Integration and compatibility | `Bibliography`, `CodeBlock`, `Rule`, `Theorem`, `Quote`, `Container`, `Math`, `Citation`, `Footnote`; Word and LibreOffice open checks | Planned |
