import re
from pathlib import Path

from .. import tree
from ..errors import Exit, TejtexError
from ..normalize import EXTS
from . import bib
from .context import DELIMS, FORMATS, DocumentContext, counter
from .nodes import (
    Anchor, BibEntry, Bibliography, Break, Cell, Citation, CodeBlock, Container, CrossReference,
    Document, Figure, Footnote, Heading, Hyperlink, Image, List, ListItem, Math, Meta, Paragraph,
    Placeholder, Quote, Row, Rule, Seq, Table, TextRun, Theorem, merge, tidy,
)

ENV = re.compile(r"\s*\\begin\{(\w+)(\*?)\}")
LABEL = re.compile(r"\\label\s*\{([^}]*)\}")
TAG = re.compile(r"\\tag\*?\s*\{([^}]*)\}")
NONUM = re.compile(r"\\(?:nonumber|notag)(?![A-Za-z])")
THM = re.compile(r"(.+?)\s+(\d[\w.]*)$")
SAFE = re.compile(r"(?:https?|ftp)://[^\s\"<>\\^`{|}]+|mailto:[^\s\"<>\\^`{|}]+", re.I)
NEWTHM = re.compile(r"\\newtheorem(\*?)\s*\{([^}]*)\}\s*(?:\[([^\]]*)\])?\s*\{[^}]*\}\s*(?:\[([^\]]*)\])?")
NOSORT = re.compile(r"sorting\s*=\s*none")
WITHIN = re.compile(r"\\numberwithin\s*\{([^}]*)\}\s*\{([^}]*)\}")
SEQS = {"figure": "Figure", "table": "Table", "equation": "Equation"}
FIELDS = {"figure", "table", "equation"}
ENUMITEM = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{[^}]*\benumitem\b")
NUMBERED = {"equation", "align", "gather", "multline", "flalign", "alignat", "eqnarray"}
ROWS = {"align", "gather", "flalign", "alignat", "eqnarray"}
PLAIN_DIVS = {"center", "flushleft", "flushright", "minipage", "thebibliography"}
ALIGN = {"AlignLeft": "left", "AlignRight": "right", "AlignCenter": "center", "AlignDefault": None}
MARK = {
    "Emph": "italic", "Strong": "bold", "Underline": "underline", "Strikeout": "strike",
    "Superscript": "sup", "Subscript": "sub", "SmallCaps": "smallcaps",
}
NAMES = {"section": "Section", "figure": "Figure", "table": "Table", "equation": "Equation"}
RASTER = {b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"GIF8": ".gif", b"BM": ".bmp", b"II*\x00": ".tif", b"MM\x00*": ".tif"}
CMDS = {"ref": "ref", "eqref": "eqref", "ref+label": "cref", "ref+Label": "Cref", "pageref": "pageref"}
ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
         (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]


def roman(n):
    out = ""
    for v, s in ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def alpha(n):
    return chr(96 + n) if 1 <= n <= 26 else str(n)


COUNTERS = {
    "decimal": str, "lowerLetter": alpha, "upperLetter": lambda n: alpha(n).upper(),
    "lowerRoman": roman, "upperRoman": lambda n: roman(n).upper(),
}


def item_ref(nums):
    n, f, pat = nums[-1]
    if pat:
        return pat.format(COUNTERS[f](n))
    s = [COUNTERS[f](n) for n, f, _ in nums[:4]]
    if len(s) < 3:
        return "".join(s)
    return s[0] + "(" + s[1] + ")" + "".join(s[2:])


def plain(inls):
    out = []
    for x in inls:
        t, c = x.get("t"), x.get("c")
        if t == "Str":
            out.append(c)
        elif t in ("Space", "SoftBreak", "LineBreak"):
            out.append(" ")
        elif t in MARK:
            out.append(plain(c))
        elif t in ("Span", "Quoted", "Link"):
            out.append(plain(c[1]))
        elif t in ("Code", "Math"):
            out.append(c[1])
    return "".join(out)


def seq_name(c):
    if c in SEQS:
        return SEQS[c]
    s = re.sub(r"[^A-Za-z0-9_]", "_", c)
    return (s if s[:1].isalpha() else "C" + s)[:40]


def sniff(p):
    try:
        with open(p, "rb") as f:
            head = f.read(8)
    except OSError:
        return None
    for magic, ext in RASTER.items():
        if head.startswith(magic):
            return ext
    return None


def custom(it):
    if it and it[0].get("t") in ("Para", "Plain"):
        c = it[0]["c"]
        if c and c[0].get("t") == "Span" and "tejtex-item" in c[0]["c"][0][1]:
            return c[0]
    return None


def plain_blocks(blocks):
    return " ".join(plain(b["c"]) for b in blocks if b.get("t") in ("Para", "Plain"))


def skip_spaces(c, i):
    while i < len(c) and c[i].get("t") in ("Space", "SoftBreak"):
        i += 1
    return i


def trim(c):
    i = skip_spaces(c, 0)
    j = len(c)
    while j > i and c[j - 1].get("t") in ("Space", "SoftBreak"):
        j -= 1
    return c[i:j]


def theorem(body):
    if not body or body[0].get("t") not in ("Para", "Plain"):
        return None
    c = body[0]["c"]
    if not c or c[0].get("t") != "Strong":
        return None
    i = skip_spaces(c, 1)
    if i >= len(c) or c[i].get("t") != "Str" or not c[i]["c"].startswith((".", "(")):
        return None
    s = plain(c[0]["c"]).strip()
    m = THM.match(s)
    return (m[1], m[2]) if m else (s, None)


def split_rows(body):
    out = []
    depth = start = i = 0
    while i < len(body):
        if body.startswith("\\begin{", i):
            depth += 1
            i = body.find("}", i) + 1 or len(body)
            continue
        if body.startswith("\\end{", i):
            depth -= 1
            i = body.find("}", i) + 1 or len(body)
            continue
        if body.startswith("\\\\", i) and depth == 0:
            out.append(body[start:i])
            i += 2
            start = i
            continue
        c = body[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    out.append(body[start:])
    if len(out) > 1 and not out[-1].strip():
        out.pop()
    return out


def equation(tex):
    m = ENV.match(tex)
    if not m:
        return False, [tex]
    env, star = m[1], m[2]
    body = tex[m.end():]
    k = body.rfind("\\end{")
    if k >= 0:
        body = body[:k]
    rows = split_rows(body) if env in ROWS else [body]
    return env in NUMBERED and not star, rows


def clean(tex):
    return TAG.sub("", NONUM.sub("", LABEL.sub("", tex)))


class Builder:
    def __init__(self, rep, src, cfg):
        self.cfg = cfg
        self.ctx = DocumentContext(rep, src)
        self.info = {}
        self.labels = {}
        self.count = 0
        self.sec = [0] * 6
        self.chapters = src is not None and "\\chapter" in src.text
        self.enumitem = src is not None and ENUMITEM.search(src.text) is not None
        self.notes = self.bibn = 0
        self.current = None
        self.root = Path(src.root).resolve() if src is not None else None
        self.counts = {}
        self.within = {c: 1 if self.chapters else 0 for c in FIELDS}
        self.share = {}
        self.cited = []
        self.made = []
        self.nobib = set()
        self.static = set()
        self.star = set()
        self.bst = ""
        text = src.text if src is not None else ""
        for m in NEWTHM.finditer(text):
            if m[1]:
                self.star.add(m[2].strip())
                continue
            env = m[2].strip()
            if m[3]:
                self.share[env] = m[3].strip()
            else:
                self.share[env] = env
                self.within[env] = self.level(m[4].strip()) if m[4] else 0
        for m in WITHIN.finditer(text):
            lv = self.level(m[2].strip())
            if lv is None:
                el = "\\numberwithin{%s}{%s}" % (m[1].strip(), m[2].strip())
                self.ctx.diags.add("warning", "partial", el, "Word restarts numbers only at heading levels 1-3; this number runs on", "")
            else:
                self.within[m[1].strip()] = lv

    def use(self, sid):
        return self.ctx.styles.use(sid)

    def level(self, name):
        lv = {"chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3}.get(name)
        if lv is None:
            return None
        lv += 1 if self.chapters else 0
        return lv if 1 <= lv <= 3 else None

    def step(self, c):
        self.counts[c] = self.counts.get(c, 0) + 1
        lv = self.within.get(c) or 0
        pre = ".".join(str(x) for x in self.sec[:lv]) + "." if lv else ""
        return pre + str(self.counts[c])

    def seq(self, c):
        return Seq(seq_name(c), self.within.get(c) or 0)

    def at(self, label):
        return self.ctx.source.label(label)

    def visit(self, n, d, path):
        if d > self.cfg.nesting:
            raise TejtexError(f"the document is nested more than {self.cfg.nesting} levels deep", Exit.LIMIT)
        self.count += 1
        if self.count > self.cfg.nodes:
            raise TejtexError(f"the document has more than {self.cfg.nodes} elements", Exit.LIMIT)
        if not isinstance(n, dict):
            return
        t = n.get("t")
        if t == "Header":
            self.header(n)
        elif t == "Figure":
            self.figure(n)
        elif t == "Table":
            self.table1(n)
        elif t == "Div":
            if self.div1(n, d, path):
                return
        elif t == "Span":
            self.span1(n, path)
        elif t == "Math":
            self.math1(n)
        elif t == "Note":
            self.notes += 1
            self.info[id(n)] = str(self.notes)
            path = path + [("note", str(self.notes), None)]
        elif t == "Image":
            self.image1(n)
        elif t == "Cite":
            self.cited += [x["citationId"] for x in n["c"][0]]
        elif t == "Link":
            self.link1(n)
        elif t in ("BulletList", "OrderedList", "DefinitionList"):
            self.list1(n, d, path)
            return
        for lst in tree.lists(n):
            for x in lst:
                self.visit(x, d + 1, path)

    def header(self, n):
        level, a, _ = n["c"]
        num = None
        if "unnumbered" not in a[1] and 1 <= level <= 3:
            self.sec[level - 1] += 1
            for k in range(level, 6):
                self.sec[k] = 0
            num = ".".join(str(x) for x in self.sec[:level])
            for c, lv in self.within.items():
                if lv and level <= lv:
                    self.counts[c] = 0
            self.current = num
            self.ctx.numbering.headings()
        t = self.ctx.refs.add(a[0], "section", num, self.at(a[0])) if a[0] else None
        self.info[id(n)] = (num, t)

    def figure(self, n):
        a, cap, _ = n["c"]
        num = self.step("figure") if cap[1] else None
        t = self.ctx.refs.add(a[0], "figure", num, self.at(a[0])) if a[0] else None
        self.info[id(n)] = (num, t, self.seq("figure") if num else None)

    def table1(self, n):
        a, cap = n["c"][0], n["c"][1]
        num = self.step("table") if cap[1] else None
        t = self.ctx.refs.add(a[0], "table", num, self.at(a[0])) if a[0] else None
        self.info[id(n)] = [num, t, self.seq("table") if num else None]

    def div1(self, n, d, path):
        a, body = n["c"]
        cls = a[1]
        if a[0] and not cls and len(body) == 1 and body[0].get("t") == "Table":
            self.visit(body[0], d + 1, path)
            info = self.info[id(body[0])]
            info[1] = self.ctx.refs.add(a[0], "table", info[0], self.at(a[0]))
            return True
        if "tejtex-placeholder" in cls:
            return False
        th = theorem(body) if cls and cls[0] not in PLAIN_DIVS else None
        if th:
            num, sq = self.thm(cls[0], th[1], a[0])
            t = self.ctx.refs.add(a[0], cls[0], num, self.at(a[0])) if a[0] else None
            self.info[id(n)] = ((th[0], num), t, sq)
        elif a[0]:
            self.info[id(n)] = (None, self.ctx.refs.add(a[0], "label", self.current, self.at(a[0])))
        return False

    def thm(self, env, number, label):
        if not number or env in self.star:
            return None, None
        c = self.share.get(env)
        if c is not None and self.share.get(c, c) != c:
            c = self.share[c]
        if c is not None and self.within.get(c) is not None:
            return self.step(c), self.seq(c)
        if env not in self.static:
            self.static.add(env)
            loc = self.at(label) if label else ""
            self.ctx.diags.add("info", "partial", env, "numbering scheme not found; the number is kept as static text", loc)
        return number, None

    def here(self, path):
        for i in range(len(path) - 1, -1, -1):
            kind, v, _ = path[i]
            if kind == "note":
                return v
            if kind == "list" and v is not None:
                return item_ref([p[1] for p in path[:i + 1] if p[0] == "list" and p[1] is not None])
        return self.current

    def span1(self, n, path):
        a = n["c"][0]
        cls = a[1]
        at = dict(a[2])
        if "tejtex-anchor" in cls:
            key = at.get("key")
            if key:
                self.bibn += 1
                self.ctx.refs.cite(key, str(self.bibn), at.get("source", ""))
        elif a[0] and "tejtex-equation" not in cls and "tejtex-placeholder" not in cls:
            t = self.ctx.refs.add(a[0], "label", self.here(path), self.at(a[0]))
            if t:
                self.info[id(n)] = t

    def math1(self, n):
        if n["c"][0]["t"] != "DisplayMath":
            return
        numbered, rows = equation(n["c"][1])
        nums = []
        for r in rows:
            m = LABEL.search(r)
            label = m[1] if m else None
            tag = TAG.search(r)
            if tag:
                text = tag[1]
            elif numbered and not NONUM.search(r):
                text = self.step("equation")
            else:
                continue
            t = self.ctx.refs.add(label, "equation", text, self.at(label)) if label else None
            nums.append((text, t.bookmark if t else None, label, None if tag else self.seq("equation")))
        self.info[id(n)] = nums

    def image1(self, n):
        url = n["c"][2][0]
        if self.root is None or not url:
            return
        for e in EXTS:
            p = (self.root / (url + e)).resolve()
            if p.is_relative_to(self.root) and p.is_file():
                ext = sniff(p)
                if ext:
                    self.info[id(n)] = self.ctx.rels.image(p, ext)
                else:
                    el = "\\includegraphics{%s}" % url
                    self.ctx.diags.add("warning", "render", el, "needs rendering; a placeholder is inserted", self.ctx.source.find(url))
                return

    def link1(self, n):
        a, _, target = n["c"]
        url = target[0]
        if "reference-type" in dict(a[2]) or not url or url.startswith("#"):
            return
        if SAFE.fullmatch(url):
            self.info[id(n)] = self.ctx.rels.link(url)
        else:
            el = "\\href{%s}" % url
            msg = "link target not allowed (only http, https, ftp and mailto); the text is kept without a link"
            self.ctx.diags.add("warning", "partial", el, msg, self.ctx.source.find(url))

    def list1(self, n, d, path):
        t, c = n["t"], n["c"]
        lv = sum(1 for p in path if p[0] == "list")
        if t == "DefinitionList":
            self.info[id(n)] = lv
            for term, defs in c:
                for x in term:
                    self.visit(x, d + 1, path)
                for blocks in defs:
                    for x in blocks:
                        self.visit(x, d + 1, path + [("list", None, "description")])
            return
        kind = "bullet" if t == "BulletList" else "ordered"
        dep = sum(1 for p in path if p[0] == "list" and p[2] == kind)
        if kind == "bullet":
            self.info[id(n)] = self.ctx.numbering.new("bullet", None, None, 1, lv, dep)
            start, fmt, pat, items = 1, None, None, c
        else:
            start, style, delim = c[0][0], c[0][1]["t"], c[0][2]["t"]
            self.info[id(n)] = self.ctx.numbering.new("ordered", style, delim, start, lv, dep)
            fmt, items = counter(style, dep), c[1]
            pat = DELIMS.get(delim, "{}.") if self.enumitem and style in FORMATS else None
        k = start - 1
        last = None
        for it in items:
            lab = custom(it)
            if lab:
                s = plain(lab["c"][1]).strip()
                self.labels[id(it)] = (s, self.ctx.numbering.label(s, lv))
                v = last
            elif fmt:
                k += 1
                v = last = (k, fmt, pat)
            else:
                v = None
            for x in it:
                self.visit(x, d + 1, path + [("list", v, kind)])

    def blocks(self, lst, d, style):
        out = []
        for n in lst:
            out += self.block(n, d, style)
        return out

    def block(self, n, d, style):
        t, c = n.get("t"), n.get("c")
        if t in ("Para", "Plain"):
            st = "Compact" if t == "Plain" and style == "BodyText" else style
            return [Paragraph(self.use(st), tidy(self.inl(c, d + 1)))]
        if t == "LineBlock":
            inls = []
            for i, line in enumerate(c):
                if i:
                    inls.append({"t": "LineBreak"})
                inls += line
            return [Paragraph(self.use(style), self.inl(inls, d + 1))]
        if t == "CodeBlock":
            return [CodeBlock(c[1], self.use("SourceCode"))]
        if t == "RawBlock":
            self.use("Placeholder")
            return [Placeholder("unsupported", "RawBlock", "[TejTeX: raw LaTeX is not supported]")]
        if t == "BlockQuote":
            return [Quote(self.blocks(c, d + 1, "BlockText"))]
        if t in ("BulletList", "OrderedList"):
            self.use("Compact")
            num = self.info[id(n)]
            kind = "bullet" if t == "BulletList" else "ordered"
            items = []
            for it in (c if t == "BulletList" else c[1]):
                lab, ln = self.labels.get(id(it), (None, None))
                if lab is not None:
                    it = self.unlabel(it)
                items.append(ListItem(self.blocks(it, d + 1, "Compact"), [], lab, ln.id if ln else None))
            return [List(kind, items, num.id, num.level, num.start)]
        if t == "DefinitionList":
            self.use("Compact")
            items = []
            for term, defs in c:
                body = [b for blocks in defs for b in blocks]
                items.append(ListItem(self.blocks(body, d + 1, "Compact"), self.inl(term, d + 1)))
            return [List("description", items, None, self.info[id(n)])]
        if t == "Header":
            level, a, inls = c
            num, tg = self.info.get(id(n), (None, None))
            return [Heading(level, self.inl(inls, d + 1), self.use(f"Heading{min(max(level, 1), 6)}"), num,
                            tg.bookmark if tg else None, a[0] or None, tg.src if tg else "")]
        if t == "HorizontalRule":
            return [Rule()]
        if t == "Table":
            return [self.table(n, d)]
        if t == "Figure":
            a, cap, body = c
            num, tg, sq = self.info.get(id(n), (None, None, None))
            return [Figure(self.blocks(body, d + 1, "Figure"), self.blocks(cap[1], d + 1, "Caption"), num,
                           tg.bookmark if tg else None, a[0] or None, tg.src if tg else "", seq=sq)]
        if t == "Div":
            return self.div(n, d, style)
        return []

    def unlabel(self, it):
        c = it[0]["c"]
        del c[0]
        while c and c[0].get("t") in ("Space", "SoftBreak"):
            del c[0]
        return it if c else it[1:]

    def table(self, n, d):
        a, cap, specs, head, bodies, foot = n["c"]
        num, tg, sq = self.info.get(id(n), (None, None, None))
        rows = [self.row(r, d) for r in head[1]]
        nhead = len(rows)
        for b in bodies:
            rows += [self.row(r, d) for r in b[2] + b[3]]
        rows += [self.row(r, d) for r in foot[1]]
        aligns = [ALIGN.get(s[0]["t"]) for s in specs]
        widths = [s[1].get("c") if s[1]["t"] == "ColWidth" else None for s in specs]
        return Table(rows, aligns, nhead, self.blocks(cap[1], d + 1, "Caption"), num,
                     tg.bookmark if tg else None, tg.label if tg else None, self.use("Table"), tg.src if tg else "", widths,
                     seq=sq)

    def row(self, r, d):
        cells = []
        for cell in r[1]:
            cells.append(Cell(self.blocks(cell[4], d + 2, "Compact"), ALIGN.get(cell[1]["t"]), cell[2], cell[3]))
        return Row(cells)

    def div(self, n, d, style):
        a, body = n["c"]
        cls = a[1]
        if "tejtex-placeholder" in cls:
            at = dict(a[2])
            self.use("Placeholder")
            return [Placeholder(at.get("category", ""), at.get("element", ""), plain_blocks(body), at.get("source", ""))]
        if a[0] and not cls and len(body) == 1 and body[0].get("t") == "Table":
            return [self.table(body[0], d + 1)]
        if "thebibliography" in cls:
            return [self.refhead(), self.bibliography(body, d)]
        info = self.info.get(id(n))
        if info and info[0]:
            return [self.theorem(n, d, info)]
        tg = info[1] if info else None
        return [Container(cls[0] if cls else None, self.blocks(body, d + 1, style), tg.bookmark if tg else None, a[0] or None)]

    def theorem(self, n, d, info):
        a, body = n["c"]
        (name, number), tg, sq = info
        first = body[0]["c"][1:]
        i = skip_spaces(first, 0)
        title = []
        if i < len(first) and first[i].get("t") == "Str" and first[i]["c"] == ".":
            i += 1
        elif i < len(first) and first[i].get("t") == "Str" and first[i]["c"].startswith("("):
            j = i
            while j < len(first) and not (first[j].get("t") == "Str" and first[j]["c"].endswith(").")):
                j += 1
            if j < len(first):
                title = list(first[i:j + 1])
                title[0] = {"t": "Str", "c": title[0]["c"][1:]}
                title[-1] = {"t": "Str", "c": title[-1]["c"][:-2]}
                i = j + 1
        rest = first[skip_spaces(first, i):]
        blocks = [{"t": body[0]["t"], "c": rest}] + body[1:]
        return Theorem(a[1][0], name, self.blocks(blocks, d + 1, "BodyText"), number, self.inl(title, d + 1),
                       tg.bookmark if tg else None, a[0] or None, tg.src if tg else "", sq)

    def bibliography(self, body, d):
        entries = []
        cur = None
        for b in body:
            if b.get("t") not in ("Para", "Plain"):
                continue
            for x in b["c"]:
                if x.get("t") == "Span" and "tejtex-anchor" in x["c"][0][1]:
                    cur = [dict(x["c"][0][2]).get("key", ""), []]
                    entries.append(cur)
                elif cur is None:
                    if x.get("t") not in ("Space", "SoftBreak"):
                        cur = [None, [x]]
                        entries.append(cur)
                else:
                    cur[1].append(x)
        self.use("Bibliography")
        out = []
        for key, inls in entries:
            t = self.ctx.refs.bib.get(key) if key else None
            num = t.number if t else None
            out.append(BibEntry(key, num, self.inl(trim(inls), d + 1), t.bookmark if t else None, Seq("Bib") if num else None))
        return Bibliography(out)

    def refhead(self):
        return Heading(1, [TextRun("Bibliography" if self.chapters else "References")], self.use("Heading1"))

    def bibfile(self, src):
        if self.ctx.refs.bib or src is None or not getattr(src, "bibs", None):
            return
        entries = []
        seen = set()
        for rel, text, loc in src.bibs:
            for e in bib.parse(text):
                if e["key"] not in seen:
                    seen.add(e["key"])
                    entries.append(e)
        self.bst = (src.bibstyle or "").strip()
        style = self.bst
        if not style and src.biblatex:
            style = "none" if NOSORT.search(src.text) else "nty"
        self.made = bib.order(entries, self.cited + list(src.nocite), style)
        for i, e in enumerate(self.made, 1):
            self.ctx.refs.cite(e["key"], str(i))

    def references(self):
        self.use("Bibliography")
        out = []
        for e in self.made:
            t = self.ctx.refs.bib[e["key"]]
            inls, url = bib.runs(e, bool(self.bst))
            if url and SAFE.fullmatch(url):
                self.use("Hyperlink")
                inls += [TextRun(" "), Hyperlink([TextRun(url)], url, self.ctx.rels.link(url).id)]
            out.append(BibEntry(e["key"], t.number, inls, t.bookmark, Seq("Bib")))
        return [self.refhead(), Bibliography(out)]

    def inl(self, lst, d, fmt=None):
        out = []
        for x in lst:
            self.inline(x, d, fmt or {}, out)
        return merge(out)

    def inline(self, n, d, fmt, out):
        t, c = n.get("t"), n.get("c")
        if t == "Str":
            out.append(TextRun(c, **fmt))
        elif t in ("Space", "SoftBreak"):
            out.append(TextRun(" ", **fmt))
        elif t == "LineBreak":
            out.append(Break())
        elif t in MARK:
            k = MARK[t]
            f = dict(fmt)
            f[k] = not fmt.get(k, False) if k == "italic" else True
            for x in c:
                self.inline(x, d + 1, f, out)
        elif t == "Quoted":
            q = "“”" if c[0]["t"] == "DoubleQuote" else "‘’"
            out.append(TextRun(q[0], **fmt))
            for x in c[1]:
                self.inline(x, d + 1, fmt, out)
            out.append(TextRun(q[1], **fmt))
        elif t == "Code":
            self.use("VerbatimChar")
            out.append(TextRun(c[1], **dict(fmt, code=True)))
        elif t == "Math":
            kind, tex = c
            out.append(Math(clean(tex), kind["t"] == "DisplayMath", self.info.get(id(n), [])))
        elif t == "Cite":
            out.append(self.cite(c))
        elif t == "Link":
            out.append(self.link(n, d, fmt))
        elif t == "Image":
            out.append(self.image(n))
        elif t == "Note":
            self.use("FootnoteReference")
            out.append(Footnote(self.info.get(id(n)), self.blocks(c, d + 1, "FootnoteText")))
        elif t == "Span":
            self.span(n, d, fmt, out)
        elif t == "RawInline":
            self.use("PlaceholderChar")
            out.append(Placeholder("unsupported", "RawInline", "[TejTeX: raw LaTeX is not supported]", "", True))

    def cite(self, c):
        cs = c[0]
        keys = [x["citationId"] for x in cs]
        bib = self.ctx.refs.bib
        src = self.ctx.source.cite(keys[0]) if keys else ""
        if bib:
            ts = [bib.get(k) for k in keys]
            for k, t in zip(keys, ts):
                if t is None:
                    self.ctx.diags.add("warning", "", "\\cite{%s}" % k, "citation key not found in the bibliography", src)
            nums = [t.number if t else "?" for t in ts]
            marks = [t.bookmark if t else None for t in ts]
        else:
            nums = keys
            marks = [None] * len(keys)
            for k in keys:
                if k not in self.nobib:
                    self.nobib.add(k)
                    self.ctx.diags.add("warning", "", "\\cite{%s}" % k, "no bibliography found; the citation shows its key", src)
        suffix = plain(cs[-1]["citationSuffix"]).strip() if cs else ""
        text = "[" + ", ".join(nums) + (", " + suffix if suffix else "") + "]"
        mode = cs[0]["citationMode"]["t"] if cs else "NormalCitation"
        return Citation(keys, text, marks, mode, src, nums, suffix)

    def link(self, n, d, fmt):
        a, kids, target = n["c"]
        url = target[0]
        at = dict(a[2])
        if "reference-type" in at:
            return self.xref(at["reference"], at["reference-type"], kids)
        self.use("Hyperlink")
        inls = self.inl(kids, d + 1, fmt)
        if url.startswith("#"):
            tg = self.ctx.refs.get(url[1:])
            if tg is None:
                self.ctx.diags.add("warning", "", "\\hyperref[%s]" % url[1:], "link to an undefined label", self.ctx.source.ref(url[1:]))
            return Hyperlink(inls, None, None, tg.bookmark if tg else None)
        rel = self.info.get(id(n))
        return Hyperlink(inls, url, rel.id if rel else None)

    def xref(self, label, kind, kids):
        tg = self.ctx.refs.get(label)
        src = self.ctx.source.ref(label)
        if tg is None:
            el = "\\%s{%s}" % (CMDS.get(kind, "ref"), label)
            self.ctx.diags.add("warning", "", el, "reference to an undefined label", src)
            return CrossReference(label, kind, "(??)" if kind == "eqref" else "??", None, src)
        num = tg.number
        before = after = ""
        if num and kind == "eqref":
            before, after = "(", ")"
        elif num and kind.startswith("ref+"):
            before = f"{NAMES.get(tg.kind, tg.kind.capitalize())} "
        text = before + num + after if num else plain(kids) or "??"
        field = None
        if num and tg.kind == "section":
            field = "paragraph"
        elif num and tg.kind not in ("label", "bibitem"):
            field = "text"
        return CrossReference(label, kind, text, tg.bookmark, src, field, num if field else None, before, after)

    def image(self, n):
        a, alt, target = n["c"]
        rel = self.info.get(id(n))
        if not rel:
            self.use("PlaceholderChar")
        at = dict(a[2])
        text = plain(alt)
        return Image(target[0], rel.id if rel else None, rel.target if rel else None,
                     at.get("width"), at.get("height"), "" if text == "image" else text, self.ctx.source.find(target[0]))

    def span(self, n, d, fmt, out):
        a, kids = n["c"]
        cls = a[1]
        if "tejtex-placeholder" in cls:
            at = dict(a[2])
            self.use("PlaceholderChar")
            out.append(Placeholder(at.get("category", ""), at.get("element", ""), plain(kids), at.get("source", ""), True))
            return
        if "tejtex-anchor" in cls:
            tg = self.ctx.refs.bib.get(dict(a[2]).get("key", ""))
            if tg:
                out.append(Anchor(tg.bookmark, tg.label))
            return
        tg = self.info.get(id(n))
        if tg:
            out.append(Anchor(tg.bookmark, tg.label))
        for x in kids:
            self.inline(x, d + 1, fmt, out)

    def meta(self, m):
        out = Meta()
        if "title" in m:
            self.use("Title")
            out.title = self.meta_inl(m["title"])
        if "author" in m:
            self.use("Author")
            v = m["author"]
            out.authors = [self.meta_inl(x) for x in (v["c"] if v["t"] == "MetaList" else [v])]
        if "date" in m:
            self.use("Date")
            out.date = self.meta_inl(m["date"])
        if "abstract" in m:
            v = m["abstract"]
            if v["t"] == "MetaBlocks":
                out.abstract = self.blocks(v["c"], 1, "Abstract")
            else:
                out.abstract = [Paragraph(self.use("Abstract"), self.meta_inl(v))]
        return out

    def meta_inl(self, v):
        t = v.get("t")
        if t == "MetaInlines":
            return self.inl(v["c"], 1)
        if t == "MetaString":
            return [TextRun(v["c"])]
        if t == "MetaBlocks":
            return self.inl([x for b in v["c"] if b.get("t") in ("Para", "Plain") for x in b["c"]], 1)
        return []


def build(ast, rep, src, cfg):
    b = Builder(rep, src, cfg)
    for n in ast["blocks"]:
        b.visit(n, 1, [])
    b.bibfile(src)
    for label, loc in b.ctx.refs.dups:
        rep.add("warning", "", "\\label{%s}" % label, "label defined more than once; the first one is used", loc)
    meta = b.meta(ast.get("meta", {}))
    blocks = b.blocks(ast["blocks"], 1, "BodyText")
    if b.made:
        blocks += b.references()
    return Document(meta, blocks, b.ctx)
