# 0003 — Bibliography: static entries with field numbers, not Word sources

Status: accepted (Phase 5, 22 November 2026)

## Question

Stage 5.6 asks to investigate Word's native citation system and to keep it apart from the static bibliography. Should TejTeX write `.bib` entries as Word sources, with `CITATION` and `BIBLIOGRAPHY` fields, instead of text?

## What Word's native citations are

- **Sources.** A Custom XML part (`customXml/item1.xml` with its properties part) holds `b:Sources` in the bibliography namespace `http://schemas.openxmlformats.org/officeDocument/2006/bibliography` (ECMA-376 Part 1, §22.6). Each `b:Source` has a `b:Tag` (the key), a `b:SourceType` (`Book`, `JournalArticle`, `ConferenceProceedings`, `Report`, `Misc`, …), structured names (`b:Person` with `b:Last`, `b:First`) and fields such as `b:Title`, `b:Year`, `b:Publisher`, `b:Pages`. `References ▸ Manage Sources` edits them.
- **Citations.** A content control (`w:sdt` with `w:citation`) around a `CITATION knuth \l 1033` field; further keys are `\m key`, a page is `\p 5`.
- **Bibliography.** A content control (`w:docPartObj`, gallery `Bibliographies`) around a `BIBLIOGRAPHY` field.
- **Formatting.** Word formats both with its own XSLT styles (APA, Chicago, GB7714, GOST, Harvard, IEEE, ISO 690, MLA, SIST02, Turabian) and rewrites the text whenever the fields are updated. The style is chosen in Word, per document.

## Comparison

| | Static entries + `SEQ`/`REF` (chosen) | Word sources + `CITATION`/`BIBLIOGRAPHY` |
|---|---|---|
| Looks like the LaTeX output | Yes: order and format follow `\bibliographystyle` (sorted styles, `unsrt`, sentence-case titles) | No: none of Word's styles is a BibTeX style; `plain` and `unsrt` cannot be reproduced, and an update replaces TejTeX's text with Word's |
| Numbers follow edits | Yes: a new or moved entry renumbers its citations after an update | Yes, with Word's numeric styles (IEEE) |
| Entries editable in Word | As text | As structured sources (Manage Sources) |
| LibreOffice | Shown and numbered (with LibreOffice's field limits, see [limitations.md](../limitations.md)) | Not checked; LibreOffice keeps its own bibliography database |
| Mapping effort | None beyond the `.bib` reader | Every BibTeX type and field needs a Word source type and field; `misc`, `techreport` and theses fit only loosely; braces, accents and macros must still be decoded |
| Validation | Bookmarks and fields are checked (`REF` targets exist) | Custom XML parts, content controls and source tags would need new checks |

## Decision

Keep the bibliography that TejTeX writes from `thebibliography` or the `.bib` files as static text, with a `SEQ Bib` field for each entry number and a `REF` field for each number in a citation. It stays the bibliography LaTeX prints, and it still renumbers when entries are added or moved in Word.

Word sources are not written. They would trade LaTeX's formatting for Word's and make the output depend on which style Word applies. If users ask to manage references in Word, an opt-in mode could write `b:Sources` with `CITATION` and `BIBLIOGRAPHY` fields in Word's IEEE style. This needs a prototype checked in Word and LibreOffice first.

## Consequences

- Editing an entry's text in Word does not change other entries, and adding a `.bib` entry needs a new compile.
- Author-year citation styles (natbib `\citet`, biblatex `authoryear`) are still written as numbers ([limitations.md](../limitations.md)).
- `tests/test_bib.py` and `tests/test_fields.py` cover the reader, the order and format, the fields and their targets.
