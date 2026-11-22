from dataclasses import dataclass, field

LEAVES = ("Para", "Plain", "Header", "CodeBlock")


@dataclass
class Para:
    text: str


@dataclass
class Doc:
    blocks: list = field(default_factory=list)


def text(x):
    if isinstance(x, list):
        return "".join(text(i) for i in x)
    if not isinstance(x, dict):
        return ""
    t = x.get("t")
    if t == "Str":
        return x["c"]
    if t in ("Space", "SoftBreak", "LineBreak"):
        return " "
    if t in ("Math", "Code", "CodeBlock"):
        return x["c"][1]
    if t in ("RawInline", "RawBlock"):
        return ""
    return text(x.get("c", []))


def leaves(x, out):
    if isinstance(x, list):
        for i in x:
            leaves(i, out)
    elif isinstance(x, dict):
        if x.get("t") in LEAVES:
            out.append(x)
        else:
            leaves(x.get("c", []), out)


def build(ast):
    found = []
    leaves(ast.get("blocks", []), found)
    doc = Doc()
    for b in found:
        s = text(b).strip()
        if s:
            doc.blocks.append(Para(s))
    return doc
