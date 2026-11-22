import posixpath
import re
import zipfile
from io import BytesIO

from lxml import etree

CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAIN = DOC + "officeDocument"
BOOKMARK = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,39}$")
PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def rels_of(xml, part):
    d, f = posixpath.split(part)
    root = xml.get(posixpath.join(d, "_rels", f + ".rels"))
    out = {}
    if root is not None:
        for r in root.iter(PR + "Relationship"):
            target = r.get("Target")
            if r.get("TargetMode") != "External":
                target = posixpath.normpath(target[1:] if target.startswith("/") else posixpath.join(d, target))
            out[r.get("Id")] = (r.get("Type"), target)
    return out


def ids(root, tag, attr):
    return {e.get(W + attr) for e in root.iter(W + tag)} if root is not None else set()


def check(data):
    try:
        z = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        return ["not a ZIP package"]
    out = []
    names = z.namelist()
    if len(names) != len(set(names)):
        out.append("duplicate ZIP entries")
    xml = {}
    for n in names:
        if n.endswith((".xml", ".rels")):
            try:
                xml[n] = etree.fromstring(z.read(n), PARSER)
            except etree.XMLSyntaxError as e:
                out.append(f"{n}: not well-formed XML: {e}")
    ct = xml.get("[Content_Types].xml")
    if ct is None:
        return out + ["[Content_Types].xml is missing"]
    defaults = {e.get("Extension").lower() for e in ct.iter(CT + "Default")}
    overrides = {e.get("PartName") for e in ct.iter(CT + "Override")}
    for n in names:
        if n != "[Content_Types].xml" and "/" + n not in overrides and n.rsplit(".", 1)[-1].lower() not in defaults:
            out.append(f"{n}: no content type")
    for p in sorted(overrides):
        if p[1:] not in names:
            out.append(f"content type declared for missing part {p}")
    if "_rels/.rels" not in xml:
        return out + ["_rels/.rels is missing"]
    for n in names:
        if not n.endswith(".rels") or n not in xml:
            continue
        seen = set()
        for r in xml[n].iter(PR + "Relationship"):
            rid = r.get("Id")
            if rid in seen:
                out.append(f"{n}: duplicate relationship id {rid}")
            seen.add(rid)
        part = posixpath.join(posixpath.dirname(posixpath.dirname(n)), posixpath.basename(n)[:-5])
        for rid, (kind, target) in rels_of(xml, part).items():
            if not target.startswith(("http:", "https:", "mailto:")) and target not in names:
                out.append(f"{n}: {rid} points to missing part {target}")
    main = [t for k, t in rels_of(xml, "").values() if k == MAIN]
    if not main or main[0] not in xml:
        return out + ["main document part is missing"]
    main = main[0]
    doc = xml[main]
    if doc.tag != W + "document" or doc.find(W + "body") is None:
        out.append(f"{main}: not a WordprocessingML document")
    rels = rels_of(xml, main)
    for e in doc.iter():
        for k in ("id", "embed", "link"):
            v = e.get(R + k)
            if v is not None and v not in rels:
                out.append(f"{main}: r:{k}={v} has no relationship")
    parts = {k.rsplit("/", 1)[-1]: xml.get(t) for k, t in rels.values()}
    styles = ids(parts.get("styles"), "style", "styleId")
    for tag in ("pStyle", "rStyle", "tblStyle"):
        for v in ids(doc, tag, "val") - styles:
            out.append(f"{main}: style {v} is not defined")
    numbering = parts.get("numbering")
    nums = ids(numbering, "num", "numId")
    for v in ids(doc, "numId", "val") - nums - {"0"}:
        out.append(f"{main}: numbering {v} is not defined")
    if numbering is not None:
        abstracts = ids(numbering, "abstractNum", "abstractNumId")
        for num in numbering.iter(W + "num"):
            a = num.find(W + "abstractNumId")
            if a is None or a.get(W + "val") not in abstracts:
                out.append(f"numbering {num.get(W + 'numId')} has no abstract definition")
    starts = {}
    for e in doc.iter(W + "bookmarkStart"):
        i, name = e.get(W + "id"), e.get(W + "name") or ""
        if i in starts:
            out.append(f"{main}: bookmark id {i} is used twice")
        if not BOOKMARK.match(name):
            out.append(f"{main}: bookmark name {name!r} breaks Word's rules")
        starts[i] = name.casefold()
    if len(set(starts.values())) != len(starts):
        out.append(f"{main}: bookmark names are not unique")
    ends = ids(doc, "bookmarkEnd", "id")
    for i in sorted(set(starts) ^ ends):
        out.append(f"{main}: bookmark {i} is not paired")
    for v in ids(doc, "hyperlink", "anchor") - {None}:
        if v.casefold() not in set(starts.values()):
            out.append(f"{main}: link to missing bookmark {v}")
    return out
