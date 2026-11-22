from pathlib import Path

from tejtex import normalize, source, tree
from tejtex.config import Config
from tejtex.diag import Report

A = ["", [], []]


def s(x):
    return {"t": "Str", "c": x}


def setup(tmp_path, text="\\begin{document}\nx\n\\end{document}\n"):
    (tmp_path / "main.tex").write_text(text, encoding="utf-8")
    rep = Report()
    src = source.load(tmp_path / "main.tex", tmp_path.resolve(), Config(), rep)
    return src, rep


def link(src, info):
    n = src.mark(info)
    url = n[len("\\href{"):n.index("}")]
    return {"t": "Link", "c": [A, [], [url, ""]]}


def doc(*blocks):
    return {"pandoc-api-version": [1, 23, 1, 1], "meta": {}, "blocks": list(blocks)}


def test_markers_become_placeholders(tmp_path):
    src, rep = setup(tmp_path)
    tikz = {"element": "tikzpicture", "category": "render", "loc": "main.tex:2:1", "text": "[TejTeX: tikzpicture needs rendering]"}
    cmd = {"element": "\\foo", "category": "unsupported", "loc": "main.tex:3:5", "text": "[TejTeX: \\foo is not supported]"}
    bib = {"element": "\\bibitem", "category": "partial", "loc": "", "text": "", "anchor": True, "key": "k1"}
    ast = doc(
        {"t": "Para", "c": [link(src, tikz)]},
        {"t": "Para", "c": [s("a"), {"t": "Space"}, link(src, cmd), s("b")]},
        {"t": "Para", "c": [link(src, bib), s("entry")]},
    )
    normalize.run(ast, src, rep)
    b = ast["blocks"]
    assert b[0]["t"] == "Div"
    assert b[0]["c"][0][1] == ["tejtex-placeholder"]
    assert dict(b[0]["c"][0][2]) == {"category": "render", "element": "tikzpicture", "source": "main.tex:2:1"}
    span = b[1]["c"][2]
    assert span["t"] == "Span"
    assert span["c"][1][0] == s("[TejTeX:")
    anchor = b[2]["c"][0]
    assert anchor["c"][0][1] == ["tejtex-anchor"]
    assert dict(anchor["c"][0][2])["key"] == "k1"
    assert anchor["c"][1] == []
    assert tree.check(ast) == []
    assert rep.elements["tikzpicture"]["category"] == "render"
    assert rep.elements["\\foo"]["category"] == "unsupported"
    assert rep.elements["\\bibitem"]["category"] == "partial"


def test_images(tmp_path):
    src, rep = setup(tmp_path)
    (tmp_path / "ok.png").write_bytes(b"x")

    def img(p):
        return {"t": "Image", "c": [A, [], [p, ""]]}

    ast = doc({"t": "Para", "c": [img("ok.png"), img("ok"), img("missing.png"), img("../x.png"), img("http://e.com/a.png")]})
    normalize.run(ast, src, rep)
    c = ast["blocks"][0]["c"]
    assert [x["t"] for x in c] == ["Image", "Image", "Image", "Span", "Span"]
    levels = sorted((d.level, d.element) for d in rep.diags)
    assert levels == [
        ("error", "\\includegraphics{../x.png}"),
        ("error", "\\includegraphics{http://e.com/a.png}"),
        ("warning", "\\includegraphics{missing.png}"),
    ]


def test_equation_labels(tmp_path):
    src, rep = setup(tmp_path)
    m = {"t": "Math", "c": [{"t": "DisplayMath"}, "\\begin{align}\na \\label{eq:a}\\\\\nb \\label{eq:b}\n\\end{align}"]}
    ast = doc({"t": "Para", "c": [m]})
    normalize.run(ast, src, rep)
    span = ast["blocks"][0]["c"][0]
    assert span["t"] == "Span"
    assert span["c"][0] == ["eq:a", ["tejtex-equation"], [["labels", "eq:a eq:b"]]]
    assert "\\label" not in span["c"][1][0]["c"][1]


def test_bibliography_width_and_cite(tmp_path):
    src, rep = setup(tmp_path)
    cite = {"t": "Cite", "c": [[{"citationId": "k", "citationPrefix": [], "citationSuffix": [], "citationMode": {"t": "NormalCitation"}, "citationNoteNum": 0, "citationHash": 0}], [{"t": "RawInline", "c": ["latex", "\\cite{k}"]}]]}
    ast = doc(
        {"t": "Para", "c": [cite]},
        {"t": "Div", "c": [["", ["thebibliography"], []], [{"t": "Para", "c": [{"t": "Span", "c": [A, [s("9")]]}, {"t": "SoftBreak"}, s("Entry")]}]]},
    )
    rep.add("warning", "partial", "thebibliography", "kept as text")
    normalize.run(ast, src, rep)
    assert ast["blocks"][0]["c"][0]["c"][1] == []
    assert ast["blocks"][1]["c"][1][0]["c"] == [s("Entry")]
    assert rep.elements["Div.thebibliography"]["category"] == "partial"
    assert "RawInline" not in rep.elements
