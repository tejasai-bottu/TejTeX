import re

LAYOUT = {
    "vspace", "vspace*", "hspace", "hspace*", "centering", "raggedright", "raggedleft",
    "noindent", "indent", "newpage", "clearpage", "cleardoublepage", "pagebreak",
    "nopagebreak", "linebreak", "nolinebreak", "smallskip", "medskip", "bigskip",
    "vfill", "hfill", "vskip", "hskip", "setlength", "addtolength", "setcounter",
    "addtocounter", "pagestyle", "thispagestyle", "pagenumbering", "geometry",
    "linespread", "onehalfspacing", "doublespacing", "singlespacing", "flushbottom",
    "raggedbottom", "fontsize", "selectfont", "graphicspath", "bibliographystyle",
}
RENDER_ENVS = {"tikzpicture", "pgfpicture", "circuitikz", "forest", "pspicture", "tikzcd"}
RENDER_CMDS = {"tikz"}
MARK = {"tableofcontents", "listoffigures", "listoftables", "printbibliography"}
HANDLED = {"maketitle": "title block is built from \\title, \\author and \\date"}
PARTIAL_ENVS = {"thebibliography": "bibliography kept as plain text; entry keys are kept as anchors"}
PACKAGES = {
    "geometry": "page size and margins are not transferred yet",
    "fancyhdr": "headers and footers are not transferred yet",
    "setspace": "line spacing is not transferred",
    "titlesec": "heading formats are not transferred",
}
NODES = {
    "Plain", "Para", "LineBlock", "CodeBlock", "BlockQuote", "OrderedList", "BulletList",
    "DefinitionList", "Header", "HorizontalRule", "Table", "Figure", "Div",
    "Str", "Emph", "Underline", "Strong", "Strikeout", "Superscript", "Subscript",
    "SmallCaps", "Quoted", "Cite", "Code", "Space", "SoftBreak", "LineBreak", "Math",
    "Link", "Image", "Note", "Span",
}

CMD = re.compile(r"\\([A-Za-z@]+\*?|.)")
ENV = re.compile(r"\\(begin|end)\s*\{([^}]*)\}")


def skip(s):
    t = s.strip()
    if t.startswith("["):
        return t, "partial", "warning", False, "option ignored; the formatting it sets is lost"
    m = ENV.match(t)
    if m:
        env = m[2]
        if env in RENDER_ENVS:
            return env, "render", "warning", True, "needs rendering; a placeholder is inserted"
        if m[1] == "end":
            return None
        return env, "partial", "warning", False, PARTIAL_ENVS.get(env, "environment not recognised; its content is kept")
    m = CMD.match(t)
    name = m[1] if m else t
    el = "\\" + name
    if name in RENDER_CMDS:
        return el, "render", "warning", True, "needs rendering; a placeholder is inserted"
    if name in HANDLED:
        return el, "supported", "info", False, HANDLED[name]
    if name in LAYOUT:
        return el, "unsupported", "info", False, "layout command ignored; Word handles layout"
    if name == "bibitem":
        return el, "partial", "info", True, "entry key kept as an anchor"
    if name in MARK or "{" in t:
        return el, "unsupported", "warning", True, "not supported; a placeholder is inserted"
    return el, "unsupported", "warning", False, "not supported; ignored"


def label(el, cat):
    if cat == "render":
        return f"[TejTeX: {el} needs rendering]"
    return f"[TejTeX: {el} is not supported]"
