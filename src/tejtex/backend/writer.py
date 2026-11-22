import re

from ..errors import Exit, TejtexError
from ..ir.nodes import (
    Anchor, BibEntry, Bibliography, Break, Cell, Citation, CodeBlock, Container, CrossReference, Document,
    Figure, Footnote, Heading, Hyperlink, Image, List, ListItem, Math, Meta, Paragraph, Placeholder, Quote,
    Row, Rule, Table, TextRun, Theorem, block_lines, note_lines, text,
)
from .check import check
from .package import new, save
from .styles import ensure

BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


def clean(s):
    return BAD.sub("", s)


def inner(b):
    if isinstance(b, (Quote, Container, Theorem)):
        return b.blocks
    if isinstance(b, Figure):
        return b.blocks + b.caption
    if isinstance(b, Table):
        return b.caption + [x for r in b.rows for c in r.cells for x in c.blocks]
    if isinstance(b, List):
        out = []
        for it in b.items:
            if it.term:
                out.append(Paragraph("Compact", it.term))
            out += it.blocks
        return out
    return None


class Writer:
    def __init__(self, doc):
        self.doc = doc
        m = doc.meta
        self.d = new(text(m.title), "; ".join(text(a) for a in m.authors))
        self.st = ensure(self.d, doc.ctx.styles)

    def para(self, s, style=None):
        return self.d.add_paragraph(clean(s), style=self.st[style] if style else None)

    def block(self, b):
        if type(b) not in BLOCKS:
            raise TejtexError(f"the backend has no handler for {type(b).__name__}", Exit.INTERNAL)
        f = BLOCKS[type(b)]
        if f:
            f(self, b)
            return
        kids = inner(b)
        if kids is None:
            for s in block_lines(b):
                self.para(s)
            return
        if isinstance(b, Theorem):
            head = b.name + (f" {b.number}" if b.number else "")
            if b.title:
                head += f" ({text(b.title)})"
            self.para(head + ".")
        for k in kids:
            self.block(k)

    def paragraph(self, b):
        p = self.para("", b.style)
        self.inlines(p, b.inlines)

    def heading(self, b):
        p = self.para("", b.style)
        if b.number:
            p.add_run(b.number + "\t")
        self.inlines(p, b.inlines)

    def inlines(self, p, items):
        for x in items:
            if type(x) not in INLINES:
                raise TejtexError(f"the backend has no handler for {type(x).__name__}", Exit.INTERNAL)
            f = INLINES[type(x)]
            if f:
                f(self, p, x)
            else:
                s = clean(text([x]))
                if s:
                    p.add_run(s)

    def notice(self, b):
        self.para(b.text, "Placeholder")

    def textrun(self, p, x):
        r = p.add_run(clean(x.text))
        f = r.font
        if x.bold:
            f.bold = True
        if x.italic:
            f.italic = True
        if x.underline:
            f.underline = True
        if x.strike:
            f.strike = True
        if x.sup:
            f.superscript = True
        if x.sub:
            f.subscript = True
        if x.smallcaps:
            f.small_caps = True
        if x.code:
            r.style = self.st["VerbatimChar"]

    def brk(self, p, x):
        p.add_run().add_break()

    def placeholder(self, p, x):
        r = p.add_run(clean(x.text))
        r.style = self.st["PlaceholderChar"]

    def line(self, style, items):
        p = self.para("", style)
        self.inlines(p, items)

    def meta(self):
        m = self.doc.meta
        if m.title:
            self.line("Title", m.title)
        for a in m.authors:
            self.line("Author", a)
        if m.date:
            self.line("Date", m.date)
        for b in m.abstract:
            self.block(b)

    def run(self):
        self.meta()
        for b in self.doc.blocks:
            self.block(b)
        for s in note_lines(self.doc):
            self.para(s)
        return save(self.d)


BLOCKS = {
    Paragraph: Writer.paragraph, Heading: Writer.heading, List: None, Table: None, Figure: None, Theorem: None,
    Bibliography: None, Quote: None, Container: None, CodeBlock: None, Rule: None, Placeholder: Writer.notice,
}
INLINES = {
    TextRun: Writer.textrun, Break: Writer.brk, Placeholder: Writer.placeholder, Math: None, Citation: None,
    CrossReference: None, Hyperlink: None, Image: None, Footnote: None, Anchor: None,
}
PARTS = {Document, Meta, ListItem, Row, Cell, BibEntry}


def render(doc):
    data = Writer(doc).run()
    bad = check(data)
    if bad:
        raise TejtexError("the generated DOCX package is invalid: " + bad[0], Exit.INTERNAL)
    return data
