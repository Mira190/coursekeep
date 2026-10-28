# Changelog

Versions follow [Semantic Versioning](https://semver.org). The version is set in `scripts/coursekeep.py` (`__version__`).

## Unreleased

Web app usability, from a look at how Firecrawl, ArchiveBox, HTTrack, JDownloader and course downloaders handle the same job (`docs/research.md`).

**Fixes**

- Progress lines from parallel downloads could merge into one line, which garbled an item's name in the web app and undercounted progress.
- "Check for new" now repeats the options a course was kept with. Before, a course kept with sub-pages was rerun without them, and they dropped out of its index.
- Reloading or closing the tab during a download no longer loses it: the page picks the run back up.
- Starting the app twice opens the copy that is already running. On Windows, two copies could share one port before.
- `index.md` escapes HTML in the page title.

**New**

- **Your courses**: built from the download folder instead of the browser's storage, so it survives a new browser or port. You can view a course's last results without downloading again.
- **Live progress**: each file's type, or why it failed, shows as it arrives, plus a running clock.
- **Results**: search (`/`), file sizes, total size and run time.
- **Fixing failures**: *Try again*, *Allow up to 500 MB* for files over the limit, and *Continue* after a cancel.
- **`index.html`** in every course folder: the index as a plain page any browser opens, also inside the zip. No scripts; all page text is escaped.
- **Smaller touches**:
  - "Download everything again" switches itself off after one run.
  - You can drop a link onto the page.
  - On phones, the filter chips scroll sideways.
  - Screen readers no longer announce every progress tick.
- **`report.json`** now records the run's options, each file's size and the run time.

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
