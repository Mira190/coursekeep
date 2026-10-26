"""CourseKeep web app: a local page where you paste a URL and get the whole course.

Usage: python scripts/app.py [--port 8765] [--out ~/Downloads/CourseKeep] [--no-browser]
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

FROZEN = getattr(sys, "frozen", False)  # running as the packaged CourseKeep.exe (PyInstaller)
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
# Downloads are untrusted: only document types are opened directly, anything else is shown in its folder.
OPENABLE = {".pdf", ".pptx", ".ppt", ".key", ".odp", ".docx", ".doc", ".odt", ".rtf", ".xlsx", ".xls", ".csv", ".md", ".txt"}
JOBS, OUT, PORT, VERSION = {}, Path(), 0, ""


def engine_cmd():
    # The packaged app has no python.exe: it runs the engine by calling itself with --engine.
    return [sys.executable, "--engine"] if FROZEN else [sys.executable, "-X", "utf8", "-u", str(HERE / "coursekeep.py")]


def kill_tree(proc):
    """Stop the engine and the hidden browser it may have started; killing only the parent leaves the browser running."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        os.killpg(proc.pid, 15)


class Job:
    """One coursekeep.py run in a subprocess; its stdout lines are the progress feed."""

    def __init__(self, url, flags):
        self.lines, self.out, self.done, self.started = [], None, False, time.time()
        self.proc = subprocess.Popen(
            [*engine_cmd(), url, "-o", str(OUT), *flags], start_new_session=sys.platform != "win32",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            if m := re.search(r"links to process -> (.+)$", line.rstrip()):
                self.out = Path(m[1])
            self.lines.append(line.rstrip())
        self.proc.wait()
        self.done = True

    def report(self):
        p = self.out / "report.json" if self.out else None
        fresh = p and p.exists() and p.stat().st_mtime >= self.started  # a cancelled run must not show last run's report
        return json.loads(p.read_text(encoding="utf-8")) if fresh else None


def reveal(path):
    if sys.platform == "win32":
        if path.is_dir() or path.suffix.lower() in OPENABLE:
            os.startfile(path)
        else:
            subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)] if path.is_dir() or path.suffix.lower() in OPENABLE else ["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path if path.is_dir() or path.suffix.lower() in OPENABLE else path.parent)])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def guard(self):
        """Only this page may call the API: blocks DNS rebinding and other sites' requests to localhost."""
        ours = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        origin = self.headers.get("Origin")
        if self.headers.get("Host") not in ours or (origin and urlparse(origin).netloc not in ours):
            self.send_error(403)
            return False
        return True

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def job(self, jid):
        if jid not in JOBS:
            self.send(404, {"error": "unknown job"})
        return JOBS.get(jid)

    def do_GET(self):
        if not self.guard():
            return
        path = urlparse(self.path).path
        if path == "/":
            self.send(200, (HERE / "ui.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/config":
            self.send(200, {"out": str(OUT), "version": VERSION})
        elif (m := re.fullmatch(r"/api/jobs/(\w+)/events", path)) and (job := self.job(m[1])):
            self.events(job)
        elif (m := re.fullmatch(r"/api/jobs/(\w+)/zip", path)) and (job := self.job(m[1])):
            self.zip(job)
        elif not path.startswith("/api/jobs/"):
            self.send(404, {"error": "not found"})

    def do_POST(self):
        if not self.guard():
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.send(415, {"error": "JSON only"})  # forces a CORS preflight for any cross-site caller
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad JSON"})
        path = urlparse(self.path).path
        if path == "/api/jobs":
            url = str(body.get("url", "")).strip()
            if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
                return self.send(400, {"error": "Enter a full web address, like https://example.edu/course"})
            flags = ["--depth", "1"] if body.get("depth") else []
            flags += ["--refresh"] * bool(body.get("refresh")) + ["--all-links"] * bool(body.get("allLinks"))
            flags += ["--max-mb", str(int(body.get("maxMb") or 100))]
            jid = uuid.uuid4().hex[:12]
            JOBS[jid] = Job(url, flags)
            self.send(200, {"id": jid})
        elif path == "/api/open":
            job = JOBS.get(body.get("job"))
            base = (job.out if job and job.out else OUT).resolve()
            target = (base / str(body.get("rel") or "")).resolve()
            if not target.is_relative_to(base) or not target.exists():
                return self.send(400, {"error": "not in the download folder"})
            reveal(target)
            self.send(200, {"ok": True})
        elif (m := re.fullmatch(r"/api/jobs/(\w+)/cancel", path)) and (job := self.job(m[1])):
            kill_tree(job.proc)
            self.send(200, {"ok": True})
        elif not path.startswith("/api/jobs/"):
            self.send(404, {"error": "not found"})

    def events(self, job):
        """Server-sent events: every progress line, then 'done' with the report."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        i = int(self.headers.get("Last-Event-ID") or -1) + 1  # resume after a reconnect instead of replaying
        try:
            while True:
                while i < len(job.lines):
                    self.wfile.write(f"id: {i}\nevent: line\ndata: {job.lines[i]}\n\n".encode())
                    i += 1
                if job.done and i >= len(job.lines):
                    done = {"code": job.proc.returncode, "report": job.report(), "last": job.lines[-1] if job.lines else ""}
                    self.wfile.write(f"event: done\ndata: {json.dumps(done)}\n\n".encode())
                    self.wfile.flush()
                    return
                self.wfile.flush()
                time.sleep(0.15)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def zip(self, job):
        if not job.out or not job.out.exists():
            return self.send(404, {"error": "nothing downloaded yet"})
        with tempfile.TemporaryFile() as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:  # PDFs and slides are already compressed
                for f in sorted(job.out.rglob("*")):
                    if f.is_file() and f.name not in ("manifest.json", "report.json") and f.suffix != ".part":
                        z.write(f, Path(job.out.name) / f.relative_to(job.out))
            size = tmp.tell()
            tmp.seek(0)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f"attachment; filename=\"coursekeep.zip\"; "
                                                    f"filename*=UTF-8''{quote(job.out.name + '.zip')}")
            self.end_headers()
            shutil.copyfileobj(tmp, self.wfile)


def main():
    global OUT, PORT, VERSION
    if sys.argv[1:2] == ["--engine"]:  # the packaged app calling itself to run one download (see engine_cmd)
        import coursekeep
        sys.stdout.reconfigure(line_buffering=True)  # progress lines must reach the page as they happen
        sys.argv = ["coursekeep", *sys.argv[2:]]
        return coursekeep.main()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if missing := [m for m in ("requests", "bs4", "lxml", "trafilatura") if importlib.util.find_spec(m) is None]:
        sys.exit(f"CourseKeep needs {', '.join(missing)}. Install everything it uses with:\n"
                 f'  "{sys.executable}" -m pip install -r "{HERE.parent / "requirements.txt"}"')
    from coursekeep import __version__ as VERSION
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"CourseKeep {VERSION}")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", default=str(Path.home() / "Downloads" / "CourseKeep"))
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    OUT = Path(a.out).expanduser().resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    for PORT in range(a.port, a.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)  # never 0.0.0.0: it fetches any URL it is given
            break
        except OSError:
            continue
    else:
        sys.exit("No free port found.")
    url = f"http://127.0.0.1:{PORT}/"
    print(f"CourseKeep is running at {url}\nFiles are saved to {OUT}\nKeep this window open. Press Ctrl+C to stop.")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in JOBS.values():  # closing the window must not leave downloads or hidden browsers running
            kill_tree(job.proc)


if __name__ == "__main__":
    main()
