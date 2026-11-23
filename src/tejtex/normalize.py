import re

from . import caps, tree
from .source import check

LABEL = re.compile(r"\\label\s*\{([^}]*)\}")
EXTS = ["", ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"]
MARKS = {"tejtex-placeholder", "tejtex-anchor"}
ITEM = "tejtex-item"


def words(s):
    out = []
    for w in s.split():
        if out:
            out.append({"t": "Space"})
        out.append({"t": "Str", "c": w})
    return out


def attrs(info):
    a = [["category", info["category"]], ["element", info["element"]], ["source", info.get("loc", "")]]
    if info.get("key"):
        a.append(["key", info["key"]])
    return a


def span(info):
    if info.get("anchor"):
        return {"t": "Span", "c": [["", ["tejtex-anchor"], attrs(info)], []]}
    return {"t": "Span", "c": [["", ["tejtex-placeholder"], attrs(info)], words(info["text"])]}


def div(info):
    para = {"t": "Para", "c": words(info["text"])}
    return {"t": "Div", "c": [["", ["tejtex-placeholder"], attrs(info)], [para]]}


def mark(n, s):
    if n.get("t") != "Link":
        return None
    url = n["c"][2][0]
    pre = f"tejtex-{s.token}:"
    if not url.startswith(pre):
        return None
    return s.marks.get(int(url[len(pre):]))


def alone(n, s):
    items = [x for x in n["c"] if x.get("t") not in ("Space", "SoftBreak")]
    if len(items) == 1:
        info = mark(items[0], s)
        if info and not info.get("anchor") and not info.get("item"):
            return info
    return None


def image(n, s, rep):
    src = n["c"][2][0]
    el = "\\includegraphics{%s}" % src
    i = s.text.find(src)
    loc = s.where(i) if i >= 0 else ""
    p, why = check(s.root, src)
    if why:
        rep.add("error", "unsupported", el, "rejected: " + why, loc)
        return span({"element": el, "category": "unsupported", "loc": loc, "text": f"[TejTeX: image {src} rejected]"})
    if not any((s.root / (src + e)).is_file() for e in EXTS):
        rep.add("warning", "", el, "image file not found", loc)
    return n


def bib(n):
    blocks = n["c"][1]
    if blocks and blocks[0].get("t") in ("Para", "Plain"):
        c = blocks[0]["c"]
        if c and c[0].get("t") == "Span" and c[0]["c"][0] == ["", [], []]:
            del c[0]
            while c and c[0].get("t") in ("Space", "SoftBreak"):
                del c[0]


def name(n, partial):
    t = n.get("t")
    if t in ("Div", "Span"):
        a = n["c"][0]
        if ITEM in a[1]:
            return "\\item[]", "supported"
        if MARKS & set(a[1]):
            d = dict(a[2])
            return d["element"], d["category"]
        if a[1]:
            return f"{t}.{a[1][0]}", "partial" if a[1][0] in partial else "supported"
    return t, "supported" if t in caps.NODES else "unsupported"


def run(ast, s, rep):
    partial = {d.element for d in rep.diags if d.category == "partial"}
    done = set()
    for lst, i in tree.each(ast["blocks"]):
        n = lst[i]
        t = n.get("t")
        if t in ("Para", "Plain"):
            info = alone(n, s)
            if info:
                n = lst[i] = div(info)
        elif t == "Link":
            info = mark(n, s)
            if info and info.get("item"):
                n = lst[i] = {"t": "Span", "c": [["", [ITEM], []], n["c"][1]]}
            elif info:
                n = lst[i] = span(info)
        elif t == "Image":
            n = lst[i] = image(n, s, rep)
        elif t == "Math" and id(n) not in done:
            labels = LABEL.findall(n["c"][1])
            if labels:
                done.add(id(n))
                n = lst[i] = {"t": "Span", "c": [[labels[0], ["tejtex-equation"], [["labels", " ".join(labels)]]], [n]]}
        elif t == "Cite":
            n["c"][1] = [x for x in n["c"][1] if x.get("t") != "RawInline"]
        elif t == "Div" and "thebibliography" in n["c"][0][1]:
            bib(n)
        el, cat = name(n, partial)
        rep.count(el, cat)
        if n.get("t") in ("RawBlock", "RawInline"):
            rep.add("warning", "unsupported", n["t"], "raw LaTeX kept by Pandoc is not converted", "")
