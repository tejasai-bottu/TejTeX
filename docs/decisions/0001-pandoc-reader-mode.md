# 0001 — Pandoc reader mode for the frontend

Status: accepted (Phase 2, 22 November 2026)

## Question

Section 7.2 of the problem statement leaves open whether the frontend runs Pandoc's LaTeX reader in default mode, in `raw_tex` mode, or both.

## Experiment

The Section 6.3 test document (plus an unknown command `\unknowncmd{kept arg}` and an unknown environment) was read with Pandoc 3.9 (`pandoc-api-version` 1.23.1.1) in both modes, with `--sandbox` and `--log` (JSON log).

| Construct | Default mode | `raw_tex` mode |
|---|---|---|
| `\ref`, `\eqref` | `Link` with `reference-type` / `reference` attributes | `RawInline` — label link lost |
| `\label` in a theorem | `Div` id `thm:a` | `RawInline`, `Div` id lost |
| `\label` in an equation | kept inside the `Math` text | kept inside the `Math` text |
| `\cite` | `Cite` node with `citationId` | same |
| Unknown environment | `Div` with the environment name as class, content parsed | one `RawBlock`, content not parsed |
| `thebibliography` | `Div`, entries as text, stray width argument `9`, `\bibitem` keys skipped | one `RawBlock`, nothing parsed |
| TikZ picture | dropped | `RawBlock` at the right position |
| `\vspace`, `\centering` | dropped | `RawBlock` / position kept |
| `\unknowncmd{kept arg}` | dropped with its argument | `RawInline` at the right position |
| enumitem `[label=(\roman*)]` | dropped | dropped |
| `geometry` options | silently ignored | silently ignored |

The JSON log (`--log`) reports every skipped construct in default mode with its full text, line and column; in `raw_tex` mode only the enumitem option is reported. `--log` works together with `--sandbox` and with input on stdin.

## Decision

Default mode, with the JSON log as a second output, and a marker pass for content that needs a position:

1. TejTeX resolves `\input`/`\include` itself and sends the combined source to Pandoc on stdin.
2. Pass 1 runs Pandoc in default mode and reads the JSON log.
3. Every skipped construct is classified by the Capability Registry and produces a diagnostic.
4. Skipped constructs that carry content or need an anchor (TikZ, unknown commands with arguments, `\bibitem`, `\tableofcontents`, …) are replaced in the source by a marker `\href{tejtex-<token>:<n>}{}`, which Pandoc keeps as a `Link` at the right position in every context (paragraph, heading, table cell, list item, figure).
5. Pass 2 runs Pandoc on the marked source. Pass 2 only runs when pass 1 found something to mark.
6. Normalization turns markers into placeholders (`Span`/`Div` with class `tejtex-placeholder`) or anchors (`tejtex-anchor`).

`raw_tex` mode is not used: it loses resolved references, labels on theorems and the structure of unknown environments and bibliographies, which matter more than the positions it keeps.

## Additions

Stage 4.3 (lists):

- Pandoc drops the optional argument of `\item` in `itemize` and `enumerate` without reporting it. TejTeX finds `\item[...]` in those environments (not in `description`, not in comments) and rewrites it to `\item \href{tejtex-<token>:<n>}{...}`. The label reaches the model as a `Span` with class `tejtex-item`.
- enumitem options on `enumerate`, which Pandoc skips, are translated when they map onto Pandoc's own markers: `label=` with one counter (`\arabic*`, `\alph*`, `\Alph*`, `\roman*`, `\Roman*`) followed by `.` or `)` or inside `(…)`, and `start=`. Spacing options are ignored with an info diagnostic. Anything else stays a `partial` warning; `resume` is reported as not applied.

## Consequences

- Pandoc runs twice when the document contains markable constructs.
- Pandoc reports the position after the skipped command (or after `\begin{...}` for environments); TejTeX locates the exact span by searching for the reported text backwards from that position.
- Layout-only commands are reported and ignored; Word owns layout.
- `geometry` is detected from Pandoc's attempt to load `geometry.sty`, not from its options.
