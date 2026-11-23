from tejtex import caps


def test_layout_is_ignored():
    assert caps.skip("\\vspace{1cm}") == ("\\vspace", "unsupported", "info", False, "layout command ignored; Word handles layout")
    assert caps.skip("\\centering")[1:4] == ("unsupported", "info", False)


def test_render():
    k = caps.skip("\\begin{tikzpicture}\n\\draw (0,0);\n\\end{tikzpicture}")
    assert k[:2] == ("tikzpicture", "render")
    assert k[3] is True
    assert caps.skip("\\tikz ")[:2] == ("\\tikz", "render")


def test_environments():
    assert caps.skip("\\begin{foo}")[:2] == ("foo", "partial")
    assert caps.skip("\\end{foo}") is None
    assert caps.skip("\\begin{thebibliography}")[4].startswith("entries are numbered")


def test_options_and_bibitem():
    assert caps.skip("[label=(\\roman*)]")[:2] == ("[label=(\\roman*)]", "partial")
    k = caps.skip("\\bibitem{knuth84}")
    assert k[:2] == ("\\bibitem", "partial")
    assert k[3] is True


def test_unknown_commands():
    assert caps.skip("\\unknown{x}")[1:4] == ("unsupported", "warning", True)
    assert caps.skip("\\foo ")[:4] == ("\\foo", "unsupported", "warning", False)
    assert caps.skip("\\tableofcontents")[3] is True


def test_label():
    assert caps.label("tikzpicture", "render") == "[TejTeX: tikzpicture needs rendering]"
    assert caps.label("\\foo", "unsupported") == "[TejTeX: \\foo is not supported]"
