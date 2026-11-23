# The document model (semantic IR)

Phase 3. Package `tejtex.ir`. It turns the normalized Pandoc AST into a Word-independent model of the document. It does not import python-docx or lxml (tested); Phase 4 reads the model and writes OOXML.

```
doc = ir.build(ast, report, source, config)   # Document(meta, blocks, ctx)
```

## Content tree (`ir/nodes.py`)

| Pandoc | Model |
|---|---|
| `Para`, `Plain`, `LineBlock` | `Paragraph(style, inlines)` |
| `Header` | `Heading(level, inlines, style, number, bookmark, label, src)` |
| `BulletList`, `OrderedList`, `DefinitionList` | `List(kind, items, num, level, start)` with `ListItem(blocks, term, label, num)` — `label` is a custom `\item[...]` label and `num` its numbering instance |
| `Table` (and the `Div` Pandoc wraps around a labelled table) | `Table(rows, aligns, head, caption, number, bookmark, label, style, src, widths, name)` with `Row` and `Cell(blocks, align, rowspan, colspan)`; `widths` holds Pandoc's relative column widths (`p{0.4\linewidth}` → `0.4`, otherwise `None`); `name` is the caption word (`Table`) |
| `Figure` | `Figure(blocks, caption, number, bookmark, label, src, name)` |
| theorem-like `Div` | `Theorem(kind, name, blocks, number, title, bookmark, label, src)` — Pandoc's static "Theorem 1.1 (Title)." prefix is parsed and removed |
| `Div.thebibliography` | `Bibliography(entries)` with `BibEntry(key, number, inlines, bookmark)` |
| other `Div` | `Container(kind, blocks, bookmark, label)` |
| `BlockQuote`, `CodeBlock`, `HorizontalRule` | `Quote`, `CodeBlock`, `Rule` |
| `Str`, `Space`, `Emph`, `Strong`, `Underline`, `Strikeout`, `Superscript`, `Subscript`, `SmallCaps`, `Quoted`, `Code` | `TextRun(text, bold, italic, underline, strike, sup, sub, smallcaps, code)` — formatting is flattened onto runs, `\emph` toggles italic as in LaTeX, adjacent runs with the same formatting are merged |
| `LineBreak` | `Break` |
| `Math` | `Math(tex, display, numbers)` — `\label`, `\nonumber`, `\notag`, `\tag` are removed from `tex`; `numbers` is one `(text, bookmark, label)` per numbered row |
| `Link` with `reference-type` | `CrossReference(label, kind, text, bookmark, src)` |
| other `Link` | `Hyperlink(inlines, url, rel, bookmark)` — `#label` targets get the label's bookmark; external targets get a relationship only when they are `http`, `https`, `ftp` or `mailto` URLs without spaces or quotes, otherwise the text stays without a link and a `partial` warning names the target |
| `Cite` | `Citation(keys, text, bookmarks, mode, src)` |
| `Image` | `Image(path, rel, media, width, height, alt, src)` — `rel` is set only for a file Word can show (PNG, JPEG, GIF, BMP, TIFF, recognised by content); other formats get a `render` diagnostic; Pandoc's default alt text `image` becomes empty |
| `Note` | `Footnote(number, blocks)` |
| `Span` with an id, bibliography anchors | `Anchor(bookmark, label)` |
| TejTeX placeholders | `Placeholder(category, element, text, src, inline)` |
| `RawBlock`, `RawInline` | `Placeholder` (unsupported) |
| metadata (`\title`, `\author`, `\date`, `abstract`) | `Meta(title, authors, date, abstract)` |

`ir.walk(node)` visits every node in document order without recursion. `ir.lines(doc)` gives a plain-text view, used by the Phase 1 backend until Phase 4.

## Document context (`ir/context.py`)

| Component | Holds |
|---|---|
| `StyleRegistry` | Semantic paragraph, character and table styles (`BodyText`, `Compact`, `Heading1`–`Heading6` named `heading 1`… so Word's Navigation Pane sees them, `Caption`, `Bibliography`, `FootnoteText`, `Hyperlink`, `TejTeX Placeholder`, `Table` based on Word's `Table Grid`, …), each with its base style; records which styles the document uses |
| `NumberingEngine` | One abstract list definition per list kind, format and offset (LaTeX defaults: `1.`, `(a)`, `i.`, `A.`; bullets `•`, `–`, `∗`, `·`) and one numbering instance per list with its nesting level and start value, so every list restarts like LaTeX and nested lists are indented by level. Labels follow the depth of each kind, as in LaTeX: an `enumerate` inside an `itemize` is numbered `1.`, not `(a)`, but indented one level deeper. A custom `\item[...]` label gets one instance per label text, with format `none` and the label as its text |
| `RelationshipManager` | Relationship ids (`rTej1`, …) for images and external hyperlinks; media part names `media/image<n>.<ext>` are generated, never taken from source paths, with the extension of the detected format; the same file or URL gets the same relationship |
| `ReferenceTracker` | Every label and bibliography key with its kind, number, bookmark name and source location; duplicates are reported |
| `SourceMap` | File, line and column of `\label`, `\ref`-family commands, `\cite`-family commands and image paths, through the Phase 2 source map |
| `diags` | The diagnostics report |
| `caps` | The capability registry |

Bookmark names follow Word's rules: they start with a letter, use only `A–Z a–z 0–9 _`, have at most 40 characters and are unique ignoring case (`fig:a` → `fig_a`, then `fig_a_2`; `1abc` → `L1abc`; bibliography keys get `bib_`).

## Two passes (`ir/build.py`)

1. **Registration** walks the AST once in document order and assigns, before anything is built: section numbers, figure, table and equation numbers, theorem numbers, footnote numbers, list numbering instances, relationship ids for images and links, bibliography entry numbers, and a target for every label. A reference that appears before its target therefore resolves.
2. **Instantiation** builds the content tree and asks the context for numbers, bookmarks and relationship ids. An undefined `\ref`, `\cref` or `\hyperref` becomes `??` (`\eqref` becomes `(??)`, as in LaTeX) with a warning at its source location; a citation key missing from `thebibliography` becomes `?` with a warning.

Numbering rules follow LaTeX:

- Headings: levels 1–3 are numbered hierarchically (`1`, `1.1`, `1.1.1`), starred headings are not. If the document uses `\chapter`, level 1 is the chapter and figures, tables and equations are numbered per chapter (`2.1`).
- Equations: `equation`, `align`, `gather`, `multline`, `flalign`, `alignat`, `eqnarray` are numbered unless starred; multi-row environments get one number per row, split at top-level `\\`; `\nonumber`/`\notag` skip a row; `\tag{x}` sets the number without counting.
- Theorems: the number Pandoc writes (it knows shared counters such as `\newtheorem{lemma}[theorem]`).
- List items: `\label` in an `enumerate` item refers to the item as LaTeX prints it: `2`, `2a`, `2(a)iii`. With an explicit format the counter is written in that format (`[(a)]` with the enumerate package gives `a`); when the document loads enumitem the reference is the whole label (`(a)`, `C.`), which is enumitem's default. A custom `\item[x]` does not step the counter, and a `\label` after it refers to the previous item. In a footnote `\label` refers to the footnote; elsewhere to the current section.
- Bibliography: entries are numbered in order; citations read `[1]`, `[1, 2, p. 5]`; without a `thebibliography` the key is shown (`[knuth84]`) until Phase 5 reads `.bib` files.

## Limits

Registration stops with exit code 6 when the AST is nested more than 100 levels or has more than 1,000,000 nodes (`Config.nesting`, `Config.nodes`). Both passes therefore stay far below Python's recursion limit; a JSON input that is too deep for Python's parser is also reported as exit code 6.
