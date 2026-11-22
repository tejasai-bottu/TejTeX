import time
import zipfile

import docx

from tejtex import backend
from tejtex.ir import Doc, Para


def parts(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_write(tmp_path):
    out = tmp_path / "a.docx"
    backend.write(Doc([Para("one"), Para("two")]), out)
    assert [p.text for p in docx.Document(str(out)).paragraphs] == ["one", "two"]


def test_same_input_same_xml(tmp_path):
    doc = Doc([Para("same")])
    backend.write(doc, tmp_path / "a.docx")
    time.sleep(1.1)
    backend.write(doc, tmp_path / "b.docx")
    assert parts(tmp_path / "a.docx") == parts(tmp_path / "b.docx")
