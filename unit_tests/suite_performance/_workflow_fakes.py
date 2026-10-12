"""The fake GitHub REST API and the artifact store of the TQ-600a-13 workflow executor.

Split out of ``_workflow_jobs.py`` (file-size limit). Test infrastructure, not a test.
"""

from __future__ import annotations

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ._workflow_conditions import _fail


# --------------------------------------------------------------------------- fake GitHub REST API
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 -- http.server naming
        self.server.requests.append(self.path)
        body = json.dumps({"total_count": 0, "workflow_runs": [], "artifacts": [], "jobs": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return None


class FakeGitHub:
    """A recording fake of the REST API on 127.0.0.1 that serves an empty history for every GET."""

    def __init__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.requests = []
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @property
    def requests(self):
        return list(self._server.requests)

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


# --------------------------------------------------------------------------- artifacts
class ArtifactStore:
    """Named artifacts: the only thing that crosses from one job to another."""

    def __init__(self, root):
        self.root = Path(root)

    def names(self):
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def upload(self, name, entries):
        dest = self.root / name
        try:
            if dest.exists():
                shutil.rmtree(dest)
            for rel, src in entries:
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
        except OSError as exc:
            _fail(f"cannot store artifact {name!r}: {exc}", exc)

    def files(self, name):
        base = self.root / name
        if not base.is_dir():
            return {}
        return {str(p.relative_to(base)): p for p in sorted(base.rglob("*")) if p.is_file()}

    def read_text(self, name, rel):
        try:
            return (self.root / name / rel).read_text(encoding="utf-8")
        except OSError as exc:
            _fail(f"artifact {name!r} has no readable file {rel!r}: {exc}", exc)

    def read_json(self, name, rel):
        try:
            return json.loads(self.read_text(name, rel))
        except ValueError as exc:
            _fail(f"artifact {name!r} file {rel!r} is not JSON: {exc}", exc)
