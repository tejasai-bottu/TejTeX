import io
import zipfile

from lxml import etree

from tejtex.diag import Report
from tejtex.ir.context import DocumentContext
from tejtex.ir.nodes import Document, Meta, Placeholder, TextRun, walk

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
