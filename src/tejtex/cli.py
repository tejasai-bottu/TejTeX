import argparse
import logging
import sys

from . import PANDOC_VERSION, __version__
from .compiler import compile_file
from .config import Config
from .errors import Exit, TejtexError

log = logging.getLogger("tejtex")


def positive(s):
    n = int(s)
    if n <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return n


def parser():
    p = argparse.ArgumentParser(prog="tejtex", description="Compile LaTeX into native, editable Word documents.")
    p.add_argument("--version", action="version", version=f"tejtex {__version__} (pandoc {PANDOC_VERSION})")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("compile", help="compile a .tex file to .docx")
    c.add_argument("src", help="main .tex file")
    c.add_argument("-o", "--output", help="output .docx file (default: next to the input)")
    c.add_argument("--pandoc", default=Config.pandoc, help="pandoc executable (default: %(default)s)")
    c.add_argument("--timeout", type=positive, default=Config.timeout, help="pandoc time limit in seconds (default: %(default)s)")
    c.add_argument("--max-memory", type=positive, default=Config.memory, help="pandoc memory limit in MB (default: %(default)s)")
    c.add_argument("--root", help="project root; included files and images are resolved relative to it and must stay inside it (default: folder of the input)")
    g = c.add_mutually_exclusive_group()
    g.add_argument("-v", "--verbose", action="store_true", help="show debug messages")
    g.add_argument("-q", "--quiet", action="store_true", help="show errors only")
    return p


def setup_log(args):
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("tejtex: %(levelname)s: %(message)s"))
    log.handlers.clear()
    log.addHandler(h)
    log.setLevel(level)


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.cmd is None:
        p.print_help(sys.stderr)
        return Exit.USAGE
    setup_log(args)
    cfg = Config(pandoc=args.pandoc, timeout=args.timeout, memory=args.max_memory, root=args.root)
    try:
        out = compile_file(args.src, args.output, cfg)
    except TejtexError as e:
        log.error(e)
        return e.code
    except Exception:
        log.exception("internal error")
        return Exit.INTERNAL
    log.info("wrote %s", out)
    return Exit.OK
