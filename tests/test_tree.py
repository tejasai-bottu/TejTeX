import copy

from tejtex import tree


def s(x):
    return {"t": "Str", "c": x}


def plain(x):
    return {"t": "Plain", "c": [s(x)]}


A = ["", [], []]
CELL = [A, {"t": "AlignDefault"}, 1, 1, [plain("cell")]]
DOC = {
    "pandoc-api-version": [1, 23, 1, 1],
    "meta": {},
    "blocks": [
        {"t": "Header", "c": [1, A, [s("h")]]},
        {"t": "Para", "c": [s("p"), {"t": "Space"}, {"t": "Note", "c": [plain("note")]}]},
        {"t": "BulletList", "c": [[plain("b1")], [plain("b2")]]},
        {"t": "OrderedList", "c": [[1, {"t": "Decimal"}, {"t": "Period"}], [[plain("o1")]]]},
        {"t": "DefinitionList", "c": [[[s("term")], [[plain("def")]]]]},
        {"t": "Figure", "c": [A, [None, [plain("cap")]], [plain("fig")]]},
        {"t": "Table", "c": [A, [None, [plain("tcap")]], [], [A, [[A, [CELL]]]], [[A, 0, [], [[A, [CELL]]]]], [A, []]]},
        {"t": "Para", "c": [{"t": "Cite", "c": [[{"citationId": "k", "citationPrefix": [s("pre")], "citationSuffix": [], "citationMode": {"t": "NormalCitation"}, "citationNoteNum": 0, "citationHash": 0}], []]}]},
        {"t": "Div", "c": [A, [{"t": "Para", "c": [{"t": "Span", "c": [A, [s("span")]]}]}]]},
        {"t": "HorizontalRule"},
    ],
}


def strs(doc):
    return sorted(lst[i]["c"] for lst, i in tree.each(doc["blocks"]) if lst[i]["t"] == "Str")


def test_each_reaches_every_node():
    assert strs(DOC) == sorted(["h", "p", "note", "b1", "b2", "o1", "term", "def", "cap", "fig", "tcap", "cell", "cell", "pre", "span"])


def test_each_allows_replacement():
    doc = copy.deepcopy(DOC)
    for lst, i in tree.each(doc["blocks"]):
        if lst[i]["t"] == "Str" and lst[i]["c"] == "h":
            lst[i] = {"t": "Emph", "c": [s("new")]}
    assert "new" in strs(doc)
    assert "h" not in strs(doc)


def test_check_accepts_valid_tree():
    assert tree.check(DOC) == []


def test_check_finds_problems():
    assert tree.check({"pandoc-api-version": [1, 22], "blocks": []}) == ["unsupported pandoc-api-version"]
    doc = copy.deepcopy(DOC)
    doc["blocks"].append({"t": "Bogus", "c": []})
    doc["blocks"].append({"t": "Para"})
    doc["blocks"].append({"t": "Para", "c": [{"t": "Link", "c": [A, [], ["tejtex-0a1b2c3d:1", ""]]}]})
    doc["blocks"].append({"t": "Div", "c": [["", ["tejtex-placeholder"], []], []]})
    out = tree.check(doc)
    assert len(out) == 4
    assert out[0].startswith("unknown node")
