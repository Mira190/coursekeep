---
name: coursekeep
description: CourseKeep downloads every material linked from a course page, syllabus or blog post (Google Slides as .pptx, PDFs, arXiv papers, Google Docs, notebooks, and reading-list pages as clean Markdown) into a local folder sorted by week/section and type, with an index of what failed and why. Use when the user gives a course, lecture, syllabus or blog URL and wants its slides, PDFs or readings saved offline, downloaded in bulk, or organized.
---

# CourseKeep

One command turns a course page or blog post into a local folder:

```
<out>/<page title>/
  index.md        every material by section: local file, link only, or why it failed (🆕 = new since last run)
  index.html      the same list as a page the user can open in any browser
  _page.md        the page's own text
  manifest.json   what was saved when; a rerun fetches only what is new
  <Week / section>/slides | pdf | docs | articles | files
```

`<skill-dir>` below is the folder that contains this SKILL.md.

## Run

1. Install dependencies once: `pip install -r <skill-dir>/requirements.txt`. Playwright is optional. It drives the user's installed Chrome or Edge and is only needed for pages that load content with JavaScript. If no browser is available, the script falls back to scanning the page's scripts.
2. Run it from the user's working directory, so output lands there:
   ```
   python -X utf8 <skill-dir>/scripts/coursekeep.py "<URL>" -o downloads
   ```
3. Read `<out>/<page title>/index.md` and report back:
   - how many items were saved, new, linked only, and failed;
   - the folder path;
   - every `failed:` line with its reason.

   Do not paste the whole index.

## Pick flags from what the user says

| User says / situation | Flag |
|---|---|
| Slides are on per-lecture sub-pages (MIT OCW style), or "get everything in the course" | `--depth 1` (stays inside the course root) |
| The course is behind a login (Canvas, Moodle) and the user gives you a cookies.txt | `--cookies <file>` |
| "Slides were updated", "download again" | `--refresh` |
| A blog post, but the user wants the cited pages too | `--all-links` |
| Big files wanted (default skips >100 MB) | `--max-mb 500` |

## Reading failures

- `got a web page instead of the file`: the Google/Drive file is not shared publicly. Tell the user. Do not try to work around it.
- `403` / `419`: the site blocks scripts. Report it. Do not try to bypass bot protection.
- `404` / name resolution errors: the course itself links to a dead page.
- `too big`: rerun with a higher `--max-mb` if the user wants that file.
- `no main text found` / `needs JavaScript`: the page stayed empty even in a browser. It is not saved as junk; offer the original link.
- `GitHub API limit reached`: a GitHub folder without a README needs the API (60 requests an hour). Rerun later.
- `blocked a link into your local network`: a public page linked to a private address. This is a safety block; do not work around it.
- `program file (.exe), not downloaded`: the server sent a program (often disguised as a document link). Never download it some other way; tell the user.
- `the page is too big or never finishes loading`: a linked page over 20 MB or endless. Offer the link.

Identical files are stored once, so two links may point to the same file in the index. Reruns fetch only new items, retry failures, and resume a cancelled run.

Videos (YouTube, .mp4), Drive folders and Figma are listed in the index, not downloaded.

Only download from pages the user asked for. Course materials are usually copyrighted, so keep them for the user's personal study.
