# TejTeX

TejTeX compiles LaTeX source into native, structurally editable Microsoft Word (DOCX) documents. It maps the semantic structure of the source (headings, paragraphs, lists, tables, figures, captions, references and styles) onto Word's own document structures and leaves layout and pagination to Word.

**Status: Phase 2 (frontend).** The pipeline runs end to end (Pandoc frontend → IR → DOCX backend). The frontend resolves included files, runs Pandoc safely, classifies every LaTeX construct and reports what it cannot convert. The backend still writes every block as a plain paragraph; headings, lists, tables and images become native Word structures in Phases 3–4.

## Requirements

- Python 3.10 or newer
- [Pandoc 3.9](https://github.com/jgm/pandoc/releases/tag/3.9), exactly. TejTeX checks the version before every run because Pandoc's AST format is versioned.

## Install

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

```
tejtex --version
tejtex compile main.tex                      # writes main.docx next to main.tex
tejtex compile main.tex -o out/paper.docx
tejtex compile main.tex --pandoc C:\tools\pandoc-3.9\pandoc.exe --timeout 120 -v
```

| Option | Meaning |
|---|---|
| `-o, --output` | Output `.docx` file (default: next to the input) |
| `--pandoc` | Pandoc executable (default: `pandoc` on PATH) |
| `--timeout` | Pandoc time limit in seconds (default: 60; must be positive) |
| `--max-memory` | Pandoc memory limit in MB (default: 2048; must be positive) |
| `--root` | Project root (default: folder of the input) |
| `-v, --verbose` | Show debug messages, including Pandoc's log |
| `-q, --quiet` | Show errors only |

On Windows with Smart App Control turned on, the `tejtex.exe` launcher that pip creates can be blocked ("An Application Control policy has blocked this file"). Use `python -m tejtex` instead; it takes the same options and returns the same exit codes.

## Project root and included files

TejTeX resolves `\input` and `\include` itself, relative to the main file's folder as LaTeX does, and only inside the project root. Absolute paths, URLs, paths that leave the root (also through symbolic links), missing files and circular includes are reported and replaced by a visible placeholder. Images follow the same rules. Pandoc runs with `--sandbox`, so it cannot read files or fetch URLs on its own.

Limits: 16 levels of nested includes, 256 files and 20 million characters of source. Going over a limit stops compilation with exit code 6.

## Diagnostics

Every construct Pandoc skips is reported with its file, line and column and one of four support categories:

| Category | Meaning | Example |
|---|---|---|
| supported | converted | `\section`, lists, `tabular`, `\footnote`, `\cite` |
| partial | converted with some information lost | `enumerate` with an enumitem label, unknown environments, `thebibliography` |
| unsupported | not converted; layout commands are ignored, content is replaced by a visible placeholder | `\vspace`, `\centering`, unknown commands, `geometry` |
| render | needs rendering as an image (later phase); a visible placeholder for now | TikZ |

The choice of Pandoc reader mode behind this is recorded in [docs/decisions/0001-pandoc-reader-mode.md](docs/decisions/0001-pandoc-reader-mode.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Internal error (a bug in TejTeX) |
| 2 | Usage error (bad command-line arguments) |
| 3 | File error (input missing or not `.tex`; output not `.docx`, folder missing or not writable) |
| 4 | Toolchain error (Pandoc missing or not version 3.9) |
| 5 | Conversion error (Pandoc could not read the input) |
| 6 | Limit exceeded (for example the Pandoc time limit) |

No output file is written when the exit code is not 0.

## Development

```
pytest
```

Tests that need the real Pandoc 3.9 are skipped when it is not on PATH. All other tests use a fake Pandoc. Set `TEJTEX_NO_SKIP=1` to turn every skip into a failure. CI (GitHub Actions, Linux and Windows, Python 3.10 and 3.12) installs Pandoc 3.9 and runs everything with `TEJTEX_NO_SKIP=1`.

| Module | Role |
|---|---|
| `cli.py` | Command line, logging |
| `compiler.py` | Pipeline: frontend → IR → backend |
| `source.py` | Reads the main file, resolves `\input`/`\include` inside the project root, maps positions back to files |
| `frontend.py` | Runs Pandoc (version check, `--sandbox`, timeout, memory cap, JSON log), marks skipped content |
| `caps.py` | Capability registry: support category for each skipped construct |
| `normalize.py` | Placeholders, image checks, equation labels, Pandoc clean-ups; element classification |
| `tree.py` | Pandoc AST traversal and validation |
| `diag.py` | Diagnostics and the report |
| `ir.py` | Semantic IR; must not import python-docx or lxml |
| `backend.py` | DOCX writer |
| `config.py` | Settings |
| `errors.py` | Exit codes and the error type |

## License

MIT
