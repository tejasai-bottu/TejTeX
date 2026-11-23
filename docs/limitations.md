# Supported features and known limitations

This is the state at the end of Phase 4 (Milestone 1). Every construct TejTeX cannot convert is reported with its file, line and column, and its content stays visible in the document. Nothing is dropped silently, apart from the few Pandoc behaviours listed under "Unsupported".

## Supported — native Word structures

| Feature | LaTeX | Word |
|---|---|---|
| Headings | `\chapter`, `\section` … `\subparagraph`, starred forms | Built-in `heading 1`–`6`, so they appear in the Navigation Pane; the number is text in the heading |
| Paragraphs | body text, quotations, `center` and other environments | Native paragraphs with the model's styles |
| Character formatting | `\textbf`, `\emph` (nested), `\textit`, `\underline`, `\sout`, `\textsc`, `\textsuperscript`, `\textsubscript`, `\texttt` | `w:b`, `w:i`, `w:u`, `w:strike`, `w:smallCaps`, `w:vertAlign`, the `Verbatim Char` style |
| Title block | `\title`, `\author`, `\date`, `\maketitle`, `abstract` | `Title`, `Author`, `Date` and `Abstract` paragraphs; document properties |
| Lists | `itemize`, `enumerate`, `description`, nested to any depth | Native numbering (`numbering.xml`): Enter continues a list, Tab and Shift+Tab change the level |
| List labels | LaTeX defaults per depth, enumerate-package markers (`[(a)]`, `[i.]`), enumitem `label=` with one counter and `start=`, `\setcounter{enumi}`, `\item[x]` | Word number formats; custom labels as literal level text |
| Tables | `tabular`, `longtable`, `\multicolumn`, `\multirow`, header rows, `l`/`c`/`r`, `p{0.4\linewidth}` | `w:tbl` with merged cells, repeating header rows, alignment and widths |
| Images | `\includegraphics` with PNG, JPEG, GIF, BMP or TIFF; `width`, `height` in any LaTeX unit or as a fraction of `\linewidth`/`\textheight` | Inline pictures in `word/media/`, each file stored once |
| Figures and captions | `figure`, `table`, `\caption` | `Figure 1: …` below the figure and `Table 1: …` above the table, in Word's `caption` style |
| Bookmarks | `\label` on headings, figures, tables, equations, theorems, items, footnotes and other environments; `\bibitem` | Word bookmarks with valid, unique names |
| Internal links | `\ref`, `\eqref`, `\autoref`, `\cref`, `\Cref`, `\hyperref[…]{…}`, `\cite` | `w:hyperlink` to the bookmark, with the number LaTeX prints |
| External links | `\href`, `\url` with `http`, `https`, `ftp` or `mailto` | `w:hyperlink` with an external relationship, `Hyperlink` style |
| Theorems | amsthm `\newtheorem`, shared counters, optional titles | `Theorem 1 (Title).` in bold, then the body |
| Bibliography | `thebibliography` | `[1] …` paragraphs in the `Bibliography` style |
| Code | `verbatim`, `\texttt` | `Source Code` paragraphs, `Verbatim Char` runs |

## Partially supported

| Feature | What happens | Planned |
|---|---|---|
| Mathematics | Written as its TeX source; display equations carry their numbers `(1)` and bookmarks, so `\eqref` links work | Office Math (OMML), Phase 5 |
| Footnotes | `[1]` in the text; the footnote text follows at the end of the document | Native Word footnotes, Phase 5 |
| Numbers | Heading, caption, equation and reference numbers are static text. Moving a section in Word does not renumber anything | Heading numbering linked to the heading styles; SEQ and REF fields; Phase 5 |
| Table borders | Every table uses the `Table` style (Word's `Table Grid` look). Pandoc does not pass on `|`, `\hline` or booktabs rules | Per-table rules need a source-level pass |
| Table captions | Always above the table; Pandoc does not pass on where the caption was | — |
| Fixed column widths | `p{3cm}` arrives without a size and is treated like an automatic column | — |
| An item that starts with a nested list | Its number is on its own line; LaTeX puts both labels on one line | — |
| enumitem | `resume`, labels with text (`Step \arabic*:`) and `itemize` labels are reported; the list uses its default format and restarts | — |
| Custom item labels with mathematics | Shown as TeX (`\star`) | Phase 5 |
| Bibliographies from `.bib` files | `\cite` shows the key; no bibliography is generated | Phase 5 |
| Links to other targets | `javascript:`, `file:`, `data:` and relative links keep their text without a link (warning) | By design |

## Unsupported — visible placeholder and diagnostic

| Construct | Placeholder |
|---|---|
| TikZ, PGF and similar pictures | `[TejTeX: tikzpicture needs rendering]` (category `render`) |
| PDF, EPS and SVG images | `[image: figs/plot.pdf]` (category `render`) |
| Missing or rejected images | `[image: path]` or `[TejTeX: image … rejected]` |
| Unknown commands with arguments, raw LaTeX | `[TejTeX: \foo is not supported]` |
| `\tableofcontents`, `\listoffigures`, `\printbibliography` | `[TejTeX: … is not supported]` |
| Page layout (`geometry`, `fancyhdr`, `\vspace`, `\centering`, …) | Not transferred; reported as layout that Word handles |

Placeholders use the `TejTeX Placeholder` styles (red italic), so they are easy to find and replace in Word.

Pandoc drops a few things without reporting them, so TejTeX cannot report them either:

- `scale=` and `angle=` on `\includegraphics`;
- vertical rules and rule positions in tables;
- `\pageref`;
- horizontal rules, which have no text.

## Microsoft Word and LibreOffice

The same documents were checked in Microsoft Word 16.0.20625 (Office16, Windows 11) and LibreOffice 26.2 (Linux). The results are in [phase4-test-report.md](phase4-test-report.md). Differences:

- **Link addresses.** Word shows an external link's address in its normalised form (`https://www.ctan.org/` for `https://www.ctan.org`). The link target is the same.
- **List formats.** LibreOffice converts Word's list definitions into its own list styles. The numbers it shows are the same as Word's.
- **Adjacent tables.** Both programs merge two tables that touch into one table. TejTeX always puts a paragraph between them.
- **Automated Word checks.** These cover structure and behaviour (numbering, Enter and Tab, merges, header rows, pictures, bookmarks, link targets). How the page looks, and opening an external link in a browser, are checked by hand; see the test report.

## Known unresolved issues

- Mathematics, native footnotes, fields, `.bib` bibliographies and the TikZ/vector-image renderer are Phases 5 and 6.
- There is no size limit for embedded image files yet (Phase 6 limits).
- Windows has no CPU or memory limit for Pandoc apart from Pandoc's own `+RTS -M` (Phase 6).
