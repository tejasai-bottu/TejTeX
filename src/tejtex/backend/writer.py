from ..errors import Exit, TejtexError
from ..ir.nodes import (
    Anchor, BibEntry, Bibliography, Break, Cell, Citation, CodeBlock, Container, CrossReference, Document,
    Figure, Footnote, Heading, Hyperlink, Image, List, ListItem, Math, Meta, Paragraph, Placeholder, Quote,
    Row, Rule, Table, TextRun, Theorem, block_lines, meta_lines, note_lines, text,
)
from .check import check
from .package import new, save

BLOCKS = {
    Paragraph: None, Heading: None, List: None, Table: None, Figure: None, Theorem: None,
    Bibliography: None, Quote: None, Container: None, CodeBlock: None, Rule: None, Placeholder: None,
}
INLINES = {
    TextRun: None, Break: None, Math: None, Citation: None, CrossReference: None, Hyperlink: None,
    Image: None, Footnote: None, Anchor: None, Placeholder: None,
}
PARTS = {Document, Meta, ListItem, Row, Cell, BibEntry}


class Writer:
    def __init__(self, doc):
        self.doc = doc
        m = doc.meta
        self.d = new(text(m.title), "; ".join(text(a) for a in m.authors))

    def para(self, s):
        self.d.add_paragraph(s)

    def block(self, b):
        if type(b) not in BLOCKS:
            raise TejtexError(f"the backend has no handler for {type(b).__name__}", Exit.INTERNAL)
        f = BLOCKS[type(b)]
        if f:
            f(self, b)
        else:
            for s in block_lines(b):
                self.para(s)

    def run(self):
        for s in meta_lines(self.doc):
            self.para(s)
        for b in self.doc.blocks:
            self.block(b)
        for s in note_lines(self.doc):
            self.para(s)
        return save(self.d)


def render(doc):
    data = Writer(doc).run()
    bad = check(data)
    if bad:
        raise TejtexError("the generated DOCX package is invalid: " + bad[0], Exit.INTERNAL)
    return data
