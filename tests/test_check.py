import io
import zipfile

from tejtex import backend
from tejtex.backend.check import check
from tejtex.ir.nodes import Document, Meta, Paragraph, TextRun

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def good():
    return backend.render(Document(Meta(), [Paragraph("BodyText", [TextRun("x")])]))


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
