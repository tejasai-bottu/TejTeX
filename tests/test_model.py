import re
from pathlib import Path

from tejtex import frontend, ir, tree
from tejtex.config import Config
from tejtex.ir.nodes import Bibliography, Citation, CrossReference, Figure, Heading, Image, Math, Table, Theorem, walk

DATA = Path(__file__).parent / "data"


def model(name):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config())
    pandoc = {}
    for lst, i in tree.each(ast["blocks"]):
        n = lst[i]
        if n.get("t") == "Link":
            at = dict(n["c"][0][2])
            if "reference" in at:
                pandoc[at["reference"]] = "".join(x.get("c", " ") for x in n["c"][1])
    return ir.build(ast, rep, s, Config()), rep, pandoc


def of(d, cls):
    return [n for n in walk(d) if isinstance(n, cls)]


def test_numbers_match_latex(real_pandoc):
    d, rep, pandoc = model("refs")
    xs = {x.label: x.text for x in of(d, CrossReference) if x.kind != "ref+label"}
    assert xs == {
        "fig:later": "2.1", "tab:later": "2.1", "eq:second": "(2.2)", "thm:main": "2.1", "it:two": "2",
        "nope": "??", "sec:bg": "1.1", "sec:details": "1.1.1", "eq:first": "(2.1)", "lem:aux": "2.2",
        "fn:one": "1", "it:nested": "2a",
    }
    for label, text in pandoc.items():
        if re.fullmatch(r"[\d.]+", text):
            assert xs[label] == text, label


def test_forward_and_backward_references_resolve(real_pandoc):
    d, rep, _ = model("refs")
    xs = of(d, CrossReference)
    assert all(x.bookmark for x in xs if x.label != "nope")
    bookmarks = {n.bookmark for n in walk(d) if getattr(n, "bookmark", None)}
    for x in xs:
        if x.bookmark:
            assert x.bookmark in bookmarks or any(x.bookmark == m[1] for m in (n.numbers for n in of(d, Math)) for m in m)


def test_diagnostics_have_locations(real_pandoc):
    d, rep, _ = model("refs")
    got = {(x.element, x.loc) for x in rep.diags if not x.category}
    assert got == {
        ("\\label{sec:bg}", "main.tex:58:7"),
        ("\\ref{nope}", "main.tex:15:10"),
        ("\\cite{gamma}", "main.tex:15:44"),
    }
    assert all(x.loc for x in rep.diags)


def test_model_contents(real_pandoc):
    d, rep, _ = model("refs")
    hs = of(d, Heading)
    assert [(h.level, h.number, h.bookmark) for h in hs] == [
        (1, "1", "ch_intro"), (2, "1.1", "sec_bg"), (3, "1.1.1", "sec_details"), (1, "2", "ch_results"), (1, None, None)]
    assert hs[1].src == "main.tex:16:21"
    fig, = of(d, Figure)
    assert (fig.number, fig.bookmark, fig.src) == ("2.1", "fig_later", "main.tex:35:19")
    img, = of(d, Image)
    assert (img.rel, img.media) == ("rTej3", "media/image1.png")
    tab, = of(d, Table)
    assert (tab.number, tab.bookmark, tab.head, len(tab.rows)) == ("2.1", "tab_later", 1, 2)
    thm, lem = of(d, Theorem)
    assert (thm.name, thm.number, "".join(r.text for r in thm.title)) == ("Theorem", "2.1", "Main")
    assert (lem.name, lem.number) == ("Lemma", "2.2")
    bib, = of(d, Bibliography)
    assert [(e.key, e.number) for e in bib.entries] == [("alpha", "1"), ("beta", "2")]
    assert [c.text for c in of(d, Citation)] == ["[1]", "[2, ?]"]
    assert "".join(r.text for r in d.meta.title) == "Reference Test"
    assert len(d.meta.authors) == 2
    assert [r.kind for r in d.ctx.rels.rels] == ["hyperlink", "hyperlink", "image"]
    assert "Heading3" in d.ctx.styles.used


def test_sec63_model(real_pandoc):
    d, rep, _ = model("sec63")
    xs = {x.label: x.text for x in of(d, CrossReference)}
    assert xs == {"sec:method": "2", "fig:a": "1", "tab:a": "1", "eq:a": "(1)"}
    assert [m.numbers[0][0] for m in of(d, Math) if m.numbers] == ["1"]
    assert ir.lines(d)[0] == "1 Introduction"
    assert "[TejTeX: tikzpicture needs rendering]" in ir.lines(d)
