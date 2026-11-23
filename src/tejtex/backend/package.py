import io
import re
import zipfile

import docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT

DROP = {RT.CUSTOM_XML, "http://schemas.microsoft.com/office/2007/relationships/stylesWithEffects"}
APP = (
    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
    b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    b"<Application>TejTeX</Application></Properties>"
)
TERMS = "{http://purl.org/dc/terms/}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LEFTOVERS = [
    W + "proofState", W + "rsids",
    "{http://schemas.microsoft.com/office/word/2010/wordml}docId",
    "{http://schemas.microsoft.com/office/word/2012/wordml}docId",
]
STAMP = (1980, 1, 1, 0, 0, 0)
BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def clean(s):
    return BAD.sub("", s)


def new(title="", authors=""):
    d = docx.Document()
    part = d.part
    for rid, rel in list(part.rels.items()):
        if rel.reltype in DROP:
            part.drop_rel(rid)
    pkg = part.package
    for rid, rel in list(pkg.rels.items()):
        if rel.reltype == RT.THUMBNAIL:
            pkg.rels.pop(rid)
        elif rel.reltype == RT.EXTENDED_PROPERTIES:
            rel.target_part._blob = APP
    cp = d.core_properties
    cp.title = title
    cp.author = authors
    cp.comments = ""
    cp.last_modified_by = ""
    el = cp._element
    for tag in ("created", "modified"):
        x = el.find(TERMS + tag)
        if x is not None:
            el.remove(x)
    st = d.settings.element
    for tag in LEFTOVERS:
        for x in st.findall(tag):
            st.remove(x)
    for x in st.iter(W + "compatSetting"):
        if x.get(W + "name") == "compatibilityMode":
            x.set(W + "val", "15")
    return d


def save(d):
    raw = io.BytesIO()
    d.save(raw)
    out = io.BytesIO()
    with zipfile.ZipFile(raw) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for i in zin.infolist():
            zi = zipfile.ZipInfo(i.filename, STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            zout.writestr(zi, zin.read(i.filename))
    return out.getvalue()
