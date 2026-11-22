from .writer import render


def write(doc, out):
    out.write_bytes(render(doc))
