import re
import secrets
from bisect import bisect_right
from pathlib import Path, PurePosixPath

from .errors import Exit, TejtexError

CS = re.compile(r"\\([A-Za-z@]+\*?|.)", re.S)
ARG = re.compile(r"\s*\{([^{}]*)\}")
OPTARG = re.compile(r"\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
VERB = {"verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "comment"}


def check(root, name):
    if SCHEME.match(name):
        return None, "URLs and drive paths are not allowed"
    if name.startswith(("/", "\\")) or PurePosixPath(name).is_absolute():
        return None, "absolute paths are not allowed"
    p = (root / name).resolve()
    if not p.is_relative_to(root):
        return None, "path leaves the project folder"
    return p, None


def pos(text, off):
    line = text.count("\n", 0, off) + 1
    col = off - text.rfind("\n", 0, off)
    return line, col


def read(p):
    try:
        return p.read_text("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


class Source:
    def __init__(self, root, cfg, rep):
        self.root = root
        self.cfg = cfg
        self.rep = rep
        self.parts = []
        self.segs = []
        self.texts = {}
        self.size = 0
        self.total = 0
        self.used = 0
        self.marks = {}
        self.token = secrets.token_hex(4)
        self.body = None
        self.bibs = []
        self.bibstyle = None
        self.nocite = []
        self.biblatex = False
        self.text = ""
        self.starts = []

    def add(self, s, rel, at):
        if s:
            self.segs.append((self.size, rel, at))
            self.parts.append(s)
            self.size += len(s)

    def mark(self, info, body=""):
        n = len(self.marks) + 1
        self.marks[n] = info
        return "\\href{tejtex-%s:%d}{%s}" % (self.token, n, body)

    def where(self, off):
        i = bisect_right(self.starts, off) - 1
        if i < 0:
            return ""
        start, rel, at = self.segs[i]
        if rel is None:
            return ""
        line, col = pos(self.texts[rel], at + off - start)
        return f"{rel}:{line}:{col}"

    def expand(self, text, rel, depth, chain):
        self.used += 1
        if self.used > self.cfg.files:
            raise TejtexError(f"more than {self.cfg.files} files are included", Exit.LIMIT)
        self.total += len(text)
        if self.total > self.cfg.size:
            raise TejtexError(f"the source is larger than {self.cfg.size} characters", Exit.LIMIT)
        self.texts[rel] = text
        i = start = 0
        n = len(text)
        while i < n:
            c = text[i]
            if c == "%":
                k = text.find("\n", i)
                i = n if k < 0 else k
                continue
            if c != "\\":
                i += 1
                continue
            m = CS.match(text, i)
            if not m:
                break
            name, j = m[1], m.end()
            if name in ("verb", "verb*"):
                k = text.find(text[j], j + 1) if j < n else -1
                i = n if k < 0 else k + 1
                continue
            if name == "begin":
                a = ARG.match(text, j)
                if a and a[1] in VERB:
                    k = text.find("\\end{%s}" % a[1], a.end())
                    i = n if k < 0 else k
                    continue
                if a and a[1] == "document" and self.body is None:
                    self.body = self.size + i - start
            if name in ("bibliography", "addbibresource", "bibliographystyle", "nocite"):
                a = OPTARG.match(text, j)
                if a:
                    self.bib(name, a[1], rel, i)
                    i = a.end()
                    continue
            if name in ("input", "include"):
                a = ARG.match(text, j)
                if a:
                    self.add(text[start:i], rel, start)
                    self.include(name, a[1].strip(), rel, i, depth, chain)
                    i = start = a.end()
                    continue
            i = j
        self.add(text[start:], rel, start)

    def include(self, cmd, name, rel, at, depth, chain):
        line, col = pos(self.texts[rel], at)
        loc = f"{rel}:{line}:{col}"
        el = "\\%s{%s}" % (cmd, name)
        names = [name] if name.endswith(".tex") else [name + ".tex", name]
        p = None
        for nm in names:
            q, why = check(self.root, nm)
            if why:
                return self.reject(el, why, loc, "error")
            if q.is_file():
                p = q
                break
        if p is None:
            return self.reject(el, "file not found", loc, "warning")
        r = p.relative_to(self.root).as_posix()
        if r in chain:
            return self.reject(el, "circular include", loc, "error")
        if depth >= self.cfg.depth:
            raise TejtexError(f"{loc}: includes are nested more than {self.cfg.depth} levels deep", Exit.LIMIT)
        text = read(p)
        if text is None:
            return self.reject(el, "file cannot be read as UTF-8 text", loc, "error")
        self.expand(text, r, depth + 1, chain + [r])

    def bib(self, cmd, arg, rel, at):
        line, col = pos(self.texts[rel], at)
        loc = f"{rel}:{line}:{col}"
        names = [x.strip() for x in arg.split(",") if x.strip()]
        if cmd == "bibliographystyle":
            self.bibstyle = arg.strip()
            return
        if cmd == "nocite":
            self.nocite += names
            return
        if cmd == "addbibresource":
            self.biblatex = True
        for name in names:
            el = "\\%s{%s}" % (cmd, name)
            nm = name if name.endswith(".bib") else name + ".bib"
            p, why = check(self.root, nm)
            if why is None and not p.is_file():
                why = "file not found"
            text = read(p) if why is None else None
            if why is None and text is None:
                why = "file cannot be read as UTF-8 text"
            if why:
                self.rep.add("warning", "unsupported", el, "bibliography not read: " + why, loc)
                continue
            self.total += len(text)
            if self.total > self.cfg.size:
                raise TejtexError(f"the source is larger than {self.cfg.size} characters", Exit.LIMIT)
            self.bibs.append((p.relative_to(self.root).as_posix(), text, loc))

    def reject(self, el, why, loc, level):
        self.rep.add(level, "unsupported", el, "not included: " + why, loc)
        info = {"element": el, "category": "unsupported", "loc": loc, "text": f"[TejTeX: {el} not included]"}
        self.add(self.mark(info), None, 0)


def load(src, root, cfg, rep):
    if not root.is_dir():
        raise TejtexError(f"project root not found: {root}", Exit.FILE)
    p = Path(src).resolve()
    if not p.is_relative_to(root):
        raise TejtexError(f"input file is outside the project root {root}", Exit.FILE)
    text = read(p)
    if text is None:
        raise TejtexError(f"cannot read {src} as UTF-8 text", Exit.FILE)
    s = Source(root, cfg, rep)
    r = p.relative_to(root).as_posix()
    s.expand(text, r, 0, [r])
    s.text = "".join(s.parts)
    s.starts = [x[0] for x in s.segs]
    return s
