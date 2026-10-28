"""Offline checks of the web app's request guards: python scripts/test_app.py"""
import http.client
import io
import json
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import app

app.OUT = Path(tempfile.mkdtemp())
(app.OUT / "course" / "pdf").mkdir(parents=True)
(app.OUT / "course" / "pdf" / "a.pdf").write_bytes(b"%PDF")
(app.OUT / "course" / "report.json").write_text(json.dumps({"title": "Course", "url": "https://x.org/c", "options": {"depth": 1}, "items": [
    {"name": "a", "status": "ok", "path": "pdf/a.pdf", "size": 4}, {"name": "a again", "status": "exists", "path": "pdf/a.pdf", "size": 4},
    {"name": "b", "status": "failed", "path": None}]}))
(app.OUT / "broken").mkdir()
(app.OUT / "broken" / "report.json").write_text("{")  # a run that died while writing it
(app.OUT / "odd").mkdir()
(app.OUT / "odd" / "report.json").write_text(json.dumps({"items": [{"path": "a", "size": "lots"}]}))  # hand-edited
server = app.Server(("127.0.0.1", 0), app.Handler)
app.PORT = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()
app.JOBS["j1"] = SimpleNamespace(out=app.OUT / "course", done=True, url="https://x.org/c")
app.JOBS["j2"] = SimpleNamespace(done=False, url="https://x.org/running", opts={"depth": True}, started=5.0)
opened = []
app.reveal = opened.append  # never launch real programs from a test


def req(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", app.PORT)
    h = {"Host": f"127.0.0.1:{app.PORT}", **(headers or {})}
    if body is not None:
        h.setdefault("Content-Type", "application/json")
    c.request(method, path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    return r.status, r.read()


assert req("GET", "/")[0] == 200
assert req("GET", "/", headers={"Host": "evil.example"})[0] == 403                      # DNS rebinding
assert req("POST", "/api/jobs", {"url": "https://x.org"}, {"Origin": "https://evil.example"})[0] == 403
assert req("POST", "/api/jobs", {"url": "https://x.org"}, {"Content-Type": "text/plain"})[0] == 415  # simple cross-site POST
assert req("POST", "/api/jobs", {"url": "file:///etc/passwd"})[0] == 400
assert req("POST", "/api/jobs", {"url": "not a url"})[0] == 400
assert req("POST", "/api/jobs", {"url": "https://x.org", "maxMb": "lots"})[0] == 400
assert req("POST", "/api/open", {"course": "course", "rel": "../../../Windows/System32"})[0] == 400   # path traversal
for bad in ("..", "../..", "/etc", "C:\\Windows", "course/pdf", "a\0b", "missing"):              # course names come from page text
    assert req("POST", "/api/open", {"course": bad})[0] == 400, bad
    assert req("GET", f"/api/course?course={quote(bad)}")[0] == 404, bad
    assert req("GET", f"/api/zip?course={quote(bad)}")[0] == 404, bad
assert req("POST", "/api/open", {"course": "course", "rel": "pdf/a.pdf"})[0] == 200
assert req("POST", "/api/open", {})[0] == 200                                                  # the download folder itself
assert opened == [(app.OUT / "course" / "pdf" / "a.pdf").resolve(), app.OUT.resolve()]

code, body = req("GET", "/api/courses")                                                        # the library: finished runs only
assert code == 200 and [c["name"] for c in json.loads(body)] == ["course"], body
c = json.loads(body)[0]
assert (c["saved"], c["failed"], c["bytes"], c["options"]) == (2, 1, 4, {"depth": 1}), c       # a file reached twice counts once
code, body = req("GET", "/api/course?course=course")
assert code == 200 and json.loads(body)["name"] == "course" and len(json.loads(body)["items"]) == 3
code, body = req("GET", "/api/zip?course=course")
assert code == 200 and zipfile.ZipFile(io.BytesIO(body)).namelist() == ["course/pdf/a.pdf"], body[:200]  # no report or manifest

code, body = req("GET", "/api/jobs")                                                           # a reloaded page finds its run
assert code == 200 and json.loads(body) == [{"id": "j2", "url": "https://x.org/running", "opts": {"depth": True}, "started": 5.0}], body
code, body = req("POST", "/api/jobs", {"url": "https://x.org/running"})                        # never two runs into one folder
assert code == 200 and json.loads(body) == {"id": "j2", "opts": {"depth": True}} and len(app.JOBS) == 2, body  # its own options

app.JOBS["j3"] = SimpleNamespace(done=True, cancelled=False, lines=["[ok    ] Week 1 / a: pdf"], report=lambda: None,
                                 proc=SimpleNamespace(poll=iter([None, 0]).__next__, returncode=-15))  # running, then stopped
assert req("POST", "/api/jobs/j3/cancel", {})[0] == 200                                        # cancelled in one tab...
code, body = req("GET", "/api/jobs/j3/events")
assert code == 200 and b'"cancelled": true' in body and b"data: [ok    ] Week 1 / a: pdf" in body, body  # ...every tab is told
app.JOBS["j4"] = SimpleNamespace(done=True, cancelled=False, proc=SimpleNamespace(poll=lambda: 0))
assert req("POST", "/api/jobs/j4/cancel", {})[0] == 200 and not app.JOBS["j4"].cancelled          # too late: it finished

assert app.serves_us(app.PORT)                                                                 # started twice: reuse that one
other = ThreadingHTTPServer(("127.0.0.1", 0), type("Other", (BaseHTTPRequestHandler,), {"log_message": lambda *a: None, "do_GET": lambda h: (
    h.send_response(200), h.end_headers(), h.wfile.write(b'{"version": "1", "out": "/elsewhere"}'))}))
threading.Thread(target=other.serve_forever, daemon=True).start()
assert not app.serves_us(other.server_address[1])                                              # ...not one saving elsewhere
other.server_close()
assert not app.serves_us(other.server_address[1])                                              # nothing listening

job = app.Job.__new__(app.Job)  # progress lines carry page text; a section titled like the header line must not move the folder
job.out, job.lines = None, []
job.proc = SimpleNamespace(stdout=iter(["3 links to process -> /dl/Course\n", "[ok    ] links to process -> /etc / x\n"]), wait=int)
job._read()
assert job.out == Path("/dl/Course"), job.out
print("ok")
