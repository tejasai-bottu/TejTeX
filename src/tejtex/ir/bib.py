import re
import unicodedata

from .nodes import TextRun

ACCENTS = {
    '"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304", ".": "\u0307",
    "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a",
}
SYMBOLS = {
    "ss": "ß", "o": "ø", "O": "Ø", "aa": "å", "AA": "Å", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ",
    "l": "ł", "L": "Ł", "i": "ı", "j": "ȷ", "LaTeX": "LaTeX", "TeX": "TeX", "textendash": "–", "textemdash": "—",
    "&": "&", "%": "%", "$": "$", "_": "_", "#": "#", "{": "{", "}": "}", " ": " ", "\\": " ",
}
ACCENT = re.compile(r"\\([\"'`^~=.]|[uvHckr](?![A-Za-z]))\s*(?:\{\s*(\\?[A-Za-z])\s*\}|(\\?[A-Za-z]))")
ENTRY = re.compile(r"@\s*(\w+)\s*\{")
COMMAND = re.compile(r"\\([A-Za-z]+\s*|.)")
SORTED = {"plain", "abbrv", "alpha", "acm", "siam", "apalike", "plainnat", "abbrvnat", "amsplain", "amsalpha", "abstract"}


def sentence(s):
    out = ""
    d = 0
    keep = True
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and d == 0:
            m = re.match(r"\\([A-Za-z]+|.?)", s[i:])
            out += m[0]
            i += len(m[0])
            keep = False
            continue
        if c == "{":
            d += 1
            keep = False
        elif c == "}":
            d -= 1
        elif d == 0 and not c.isspace():
            c = c if keep else c.lower()
            keep = c == ":"
        out += c
        i += 1
    return out


def ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def accent(m):
    base = m[2] or m[3]
    base = {"\\i": "i", "\\j": "j"}.get(base, base)
    return unicodedata.normalize("NFC", base + ACCENTS[m[1]])


def decode(s):
    s = ACCENT.sub(accent, s)
    s = COMMAND.sub(lambda m: SYMBOLS.get(m[1].strip() or m[1], ""), s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”").replace("~", "\u00a0")
    return re.sub(r"[ \t\r\n]+", " ", s).strip()


def group(text, i):
    d = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            d += 1
        elif text[j] == "}":
            d -= 1
            if d == 0:
                return text[i + 1:j], j + 1
    return text[i + 1:], len(text)


def value(text, i, macros):
    out = ""
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        c = text[i]
        if c == "{":
            v, i = group(text, i)
        elif c == '"':
            j = i + 1
            d = 0
            while j < len(text) and not (text[j] == '"' and d == 0):
                d += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            v, i = text[i + 1:j], j + 1
        else:
            m = re.match(r"[^\s,#}]+", text[i:])
            if not m:
                break
            w = m[0]
            v = macros.get(w.lower(), w)
            i += len(w)
        out += v
        while i < len(text) and text[i].isspace():
            i += 1
        if i < len(text) and text[i] == "#":
            i += 1
            continue
        break
    return out, i


def fields(body, macros):
    out = {}
    i = 0
    while i < len(body):
        m = re.compile(r"\s*,?\s*([A-Za-z][\w:-]*)\s*=\s*").match(body, i)
        if not m:
            break
        v, i = value(body, m.end(), macros)
        out[m[1].lower()] = v
    return out


def parse(text):
    macros = {"jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May", "jun": "June",
              "jul": "July", "aug": "August", "sep": "September", "oct": "October", "nov": "November", "dec": "December"}
    out = []
    i = 0
    while True:
        m = ENTRY.search(text, i)
        if not m:
            break
        kind = m[1].lower()
        body, i = group(text, m.end() - 1)
        if kind in ("comment", "preamble"):
            continue
        if kind == "string":
            for k, v in fields(body, macros).items():
                macros[k] = v
            continue
        key, _, rest = body.partition(",")
        key = key.strip()
        if key:
            out.append({"type": kind, "key": key, "fields": fields(rest, macros)})
    return out


def split(s):
    out = [""]
    d = 0
    for w in re.split(r"(\{|\}|\s+and\s+)", s):
        if w == "{":
            d += 1
        elif w == "}":
            d -= 1
        if d == 0 and re.fullmatch(r"\s+and\s+", w or ""):
            out.append("")
        else:
            out[-1] += w
    return [x.strip() for x in out if x.strip()]


def person(s):
    if s.startswith("{") and s.endswith("}") and group(s, 0)[1] == len(s):
        return decode(s), decode(s)
    if "," in s:
        last, _, first = s.partition(",")
        return decode(f"{first.strip()} {last.strip()}"), decode(last)
    words = s.split()
    return decode(s), decode(words[-1]) if words else ""


def people(s):
    names = [person(x)[0] for x in split(s)]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


def family(e):
    f = e["fields"]
    who = split(f.get("author") or f.get("editor") or "")
    return ascii(person(who[0])[1]) if who else ""


def order(entries, cited, style):
    keys = {e["key"]: e for e in entries}
    if "*" in cited:
        chosen = list(entries)
    else:
        chosen = [keys[k] for k in dict.fromkeys(cited) if k in keys]
    year = lambda e: decode(e["fields"].get("year", ""))
    title = lambda e: ascii(decode(e["fields"].get("title", "")))
    if style == "nty":
        chosen.sort(key=lambda e: (family(e), title(e), year(e)))
    elif style in SORTED:
        chosen.sort(key=lambda e: (family(e), year(e), title(e)))
    else:
        rank = {k: i for i, k in enumerate(dict.fromkeys(cited))}
        chosen.sort(key=lambda e: rank.get(e["key"], len(rank)))
    return chosen


ORDINAL = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
WHOLE = {"book", "phdthesis", "mastersthesis", "manual", "proceedings"}
INSIDE = {"inproceedings", "conference", "incollection", "inbook"}


def join(*xs):
    return ", ".join(x for x in xs if x)


def runs(e, case=False):
    f = {k: decode(v) for k, v in e["fields"].items()}
    t = e["type"]
    if case and f.get("title") and t not in WHOLE:
        f["title"] = decode(sentence(e["fields"]["title"]))
    if case and f.get("edition"):
        f["edition"] = f["edition"].lower()
    seg = []
    if f.get("author"):
        seg.append((people(e["fields"]["author"]) + ". ", False))
    if f.get("title"):
        seg += [(f["title"], t in WHOLE), (". ", False)]
    pages = re.sub(r"\s*[-–]+\s*", "–", f.get("pages", ""))
    year = f.get("year", "")
    if t == "article":
        vol = f.get("volume", "") + (f"({f['number']})" if f.get("number") else "")
        page = ("pages " if re.search(r"[–,+]", pages) else "page ") + pages if pages else ""
        rest = join(vol + (":" + pages if vol and pages else ""), "" if vol else page, year)
        if f.get("journal"):
            seg.append((f["journal"], True))
            rest = ", " + rest if rest else ""
        seg.append((rest + ".", False))
    elif t in INSIDE:
        seg.append(("In ", False))
        if f.get("editor"):
            many = len(split(e["fields"]["editor"])) > 1
            seg.append((people(e["fields"]["editor"]) + (", editors, " if many else ", editor, "), False))
        seg.append((f.get("booktitle", ""), True))
        seg.append(((", pages " + pages if pages else "") + ".", False))
        rest = join(f.get("publisher", ""), year)
        if rest:
            seg.append((" " + rest + ".", False))
    elif t in ("phdthesis", "mastersthesis"):
        seg.append((join("PhD thesis" if t == "phdthesis" else "Master's thesis", f.get("school", ""), year) + ".", False))
    elif t == "techreport":
        seg.append((join(("Technical Report " + f.get("number", "")).strip(), f.get("institution", ""), year) + ".", False))
    elif t == "book":
        ed = f.get("edition", "")
        if ed.isdigit() and 0 < int(ed) < len(ORDINAL):
            ed = ORDINAL[int(ed)]
        seg.append((join(f.get("publisher", ""), ed + " edition" if ed else "", year) + ".", False))
    else:
        rest = join(f.get("howpublished", ""), year)
        if rest:
            seg.append((rest + ".", False))
    if f.get("note"):
        seg.append((" " + f["note"] + ".", False))
    out = [TextRun(x, italic=i) for x, i in seg if x and x != "."]
    if out:
        out[-1].text = out[-1].text.rstrip()
    return out, f.get("url", "")
