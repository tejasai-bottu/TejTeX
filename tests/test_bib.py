from helpers import fields, shown
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.config import Config
from tejtex.ir import bib
from tejtex.ir.nodes import Citation, walk

BIB = r"""
@comment{ignored @book{hidden, title={No}} }
@preamble{"\newcommand{\x}{y}"}
@STRING{ pub = "Big" # " Press" }
@Book{b1, author = {Zed, Ann and Bob Young and {World Health Organization}}, title = {A Book},
  publisher = pub, year = 2001, month = jan, edition = {3}}
@inproceedings{p1, author = "Carl Ames", title = "Fast {T}rees: {GPU} Methods", booktitle = "Proc. of Stuff",
  editor = "Dee Eff and Gee Aitch", pages = "5--9", publisher = "ACM", year = 2010}
@phdthesis{t1, author = {Ivy Jay}, title = {Deep Thoughts}, school = {MIT}, year = {2015}}
@techreport{r1, author = {Kay Ell}, title = {A Report}, institution = {Lab}, number = {TR-7}, year = {2019}, note = {Draft}}
@misc{m1, author = {Em En}, title = {Web Page}, howpublished = {Online}, year = {2022}, url = {https://example.org/m}}
@article{a2, author = {Ann Zed}, title = {Second Paper}, journal = {J}, year = {1999}, pages = {7}}
"""


def entries():
    return {e["key"]: e for e in bib.parse(BIB)}


def text(e, case=True):
    runs, url = bib.runs(e, case)
    return "".join(f"<{r.text}>" if r.italic else r.text for r in runs), url


def test_decode_turns_latex_into_text():
    assert bib.decode(r"B{\"o}hm \'{e} \c{c} \c c {\ss} \o{} {\LaTeX} --- 1--2 ``q'' a~b {\i} \v{s} \& {\relax}") == \
        "Böhm é ç ç ß ø LaTeX — 1–2 “q” a\xa0b ı š &"


def test_sentence_case_keeps_braces_and_the_start():
    assert bib.sentence(r"The {GPU} Era: {\LaTeX} Fields and More") == r"The {GPU} era: {\LaTeX} fields and more"
    assert bib.decode(bib.sentence(r"{\"O}ffentliche Daten")) == "Öffentliche daten"


def test_parse_reads_strings_months_and_skips_comments():
    es = entries()
    assert list(es) == ["b1", "p1", "t1", "r1", "m1", "a2"]
    assert es["b1"]["type"] == "book"
    assert (es["b1"]["fields"]["publisher"], es["b1"]["fields"]["month"]) == ("Big Press", "January")
    assert es["p1"]["fields"]["pages"] == "5--9"


def test_people_and_order():
    assert bib.people("A and B and C") == "A, B, and C"
    assert bib.people("Zed, Ann and {Big Org}") == "Ann Zed and Big Org"
    es = list(entries().values())
    cited = ["t1", "p1", "b1", "zz"]
    assert [e["key"] for e in bib.order(es, cited, "plain")] == ["p1", "t1", "b1"]
    assert [e["key"] for e in bib.order(es, cited, "unsrt")] == ["t1", "p1", "b1"]
    assert [e["key"] for e in bib.order(es, ["a2", "b1"], "plain")] == ["a2", "b1"]
    assert [e["key"] for e in bib.order(es, ["a2", "b1"], "nty")] == ["b1", "a2"]
    assert [e["key"] for e in bib.order(es, ["*"], "none")] == ["b1", "p1", "t1", "r1", "m1", "a2"]


def test_entry_formats():
    es = entries()
    assert text(es["b1"]) == ("Ann Zed, Bob Young, and World Health Organization. <A Book>. Big Press, third edition, 2001.", "")
    assert text(es["p1"]) == ("Carl Ames. Fast Trees: GPU methods. In Dee Eff and Gee Aitch, editors, <Proc. of Stuff>, pages 5–9. ACM, 2010.", "")
    assert text(es["p1"], False)[0].startswith("Carl Ames. Fast Trees: GPU Methods. ")
    assert text(es["t1"]) == ("Ivy Jay. <Deep Thoughts>. PhD thesis, MIT, 2015.", "")
    assert text(es["r1"]) == ("Kay Ell. A report. Technical Report TR-7, Lab, 2019. Draft.", "")
    assert text(es["m1"]) == ("Em En. Web page. Online, 2022.", "https://example.org/m")
    assert text(es["a2"]) == ("Ann Zed. Second paper. <J>, page 7, 1999.", "")


def build(tmp_path, tex, files):
    (tmp_path / "main.tex").write_text(tex, encoding="utf-8")
    for k, v in files.items():
        (tmp_path / k).write_text(v, encoding="utf-8")
    ast, rep, s = frontend.read(tmp_path / "main.tex", Config())
    d = ir.build(ast, rep, s, Config())
    data = backend.render(d)
    assert check(data) == []
    return d, data, rep


def doc(body, pre=""):
    return "\\documentclass{article}\n" + pre + "\\begin{document}\n" + body + "\n\\end{document}\n"


def test_cited_keys_and_nocite_make_the_bibliography(real_pandoc, tmp_path):
    tex = doc("See \\cite{t1} and \\cite{a2,nope}.\n\\nocite{m1}\n\\bibliographystyle{unsrt}\n\\bibliography{refs}")
    d, data, rep = build(tmp_path, tex, {"refs.bib": BIB})
    assert shown(data) == [
        "See [1] and [2, ?].", "References",
        "[1] Ivy Jay. Deep Thoughts. PhD thesis, MIT, 2015.",
        "[2] Ann Zed. Second paper. J, page 7, 1999.",
        "[3] Em En. Web page. Online, 2022. https://example.org/m",
    ]
    assert [c.numbers for c in walk(d) if isinstance(c, Citation)] == [["1"], ["2", "?"]]
    assert [f for f in fields(data) if f[0].startswith("REF")] == [("REF bib_t1 \\h \\* CHARFORMAT", "1"), ("REF bib_a2 \\h \\* CHARFORMAT", "2")]
    assert [(x.element, x.message) for x in rep.diags if x.level == "warning"] == [
        ("\\cite{nope}", "citation key not found in the bibliography")]


def test_biblatex_sorts_by_name_and_keeps_title_case(real_pandoc, tmp_path):
    tex = doc("\\cite{a2} \\cite{b1}\n\\printbibliography", "\\usepackage{biblatex}\n\\addbibresource{refs.bib}\n")
    d, data, rep = build(tmp_path, tex, {"refs.bib": BIB})
    assert shown(data)[2:] == [
        "[1] Ann Zed, Bob Young, and World Health Organization. A Book. Big Press, third edition, 2001.",
        "[2] Ann Zed. Second Paper. J, page 7, 1999.",
    ]
    tex = doc("\\cite{a2} \\cite{b1}\n\\printbibliography", "\\usepackage[sorting=none]{biblatex}\n\\addbibresource{refs.bib}\n")
    d, data, rep = build(tmp_path, tex, {"refs.bib": BIB})
    assert shown(data)[0] == "[1] [2]"


def test_missing_or_unsafe_bib_files_are_reported(real_pandoc, tmp_path):
    (tmp_path / "doc").mkdir()
    tex = doc("\\cite{a}\n\\bibliography{gone,../outside}")
    d, data, rep = build(tmp_path / "doc", tex, {})
    got = [(x.element, x.message) for x in rep.diags if x.level == "warning"]
    assert ("\\bibliography{gone}", "bibliography not read: file not found") in got
    assert any(e == "\\bibliography{../outside}" and m.startswith("bibliography not read:") for e, m in got)
    assert ("\\cite{a}", "no bibliography found; the citation shows its key") in got
    assert shown(data) == ["[a]"]
