"""Static HTML vs browser on a corpus of real pages: link recall, auto-mode decision, time.

Usage: python scripts/bench.py [URL ...]
"""
import sys
import time
from urllib.parse import urlparse

import coursekeep

CORPUS = [
    "https://themodernsoftware.dev/fall2025",                     # Next.js, tabs
    "https://cs231n.github.io/",                                  # Jekyll, notes are same-site pages
    "https://web.stanford.edu/class/cs224n/",                     # static, PDF slides
    "https://stanford-cs336.github.io/spring2025/",               # GitHub Pages
    "https://pdos.csail.mit.edu/6.824/schedule.html",             # big static table
    "https://missing.csail.mit.edu/",                             # Jekyll
    "https://rail.eecs.berkeley.edu/deeprlcourse/",               # Google Slides/PDF
    "https://cs50.harvard.edu/x/2024/weeks/0/",                   # slides + videos
    "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/lecture-notes/",
    "https://course.fast.ai/",                                    # Quarto
    "https://introtodeeplearning.com/",                           # MIT 6.S191
    "https://huggingface.co/learn/llm-course/chapter1/1",         # Svelte SSR
    "https://csdiy.wiki/",                                        # Chinese, MkDocs
    "https://karpathy.github.io/2015/05/21/rnn-effectiveness/",   # blog
    "https://lilianweng.github.io/posts/2023-06-23-agent/",       # blog
    "https://www.ruanyifeng.com/blog/2019/09/react-hooks.html",   # Chinese blog
]


def materials(links, page):
    host = urlparse(page).netloc
    return {coursekeep.download_url(l["url"].split("#")[0]) for l in links
            if l["url"].split("#")[0] != page and coursekeep.plan({**l, "url": l["url"].split("#")[0]}, host) != "skip"}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = []
    for url in sys.argv[1:] or CORPUS:
        try:
            t = time.time(); final, _, sl, _, _ = coursekeep.collect(url, "never"); ts = time.time() - t
            r = coursekeep.session().get(url, timeout=30)
            _, links, soup = coursekeep.parse_links(r.content, r.url)
            why = coursekeep.needs_browser(soup, links)
            t = time.time(); _, _, bl, _, _ = coursekeep.collect(url, "always"); tb = time.time() - t
        except Exception as e:
            print(f"{url}: {str(e)[:100]}")
            continue
        s, b = materials(sl, final), materials(bl, final)
        recall = len(s & b) / len(b) if b else 1.0
        # Judge on files/videos only: browser-only *pages* are mostly injected ads, widgets and site chrome.
        need = any(coursekeep.looks_material(u) or coursekeep.plan({"url": u}, "") == "list" for u in b - s)
        verdict = "ok" if bool(why) == need else ("MISSED (static lost files)" if need else "wasted browser")
        rows.append((urlparse(url).netloc + urlparse(url).path[:25], len(s), len(b), recall, why or "-", ts, tb, verdict))
        print(f"{rows[-1][0]:50} static {len(s):4}  browser {len(b):4}  recall {recall:4.0%}  "
              f"{ts:4.1f}s vs {tb:4.1f}s  auto: {why or 'static'} -> {verdict}")
        for u in sorted(b - s)[:5]:
            print(f"      only in browser: {u}")
    if "p" in coursekeep._pw:
        coursekeep._pw["p"].stop()
    ok = sum(r[-1] == "ok" for r in rows)
    print(f"\nauto mode right on {ok}/{len(rows)} pages; static total {sum(r[5] for r in rows):.1f}s, "
          f"browser total {sum(r[6] for r in rows):.1f}s")


if __name__ == "__main__":
    main()
