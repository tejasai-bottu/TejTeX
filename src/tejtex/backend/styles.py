from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

KINDS = {"paragraph": WD_STYLE_TYPE.PARAGRAPH, "character": WD_STYLE_TYPE.CHARACTER, "table": WD_STYLE_TYPE.TABLE}
BUILTIN = {"BlockText", "Bibliography", "FootnoteText", "Hyperlink", "FootnoteReference"}
RED = RGBColor(0xC0, 0x00, 0x00)
BLUE = RGBColor(0x05, 0x63, 0xC1)
MONO = "Consolas"


def look(s):
    sid = s.style_id
    f = s.font
    pf = s.paragraph_format if s.type != WD_STYLE_TYPE.CHARACTER else None
    if sid == "Compact":
        pf.space_before = Pt(2)
        pf.space_after = Pt(2)
    elif sid in ("Author", "Date"):
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_after = Pt(6)
    elif sid == "Abstract":
        pf.left_indent = Inches(0.5)
        pf.right_indent = Inches(0.5)
        f.size = Pt(10)
    elif sid == "Figure":
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.keep_with_next = True
    elif sid == "BlockText":
        pf.left_indent = Inches(0.5)
        pf.right_indent = Inches(0.5)
    elif sid == "SourceCode":
        f.name = MONO
        f.size = Pt(10)
        pf.space_after = Pt(0)
    elif sid == "Bibliography":
        pf.left_indent = Inches(0.5)
        pf.first_line_indent = Inches(-0.5)
    elif sid == "FootnoteText":
        f.size = Pt(10)
        pf.space_after = Pt(0)
    elif sid in ("Placeholder", "PlaceholderChar"):
        f.color.rgb = RED
        f.italic = True
    elif sid == "Hyperlink":
        f.color.rgb = BLUE
        f.underline = True
    elif sid == "VerbatimChar":
        f.name = MONO
    elif sid == "FootnoteReference":
        f.superscript = True


def ensure(d, reg):
    have = {s.style_id: s for s in d.styles}
    made = []
    for sid in reg.used:
        if sid in have:
            continue
        st = reg.all[sid]
        s = d.styles.add_style(st.name, KINDS[st.kind], builtin=sid in BUILTIN)
        s.style_id = sid
        have[sid] = s
        made.append((s, st))
    for s, st in made:
        if st.base in have:
            s.base_style = have[st.base]
        look(s)
    return {s.style_id: s for s in d.styles}
