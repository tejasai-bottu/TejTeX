from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Twips

from ..errors import Exit, TejtexError
from ..ir.nodes import (
    Anchor, BibEntry, Bibliography, Break, Cell, Citation, CodeBlock, Container, CrossReference, Document,
    Figure, Footnote, Heading, Hyperlink, Image, List, ListItem, Math, Meta, Paragraph, Placeholder, Quote,
    Row, Rule, Table, TextRun, Theorem, block_lines, text, walk,
)
from .check import check
from .media import Media
from .numbering import build, left
from .package import clean, new, save
from .styles import ensure
from .tables import ends_with_table, finish, grid


def numbered(b):
    return bool(b.number and b.caption and isinstance(b.caption[0], Paragraph))


class Writer:
    def __init__(self, doc):
        self.doc = doc
        m = doc.meta
        self.d = new(text(m.title), "; ".join(text(a) for a in m.authors))
        self.st = ensure(self.d, doc.ctx.styles)
        self.ids = build(self.d, doc.ctx.numbering)
        self.media = Media(self.d, doc.ctx.rels.rels)
        for r in doc.ctx.rels.rels:
            if r.kind == "hyperlink":
                self.d.part.rels.add_relationship(RT.HYPERLINK, r.target, r.id, True)
        self.box = self.d
        self.pending = []
        self.indent = None
        self.bid = 0
        self.inlink = False

    def para(self, s="", style=None):
        p = self.box.add_paragraph(style=self.st[style] if style else None)
        f = p.paragraph_format
        todo, self.pending = self.pending, []
        for kind, a, b in todo:
            if kind == "num":
                pr = p._p.get_or_add_pPr().get_or_add_numPr()
                pr.get_or_add_ilvl().val = b
                pr.get_or_add_numId().val = a
            elif kind == "term":
                f.left_indent = Twips(left(b))
                f.first_line_indent = Twips(-720)
                n = len(p.runs)
                self.inlines(p, a)
                for r in p.runs[n:]:
                    r.font.bold = True
                p.add_run(" ")
            elif kind == "thm":
                k = self.start(p, a.bookmark)
                p.add_run(a.name + (f" {a.number}" if a.number else "")).bold = True
                self.end(p, k)
                if a.title:
                    p.add_run(" (")
                    self.inlines(p, a.title)
                    p.add_run(")")
                p.add_run(".").bold = True
                p.add_run(" ")
            elif kind == "lead":
                p.add_run(a)
            elif kind == "mark":
                self.end(p, self.start(p, a))
        if self.indent and not any(k in ("num", "term") for k, _, _ in todo):
            f.left_indent = Twips(self.indent)
        if s:
            p.add_run(clean(s))
        return p

    def flush(self, style=None):
        if any(k != "mark" for k, _, _ in self.pending):
            self.para("", style)

    def start(self, p, name):
        if not name:
            return None
        self.bid += 1
        e = OxmlElement("w:bookmarkStart")
        e.set(qn("w:id"), str(self.bid))
        e.set(qn("w:name"), name)
        p._p.append(e)
        return self.bid

    def end(self, p, k):
        if k is not None:
            e = OxmlElement("w:bookmarkEnd")
            e.set(qn("w:id"), str(k))
            p._p.append(e)

    def link(self, p, items, attr, val, style=None):
        if self.inlink:
            self.inlines(p, items)
            return
        n = len(p._p)
        self.inlink = True
        self.inlines(p, items)
        self.inlink = False
        h = OxmlElement("w:hyperlink")
        h.set(qn(attr), val)
        if attr == "r:id":
            h.set(qn("w:history"), "1")
        for e in list(p._p)[n:]:
            h.append(e)
        p._p.append(h)
        if style:
            for r in h.iter(qn("w:r")):
                rp = r.get_or_add_rPr()
                if rp.style is None:
                    rp.style = style

    def block(self, b):
        if type(b) not in BLOCKS:
            raise TejtexError(f"the backend has no handler for {type(b).__name__}", Exit.INTERNAL)
        f = BLOCKS[type(b)]
        if f:
            f(self, b)
            return
        for s in block_lines(b):
            self.para(s)

    def paragraph(self, b):
        p = self.para("", b.style)
        self.inlines(p, b.inlines)

    def items(self, b):
        self.flush("Compact")
        old = self.indent
        for it in b.items:
            if b.kind == "description":
                self.pending.append(("term", it.term, b.level))
            else:
                self.pending.append(("num", self.ids[it.num or b.num], b.level))
            self.indent = left(b.level)
            for x in it.blocks:
                self.block(x)
            self.flush("Compact")
        self.indent = old

    def caption(self, b, above=False):
        for i, x in enumerate(b.caption):
            if i == 0 and numbered(b):
                p = self.para("", x.style)
                k = self.start(p, b.bookmark)
                p.add_run(f"{b.name} {b.number}: ")
                self.inlines(p, x.inlines)
                self.end(p, k)
                if above:
                    p.paragraph_format.keep_with_next = True
            else:
                self.block(x)

    def table(self, b):
        self.caption(b, True)
        self.flush("Compact")
        if b.bookmark and not numbered(b):
            self.pending.append(("mark", b.bookmark, None))
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
        if b.bookmark and not numbered(b):
            self.pending.append(("mark", b.bookmark, None))
        for x in b.blocks:
            self.block(x)
        self.caption(b)

    def theorem(self, b):
        self.pending.append(("thm", b, None))
        for x in b.blocks:
            self.block(x)
        self.flush()

    def container(self, b):
        if b.bookmark:
            self.pending.append(("mark", b.bookmark, None))
        for x in b.blocks:
            self.block(x)

    def quote(self, b):
        for x in b.blocks:
            self.block(x)

    def code(self, b):
        self.para(b.text, b.style)

    def bibliography(self, b):
        for e in b.entries:
            p = self.para("", "Bibliography")
            k = self.start(p, e.bookmark)
            if e.number:
                p.add_run(f"[{e.number}]")
            self.end(p, k)
            if e.number:
                p.add_run(" ")
            self.inlines(p, e.inlines)

    def heading(self, b):
        p = self.para("", b.style)
        k = self.start(p, b.bookmark)
        if b.number:
            p.add_run(b.number + "\t")
        self.inlines(p, b.inlines)
        self.end(p, k)

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

    def math(self, p, x):
        p.add_run(clean(x.tex.strip()))
        for num, bm, _ in x.numbers:
            p.add_run(" ")
            k = self.start(p, bm)
            p.add_run(f"({num})")
            self.end(p, k)

    def xref(self, p, x):
        if x.bookmark:
            self.link(p, [TextRun(x.text)], "w:anchor", x.bookmark)
        else:
            p.add_run(clean(x.text))

    def cite(self, p, x):
        bm = next((b for b in x.bookmarks if b), None)
        if bm:
            self.link(p, [TextRun(x.text)], "w:anchor", bm)
        else:
            p.add_run(clean(x.text))

    def hyperlink(self, p, x):
        if x.bookmark:
            self.link(p, x.inlines, "w:anchor", x.bookmark)
        elif x.rel:
            self.link(p, x.inlines, "r:id", x.rel, "Hyperlink")
        else:
            self.inlines(p, x.inlines)

    def anchor(self, p, x):
        self.end(p, self.start(p, x.bookmark))

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

    def notes(self):
        for n in walk(self.doc):
            if isinstance(n, Footnote):
                self.pending.append(("lead", f"[{n.number}] ", None))
                for b in n.blocks:
                    self.block(b)
                self.flush()

    def run(self):
        self.meta()
        for b in self.doc.blocks:
            self.block(b)
        self.notes()
        if self.pending:
            self.para()
        return save(self.d)


BLOCKS = {
    Paragraph: Writer.paragraph, Heading: Writer.heading, List: Writer.items, Table: Writer.table, Figure: Writer.figure,
    Theorem: Writer.theorem, Bibliography: Writer.bibliography, Quote: Writer.quote, Container: Writer.container,
    CodeBlock: Writer.code, Rule: None, Placeholder: Writer.notice,
}
INLINES = {
    TextRun: Writer.textrun, Break: Writer.brk, Placeholder: Writer.placeholder, Math: Writer.math, Citation: Writer.cite,
    CrossReference: Writer.xref, Hyperlink: Writer.hyperlink, Image: Writer.image, Footnote: None, Anchor: Writer.anchor,
}
PARTS = {Document, Meta, ListItem, Row, Cell, BibEntry}


def render(doc):
    data = Writer(doc).run()
    bad = check(data)
    if bad:
        raise TejtexError("the generated DOCX package is invalid: " + bad[0], Exit.INTERNAL)
    return data
