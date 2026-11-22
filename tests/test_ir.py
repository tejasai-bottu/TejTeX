import subprocess
import sys

from tejtex import ir


def s(x):
    return {"t": "Str", "c": x}


SP = {"t": "Space"}


def test_flatten_blocks():
    ast = {
        "blocks": [
            {"t": "Header", "c": [1, ["a", [], []], [s("Intro")]]},
            {"t": "Para", "c": [s("Hello"), SP, {"t": "Strong", "c": [s("bold")]}, {"t": "SoftBreak"}, s("text.")]},
            {"t": "BulletList", "c": [[{"t": "Plain", "c": [s("one")]}], [{"t": "Plain", "c": [s("two")]}]]},
            {"t": "OrderedList", "c": [[1, {"t": "Decimal"}, {"t": "Period"}], [[{"t": "Plain", "c": [s("three")]}]]]},
            {"t": "Para", "c": [{"t": "Math", "c": [{"t": "InlineMath"}, "x^2"]}]},
            {"t": "CodeBlock", "c": [["", [], []], "print(1)"]},
            {"t": "Para", "c": [{"t": "RawInline", "c": ["latex", "\\foo"]}]},
        ]
    }
    doc = ir.build(ast)
    assert [b.text for b in doc.blocks] == ["Intro", "Hello bold text.", "one", "two", "three", "x^2", "print(1)"]


def test_empty():
    assert ir.build({"blocks": []}).blocks == []


def test_ir_does_not_import_docx_or_lxml():
    code = "import sys, tejtex.ir; bad = [m for m in ('docx', 'lxml') if m in sys.modules]; print(bad); sys.exit(1 if bad else 0)"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
