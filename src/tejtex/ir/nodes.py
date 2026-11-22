from dataclasses import dataclass, field, fields, is_dataclass

FMT = ("bold", "italic", "underline", "strike", "sup", "sub", "smallcaps", "code")


@dataclass
class TextRun:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    sup: bool = False
    sub: bool = False
    smallcaps: bool = False
    code: bool = False

    def fmt(self):
        return tuple(getattr(self, k) for k in FMT)


@dataclass
class Break:
    pass


@dataclass
class Math:
    tex: str
    display: bool = False
    numbers: list = field(default_factory=list)


@dataclass
class Citation:
    keys: list
    text: str
    bookmarks: list = field(default_factory=list)
    mode: str = "NormalCitation"
    src: str = ""


@dataclass
class CrossReference:
    label: str
    kind: str
    text: str
    bookmark: str = None
    src: str = ""


@dataclass
class Hyperlink:
    inlines: list
    url: str = None
    rel: str = None
    bookmark: str = None


@dataclass
class Image:
    path: str
    rel: str = None
    media: str = None
    width: str = None
    height: str = None
    alt: str = ""
    src: str = ""


@dataclass
class Footnote:
    number: str
    blocks: list


@dataclass
class Anchor:
    bookmark: str
    label: str


@dataclass
class Placeholder:
    category: str
    element: str
    text: str
    src: str = ""
    inline: bool = False


@dataclass
class Paragraph:
    style: str
    inlines: list


@dataclass
class Heading:
    level: int
    inlines: list
    style: str
    number: str = None
    bookmark: str = None
    label: str = None
    src: str = ""


@dataclass
class ListItem:
    blocks: list
    term: list = field(default_factory=list)


@dataclass
class List:
    kind: str
    items: list
    num: int = None
    level: int = 0
    start: int = 1


@dataclass
class Cell:
    blocks: list
    align: str = None
    rowspan: int = 1
    colspan: int = 1


@dataclass
class Row:
    cells: list


@dataclass
class Table:
    rows: list
    aligns: list
    head: int = 0
    caption: list = field(default_factory=list)
    number: str = None
    bookmark: str = None
    label: str = None
    style: str = "Table"
    src: str = ""


@dataclass
class Figure:
    blocks: list
    caption: list = field(default_factory=list)
    number: str = None
    bookmark: str = None
    label: str = None
    src: str = ""


@dataclass
class Theorem:
    kind: str
    name: str
    blocks: list
    number: str = None
    title: list = field(default_factory=list)
    bookmark: str = None
    label: str = None
    src: str = ""


@dataclass
class BibEntry:
    key: str
    number: str
    inlines: list
    bookmark: str = None


@dataclass
class Bibliography:
    entries: list


@dataclass
class Quote:
    blocks: list


@dataclass
class Container:
    kind: str
    blocks: list
    bookmark: str = None
    label: str = None


@dataclass
class CodeBlock:
    text: str
    style: str = "SourceCode"


@dataclass
class Rule:
    pass


@dataclass
class Meta:
    title: list = field(default_factory=list)
    authors: list = field(default_factory=list)
    date: list = field(default_factory=list)
    abstract: list = field(default_factory=list)


@dataclass
class Document:
    meta: Meta
    blocks: list
    ctx: object = None


def add(v, out):
    if is_dataclass(v) and not isinstance(v, type):
        out.append(v)
    elif isinstance(v, list):
        for x in v:
            add(x, out)


def kids(n):
    out = []
    for f in fields(n):
        add(getattr(n, f.name), out)
    return out


def walk(n):
    stack = [n]
    while stack:
        x = stack.pop()
        yield x
        stack.extend(reversed(kids(x)))


def merge(items):
    out = []
    for x in items:
        if out and isinstance(x, TextRun) and isinstance(out[-1], TextRun) and x.fmt() == out[-1].fmt():
            out[-1].text += x.text
        else:
            out.append(x)
    return out


def tidy(items):
    runs = [x for x in items if isinstance(x, TextRun)]
    if runs:
        first = next((x for x in items if not isinstance(x, Anchor)), None)
        if first is runs[0]:
            first.text = first.text.lstrip()
        if items[-1] is runs[-1]:
            runs[-1].text = runs[-1].text.rstrip()
    return [x for x in items if not (isinstance(x, TextRun) and x.text == "")]


def text(items):
    out = []
    for x in items:
        if isinstance(x, TextRun):
            out.append(x.text)
        elif isinstance(x, Break):
            out.append(" ")
        elif isinstance(x, Math):
            out.append(x.tex.strip())
        elif isinstance(x, (Citation, CrossReference, Placeholder)):
            out.append(x.text)
        elif isinstance(x, Hyperlink):
            out.append(text(x.inlines))
    return "".join(out)


def lines(doc):
    out = []
    stack = list(reversed(doc.blocks))
    while stack:
        b = stack.pop()
        if isinstance(b, Heading):
            s = text(b.inlines)
            out.append(f"{b.number} {s}" if b.number else s)
        elif isinstance(b, Paragraph):
            s = text(b.inlines)
            if s.strip():
                out.append(s)
        elif isinstance(b, (CodeBlock, Placeholder)):
            out.append(b.text)
        elif isinstance(b, Theorem):
            head = b.name + (f" {b.number}" if b.number else "")
            if b.title:
                head += f" ({text(b.title)})"
            out.append(head + ".")
            stack.extend(reversed(b.blocks))
        elif isinstance(b, Bibliography):
            out += [f"[{e.number}] {text(e.inlines)}" for e in b.entries]
        elif isinstance(b, Table):
            cells = [x for r in b.rows for c in r.cells for x in c.blocks]
            stack.extend(reversed(b.caption + cells))
        elif isinstance(b, Figure):
            stack.extend(reversed(b.blocks + b.caption))
        elif isinstance(b, List):
            items = []
            for it in b.items:
                if it.term:
                    items.append(Paragraph("Compact", it.term))
                items += it.blocks
            stack.extend(reversed(items))
        elif isinstance(b, (Quote, Container)):
            stack.extend(reversed(b.blocks))
    return out
