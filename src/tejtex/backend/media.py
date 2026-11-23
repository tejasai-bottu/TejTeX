import posixpath
import re

from docx.image.image import Image as Picture
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.oxml.shape import CT_Inline
from docx.parts.image import ImagePart

UNITS = {"in": 914400, "cm": 360000, "mm": 36000, "pt": 12651, "bp": 12700, "pc": 151817, "px": 9525, "em": 126514, "ex": 54401}
SIZE = re.compile(r"(\d*\.?\d*)\s*(%|in|cm|mm|pt|bp|pc|px|em|ex|\\linewidth|\\textwidth|\\columnwidth|\\hsize|\\textheight)")


def length(s, wide, tall):
    m = SIZE.fullmatch(s.strip()) if s else None
    if not m:
        return None
    v = float(m[1]) if m[1] not in ("", ".") else 1.0
    u = m[2]
    if u == "%":
        return int(wide * v / 100)
    if u == "\\textheight":
        return int(tall * v)
    if u.startswith("\\"):
        return int(wide * v)
    return int(v * UNITS[u])


class Media:
    def __init__(self, d, rels):
        self.d = d
        self.rels = {r.id: r for r in rels if r.kind == "image"}
        self.pics = {}
        self.n = 0
        s = d.sections[-1]
        self.wide = s.page_width - s.left_margin - s.right_margin
        self.tall = s.page_height - s.top_margin - s.bottom_margin

    def picture(self, rid):
        if rid not in self.pics:
            r = self.rels[rid]
            try:
                pic = Picture.from_file(r.source)
            except Exception:
                pic = None
            if pic:
                part = ImagePart.from_image(pic, PackURI("/word/" + r.target))
                self.d.part.rels.add_relationship(RT.IMAGE, part, rid)
            self.pics[rid] = pic
        return self.pics[rid]

    def inline(self, x):
        pic = self.picture(x.rel) if x.rel in self.rels else None
        if not pic:
            return None
        w = length(x.width, self.wide, self.tall)
        h = length(x.height, self.wide, self.tall)
        cx, cy = pic.scaled_dimensions(w, h)
        if cx > self.wide:
            cx, cy = self.wide, int(cy * self.wide / cx)
        self.n += 1
        inline = CT_Inline.new_pic_inline(self.n, x.rel, posixpath.basename(self.rels[x.rel].target), cx, cy)
        if x.alt:
            inline.docPr.set("descr", x.alt)
        return inline
