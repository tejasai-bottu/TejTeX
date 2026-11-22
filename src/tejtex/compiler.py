from pathlib import Path

from . import backend, frontend, ir
from .errors import Exit, TejtexError


def compile_file(src, out, cfg):
    src = Path(src)
    out = Path(out) if out else src.with_suffix(".docx")
    if not src.is_file():
        raise TejtexError(f"input file not found: {src}", Exit.FILE)
    if src.suffix.lower() != ".tex":
        raise TejtexError(f"input must be a .tex file: {src}", Exit.FILE)
    if out.suffix.lower() != ".docx":
        raise TejtexError(f"output must be a .docx file: {out}", Exit.FILE)
    if not out.parent.is_dir():
        raise TejtexError(f"output folder not found: {out.parent}", Exit.FILE)
    ast = frontend.read(src, cfg)
    doc = ir.build(ast)
    try:
        backend.write(doc, out)
    except OSError as e:
        raise TejtexError(f"cannot write {out}: {e.strerror or e}", Exit.FILE)
    return out
