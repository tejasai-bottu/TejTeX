import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def convert(soffice, src, kind, out):
    subprocess.run([soffice, "--headless", "--convert-to", kind, "--outdir", out, str(src)], capture_output=True, timeout=300, check=True)
    return Path(out) / (src.stem + "." + kind)


def count(x, pattern):
    return len(re.findall(pattern, x))


def words(x):
    return set(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", x)))


def items(o):
    root = ElementTree.fromstring(o)
    return sum(1 for li in root.iter(TEXT + "list-item") for k in li if k.tag in (TEXT + "p", TEXT + "h"))


def check(soffice, src):
    with tempfile.TemporaryDirectory() as tmp:
        odt = convert(soffice, src, "odt", tmp)
        pdf = convert(soffice, src, "pdf", tmp)
        o = zipfile.ZipFile(odt).read("content.xml").decode("utf-8")
        d = zipfile.ZipFile(src).read("word/document.xml").decode("utf-8")
        size = pdf.stat().st_size
    marks = set(re.findall(r'<w:bookmarkStart [^>]*w:name="([^"]+)"', d))
    found = set(re.findall(r'<text:bookmark(?:-start)? text:name="([^"]+)"', o))
    inner = re.findall(r'w:anchor="([^"]+)"', d)
    links = re.findall(r'xlink:href="#([^"]+)"', o)
    rows = [
        ("tables", count(d, r"<w:tbl>"), count(o, r"<table:table ")),
        ("column spans", count(d, r"<w:gridSpan "), count(o, r"table:number-columns-spanned=")),
        ("row spans", count(d, r'<w:vMerge w:val="restart"/>'), count(o, r"table:number-rows-spanned=")),
        ("tables with header rows", sum(1 for t in d.split("<w:tbl>")[1:] if "<w:tblHeader/>" in t), count(o, r"<table:table-header-rows>")),
        ("pictures", count(d, r"<w:drawing>"), count(o, r"<draw:image ")),
        ("numbered paragraphs", count(d, r"<w:numPr>"), items(o)),
        ("bookmarks", len(marks), len(marks & found)),
        ("internal links", len(inner), sum(1 for x in links if x in marks)),
        ("external links", count(d, r'<w:hyperlink r:id='), count(o, r'xlink:href="(?:https?|ftp|mailto):')),
    ]
    lost = words(d) - words(o)
    ok = all(a == b for _, a, b in rows) and not lost and size > 0
    print(f"{src.name}: {'OK' if ok else 'DIFFERENT'} (PDF {size} bytes)")
    for name, a, b in rows:
        print(f"  {name:24} docx {a:4}  libreoffice {b:4}{'' if a == b else '  <--'}")
    if lost:
        print("  words missing in LibreOffice:", " ".join(sorted(lost)[:20]))
    return ok


def main(args):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("LibreOffice (soffice) is not on PATH")
        return 2
    results = [check(soffice, Path(a)) for a in args]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
