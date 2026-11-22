import os
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

from tejtex import PANDOC_VERSION, frontend
from tejtex.errors import TejtexError

FAKE = """
import os, sys, time
args = sys.argv[1:]
if "--version" in args:
    print("pandoc " + os.environ.get("FAKE_VERSION", "3.9"))
    sys.exit(0)
sys.stdin.read()
for a in args:
    if a.startswith("--log="):
        with open(a[6:], "w") as f:
            f.write(os.environ.get("FAKE_LOG", "[]"))
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "fail":
    sys.stderr.write("Error at line 3\\n")
    sys.exit(64)
if mode == "oom":
    sys.stderr.write("pandoc: Heap exhausted;\\n")
    sys.exit(251)
if mode == "slow":
    time.sleep(5)
if mode == "junk":
    print("not json")
    sys.exit(0)
print(os.environ.get("FAKE_AST", '{"pandoc-api-version":[1,23,1,1],"meta":{},"blocks":[]}'))
"""


def skip(msg):
    if os.environ.get("TEJTEX_NO_SKIP"):
        pytest.fail(msg)
    pytest.skip(msg)


@pytest.fixture
def skipper():
    return skip


@pytest.fixture
def fake(tmp_path):
    if os.name == "nt":
        py = tmp_path / "fakepandoc.py"
        py.write_text(FAKE)
        exe = tmp_path / "fakepandoc.bat"
        exe.write_text(f'@"{sys.executable}" "{py}" %*\n')
    else:
        exe = tmp_path / "fakepandoc"
        exe.write_text(f"#!{sys.executable}\n" + FAKE)
        exe.chmod(0o755)
    return str(exe)


@pytest.fixture
def tex(tmp_path):
    f = tmp_path / "doc.tex"
    f.write_text("\\section{A}\nHello.\n", encoding="utf-8")
    return f


@pytest.fixture(scope="session")
def real_pandoc():
    try:
        ok = frontend.version("pandoc", 30) == PANDOC_VERSION
    except TejtexError:
        ok = False
    if not ok:
        skip(f"pandoc {PANDOC_VERSION} is not on PATH")
    return "pandoc"


@pytest.fixture
def tejtex_exe():
    exe = Path(sysconfig.get_path("scripts")) / ("tejtex.exe" if os.name == "nt" else "tejtex")
    if not exe.exists():
        skip(f"tejtex console script not found at {exe}")
    try:
        subprocess.run([str(exe), "--version"], capture_output=True)
    except OSError as e:
        if getattr(e, "winerror", None) == 4551:
            skip("tejtex.exe is blocked by Windows Smart App Control; use python -m tejtex")
        raise
    return str(exe)
