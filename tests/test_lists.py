import io
from pathlib import Path

import docx

from helpers import W, labels, make, numbering, part
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.config import Config
from tejtex.frontend import items, options
from tejtex.ir.nodes import List, ListItem, Paragraph, TextRun, walk

DATA = Path(__file__).parent / "data"


def render(*blocks):
    return backend.render(make(list(blocks)))


def p(s):
    return Paragraph("Compact", [TextRun(s)])


def num(x):
    pr = x.find(f"{W}pPr/{W}numPr")
    if pr is None:
        return None
    return pr.find(W + "numId").get(W + "val"), pr.find(W + "ilvl").get(W + "val")


def ind(x):
    i = x.find(f"{W}pPr/{W}ind")
    return {k.replace(W, ""): v for k, v in i.attrib.items()} if i is not None else {}


def ps(data):
    return list(part(data).iter(W + "p"))


def test_numbering_part_keeps_the_template_definitions():
    data = render(List("ordered", [ListItem([p("a")])]), List("bullet", [ListItem([p("b")])]))
    root = part(data, "word/numbering.xml")
    kids = [x.tag.replace(W, "") for x in root]
    assert kids.index("num") > max(i for i, k in enumerate(kids) if k == "abstractNum")
    ids = [int(a.get(W + "abstractNumId")) for a in root.findall(W + "abstractNum")]
    assert ids == list(range(11))
    nums = root.findall(W + "num")
    assert [n.get(W + "numId") for n in nums] == [str(i) for i in range(1, 12)]
    own = nums[-2:]
    assert [n.find(W + "abstractNumId").get(W + "val") for n in own] == ["9", "10"]
    for n in own:
        o = n.find(W + "lvlOverride")
        assert o.get(W + "ilvl") == "0" and o.find(W + "startOverride").get(W + "val") == "1"
    a = root.findall(W + "abstractNum")[9]
    assert a.find(W + "multiLevelType").get(W + "val") == "hybridMultilevel"
    assert len(a.findall(W + "lvl")) == 9
    assert check(data) == []


def test_items_use_native_numbering():
    data = render(List("ordered", [ListItem([p("one"), p("more")]), ListItem([p("two")])]))
    a, b, c = ps(data)
    assert num(a) == ("10", "0") and num(c) == ("10", "0")
    assert num(b) is None and ind(b) == {"left": "720"}
    assert [x.text for x in a.iter(W + "t")] == ["one"]
    assert labels(data) == [("1.", "one"), (None, "more"), ("2.", "two")]


def test_level_indents():
    data = render(List("ordered", [ListItem([p("x")])], level=2))
    lvl = [x for x in part(data, "word/numbering.xml").iter(W + "lvl") if x.get(W + "ilvl") == "2"][-1]
    assert ind(lvl) == {"left": "2160", "hanging": "360"}
    assert num(ps(data)[0]) == ("10", "2")


def test_nested_lists_and_empty_items():
    inner = List("bullet", [ListItem([p("in")])], level=1)
    data = render(List("ordered", [ListItem([inner, p("after")]), ListItem([])]))
    assert labels(data) == [("1.", ""), ("–", "in"), (None, "after"), ("2.", "")]
    a, b, c, d = ps(data)
    assert num(b) == ("11", "1")
    assert ind(c) == {"left": "720"}


def test_lists_restart():
    data = render(List("ordered", [ListItem([p("a")]), ListItem([p("b")])]), List("ordered", [ListItem([p("c")])], start=4))
    assert labels(data) == [("1.", "a"), ("2.", "b"), ("4.", "c")]
    nums = numbering(data)
    assert nums["10"][0] == nums["11"][0]
    assert nums["11"][1] == {0: 4}


def test_custom_labels():
    lst = List("ordered", [ListItem([p("a")]), ListItem([p("b")], label="(x)"), ListItem([p("c")])])
    data = render(lst)
    assert labels(data) == [("1.", "a"), ("(x)", "b"), ("2.", "c")]
    lid = num(ps(data)[1])[0]
    assert set(numbering(data)[lid][0].values()) == {("none", "(x)")}


def test_description_lists():
    nested = List("bullet", [ListItem([p("deep")])], level=1)
    term = [TextRun("Term"), TextRun(" it", italic=True)]
    data = render(List("description", [ListItem([p("body"), p("more"), nested], term)]))
    a, b, c = ps(data)
    assert num(a) is None and ind(a) == {"left": "720", "hanging": "720"}
    runs = [(r.find(f"{W}t").text, r.find(f"{W}rPr/{W}b") is not None) for r in a.iter(W + "r")]
    assert runs == [("Term", True), (" it", True), (" ", False), ("body", False)]
    assert ind(b) == {"left": "720"}
    assert num(c) == ("10", "1")


def test_enumitem_options():
    assert options("[label=(\\alph*)]") == ("[(a)]", "supported", "label and start are kept as Word numbering")
    assert options("[label=\\Roman*., start=3]")[0] == "[I.]\\setcounter{enumi}{2}"
    assert options("[label={\\arabic*)}, leftmargin=*]")[:2] == ("[1)]", "supported")
    assert options("[start=0]")[0] == "\\setcounter{enumi}{-1}"
    assert options("[nosep, leftmargin=2em]") == ("", "unsupported", "layout options ignored; Word handles layout")
    assert options("[label=Step \\arabic*:]") is None
    assert options("[label=(\\alph*.]") is None
    assert options("[resume]") is None
    assert options("[font=\\bfseries]") is None


class Src:
    def __init__(self, text):
        self.text = text
        self.body = 0

    def mark(self, info, body=""):
        assert info == {"item": True}
        return f"<{body}>"


def test_item_labels_are_marked_in_itemize_and_enumerate_only():
    t = (
        "\\begin{enumerate}\\item[(x)] a % \\item[no]\n\\item[{[y]}] b"
        "\\begin{description}\\item[T] d\\end{description}\\item[$\\star$] c\\end{enumerate}"
        "\\begin{itemize}\\item [--] e \\itemsep[x]\\end{itemize}\\item[out]"
    )
    got = items(Src(t))
    assert [t[a:b] for a, b, _ in got] == ["\\item[(x)]", "\\item[{[y]}]", "\\item[$\\star$]", "\\item [--]"]
    assert [r for _, _, r in got] == ["\\item <(x)>", "\\item <{[y]}>", "\\item <$\\star$>", "\\item <-->"]


def test_lists_corpus_follows_latex(real_pandoc):
    ast, rep, s = frontend.read(DATA / "lists" / "main.tex", Config())
    d = ir.build(ast, rep, s, Config())
    data = backend.render(d)
    assert check(data) == []
    got = [(a, t.strip()) for a, t in labels(data)]
    assert got == [
        (None, "1Lists"), ("1.", "First step."), ("2.", "Second step."), ("(a)", "Inner one."),
        ("(b)", "Inner two."), ("i.", "Deep one."), ("A.", "Deepest one."), ("(x)", "Custom label."),
        ("3.", "Third step."), (None, "A second paragraph in the third step."), ("4.", ""),
        ("•", "Item that starts with a list."), ("5.", ""), ("•", "Bullet one."), ("–", "Bullet two."),
        ("∗", "Bullet three."), ("·", "Bullet four."), ("•", "Bullet with numbers."),
        ("1.", "Numbered inside bullets."), (None, "Text between lists."), ("1.", "Restarted inside bullets."),
        ("–", "Dash label."), ("(a)", "Lettered."), ("5.", "Starts at five."), ("C.", "Starts at C."),
        ("1.", "Resumed in LaTeX."), (None, "Term Definition text."), ("•", "Nested in a definition."),
        (None, "Other Second definition."), (None, "See items 2, 2b, 2(b)i, 2(b)iA, 1 and (a)."),
    ]
    diags = {(x.element, x.category, x.loc) for x in rep.diags}
    assert ("[label=\\Alph*., start=3]", "supported", "main.tex:60:18") in diags
    assert ("[resume]", "partial", "main.tex:64:18") in diags
    shown = {lv[1] for levels, _ in numbering(data).values() for lv in levels.values()}
    for n in walk(d):
        if isinstance(n, ListItem) and n.label is not None:
            assert n.label in shown


def test_lists_corpus_opens_in_python_docx(real_pandoc):
    ast, rep, s = frontend.read(DATA / "lists" / "main.tex", Config())
    data = backend.render(ir.build(ast, rep, s, Config()))
    doc = docx.Document(io.BytesIO(data))
    assert sum(1 for x in doc.paragraphs if x._p.pPr is not None and x._p.pPr.numPr is not None) == 24
