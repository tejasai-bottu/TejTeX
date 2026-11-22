import json
import logging
import subprocess

from . import PANDOC_VERSION
from .errors import Exit, TejtexError

log = logging.getLogger("tejtex")


def run(cmd, timeout):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except OSError as e:
        raise TejtexError(f"cannot run pandoc ({cmd[0]}): {e.strerror or e}", Exit.TOOLCHAIN)
    except subprocess.TimeoutExpired:
        raise TejtexError(f"pandoc timed out after {timeout}s", Exit.LIMIT)


def parse_version(out):
    lines = out.splitlines()
    parts = lines[0].split() if lines else []
    if len(parts) > 1 and parts[0].startswith("pandoc"):
        return parts[1]
    return None


def version(pandoc, timeout):
    r = run([pandoc, "--version"], timeout)
    return parse_version(r.stdout.decode("utf-8", "replace"))


def check(cfg):
    v = version(cfg.pandoc, cfg.timeout)
    if v != PANDOC_VERSION:
        raise TejtexError(f"pandoc {PANDOC_VERSION} is required, found {v or 'an unknown version'}", Exit.TOOLCHAIN)


def read(src, cfg):
    check(cfg)
    r = run([cfg.pandoc, "-f", "latex", "-t", "json", "--sandbox", str(src)], cfg.timeout)
    err = r.stderr.decode("utf-8", "replace").strip()
    for line in err.splitlines():
        log.debug("pandoc: %s", line)
    if r.returncode != 0:
        msg = f"pandoc failed with exit code {r.returncode}"
        if err:
            msg += f": {err}"
        raise TejtexError(msg, Exit.CONVERT)
    try:
        return json.loads(r.stdout)
    except ValueError:
        raise TejtexError("pandoc returned invalid JSON", Exit.CONVERT)
