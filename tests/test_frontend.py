import json

import pytest

from tejtex import frontend
from tejtex.config import Config
from tejtex.errors import Exit, TejtexError


def test_parse_version():
    assert frontend.parse_version("pandoc 3.9\nFeatures: +server\n") == "3.9"
    assert frontend.parse_version("pandoc.exe 3.9\n") == "3.9"
    assert frontend.parse_version("pandoc.exe 3.9\r\nFeatures\r\n") == "3.9"
    assert frontend.parse_version("") is None
    assert frontend.parse_version("something else 1.0") is None


def test_read(real_pandoc, tmp_path):
    f = tmp_path / "a.tex"
    f.write_text("\\section{Intro}\nHello \\textbf{world}.\n", encoding="utf-8")
    ast, rep = frontend.read(f, Config())
    assert rep.diags == []
    assert ast["pandoc-api-version"][:2] == [1, 23]
    assert ast["blocks"][0]["t"] == "Header"


def test_pandoc_runs_sandboxed(real_pandoc, tmp_path):
    secret = tmp_path / "secret.tex"
    secret.write_text("TOPSECRET")
    ast, msgs = frontend.run("Start \\input{" + secret.as_posix() + "} end.\n", Config())
    assert "TOPSECRET" not in json.dumps(ast)


def test_memory_cap(real_pandoc):
    text = "\n\n".join(f"Paragraph {i} with some words here." for i in range(20000))
    with pytest.raises(TejtexError) as e:
        frontend.run(text, Config(memory=64))
    assert e.value.code == Exit.LIMIT
