from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .package import clean


def el(tag, parent=None, **attrs):
    e = OxmlElement("w:" + tag)
    for k, v in attrs.items():
        e.set(qn("w:" + k), str(v))
    if parent is not None:
        parent.append(e)
    return e


def left(level):
    return 720 * (level + 1)


def abstract(aid, a):
    x = el("abstractNum", abstractNumId=aid)
    el("nsid", x, val=f"{0x54540000 + aid:08X}")
    el("multiLevelType", x, val="hybridMultilevel")
    for lv in a.levels:
        l = el("lvl", x, ilvl=lv.ilvl)
        el("start", l, val=1)
        el("numFmt", l, val=lv.fmt)
        el("lvlText", l, val=clean(lv.text))
        el("lvlJc", l, val="left")
        el("ind", el("pPr", l), left=left(lv.ilvl), hanging=360)
    return x


def build(d, eng):
    root = d.part.numbering_part.element
    old = root.findall(qn("w:abstractNum"))
    a0 = max((int(x.get(qn("w:abstractNumId"))) for x in old), default=-1)
    n0 = max((int(x.get(qn("w:numId"))) for x in root.findall(qn("w:num"))), default=0)
    pos = root.index(old[-1]) + 1 if old else len(root.findall(qn("w:numPicBullet")))
    for a in eng.abstracts.values():
        root.insert(pos, abstract(a0 + a.id, a))
        pos += 1
    ids = {}
    for n in eng.nums:
        x = el("num", root, numId=n0 + n.id)
        el("abstractNumId", x, val=a0 + n.abstract)
        el("startOverride", el("lvlOverride", x, ilvl=n.level), val=n.start)
        ids[n.id] = n0 + n.id
    return ids
