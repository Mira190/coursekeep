"""Offline checks of the web app's request guards: python scripts/test_app.py"""
import http.client
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import app

app.OUT = Path(tempfile.mkdtemp())
(app.OUT / "course" / "pdf").mkdir(parents=True)
(app.OUT / "course" / "pdf" / "a.pdf").write_bytes(b"%PDF")
server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
app.PORT = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()
app.JOBS["j1"] = SimpleNamespace(out=app.OUT / "course")
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
assert req("POST", "/api/open", {"job": "j1", "rel": "../../../Windows/System32"})[0] == 400   # path traversal
assert req("POST", "/api/open", {"job": "j1", "rel": "pdf/a.pdf"})[0] == 200
assert opened == [(app.OUT / "course" / "pdf" / "a.pdf").resolve()]
assert req("GET", "/api/jobs/nope/zip")[0] == 404

job = app.Job.__new__(app.Job)  # progress lines carry page text; a section titled like the header line must not move the folder
job.out, job.lines = None, []
job.proc = SimpleNamespace(stdout=iter(["3 links to process -> /dl/Course\n", "[ok    ] links to process -> /etc / x\n"]), wait=int)
job._read()
assert job.out == Path("/dl/Course"), job.out
print("ok")
