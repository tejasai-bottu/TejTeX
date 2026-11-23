import copy
from pathlib import Path

from helpers import W, fields, home, labels, linked, make, marks, part, shown, update
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.config import Config
from tejtex.ir.nodes import (
    BibEntry, Bibliography, Citation, CrossReference, Figure, Heading, Math, Paragraph, Seq, TextRun, Theorem, walk,
)

DATA = Path(__file__).parent / "data"


def p(s, st="BodyText"):
    return Paragraph(st, [TextRun(s)])


def h(level, text, num=None, mark=None):
    return Heading(level, [TextRun(text)], f"Heading{level}", num, mark)


def render(*blocks):
    data = backend.render(make(list(blocks)))
    assert check(data) == []
    return data


def corpus(name):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config())
    d = ir.build(ast, rep, s, Config())
    data = backend.render(d)
    assert check(data) == []
    return d, data, rep


def strip(e):
    e = copy.deepcopy(e)
    for b in list(e.iter(W + "bookmarkStart", W + "bookmarkEnd")):
        b.getparent().remove(b)
    return e


def find(root, text):
    return next(x for x in root.iter(W + "p") if "".join(t.text or "" for t in x.iter(W + "t")).startswith(text))


def test_heading_styles_share_one_outline_list():
    data = render(h(1, "A", "1"), h(2, "B", "1.1"), h(3, "C", "1.1.1"), h(1, "Plain"), h(4, "D"), h(1, "E", "2"))
    link = linked(data)
    nid = link["Heading1"][0]
    assert {k: link.get(k) for k in ["Heading1", "Heading2", "Heading3", "Heading4"]} == {
        "Heading1": (nid, 0), "Heading2": (nid, 1), "Heading3": (nid, 2), "Heading4": None}
    root = part(data, "word/numbering.xml")
    num = next(n for n in root.iter(W + "num") if n.get(W + "numId") == nid)
    aid = num.find(W + "abstractNumId").get(W + "val")
    a = next(x for x in root.iter(W + "abstractNum") if x.get(W + "abstractNumId") == aid)
    assert a.find(W + "multiLevelType").get(W + "val") == "multilevel"
    lv = []
    for x in a.findall(W + "lvl"):
        st = x.find(W + "pStyle")
        lv.append((st.get(W + "val") if st is not None else None, x.find(W + "lvlText").get(W + "val")))
    assert lv[:4] == [("Heading1", "%1"), ("Heading2", "%1.%2"), ("Heading3", "%1.%2.%3"), (None, "")]
    assert labels(data) == [("1", "A"), ("1.1", "B"), ("1.1.1", "C"), (None, "Plain"), (None, "D"), ("2", "E")]
    plain = find(part(data), "Plain")
    assert plain.find(f"{W}pPr/{W}numPr/{W}numId").get(W + "val") == "0"
    assert all(t.text in "ABCDE" or t.text == "Plain" for t in part(data).iter(W + "t"))


def test_documents_without_numbered_headings_have_no_heading_list():
    data = render(h(1, "Plain"), p("text"))
    assert not any(k.startswith("Heading") for k in linked(data))
    assert find(part(data), "Plain").find(f"{W}pPr/{W}numPr") is None


def test_headings_renumber_when_inserted_or_moved():
    data = render(h(1, "A", "1"), h(2, "B", "1.1"), h(1, "C", "2"), h(2, "D", "2.1"))
    root = part(data)
    new = strip(find(root, "B"))
    new.find(f".//{W}t").text = "New"
    find(root, "A").addnext(new)
    assert labels(data, root) == [("1", "A"), ("1.1", "New"), ("1.2", "B"), ("2", "C"), ("2.1", "D")]
    c = find(root, "C")
    body = root.find(W + "body")
    body.remove(c)
    body.insert(0, c)
    assert labels(data, root) == [("1", "C"), ("2", "A"), ("2.1", "New"), ("2.2", "B"), ("2.3", "D")]


def test_caption_numbers_are_seq_fields():
    fig = Figure([p("picture", "Figure")], [p("A plot", "Caption")], "2.3", "fig_a", seq=Seq("Figure", 1))
    tab = Figure([p("x", "Figure")], [p("Data", "Caption")], "4", "tab_a", name="Table", seq=Seq("Table"))
    data = render(fig, tab)
    assert fields(data) == [("STYLEREF 1 \\w", "2"), ("SEQ Figure \\* ARABIC \\s 1", "3"), ("SEQ Table \\* ARABIC", "4")]
    assert marks(data) == {"fig_a": "2.3", "tab_a": "4"}
    assert home(data, "fig_a") == ("Caption", "Figure 2.3: A plot")
    assert home(data, "tab_a") == ("Caption", "Table 4: Data")


def test_equation_and_theorem_numbers_are_seq_fields():
    eq = Paragraph("BodyText", [Math("a = b", True, [("1.2", "eq_a", "eq:a", Seq("Equation", 1)), ("*", None, None, None)])])
    thm = Theorem("theorem", "Theorem", [p("Claim.")], "3", [], "thm_a", seq=Seq("theorem"))
    note = Theorem("note", "Note", [p("Aside.")], None, [], "note_a")
    data = render(eq, thm, note)
    assert fields(data) == [("STYLEREF 1 \\w", "1"), ("SEQ Equation \\* ARABIC \\s 1", "2"), ("SEQ theorem \\* ARABIC", "3")]
    assert marks(data) == {"eq_a": "1.2", "thm_a": "3", "note_a": "Note"}
    assert home(data, "eq_a")[1] == "a = b (1.2) (*)"
    assert home(data, "thm_a")[1] == "Theorem 3. Claim."
    bold = [r for r in part(data).iter(W + "r") if r.find(f"{W}rPr/{W}b") is not None]
    assert "".join(t.text for r in bold for t in r.iter(W + "t")) == "Theorem 3.Note."


def test_cross_references_are_ref_fields():
    target = [h(1, "Intro", "1", "sec_a"), Paragraph("BodyText", [Math("x", True, [("2", "eq_b", "eq:b", Seq("Equation"))])])]
    refs = Paragraph("BodyText", [
        CrossReference("sec:a", "ref", "1", "sec_a", "", "paragraph", "1"), TextRun(", "),
        CrossReference("eq:b", "eqref", "(2)", "eq_b", "", "text", "2", "(", ")"), TextRun(", "),
        CrossReference("eq:b", "ref+label", "Equation 2", "eq_b", "", "text", "2", "Equation "), TextRun(", "),
        CrossReference("it:c", "ref", "3", "sec_a"), TextRun(", "), CrossReference("nope", "ref", "??"),
    ])
    data = render(*target, refs)
    assert [f for f in fields(data) if f[0].startswith("REF")] == [
        ("REF sec_a \\w \\h \\* CHARFORMAT", "1"), ("REF eq_b \\h \\* CHARFORMAT", "2"), ("REF eq_b \\h \\* CHARFORMAT", "2")]
    assert shown(data)[-1] == "1, (2), Equation 2, 3, ??"
    assert [h.get(W + "anchor") for h in part(data).iter(W + "hyperlink")] == ["sec_a"]


def test_citations_are_ref_fields_to_bibliography_numbers():
    cite = Citation(["a", "b", "zz"], "[1, 2, ?, p. 5]", ["bib_a", "bib_b", None], numbers=["1", "2", "?"], suffix="p. 5")
    bib = Bibliography([BibEntry("a", "1", [TextRun("First.")], "bib_a", Seq("Bib")), BibEntry("b", "2", [TextRun("Second.")], "bib_b", Seq("Bib"))])
    data = render(Paragraph("BodyText", [cite]), bib)
    assert fields(data) == [("REF bib_a \\h \\* CHARFORMAT", "1"), ("REF bib_b \\h \\* CHARFORMAT", "2"), ("SEQ Bib \\* ARABIC", "1"), ("SEQ Bib \\* ARABIC", "2")]
    assert shown(data) == ["[1, 2, ?, p. 5]", "[1] First.", "[2] Second."]
    assert marks(data) == {"bib_a": "1", "bib_b": "2"}


def test_field_results_match_a_word_style_update(real_pandoc):
    for name in ["fields", "refs", "links", "full"]:
        d, data, rep = corpus(name)
        assert update(data) == fields(data), name


def test_fields_corpus_follows_latex(real_pandoc):
    d, data, rep = corpus("fields")
    assert shown(data) == [
        "Field Test", "1\tStart",
        "See Chapter\xa02, Section\xa01.2, Figure\xa01.1, Table\xa01.1, Equation\xa0(1.1.1), Theorem\xa01.1, "
        "Lemma\xa01.2, Definition\xa01.1.1, Remark\xa01 and [2, 3].",
        "1.1\tOne", "\\begin{equation}a = b \\end{equation} (1.1.1)", "Theorem 1.1. First.", "Lemma 1.2. Second.",
        "Definition 1.1.1. Third.", "Remark 1. Fourth.", "Note. Unnumbered.", "", "Figure 1.1: First figure",
        "1.2\tTwo", "\\begin{equation}c = d \\end{equation} (1.2.1)", "Table 1.1: First table", "x", "y",
        "Definition 1.2.1. Fifth.", "2\tEnd", "", "Figure 2.1: Second figure", "Theorem 2.1. Sixth.", "Remark 2. Seventh.",
        "Back to Section\xa01.1, Equation\xa0(1.2.1), Figure\xa02.1, Theorem\xa02.1, Definition\xa01.2.1 and [2, p.\xa03]. "
        "Missing: [?].",
        "Bibliography",
        "[1] Ann Böhm and Carl Doe. On dynamic fields. TUGboat, 12(3):1–10, 2020. https://example.org/fields",
        "[2] Donald E. Knuth. The TeXbook. Addison-Wesley, 1984.",
        "[3] Leslie Lamport. LaTeX: A Document Preparation System. Addison-Wesley, 2nd edition, 1994.",
    ]
    seqs = sorted({c.split()[1] + " " + " ".join(c.split()[4:]) for c, _ in fields(data) if c.startswith("SEQ")})
    assert seqs == ["Bib ", "Equation \\s 2", "Figure \\s 1", "Table \\s 1", "definition \\s 2", "remark ", "theorem \\s 1"]
    thms = [(t.name, t.number, t.seq) for t in walk(d) if isinstance(t, Theorem)]
    assert thms == [
        ("Theorem", "1.1", Seq("theorem", 1)), ("Lemma", "1.2", Seq("theorem", 1)), ("Definition", "1.1.1", Seq("definition", 2)),
        ("Remark", "1", Seq("remark")), ("Note", None, None), ("Definition", "1.2.1", Seq("definition", 2)),
        ("Theorem", "2.1", Seq("theorem", 1)), ("Remark", "2", Seq("remark")),
    ]
    got = [(x.level, x.element, x.message) for x in rep.diags if x.element != "\\centering"]
    assert got == [
        ("info", "\\numberwithin", "numbers restart at the heading level with Word fields"),
        ("info", "\\maketitle", "title block is built from \\title, \\author and \\date"),
        ("info", "\\bibliographystyle", "the style sets the order and the title case of the bibliography"),
        ("warning", "\\cite{missing}", "citation key not found in the bibliography"),
    ]


def test_inserted_content_renumbers_after_update(real_pandoc):
    d, data, rep = corpus("fields")
    root = part(data)
    find(root, "Start").addprevious(strip(find(root, "Start")))
    find(root, "Figure 1.1").addprevious(strip(find(root, "Figure 1.1")))
    find(root, "\\begin{equation}a").addprevious(strip(find(root, "\\begin{equation}a")))
    find(root, "Theorem 1.1").addprevious(strip(find(root, "Theorem 1.1")))
    find(root, "Remark 1.").addprevious(strip(find(root, "Remark 1.")))
    new = dict((c.split()[1], v) for c, v in update(data, root) if c.startswith("REF"))
    old = dict((c.split()[1], v) for c, v in fields(data) if c.startswith("REF"))
    assert old == {
        "ch_end": "2", "sec_two": "1.2", "fig_one": "1.1", "tab_one": "1.1", "eq_one": "1.1.1", "thm_one": "1.1",
        "lem_one": "1.2", "def_one": "1.1.1", "rem_one": "1", "bib_knuth": "2", "bib_lamport": "3", "sec_one": "1.1",
        "eq_two": "1.2.1", "fig_two": "2.1", "thm_two": "2.1", "def_two": "1.2.1",
    }
    assert new == {
        "ch_end": "3", "sec_two": "2.2", "fig_one": "2.2", "tab_one": "2.1", "eq_one": "2.1.2", "thm_one": "2.2",
        "lem_one": "2.3", "def_one": "2.1.1", "rem_one": "2", "bib_knuth": "2", "bib_lamport": "3", "sec_one": "2.1",
        "eq_two": "2.2.1", "fig_two": "3.1", "thm_two": "3.1", "def_two": "2.2.1",
    }


def test_moved_figure_renumbers_after_update(real_pandoc):
    d, data, rep = corpus("fields")
    root = part(data)
    second = find(root, "Figure 2.1")
    second.getparent().remove(second)
    find(root, "Figure 1.1").addprevious(second)
    new = dict((c.split()[1], v) for c, v in update(data, root) if c.startswith("REF"))
    assert (new["fig_two"], new["fig_one"]) == ("1.1", "1.2")


def test_numbering_within_a_deep_level_is_reported(real_pandoc, tmp_path):
    tex = "\\documentclass{article}\n\\usepackage{amsmath}\n\\numberwithin{equation}{paragraph}\n\\begin{document}\n" \
          "\\section{A}\n\\begin{equation}x\\end{equation}\n\\end{document}\n"
    (tmp_path / "main.tex").write_text(tex, encoding="utf-8")
    ast, rep, s = frontend.read(tmp_path / "main.tex", Config())
    d = ir.build(ast, rep, s, Config())
    assert [(x.level, x.element) for x in rep.diags if x.category == "partial"] == [("warning", "\\numberwithin{equation}{paragraph}")]
    assert [m.numbers for m in walk(d) if isinstance(m, Math)] == [[("1", None, None, Seq("Equation"))]]


def test_every_link_and_field_points_to_a_bookmark(real_pandoc):
    for name in ["fields", "refs", "links", "full", "format", "lists", "tables", "media"]:
        d, data, rep = corpus(name)
        names = {k.casefold() for k in marks(data)}
        for e in part(data).iter(W + "hyperlink"):
            assert e.get(W + "anchor") is None or e.get(W + "anchor").casefold() in names
        for c, _ in fields(data):
            if c.startswith("REF"):
                assert c.split()[1].casefold() in names
