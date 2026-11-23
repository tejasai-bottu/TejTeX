from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Twips

ALIGN = {"center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}


def place(b):
    taken = set()
    out = []
    ncols = len(b.aligns)
    for r, row in enumerate(b.rows):
        c = 0
        for cell in row.cells:
            while (r, c) in taken:
                c += 1
            rs = min(max(cell.rowspan, 1), len(b.rows) - r)
            cs = max(cell.colspan, 1)
            out.append((r, c, rs, cs, cell))
            for i in range(rs):
                for j in range(cs):
                    taken.add((r + i, c + j))
            c += cs
            ncols = max(ncols, c)
    return out, len(b.rows), ncols


def widths(fr, n, total):
    fr = (list(fr) + [None] * n)[:n]
    fixed = sum(f for f in fr if f)
    free = sum(1 for f in fr if not f)
    rest = max(total * (1 - fixed) / free, 720) if free else 0
    return [int(total * f) if f else int(rest) for f in fr]


def grid(box, b):
    cells, nrows, ncols = place(b)
    t = box.add_table(nrows, ncols)
    total = sum(col.width.twips for col in t.columns)
    ws = widths(b.widths, ncols, total)
    for i, col in enumerate(t.columns):
        col.width = Twips(ws[i])
    for r, c, rs, cs, cell in cells:
        if rs > 1 or cs > 1:
            t.cell(r, c).merge(t.cell(r + rs - 1, c + cs - 1))
    for tr in t._tbl.tr_lst:
        c = 0
        for tc in tr.tc_lst:
            tc.width = Twips(sum(ws[c:c + tc.grid_span]))
            c += tc.grid_span
    for i in range(min(b.head, nrows)):
        t.rows[i]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    return t, cells


def ends_with_table(box):
    el = box._tc if hasattr(box, "_tc") else box.element.body
    kids = [k for k in el if k.tag not in (qn("w:sectPr"), qn("w:tcPr"))]
    return bool(kids) and kids[-1].tag == qn("w:tbl")


def finish(box, first, align, rows):
    tc = box._tc
    if len([x for x in tc if x.tag != qn("w:tcPr")]) > 1:
        tc.remove(first)
    if align in ALIGN:
        for p in box.paragraphs:
            if p.alignment is None:
                p.alignment = ALIGN[align]
    if rows > 1:
        box.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
