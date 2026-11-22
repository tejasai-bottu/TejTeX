import shutil
import subprocess
from pathlib import Path

import docx

from tejtex.cli import main
from tejtex.errors import Exit

EXAMPLE = Path(__file__).parent.parent / "examples" / "main.tex"


def texts(path):
    return [p.text for p in docx.Document(str(path)).paragraphs]


def test_example_compiles(real_pandoc, tmp_path):
    src = tmp_path / "main.tex"
    shutil.copy(EXAMPLE, src)
    assert main(["compile", str(src)]) == Exit.OK
    t = texts(src.with_suffix(".docx"))
    assert t[0] == "Introduction"
    for s in ["Goals", "Native headings", "Second step", "Data", "alpha", "1"]:
        assert s in t


def test_console_compile_main_tex(real_pandoc, tejtex_exe, tmp_path):
    shutil.copy(EXAMPLE, tmp_path / "main.tex")
    r = subprocess.run([tejtex_exe, "compile", "main.tex"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert texts(tmp_path / "main.docx")[0] == "Introduction"


def test_paths_with_spaces_and_unicode(real_pandoc, tmp_path):
    d = tmp_path / "my files" / "café"
    d.mkdir(parents=True)
    src = d / "main.tex"
    shutil.copy(EXAMPLE, src)
    out = tmp_path / "out put" / "résumé.docx"
    out.parent.mkdir()
    assert main(["compile", str(src), "-o", str(out)]) == Exit.OK
    assert texts(out)[0] == "Introduction"


def test_relative_paths(real_pandoc, tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "build").mkdir()
    shutil.copy(EXAMPLE, tmp_path / "src" / "main.tex")
    monkeypatch.chdir(tmp_path)
    assert main(["compile", "src/main.tex", "-o", "build/main.docx"]) == Exit.OK
    assert (tmp_path / "build" / "main.docx").exists()
