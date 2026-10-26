"""End-to-end run of coursekeep.py against a fake course site on localhost (no internet): python scripts/test_integration.py"""
import json
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

import coursekeep

HERE = Path(__file__).resolve().parent
site, out = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
(site / "files").mkdir()
(site / "private").mkdir()
(site / "index.html").write_text("""<html><head><title>Fixture Course</title></head><body>
<nav><a href="/">Home</a> <a href="/other.html">Other course</a></nav>
<h2>Week 1</h2><ul>
<li>Lecture 1: Intro - <a href="files/lec1.pdf">Slides</a> - <a href="files/lec1.pptx">Deck</a></li>
<li><a href="notes.html">Lecture notes</a></li>
<li><a href="files/fake.pdf">Broken PDF</a></li>
<li><a href="missing.pdf">Dead link</a></li>
<li><a href="files/cut.pdf">Cut file</a></li>
<li><a href="https://www.youtube.com/watch?v=abc">Lecture video</a></li>
<li><a href="private/page.html">Staff page</a></li>
<li><a href="app.html">Interactive notes</a></li>
<li><a href="gone.html">Old reading</a></li>
</ul>
<h2>Week 2</h2><ul><li><a href="files/big.zip">Dataset</a></li><li><a href="files/con.pdf">CON</a></li>
<li><a href="files/lec1-mirror.pdf">Mirror of lecture 1</a></li>
<li><a href="files/lec1.pdf?utm_source=newsletter">Lecture 1 again, with tracking</a></li></ul>
</body></html>""", encoding="utf-8")
(site / "notes.html").write_text("<html><head><title>Notes</title></head><body><article><h1>Lecture notes</h1>"
                                 + "".join(f"<p>Step {i}: gradient descent moves weight {i} against its gradient.</p>" for i in range(40))
                                 + "</article></body></html>", encoding="utf-8")
(site / "app.html").write_text('<html><body><noscript>You need to enable JavaScript to run this app.</noscript>'
                               '<div id="root"></div></body></html>')                    # empty until JS runs
(site / "gone.html").write_text("<html><head><title>Not found</title></head><body><h1>Page not found</h1>"
                                "<p>Sorry, the page you are looking for does not exist.</p></body></html>")  # a 404 sent as 200
(site / "private" / "page.html").write_text('<html><body><p>Staff only</p><a href="/files/secret.pdf">secret</a></body></html>')
(site / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
(site / "files" / "lec1.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
(site / "files" / "lec1-mirror.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)  # same bytes, different URL
(site / "files" / "secret.pdf").write_bytes(b"%PDF-1.4\n")
(site / "files" / "con.pdf").write_bytes(b"%PDF-1.4\n")
(site / "files" / "lec1.pptx").write_bytes(b"PK\x03\x04" + b"x" * 2000)
(site / "files" / "fake.pdf").write_bytes(b"<html>Please sign in</html>")  # served as application/pdf
(site / "files" / "big.zip").write_bytes(b"PK\x03\x04" + b"\0" * 1_100_000)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/files/cut.pdf":  # promises 100 kB, sends 13 bytes, hangs up
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", "100000")
            self.end_headers()
            self.wfile.write(b"%PDF-1.4\npart")
            self.close_connection = True
            return
        super().do_GET()


server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(site)))
server.handle_error = lambda request, address: None  # the client hangs up on purpose (too big, cut off)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{server.server_address[1]}/index.html"


def grab(*flags, dest=out):
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "coursekeep.py"), URL, "-o", str(dest), "--browser", "never",
                        "--max-mb", "1", *flags], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return {i["name"]: i for i in json.loads(next(dest.glob("*/report.json")).read_text(encoding="utf-8"))["items"]}


items = grab()
ok = lambda name, kind: items[name]["status"] == "ok" and items[name]["kind"] == kind
assert ok("Lecture 1: Intro - Slides".replace(":", ""), "pdf") or ok("Lecture 1 Intro - Slides", "pdf"), items.keys()
assert ok("Lecture 1 Intro - Deck", "slides")
assert ok("Lecture notes", "articles")
assert items["_CON"]["status"] == "ok" and items["_CON"]["path"].endswith("/_CON.pdf"), items["_CON"]  # Windows reserved name
mirror = items["Mirror of lecture 1"]                                                                 # same file, two links
assert mirror["status"] == "exists" and "same content" in mirror["reason"] and not mirror["new"], mirror
assert mirror["path"] == items["Lecture 1 Intro - Slides"]["path"]
assert "Lecture 1 again, with tracking" not in items                                                  # utm_* is the same URL
assert items["Broken PDF"]["status"] == "failed" and "not a .pdf" in items["Broken PDF"]["reason"]   # login page posing as PDF
assert items["Dead link"]["status"] == "failed" and "404" in items["Dead link"]["reason"]
assert items["Cut file"]["status"] == "failed", items["Cut file"]                                       # truncated download
assert items["Dataset"]["status"] == "failed" and "too big" in items["Dataset"]["reason"]
assert items["Lecture video"]["status"] == "linked"
assert items["Interactive notes"]["status"] == "failed" and "JavaScript" in items["Interactive notes"]["reason"]  # not saved as junk
assert items["Old reading"]["status"] == "failed" and "404" in items["Old reading"]["reason"]                   # soft 404
assert "Home" not in items and "Other course" not in items                                              # menu links
course = next(out.glob("*/"))
assert not list(course.rglob("*.part")) and not list(course.rglob("Cut file*")), "no partial files left behind"
assert len(list(course.rglob("*.pdf"))) == 2, "lecture 1 is stored once, plus _CON.pdf"
md = (course / "Week 1" / "articles" / "Lecture notes.md").read_text(encoding="utf-8")
assert "gradient descent moves weight 39" in md and "Source: http" in md

again = grab()                                                       # rerun: nothing new, nothing re-downloaded
assert all(i["status"] in ("exists", "failed", "linked") and not i["new"] for i in again.values()), again
stray = course / "Week 1" / "pdf" / "Slides saved under an older name.pdf"  # a copy an older version left behind
stray.write_bytes((course / items["Lecture 1 Intro - Slides"]["path"]).read_bytes())
grab()
report = json.loads((course / "report.json").read_text(encoding="utf-8"))
assert not stray.exists() and report["duplicates_removed"] == ["Week 1/pdf/Slides saved under an older name.pdf"], report
(course / "manifest.json").unlink()                                  # as if the last run was cancelled
resumed = grab()
assert resumed["Lecture 1 Intro - Deck"]["status"] == "exists", "resume finds files without a manifest"

(site / "files" / "lec0.pdf").write_bytes(b"%PDF-1.4\n" + b"y" * 3000)  # the course adds a same-named link above lecture 1
index = (site / "index.html").read_text(encoding="utf-8")
(site / "index.html").write_text(index.replace("<li>Lecture 1:", '<li>Lecture 1: Intro - <a href="files/lec0.pdf">Slides</a></li>\n<li>Lecture 1:', 1),
                                 encoding="utf-8")
grown = grab("--refresh")
old, added = grown["Lecture 1 Intro - Slides"], grown["Lecture 1 Intro - Slides (2)"]
assert old["url"].endswith("lec1.pdf") and old["path"] == items["Lecture 1 Intro - Slides"]["path"], old  # keeps its file
assert added["url"].endswith("lec0.pdf") and added["status"] == "ok" and (course / added["path"]).stat().st_size > 3000, added

deep_dir = Path(tempfile.mkdtemp())
deep = grab("--depth", "1", dest=deep_dir)                           # robots.txt keeps the crawler out of /private/
assert "secret" not in " ".join(deep), deep.keys()
assert "gradient descent moves weight 39" in next(deep_dir.glob("*/Lecture notes/_page.md")).read_text(encoding="utf-8")  # sub-page crawled

coursekeep.ALLOW_PRIVATE = False                                     # a public page linking into your LAN
try:
    coursekeep.session().get(URL, timeout=5)
    raise AssertionError("private address was not blocked")
except requests.ConnectionError as e:
    assert "local network" in str(e)
print("ok")
