from pathlib import Path

import pytest

from helpers import W, make, paras, part, style
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.config import Config
from tejtex.ir.nodes import (
    Break, Citation, CrossReference, Footnote, Heading, Image, List, ListItem, Math, Meta, Paragraph,
    Placeholder, Quote, TextRun,
)

DATA = Path(__file__).parent / "data"


def render(*blocks, meta=None):
    data = backend.render(make(list(blocks), meta))
    assert check(data) == []
    return data


def test_paragraph_styles():
    data = render(Paragraph("BodyText", [TextRun("body")]), Paragraph("Compact", [TextRun("tight")]))
    assert [(s, [t for t, _ in r]) for s, r in paras(data)] == [("BodyText", ["body"]), ("Compact", ["tight"])]


def test_headings_use_builtin_styles_with_outline_levels():
    hs = [Heading(i, [TextRun(f"H{i}")], f"Heading{i}", "2.1" if i == 2 else None) for i in range(1, 7)]
    data = render(*hs)
    got = paras(data)
    assert [s for s, _ in got] == [f"Heading{i}" for i in range(1, 7)]
    assert got[1][1] == [("2.1\t", set()), ("H2", set())]
    assert got[0][1] == [("H1", set())]
    for i in range(1, 7):
        s = style(data, f"Heading{i}")
        assert s.find(f"{W}name").get(W + "val") == f"heading {i}"
        assert s.find(f"{W}pPr/{W}outlineLvl").get(W + "val") == str(i - 1)
        assert s.get(W + "customStyle") is None


def test_headings_have_no_direct_formatting():
    data = render(Heading(1, [TextRun("Title")], "Heading1", "1"))
    p = next(part(data).iter(W + "p"))
    assert [c.tag for c in p.find(W + "pPr")] == [W + "pStyle"]
    assert all(r.find(W + "rPr") is None for r in p.iter(W + "r"))


@pytest.mark.parametrize("flag,prop", [
    ("bold", "b"), ("italic", "i"), ("underline", "u=single"), ("strike", "strike"),
    ("sup", "vertAlign=superscript"), ("sub", "vertAlign=subscript"), ("smallcaps", "smallCaps"),
    ("code", "rStyle=VerbatimChar"),
])
def test_run_properties(flag, prop):
    data = render(Paragraph("BodyText", [TextRun("plain"), TextRun("x", **{flag: True})]))
    assert paras(data)[0][1] == [("plain", set()), ("x", {prop})]


def test_combined_formatting():
    data = render(Paragraph("BodyText", [TextRun("bi", bold=True, italic=True)]))
    assert paras(data)[0][1] == [("bi", {"b", "i"})]


def test_breaks_and_placeholders():
    data = render(
        Paragraph("BodyText", [TextRun("a"), Break(), TextRun("b"), Placeholder("unsupported", "\\foo", "[TejTeX: \\foo is not supported]", "", True)]),
        Placeholder("render", "tikzpicture", "[TejTeX: tikzpicture needs rendering]"),
    )
    (s1, r1), (s2, r2) = paras(data)
    assert r1 == [("a", set()), ("\n", set()), ("b", set()), ("[TejTeX: \\foo is not supported]", {"rStyle=PlaceholderChar"})]
    assert (s2, r2) == ("Placeholder", [("[TejTeX: tikzpicture needs rendering]", set())])


def test_inline_types_without_native_handler_keep_their_text():
    data = render(Paragraph("BodyText", [
        CrossReference("a", "ref", "2.1"), Citation(["k"], "[1]"), Math("x^2"),
        Footnote("1", [Paragraph("FootnoteText", [TextRun("note")])]), Image("f.png"),
    ]))
    assert [t for t, _ in paras(data)[0][1]] == ["2.1", "[1]", "x^2", "[1]", "[image: f.png]"]
    assert paras(data)[-1][1][0][0] == "[1] note"


def test_title_block():
    meta = Meta(title=[TextRun("T")], authors=[[TextRun("A")], [TextRun("B")]], date=[TextRun("D")],
                abstract=[Paragraph("Abstract", [TextRun("Abs.")])])
    data = render(Paragraph("BodyText", [TextRun("x")]), meta=meta)
    assert [(s, r[0][0]) for s, r in paras(data)] == [
        ("Title", "T"), ("Author", "A"), ("Author", "B"), ("Date", "D"), ("Abstract", "Abs."), ("BodyText", "x")]


def test_created_styles():
    data = render(
        Paragraph("Compact", [TextRun("c", code=True)]),
        Quote([Paragraph("BlockText", [TextRun("q")])]),
        Placeholder("render", "x", "[TejTeX: x needs rendering]"),
    )
    assert style(data, "VerbatimChar").find(f"{W}rPr/{W}rFonts").get(W + "ascii") == "Consolas"
    assert style(data, "Placeholder").find(f"{W}rPr/{W}color").get(W + "val") == "C00000"
    assert style(data, "Compact").find(f"{W}basedOn").get(W + "val") == "BodyText"
    assert style(data, "Compact").get(W + "customStyle") == "1"
    assert style(data, "BlockText").get(W + "customStyle") is None
    assert style(data, "BlockText").find(f"{W}name").get(W + "val") == "Block Text"


def test_xml_invalid_characters_are_removed():
    data = render(Paragraph("BodyText", [TextRun("a\x0cb\x01c")]))
    assert paras(data)[0][1] == [("abc", set())]


def test_containers_write_their_paragraphs_natively():
    lst = List("bullet", [ListItem([Paragraph("Compact", [TextRun("item", bold=True)])])], 1)
    data = render(Quote([Paragraph("BlockText", [TextRun("quoted")])]), lst)
    assert paras(data) == [("BlockText", [("quoted", set())]), ("Compact", [("item", {"b"})])]


def corpus(name):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config())
    data = backend.render(ir.build(ast, rep, s, Config()))
    assert check(data) == []
    return paras(data)


def test_format_corpus_runs(real_pandoc):
    got = corpus("format")
    runs = next(r for s, r in got if s == "BodyText" and r[0][0] == "Plain ")
    assert runs == [
        ("Plain ", set()), ("bold", {"b"}), (" ", set()), ("italic", {"i"}), (" ", set()),
        ("emph ", {"i"}), ("upright", set()), (" again", {"i"}), (" ", set()), ("both", {"b", "i"}), (" ", set()),
        ("code()", {"rStyle=VerbatimChar"}), (" ", set()), ("under", {"u=single"}), (" ", set()),
        ("struck", {"strike"}), (" x", set()), ("2", {"vertAlign=superscript"}), (" H", set()),
        ("2", {"vertAlign=subscript"}), ("O ", set()), ("Small Caps", {"smallCaps"}), (". ", set()),
        ("Italic with ", {"i"}), ("upright", set()), (" inside", {"i"}), (".", set()), ("\n", set()),
        ("After a line break.", set()),
    ]


def test_format_corpus_structure(real_pandoc):
    got = corpus("format")
    assert [s for s, _ in got[:5]] == ["Title", "Author", "Author", "Date", "Abstract"]
    heads = [(s, r[0][0]) for s, r in got if s and s.startswith("Heading")]
    assert heads == [("Heading1", "1\t"), ("Heading2", "1.1\t"), ("Heading3", "1.1.1\t"), ("Heading4", "Fourth level"), ("Heading1", "Unnumbered")]
    assert ("BlockText", [("A quoted paragraph.", set())]) in got
    assert ("Placeholder", [("[TejTeX: tikzpicture needs rendering]", set())]) in got
    assert any(("[TejTeX: \\unknowncmd is not supported]", {"rStyle=PlaceholderChar"}) in r for _, r in got)


def test_refs_corpus_headings(real_pandoc):
    heads = [(s, r[0][0]) for s, r in corpus("refs") if s and s.startswith("Heading")]
    assert heads == [("Heading1", "1\t"), ("Heading2", "1.1\t"), ("Heading3", "1.1.1\t"), ("Heading1", "2\t")]
