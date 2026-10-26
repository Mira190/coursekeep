"""Checks a packaged CourseKeep app actually works (PyInstaller can leave out modules or data files the tests never see).

Usage: python scripts/smoke_app.py dist/CourseKeep/CourseKeep[.exe]
"""
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import coursekeep

exe = str(Path(sys.argv[1]).resolve())
site, out = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
(site / "index.html").write_text('<html><head><title>Smoke</title></head><body><h2>Week 1</h2><ul>'
                                 '<li><a href="slides.pdf">Slides</a></li><li><a href="notes.html">Notes</a></li></ul></body></html>')
(site / "notes.html").write_text("<html><body><article>" + "".join(f"<p>Sentence {i} about gradients and learning rates.</p>"
                                                                  for i in range(40)) + "</article></body></html>")
(site / "slides.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 500)
server = ThreadingHTTPServer(("127.0.0.1", 0), partial(type("H", (SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}),
                                                       directory=str(site)))
threading.Thread(target=server.serve_forever, daemon=True).start()

version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120).stdout.strip()
assert version == f"CourseKeep {coursekeep.__version__}", version

# The engine inside the app: trafilatura's data files and the link rules must all be bundled.
r = subprocess.run([exe, "--engine", f"http://127.0.0.1:{server.server_address[1]}/", "-o", str(out), "--browser", "never"],
                   capture_output=True, text=True, encoding="utf-8", timeout=300)
assert r.returncode == 0, r.stdout + r.stderr
items = {i["name"]: i for i in json.loads(next(out.glob("*/report.json")).read_text(encoding="utf-8"))["items"]}
assert items["Slides"]["status"] == "ok" and items["Notes"]["status"] == "ok", items

# The web app: starts, serves its page (ui.html is bundled) and reports its version.
app = subprocess.Popen([exe, "--no-browser", "--port", "8799", "--out", str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8799/api/config", timeout=5) as resp:
                assert json.load(resp)["version"] == coursekeep.__version__
            with urllib.request.urlopen("http://127.0.0.1:8799/", timeout=5) as resp:
                assert b"CourseKeep" in resp.read()
            break
        except OSError:
            time.sleep(1)
    else:
        raise AssertionError("the app never answered on port 8799")
finally:
    app.kill()
print("ok")
