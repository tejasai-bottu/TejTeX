import io
import zipfile
from pathlib import Path

from helpers import W, make, part, png
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.backend.media import length
from tejtex.config import Config
from tejtex.ir.nodes import Cell, Figure, Image, List, ListItem, Paragraph, Row, Table, TextRun

DATA = Path(__file__).parent / "data"
IN = 914400


def doc(tmp_path, blocks, files):
    d = make(blocks)
    for name, data in files.items():
        f = tmp_path / name
        f.write_bytes(data)
        d.ctx.rels.image(f, f.suffix)
    return d


def img(rel, **kw):
    return Image("x", rel, None, **kw)


def para(*xs):
    return Paragraph("BodyText", list(xs))


def names(data):
    return zipfile.ZipFile(io.BytesIO(data)).namelist()


def extents(data):
    return [(int(e.get("cx")), int(e.get("cy"))) for e in part(data).iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")]


def embeds(data):
    a = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    return [b.get(a) for b in part(data).iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip")]


def test_length():
    w, h = 6 * IN, 9 * IN
    assert length("50%", w, h) == 3 * IN
    assert length("3cm", w, h) == 1080000
    assert length("1in", w, h) == IN
    assert length("72bp", w, h) == IN
    assert length("\\linewidth", w, h) == w
    assert length(".3\\columnwidth", w, h) == int(w * 0.3)
    assert length("0.5\\textheight", w, h) == int(h * 0.5)
    assert length("2\\foo", w, h) is None
    assert length(None, w, h) is None


def test_images_are_embedded_once(tmp_path):
    blocks = [para(img("rTej1", width="50%"), img("rTej2"), img("rTej1", height="1in", alt="A plot"))]
    d = doc(tmp_path, blocks, {"a.png": png(240, 120, 96), "b.png": png(60, 30, 72)})
    data = backend.render(d)
    assert check(data) == []
    assert [n for n in names(data) if n.startswith("word/media/")] == ["word/media/image1.png", "word/media/image2.png"]
    assert embeds(data) == ["rTej1", "rTej2", "rTej1"]
    assert extents(data) == [(3 * IN, int(1.5 * IN)), (int(60 / 72 * IN), int(30 / 72 * IN)), (2 * IN, IN)]
    pr = list(part(data).iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"))
    assert [x.get("id") for x in pr] == ["1", "2", "3"]
    assert [x.get("descr") for x in pr] == [None, None, "A plot"]
    rels = part(data, "word/_rels/document.xml.rels")
    assert {r.get("Id"): r.get("Target") for r in rels if "image" in r.get("Type")} == {"rTej1": "media/image1.png", "rTej2": "media/image2.png"}


def test_large_images_fit_the_text_width(tmp_path):
    d = doc(tmp_path, [para(img("rTej1"))], {"big.png": png(1200, 600, 72)})
    cx, cy = extents(backend.render(d))[0]
    assert cx == 6 * IN and cy == 3 * IN


def test_missing_and_broken_images_stay_visible(tmp_path):
    d = doc(tmp_path, [para(Image("gone.png"), img("rTej1"))], {"bad.png": b"\x89PNG\r\n\x1a\nbroken"})
    d.ctx.styles.use("PlaceholderChar")
    data = backend.render(d)
    assert check(data) == []
    assert not [n for n in names(data) if n.startswith("word/media/")]
    runs = [("".join(t.text for t in r.iter(W + "t")), r.find(f"{W}rPr/{W}rStyle").get(W + "val")) for r in part(data).iter(W + "r")]
    assert runs == [("[image: gone.png]", "PlaceholderChar"), ("[image: x]", "PlaceholderChar")]


def test_figure_caption_goes_below(tmp_path):
    fig = Figure([Paragraph("Figure", [img("rTej1")])], [Paragraph("Caption", [TextRun("A plot")])], "2")
    d = doc(tmp_path, [fig], {"a.png": png(10, 10)})
    ps = list(part(backend.render(d)).iter(W + "p"))
    assert [x.find(f"{W}pPr/{W}pStyle").get(W + "val") for x in ps] == ["Figure", "Caption"]
    assert "".join(t.text for t in ps[1].iter(W + "t")) == "Figure 2: A plot"
    assert ps[0].find(f".//{W}drawing") is not None


def test_images_in_tables_in_lists(tmp_path):
    cell = Cell([Paragraph("Compact", [TextRun("pic "), img("rTej1", width="1cm")])])
    tab = Table([Row([Cell([Paragraph("Compact", [TextRun("a")])]), cell])], [None, None], caption=[Paragraph("Caption", [TextRun("Both")])], number="1")
    lst = List("ordered", [ListItem([tab]), ListItem([Paragraph("Compact", [TextRun("next")])])])
    d = doc(tmp_path, [lst], {"a.png": png(20, 20)})
    data = backend.render(d)
    assert check(data) == []
    kids = list(part(data).find(W + "body"))
    assert [k.tag.replace(W, "") for k in kids] == ["p", "tbl", "p", "sectPr"]
    assert kids[0].find(f"{W}pPr/{W}numPr") is not None and "".join(t.text for t in kids[0].iter(W + "t")) == "Table 1: Both"
    tc = kids[1].findall(f"{W}tr/{W}tc")[1]
    assert tc.find(f".//{W}drawing") is not None and tc.find(f".//{W}numPr") is None
    assert extents(data) == [(360000, 360000)]
    assert kids[2].find(f"{W}pPr/{W}numPr") is not None


def test_media_corpus(real_pandoc):
    ast, rep, s = frontend.read(DATA / "media" / "main.tex", Config())
    d = ir.build(ast, rep, s, Config())
    data = backend.render(d)
    assert check(data) == []
    assert [n for n in names(data) if n.startswith("word/media/")] == ["word/media/image1.png", "word/media/image2.jpg"]
    assert embeds(data) == ["rTej1", "rTej2", "rTej1", "rTej2", "rTej1", "rTej2"]
    assert extents(data) == [
        (3 * IN, int(1.5 * IN)), (1080000, 1080000), (2 * IN, IN), (6 * IN, 6 * IN), (int(2.5 * IN), int(1.25 * IN)), (360000, 360000),
    ]
    diags = {(x.element, x.category, x.loc) for x in rep.diags}
    assert ("\\includegraphics{figs/vector.pdf}", "render", "main.tex:22:18") in diags
    assert ("\\includegraphics{figs/missing.png}", "", "main.tex:26:18") in diags
    texts = ["".join(t.text for t in x.iter(W + "t")) for x in part(data).iter(W + "p")]
    for t in ["Figure 1: A wide image", "Figure 2: Two images, one reused", "Figure 3: Vector figure",
              "[image: figs/vector.pdf]", "[image: figs/missing.png]", "See Figures 1 and 2."]:
        assert t in texts
