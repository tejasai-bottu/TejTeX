import io
import zipfile

from lxml import etree

from tejtex.diag import Report
from tejtex.ir.context import DocumentContext
from tejtex.ir.nodes import Document, List, ListItem, Meta, Placeholder, TextRun, walk

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def make(blocks, meta=None):
    ctx = DocumentContext(Report(), None)
    d = Document(meta or Meta(), blocks, ctx)
    use = ctx.styles.use
    for n in walk(d):
        st = getattr(n, "style", None)
        if isinstance(st, str) and st in ctx.styles.all:
            use(st)
        if isinstance(n, TextRun) and n.code:
            use("VerbatimChar")
        if isinstance(n, Placeholder):
            use("PlaceholderChar" if n.inline else "Placeholder")
        if isinstance(n, List):
            use("Compact")
            if n.kind != "description":
                n.num = ctx.numbering.new(n.kind, "DefaultStyle", "DefaultDelim", n.start, n.level).id
        if isinstance(n, ListItem) and n.label is not None:
            n.num = ctx.numbering.label(n.label, 0).id
    m = d.meta
    for sid, v in (("Title", m.title), ("Author", m.authors), ("Date", m.date)):
        if v:
            use(sid)
    return d


def part(data, name="word/document.xml"):
    return etree.fromstring(zipfile.ZipFile(io.BytesIO(data)).read(name))


def paras(data):
    out = []
    for p in part(data).iter(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        runs = []
        for r in p.iter(W + "r"):
            t = "".join(x.text or "" for x in r.iter(W + "t"))
            if r.find(W + "tab") is not None:
                t += "\t"
            if r.find(W + "br") is not None:
                t += "\n"
            props = set()
            rp = r.find(W + "rPr")
            if rp is not None:
                for c in rp:
                    v = c.get(W + "val")
                    name = c.tag.replace(W, "")
                    props.add(f"{name}={v}" if v else name)
            runs.append((t, props))
        out.append((st.get(W + "val") if st is not None else None, runs))
    return out


def style(data, sid):
    for s in part(data, "word/styles.xml").iter(W + "style"):
        if s.get(W + "styleId") == sid:
            return s
    return None


def roman(n):
    out = ""
    for v, s in [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                 (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]:
        while n >= v:
            out += s
            n -= v
    return out


SHOW = {
    "decimal": str, "lowerLetter": lambda n: chr(96 + n), "upperLetter": lambda n: chr(64 + n),
    "lowerRoman": roman, "upperRoman": lambda n: roman(n).upper(),
}


def numbering(data):
    root = part(data, "word/numbering.xml")
    absts = {}
    for a in root.findall(W + "abstractNum"):
        lv = {}
        for x in a.findall(W + "lvl"):
            lv[int(x.get(W + "ilvl"))] = (x.find(W + "numFmt").get(W + "val"), x.find(W + "lvlText").get(W + "val"))
        absts[a.get(W + "abstractNumId")] = lv
    nums = {}
    for n in root.findall(W + "num"):
        starts = {int(o.get(W + "ilvl")): int(o.find(W + "startOverride").get(W + "val")) for o in n.findall(W + "lvlOverride")}
        nums[n.get(W + "numId")] = (absts[n.find(W + "abstractNumId").get(W + "val")], starts)
    return nums


def labels(data):
    nums = numbering(data)
    count = {}
    out = []
    for p in part(data).iter(W + "p"):
        t = "".join(x.text or "" for x in p.iter(W + "t"))
        pr = p.find(f"{W}pPr/{W}numPr")
        if pr is None:
            out.append((None, t))
            continue
        nid = pr.find(W + "numId").get(W + "val")
        lv = int(pr.find(W + "ilvl").get(W + "val"))
        levels, starts = nums[nid]
        c = count.setdefault(nid, {})
        c[lv] = c[lv] + 1 if lv in c else starts.get(lv, 1)
        for k in [k for k in c if k > lv]:
            del c[k]
        label = levels[lv][1]
        for k in range(lv + 1):
            fmt = levels[k][0]
            if fmt in SHOW:
                label = label.replace(f"%{k + 1}", SHOW[fmt](c.get(k, 1)))
        out.append((label, t))
    return out
