# The document model (semantic IR)

Phase 3, extended in Phase 5. Package `tejtex.ir`. It turns the normalized Pandoc AST into a Word-independent model of the document. It does not import python-docx or lxml (tested); Phase 4 reads the model and writes OOXML.

```
doc = ir.build(ast, report, source, config)   # Document(meta, blocks, ctx)
```

## Content tree (`ir/nodes.py`)

| Pandoc | Model |
|---|---|
| `Para`, `Plain`, `LineBlock` | `Paragraph(style, inlines)` |
| `Header` | `Heading(level, inlines, style, number, bookmark, label, src)` |
| `BulletList`, `OrderedList`, `DefinitionList` | `List(kind, items, num, level, start)` with `ListItem(blocks, term, label, num)` — `label` is a custom `\item[...]` label and `num` its numbering instance |
| `Table` (and the `Div` Pandoc wraps around a labelled table) | `Table(rows, aligns, head, caption, number, bookmark, label, style, src, widths, name, seq)` with `Row` and `Cell(blocks, align, rowspan, colspan)`; `widths` holds Pandoc's relative column widths (`p{0.4\linewidth}` → `0.4`, otherwise `None`); `name` is the caption word (`Table`) |
| `Figure` | `Figure(blocks, caption, number, bookmark, label, src, name, seq)` |
| theorem-like `Div` | `Theorem(kind, name, blocks, number, title, bookmark, label, src, seq)` — Pandoc's static "Theorem 1.1 (Title)." prefix is parsed and removed; the number is the model's own (below) |
| `Div.thebibliography`, or the `.bib` files of `\bibliography`/`\addbibresource` | a `Heading` (`References`, or `Bibliography` with chapters), then `Bibliography(entries)` with `BibEntry(key, number, inlines, bookmark, seq)` |
| other `Div` | `Container(kind, blocks, bookmark, label)` |
| `BlockQuote`, `CodeBlock`, `HorizontalRule` | `Quote`, `CodeBlock`, `Rule` |
| `Str`, `Space`, `Emph`, `Strong`, `Underline`, `Strikeout`, `Superscript`, `Subscript`, `SmallCaps`, `Quoted`, `Code` | `TextRun(text, bold, italic, underline, strike, sup, sub, smallcaps, code)` — formatting is flattened onto runs, `\emph` toggles italic as in LaTeX, adjacent runs with the same formatting are merged |
| `LineBreak` | `Break` |
| `Math` | `Math(tex, display, numbers)` — `\label`, `\nonumber`, `\notag`, `\tag` are removed from `tex`; `numbers` is one `(text, bookmark, label, seq)` per numbered row (`seq` is `None` for `\tag` and `*`) |
| `Link` with `reference-type` | `CrossReference(label, kind, text, bookmark, src, field, number, before, after)` — `field` is `paragraph` for a numbered heading, `text` for a numbered figure, table, equation or theorem, and `None` otherwise; `number` is the target's number and `before`/`after` the text around it (`(`…`)` for `\eqref`, `Figure ` for `\autoref`) |
| other `Link` | `Hyperlink(inlines, url, rel, bookmark)` — `#label` targets get the label's bookmark; external targets get a relationship only when they are `http`, `https`, `ftp` or `mailto` URLs without spaces or quotes, otherwise the text stays without a link and a `partial` warning names the target |
| `Cite` | `Citation(keys, text, bookmarks, mode, src, numbers, suffix)` — one number per key (`?` for a missing key), and the optional text (`p. 5`) |
| `Image` | `Image(path, rel, media, width, height, alt, src)` — `rel` is set only for a file Word can show (PNG, JPEG, GIF, BMP, TIFF, recognised by content); other formats get a `render` diagnostic; Pandoc's default alt text `image` becomes empty |
| `Note` | `Footnote(number, blocks)` |
| `Span` with an id, bibliography anchors | `Anchor(bookmark, label)` |
| TejTeX placeholders | `Placeholder(category, element, text, src, inline)` |
| `RawBlock`, `RawInline` | `Placeholder` (unsupported) |
| metadata (`\title`, `\author`, `\date`, `abstract`) | `Meta(title, authors, date, abstract)` |

A number that Word can recompute carries a `Seq(name, within)`: the Word sequence that counts it (`Figure`, `Table`, `Equation`, the theorem counter, `Bib`) and the heading level it restarts at (`0` for never). The `number` text stays the number LaTeX prints, and the backend writes it as the field's cached result.

`ir.walk(node)` visits every node in document order without recursion. `ir.lines(doc)` gives a plain-text view, used by the Phase 1 backend until Phase 4.

## Document context (`ir/context.py`)

| Component | Holds |
|---|---|
| `StyleRegistry` | Semantic paragraph, character and table styles (`BodyText`, `Compact`, `Heading1`–`Heading6` named `heading 1`… so Word's Navigation Pane sees them, `Caption`, `Bibliography`, `FootnoteText`, `Hyperlink`, `TejTeX Placeholder`, `Table` based on Word's `Table Grid`, …), each with its base style; records which styles the document uses |
| `NumberingEngine` | One outline list for numbered headings (`%1`, `%1.%2`, `%1.%2.%3`, each level linked to its heading style), created when the first numbered heading is registered. One abstract list definition per list kind, format and offset (LaTeX defaults: `1.`, `(a)`, `i.`, `A.`; bullets `•`, `–`, `∗`, `·`) and one numbering instance per list with its nesting level and start value, so every list restarts like LaTeX and nested lists are indented by level. Labels follow the depth of each kind, as in LaTeX: an `enumerate` inside an `itemize` is numbered `1.`, not `(a)`, but indented one level deeper. A custom `\item[...]` label gets one instance per label text, with format `none` and the label as its text |
| `RelationshipManager` | Relationship ids (`rTej1`, …) for images and external hyperlinks; media part names `media/image<n>.<ext>` are generated, never taken from source paths, with the extension of the detected format; the same file or URL gets the same relationship |
| `ReferenceTracker` | Every label and bibliography key with its kind, number, bookmark name and source location; duplicates are reported |
| `SourceMap` | File, line and column of `\label`, `\ref`-family commands, `\cite`-family commands and image paths, through the Phase 2 source map |
| `diags` | The diagnostics report |
| `caps` | The capability registry |

Bookmark names follow Word's rules: they start with a letter, use only `A–Z a–z 0–9 _`, have at most 40 characters and are unique ignoring case (`fig:a` → `fig_a`, then `fig_a_2`; `1abc` → `L1abc`; bibliography keys get `bib_`).

## Two passes (`ir/build.py`)

1. **Registration** walks the AST once in document order and assigns, before anything is built: section numbers, figure, table and equation numbers, theorem numbers, footnote numbers, list numbering instances, relationship ids for images and links, bibliography entry numbers, and a target for every label. A reference that appears before its target therefore resolves.
2. **Instantiation** builds the content tree and asks the context for numbers, bookmarks and relationship ids. An undefined `\ref`, `\cref` or `\hyperref` becomes `??` (`\eqref` becomes `(??)`, as in LaTeX) with a warning at its source location; a citation key missing from the bibliography becomes `?` with a warning.

Between the passes the `.bib` files are read (`ir/bib.py`), so citations before the bibliography get their numbers.

Numbering rules follow LaTeX:

- Headings: levels 1–3 are numbered hierarchically (`1`, `1.1`, `1.1.1`), starred headings are not. If the document uses `\chapter`, level 1 is the chapter and figures, tables and equations are numbered per chapter (`2.1`). `\numberwithin{equation}{section}` (or `figure`, `table`, a theorem counter) numbers within that heading level; a deeper level cannot restart a Word sequence, so it gets a warning and the numbers run on.
- Equations: `equation`, `align`, `gather`, `multline`, `flalign`, `alignat`, `eqnarray` are numbered unless starred; multi-row environments get one number per row, split at top-level `\\`; `\nonumber`/`\notag` skip a row; `\tag{x}` sets the number without counting.
- Theorems: counted by the model from the `\newtheorem` lines in the source, as LaTeX counts them. `\newtheorem{lemma}[theorem]{Lemma}` shares the `theorem` counter, `\newtheorem{definition}{Definition}[section]` numbers within sections (`1.1.1` in a chapter document), `\newtheorem{remark}{Remark}` counts through the whole document (`1`, `2`), and `\newtheorem*` environments are unnumbered. Pandoc numbers some of these differently (it numbered the remark `1.1` and the starred environment `1.1`), so its numbers are only used for an environment whose `\newtheorem` the model cannot see (defined in a package, or with `\declaretheorem`); such a number stays static text and gets an `info` diagnostic.
- List items: `\label` in an `enumerate` item refers to the item as LaTeX prints it: `2`, `2a`, `2(a)iii`. With an explicit format the counter is written in that format (`[(a)]` with the enumerate package gives `a`); when the document loads enumitem the reference is the whole label (`(a)`, `C.`), which is enumitem's default. A custom `\item[x]` does not step the counter, and a `\label` after it refers to the previous item. In a footnote `\label` refers to the footnote; elsewhere to the current section.
- Bibliography: `thebibliography` entries are numbered in order. Otherwise the `.bib` files of `\bibliography{a,b}` or `\addbibresource{a.bib}` are read (inside the project root, like included files) and the bibliography is built from them: every cited key and every `\nocite` key (`\nocite{*}` for all) that has an entry, once. Missing files and missing keys are warnings. Citations read `[1]`, `[1, 2, p. 5]`; without any bibliography the key is shown (`[knuth84]`) with a warning.

## Bibliography files (`ir/bib.py`)

A small BibTeX reader, no external package:

- **Parsing.** `@type{key, field = value, …}` with values in braces, quotes, bare numbers or `@string` macros, joined with `#`; month macros (`jan` → `January`); `@comment` and `@preamble` are skipped. Accents (`{\"o}`, `\'e`, `\c{c}`), special letters (`\ss`, `\o`, `\i`), `--`, `---`, ``` `` ```, `''` and `~` are turned into Unicode; other commands are dropped and braces removed.
- **Order.** With `\bibliographystyle{plain}` (also `abbrv`, `alpha`, `plainnat`, `abbrvnat`, `acm`, `siam`, `apalike`, `amsplain`, `amsalpha`) entries are sorted by the first author's family name, year and title; with `unsrt` and other styles they follow the order of first citation. biblatex (`\addbibresource`) sorts by name, title and year, or in citation order with `sorting=none`.
- **Format.** One plain numeric format close to BibTeX's `plain`: authors (`A, B, and C`), title, then by type — `article` (journal in italics, `volume(number):pages`, year), `inproceedings`/`incollection` (`In` editors, book title in italics, pages, publisher, year), `book` (title in italics, publisher, edition as `third edition`, year), `phdthesis`/`mastersthesis`, `techreport`, and anything else with `howpublished` and year; then `note`. With a BibTeX style, titles of articles, papers and reports are in sentence case as BibTeX writes them (`On dynamic fields`), keeping braced words (`{GPU}`). A `url` becomes an external link after the entry.

## Limits

Registration stops with exit code 6 when the AST is nested more than 100 levels or has more than 1,000,000 nodes (`Config.nesting`, `Config.nodes`). Both passes therefore stay far below Python's recursion limit; a JSON input that is too deep for Python's parser is also reported as exit code 6.
