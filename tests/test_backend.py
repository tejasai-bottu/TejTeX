import ast
import dataclasses
import io
import time
import zipfile
from pathlib import Path

import docx
import pytest

from tejtex import backend
from tejtex.backend import writer
from tejtex.errors import Exit, TejtexError
from tejtex.ir import nodes
from tejtex.ir.nodes import Document, Footnote, Heading, Image, Meta, Paragraph, TextRun

SRC = Path(writer.__file__).parent


def doc(*texts, meta=None):
    return Document(meta or Meta(), [Paragraph("BodyText", [TextRun(t)]) for t in texts])


def texts(data):
    return [p.text for p in docx.Document(io.BytesIO(data)).paragraphs]


def test_write(tmp_path):
    out = tmp_path / "a.docx"
    d = doc("one", "two")
    d.blocks.insert(0, Heading(1, [TextRun("Head")], "Heading1", "1"))
    backend.write(d, out)
    assert [p.text for p in docx.Document(str(out)).paragraphs] == ["1 Head", "one", "two"]


def test_output_is_byte_identical():
    a = backend.render(doc("same"))
    time.sleep(1.1)
    assert backend.render(doc("same")) == a
    z = zipfile.ZipFile(io.BytesIO(a))
    assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    assert z.namelist()[0] == "[Content_Types].xml"


def test_package_is_clean():
    meta = Meta(title=[TextRun("My Title")], authors=[[TextRun("Ann")], [TextRun("Bob")]])
    z = zipfile.ZipFile(io.BytesIO(backend.render(doc("x", meta=meta))))
    names = z.namelist()
    assert not [n for n in names if "thumbnail" in n or "customXml" in n or "stylesWithEffects" in n]
    core = z.read("docProps/core.xml").decode()
    assert "<dc:title>My Title</dc:title>" in core
    assert "<dc:creator>Ann; Bob</dc:creator>" in core
    assert "created" not in core and "modified" not in core
    assert "python-docx" not in core
    assert "<Application>TejTeX</Application>" in z.read("docProps/app.xml").decode()


def test_meta_and_footnotes_are_not_dropped():
    meta = Meta(title=[TextRun("T")], authors=[[TextRun("A")]], date=[TextRun("2026")], abstract=[Paragraph("Abstract", [TextRun("Abs.")])])
    d = doc("x", meta=meta)
    d.blocks[0].inlines += [Footnote("1", [Paragraph("FootnoteText", [TextRun("Note.")])]), Image("f.png")]
    assert texts(backend.render(d)) == ["T", "A", "2026", "Abs.", "x[1][image: f.png]", "[1] Note."]


def test_every_ir_node_type_is_routed():
    classes = {c for c in vars(nodes).values() if isinstance(c, type) and dataclasses.is_dataclass(c)}
    routed = set(writer.BLOCKS) | set(writer.INLINES) | writer.PARTS
    assert classes - routed == set()


def test_unknown_block_is_an_internal_error():
    d = doc("x")
    d.blocks.append(object())
    with pytest.raises(TejtexError) as e:
        backend.render(d)
    assert e.value.code == Exit.INTERNAL


def test_invalid_package_is_never_written(tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "check", lambda data: ["broken"])
    out = tmp_path / "a.docx"
    with pytest.raises(TejtexError) as e:
        backend.write(doc("x"), out)
    assert e.value.code == Exit.INTERNAL
    assert not out.exists()


def test_backend_imports_only_the_model():
    allowed = {"tejtex.errors", "tejtex.ir.nodes", "tejtex.backend.check", "tejtex.backend.package", "tejtex.backend.writer"}
    for f in SRC.glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.ImportFrom) and n.level:
                parts = ["tejtex", "backend"][: 2 - (n.level - 1)]
                name = ".".join(parts + ([n.module] if n.module else []))
                assert name in allowed, f"{f.name} imports {name}"
            elif isinstance(n, (ast.Import, ast.ImportFrom)) and not getattr(n, "level", 0):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module]
                assert not any(m.startswith("tejtex") for m in mods), f"{f.name} imports {mods}"
