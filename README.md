# TejTeX

TejTeX compiles LaTeX source into native, structurally editable Microsoft Word (DOCX) documents. It maps the semantic structure of the source (headings, paragraphs, lists, tables, figures, captions, references and styles) onto Word's own document structures and leaves layout and pagination to Word.

**Status: Phase 1 (engineering foundation).** The pipeline runs end to end (Pandoc frontend → IR → DOCX backend), but every block is written as a plain paragraph for now. Headings, lists, tables and images become native Word structures in Phases 2–4.

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
| `-v, --verbose` | Show debug messages, including Pandoc's log |
| `-q, --quiet` | Show errors only |

On Windows with Smart App Control turned on, the `tejtex.exe` launcher that pip creates can be blocked ("An Application Control policy has blocked this file"). Use `python -m tejtex` instead; it takes the same options and returns the same exit codes.

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
| `frontend.py` | Pandoc invocation (LaTeX → JSON AST), version check, `--sandbox`, timeout |
| `ir.py` | Semantic IR; must not import python-docx or lxml |
| `backend.py` | DOCX writer |
| `config.py` | Settings |
| `errors.py` | Exit codes and the error type |

## License

MIT
