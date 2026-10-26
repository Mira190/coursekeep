# Changelog

Versions follow [Semantic Versioning](https://semver.org). The version is set in `scripts/coursekeep.py` (`__version__`).

## 1.0.1 - 2026-10-27

Security fixes.

- Programs are never saved. A server could answer a "slides.pdf" link with `setup.exe` and it was kept as a runnable file.
- Saved files carry the "downloaded from the internet" tag (Windows Zone.Identifier, macOS quarantine), like browser downloads, so Office opens them in Protected View.
- A linked page that is huge or never ends now fails after 20 MB / 2 minutes instead of filling memory and stalling the run.
- Web app: page text in progress lines can no longer change which folder the app opens or zips; a non-numeric size limit is rejected instead of crashing the request.
- `index.md`: link labels from the page are escaped, so they can't turn into clickable links in a Markdown viewer.
- The apps are now built from pinned dependency versions, and each build is smoke-tested before it is published.

## 1.0.0 - 2026-10-27

First release.

- One command, agent skill or local web app: paste a course or blog URL, get every slide deck, PDF, doc and article sorted by section and type, with an `index.md` of what was saved, linked or failed and why.
- Static HTML first, a real browser only when the page needs JavaScript.
- Share links rewritten to real downloads (Google Slides/Docs/Sheets, Drive, Colab, GitHub, arXiv, Dropbox).
- Identical files stored once; reruns fetch only new items, retry failures and resume cancelled runs.
- Junk pages (JavaScript shells, soft 404s, GitHub page chrome) are retried or reported, never saved.
- Safety: links on a public page cannot reach your local network; `--depth` follows robots.txt; at most 4 downloads per site.
- Web app in English and Chinese, WCAG 2.1 AA, Windows and macOS builds that need no Python.
