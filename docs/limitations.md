# Supported features and known limitations

This is the state at the end of Phase 5. Every construct TejTeX cannot convert is reported with its file, line and column, and its content stays visible in the document. Nothing is dropped silently, apart from the few Pandoc behaviours listed under "Unsupported".

## Supported — native Word structures

| Feature | LaTeX | Word |
|---|---|---|
| Headings | `\chapter`, `\section` … `\subparagraph`, starred forms | Built-in `heading 1`–`6`, so they appear in the Navigation Pane; levels 1–3 are numbered by an outline list linked to the heading styles, so inserted or moved headings renumber |
| Paragraphs | body text, quotations, `center` and other environments | Native paragraphs with the model's styles |
| Character formatting | `\textbf`, `\emph` (nested), `\textit`, `\underline`, `\sout`, `\textsc`, `\textsuperscript`, `\textsubscript`, `\texttt` | `w:b`, `w:i`, `w:u`, `w:strike`, `w:smallCaps`, `w:vertAlign`, the `Verbatim Char` style |
| Title block | `\title`, `\author`, `\date`, `\maketitle`, `abstract` | `Title`, `Author`, `Date` and `Abstract` paragraphs; document properties |
| Lists | `itemize`, `enumerate`, `description`, nested to any depth | Native numbering (`numbering.xml`): Enter continues a list, Tab and Shift+Tab change the level |
| List labels | LaTeX defaults per depth, enumerate-package markers (`[(a)]`, `[i.]`), enumitem `label=` with one counter and `start=`, `\setcounter{enumi}`, `\item[x]` | Word number formats; custom labels as literal level text |
| Tables | `tabular`, `longtable`, `\multicolumn`, `\multirow`, header rows, `l`/`c`/`r`, `p{0.4\linewidth}` | `w:tbl` with merged cells, repeating header rows, alignment and widths |
| Images | `\includegraphics` with PNG, JPEG, GIF, BMP or TIFF; `width`, `height` in any LaTeX unit or as a fraction of `\linewidth`/`\textheight` | Inline pictures in `word/media/`, each file stored once |
| Figures and captions | `figure`, `table`, `\caption` | `Figure 1: …` below the figure and `Table 1: …` above the table, in Word's `caption` style; the number is a `SEQ` field (with `STYLEREF` for chapter numbers) |
| Equation numbers | numbered `equation`, `align`, `gather`, … rows, `\nonumber`, `\tag`, `\numberwithin` | `(1)` or `(2.1)` after the equation, as `SEQ Equation` fields; `\tag` stays text |
| Theorem numbers | `\newtheorem` with shared counters (`[theorem]`), numbering within a section or chapter (`[section]`), `\newtheorem*` | `SEQ` fields per counter, restarted at the right heading level |
| Bookmarks | `\label` on headings, figures, tables, equations, theorems, items, footnotes and other environments; `\bibitem` | Word bookmarks with valid, unique names |
| Cross-references | `\ref`, `\eqref`, `\autoref`, `\cref`, `\Cref` to headings, figures, tables, equations and theorems | `REF` fields to the bookmark (`\h`: Ctrl+click follows them), updated with the numbers |
| Internal links | `\ref` to list items and footnotes, `\hyperref[…]{…}` | `w:hyperlink` to the bookmark, with the text LaTeX prints |
| External links | `\href`, `\url` with `http`, `https`, `ftp` or `mailto` | `w:hyperlink` with an external relationship, `Hyperlink` style |
| Theorems | amsthm `\newtheorem`, shared counters, optional titles | `Theorem 1 (Title).` in bold, then the body |
| Bibliography | `thebibliography`; `.bib` files with `\bibliography`, `\bibliographystyle`, `\nocite`, or biblatex's `\addbibresource` and `\printbibliography` | `[1] …` paragraphs in the `Bibliography` style with `SEQ` numbers; every cited key gets an entry, missing keys are reported |
| Citations | `\cite`, `\cite[p.~5]{…}`, several keys | `[1, 2, p. 5]` with one `REF` field per number |
| Code | `verbatim`, `\texttt` | `Source Code` paragraphs, `Verbatim Char` runs |

## Partially supported

| Feature | What happens | Planned |
|---|---|---|
| Mathematics | Written as its TeX source; display equations carry their numbers `(1)` as fields and bookmarks, so `\eqref` works | Office Math (OMML), a later phase |
| Footnotes | `[1]` in the text; the footnote text follows at the end of the document | Native Word footnotes, a later phase |
| Bibliography format | One numeric format close to BibTeX's `plain` for every style; author-year styles (natbib `\citet`, biblatex `authoryear`) are still numeric. The entry text is static, so editing a `.bib` file needs a new compile | Native Word sources were investigated and not adopted ([ADR 0003](decisions/0003-word-citations.md)) |
| Theorem numbers from packages | An environment whose `\newtheorem` is not in the source (a `.sty` file, thmtools `\declaretheorem`) keeps Pandoc's number as static text, with an `info` diagnostic | — |
| Numbering within deep levels | Word restarts a sequence only at heading levels 1–3. `\numberwithin` at a deeper level is reported and its numbers run on through the document; a theorem numbered within a deeper level keeps Pandoc's number as static text (`info`) | — |
| Unnumbered headings and sequences | A starred `\chapter*` (or `\section*` in an article) restarts chapter-relative sequences in Word, because it still has the `heading 1` style, but not in LaTeX. A chapter-relative number before the first chapter (LaTeX's `0.1`) has no heading to refer to and shows Word's "no text of specified style" error after an update | — |
| Table borders | Every table uses the `Table` style (Word's `Table Grid` look). Pandoc does not pass on `|`, `\hline` or booktabs rules | Per-table rules need a source-level pass |
| Table captions | Always above the table; Pandoc does not pass on where the caption was | — |
| Fixed column widths | `p{3cm}` arrives without a size and is treated like an automatic column | — |
| An item that starts with a nested list | Its number is on its own line; LaTeX puts both labels on one line | — |
| enumitem | `resume`, labels with text (`Step \arabic*:`) and `itemize` labels are reported; the list uses its default format and restarts | — |
| Custom item labels with mathematics | Shown as TeX (`\star`) | With OMML |
| Links to other targets | `javascript:`, `file:`, `data:` and relative links keep their text without a link (warning) | By design |

## Unsupported — visible placeholder and diagnostic

| Construct | Placeholder |
|---|---|
| TikZ, PGF and similar pictures | `[TejTeX: tikzpicture needs rendering]` (category `render`) |
| PDF, EPS and SVG images | `[image: figs/plot.pdf]` (category `render`) |
| Missing or rejected images | `[image: path]` or `[TejTeX: image … rejected]` |
| Unknown commands with arguments, raw LaTeX | `[TejTeX: \foo is not supported]` |
| `\tableofcontents`, `\listoffigures`, `\listoftables` | `[TejTeX: … is not supported]` |
| Page layout (`geometry`, `fancyhdr`, `\vspace`, `\centering`, …) | Not transferred; reported as layout that Word handles |

Placeholders use the `TejTeX Placeholder` styles (red italic), so they are easy to find and replace in Word.

Pandoc drops a few things without reporting them, so TejTeX cannot report them either:

- `scale=` and `angle=` on `\includegraphics`;
- vertical rules and rule positions in tables;
- `\pageref`;
- horizontal rules, which have no text.

## Microsoft Word and LibreOffice

The same documents were checked in Microsoft Word 16.0.20625 (Office16, Windows 11) and LibreOffice 26.2 (Linux). The results are in [phase4-test-report.md](phase4-test-report.md) and [phase5-test-report.md](phase5-test-report.md). Differences:

- **Link addresses.** Word shows an external link's address in its normalised form (`https://www.ctan.org/` for `https://www.ctan.org`). The link target is the same.
- **List formats.** LibreOffice converts Word's list definitions into its own list styles. The numbers it shows are the same as Word's.
- **Adjacent tables.** Both programs merge two tables that touch into one table. TejTeX always puts a paragraph between them.
- **Automated Word checks.** These cover structure and behaviour: numbering, Enter and Tab, merges, header rows, pictures, bookmarks and link targets. Kiran checked the rest in Word by hand: no repair prompt, the Navigation Pane, Ctrl+click on an external link, the Bookmark dialog, header rows on later pages, dragging a picture, and editing and saving. Results are in the test report.
- **Fields in LibreOffice.** LibreOffice imports every `SEQ`, `STYLEREF` and `REF` field and the heading numbering, but it recomputes sequences when it opens a file and ignores `SEQ`'s `\s` restart. Numbers per chapter or section are therefore right in the first chapter only (LibreOffice shows `2.2` where Word and LaTeX show `2.1`), and references follow. Word shows the right numbers before and after an update.
- **Updating fields in Word.** Word does not update fields when it opens a file; the cached numbers are already right. After inserting or moving content, select the text (Ctrl+A) and press F9.
- **Damaged files.** Word refuses a file with malformed XML but opens some structurally broken files without any message. TejTeX's checker catches those cases before a file is written.

## Known unresolved issues

- Mathematics (OMML), native footnotes and the TikZ/vector-image renderer are later phases.
- There is no size limit for embedded image files yet (Phase 6 limits).
- Windows has no CPU or memory limit for Pandoc apart from Pandoc's own `+RTS -M` (Phase 6).
