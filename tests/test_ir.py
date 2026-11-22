import subprocess
import sys
from pathlib import Path

import pytest

from tejtex import ir, source
from tejtex.config import Config
from tejtex.diag import Report
from tejtex.errors import Exit, TejtexError
from tejtex.ir.build import item_ref
from tejtex.ir.context import NumberingEngine, ReferenceTracker, RelationshipManager, StyleRegistry
from tejtex.ir.nodes import (
    Anchor, Bibliography, Break, Citation, CodeBlock, Container, CrossReference, Figure, Footnote,
    Heading, Hyperlink, Image, List, Math, Paragraph, Placeholder, Quote, Rule, Table, TextRun, Theorem, walk,
)

A = ["", [], []]


def s(x):
    return {"t": "Str", "c": x}


SP = {"t": "Space"}


def para(*c):
    return {"t": "Para", "c": list(c)}


def ref(label, kind="ref", shown="?"):
    return {"t": "Link", "c": [["", [], [["reference-type", kind], ["reference", label]]], [s(shown)], ["#" + label, ""]]}


def header(level, text, ident="", classes=None):
    return {"t": "Header", "c": [level, [ident, classes or [], []], [s(text)]]}


def doc(*blocks, meta=None):
    return {"pandoc-api-version": [1, 23, 1, 1], "meta": meta or {}, "blocks": list(blocks)}


class Src:
    def __init__(self, text="", root=None):
        self.text = text
        self.root = root or Path.cwd()

    def where(self, i):
        return ""


def build(ast, src=None, **kw):
    rep = Report()
    return ir.build(ast, rep, src or Src(), Config(**kw)), rep


def nodes(d, cls):
    return [n for n in walk(d) if isinstance(n, cls)]


def test_ir_does_not_import_docx_or_lxml():
    code = "import sys, tejtex.ir, tejtex.ir.build, tejtex.ir.nodes, tejtex.ir.context; bad = [m for m in ('docx', 'lxml') if m in sys.modules]; print(bad); sys.exit(1 if bad else 0)"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_supported_node_type_has_a_representation(tmp_path):
    (tmp_path / "f.png").write_bytes(b"x")
    cell = [A, {"t": "AlignLeft"}, 1, 1, [{"t": "Plain", "c": [s("cell")]}]]
    cite = {"t": "Cite", "c": [[{"citationId": "k", "citationPrefix": [], "citationSuffix": [], "citationMode": {"t": "NormalCitation"}, "citationNoteNum": 0, "citationHash": 0}], []]}
    ast = doc(
        header(1, "H", "h"),
        para(s("a"), SP, {"t": "Emph", "c": [s("i")]}, {"t": "Strong", "c": [s("bo")]}, {"t": "Underline", "c": [s("u")]},
             {"t": "Strikeout", "c": [s("st")]}, {"t": "Superscript", "c": [s("2")]}, {"t": "Subscript", "c": [s("0")]},
             {"t": "SmallCaps", "c": [s("sc")]}, {"t": "Quoted", "c": [{"t": "DoubleQuote"}, [s("q")]]},
             {"t": "Code", "c": [A, "code"]}, {"t": "LineBreak"}, {"t": "SoftBreak"},
             {"t": "Math", "c": [{"t": "InlineMath"}, "x^2"]}, cite, ref("h"),
             {"t": "Link", "c": [A, [s("web")], ["https://e.org", ""]]},
             {"t": "Image", "c": [A, [], ["f.png", ""]]}, {"t": "Note", "c": [para(s("note"))]},
             {"t": "Span", "c": [["sp", [], []], [s("span")]]}, {"t": "RawInline", "c": ["latex", "\\x"]}),
        {"t": "Plain", "c": [s("plain")]},
        {"t": "LineBlock", "c": [[s("l1")], [s("l2")]]},
        {"t": "CodeBlock", "c": [A, "print(1)"]},
        {"t": "RawBlock", "c": ["latex", "\\y"]},
        {"t": "BlockQuote", "c": [para(s("quote"))]},
        {"t": "OrderedList", "c": [[1, {"t": "DefaultStyle"}, {"t": "DefaultDelim"}], [[para(s("o"))]]]},
        {"t": "BulletList", "c": [[para(s("b"))]]},
        {"t": "DefinitionList", "c": [[[s("term")], [[para(s("def"))]]]]},
        {"t": "HorizontalRule"},
        {"t": "Table", "c": [A, [None, []], [[{"t": "AlignLeft"}, {"t": "ColWidthDefault"}]], [A, [[A, [cell]]]], [[A, 0, [], [[A, [cell]]]]], [A, []]]},
        {"t": "Figure", "c": [["fig", [], []], [None, [{"t": "Plain", "c": [s("cap")]}]], [{"t": "Plain", "c": [{"t": "Image", "c": [A, [], ["f.png", ""]]}]}]]},
        {"t": "Div", "c": [["", ["center"], []], [para(s("centered"))]]},
    )
    d, rep = build(ast, Src(root=tmp_path))
    kinds = {type(n).__name__ for n in walk(d)}
    assert kinds >= {
        "Heading", "Paragraph", "TextRun", "Break", "Math", "Citation", "CrossReference", "Hyperlink", "Image",
        "Footnote", "Anchor", "Placeholder", "CodeBlock", "Quote", "List", "ListItem", "Rule", "Table", "Row",
        "Cell", "Figure", "Container",
    }
    runs = {r.text: r for r in nodes(d, TextRun)}
    assert runs["i"].italic and runs["bo"].bold and runs["u"].underline and runs["st"].strike
    assert runs["2"].sup and runs["0"].sub and runs["sc"].smallcaps and runs["code"].code
    assert "“q”" in "".join(r.text for r in nodes(d, TextRun))
    assert [x.kind for x in nodes(d, List)] == ["ordered", "bullet", "description"]
    assert nodes(d, Figure)[0].number == "1"
    assert nodes(d, Image)[0].rel == nodes(d, Image)[1].rel == "rTej2"
    assert nodes(d, Hyperlink)[0].rel == "rTej1"


def test_formatting_toggles_and_merges():
    ast = doc(para(s("a"), SP, {"t": "Emph", "c": [s("b"), SP, {"t": "Emph", "c": [s("c")]}, SP, s("d")]}, SP, s("e")))
    d, rep = build(ast)
    runs = d.blocks[0].inlines
    assert [(r.text, r.italic) for r in runs] == [("a ", False), ("b ", True), ("c", False), (" d", True), (" e", False)]


def test_paragraph_whitespace_is_trimmed():
    ast = doc(para({"t": "Span", "c": [["x", [], []], []]}, SP, s("Text"), SP))
    d, rep = build(ast)
    assert isinstance(d.blocks[0].inlines[0], Anchor)
    assert d.blocks[0].inlines[1].text == "Text"


def test_bookmark_names():
    r = ReferenceTracker()
    assert r.bookmark("fig:a") == "fig_a"
    assert r.bookmark("fig_a") == "fig_a_2"
    assert r.bookmark("FIG_A") == "FIG_A_3"
    assert r.bookmark("1abc") == "L1abc"
    assert r.bookmark("café") == "caf_"
    long = r.bookmark("x" * 60)
    assert len(long) == 40
    assert len(r.bookmark("x" * 60)) == 40
    assert r.bookmark("knuth", "bib_") == "bib_knuth"


def test_numbering_engine():
    e = NumberingEngine()
    a = e.new("bullet", None, None, 1, 0)
    b = e.new("ordered", "DefaultStyle", "DefaultDelim", 1, 0)
    c = e.new("ordered", "DefaultStyle", "DefaultDelim", 3, 1)
    d = e.new("ordered", "LowerRoman", "OneParen", 1, 0)
    assert [n.id for n in (a, b, c, d)] == [1, 2, 3, 4]
    assert b.abstract == c.abstract
    assert (c.level, c.start) == (1, 3)
    levels = e.abstracts["ordered:DefaultStyle:DefaultDelim"].levels
    assert [(x.fmt, x.text) for x in levels[:4]] == [("decimal", "%1."), ("lowerLetter", "(%2)"), ("lowerRoman", "%3."), ("upperLetter", "%4.")]
    assert e.abstracts["bullet:None:None"].levels[1].text == "–"
    assert e.abstracts["ordered:LowerRoman:OneParen"].levels[0].text == "%1)"


def test_relationships():
    r = RelationshipManager()
    a = r.image(Path("a/fig.PNG"))
    assert r.image(Path("a/fig.PNG")) is a
    assert a.target == "media/image1.png"
    link = r.link("https://e.org")
    b = r.image(Path("b.jpg"))
    assert b.target == "media/image2.jpg"
    assert [x.id for x in r.rels] == ["rTej1", "rTej2", "rTej3"]
    assert link.external and not a.external


def test_style_registry():
    st = StyleRegistry()
    st.use("Compact")
    assert st.used == ["Compact", "BodyText", "Normal"]
    assert st.all["Heading2"].name == "heading 2"
    assert st.all["Heading2"].level == 2
    with pytest.raises(KeyError):
        st.use("Nope")


def test_equation_numbering():
    align = "\\begin{align}\na \\label{eq:a} \\\\\nb \\nonumber \\\\\nc \\tag{*} \\label{eq:c} \\\\\n\\begin{cases} x \\\\ y \\end{cases} \\label{eq:d}\n\\end{align}"
    ast = doc(
        para({"t": "Math", "c": [{"t": "DisplayMath"}, "\\begin{equation}\nE\n\\end{equation}"]}),
        para({"t": "Math", "c": [{"t": "DisplayMath"}, align]}),
        para({"t": "Math", "c": [{"t": "DisplayMath"}, "x = y"]}),
        para({"t": "Math", "c": [{"t": "DisplayMath"}, "\\begin{equation*} z \\end{equation*}"]}),
        para(ref("eq:a", "eqref"), ref("eq:c", "eqref"), ref("eq:d", "eqref")),
    )
    d, rep = build(ast)
    ms = nodes(d, Math)
    assert [[n[0] for n in m.numbers] for m in ms] == [["1"], ["2", "*", "3"], [], []]
    assert "\\label" not in ms[1].tex and "\\nonumber" not in ms[1].tex and "\\tag" not in ms[1].tex
    assert [x.text for x in nodes(d, CrossReference)] == ["(2)", "(*)", "(3)"]


def test_item_refs():
    assert item_ref([2]) == "2"
    assert item_ref([1, 2]) == "1b"
    assert item_ref([1, 2, 3]) == "1(b)iii"
    assert item_ref([1, 1, 1, 1]) == "1(a)iA"


def test_sections_and_chapters():
    ast = doc(header(1, "A", "a"), header(2, "B", "b"), header(3, "C", "c"), header(4, "D", "d"), header(2, "E", "e", ["unnumbered"]), header(1, "F", "f"), header(2, "G", "g"))
    d, rep = build(ast)
    assert [h.number for h in d.blocks] == ["1", "1.1", "1.1.1", None, None, "2", "2.1"]
    assert [h.style for h in d.blocks] == ["Heading1", "Heading2", "Heading3", "Heading4", "Heading2", "Heading1", "Heading2"]
    def fig(i):
        return {"t": "Figure", "c": [[i, [], []], [None, [{"t": "Plain", "c": [s("cap")]}]], []]}

    d, rep = build(doc(header(1, "Ch", "c1"), fig("f1"), header(1, "Ch2", "c2"), fig("f2")), Src("\\chapter{Ch}"))
    assert [x.number for x in nodes(d, Figure)] == ["1.1", "2.1"]


def test_forward_and_backward_references():
    ast = doc(para(ref("later"), SP, ref("earlier")), header(1, "Earlier", "earlier"), header(1, "Later", "later"), para(ref("later"), ref("earlier")))
    d, rep = build(ast)
    xs = nodes(d, CrossReference)
    assert [x.text for x in xs] == ["2", "1", "2", "1"]
    assert [x.bookmark for x in xs] == ["later", "earlier", "later", "earlier"]
    assert rep.diags == []


def test_unresolved_and_duplicate_labels_report_locations(tmp_path):
    text = "\\section{A}\\label{a}\nSee \\ref{nope} and \\ref{nope}.\n\\section{B}\\label{a}\n"
    (tmp_path / "main.tex").write_text(text, encoding="utf-8")
    src = source.load(tmp_path / "main.tex", tmp_path.resolve(), Config(), Report())
    ast = doc(header(1, "A", "a"), para(s("See"), SP, ref("nope"), SP, s("and"), SP, ref("nope")), header(1, "B", "a"))
    d, rep = build(ast, src)
    got = [(x.element, x.loc) for x in rep.diags]
    assert got == [("\\label{a}", "main.tex:3:12"), ("\\ref{nope}", "main.tex:2:5"), ("\\ref{nope}", "main.tex:2:20")]
    assert [h.bookmark for h in d.blocks if isinstance(h, Heading)] == ["a", None]
    assert [x.text for x in nodes(d, CrossReference)] == ["??", "??"]


def test_theorems():
    thm = {"t": "Div", "c": [["thm:p", ["theorem"], []], [para({"t": "Strong", "c": [s("Theorem"), SP, s("1.1")]}, SP, s("(Big"), SP, s("Name)."), SP, {"t": "Emph", "c": [s("Body.")]})]]}
    lem = {"t": "Div", "c": [["", ["lemma"], []], [para({"t": "Strong", "c": [s("Lemma"), SP, s("2")]}, s("."), SP, s("Text"))]]}
    center = {"t": "Div", "c": [["", ["center"], []], [para({"t": "Strong", "c": [s("Bold")]}, s("."), SP, s("x"))]]}
    d, rep = build(doc(thm, lem, center, para(ref("thm:p"))))
    t1, t2, c = d.blocks[:3]
    assert isinstance(t1, Theorem) and (t1.kind, t1.name, t1.number, t1.bookmark) == ("theorem", "Theorem", "1.1", "thm_p")
    assert "".join(r.text for r in t1.title) == "Big Name"
    assert [r.text for r in t1.blocks[0].inlines] == ["Body."]
    assert (t2.name, t2.number, t2.title) == ("Lemma", "2", [])
    assert [r.text for r in t2.blocks[0].inlines] == ["Text"]
    assert isinstance(c, Container) and c.kind == "center"
    assert nodes(d, CrossReference)[0].text == "1.1"


def anchor(key):
    return {"t": "Span", "c": [["", ["tejtex-anchor"], [["category", "partial"], ["element", "\\bibitem"], ["source", ""], ["key", key]]], []]}


def cite(*keys, suffix=None):
    cs = [{"citationId": k, "citationPrefix": [], "citationSuffix": [], "citationMode": {"t": "NormalCitation"}, "citationNoteNum": 0, "citationHash": 0} for k in keys]
    if suffix:
        cs[-1]["citationSuffix"] = [s(suffix)]
    return {"t": "Cite", "c": [cs, []]}


def test_bibliography_and_citations():
    bib = {"t": "Div", "c": [["", ["thebibliography"], []], [para(anchor("a"), SP, s("First."), {"t": "SoftBreak"}, anchor("b"), SP, s("Second."))]]}
    d, rep = build(doc(para(cite("b"), SP, cite("a", "zz", suffix="p.5")), bib))
    b2 = d.blocks[1]
    assert isinstance(b2, Bibliography)
    assert [(e.key, e.number, e.bookmark) for e in b2.entries] == [("a", "1", "bib_a"), ("b", "2", "bib_b")]
    assert ["".join(r.text for r in e.inlines) for e in b2.entries] == ["First.", "Second."]
    cs = nodes(d, Citation)
    assert [c.text for c in cs] == ["[2]", "[1, ?, p.5]"]
    assert cs[1].bookmarks == ["bib_a", None]
    assert [x.element for x in rep.diags] == ["\\cite{zz}"]
    d, rep = build(doc(para(cite("k"))))
    assert nodes(d, Citation)[0].text == "[k]"
    assert rep.diags == []


def test_meta():
    meta = {
        "title": {"t": "MetaInlines", "c": [s("T")]},
        "author": {"t": "MetaList", "c": [{"t": "MetaInlines", "c": [s("A")]}, {"t": "MetaInlines", "c": [s("B")]}]},
        "date": {"t": "MetaString", "c": "2026"},
        "abstract": {"t": "MetaBlocks", "c": [para(s("Abs."))]},
    }
    d, rep = build(doc(meta=meta))
    assert d.meta.title[0].text == "T"
    assert [a[0].text for a in d.meta.authors] == ["A", "B"]
    assert d.meta.date[0].text == "2026"
    assert d.meta.abstract[0].style == "Abstract"


def test_placeholders_and_lines():
    ph = {"t": "Div", "c": [["", ["tejtex-placeholder"], [["category", "render"], ["element", "tikzpicture"], ["source", "main.tex:3:1"]]], [para(s("[TejTeX:"), SP, s("tikzpicture"), SP, s("needs"), SP, s("rendering]"))]]}
    d, rep = build(doc(header(1, "H"), ph, {"t": "HorizontalRule"}))
    p = d.blocks[1]
    assert isinstance(p, Placeholder)
    assert (p.category, p.element, p.src, p.inline) == ("render", "tikzpicture", "main.tex:3:1", False)
    assert ir.lines(d) == ["1 H", "[TejTeX: tikzpicture needs rendering]"]


def test_lists_get_their_own_numbering():
    inner = {"t": "OrderedList", "c": [[1, {"t": "DefaultStyle"}, {"t": "DefaultDelim"}], [[para(s("i"))]]]}
    outer = {"t": "BulletList", "c": [[para(s("o")), inner]]}
    again = {"t": "OrderedList", "c": [[4, {"t": "Decimal"}, {"t": "Period"}], [[para(s("x"))]]]}
    d, rep = build(doc(outer, again))
    ls = nodes(d, List)
    assert [(x.kind, x.num, x.level, x.start) for x in ls] == [("bullet", 1, 0, 1), ("ordered", 2, 1, 1), ("ordered", 3, 0, 4)]
    assert ls[0].items[0].blocks[0].style == "Compact"


def test_limits():
    deep = para(s("x"))
    for _ in range(30):
        deep = {"t": "BlockQuote", "c": [deep]}
    with pytest.raises(TejtexError) as e:
        build(doc(deep), nesting=20)
    assert e.value.code == Exit.LIMIT
    build(doc(deep), nesting=40)
    with pytest.raises(TejtexError) as e:
        build(doc(*[para(s("x"))] * 50), nodes=60)
    assert e.value.code == Exit.LIMIT


def test_deep_document_does_not_hit_python_recursion():
    deep = para(s("x"))
    for _ in range(5000):
        deep = {"t": "BlockQuote", "c": [deep]}
    with pytest.raises(TejtexError) as e:
        build(doc(deep))
    assert e.value.code == Exit.LIMIT
