from docx.shared import Twips

from ..errors import Exit, TejtexError
from ..ir.nodes import (
    Anchor, BibEntry, Bibliography, Break, Cell, Citation, CodeBlock, Container, CrossReference, Document,
    Figure, Footnote, Heading, Hyperlink, Image, List, ListItem, Math, Meta, Paragraph, Placeholder, Quote,
    Row, Rule, Table, TextRun, Theorem, block_lines, note_lines, text,
)
from .check import check
from .media import Media
from .numbering import build, left
from .package import clean, new, save
from .styles import ensure
from .tables import ends_with_table, finish, grid


def inner(b):
    if isinstance(b, (Quote, Container, Theorem)):
        return b.blocks
    return None


class Writer:
    def __init__(self, doc):
        self.doc = doc
        m = doc.meta
        self.d = new(text(m.title), "; ".join(text(a) for a in m.authors))
        self.st = ensure(self.d, doc.ctx.styles)
        self.ids = build(self.d, doc.ctx.numbering)
        self.media = Media(self.d, doc.ctx.rels.rels)
        self.box = self.d
        self.pending = None
        self.indent = None

    def para(self, s="", style=None):
        p = self.box.add_paragraph(style=self.st[style] if style else None)
        f = p.paragraph_format
        if self.pending:
            kind, a, b = self.pending
            self.pending = None
            if kind == "num":
                pr = p._p.get_or_add_pPr().get_or_add_numPr()
                pr.get_or_add_ilvl().val = b
                pr.get_or_add_numId().val = a
            else:
                f.left_indent = Twips(left(b))
                f.first_line_indent = Twips(-720)
                self.inlines(p, a)
                for r in p.runs:
                    r.font.bold = True
                p.add_run(" ")
        elif self.indent:
            f.left_indent = Twips(self.indent)
        if s:
            p.add_run(clean(s))
        return p

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

    def items(self, b):
        if self.pending:
            self.para("", "Compact")
        old = self.indent
        for it in b.items:
            if b.kind == "description":
                self.pending = ("term", it.term, b.level)
            else:
                self.pending = ("num", self.ids[it.num or b.num], b.level)
            self.indent = left(b.level)
            for x in it.blocks:
                self.block(x)
            if self.pending:
                self.para("", "Compact")
        self.indent = old

    def caption(self, b, above=False):
        for i, x in enumerate(b.caption):
            if i == 0 and isinstance(x, Paragraph) and b.number:
                p = self.para("", x.style)
                p.add_run(f"{b.name} {b.number}: ")
                self.inlines(p, x.inlines)
                if above:
                    p.paragraph_format.keep_with_next = True
            else:
                self.block(x)

    def table(self, b):
        self.caption(b, True)
        if self.pending:
            self.para("", "Compact")
        if not any(r.cells for r in b.rows):
            return
        if ends_with_table(self.box):
            self.para()
        t, cells = grid(self.box, b)
        t.style = self.st[b.style]
        old = self.box, self.indent
        self.indent = None
        for r, c, rs, cs, cell in cells:
            box = t.cell(r, c)
            first = box.paragraphs[0]._p
            self.box = box
            for x in cell.blocks:
                self.block(x)
            finish(box, first, cell.align or (b.aligns[c] if c < len(b.aligns) else None), rs)
        self.box, self.indent = old

    def figure(self, b):
        for x in b.blocks:
            self.block(x)
        self.caption(b)

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

    def image(self, p, x):
        inline = self.media.inline(x)
        if inline is None:
            r = p.add_run(clean(f"[image: {x.path}]"))
            r.style = self.st.get("PlaceholderChar")
        else:
            p.add_run()._r.add_drawing(inline)

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
    Paragraph: Writer.paragraph, Heading: Writer.heading, List: Writer.items, Table: Writer.table, Figure: Writer.figure, Theorem: None,
    Bibliography: None, Quote: None, Container: None, CodeBlock: None, Rule: None, Placeholder: Writer.notice,
}
INLINES = {
    TextRun: Writer.textrun, Break: Writer.brk, Placeholder: Writer.placeholder, Math: None, Citation: None,
    CrossReference: None, Hyperlink: None, Image: Writer.image, Footnote: None, Anchor: None,
}
PARTS = {Document, Meta, ListItem, Row, Cell, BibEntry}


def render(doc):
    data = Writer(doc).run()
    bad = check(data)
    if bad:
        raise TejtexError("the generated DOCX package is invalid: " + bad[0], Exit.INTERNAL)
    return data
