import time
import zipfile

import docx

from tejtex import backend
from tejtex.ir.nodes import Document, Heading, Meta, Paragraph, TextRun


def parts(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def doc(*texts):
    return Document(Meta(), [Paragraph("BodyText", [TextRun(t)]) for t in texts])


def test_write(tmp_path):
    out = tmp_path / "a.docx"
    d = doc("one", "two")
    d.blocks.insert(0, Heading(1, [TextRun("Head")], "Heading1", "1"))
    backend.write(d, out)
    assert [p.text for p in docx.Document(str(out)).paragraphs] == ["1 Head", "one", "two"]


def test_same_input_same_xml(tmp_path):
    backend.write(doc("same"), tmp_path / "a.docx")
    time.sleep(1.1)
    backend.write(doc("same"), tmp_path / "b.docx")
    assert parts(tmp_path / "a.docx") == parts(tmp_path / "b.docx")
