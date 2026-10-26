# CourseKeep

**Keep every course. One link in, a tidy offline library out.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%20Code%20%7C%20Codex-8A2BE2.svg)
[![tests](https://github.com/Mira190/coursekeep/actions/workflows/tests.yml/badge.svg)](https://github.com/Mira190/coursekeep/actions/workflows/tests.yml)

Paste a course page or blog post URL. CourseKeep downloads every slide deck, PDF, paper, doc and notebook it links to, and saves every reading as clean Markdown. Everything is sorted by week and type. A single index shows what was saved and explains every item that could not be saved.

Use it three ways:
- **Web app**: paste a link into a page on your own computer.
- **Command line.**
- **[Agent Skill](https://agentskills.io)** for **Claude Code**, **Codex** and other skill-compatible agents.

```
downloads/CS146S The Modern Software Developer - Fall 2025 - Stanford University/
├── index.md              ← every item by week: local file, link only, or why it failed
├── _page.md              ← the course page's own text (all tabs)
├── manifest.json         ← what was saved when; reruns fetch only what's new
├── Week 1 Introduction to Coding LLMs and AI Development/
│   ├── slides/   Mon 9 22 Introduction and how an LLM is made - Slides.pptx
│   ├── pdf/      How OpenAI Uses Codex.pdf
│   └── articles/ Prompt Engineering Overview.md
├── Week 2 The Anatomy of Coding Agents/
│   ├── slides/   Mon 9 29 Building a coding agent from scratch - Slides.pptx
│   ├── files/    Mon 9 29 Building a coding agent from scratch - Completed Exercise.py
│   └── articles/ MCP Introduction.md …
└── …
```

## Why CourseKeep

Course materials are scattered: Google Slides, Drive, arXiv, GitHub, a dozen blogs. They often hide behind JavaScript tabs, and they have useless link texts like "Slides". Saving them by hand takes an hour, leaves you with `export.pptx (3).pptx`, and silently misses whatever was private or dead. CourseKeep fixes each of these:

| Pain | What CourseKeep does |
|---|---|
| Links spread over many hosts | Converts share links into real files: Google Slides → .pptx, Docs → .pdf, Sheets → .xlsx, Drive/Colab → file, arXiv abstract page → PDF, GitHub blob → raw file, Dropbox → direct |
| Content behind JS tabs | Reads static HTML first. A headless browser clicks through the tabs only when the page needs it |
| Meaningless names | Names files after the line they sit on: `Mon 9/29: Building a coding agent - Slides` |
| No structure | Sorts into section folders (taken from the page's headings) and type folders |
| Blogs disappear | Saves the main text as Markdown, without ads or menus |
| Silent gaps | `index.md` gives every failure a reason: private file, dead link, blocked site, too big |
| Junk that looks saved | Empty JavaScript shells, "page not found" pages served as 200, and GitHub's menus are caught: JS pages are re-read in a browser, GitHub folders are saved from their README or Markdown files, and anything still empty is reported, not saved |
| Duplicates | The same file reached through two links, or left over under an older name, is kept once (compared by content) |
| Course updates weekly | Rerun the command: only new items are fetched and marked 🆕. Failed items are retried, and a cancelled run resumes where it stopped |

## Quick start

**Windows, no Python needed:** download `CourseKeep-windows.zip` from [Releases](https://github.com/Mira190/coursekeep/releases), unzip it and double-click `CourseKeep.exe`.

**From source** (Windows, macOS, Linux):

```bash
git clone https://github.com/Mira190/coursekeep
cd coursekeep
pip install -r requirements.txt
python scripts/app.py          # opens CourseKeep in your browser
```

On Windows you can double-click `coursekeep.bat` instead. It checks for Python and installs the requirements on first run.

### The web app

Paste a link and press Enter. That's the whole workflow.

- **While it runs**: you see live progress, with files appearing week by week as they arrive.
- **When it finishes**: you get *Open folder* or *Download .zip*. Results can be filtered by type (slides, PDFs, articles…), and every item that failed comes with a plain-language reason and a link to the original.
- **Courses that update weekly**: they stay under *Recent*, and **Check for new** fetches only what was added.
- **Where files go**: `~/Downloads/CourseKeep` (change it with `--out`).
- **Language**: English or 中文, following your browser. The button in the top right switches it.

The app runs only on your computer, at `127.0.0.1`, and is never reachable from your network. It answers only its own page, and it opens downloaded documents but never runs downloaded programs. Closing it or pressing Cancel also stops the hidden browser it may have started.

### Command line

```bash
python scripts/coursekeep.py https://themodernsoftware.dev/fall2025
```

Playwright is optional. It is only used for pages that build their content with JavaScript, and it drives the Chrome or Edge you already have, so `playwright install` is usually not needed. Without any browser, CourseKeep still finds the slide and PDF links by scanning the page's scripts.

## Use it as an agent skill

The repository root is the skill (it holds `SKILL.md` and `scripts/`). Clone it into your agent's skills folder:

| Agent | Command |
|---|---|
| Claude Code | `git clone https://github.com/Mira190/coursekeep ~/.claude/skills/coursekeep` |
| Codex | `git clone https://github.com/Mira190/coursekeep ~/.agents/skills/coursekeep` |
| Project-local | clone into `.claude/skills/` or `.agents/skills/` inside your repo |

Then ask in plain words, e.g. *"download all the slides and readings from https://themodernsoftware.dev/fall2025"*. The agent runs CourseKeep, reads the index and tells you what was saved and what failed.

## Options

| Flag | Use it when |
|---|---|
| `-o DIR` | Output folder (default `downloads`) |
| `--depth 1` | Slides sit on sub-pages (MIT OCW: lecture page → resource page → PDF). The crawl stays inside the course root |
| `--cookies cookies.txt` | The course needs a login (Canvas, Moodle). Export cookies with a "cookies.txt" browser extension, and never commit that file |
| `--refresh` | Slides were updated after class |
| `--all-links` | For a blog post, also save the pages it cites, not only its files |
| `--max-mb N` | Raise the 100 MB per-file limit |
| `--browser auto/always/never` | Override the automatic browser decision |
| `-j N` | Parallel downloads (default 8) |

Not downloaded, only listed in the index: videos (YouTube, .mp4), Drive folders, Figma, social and discussion sites, ad and comment widgets.

## How it works and how it was measured

1. **Static HTML first, browser only on evidence.** On 26 real course and blog sites (`scripts/bench.py`), static parsing found every file the browser found on 25 of them, and ran about 8× faster (10 s vs 80 s in total). The browser starts only when one of these is true:
   - tabs load their content with JS;
   - the page is an empty JS shell;
   - slide or PDF links appear only inside scripts.

   Missing a file costs more than a few seconds, so this check leans towards using the browser.
2. **Course page or blog post?** Link density separates them: blog posts measured 0.03 to 0.07, course pages 0.09 to 0.54. A post keeps its text and its linked files, not every page it cites.
3. **Trust nothing the server sends.** Each file's header bytes are checked against its extension, so a login page saved as `lecture.pdf` is reported as a failure. Downloads go through a `.part` file. Page encoding is detected from the bytes (servers often declare the wrong charset, which garbles Chinese pages). 429 and 5xx responses are retried with backoff.
4. **Windows-safe names.** Long names are shortened in the middle, so `…- Slides` and `…- Exercise` stay distinct and paths stay under 260 characters. Reserved names like `CON` or `NUL` are prefixed with `_`.
5. **Saved means usable.** Articles are checked after extraction. A JavaScript shell ("please enable JavaScript") is re-read in the browser in a second pass, a "page not found" page served with status 200 counts as a dead link, and a download that is cut off is deleted, not kept.
6. **A good citizen on the network.** Links on a public page may not reach into your own machine or local network: this is checked for every request and every redirect, in the browser too. `--depth` crawling follows robots.txt. Each site gets at most 4 parallel downloads. The User-Agent says `CourseKeep/<version>`.
7. **Downloads are treated as untrusted.** Programs (`.exe`, `.msi`, `.bat`, `.lnk`, `.dmg`, ...) are never saved, even when a "slides.pdf" link turns out to be one. Saved files carry the same "downloaded from the internet" tag a browser adds, so Office opens them in Protected View. Linked pages over 20 MB, or that never finish, are refused. The web app listens on 127.0.0.1 only and answers only its own page.

**Measured on the CS146S course:**
- **Slide recall**: all 25 slide links a person can see on the two course pages are accounted for: 23 saved, 1 deck the owner never shared (reported), 1 on Figma (kept as a link).
- **Article quality**: none of the 47 saved articles is an empty shell.
- **Duplicates**: no file is stored twice.
- **Speed**: a full run takes 15 s; a rerun takes 6 s.

## Limits

- Sites that block automated clients (e.g. some Medium pages) are reported, not bypassed.
- Infinite scroll and "load more" buttons are not handled, and slides that are only images are not turned into text.
- The blog-vs-course threshold was tuned on 26 sites. If it guesses wrong, use `--all-links`.
- GitHub folders without a README are read through the GitHub API, which allows 60 requests an hour without sign-in.
- A link to a GitHub branch (`.../tree/master/...`) saves that branch as it is today, which may be newer than the course.
- The Windows app is not code-signed yet, so Windows SmartScreen asks before the first start. The macOS build is produced by CI but has not been tried on a Mac.

## Development

```bash
python scripts/test_coursekeep.py   # offline unit tests: naming, link rules, junk and soft-404 checks
python scripts/test_integration.py  # offline end-to-end run against a fake course site: dedup, resume, robots.txt, truncation, LAN block, program files, endless pages
python scripts/test_app.py          # offline tests: web app request guards
python scripts/smoke_app.py dist/CourseKeep/CourseKeep.exe  # a packaged app really runs (engine, web app, bundled files)
python scripts/bench.py             # static vs browser on the benchmark sites
python scripts/bench.py URL ...     # ...or on your own
```

CI runs the tests and `ruff` on Windows, macOS and Linux with Python 3.9 and 3.13, and `pip-audit` on the release dependencies. Dependabot proposes dependency and action updates monthly.

**Releasing is automatic.** The version lives only in `__version__` at the top of `scripts/coursekeep.py`. Bump it and add a `## <version> - <date>` entry to [CHANGELOG.md](CHANGELOG.md). When that commit reaches `main`, the release workflow:

1. runs the full test matrix;
2. builds the Windows and macOS apps from the pinned `requirements-build.txt`;
3. smoke-tests each built app;
4. publishes release `v<version>` with the changelog entry as its notes.

A missing changelog entry stops the release. To change a dependency of the app build, edit `requirements-build.in` and re-lock with the command at its top.

## Responsible use

CourseKeep fetches only the links on pages you point it at, and it never bypasses logins or bot protection. Course materials are usually copyrighted: keep downloads for personal study, and respect each site's terms.

## License

[MIT](LICENSE) © 2026 Mira190
