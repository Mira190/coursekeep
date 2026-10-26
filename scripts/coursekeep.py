"""CourseKeep: download every material linked from a page (slides, PDFs, docs, articles), sorted by section and type.

Usage: python scripts/coursekeep.py URL [-o OUT] [--depth N] [--browser auto|always|never] [--cookies cookies.txt] [--refresh]
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import mimetypes
import re
import sys
import threading
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.utils import requote_uri
from urllib3.util.retry import Retry

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
KIND_BY_EXT = {
    **dict.fromkeys([".ppt", ".pptx", ".key", ".odp"], "slides"),
    ".pdf": "pdf",
    **dict.fromkeys([".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".xls", ".xlsx", ".csv", ".ipynb"], "docs"),
    **dict.fromkeys([".zip", ".tar", ".gz", ".7z", ".rar"], "archives"),
    **dict.fromkeys([".mp4", ".mp3", ".mov", ".webm", ".m4a"], "media"),
}
# A login page or error page saved as "lecture.pdf" is worse than a reported failure.
MAGIC = {".pdf": b"%PDF", **dict.fromkeys([".pptx", ".docx", ".xlsx", ".zip"], b"PK"),
         **dict.fromkeys([".ppt", ".doc", ".xls"], b"\xd0\xcf\x11\xe0")}
SKIP_HOSTS = ("linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "kit.com",
              "news.ycombinator.com", "reddit.com", "discord.gg", "discord.com")
LIST_ONLY = ("youtube.com", "youtu.be", "vimeo.com", "bilibili.com", "drive.google.com/drive/folders", "figma.com")
# Share/viewer links -> direct file links. The first match wins.
REWRITES = [
    (r"https://docs\.google\.com/presentation/d/(?!e/)([\w-]+).*", r"https://docs.google.com/presentation/d/\1/export/pptx"),
    (r"https://docs\.google\.com/document/d/(?!e/)([\w-]+).*", r"https://docs.google.com/document/d/\1/export?format=pdf"),
    (r"https://docs\.google\.com/spreadsheets/d/(?!e/)([\w-]+).*", r"https://docs.google.com/spreadsheets/d/\1/export?format=xlsx"),
    (r"https://(?:drive\.google\.com/file/d/|drive\.google\.com/open\?id=|colab\.research\.google\.com/drive/)([\w-]+).*",
     r"https://drive.usercontent.google.com/download?id=\1&export=download&confirm=t"),
    (r"https://(?:github\.com|colab\.research\.google\.com/github)/([^/]+/[^/]+)/blob/(.*)", r"https://raw.githubusercontent.com/\1/\2"),
    (r"https?://arxiv\.org/abs/([^?#]+)", r"https://arxiv.org/pdf/\1"),
    (r"(https://www\.dropbox\.com/.*[?&])dl=0(.*)", r"\1dl=1\2"),
]
# Same walk as parse_links, in the browser: headings and links in document order.
COLLECT_JS = """() => { let sec = ''; const out = [];
  for (const el of document.querySelectorAll('h1,h2,h3,a[href],iframe[src],embed[src]')) {
    if (/^H[123]$/.test(el.tagName)) { sec = el.innerText.trim(); continue; }
    const p = el.closest('li,p,td,dd');
    out.push({url: el.href || el.src, text: (el.innerText || el.title || '').trim(), parent: p ? p.innerText.trim() : '',
              section: sec, nav: !!el.closest('nav,header,footer,[role=navigation]'), embed: el.tagName !== 'A'});
  } return out; }"""
JAR = MozillaCookieJar()
_local, _pw = threading.local(), {}


def safe(s, n=90):
    s = re.sub(r'[\\/:*?"<>|\s]+', " ", s).strip(" .")
    if len(s) > n:  # cut the middle: the tail ("- Slides" vs "- Exercise") is what tells siblings apart
        s = f"{s[:n - 21].rstrip()}…{s[-20:].lstrip()}"
    return s.strip(" .") or "untitled"


def label(link):
    """Short link texts like 'Slides' get the line they sit on as prefix: 'Mon 9/22: Intro ... - Slides'."""
    text, parent = link["text"], link["parent"]
    if not text or text == parent or text not in parent or len(parent) > 200:
        return text or unquote(Path(urlparse(link["url"]).path).name)
    before = re.split(r"\s+[-–|•]\s+", parent.split(text)[0].strip())[0].strip(" -–|:•")
    return f"{before} - {text}" if before else text


def looks_material(url):
    return Path(urlparse(url).path).suffix.lower() in KIND_BY_EXT or any(re.match(p, url) for p, _ in REWRITES)


def plan(link, host):
    """skip | list (record in index only) | get"""
    url, u = link["url"], urlparse(link["url"])
    if u.scheme not in ("http", "https") or u.netloc.endswith(SKIP_HOSTS):
        return "skip"
    if any(h in u.netloc + u.path for h in LIST_ONLY) or KIND_BY_EXT.get(Path(u.path).suffix.lower()) == "media":
        return "list"
    if looks_material(url):
        return "get"
    if link.get("nav") or link.get("embed") or link.get("ref") or u.path in ("", "/"):
        return "skip"  # menus, ad/comment iframes, pages cited by a blog post, bare homepages (sponsors etc.)
    return "get"


def download_url(url):
    for pat, rep in REWRITES:
        if re.match(pat, url):
            return re.sub(pat, rep, url, count=1)
    return url


def session():
    if not hasattr(_local, "s"):
        s = _local.s = requests.Session()
        s.headers.update(UA)
        s.cookies.update(JAR)
        retry = Retry(total=3, connect=1, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.mount("https://", HTTPAdapter(max_retries=retry))
    return _local.s


def parse_links(html, url):
    soup = BeautifulSoup(html, "lxml")
    base = urljoin(url, soup.base["href"]) if soup.base and soup.base.get("href") else url
    sec, links = "", []
    for el in soup.find_all(["h1", "h2", "h3", "a", "iframe", "embed"]):
        if el.name in ("h1", "h2", "h3"):
            sec = el.get_text(" ", strip=True)
        elif href := (el.get("href") or el.get("src") or "").strip():
            p = el.find_parent(["li", "p", "td", "dd"])
            links.append({"url": requote_uri(urljoin(base, href)), "text": el.get_text(" ", strip=True) or el.get("title", ""),
                          "parent": p.get_text(" ", strip=True) if p else "", "section": sec, "embed": el.name != "a",
                          "nav": bool(el.find_parent(["nav", "header", "footer"]) or el.find_parent(attrs={"role": "navigation"}))})
    return (soup.title.get_text(strip=True) if soup.title else ""), links, soup


def raw_urls(text):
    text = text.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    return {u.rstrip(".,;)") for u in re.findall(r"https?://[^\s\"'<>\\`]+", text)}


def needs_browser(soup, links):
    """Why static HTML is not enough, or '' when it is."""
    for el in soup.select("[role=tab], nav button"):
        ctl = el.get("aria-controls") or (el.find(attrs={"aria-controls": True}) or {}).get("aria-controls")
        if ctl and soup.find(id=ctl):
            continue  # its panel is already in the HTML
        if el.name == "button" and (el.has_attr("aria-expanded") or not el.get_text(strip=True)):
            continue  # menu toggles and icon buttons
        return "tabs load their content with JS"
    if sum(len(s.strip()) for s in soup.find_all(string=True) if s.parent.name not in ("script", "style", "noscript")) < 500:
        return "almost no static text (JS app)"
    found, scripts = {l["url"] for l in links}, " ".join(s.string or "" for s in soup.find_all("script"))
    if hidden := [u for u in raw_urls(scripts) if looks_material(u) and u not in found]:
        return f"{len(hidden)} material links only inside scripts"
    return ""


def script_urls(soup, page):
    """No-browser fallback: material URLs inside the page and its same-site scripts (no section info)."""
    texts, host = [page.text], urlparse(page.url).netloc
    for s in soup.find_all("script", src=True):
        src = urljoin(page.url, s["src"])
        if urlparse(src).netloc == host:
            try:
                texts.append(session().get(src, timeout=30).text)
            except requests.RequestException:
                pass
    return sorted({u for t in texts for u in raw_urls(t) if looks_material(u)})


def launch(p):
    for kw in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return p.chromium.launch(**kw)
        except Exception:
            pass
    raise RuntimeError("no browser: run `playwright install chromium` or install Chrome/Edge")


def browser():
    if "ctx" not in _pw:
        from playwright.sync_api import sync_playwright  # optional: only needed for JS-built pages
        _pw["p"] = sync_playwright().start()
        ctx = _pw["ctx"] = launch(_pw["p"]).new_context(user_agent=UA["User-Agent"])
        if len(JAR):
            ctx.add_cookies([{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in JAR])
        ctx.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "media", "font") else r.continue_())
    return _pw["ctx"]


def render(url):
    """Render with JS and click through tabs; return (title, links, html of every tab state)."""
    pg = browser().new_page()
    try:
        pg.goto(url, wait_until="load", timeout=45000)
        try:
            pg.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # ads and analytics can keep the network busy forever
        title, links, htmls = pg.title(), pg.evaluate(COLLECT_JS), [pg.content()]
        # Same filter as needs_browser: visible, labelled, not a menu toggle. Capped so a big sidebar can't eat a minute.
        tabs = pg.locator("[role=tab]:visible, nav button:visible").filter(has_text=re.compile(r"\S"))
        for i in range(min(tabs.count(), 15)):
            try:
                if tabs.nth(i).get_attribute("aria-expanded", timeout=1000) is not None:
                    continue
                tabs.nth(i).click(timeout=1000)
                pg.wait_for_timeout(500)
            except Exception:
                continue
            links += pg.evaluate(COLLECT_JS)
            htmls.append(pg.content())
        return title, links, htmls
    finally:
        pg.close()


def collect(url, mode):
    """Static HTML first; the browser only when the page builds its content with JS."""
    r = session().get(url, timeout=(15, 60))
    r.raise_for_status()
    title, links, soup = parse_links(r.content, r.url)
    htmls = [r.content]
    why = {"never": "", "always": "--browser always"}.get(mode)
    if why is None:
        why = needs_browser(soup, links)
    if why:
        try:
            btitle, blinks, htmls = render(r.url)
            title, links = btitle or title, blinks + links
        except Exception as e:
            why += f"; browser failed ({str(e).splitlines()[0][:80]}), scanned scripts instead"
            links += [{"url": u, "text": "", "parent": "", "section": "_unsorted", "nav": False, "embed": False} for u in script_urls(soup, r)]
    return r.url, title, links, htmls, why


def link_density(html):
    """Share of body text that is link text: blog posts measured 0.03-0.07, course pages 0.09-0.54."""
    soup = BeautifulSoup(html, "lxml")
    for x in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        x.decompose()
    body = soup.body or soup
    return sum(len(a.get_text(" ", strip=True)) for a in body.find_all("a")) / max(len(body.get_text(" ", strip=True)), 1)


def page_text(htmls, url):
    parts = [trafilatura.extract(h, output_format="markdown", include_links=True, url=url) or "" for h in htmls]
    return "\n\n---\n\n".join(dict.fromkeys(t for t in parts if t))


def ext_of(resp, url):
    cd = resp.headers.get("content-disposition", "")
    if m := re.search(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)", cd):
        return Path(unquote(m[1] or m[2])).suffix.lower()
    ctype = resp.headers.get("content-type", "").split(";")[0].strip()
    return Path(urlparse(url).path).suffix.lower() or mimetypes.guess_extension(ctype) or ".bin"


def fetch(job, out, max_mb):
    url, dl, sec, limit = job["url"], download_url(job["url"]), out / job["sec"], max_mb * 1_000_000
    with session().get(dl, timeout=(15, 120), stream=True) as r:
        r.raise_for_status()
        if (size := int(r.headers.get("content-length") or 0)) > limit:
            raise RuntimeError(f"too big ({size // 1_000_000} MB > --max-mb {max_mb}), not downloaded")
        if r.headers.get("content-type", "").startswith("text/html"):
            if dl != url:
                raise RuntimeError("got a web page instead of the file (private or needs login?)")
            md = trafilatura.extract(r.content, output_format="markdown", include_links=True, url=url)
            if not md:
                raise RuntimeError("no main text found")
            path = sec / "articles" / f"{job['name']}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {job['name']}\n\nSource: {url}\n\n{md}\n", encoding="utf-8")
            return path
        ext = ext_of(r, dl)
        chunks = r.iter_content(1 << 16)
        first = next(chunks, b"")
        if (magic := MAGIC.get(ext)) and not first.startswith(magic):
            raise RuntimeError(f"server sent something that is not a {ext} file")
        path = sec / KIND_BY_EXT.get(ext, "files") / f"{job['name']}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")  # no half-written file is mistaken for done on rerun
        with open(tmp, "wb") as f:
            f.write(first)
            for chunk in chunks:
                f.write(chunk)
                if f.tell() > limit:  # servers that send no content-length
                    break
        if tmp.stat().st_size > limit:
            tmp.unlink()
            raise RuntimeError(f"too big (> --max-mb {max_mb}), not downloaded")
        tmp.replace(path)
        return path


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("-o", "--out", default="downloads")
    ap.add_argument("-j", "--threads", type=int, default=8)
    ap.add_argument("--depth", type=int, default=0, help="also follow same-site pages under the URL's folder, N levels")
    ap.add_argument("--browser", choices=("auto", "always", "never"), default="auto")
    ap.add_argument("--cookies", help="cookies.txt (Netscape format) for pages that need a login")
    ap.add_argument("--refresh", action="store_true", help="download again even if already saved (updated slides)")
    ap.add_argument("--all-links", action="store_true", help="also save pages linked from a blog post, not only its files")
    ap.add_argument("--max-mb", type=int, default=100, help="skip files bigger than this (default 100)")
    a = ap.parse_args()
    if a.cookies:
        JAR.load(a.cookies, ignore_discard=True, ignore_expires=True)

    start = urlparse(a.url)
    # Crawl scope = course root, the first two folders of the URL: /courses/6-006-x/pages/notes/ -> /courses/6-006-x/
    root = "/".join(start.path[:start.path.rfind("/") + 1].strip("/").split("/")[:2])
    scope = f"{start.scheme}://{start.netloc}/{root + '/' if root else ''}"
    frontier, pages, links, title, level = [(a.url, "")], {}, [], "", 0
    while frontier and len(pages) < 200:
        nxt = []
        for url, sec in frontier:
            if url in pages:
                continue
            try:
                final, t, found, htmls, why = collect(url, a.browser)
            except Exception as e:
                print(f"[failed] page {url}: {e}")
                continue
            pages[url] = pages[final] = (sec, page_text(htmls, final))
            title = title or t
            # A post's links are references: keep its text and linked files, not every page it cites.
            # max over tab states: a text-only FAQ tab must not make a course page look like a post.
            article = not a.all_links and max(map(link_density, htmls)) < 0.08
            print(f"[page  ] {final} ({len(found)} links{', browser: ' + why if why else ''}"
                  f"{', article: text + files only (--all-links to change)' if article else ''})")
            for link in found:
                link["url"] = link["url"].split("#")[0]
                link["section"] = sec or link["section"]
                link["ref"] = article
                u = urlparse(link["url"])
                if level < a.depth and link["url"].startswith(scope) and not u.query \
                        and not looks_material(link["url"]) and not link.get("embed") \
                        and Path(u.path).suffix.lower() in ("", ".html", ".htm", ".php", ".asp", ".aspx"):
                    nxt.append((link["url"], safe(label(link), 60)))
            links += found
        frontier, level = nxt, level + 1
    if "p" in _pw:
        _pw["p"].stop()
    if not pages:
        sys.exit("Could not open the page.")

    out = Path(a.out) / safe(title, 80)
    out.mkdir(parents=True, exist_ok=True)
    for sec, md in dict(pages.values()).items():
        (out / sec).mkdir(exist_ok=True)
        (out / sec / "_page.md").write_text(f"# {sec or title}\n\n{md}\n", encoding="utf-8")
    mpath = out / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}

    # Windows paths stop at 260 characters unless long paths are enabled.
    room = 250 - len(str(out.resolve()))
    jobs, seen, used = [], set(), set()
    for link in links:
        url, key = link["url"], download_url(link["url"])
        act = "skip" if url in pages else plan(link, start.netloc)
        if act == "skip" or key in seen:
            continue
        seen.add(key)
        sec = safe(link["section"] or "_misc", 60)
        name = base = safe(label(link), max(40, min(90, room - len(sec) - 12)))
        i = 2
        while (sec, name.lower()) in used:
            name, i = f"{base} ({i})", i + 1
        used.add((sec, name.lower()))
        jobs.append({**link, "act": act, "sec": sec, "name": name})
    print(f"{len(jobs)} links to process -> {out}")

    def run(job):
        prev = manifest.get(job["url"])
        if job["act"] == "list":
            return "linked", None
        if prev and not a.refresh and (out / prev["path"]).exists():
            return "exists", out / prev["path"]
        try:
            status, path = "ok", fetch(job, out, a.max_mb)
        except Exception as e:
            status, path = f"failed: {e}"[:160], None
        print(f"[{status[:6]:6}] {job['sec']} / {job['name']}")
        return status, path

    with cf.ThreadPoolExecutor(a.threads) as ex:
        results = list(ex.map(run, jobs))

    today, new = datetime.date.today().isoformat(), 0
    lines, cur = [f"# {title}\n\nSource: {a.url}\n"], None
    order = {}  # browser and static links interleave: group by section, in order of first appearance
    for job, (status, path) in sorted(zip(jobs, results), key=lambda jr: order.setdefault(jr[0]["sec"], len(order))):
        rel = path.relative_to(out).as_posix() if path else None
        is_new = bool(rel) and job["url"] not in manifest
        if rel:
            manifest[job["url"]] = {"path": rel, "first_seen": manifest.get(job["url"], {}).get("first_seen", today)}
        new += is_new
        if job["sec"] != cur:
            cur = job["sec"]
            lines.append(f"\n## {cur}\n")
        lines.append(f"- {'🆕 ' if is_new else ''}{job['name']} — {f'[{rel}](<{rel}>)' if rel else status} — <{job['url']}>")
    (out / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = sum(s.startswith("failed") for s, _ in results)
    print(f"Done: {len(results) - bad} saved/linked ({new} new), {bad} failed. See {out / 'index.md'}")


if __name__ == "__main__":
    main()
