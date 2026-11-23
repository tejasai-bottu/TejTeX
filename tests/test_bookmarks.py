import re
from pathlib import Path

from helpers import W, home, labels, make, marks, part
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.config import Config
from tejtex.ir.nodes import (
    Anchor, BibEntry, Bibliography, Cell, Container, Figure, Heading, Math, Paragraph, Row, Table, TextRun, Theorem,
)

DATA = Path(__file__).parent / "data"


def p(s, st="BodyText"):
    return Paragraph(st, [TextRun(s)])


def render(*blocks):
    data = backend.render(make(list(blocks)))
    assert check(data) == []
    return data


def corpus(name):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config())
    data = backend.render(ir.build(ast, rep, s, Config()))
    assert check(data) == []
    return data, rep


def test_heading_bookmark_wraps_the_text():
    data = render(Heading(1, [TextRun("Intro")], "Heading1", "1", "sec_intro"))
    assert marks(data) == {"sec_intro": "Intro"}
    assert home(data, "sec_intro") == ("Heading1", "Intro")
    assert labels(data) == [("1", "Intro")]


def test_caption_bookmarks():
    fig = Figure([p("picture", "Figure")], [p("A plot", "Caption")], "2", "fig_a")
    tab = Table([Row([Cell([p("x", "Compact")])])], [None], caption=[p("Data", "Caption")], number="1", bookmark="tab_a")
    data = render(fig, tab)
    assert marks(data) == {"fig_a": "2", "tab_a": "1"}
    assert home(data, "fig_a") == ("Caption", "Figure 2: A plot")
    kids = [k.tag.replace(W, "") for k in part(data).find(W + "body")]
    assert kids[:4] == ["p", "p", "p", "tbl"]


def test_targets_without_captions_get_a_point_bookmark():
    fig = Figure([p("picture", "Figure")], bookmark="fig_b")
    tab = Table([Row([Cell([p("cell", "Compact")]), Cell([p("y", "Compact")])])], [None, None], bookmark="tab_b")
    box = Container("center", [p("inside"), p("more")], "div_c")
    data = render(fig, tab, box)
    assert marks(data) == {"fig_b": "", "tab_b": "", "div_c": ""}
    assert home(data, "fig_b") == ("Figure", "picture")
    assert home(data, "tab_b") == ("Compact", "cell")
    assert home(data, "div_c") == ("BodyText", "inside")


def test_equations_theorems_bibliography_and_anchors():
    eq = Paragraph("BodyText", [Math("a = b", True, [("1", "eq_a", "eq:a", None), ("*", None, None, None), ("2", "eq_b", "eq:b", None)])])
    thm = Theorem("theorem", "Theorem", [p("Claim.")], "3", [TextRun("Main")], "thm_main")
    bib = Bibliography([BibEntry("knuth", "1", [TextRun("D. Knuth.")], "bib_knuth")])
    anc = Paragraph("BodyText", [TextRun("Second "), Anchor("it_two", "it:two"), TextRun("item")])
    data = render(eq, thm, bib, anc)
    assert marks(data) == {"eq_a": "1", "eq_b": "2", "thm_main": "3", "bib_knuth": "1", "it_two": ""}
    assert home(data, "thm_main") == ("BodyText", "Theorem 3 (Main). Claim.")
    assert home(data, "bib_knuth") == ("Bibliography", "[1] D. Knuth.")
    assert home(data, "it_two") == ("BodyText", "Second item")


def test_bookmarks_are_paired_unique_and_valid():
    data, rep = corpus("refs")
    root = part(data)
    starts = [(e.get(W + "id"), e.get(W + "name")) for e in root.iter(W + "bookmarkStart")]
    ends = [e.get(W + "id") for e in root.iter(W + "bookmarkEnd")]
    assert sorted(i for i, _ in starts) == sorted(ends)
    assert len({i for i, _ in starts}) == len(starts)
    assert len({n.casefold() for _, n in starts}) == len(starts)
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", n) for _, n in starts)


def test_every_kind_of_label_is_a_bookmark_in_the_right_place():
    data, rep = corpus("refs")
    got = {name: home(data, name) for name in marks(data)}
    assert got["ch_intro"] == ("Heading1", "Intro")
    assert got["sec_bg"] == ("Heading2", "Background")
    assert got["sec_details"] == ("Heading3", "Details")
    assert got["fig_later"] == ("Caption", "Figure 2.1: A plot")
    assert got["tab_later"] == ("Caption", "Table 2.1: A table")
    assert got["eq_first"][1].endswith("(2.1) (2.2)") and got["eq_second"] == got["eq_first"]
    assert got["thm_main"][1].startswith("Theorem 2.1 (Main). ")
    assert got["lem_aux"][1].startswith("Lemma 2.2. ")
    assert got["bib_alpha"] == ("Bibliography", "[1] A. Author. First. 2020.")
    assert got["it_two"] == ("Compact", "Second")
    assert got["it_nested"] == ("Compact", "Nested")
    assert got["fn_one"] == ("FootnoteText", "[1] A note.")
    m = marks(data)
    assert [m[k] for k in ["eq_first", "eq_second", "fig_later", "thm_main", "lem_aux", "bib_beta"]] == ["2.1", "2.2", "2.1", "2.1", "2.2", "2"]
    assert len(marks(data)) == 15


def test_normalized_and_duplicate_labels():
    data, rep = corpus("links")
    names = list(marks(data))
    assert names == [
        "sec_start", "sec_a", "sec_a_2", "L1abc", "sec_a_very_long_label_name_that_goes_bey",
        "sec_a_very_long_label_name_that_goes_b_2", "fig_plot", "tab_data", "eq_energy", "thm_main", "sec_end",
    ]
    assert home(data, "sec_a")[1] == "Middle" and home(data, "sec_a_2")[1] == "Same name"
    nums = dict((t, a) for a, t in labels(data))
    assert (nums["Middle"], nums["Same name"], nums["End"]) == ("2", "2.1", "3")
    diags = [(x.element, x.loc) for x in rep.diags if "more than once" in x.message]
    assert diags == [("\\label{sec:end}", "main.tex:42:1")]
