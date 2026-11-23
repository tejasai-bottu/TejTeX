import hashlib
import io
import shutil
import zipfile
from pathlib import Path

from helpers import W, fields, labels, links, marks, part, words
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.cli import main
from tejtex.config import Config
from tejtex.errors import Exit

DATA = Path(__file__).parent / "data"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def full():
    ast, rep, s = frontend.read(DATA / "full" / "main.tex", Config())
    return backend.render(ir.build(ast, rep, s, Config())), rep


def styles_of(data):
    out = []
    for p in part(data).find(W + "body").iter(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        out.append((st.get(W + "val") if st is not None else None, words(p)))
    return out


def test_full_document_is_valid(real_pandoc):
    data, rep = full()
    assert check(data) == []


def test_headings_lists_and_formatting(real_pandoc):
    data, rep = full()
    heads = [x for (s, _), x in zip(styles_of(data), labels(data)) if s == "Heading1"]
    assert heads == [
        ("1", "Introduction"), ("2", "Lists"), ("3", "Tables"), ("4", "Figures"), ("5", "Mathematics"),
        ("6", "Unsupported content"), ("7", "Results"), (None, "References"),
    ]
    assert [x for (s, _), x in zip(styles_of(data), labels(data)) if x[0] and s != "Heading1"] == [
        ("1.", "First step."), ("2.", "Second step with a nested list:"), ("(a)", "Inner step."), ("•", "A bullet inside."),
        ("i.", "Deep step. "), ("(x)", "Custom label."), ("3.", "Third step."), ("(a)", "Restarted list in another format."),
        ("•", "listed"), ("•", "in a cell"),
    ]
    props = {}
    for r in part(data).iter(W + "r"):
        rp = r.find(W + "rPr")
        props["".join(t.text for t in r.iter(W + "t"))] = {c.tag.replace(W, "") for c in rp} if rp is not None else set()
    assert props["bold"] == {"b"} and props["emphasis with "] == {"i"} and props["nested"] == set()
    assert props["underlined"] == {"u"} and props["Small Caps"] == {"smallCaps"} and props["code"] == {"rStyle"}


def test_tables_with_merges_lists_and_images(real_pandoc):
    data, rep = full()
    tbls = list(part(data).find(W + "body").iter(W + "tbl"))
    assert len(tbls) == 2
    first, long = tbls
    assert len(list(first.iter(W + "gridSpan"))) == 1
    assert [v.get(W + "val") for v in first.iter(W + "vMerge")] == ["restart", None]
    cells = first.findall(f"{W}tr/{W}tc")
    assert any(c.find(f".//{W}numPr") is not None for c in cells)
    assert any(c.find(f".//{W}drawing") is not None for c in cells)
    assert len(long.findall(W + "tr")) == 61
    assert long.find(f"{W}tr/{W}trPr/{W}tblHeader") is not None


def test_images_are_reused(real_pandoc):
    data, rep = full()
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert [n for n in names if n.startswith("word/media/")] == ["word/media/image1.jpg", "word/media/image2.png"]
    blips = [b.get(R + "embed") for b in part(data).iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip")]
    assert blips == ["rTej3", "rTej4", "rTej4", "rTej4"]


def test_captions_bookmarks_and_links(real_pandoc):
    data, rep = full()
    caps = [t for s, t in styles_of(data) if s == "Caption"]
    assert caps == ["Table 1: Scores with merged cells", "Figure 1: A chart", "Figure 2: A vector diagram"]
    assert list(marks(data)) == [
        "sec_intro", "sec_lists", "it_deep", "sec_tables", "tab_scores", "sec_figures", "fig_chart", "sec_math",
        "eq_euler", "eq_first", "eq_second", "thm_main", "sec_unsupported", "sec_results", "bib_knuth", "fn_note",
    ]
    assert [f for f in fields(data) if f[0].startswith("REF")] == [
        ("REF sec_results \\w \\h \\* CHARFORMAT", "7"), ("REF fig_chart \\h \\* CHARFORMAT", "1"), ("REF tab_scores \\h \\* CHARFORMAT", "1"), ("REF eq_euler \\h \\* CHARFORMAT", "1"),
        ("REF thm_main \\h \\* CHARFORMAT", "1"), ("REF sec_intro \\w \\h \\* CHARFORMAT", "1"), ("REF sec_lists \\w \\h \\* CHARFORMAT", "2"), ("REF fig_chart \\h \\* CHARFORMAT", "1"),
        ("REF tab_scores \\h \\* CHARFORMAT", "1"), ("REF eq_first \\h \\* CHARFORMAT", "2"), ("REF eq_second \\h \\* CHARFORMAT", "3"), ("REF thm_main \\h \\* CHARFORMAT", "1"),
        ("REF bib_knuth \\h \\* CHARFORMAT", "1"),
    ]
    assert links(data) == [
        ("it_deep", "2(a)i"), ("rTej1", "https://example.org/tejtex"), ("rTej2", "CTAN"), ("fn_note", "1"),
        ("sec_tables", "the tables section"),
    ]


def test_unsupported_content_stays_visible(real_pandoc):
    data, rep = full()
    text = "\n".join(t for _, t in styles_of(data))
    for s in ["[TejTeX: tikzpicture needs rendering]", "[TejTeX: \\unknowncmd is not supported]",
              "[image: figs/diagram.pdf]", "do not click", "An undefined reference: ??."]:
        assert s in text
    got = {(x.element, x.category) for x in rep.diags if x.level == "warning"}
    assert got == {
        ("tikzpicture", "render"), ("\\unknowncmd", "unsupported"), ("thebibliography", "partial"),
        ("\\href{javascript:alert(1)}", "partial"), ("\\includegraphics{figs/diagram.pdf}", "render"), ("\\ref{sec:missing}", ""),
    }
    assert all(x.loc.startswith("main.tex:") for x in rep.diags if x.level == "warning")


def test_output_is_deterministic(real_pandoc, tmp_path):
    a, _ = full()
    b, _ = full()
    assert a == b
    shutil.copytree(DATA / "full", tmp_path / "full")
    src = tmp_path / "full" / "main.tex"
    assert main(["compile", str(src), "-o", str(tmp_path / "a.docx"), "-q"]) == Exit.OK
    assert main(["compile", str(src), "-o", str(tmp_path / "b.docx"), "-q"]) == Exit.OK
    assert (tmp_path / "a.docx").read_bytes() == (tmp_path / "b.docx").read_bytes() == a


def tree(d):
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}


def test_compiling_leaves_the_latex_sources_alone(real_pandoc, tmp_path):
    shutil.copytree(DATA / "full", tmp_path / "full")
    before = tree(tmp_path / "full")
    assert main(["compile", str(tmp_path / "full" / "main.tex"), "-q"]) == Exit.OK
    after = tree(tmp_path / "full")
    assert set(after) - set(before) == {"main.docx"}
    assert {k: after[k] for k in before} == before
