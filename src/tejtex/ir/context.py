import re
from dataclasses import dataclass

from .. import caps


@dataclass
class Style:
    id: str
    name: str
    kind: str
    base: str = None
    level: int = None


STYLES = [
    Style("Normal", "Normal", "paragraph"),
    Style("BodyText", "Body Text", "paragraph", "Normal"),
    Style("Compact", "Compact", "paragraph", "BodyText"),
    *[Style(f"Heading{i}", f"heading {i}", "paragraph", "Normal", i) for i in range(1, 7)],
    Style("Title", "Title", "paragraph", "Normal"),
    Style("Author", "Author", "paragraph", "Normal"),
    Style("Date", "Date", "paragraph", "Normal"),
    Style("Abstract", "Abstract", "paragraph", "Normal"),
    Style("Caption", "Caption", "paragraph", "Normal"),
    Style("Figure", "Figure", "paragraph", "Normal"),
    Style("BlockText", "Block Text", "paragraph", "Normal"),
    Style("SourceCode", "Source Code", "paragraph", "Normal"),
    Style("Bibliography", "Bibliography", "paragraph", "Normal"),
    Style("FootnoteText", "footnote text", "paragraph", "Normal"),
    Style("Placeholder", "TejTeX Placeholder", "paragraph", "Normal"),
    Style("Hyperlink", "Hyperlink", "character"),
    Style("VerbatimChar", "Verbatim Char", "character"),
    Style("FootnoteReference", "footnote reference", "character"),
    Style("PlaceholderChar", "TejTeX Placeholder Char", "character"),
    Style("TableNormal", "Normal Table", "table"),
    Style("TableGrid", "Table Grid", "table", "TableNormal"),
    Style("Table", "Table", "table", "TableGrid"),
]


class StyleRegistry:
    def __init__(self):
        self.all = {s.id: s for s in STYLES}
        self.used = []

    def use(self, sid):
        s = self.all[sid]
        if sid not in self.used:
            self.used.append(sid)
            if s.base:
                self.use(s.base)
        return sid


BULLETS = ["•", "–", "∗", "·"]
LATEX = [("decimal", "%1."), ("lowerLetter", "(%1)"), ("lowerRoman", "%1."), ("upperLetter", "%1.")]
FORMATS = {
    "Decimal": "decimal", "Example": "decimal", "LowerAlpha": "lowerLetter",
    "UpperAlpha": "upperLetter", "LowerRoman": "lowerRoman", "UpperRoman": "upperRoman",
}
DELIMS = {"Period": "{}.", "OneParen": "{})", "TwoParens": "({})"}


@dataclass
class Level:
    ilvl: int
    fmt: str
    text: str
    style: str = None


@dataclass
class Abstract:
    id: int
    key: str
    levels: list
    outline: bool = False


@dataclass
class Num:
    id: int
    abstract: int
    level: int
    start: int


def levels(kind, style, delim, shift=0):
    out = []
    for i in range(9):
        k = max(i - shift, 0)
        if kind == "bullet":
            out.append(Level(i, "bullet", BULLETS[k % 4]))
        elif kind == "label":
            out.append(Level(i, "none", style))
        elif style in FORMATS:
            out.append(Level(i, FORMATS[style], DELIMS.get(delim, "{}.").format(f"%{i + 1}")))
        else:
            fmt, pat = LATEX[k % 4]
            out.append(Level(i, fmt, pat.replace("%1", f"%{i + 1}")))
    return out


def counter(style, depth):
    return FORMATS.get(style) or LATEX[depth % 4][0]


class NumberingEngine:
    def __init__(self):
        self.abstracts = {}
        self.nums = []
        self.labels = {}
        self.heading = None

    def abstract(self, kind, style, delim, shift=0):
        key = f"{kind}:{style}:{delim}:{shift}"
        if key not in self.abstracts:
            self.abstracts[key] = Abstract(len(self.abstracts) + 1, key, levels(kind, style, delim, shift))
        return self.abstracts[key]

    def new(self, kind, style, delim, start, level, depth=None):
        a = self.abstract(kind, style, delim, level - depth if depth is not None else 0)
        n = Num(len(self.nums) + 1, a.id, level, start)
        self.nums.append(n)
        return n

    def headings(self):
        if self.heading is None:
            texts = ["%1", "%1.%2", "%1.%2.%3"]
            levels = [Level(i, "decimal", t, f"Heading{i + 1}") for i, t in enumerate(texts)]
            levels += [Level(i, "none", "") for i in range(3, 9)]
            a = Abstract(len(self.abstracts) + 1, "heading", levels, True)
            self.abstracts["heading"] = a
            self.heading = Num(len(self.nums) + 1, a.id, 0, 1)
            self.nums.append(self.heading)
        return self.heading

    def label(self, text, level):
        if text not in self.labels:
            a = self.abstract("label", text, None)
            n = Num(len(self.nums) + 1, a.id, level, 1)
            self.nums.append(n)
            self.labels[text] = n
        return self.labels[text]


@dataclass
class Rel:
    id: str
    kind: str
    target: str
    source: str = None
    external: bool = False


class RelationshipManager:
    def __init__(self):
        self.rels = []
        self.index = {}

    def add(self, key, kind, target, source=None, external=False):
        if key not in self.index:
            r = Rel(f"rTej{len(self.rels) + 1}", kind, target, source, external)
            self.rels.append(r)
            self.index[key] = r
        return self.index[key]

    def image(self, path, ext=None):
        key = "image:" + str(path)
        if key in self.index:
            return self.index[key]
        n = sum(1 for r in self.rels if r.kind == "image") + 1
        return self.add(key, "image", f"media/image{n}{ext or path.suffix.lower()}", str(path))

    def link(self, url):
        return self.add("link:" + url, "hyperlink", url, None, True)


@dataclass
class Target:
    label: str
    kind: str
    number: str
    bookmark: str
    src: str = ""


class ReferenceTracker:
    def __init__(self):
        self.targets = {}
        self.bib = {}
        self.names = set()
        self.dups = []

    def bookmark(self, label, prefix=""):
        base = re.sub(r"[^A-Za-z0-9_]", "_", prefix + label)
        if not base[:1].isalpha():
            base = "L" + base
        name = base[:40]
        n = 1
        while name.casefold() in self.names:
            n += 1
            sfx = f"_{n}"
            name = base[:40 - len(sfx)] + sfx
        self.names.add(name.casefold())
        return name

    def add(self, label, kind, number, src=""):
        if label in self.targets:
            self.dups.append((label, src))
            return None
        t = Target(label, kind, number, self.bookmark(label), src)
        self.targets[label] = t
        return t

    def cite(self, key, number, src=""):
        if key in self.bib:
            self.dups.append((key, src))
            return None
        t = Target(key, "bibitem", number, self.bookmark(key, "bib_"), src)
        self.bib[key] = t
        return t

    def get(self, label):
        return self.targets.get(label)


REFS = re.compile(r"\\(?:[A-Za-z]*ref\*?\s*\{([^}]*)\}|hyperref\[([^\]]*)\])")
CITES = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")
LABELS = re.compile(r"\\label\s*\{([^}]*)\}")


class SourceMap:
    def __init__(self, src):
        self.src = src
        self.text = src.text if src is not None else ""
        self.seen = {}
        self.refs = self.index(REFS)
        self.cites = self.index(CITES)
        self.labels = self.index(LABELS)

    def index(self, rx):
        out = {}
        for m in rx.finditer(self.text):
            names = m[1] if m[1] is not None else m[m.lastindex]
            for name in names.split(","):
                out.setdefault(name.strip(), []).append(m.start())
        return out

    def at(self, i):
        if self.src is None or i is None or i < 0:
            return ""
        return self.src.where(i)

    def nth(self, index, kind, name):
        hits = index.get(name, [])
        k = self.seen.get((kind, name), 0)
        self.seen[(kind, name)] = k + 1
        return self.at(hits[min(k, len(hits) - 1)]) if hits else ""

    def find(self, s):
        return self.at(self.text.find(s)) if s else ""

    def label(self, name):
        return self.nth(self.labels, "label", name)

    def ref(self, label):
        return self.nth(self.refs, "ref", label)

    def cite(self, key):
        return self.nth(self.cites, "cite", key)


class DocumentContext:
    def __init__(self, rep, src):
        self.styles = StyleRegistry()
        self.numbering = NumberingEngine()
        self.rels = RelationshipManager()
        self.refs = ReferenceTracker()
        self.diags = rep
        self.caps = caps
        self.source = SourceMap(src)
