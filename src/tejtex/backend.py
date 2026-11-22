import io

from docx import Document


def write(doc, out):
    d = Document()
    for b in doc.blocks:
        d.add_paragraph(b.text)
    buf = io.BytesIO()
    d.save(buf)
    out.write_bytes(buf.getvalue())
