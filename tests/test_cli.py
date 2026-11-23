import json
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import shown
from tejtex import __version__
from tejtex.cli import main
from tejtex.errors import Exit

AST = {
    "pandoc-api-version": [1, 23, 1, 1],
    "meta": {},
    "blocks": [
        {"t": "Header", "c": [1, ["intro", [], []], [{"t": "Str", "c": "Intro"}]]},
        {"t": "Para", "c": [{"t": "Str", "c": "Hello"}, {"t": "Space"}, {"t": "Str", "c": "world."}]},
    ],
}


def texts(path):
    return shown(Path(path).read_bytes())


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert f"tejtex {__version__}" in capsys.readouterr().out


def test_no_command():
    assert main([]) == Exit.USAGE


def test_bad_timeout():
    with pytest.raises(SystemExit) as e:
        main(["compile", "a.tex", "--timeout", "0"])
    assert e.value.code == Exit.USAGE


def test_missing_input(tmp_path):
    assert main(["compile", str(tmp_path / "nope.tex")]) == Exit.FILE


def test_not_tex(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    assert main(["compile", str(f)]) == Exit.FILE


def test_output_not_docx(tex, fake):
    assert main(["compile", str(tex), "-o", str(tex), "--pandoc", fake]) == Exit.FILE
    assert tex.read_text().startswith("\\section")


def test_output_folder_missing(tex, fake):
    out = tex.parent / "no" / "a.docx"
    assert main(["compile", str(tex), "-o", str(out), "--pandoc", fake]) == Exit.FILE


def test_pandoc_missing(tex, tmp_path):
    assert main(["compile", str(tex), "--pandoc", str(tmp_path / "nopandoc")]) == Exit.TOOLCHAIN


def test_pandoc_wrong_version(tex, fake, monkeypatch):
    monkeypatch.setenv("FAKE_VERSION", "2.9.2.1")
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.TOOLCHAIN


def test_pandoc_fails(tex, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "fail")
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.CONVERT
    assert not tex.with_suffix(".docx").exists()


def test_pandoc_junk(tex, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "junk")
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.CONVERT


def test_pandoc_timeout(tex, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "slow")
    assert main(["compile", str(tex), "--pandoc", fake, "--timeout", "1"]) == Exit.LIMIT
    assert not tex.with_suffix(".docx").exists()


def test_internal_error(tex, fake, monkeypatch):
    def boom(ast):
        raise RuntimeError("bug")

    monkeypatch.setattr("tejtex.compiler.ir.build", boom)
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.INTERNAL


def test_compile_ok(tex, fake, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_AST", json.dumps(AST))
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.OK
    assert texts(tex.with_suffix(".docx")) == ["1\tIntro", "Hello world."]
    assert "wrote" in capsys.readouterr().err


def test_compile_output_option(tex, fake, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_AST", json.dumps(AST))
    out = tmp_path / "out.docx"
    assert main(["compile", str(tex), "-o", str(out), "--pandoc", fake, "-q"]) == Exit.OK
    assert texts(out) == ["1\tIntro", "Hello world."]


def test_module_run(tmp_path):
    r = subprocess.run([sys.executable, "-m", "tejtex", "compile", str(tmp_path / "x.tex")], capture_output=True, text=True)
    assert r.returncode == Exit.FILE
    assert "input file not found" in r.stderr


def test_console_script(tejtex_exe):
    r = subprocess.run([tejtex_exe, "--version"], capture_output=True, text=True)
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_bad_max_memory():
    with pytest.raises(SystemExit) as e:
        main(["compile", "a.tex", "--max-memory", "0"])
    assert e.value.code == Exit.USAGE


def test_pandoc_out_of_memory(tex, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "oom")
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.LIMIT
    assert not tex.with_suffix(".docx").exists()


def test_root_must_contain_input(tex, fake, tmp_path):
    other = tmp_path / "other"
    assert main(["compile", str(tex), "--pandoc", fake, "--root", str(other)]) == Exit.FILE
    other.mkdir()
    assert main(["compile", str(tex), "--pandoc", fake, "--root", str(other)]) == Exit.FILE
    assert main(["compile", str(tex), "--pandoc", fake, "--root", str(tmp_path)]) == Exit.OK


def test_diagnostics_are_printed(tmp_path, fake, monkeypatch, capsys):
    tex = tmp_path / "doc.tex"
    tex.write_text("Hi.\n\\vspace{1cm}\nBye.\n", encoding="utf-8")
    msgs = [{"type": "SkippedContent", "verbosity": "INFO", "contents": "\\vspace{1cm}", "source": "", "line": 2, "column": 13}]
    monkeypatch.setenv("FAKE_LOG", json.dumps(msgs))
    monkeypatch.setenv("FAKE_AST", json.dumps(AST))
    assert main(["compile", str(tex), "--pandoc", fake]) == Exit.OK
    err = capsys.readouterr().err
    assert "doc.tex:2:1: \\vspace: layout command ignored" in err
    assert "1 diagnostics: 1 unsupported" in err
