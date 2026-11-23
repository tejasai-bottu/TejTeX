from pathlib import Path

from helpers import W, make, part, style
from tejtex import backend, frontend, ir
from tejtex.backend.check import check
from tejtex.backend.tables import place, widths
from tejtex.config import Config
from tejtex.ir.nodes import Cell, List, ListItem, Paragraph, Row, Table, TextRun

DATA = Path(__file__).parent / "data"


def p(s, st="Compact"):
    return Paragraph(st, [TextRun(s)])


def cell(s, **kw):
    return Cell([p(s)] if s else [], **kw)


def table(rows, aligns=None, **kw):
    n = max(sum(c.colspan for c in r) for r in rows)
    return Table([Row(r) for r in rows], aligns or [None] * n, **kw)


def render(*blocks):
    data = backend.render(make(list(blocks)))
    assert check(data) == []
    return data


def text(x):
    return "".join(t.text or "" for t in x.iter(W + "t"))


def grid(t):
    out = []
    for tr in t.findall(W + "tr"):
        row = []
        for tc in tr.findall(W + "tc"):
            pr = tc.find(W + "tcPr")
            span = pr.find(W + "gridSpan")
            vm = pr.find(W + "vMerge")
            tag = ""
            if span is not None:
                tag += "+" + span.get(W + "val")
            if vm is not None:
                tag += "^" + (vm.get(W + "val") or "continue")
            row.append(text(tc) + tag)
        out.append(row)
    return out


def body(data):
    return list(part(data).find(W + "body"))


def test_table_is_a_native_word_table():
    t = table([[cell("H1"), cell("H2")], [cell("a"), cell("b")]], head=1, caption=[p("Results", "Caption")], number="3")
    data = render(t)
    cap, tbl = body(data)[:2]
    assert cap.tag == W + "p" and text(cap) == "Table 3: Results"
    assert cap.find(f"{W}pPr/{W}keepNext") is not None
    assert tbl.tag == W + "tbl"
    assert tbl.find(f"{W}tblPr/{W}tblStyle").get(W + "val") == "Table"
    assert grid(tbl) == [["H1", "H2"], ["a", "b"]]
    rows = tbl.findall(W + "tr")
    assert rows[0].find(f"{W}trPr/{W}tblHeader") is not None
    assert rows[1].find(f"{W}trPr/{W}tblHeader") is None


def test_merged_cells():
    t = table([
        [cell("G"), cell("Score", colspan=2)],
        [cell("A", rowspan=2), cell("1"), cell("2")],
        [cell("3"), cell("4")],
    ])
    tbl = body(render(t))[0]
    assert grid(tbl) == [["G", "Score+2"], ["A^restart", "1", "2"], ["^continue", "3", "4"]]
    a = tbl.findall(W + "tr")[1].find(W + "tc")
    assert a.find(f"{W}tcPr/{W}vAlign").get(W + "val") == "center"


def test_placement_and_ragged_rows():
    t = table([[cell("a", rowspan=3), cell("b")], [cell("c")], [], [cell("d"), cell("e"), cell("f")]], [None, None])
    cells, nrows, ncols = place(t)
    assert [(r, c, rs, cs) for r, c, rs, cs, _ in cells] == [(0, 0, 3, 1), (0, 1, 1, 1), (1, 1, 1, 1), (3, 0, 1, 1), (3, 1, 1, 1), (3, 2, 1, 1)]
    assert (nrows, ncols) == (4, 3)
    tbl = body(render(t))[0]
    assert grid(tbl) == [["a^restart", "b", ""], ["^continue", "c", ""], ["^continue", "", ""], ["d", "e", "f"]]


def test_alignment():
    t = table([[cell("l"), cell("c"), cell("r"), cell("x", align="left")]], [None, "center", "right", "right"])
    tbl = body(render(t))[0]
    jc = []
    for tc in tbl.iter(W + "tc"):
        j = tc.find(f"{W}p/{W}pPr/{W}jc")
        jc.append(j.get(W + "val") if j is not None else None)
    assert jc == [None, "center", "right", None]


def test_column_widths():
    assert widths([], 3, 9000) == [3000, 3000, 3000]
    assert widths([None, 0.4], 2, 8640) == [5184, 3456]
    assert widths([0.6, 0.5, None], 3, 8640) == [5184, 4320, 720]
    tbl = body(render(table([[cell("a"), cell("b")]], widths=[None, 0.4])))[0]
    assert [g.get(W + "w") for g in tbl.iter(W + "gridCol")] == ["5184", "3456"]
    assert [w.get(W + "w") for w in tbl.iter(W + "tcW")] == ["5184", "3456"]


def test_cell_content():
    lst = List("bullet", [ListItem([p("one")]), ListItem([p("two")])])
    t = table([[Cell([p("first"), p("second")]), Cell([lst]), cell("")]])
    tcs = list(body(render(t))[0].iter(W + "tc"))
    assert [text(x) for x in tcs[0].findall(W + "p")] == ["first", "second"]
    ps = tcs[1].findall(W + "p")
    assert [text(x) for x in ps] == ["one", "two"]
    assert all(x.find(f"{W}pPr/{W}numPr") is not None for x in ps)
    assert len(tcs[2].findall(W + "p")) == 1


def test_nested_table_ends_with_a_paragraph():
    inner = table([[cell("in")]])
    tbl = body(render(table([[Cell([inner]), cell("x")]])))[0]
    tc = tbl.find(f"{W}tr/{W}tc")
    kids = [k.tag for k in tc if k.tag != W + "tcPr"]
    assert kids == [W + "tbl", W + "p"]


def test_adjacent_tables_are_kept_apart():
    data = render(table([[cell("a")]]), table([[cell("b")]]))
    assert [k.tag.replace(W, "") for k in body(data)] == ["tbl", "p", "tbl", "sectPr"]


def test_empty_table_writes_only_its_caption():
    data = render(Table([], [], caption=[p("Nothing", "Caption")], number="1"))
    assert [k.tag.replace(W, "") for k in body(data)] == ["p", "sectPr"]


def test_table_style_has_borders():
    data = render(table([[cell("a")]]))
    s = style(data, "Table")
    assert s.find(W + "basedOn").get(W + "val") == "TableGrid"
    grid_style = style(data, "TableGrid")
    borders = grid_style.find(f"{W}tblPr/{W}tblBorders")
    assert {b.tag.replace(W, "") for b in borders} == {"top", "left", "bottom", "right", "insideH", "insideV"}


def test_tables_corpus(real_pandoc):
    ast, rep, s = frontend.read(DATA / "tables" / "main.tex", Config())
    data = backend.render(ir.build(ast, rep, s, Config()))
    assert check(data) == []
    kids = body(data)
    tbls = [k for k in kids if k.tag == W + "tbl"]
    assert [grid(t) for t in tbls] == [
        [["Group", "Score+2"], ["A^restart", "1", "2"], ["^continue", "3", "4"], ["B", "5", "6"]],
        [["Name", "Notes"], ["Short", "A longer cell that wraps."], ["List", "onetwo"], ["Empty", ""]],
        [["x", "y"], ["z", ""]],
    ]
    assert [[g.get(W + "w") for g in t.iter(W + "gridCol")] for t in tbls] == [["2880"] * 3, ["5184", "3456"], ["4320"] * 2]
    caps = [text(k) for k in kids if k.tag == W + "p" and k.find(f"{W}pPr/{W}pStyle") is not None
            and k.find(f"{W}pPr/{W}pStyle").get(W + "val") == "Caption"]
    assert caps == ["Table 1: Scores by group", "Table 2: Booktabs table"]
    assert [sum(1 for _ in t.iter(W + "tblHeader")) for t in tbls] == [1, 1, 0]
    assert any(text(k) == "Table 1 and Table 2." for k in kids)
    i = kids.index(tbls[1])
    assert kids[i + 1].tag == W + "p" and kids[i + 2] is tbls[2]
