from pathlib import Path

from helpers import W, links, make, part
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.config import Config
from tejtex.ir.nodes import (
    Anchor, Citation, CrossReference, Hyperlink, List, ListItem, Paragraph, TextRun,
)

DATA = Path(__file__).parent / "data"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def render(*blocks, urls=()):
    d = make(list(blocks))
    for u in urls:
        d.ctx.rels.link(u)
    data = backend.render(d)
    assert check(data) == []
    return data


def corpus(name):
    ast, rep, s = frontend.read(DATA / name / "main.tex", Config())
    data = backend.render(ir.build(ast, rep, s, Config()))
    assert check(data) == []
    return data, rep


def para(*xs):
    return Paragraph("BodyText", list(xs))


def target():
    return para(TextRun("Here"), Anchor("sec_a", "sec:a"))


def test_cross_references_become_internal_links():
    data = render(target(), para(CrossReference("sec:a", "ref", "2", "sec_a"), TextRun(" and "), CrossReference("sec:a", "eqref", "(2)", "sec_a")))
    assert links(data) == [("sec_a", "2"), ("sec_a", "(2)")]
    assert not part(data, "word/_rels/document.xml.rels").xpath("//*[contains(@Target, 'sec_a')]")


def test_undefined_reference_is_plain_text():
    data = render(para(CrossReference("nope", "ref", "??"), CrossReference("nope", "eqref", "(??)")))
    assert links(data) == []
    assert "".join(t.text for t in part(data).iter(W + "t")) == "??(??)"


def test_citations_link_to_their_first_entry():
    data = render(target(), para(Citation(["a", "b"], "[1, 2]", [None, "sec_a"]), Citation(["c"], "[?]", [None])))
    assert links(data) == [("sec_a", "[1, 2]")]


def test_external_links_use_relationships():
    data = render(para(Hyperlink([TextRun("site")], "https://example.org", "rTej1")), urls=["https://example.org"])
    h = part(data).find(f".//{W}hyperlink")
    assert h.get(R + "id") == "rTej1" and h.get(W + "anchor") is None
    assert h.find(f"{W}r/{W}rPr/{W}rStyle").get(W + "val") == "Hyperlink"
    rel = [r for r in part(data, "word/_rels/document.xml.rels") if r.get("Id") == "rTej1"][0]
    assert (rel.get("Target"), rel.get("TargetMode")) == ("https://example.org", "External")
    assert rel.get("Type").endswith("/hyperlink")


def test_links_keep_their_formatting_and_work_in_lists():
    bold = Hyperlink([TextRun("bold ", bold=True), TextRun("code", code=True)], "https://e.org", "rTej1")
    item = ListItem([Paragraph("Compact", [TextRun("see "), CrossReference("sec:a", "ref", "2", "sec_a")])])
    data = render(target(), para(bold), List("bullet", [item]), urls=["https://e.org"])
    hs = list(part(data).iter(W + "hyperlink"))
    runs = [(r.find(f"{W}t").text, r.find(f"{W}rPr/{W}b") is not None, r.find(f"{W}rPr/{W}rStyle").get(W + "val")) for r in hs[0].iter(W + "r")]
    assert runs == [("bold ", True, "Hyperlink"), ("code", False, "VerbatimChar")]
    li = hs[1].getparent()
    assert li.find(f"{W}pPr/{W}numPr") is not None and hs[1].get(W + "anchor") == "sec_a"


def test_links_are_not_nested():
    inner = Hyperlink([TextRun("see "), CrossReference("sec:a", "ref", "2", "sec_a")], None, None, "sec_a")
    data = render(target(), para(inner))
    assert links(data) == [("sec_a", "see 2")]
    assert not part(data).xpath("//w:hyperlink//w:hyperlink", namespaces={"w": W[1:-1]})


def test_links_corpus():
    data, rep = corpus("links")
    got = links(data)
    assert got[:8] == [
        ("fig_plot", "Figure 1"), ("tab_data", "1"), ("eq_energy", "(1)"), ("thm_main", "1"),
        ("sec_end", "3"), ("sec_end", "3"), ("sec_end", "3"), ("tab_data", "1"),
    ]
    assert ("sec_start", "back to the start") in got
    assert got[-7:] == [
        ("sec_start", "1"), ("sec_a", "2"), ("sec_a_2", "2.1"), ("L1abc", "2.2"),
        ("sec_a_very_long_label_name_that_goes_bey", "2.3"), ("sec_a_very_long_label_name_that_goes_b_2", "2.4"), ("eq_energy", "Equation 1"),
    ]
    rels = {r.get("Id"): r.get("Target") for r in part(data, "word/_rels/document.xml.rels") if r.get("TargetMode") == "External"}
    assert sorted(rels.values()) == ["https://example.com/a?b=1&c=2", "https://example.org/list", "mailto:info@example.com"]
    ext = [(rels[a], t) for a, t in got if a in rels]
    assert ext == [("https://example.org/list", "a list link"), ("https://example.com/a?b=1&c=2", "https://example.com/a?b=1&c=2"), ("mailto:info@example.com", "mail")]
    text = "".join(t.text for t in part(data).iter(W + "t"))
    assert "Undefined: ?? and (??)." in text
    assert "script, file and relative" in text
    bad = sorted((x.element, x.loc) for x in rep.diags if "not allowed" in x.message)
    assert bad == [("\\href{file:///etc/passwd}", "main.tex:36:43"), ("\\href{javascript:alert(1)}", "main.tex:36:7"), ("\\href{notes.pdf}", "main.tex:36:79")]
    und = [(x.element, x.loc) for x in rep.diags if "undefined" in x.message]
    assert und == [("\\ref{sec:nowhere}", "main.tex:8:12"), ("\\eqref{eq:nowhere}", "main.tex:8:34")]


def test_refs_corpus_links_forward_and_backward():
    data, rep = corpus("refs")
    anchors = [a for a, _ in links(data)]
    assert anchors[:6] == ["fig_later", "tab_later", "eq_second", "thm_main", "it_two", "fig_later"]
    assert anchors[-7:] == ["sec_bg", "sec_details", "eq_first", "lem_aux", "fn_one", "it_nested", "ch_intro"]
    assert ("bib_alpha", "[1]") in links(data) and ("bib_beta", "[2, ?]") in links(data)
