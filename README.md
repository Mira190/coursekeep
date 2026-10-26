# CourseKeep

**Keep every course. One link in, a tidy offline library out.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%20Code%20%7C%20Codex-8A2BE2.svg)

Paste a course page or blog post URL. CourseKeep downloads every slide deck, PDF, paper, doc and notebook it links to, and saves every reading as clean Markdown. Everything is sorted by week and type. A single index shows what was saved and explains every item that could not be saved.

Use it as a command-line tool, or as an [Agent Skill](https://agentskills.io) in **Claude Code**, **Codex** and other skill-compatible agents.

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
| Course updates weekly | Rerun the command: only new items are fetched and marked 🆕 |

## Quick start

```bash
git clone https://github.com/Mira190/coursekeep
cd coursekeep
pip install -r requirements.txt
python scripts/coursekeep.py https://themodernsoftware.dev/fall2025
```

On Windows you can also double-click `coursekeep.bat` and paste the URL.

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
4. **Windows-safe names.** Long names are shortened in the middle, so `…- Slides` and `…- Exercise` stay distinct and paths stay under 260 characters.

Example: the Fall 2025 run of [CS146S](https://themodernsoftware.dev/fall2025) saved 66 items in 15 s (a rerun takes 6 s). The 7 failures were the course's own dead links, one unshared deck and one site that blocks scripts.

## Limits

- Sites that block automated clients (e.g. some Medium pages) are reported, not bypassed.
- Infinite scroll and "load more" buttons are not handled. Neither are Notion- or Feishu-style apps, or slides that are only images.
- The blog-vs-course threshold was tuned on 26 sites. If it guesses wrong, use `--all-links`.

## Development

```bash
python scripts/test_coursekeep.py   # offline tests
python scripts/bench.py             # static vs browser on the benchmark sites
python scripts/bench.py URL ...     # ...or on your own
```

## Responsible use

CourseKeep fetches only the links on pages you point it at, and it never bypasses logins or bot protection. Course materials are usually copyrighted: keep downloads for personal study, and respect each site's terms.

## License

[MIT](LICENSE) © 2026 Mira190
