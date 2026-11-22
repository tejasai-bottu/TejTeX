import json

from tejtex import frontend
from tejtex.config import Config


def test_parse_version():
    assert frontend.parse_version("pandoc 3.9\nFeatures: +server\n") == "3.9"
    assert frontend.parse_version("pandoc.exe 3.9\n") == "3.9"
    assert frontend.parse_version("pandoc.exe 3.9\r\nFeatures\r\n") == "3.9"
    assert frontend.parse_version("") is None
    assert frontend.parse_version("something else 1.0") is None


def test_read(real_pandoc, tmp_path):
    f = tmp_path / "a.tex"
    f.write_text("\\section{Intro}\nHello \\textbf{world}.\n", encoding="utf-8")
    ast = frontend.read(f, Config())
    assert ast["pandoc-api-version"][:2] == [1, 23]
    assert ast["blocks"][0]["t"] == "Header"


def test_sandbox_blocks_outside_file(real_pandoc, tmp_path):
    secret = tmp_path / "secret.tex"
    secret.write_text("TOPSECRET")
    f = tmp_path / "a.tex"
    f.write_text("Start \\input{" + secret.as_posix() + "} end.\n")
    ast = frontend.read(f, Config())
    assert "TOPSECRET" not in json.dumps(ast)
