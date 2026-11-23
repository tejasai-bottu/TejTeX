import io
import zipfile

from helpers import make, png
from tejtex import backend
from tejtex.backend.check import check
from tejtex.ir.nodes import Cell, Hyperlink, Image, Paragraph, Row, Table, TextRun

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def good():
    return backend.render(make([Paragraph("BodyText", [TextRun("x")])]))


def change(data, edits=None, drop=(), add=None):
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n in src.namelist():
            if n in drop:
                continue
            b = src.read(n)
            for name, old, new in edits or []:
                if name == n:
                    b = b.replace(old, new)
            z.writestr(n, b)
        for n, b in (add or {}).items():
            z.writestr(n, b)
    return out.getvalue()


def body(xml):
    return change(good(), [("word/document.xml", b"<w:body>", b"<w:body>" + xml.encode())])


def test_good_package():
    assert check(good()) == []


def test_not_a_zip():
    assert check(b"hello") == ["not a ZIP package"]


def test_bad_xml_and_missing_content_type():
    out = check(change(good(), add={"word/extra.bin": b"x", "word/broken.xml": b"<a>"}))
    assert "word/extra.bin: no content type" in out
    assert any(p.startswith("word/broken.xml: not well-formed XML") for p in out)


def test_missing_part_and_duplicate_relationship():
    out = check(change(good(), drop=["word/fontTable.xml"]))
    assert "content type declared for missing part /word/fontTable.xml" in out
    assert any("points to missing part word/fontTable.xml" in p for p in out)
    dup = change(good(), [("word/_rels/document.xml.rels", b'Id="rId5"', b'Id="rId3"')])
    assert any("duplicate relationship id rId3" in p for p in check(dup))


def test_dangling_relationship_reference():
    out = check(body(f'<w:p {R}><w:hyperlink r:id="rNope"/></w:p>'))
    assert "word/document.xml: r:id=rNope has no relationship" in out


def test_styles_and_numbering_must_exist():
    out = check(body('<w:p><w:pPr><w:pStyle w:val="Nope"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="999"/></w:numPr></w:pPr></w:p>'))
    assert "word/document.xml: style Nope is not defined" in out
    assert "word/document.xml: numbering 999 is not defined" in out


def test_bookmarks_and_internal_links():
    ok = '<w:p><w:bookmarkStart w:id="0" w:name="fig_a"/><w:bookmarkEnd w:id="0"/><w:hyperlink w:anchor="fig_a"/></w:p>'
    assert check(body(ok)) == []
    bad = ('<w:p><w:bookmarkStart w:id="0" w:name="fig:a"/><w:bookmarkStart w:id="1" w:name="x"/>'
           '<w:bookmarkStart w:id="2" w:name="X"/><w:bookmarkEnd w:id="2"/><w:hyperlink w:anchor="missing"/></w:p>')
    out = check(body(bad))
    assert "word/document.xml: bookmark name 'fig:a' breaks Word's rules" in out
    assert "word/document.xml: bookmark names are not unique" in out
    assert "word/document.xml: bookmark 0 is not paired" in out
    assert "word/document.xml: link to missing bookmark missing" in out


def rich(tmp_path):
    cell = Cell([Paragraph("Compact", [TextRun("c")])])
    blocks = [
        Paragraph("BodyText", [Hyperlink([TextRun("site")], "https://e.org", "rTej1"), Image("a.png", "rTej2")]),
        Table([Row([cell, cell]), Row([cell, cell])], [None, None]),
    ]
    d = make(blocks)
    d.ctx.rels.link("https://e.org")
    (tmp_path / "a.png").write_bytes(png(4, 4))
    d.ctx.rels.image(tmp_path / "a.png", ".png")
    data = backend.render(d)
    assert check(data) == []
    return data


DOCREL = "word/_rels/document.xml.rels"
DOCXML = "word/document.xml"


def test_unsafe_and_mistyped_relationships(tmp_path):
    data = rich(tmp_path)
    out = check(change(data, [(DOCREL, b"https://e.org", b"javascript:alert(1)")]))
    assert "word/_rels/document.xml.rels: rTej1 has an unsafe external target 'javascript:alert(1)'" in out
    out = check(change(data, [(DOCREL, b"https://e.org", b"file:///etc/passwd")]))
    assert any("unsafe external target 'file:///etc/passwd'" in p for p in out)
    out = check(change(data, [(DOCXML, b'r:id="rTej1"', b'r:id="rTej2"')]))
    assert "word/document.xml: hyperlink r:id=rTej2 is not an external hyperlink relationship" in out
    out = check(change(data, [(DOCXML, b'r:embed="rTej2"', b'r:embed="rTej1"')]))
    assert "word/document.xml: picture r:embed=rTej1 is not an image part" in out
    out = check(change(data, drop=["word/media/image1.png"]))
    assert any("points to missing part word/media/image1.png" in p for p in out)


def test_hyperlinks_need_one_target():
    out = check(body('<w:p><w:hyperlink/></w:p>'))
    assert "word/document.xml: a hyperlink needs either r:id or w:anchor" in out
    out = check(body(f'<w:p {R}><w:bookmarkStart w:id="1" w:name="a"/><w:bookmarkEnd w:id="1"/><w:hyperlink w:anchor="a" r:id="rId3"/></w:p>'))
    assert "word/document.xml: a hyperlink needs either r:id or w:anchor" in out


def test_bookmark_names_and_order():
    out = check(body('<w:p><w:bookmarkStart w:id="1" w:name="_hidden"/><w:bookmarkEnd w:id="1"/><w:bookmarkStart w:id="2" w:name="1abc"/><w:bookmarkEnd w:id="2"/></w:p>'))
    assert "word/document.xml: bookmark name '_hidden' breaks Word's rules" in out
    assert "word/document.xml: bookmark name '1abc' breaks Word's rules" in out
    out = check(body('<w:p><w:bookmarkEnd w:id="3"/><w:bookmarkStart w:id="3" w:name="late"/></w:p>'))
    assert "word/document.xml: bookmark 3 ends before it starts" in out


def test_duplicate_identifiers(tmp_path):
    data = rich(tmp_path)
    two = change(data, [(DOCXML, b"</w:body>", b'<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><wp:docPr id="1" name="x"/></wp:inline></w:drawing></w:r></w:p></w:body>')])
    assert "word/document.xml: drawing ids are not unique positive numbers" in check(two)
    out = check(change(data, [("word/styles.xml", b'w:styleId="Title"', b'w:styleId="Normal"')]))
    assert "styles: a style id is defined twice" in out
    out = check(change(data, [("word/styles.xml", b'<w:basedOn w:val="TableGrid"/>', b'<w:basedOn w:val="Nope"/>')]))
    assert "styles: base style Nope is not defined" in out
    out = check(change(data, [("word/numbering.xml", b'<w:num w:numId="2">', b'<w:num w:numId="1">')]))
    assert "numbering: numId values are not unique" in out
    out = check(change(data, [("word/numbering.xml", b'<w:lvl w:ilvl="0"', b'<w:lvl w:ilvl="12"')]))
    assert "numbering: level 12 is out of range" in out


def test_table_structure(tmp_path):
    data = rich(tmp_path)
    tc = b'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="4320"/></w:tcPr><w:p/></w:tc>'
    out = check(change(data, [(DOCXML, b"</w:tr>", tc + b"</w:tr>")]))
    assert "word/document.xml: table 1 row 1 has 3 columns, the grid has 2" in out
    out = check(change(data, [(DOCXML, b'<w:tcW w:type="dxa" w:w="4320"/></w:tcPr>', b'<w:tcW w:type="dxa" w:w="4320"/><w:vMerge/></w:tcPr>')]))
    assert "word/document.xml: table 1 row 1 continues a merge that has no start" in out
    out = check(change(data, [(DOCXML, b"<w:gridCol", b"<w:nogrid")]))
    assert "word/document.xml: table 1 has no grid" in out
    stripped = change(data, [(DOCXML, b'<w:p><w:pPr><w:pStyle w:val="Compact"/></w:pPr><w:r><w:t>c</w:t></w:r></w:p></w:tc>', b'</w:tc>')])
    assert "word/document.xml: table 1 has a cell that does not end with a paragraph" in check(stripped)
