import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from . import PANDOC_VERSION, caps, normalize, source, tree
from .diag import Report
from .errors import Exit, TejtexError

log = logging.getLogger("tejtex")
KEY = re.compile(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
TOK = re.compile(r"\\(begin|end)\s*\{([^}]*)\}|\\item(?![A-Za-z])\s*\[|\\[^A-Za-z]|%[^\n]*")
FORM = re.compile(r"(\(?)(\\[A-Za-z]+\*)([.)]?)")
NUMS = {"\\arabic*": "1", "\\alph*": "a", "\\Alph*": "A", "\\roman*": "i", "\\Roman*": "I"}
SPACING = {
    "leftmargin", "rightmargin", "labelsep", "labelwidth", "labelindent", "itemindent", "listparindent",
    "itemsep", "topsep", "parsep", "partopsep", "noitemsep", "nosep", "nolistsep", "align", "widest",
}


def call(cmd, timeout, data=None):
    try:
        return subprocess.run(cmd, input=data, capture_output=True, timeout=timeout)
    except OSError as e:
        raise TejtexError(f"cannot run pandoc ({cmd[0]}): {e.strerror or e}", Exit.TOOLCHAIN)
    except subprocess.TimeoutExpired:
        raise TejtexError(f"pandoc timed out after {timeout}s", Exit.LIMIT)


def parse_version(out):
    lines = out.splitlines()
    parts = lines[0].split() if lines else []
    if len(parts) > 1 and parts[0].startswith("pandoc"):
        return parts[1]
    return None


def version(pandoc, timeout):
    r = call([pandoc, "--version"], timeout)
    return parse_version(r.stdout.decode("utf-8", "replace"))


def check(cfg):
    v = version(cfg.pandoc, cfg.timeout)
    if v != PANDOC_VERSION:
        raise TejtexError(f"pandoc {PANDOC_VERSION} is required, found {v or 'an unknown version'}", Exit.TOOLCHAIN)


def run(text, cfg):
    with tempfile.TemporaryDirectory(prefix="tejtex-") as tmp:
        logf = Path(tmp) / "log.json"
        cmd = [cfg.pandoc, "+RTS", f"-M{cfg.memory}m", "-RTS", "-f", "latex", "-t", "json", "--sandbox", f"--log={logf}"]
        r = call(cmd, cfg.timeout, text.encode("utf-8"))
        err = r.stderr.decode("utf-8", "replace").strip()
        for line in err.splitlines():
            log.debug("pandoc: %s", line)
        if r.returncode == 251:
            raise TejtexError(f"pandoc ran out of memory (limit {cfg.memory} MB)", Exit.LIMIT)
        if r.returncode != 0:
            msg = f"pandoc failed with exit code {r.returncode}"
            if err:
                msg += f": {err}"
            raise TejtexError(msg, Exit.CONVERT)
        try:
            ast = json.loads(r.stdout)
            msgs = json.loads(logf.read_text("utf-8")) if logf.exists() else []
        except ValueError:
            raise TejtexError("pandoc returned invalid JSON", Exit.CONVERT)
        except RecursionError:
            raise TejtexError("the document is nested too deeply", Exit.LIMIT)
    return ast, msgs


def line_starts(text):
    out = [0]
    i = text.find("\n")
    while i >= 0:
        out.append(i + 1)
        i = text.find("\n", i + 1)
    return out


def offset(starts, line, col, size):
    if not line:
        return None
    if line > len(starts):
        return size
    return min(starts[line - 1] + max(col or 1, 1) - 1, size)


def find(text, starts, line, off, c):
    lo = starts[max(min(line, len(starts)) - 1 - c.count("\n"), 0)]
    i = text.rfind(c, lo, off + len(c))
    return (i, i + len(c)) if i >= 0 else None


def tikz_end(text, j):
    n = len(text)
    k = j
    while k < n and text[k].isspace():
        k += 1
    if text.startswith("[", k):
        e = text.find("]", k)
        k = e + 1 if e >= 0 else k
        while k < n and text[k].isspace():
            k += 1
    if text.startswith("{", k):
        d = 0
        for e in range(k, n):
            if text[e] == "{":
                d += 1
            elif text[e] == "}":
                d -= 1
                if d == 0:
                    return e + 1
        return j
    e = text.find(";", k)
    return e + 1 if e >= 0 else j


def package(path, loc, s, rep):
    if not path.endswith(".sty"):
        rep.add("warning", "unsupported", path, "file not loaded", loc)
        return
    name = path[:-4]
    if name in caps.PACKAGES:
        rep.add("info", "unsupported", "package " + name, caps.PACKAGES[name], loc)
    elif (s.root / path).is_file():
        rep.add("warning", "unsupported", "package " + name, "local package not loaded; its macros are not expanded", loc)


def split(t):
    out = [""]
    d = 0
    for ch in t:
        if ch == "," and d == 0:
            out.append("")
            continue
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
        out[-1] += ch
    return [x.strip() for x in out if x.strip()]


def options(c):
    t = c.strip()
    if not (t.startswith("[") and t.endswith("]")):
        return None
    marker = start = None
    rest = False
    for part in split(t[1:-1]):
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        if v.startswith("{") and v.endswith("}"):
            v = v[1:-1].strip()
        if k == "label":
            m = FORM.fullmatch(v)
            if not m or m[2] not in NUMS:
                return None
            if m[1] and m[3] == ")":
                marker = "(" + NUMS[m[2]] + ")"
            elif not m[1] and m[3]:
                marker = NUMS[m[2]] + m[3]
            else:
                return None
        elif k == "start" and v.isdigit():
            start = int(v)
        elif k in SPACING:
            rest = True
        else:
            return None
    if marker is None and start is None:
        return "", "unsupported", "layout options ignored; Word handles layout"
    out = f"[{marker}]" if marker else ""
    if start is not None:
        out += "\\setcounter{enumi}{%d}" % (start - 1)
    msg = "label and start are kept as Word numbering"
    if rest:
        msg += "; layout options are ignored"
    return out, "supported", msg


def after_enumerate(text, a):
    j = text.rfind("\\begin{enumerate}", 0, a)
    return j >= 0 and not text[j + 17:a].strip()


def close(text, i):
    d = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            d += 1
        elif text[j] == "}":
            d -= 1
        elif text[j] == "]" and d == 0:
            return j
    return -1


def items(s):
    out = []
    stack = []
    for m in TOK.finditer(s.text, s.body or 0):
        if m[1] == "begin":
            stack.append(m[2])
        elif m[1] == "end":
            if m[2] in stack:
                while stack.pop() != m[2]:
                    pass
        elif m[0].startswith("\\item") and stack and stack[-1] in ("itemize", "enumerate"):
            j = close(s.text, m.end())
            if j >= 0:
                out.append((m.start(), j + 1, "\\item " + s.mark({"item": True}, s.text[m.end():j])))
    return out


def scan(s, msgs, rep):
    starts = line_starts(s.text)
    body = s.body or 0
    spans = []
    for m in msgs:
        t = m.get("type")
        off = offset(starts, m.get("line"), m.get("column"), len(s.text))
        if t == "SkippedContent":
            c = m.get("contents", "")
            if off is not None and any(a <= off <= b for a, b, _ in spans):
                continue
            sp = find(s.text, starts, m["line"], off, c) if off is not None else None
            loc = s.where(sp[0] if sp else off) if off is not None else ""
            opt = options(c) if sp and after_enumerate(s.text, sp[0]) else None
            if opt:
                r, cat, msg = opt
                rep.add("info", cat, c.strip(), msg, loc)
                if r:
                    spans.append((sp[0], sp[1], r))
                continue
            k = caps.skip(c)
            if k is None:
                continue
            el, cat, level, marked, msg = k
            rep.add(level, cat, el, msg, loc)
            if marked and sp and sp[0] >= body:
                a, b = sp
                if el == "\\tikz":
                    b = tikz_end(s.text, b)
                info = {"element": el, "category": cat, "loc": loc, "text": caps.label(el, cat)}
                if el == "\\bibitem":
                    key = KEY.match(c.strip())
                    info["anchor"] = True
                    info["key"] = key[1] if key else ""
                spans.append((a, b, s.mark(info)))
        elif t == "CouldNotLoadIncludeFile":
            loc = s.where(off) if off is not None else ""
            package(m.get("path", ""), loc, s, rep)
        elif m.get("verbosity") in ("WARNING", "ERROR"):
            loc = s.where(off) if off is not None else ""
            rep.add(m["verbosity"].lower(), "", t, m.get("pretty", t), loc)
    return spans


def apply(text, spans):
    out = []
    last = 0
    for a, b, r in sorted(spans):
        if a < last:
            continue
        out.append(text[last:a])
        out.append(r)
        last = b
    out.append(text[last:])
    return "".join(out)


def read(src, cfg):
    check(cfg)
    src = Path(src)
    root = Path(cfg.root) if cfg.root else src.parent
    rep = Report()
    s = source.load(src, root.resolve(), cfg, rep)
    ast, msgs = run(s.text, cfg)
    spans = scan(s, msgs, rep) + items(s)
    if spans:
        ast, _ = run(apply(s.text, spans), cfg)
    normalize.run(ast, s, rep)
    bad = tree.check(ast)
    if bad:
        raise TejtexError("normalized AST is invalid: " + bad[0], Exit.INTERNAL)
    return ast, rep, s
