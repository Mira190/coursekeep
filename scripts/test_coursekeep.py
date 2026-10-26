from coursekeep import NeedsBrowser, check_text, download_url, link_density, norm_url, readme_urls, label, needs_browser, parse_links, plan, raw_urls, safe

H = "themodernsoftware.dev"
L = lambda url, nav=False: {"url": url, "nav": nav}
assert plan(L("https://themodernsoftware.dev/fall2025", nav=True), H) == "skip"
assert plan(L("https://themodernsoftware.dev/notes/lecture1"), H) == "get"  # same-site content page -> article
assert plan(L("https://themodernsoftware.dev/slides/l1.pdf", nav=True), H) == "get"
assert plan(L("https://www.warp.dev"), H) == "skip"
assert plan(L("https://www.linkedin.com/in/x"), H) == "skip"
assert plan(L("https://www.youtube.com/watch?v=abc"), H) == "list"
assert plan(L("https://drive.google.com/drive/folders/abc"), H) == "list"
assert plan(L("https://arxiv.org/pdf/2405.13565"), H) == "get"
assert plan(L("mailto:a@b.c"), H) == "skip"
assert plan(L("https://ocw.mit.edu/x/lec1.mp4"), H) == "list"
assert plan({"url": "https://disqus.com/embed/comments/?x=1", "embed": True}, H) == "skip"
assert plan({"url": "https://blog.example/cited-post", "ref": True}, H) == "skip"
assert plan({"url": "https://arxiv.org/abs/1", "ref": True}, H) == "get"
assert plan({"url": "https://docs.google.com/presentation/d/K/embed", "embed": True}, H) == "get"

assert download_url("https://docs.google.com/presentation/d/AB-c_1/edit?usp=sharing") == \
    "https://docs.google.com/presentation/d/AB-c_1/export/pptx"
assert download_url("https://docs.google.com/presentation/d/e/2PACX-1/pub") == "https://docs.google.com/presentation/d/e/2PACX-1/pub"
assert download_url("https://drive.google.com/file/d/XYZ/view").endswith("id=XYZ&export=download&confirm=t")
assert download_url("https://colab.research.google.com/drive/1aB-c?usp=sharing").endswith("id=1aB-c&export=download&confirm=t")
assert download_url("https://github.com/a/b/blob/master/w3/x.md") == "https://raw.githubusercontent.com/a/b/master/w3/x.md"
assert download_url("https://colab.research.google.com/github/a/b/blob/main/n.ipynb") == "https://raw.githubusercontent.com/a/b/main/n.ipynb"
assert download_url("https://arxiv.org/abs/2405.13565v2") == "https://arxiv.org/pdf/2405.13565v2"
assert download_url("https://www.dropbox.com/s/k/f.pdf?dl=0") == "https://www.dropbox.com/s/k/f.pdf?dl=1"

line = "Mon 9/29: Building a coding agent from scratch - Slides - Completed Exercise"
assert label({"text": "Slides", "parent": line, "url": ""}) == "Mon 9/29: Building a coding agent from scratch - Slides"
assert label({"text": "Completed Exercise", "parent": line, "url": ""}) == \
    "Mon 9/29: Building a coding agent from scratch - Completed Exercise"
assert label({"text": "MCP Introduction", "parent": "MCP Introduction", "url": ""}) == "MCP Introduction"
assert label({"text": "", "parent": "", "url": "https://x.org/a/Lec%201.pdf"}) == "Lec 1.pdf"
assert safe('a/b:c*?"<>|  d. ') == "a b c d"
assert safe("Mon 9/29: Building a coding agent from scratch - Completed Exercise", 40) == "Mon 9 29 Building a…- Completed Exercise"
assert len(safe("x" * 200, 40)) == 40

page = """<html><head><title>C</title><base href="https://c.edu/f/"></head><body>
<nav><a href="/">Home</a></nav><h2>Week 1</h2><ul><li>Intro - <a href="s1.pdf">Slides</a></li></ul>
<h3>Week 2</h3><iframe src="https://docs.google.com/presentation/d/K/embed"></iframe></body></html>"""
title, links, soup = parse_links(page, "https://c.edu/x")
assert title == "C"
assert [(l["url"], l["section"], l["nav"]) for l in links] == [
    ("https://c.edu/", "", True), ("https://c.edu/f/s1.pdf", "Week 1", False),
    ("https://docs.google.com/presentation/d/K/embed", "Week 2", False)]
assert label(links[1]) == "Intro - Slides"
assert needs_browser(soup, links) == "almost no static text (JS app)"
long = page.replace("Intro", "Intro " * 200)
assert needs_browser(*parse_links(long, "https://c.edu/x")[1:][::-1]) == ""
hidden = long.replace("</body>", '<script>self.__next_f.push(["https:\\/\\/arxiv.org\\/abs\\/1234.5678"])</script></body>')
assert needs_browser(*parse_links(hidden, "https://c.edu/x")[1:][::-1]) == "1 material links only inside scripts"
assert "https://arxiv.org/abs/1234.5678" in raw_urls(hidden)
commented = long + '<!-- <a href="https://arxiv.org/abs/1234.5678">old</a> -->'
assert needs_browser(*parse_links(commented, "https://c.edu/x")[1:][::-1]) == ""
tabs = long.replace("<body>", "<body><nav><button>Overview</button><button>Syllabus</button></nav>")
assert needs_browser(*parse_links(tabs, "https://c.edu/x")[1:][::-1]) == "tabs load their content with JS"
menu = long.replace("<body>", '<body><nav><button aria-expanded="false">Menu</button><button><svg/></button></nav>')
assert needs_browser(*parse_links(menu, "https://c.edu/x")[1:][::-1]) == ""
acc = long.replace("<body>", '<body><div role="tab"><a aria-controls="p1">Q</a></div><div id="p1">A</div>')
assert needs_browser(*parse_links(acc, "https://c.edu/x")[1:][::-1]) == ""
assert parse_links('<a href="s w/a b.pdf">x</a>', "https://c.edu/")[1][0]["url"] == "https://c.edu/s%20w/a%20b.pdf"
assert link_density(long) < 0.08 < link_density(page)
assert readme_urls("https://github.com/a/b") [0] == "https://raw.githubusercontent.com/a/b/HEAD/README.md"
assert readme_urls("https://github.com/a/b/tree/master/week1")[0] == "https://raw.githubusercontent.com/a/b/master/week1/README.md"
assert readme_urls("https://github.com/a/b/blob/main/x.py") == [] and readme_urls("https://gitlab.com/a/b") == []
assert norm_url("HTTPS://Example.com:443/a/?utm_source=x&id=2") == "https://example.com/a?id=2"
check_text("A real article. " * 60)
for junk in (None, "", "JavaScript must be enabled in order to use Notion.", "Loading..."):
    try:
        check_text(junk)
        raise AssertionError(f"junk accepted: {junk!r}")
    except NeedsBrowser:
        pass
try:
    check_text("Page not found. Sorry, the page you are looking for does not exist.")
    raise AssertionError("soft 404 accepted")
except RuntimeError as e:
    assert "404" in str(e)
print("ok")
