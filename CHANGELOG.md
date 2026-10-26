# Changelog

Versions follow [Semantic Versioning](https://semver.org). The version is set in `scripts/coursekeep.py` (`__version__`).

## 1.0.0 - 2026-10-27

First release.

- One command, agent skill or local web app: paste a course or blog URL, get every slide deck, PDF, doc and article sorted by section and type, with an `index.md` of what was saved, linked or failed and why.
- Static HTML first, a real browser only when the page needs JavaScript.
- Share links rewritten to real downloads (Google Slides/Docs/Sheets, Drive, Colab, GitHub, arXiv, Dropbox).
- Identical files stored once; reruns fetch only new items, retry failures and resume cancelled runs.
- Junk pages (JavaScript shells, soft 404s, GitHub page chrome) are retried or reported, never saved.
- Safety: links on a public page cannot reach your local network; `--depth` follows robots.txt; at most 4 downloads per site.
- Web app in English and Chinese, WCAG 2.1 AA, Windows and macOS builds that need no Python.
