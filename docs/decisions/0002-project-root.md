# 0002 — Project root and path resolution

Status: accepted (Phase 3, 22 November 2026)

## Rule

1. The project root is the folder that contains the main `.tex` file. `--root DIR` sets it explicitly (Section 10.5).
2. Every `\input`, `\include` and `\includegraphics` path is resolved relative to the project root.
3. The same root is used inside included files, at every nesting depth. Paths are never resolved relative to the including file.
4. A path that leaves the root is rejected: `..` escapes, absolute paths, drive letters, URLs and symbolic links whose real path is outside the root.
5. Rejected, missing and circular includes produce a diagnostic with the file, line and column of the command, and a visible placeholder in the output.

## Why

With the default root this is what LaTeX does: TeX resolves relative paths against the folder it runs in, which is the main file's folder, not against the file that contains the `\input`. One rule for every file keeps the behaviour predictable and matches Section 10.5 of the problem statement word for word.

Phase 2 briefly resolved paths against the main file's folder while confining them to the root. That only differed when `--root` was given, and it made two folders matter instead of one. It was replaced by this rule.

## Tests

`tests/test_source.py`: `test_nested_includes_resolve_against_the_root` (three levels of includes, a path relative to the including file is not found, an escape from a nested file is rejected, locations point into the nested file) and `test_explicit_root_is_used_for_every_path`. `tests/test_corpus.py::test_root_option` runs the same rule through Pandoc.
