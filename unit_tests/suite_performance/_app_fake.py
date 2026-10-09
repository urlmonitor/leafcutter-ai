"""Recording fake of the hosting service as the dedicated hold App sees it (TQ-600a-13-vi). Not a test: underscore-named.

``AppService`` is the shared ``HoldService`` (issues, run history, jobs, workflow state) plus the App plane:

* ``GET /repos/{repo}/installation`` and ``POST /app/installations/{id}/access_tokens`` -- authorised only by a REAL RS256
  JWT: the fake verifies the signature with ``openssl dgst -sha256 -verify`` against the public half of a throwaway
  test-only key, and checks ``iss`` (the App ID) and ``exp`` (at most 10 minutes ahead). A wrong key, a wrong App ID or an
  unsigned token is a 401; ``installed = False`` is a 404; a stated ``exchange_status`` overrides the exchange.
* ``POST /repos/{repo}/check-runs`` and ``PATCH /repos/{repo}/check-runs/{id}`` -- authorised only by an installation token
  this fake minted (the GITHUB_TOKEN is a 403, as on the real service). ``create_status`` / ``complete_status`` refuse the
  write with that code. Every attempt is recorded with WHO authorised it: ``auth_kind`` is ``install`` | ``jwt`` |
  ``github_token`` | ``none`` | ``other``.
* ``GET /repos/{repo}/commits/{sha}/check-runs`` -- the check runs on a commit (seed ``check_runs``), filtered by ``check_name``.

Every request, in arrival order, is in ``log`` (method, path, query, bearer value, body), so a test can assert ORDER.
"""

from __future__ import annotations

import atexit
import base64
import functools
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ._hold_harness import HoldService
from ._notice_fakes import REPO, _Handler

APP_ID = "5249547"
INSTALLATION_ID = 777
CHECK_NAME = "Post-merge suite status"
GITHUB_TOKEN = "fake-token"  # what the executor hands every job as GITHUB_TOKEN once an API URL is given
_INSTALL_PATH = f"/repos/{REPO}/installation"
_EXCHANGE = re.compile(rf"/app/installations/{INSTALLATION_ID}/access_tokens")
_CHECKS_PATH = f"/repos/{REPO}/check-runs"
_ONE_CHECK = re.compile(rf"{re.escape(_CHECKS_PATH)}/(\d+)")
_HEAD_CHECKS = re.compile(rf"/repos/{re.escape(REPO)}/commits/([0-9a-f]{{40}})/check-runs")
_PR_COMMENTS = re.compile(rf"/repos/{re.escape(REPO)}/issues/\d+/comments")
_LOCAL = threading.local()


# --------------------------------------------------------------------------- throwaway keys
@dataclass(frozen=True)
class Keys:
    private_pem: str  # what the secret HOLD_APP_PRIVATE_KEY would hold
    public_path: Path


def _openssl(*args, data=None):
    done = subprocess.run(["openssl", *args], input=data, capture_output=True, check=False)  # noqa: S603, S607
    return done


@functools.cache
def key_pairs():
    """(right, wrong): two RSA-2048 key pairs generated once per process; the fake trusts only ``right``."""
    root = Path(tempfile.mkdtemp(prefix="hold-app-keys-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    pairs = []
    for name in ("right", "wrong"):
        private = root / f"{name}.pem"
        public = root / f"{name}.pub.pem"
        made = _openssl("genrsa", "-traditional", "-out", str(private), "2048")  # GitHub issues PKCS#1 ("BEGIN RSA PRIVATE KEY")
        if made.returncode != 0:
            message = f"openssl genrsa failed: {made.stderr.decode(errors='replace')}"
            raise AssertionError(message)
        _openssl("rsa", "-in", str(private), "-pubout", "-out", str(public))
        pairs.append(Keys(private.read_text(encoding="utf-8"), public))
    return tuple(pairs)


def _b64url(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --------------------------------------------------------------------------- the service
class _HeaderHandler(_Handler):
    """The shared handler, remembering the bearer value of the request it is serving (``handle`` gets no headers)."""

    def _dispatch(self, method):
        raw = self.headers.get("Authorization") or ""
        _LOCAL.auth = raw.removeprefix("Bearer ").removeprefix("token ").strip()
        super()._dispatch(method)


class AppService(HoldService):
    """The hold fake plus the App plane. ``reset()`` clears every injected failure and every recorded request."""

    def __init__(self):
        super().__init__()
        self._server.RequestHandlerClass = _HeaderHandler

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.log, self.minted, self.bearers, self.check_runs = [], [], [], []
        self.installed, self.exchange_status, self.create_status, self.complete_status = True, None, None, None

    # ---- routing
    def handle(self, method, raw_path, body):
        parsed = urlparse(raw_path)
        entry = {"n": len(self.log), "method": method, "path": parsed.path, "query": parse_qs(parsed.query), "auth": getattr(_LOCAL, "auth", ""), "body": body}
        self.log.append(entry)
        answer = self._app_plane(method, parsed.path, entry)
        return answer if answer is not None else super().handle(method, raw_path, body)

    def _app_plane(self, method, path, entry):
        if method == "GET" and path == _INSTALL_PATH:
            return self._jwt_gate(entry) or ((200, {"id": INSTALLATION_ID}) if self.installed else (404, {"message": "Not Found"}))
        if method == "POST" and _EXCHANGE.fullmatch(path):
            gate = self._jwt_gate(entry)
            if gate or self.exchange_status:
                return gate or (self.exchange_status, {"message": "refused"})
            self.minted.append(f"ghs_test{len(self.minted) + 1:02d}InstallationTokenValue0123456789")
            return 201, {"token": self.minted[-1], "expires_at": "2099-01-01T00:00:00Z"}
        if _PR_COMMENTS.fullmatch(path):  # the hold's own PR comment (-vii): no comment exists yet, a create is accepted
            return (200, []) if method == "GET" else (201, {"id": 9000 + entry["n"], "body": (entry["body"] or {}).get("body", "")})
        if method == "POST" and path == _CHECKS_PATH:
            return self._write_gate(entry, self.create_status) or self._create_check(entry["body"] or {})
        match = _ONE_CHECK.fullmatch(path)
        if method == "PATCH" and match:
            return self._write_gate(entry, self.complete_status) or self._complete_check(int(match.group(1)), entry["body"] or {})
        head = _HEAD_CHECKS.fullmatch(path)
        if method == "GET" and head:
            wanted = entry["query"].get("check_name", [None])[0]
            runs = [r for r in self.check_runs if r["head_sha"] == head.group(1) and wanted in (None, r["name"])]
            return 200, {"total_count": len(runs), "check_runs": runs}
        return None

    def _jwt_gate(self, entry):
        """None when the bearer is a JWT signed by the trusted key for this App ID that expires within 10 minutes."""
        self.bearers.append(entry["auth"])
        if self._jwt_ok(entry["auth"]):
            return None
        return 401, {"message": "A JSON web token could not be decoded"}

    @staticmethod
    def _jwt_ok(token):
        parts = token.split(".")
        if len(parts) != 3:
            return False
        try:
            header, claims, signature = json.loads(_b64url(parts[0])), json.loads(_b64url(parts[1])), _b64url(parts[2])
        except ValueError:
            return False
        now = time.time()
        if header.get("alg") != "RS256" or str(claims.get("iss")) != APP_ID or not now < float(claims.get("exp", 0)) <= now + 600:
            return False
        sig_path = key_pairs()[0].public_path.with_suffix(f".{threading.get_ident()}.sig")
        sig_path.write_bytes(signature)
        done = _openssl("dgst", "-sha256", "-verify", str(key_pairs()[0].public_path), "-signature", str(sig_path), data=f"{parts[0]}.{parts[1]}".encode())
        return done.returncode == 0

    def _write_gate(self, entry, injected):
        kind = self.auth_kind(entry)
        if kind == "github_token":
            return 403, {"message": "Resource not accessible by integration"}
        if kind != "install":
            return 401, {"message": "Bad credentials"}
        return (injected, {"message": "refused"}) if injected else None

    def _create_check(self, body):
        record = {"id": 5000 + len(self.check_runs), "name": body.get("name"), "head_sha": body.get("head_sha"), "status": body.get("status", "queued"), "conclusion": None, "output": body.get("output"), "app": {"id": int(APP_ID)}}
        self.check_runs.append(record)
        return 201, record

    def _complete_check(self, check_id, body):
        record = next((r for r in self.check_runs if r["id"] == check_id), None)
        if record is None:
            return 404, {"message": "Not Found"}
        record.update({k: v for k, v in body.items() if k in ("status", "conclusion", "output")})
        return 200, record

    # ---- what the server saw
    def auth_kind(self, entry):
        auth = entry["auth"]
        if not auth:
            return "none"
        if auth in self.minted:
            return "install"
        if auth == GITHUB_TOKEN:
            return "github_token"
        return "jwt" if auth.count(".") == 2 else "other"

    def check_posts(self):
        return [e for e in self.log if e["method"] == "POST" and e["path"] == _CHECKS_PATH]

    def check_patches(self):
        return [e for e in self.log if e["method"] == "PATCH" and _ONE_CHECK.fullmatch(e["path"])]

    def reads(self):
        """The hold's verdict reads, App-plane GETs (installation, a commit's check runs) excluded."""
        return [(k, q) for k, q in super().reads() if not (k.startswith("other:") and (k.endswith("/installation") or k.endswith("/check-runs")))]

    def credential_needles(self):
        """Everything that must never appear in a file or a log: key body and slices, every token, every JWT."""
        body = "".join(line for line in key_pairs()[0].private_pem.splitlines() if "-----" not in line)
        wrong = "".join(line for line in key_pairs()[1].private_pem.splitlines() if "-----" not in line)
        lines = [line for pem in (key_pairs()[0].private_pem, key_pairs()[1].private_pem) for line in pem.splitlines() if "-----" not in line and len(line) >= 20]
        return sorted({body, wrong, body[:24], body[-24:], *lines, *self.minted, *(b for b in self.bearers if b.count(".") == 2)})
