import re

from .diag import CATS

BLOCKS = {
    "Plain", "Para", "LineBlock", "CodeBlock", "RawBlock", "BlockQuote", "OrderedList",
    "BulletList", "DefinitionList", "Header", "HorizontalRule", "Table", "Figure", "Div",
}
INLINES = {
    "Str", "Emph", "Underline", "Strong", "Strikeout", "Superscript", "Subscript",
    "SmallCaps", "Quoted", "Cite", "Code", "Space", "SoftBreak", "LineBreak", "Math",
    "RawInline", "Link", "Image", "Note", "Span",
}
BARE = {"HorizontalRule", "Space", "SoftBreak", "LineBreak"}
SIMPLE = {
    "Plain", "Para", "BlockQuote", "Note", "Emph", "Underline", "Strong", "Strikeout",
    "Superscript", "Subscript", "SmallCaps",
}
MARKER = re.compile(r"tejtex-[0-9a-f]{8}:\d+$")


def caption(cap):
    out = [cap[1]]
    if cap[0]:
        out.append(cap[0])
    return out


def lists(n):
    if not isinstance(n, dict):
        return []
    t, c = n.get("t"), n.get("c")
    if t in SIMPLE:
        return [c]
    if t in ("Div", "Span", "Quoted", "Link", "Image"):
        return [c[1]]
    if t == "Header":
        return [c[2]]
    if t in ("LineBlock", "BulletList"):
        return list(c)
    if t == "OrderedList":
        return list(c[1])
    if t == "DefinitionList":
        out = []
        for term, defs in c:
            out.append(term)
            out.extend(defs)
        return out
    if t == "Cite":
        out = []
        for x in c[0]:
            out += [x["citationPrefix"], x["citationSuffix"]]
        return out + [c[1]]
    if t == "Figure":
        return caption(c[1]) + [c[2]]
    if t == "Table":
        out = caption(c[1])
        rows = c[3][1] + c[5][1]
        for b in c[4]:
            rows += b[2] + b[3]
        for r in rows:
            for cell in r[1]:
                out.append(cell[4])
        return out
    return []


def each(blocks):
    stack = [blocks]
    while stack:
        lst = stack.pop()
        if not isinstance(lst, list):
            continue
        for i in range(len(lst)):
            yield lst, i
            stack.extend(lists(lst[i]))


def check(ast):
    if not isinstance(ast, dict) or list(ast.get("pandoc-api-version", []))[:2] != [1, 23]:
        return ["unsupported pandoc-api-version"]
    if not isinstance(ast.get("blocks"), list):
        return ["missing blocks"]
    out = []
    for lst, i in each(ast["blocks"]):
        n = lst[i]
        t = n.get("t") if isinstance(n, dict) else None
        if t not in BLOCKS and t not in INLINES:
            out.append(f"unknown node {str(n)[:60]}")
        elif t not in BARE and "c" not in n:
            out.append(f"{t} has no content")
        elif t == "Link" and MARKER.match(str(n["c"][2][0])):
            out.append("unresolved TejTeX marker")
        elif t in ("Div", "Span") and "tejtex-placeholder" in n["c"][0][1]:
            if dict(n["c"][0][2]).get("category") not in CATS:
                out.append("placeholder without a category")
    return out
