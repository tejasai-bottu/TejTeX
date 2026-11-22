import json
import shutil
from pathlib import Path

import docx

from tejtex import caps, frontend, normalize, tree
from tejtex.cli import main
from tejtex.config import Config
from tejtex.diag import CATS
from tejtex.errors import Exit

DATA = Path(__file__).parent / "data"


def read(name, **kw):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config(**kw))
    return ast, rep


def find(ast, pred):
    return [lst[i] for lst, i in tree.each(ast["blocks"]) if pred(lst[i])]


def classes(n):
    return n["c"][0][1] if n.get("t") in ("Div", "Span") else []


def attr(n, k):
    return dict(n["c"][0][2]).get(k)


def test_sec63_diagnostics(real_pandoc):
    ast, rep = read("sec63")
    got = sorted((d.element, d.category) for d in rep.diags)
    assert got == sorted([
        ("package geometry", "unsupported"),
        ("[label=(\\roman*)]", "partial"),
        ("\\vspace", "unsupported"),
        ("\\centering", "unsupported"),
        ("\\centering", "unsupported"),
        ("tikzpicture", "render"),
        ("\\bibitem", "partial"),
        ("thebibliography", "partial"),
    ])
    locs = {d.element: d.loc for d in rep.diags}
    assert locs["tikzpicture"] == "main.tex:53:1"
    assert locs["[label=(\\roman*)]"] == "main.tex:20:18"


def test_sec63_every_skip_has_a_diagnostic(real_pandoc):
    text = (DATA / "sec63" / "main.tex").read_text(encoding="utf-8")
    ast, msgs = frontend.run(text, Config())
    ast, rep = read("sec63")
    elements = {d.element for d in rep.diags}
    skips = [m for m in msgs if m["type"] == "SkippedContent"]
    assert len(skips) >= 8
    for m in skips:
        k = caps.skip(m["contents"])
        assert k is None or k[0] in elements


def test_sec63_every_element_has_a_category(real_pandoc):
    ast, rep = read("sec63")
    assert all(e["category"] in CATS for e in rep.elements.values())
    partial = {d.element for d in rep.diags if d.category == "partial"}
    for lst, i in tree.each(ast["blocks"]):
        name, cat = normalize.name(lst[i], partial)
        assert rep.elements[name]["category"] == cat
    assert rep.elements["tikzpicture"]["category"] == "render"
    assert rep.elements["Div.thebibliography"]["category"] == "partial"
    assert rep.elements["Header"] == {"category": "supported", "count": 3}


def test_sec63_normalized_tree(real_pandoc):
    ast, rep = read("sec63")
    assert tree.check(ast) == []
    blocks = ast["blocks"]
    kinds = [(b["t"], classes(b)) for b in blocks]
    i = kinds.index(("Div", ["theorem"]))
    assert kinds[i + 1] == ("Div", ["tejtex-placeholder"])
    assert attr(blocks[i + 1], "element") == "tikzpicture"
    assert kinds[i + 2] == ("Div", ["thebibliography"])
    entry = blocks[i + 2]["c"][1][0]["c"]
    assert classes(entry[0]) == ["tejtex-anchor"]
    assert attr(entry[0], "key") == "knuth84"
    assert entry[1:3] == [{"t": "Space"}, {"t": "Str", "c": "D."}]
    eq = find(ast, lambda n: "tejtex-equation" in classes(n))
    assert eq[0]["c"][0] == ["eq:a", ["tejtex-equation"], [["labels", "eq:a"]]]
    refs = find(ast, lambda n: n.get("t") == "Link")
    assert sorted(attr(r, "reference") for r in refs) == ["eq:a", "fig:a", "sec:method", "tab:a"]
    cites = find(ast, lambda n: n.get("t") == "Cite")
    assert cites[0]["c"][0][0]["citationId"] == "knuth84"
    assert cites[0]["c"][1] == []
    imgs = find(ast, lambda n: n.get("t") == "Image")
    assert imgs[0]["c"][2][0] == "figure.png"


def test_unknown_constructs(real_pandoc):
    ast, rep = read("unknown")
    d = {x.element: x for x in rep.diags}
    assert d["\\unknowncmd"].loc == "main.tex:6:8"
    assert d["\\foo"].category == "unsupported"
    assert d["\\tikz"].category == "render"
    assert "\\draw" not in d
    assert d["unknownenv"].category == "partial"
    assert attr(ast["blocks"][0], "element") == "\\tableofcontents"
    text = json.dumps(ast)
    assert "kept arg" not in text
    assert "(0,0)" not in text
    assert '"Inside"' in text
    spans = find(ast, lambda n: n.get("t") == "Span" and "tejtex-placeholder" in classes(n))
    assert sorted(attr(x, "element") for x in spans) == ["\\tikz", "\\unknowncmd"]
    assert rep.elements["Div.unknownenv"]["category"] == "partial"


def test_includes(real_pandoc):
    ast, rep = read("includes")
    text = json.dumps(ast)
    for w in ['"One"', '"Two"', '"Loop"', '"End."']:
        assert w in text
    assert "SECRET" not in text
    d = {x.element: x for x in rep.diags}
    assert d["\\vspace"].loc == "chapters/one.tex:3:1"
    found = find(ast, lambda n: "tejtex-placeholder" in classes(n))
    assert sorted(attr(p, "element") for p in found) == sorted([
        "\\input{../outside}",
        "\\input{http://example.com/x}",
        "\\input{chapters/missing}",
        "\\input{chapters/loop}",
    ])


def test_images(real_pandoc):
    ast, rep = read("images")
    got = sorted((x.level, x.element) for x in rep.diags)
    assert got == [
        ("error", "\\includegraphics{../outside.png}"),
        ("error", "\\includegraphics{http://example.com/a.png}"),
        ("warning", "\\includegraphics{figs/missing.png}"),
    ]
    imgs = [n["c"][2][0] for n in find(ast, lambda n: n.get("t") == "Image")]
    assert sorted(imgs) == ["figs/missing.png", "figs/ok.png"]


def test_root_option(real_pandoc, tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "intro.tex").write_text("SHAREDINTRO", encoding="utf-8")
    src = tmp_path / "paper" / "main.tex"
    src.write_text("\\begin{document}\n\\input{shared/intro}\n\\end{document}\n", encoding="utf-8")
    ast, rep, _ = frontend.read(src, Config())
    assert "SHAREDINTRO" not in json.dumps(ast)
    ast, rep, _ = frontend.read(src, Config(root=str(tmp_path)))
    assert "SHAREDINTRO" in json.dumps(ast)
    assert rep.diags == []


def test_sec63_compiles_with_placeholders(real_pandoc, tmp_path):
    shutil.copytree(DATA / "sec63", tmp_path / "sec63")
    src = tmp_path / "sec63" / "main.tex"
    assert main(["compile", str(src), "-q"]) == Exit.OK
    text = "\n".join(p.text for p in docx.Document(str(src.with_suffix(".docx"))).paragraphs)
    assert "[TejTeX: tikzpicture needs rendering]" in text
    assert "Every test passes." in text
