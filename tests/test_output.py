import io
import shutil
from pathlib import Path

import docx
import pytest

from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.cli import main
from tejtex.config import Config
from tejtex.errors import Exit
from tejtex.ir.nodes import Citation, CrossReference, Image, Math, Placeholder, TextRun, walk

DATA = Path(__file__).parent / "data"
CORPUS = ["sec63", "unknown", "includes", "images", "refs", "format", "lists"]


def render(name):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config())
    d = ir.build(ast, rep, s, Config())
    return d, backend.render(d)


@pytest.mark.parametrize("name", CORPUS)
def test_corpus_output_is_a_valid_package(real_pandoc, name):
    d, data = render(name)
    assert check(data) == []


@pytest.mark.parametrize("name", CORPUS)
def test_no_content_is_dropped(real_pandoc, name):
    d, data = render(name)
    out = "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    for n in walk(d):
        if isinstance(n, TextRun):
            s = n.text.strip()
        elif isinstance(n, (Citation, CrossReference, Placeholder)):
            s = n.text
        elif isinstance(n, Math):
            s = n.tex.strip()
        elif isinstance(n, Image):
            s = f"[image: {n.path}]"
        else:
            continue
        assert s in out, s


def test_cli_output_is_identical_between_runs(real_pandoc, tmp_path):
    shutil.copytree(DATA / "refs", tmp_path / "refs")
    src = tmp_path / "refs" / "main.tex"
    assert main(["compile", str(src), "-o", str(tmp_path / "a.docx"), "-q"]) == Exit.OK
    assert main(["compile", str(src), "-o", str(tmp_path / "b.docx"), "-q"]) == Exit.OK
    assert (tmp_path / "a.docx").read_bytes() == (tmp_path / "b.docx").read_bytes()
