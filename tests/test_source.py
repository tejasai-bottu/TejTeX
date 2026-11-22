import os
from pathlib import Path

import pytest

from tejtex import source
from tejtex.config import Config
from tejtex.diag import Report
from tejtex.errors import Exit, TejtexError

DATA = Path(__file__).parent / "data"


def load(main, root=None, **kw):
    rep = Report()
    root = Path(root or Path(main).parent).resolve()
    return source.load(Path(main), root, Config(**kw), rep), rep


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def line_of(path, s):
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if s in line:
            return i


def test_includes_corpus():
    main = DATA / "includes" / "main.tex"
    s, rep = load(main)
    assert "One text." in s.text
    assert "Two text." in s.text
    assert s.text.count("Loop text.") == 1
    assert "OUTSIDE SECRET" not in s.text
    assert "\\input{chapters/verbatim}" in s.text
    d = {x.element: x for x in rep.diags}
    assert d["\\input{../outside}"].level == "error"
    assert d["\\input{../outside}"].loc == f"main.tex:{line_of(main, '../outside')}:1"
    assert d["\\input{http://example.com/x}"].level == "error"
    assert d["\\input{chapters/missing}"].level == "warning"
    assert d["\\input{chapters/loop}"].message.endswith("circular include")
    assert d["\\input{chapters/loop}"].loc == "chapters/loop.tex:2:1"
    assert not any("commented" in x.element or "verbatim" in x.element for x in rep.diags)
    assert len(s.marks) == 4


def test_where_maps_back_to_files():
    s, rep = load(DATA / "includes" / "main.tex")
    assert s.where(s.text.index("One more.")) == "chapters/one.tex:4:1"
    assert s.where(s.text.index("Two text.")) == "chapters/two.tex:2:1"
    assert s.where(s.text.index("End.")).startswith("main.tex:")
    assert s.text[s.body:].startswith("\\begin{document}")


def test_tex_extension_rules(tmp_path):
    write(tmp_path / "a.tex", "AAA")
    write(tmp_path / "b.txt", "BBB")
    main = write(tmp_path / "main.tex", "\\input{a} \\input{a.tex} \\input{b.txt}")
    s, rep = load(main)
    assert s.text.count("AAA") == 2
    assert "BBB" in s.text
    assert rep.diags == []


def test_verb_and_escaped_percent(tmp_path):
    write(tmp_path / "a.tex", "AAA")
    main = write(tmp_path / "main.tex", "\\verb|\\input{a}| 50\\% \\input{a}\n% \\input{a}\n")
    s, rep = load(main)
    assert s.text.count("AAA") == 1


def test_absolute_path_rejected(tmp_path):
    secret = write(tmp_path / "outside" / "secret.tex", "SECRET")
    main = write(tmp_path / "proj" / "main.tex", "\\input{%s}" % secret.as_posix())
    s, rep = load(main)
    assert "SECRET" not in s.text
    assert rep.diags[0].level == "error"


def test_symlink_out_of_root_rejected(tmp_path, skipper):
    secret = write(tmp_path / "outside" / "secret.tex", "SECRET")
    proj = tmp_path / "proj"
    proj.mkdir()
    try:
        os.symlink(secret, proj / "link.tex")
    except OSError:
        skipper("cannot create symlinks here")
    main = write(proj / "main.tex", "\\input{link}")
    s, rep = load(main)
    assert "SECRET" not in s.text
    assert rep.diags[0].message == "not included: path leaves the project folder"


def test_check():
    root = Path.cwd().resolve()
    assert source.check(root, root, "a/b.tex")[1] is None
    assert source.check(root, root, "../x.tex")[1] == "path leaves the project folder"
    assert source.check(root, root, "a/../../x.tex")[1] == "path leaves the project folder"
    assert source.check(root, root, "/etc/passwd")[1] == "absolute paths are not allowed"
    assert source.check(root, root, "C:/Windows/win.ini")[1] == "URLs and drive paths are not allowed"
    assert source.check(root, root, "https://example.com/a.tex")[1] == "URLs and drive paths are not allowed"
    assert source.check(root / "sub", root, "../x.tex")[1] is None


def test_paths_are_relative_to_the_main_file(tmp_path):
    write(tmp_path / "shared" / "macros.tex", "SHARED")
    write(tmp_path / "paper" / "intro.tex", "INTRO")
    main = write(tmp_path / "paper" / "main.tex", "\\input{intro} \\input{../shared/macros}")
    s, rep = load(main)
    assert "INTRO" in s.text
    assert "SHARED" not in s.text
    s, rep = load(main, tmp_path)
    assert "INTRO" in s.text
    assert "SHARED" in s.text
    assert rep.diags == []


def test_main_outside_root(tmp_path):
    main = write(tmp_path / "a" / "main.tex", "x")
    with pytest.raises(TejtexError) as e:
        load(main, tmp_path / "b")
    assert e.value.code == Exit.FILE
    (tmp_path / "b").mkdir()
    with pytest.raises(TejtexError) as e:
        load(main, tmp_path / "b")
    assert e.value.code == Exit.FILE


def test_main_not_utf8(tmp_path):
    main = tmp_path / "main.tex"
    main.write_bytes(b"caf\xe9")
    with pytest.raises(TejtexError) as e:
        load(main)
    assert e.value.code == Exit.FILE


def test_include_not_utf8(tmp_path):
    (tmp_path / "a.tex").write_bytes(b"caf\xe9")
    main = write(tmp_path / "main.tex", "\\input{a}")
    s, rep = load(main)
    assert rep.diags[0].message == "not included: file cannot be read as UTF-8 text"


def test_depth_limit(tmp_path):
    write(tmp_path / "a.tex", "\\input{b}")
    write(tmp_path / "b.tex", "\\input{c}")
    write(tmp_path / "c.tex", "C")
    main = write(tmp_path / "main.tex", "\\input{a}")
    s, rep = load(main, depth=3)
    assert "C" in s.text
    with pytest.raises(TejtexError) as e:
        load(main, depth=2)
    assert e.value.code == Exit.LIMIT


def test_file_and_size_limits(tmp_path):
    write(tmp_path / "a.tex", "A" * 50)
    write(tmp_path / "b.tex", "B")
    main = write(tmp_path / "main.tex", "\\input{a}\\input{b}")
    with pytest.raises(TejtexError) as e:
        load(main, files=2)
    assert e.value.code == Exit.LIMIT
    with pytest.raises(TejtexError) as e:
        load(main, size=40)
    assert e.value.code == Exit.LIMIT
