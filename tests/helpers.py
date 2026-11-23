import io
import re
import struct
import zipfile
import zlib

from lxml import etree

from tejtex.diag import Report
from tejtex.ir.context import DocumentContext
from tejtex.ir.nodes import Bibliography, Document, Heading, Hyperlink, Image, List, ListItem, Meta, Placeholder, TextRun, walk

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
        if isinstance(n, Bibliography):
            use("Bibliography")
        if isinstance(n, Heading) and n.number:
            ctx.numbering.headings()
        if isinstance(n, Hyperlink):
            use("Hyperlink")
        if isinstance(n, Image) and not n.rel:
            use("PlaceholderChar")
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


def linked(data):
    out = {}
    for st in part(data, "word/styles.xml").iter(W + "style"):
        nid = st.find(f"{W}pPr/{W}numPr/{W}numId")
        if nid is not None:
            lv = st.find(f"{W}pPr/{W}numPr/{W}ilvl")
            out[st.get(W + "styleId")] = (nid.get(W + "val"), int(lv.get(W + "val")) if lv is not None else 0)
    return out


def labels(data, root=None):
    nums = numbering(data)
    styles = linked(data)
    count = {}
    out = []
    for p in (part(data) if root is None else root).iter(W + "p"):
        t = "".join(x.text or "" for x in p.iter(W + "t"))
        pr = p.find(f"{W}pPr/{W}numPr")
        st = p.find(f"{W}pPr/{W}pStyle")
        nid, lv = styles.get(st.get(W + "val") if st is not None else None, (None, 0))
        if pr is not None:
            nid = pr.find(W + "numId").get(W + "val")
            il = pr.find(W + "ilvl")
            lv = int(il.get(W + "val")) if il is not None else lv
        if nid in (None, "0"):
            out.append((None, t))
            continue
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


def png(w, h, dpi=None):
    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data))
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    if dpi:
        ppm = round(dpi / 0.0254)
        out += chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def marks(data):
    out = {}
    names = {}
    live = {}
    for e in part(data).iter():
        if e.tag == W + "bookmarkStart":
            names[e.get(W + "id")] = e.get(W + "name")
            live[e.get(W + "id")] = ""
        elif e.tag == W + "bookmarkEnd":
            i = e.get(W + "id")
            out[names[i]] = live.pop(i)
        elif e.tag == W + "t" or (e.tag == W + "tab" and e.getparent().tag == W + "r"):
            for i in live:
                live[i] += e.text or "" if e.tag == W + "t" else "\t"
    return out


def words(p):
    out = ""
    for e in p.iter(W + "t", W + "tab"):
        if e.tag == W + "t":
            out += e.text or ""
        elif e.getparent().tag == W + "r":
            out += "\t"
    return out


def home(data, name):
    for p in part(data).iter(W + "p"):
        for e in p.iter(W + "bookmarkStart"):
            if e.get(W + "name") == name:
                st = p.find(f"{W}pPr/{W}pStyle")
                return st.get(W + "val") if st is not None else None, words(p)
    return None


def links(data):
    out = []
    for h in part(data).iter(W + "hyperlink"):
        rid = h.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        out.append((h.get(W + "anchor") or rid, "".join(t.text or "" for t in h.iter(W + "t"))))
    return out


def fields(data):
    out = []
    code = None
    result = None
    for e in part(data).iter(W + "fldChar", W + "instrText", W + "t"):
        if e.tag == W + "fldChar":
            kind = e.get(W + "fldCharType")
            if kind == "begin":
                code, result = "", None
            elif kind == "separate":
                result = ""
            elif kind == "end":
                out.append((" ".join(code.split()), result))
                code = result = None
        elif e.tag == W + "instrText" and code is not None:
            code += e.text or ""
        elif e.tag == W + "t" and result is not None:
            result += e.text or ""
    return out


def shown(data):
    return [(f"{a}\t{t}" if a else t) for a, t in labels(data)]


def update(data, root=None):
    root = part(data) if root is None else root
    nums = [a for a, _ in labels(data, root)]
    top = {}
    hist = []
    seen = {}
    count = {}
    vals = []
    home = {}
    for p, num in zip(root.iter(W + "p"), nums):
        st = p.find(f"{W}pPr/{W}pStyle")
        m = re.fullmatch(r"Heading(\d)", st.get(W + "val") if st is not None else "")
        if m:
            top[int(m[1])] = num
            hist.append(int(m[1]))
        for b in p.iter(W + "bookmarkStart"):
            home[b.get(W + "name")] = num
        code = None
        for e in p.iter(W + "fldChar", W + "instrText"):
            if e.tag == W + "instrText":
                code += e.text or ""
            elif e.get(W + "fldCharType") == "begin":
                code = ""
            elif code is not None:
                w = code.split()
                code = None
                v = None
                if w[0] == "SEQ":
                    lv = int(w[w.index("\\s") + 1]) if "\\s" in w else 0
                    if lv and any(x <= lv for x in hist[seen.get(w[1], 0):]):
                        count[w[1]] = 0
                    count[w[1]] = count.get(w[1], 0) + 1
                    seen[w[1]] = len(hist)
                    v = str(count[w[1]])
                elif w[0] == "STYLEREF":
                    v = top[int(w[1])]
                vals.append([" ".join(w), v])
    text = {}
    ids = {}
    live = []
    i = -1
    inside = False
    for e in root.iter(W + "bookmarkStart", W + "bookmarkEnd", W + "fldChar", W + "t"):
        if e.tag == W + "bookmarkStart":
            ids[e.get(W + "id")] = e.get(W + "name")
            text[e.get(W + "name")] = ""
            live.append(e.get(W + "name"))
        elif e.tag == W + "bookmarkEnd":
            live.remove(ids[e.get(W + "id")])
        elif e.tag == W + "fldChar":
            kind = e.get(W + "fldCharType")
            if kind == "begin":
                i += 1
            inside = kind == "separate"
            if kind == "end":
                for n in live:
                    text[n] += vals[i][1] or ""
        elif not inside:
            for n in live:
                text[n] += e.text or ""
    for v in vals:
        w = v[0].split()
        if w[0] == "REF":
            v[1] = home[w[1]] if "\\w" in w else text[w[1]]
    return [tuple(v) for v in vals]
