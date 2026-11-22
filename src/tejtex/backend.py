import io

from docx import Document

from . import ir


def write(doc, out):
    d = Document()
    for line in ir.lines(doc):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    out.write_bytes(buf.getvalue())
