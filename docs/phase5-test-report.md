# Phase 5 test report — Advanced document semantics

Date: 22 November 2026. Scope: Stages 5.1–5.6.

**Result: Phase 5 is complete.** A heading, a section, a figure, an equation and a theorem were inserted into a generated document in Microsoft Word. After updating the fields, every number and reference was correct. Every hyperlink anchor and `REF` field resolves to an existing bookmark.

## Completion criteria

| # | Criterion | Status |
|---|---|---|
| 5.1 | Heading numbering uses Word's heading styles and a native list, 1 / 1.1 / 1.1.1, and survives inserted and moved headings | Done. Word renumbered after an inserted chapter and section (below); `test_headings_renumber_when_inserted_or_moved` |
| 5.2 | `SEQ` fields for figure and table captions; numbers update after insertion; references stay on their captions | Done. An inserted figure moved `fig_one` from 1.1 to 2.2 in Word |
| 5.3 | `SEQ` fields for equation numbers; labels and bookmarks kept; references update | Done. An inserted equation moved `eq_one` from 1.1.1 to 2.1.2 |
| 5.4 | Native fields for theorem numbers; names and numbering relationships kept; agreed schemes | Done. Shared counter, per chapter, per section, global and starred schemes, all matching `pdflatex` |
| 5.5 | `REF` fields for headings, figures, tables, equations and theorems; targets exist; undefined references diagnostic | Done. 17 `REF` fields in the `fields` corpus, all resolved in Word; the checker rejects a `REF` to a missing bookmark |
| 5.6 | Every cited key has an entry; missing keys reported; better formatting; native Word citations investigated | Done. `.bib` support, `SEQ`/`REF` numbering, [ADR 0003](decisions/0003-word-citations.md) |
| Completion condition | Insert content in Word, update fields, numbers and references stay correct | Done in Word 16.0.20625 |
| Every anchor and `REF` resolves | — | Done: the checker on every output, `test_every_link_and_field_points_to_a_bookmark` over 8 corpora, and `Bookmarks.Exists` in Word |

## Test suite

236 tests (Phase 4: 214):

| File | Tests | File | Tests |
|---|---|---|---|
| test_backend | 9 | test_integration | 4 |
| test_bib | 8 | test_ir | 26 |
| test_bookmarks | 7 | test_lists | 11 |
| test_caps | 6 | test_media | 7 |
| test_check | 13 | test_model | 5 |
| test_cli | 21 | test_normalize | 4 |
| test_corpus | 9 | test_output | 23 |
| test_fields | 13 | test_paragraphs | 21 |
| test_frontend | 4 | test_source | 14 |
| test_full | 8 | test_tables | 11 |
| test_hyperlinks | 8 | test_tree | 4 |

| Environment | Result |
|---|---|
| Linux (Python 3.10.12, Pandoc 3.9, `TEJTEX_NO_SKIP=1`) | 236 passed |
| Windows 11 laptop (Python 3.14.0, Pandoc 3.9) | 235 passed, 1 skipped (symbolic links need administrator rights on this machine; the test runs in CI) |

Existing tests changed where the representation changed: heading numbers are no longer text (tests read them through `labels`/`shown`, which replay Word's numbering, now including style-linked lists); bookmarks wrap numbers; references to numbered targets are fields, not hyperlinks; the bibliography has its heading.

## Ground truth

`tests/data/fields` was compiled with `pdflatex` and `bibtex` (TeX Live, `plain` style). `test_fields_corpus_follows_latex` expects the PDF's text paragraph by paragraph. Two differences are intended: TejTeX adds the entry's URL as a link, and it writes the `\TeX` logo as `TeX`.

The same comparison showed that Pandoc's theorem numbers are not LaTeX's: Pandoc numbered `\newtheorem{definition}{Definition}[section]` as 1.1 (LaTeX 1.1.1), `\newtheorem{remark}{Remark}` as 1.1 and 2.1 (LaTeX 1 and 2), and the starred `note` as 1.1 (LaTeX: no number). Theorem numbers are therefore counted by TejTeX from the `\newtheorem` lines.

## Field replay

`tests/helpers.py::update` replays Word's rules for `SEQ` (with `\s` restarts), `STYLEREF` and `REF` (`\w` and bookmark text). Tests check that:

- updating an unedited document changes nothing (corpora `fields`, `refs`, `links`, `full`);
- after inserting a chapter heading, a figure caption, an equation, a theorem and a remark into the `fields` corpus, all 17 references give the new numbers;
- after moving a figure, the two figure references swap.

## Microsoft Word 16.0.20625 (Windows 11)

`scripts/word_fields.ps1` on `fields.docx`, in a new hidden Word instance on a temporary copy (Kiran's own Word window was not touched):

| Check | Result |
|---|---|
| Opened without repair | yes |
| Update all fields on the unedited file | 0 errors, all 43 results unchanged (17 `REF`, 10 `STYLEREF`, 15 `SEQ`, 1 `HYPERLINK`) |
| Heading numbers before | 1 Start, 1.1 One, 1.2 Two, 2 End; Bibliography unnumbered |
| Inserted | a `heading 1` after the title; an equation in 1.1; a theorem before Theorem 1.1; a figure caption in chapter 1; a `heading 2` after the equation in 1.2 (the fields typed as Word's Insert Caption writes them) |
| Heading numbers after | 1 Inserted chapter, 2 Start, 2.1 One, 2.2 Two, 2.3 Inserted section, 3 End |
| New numbers | equation (2.1.1), Theorem 2.1, Figure 2.1 |
| One update was enough | yes, a second update changed nothing |
| `Error!` results | none |
| Every `REF` and hyperlink sub-address exists | yes |

References after the update:

| Bookmark | Before | After | | Bookmark | Before | After |
|---|---|---|---|---|---|---|
| `ch_end` (`\w`) | 2 | 3 | | `def_one` | 1.1.1 | 2.1.1 |
| `sec_one` (`\w`) | 1.1 | 2.1 | | `rem_one` | 1 | 1 |
| `sec_two` (`\w`) | 1.2 | 2.2 | | `eq_two` | 1.2.1 | 2.2.1 |
| `fig_one` | 1.1 | 2.2 | | `fig_two` | 2.1 | 3.1 |
| `tab_one` | 1.1 | 2.1 | | `thm_two` | 2.1 | 3.1 |
| `eq_one` | 1.1.1 | 2.1.2 | | `def_two` | 1.2.1 | 2.3.1 |
| `thm_one` | 1.1 | 2.2 | | `bib_knuth` | 2 | 2 |
| `lem_one` | 1.2 | 2.3 | | `bib_lamport` | 3 | 3 |

Every value is what LaTeX would print for the edited document: the global remark counter and the bibliography do not change, the definition restarts in the new section (2.3.1), and chapter-relative numbers follow the inserted chapter.

Found and fixed during the check: after an update, a `REF` to a theorem number came out bold, because `REF` copies the formatting of the bookmarked text. `REF` fields now have `\* CHARFORMAT`; the rerun found no bold reference.

## LibreOffice 26.2 (Linux)

`scripts/libreoffice_check.py` now also compares numbered headings, `SEQ`, `STYLEREF` and `REF` fields, and leaves field codes out of the word comparison. All 13 documents (12 corpora and the example) pass: every field and heading list is imported.

LibreOffice recomputes sequences on opening and ignores `SEQ`'s `\s` restart, so per-chapter numbers are right only in the first chapter (it shows Figure 2.2 where Word and LaTeX show 2.1). With Word's caption switch `STYLEREF 1 \s` LibreOffice also showed the heading's text instead of its number (`Figure Start.1`); TejTeX writes the documented `\w` switch, which both programs read as the number. This is listed in [limitations.md](limitations.md).

## Investigation: native Word citations

Word's sources (`b:Sources` in a Custom XML part, `CITATION` and `BIBLIOGRAPHY` fields in content controls) were compared with a static bibliography numbered by fields. TejTeX keeps the static bibliography, because Word's styles cannot reproduce BibTeX styles and rewrite the text on update. Details: [ADR 0003](decisions/0003-word-citations.md).

## CI

To be recorded after the push.

## Known unresolved issues

See [limitations.md](limitations.md): fields in LibreOffice, theorem schemes from packages, numbering within levels deeper than 3, unnumbered `heading 1` paragraphs restarting sequences in Word, one bibliography format for every style, and mathematics and footnotes (later phases).
