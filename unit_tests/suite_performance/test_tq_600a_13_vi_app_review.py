"""
Tests for TQ-600a-13-vi, App publication half, review follow-ups -- what the token exchange asks for, how the signed JWT travels
(stdin, never an environment variable; the key only in the signing step), the shape of the JWT the real shell step signs, and the
wording of a failure with no response. The job is EXECUTED (real `run:` step, shared executor) against the recording fake.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml

ASSUMED PRODUCTION CONTRACT (review follow-ups M-1, L-1, L-2, L-3, L-5):

* The exchange POST body is exactly {"permissions": {"checks": "write"}, "repositories": ["<repo name>"]}.
* No process the job starts has HOLD_APP_JWT or HOLD_APP_PRIVATE_KEY in its environment (checked by name, for python and openssl).
* A step that cannot sign (the base64 or the signature step produces nothing) says "could not sign" and creates no check run.
* The JWT: iat about now-60, exp at most 10 minutes ahead, no `=` padding in any segment; a key whose PEM has no newline after the END
  line signs fine (GitHub's secret store hands the key over that way).
* A request that gets no response says "no response", never "HTTP 0".
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path
from unittest import mock

from . import _app_harness
from ._app_fake import INSTALLATION_ID, key_pairs
from ._app_harness import OBSERVER, AppTestCase, app_secrets
from ._comment_harness import pr_event, write_event
from ._ending_harness import CHECK, Cases
from ._hold_harness import HOLD_MODULE
from ._notice_fakes import REPO, import_production

EXCHANGE = f"/app/installations/{INSTALLATION_ID}/access_tokens"
SHIM = (
    "#!/bin/sh\n"
    "if [ -n \"$SHIM_DUMP\" ]; then env | sed 's/=.*//' >> \"$SHIM_DUMP\"; fi\n"
    'if [ "$SHIM_FAIL" = "$1" ]; then exit 1; fi\n'
    'if [ "$1" = base64 ] && [ -n "$SHIM_NTH" ]; then\n'
    '  n=$(cat "$SHIM_COUNT" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$SHIM_COUNT"\n'
    '  if [ "$n" = "$SHIM_NTH" ]; then exit 1; fi\n'
    "fi\n"
    'exec "$SHIM_REAL" "$@"\n'
)
NAMES_DUMP = (
    "\nimport json as _j, os as _o\n"
    "if _o.environ.get('ENV_DUMP'):\n"
    "    with open(_o.environ['ENV_DUMP'], 'a', encoding='utf-8') as _h:\n"
    "        _h.write(_j.dumps(sorted(_o.environ)) + '\\n')\n"
)
CREDENTIAL_NAMES = ("HOLD_APP_JWT", "HOLD_APP_PRIVATE_KEY")


def _segments(jwt):
    return [base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)) for part in jwt.split(".")[:2]], jwt.split(".")


class TestTq600a13viAppReview(AppTestCase):
    def _shimmed(self, *, fail=None, nth=None, **kwargs):
        """Execute the job with a wrapper `openssl` first on PATH that records the NAMES (never values) of its environment.

        ``fail`` makes every call of that openssl subcommand produce nothing; ``nth`` makes only the nth `openssl base64` call
        (1 = the JWT header, 2 = the payload, 3 = the signature) produce nothing.
        """
        with tempfile.TemporaryDirectory() as raw:
            shim_dir, dump = Path(raw) / "bin", Path(raw) / "names.txt"
            shim_dir.mkdir()
            shim = shim_dir / "openssl"
            shim.write_text(SHIM, encoding="utf-8")
            shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
            extra = {"SHIM_DUMP": str(dump), "SHIM_REAL": shutil.which("openssl"), "SHIM_FAIL": fail or "-", "SHIM_NTH": str(nth or ""), "SHIM_COUNT": str(Path(raw) / "count.txt")}

            class ShimmedRun(_app_harness.HoldRun):
                """The executor puts its own interpreter's directory first on PATH, so the shim goes first AFTER that (job only, not the fake)."""

                def __init__(self, *args):
                    super().__init__(*args)
                    self._base_env["PATH"] = f"{shim_dir}{os.pathsep}{self._base_env['PATH']}"
                    self._base_env.update(extra)

            with mock.patch.object(_app_harness, "HoldRun", ShimmedRun):
                executed = self.execute(**kwargs)
            names = dump.read_text(encoding="utf-8").split() if dump.exists() else []
        return executed, names

    def test_tq600a_13_vi_the_exchange_asks_for_checks_write_on_this_repository_only(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The access-token POST body is exactly {"permissions": {"checks": "write"}, "repositories": [<repo name>]}, the name being
        the part of owner/name after the slash.

        Wrong versions caught: an empty body (a token with every permission of the installation on every repository it covers); the
        full owner/name in `repositories`; extra permissions.
        """
        self.seed("pass")
        executed = self.execute()
        CHECK.assertEqual("success", executed.conclusion, executed.text[-600:])
        posts = [e for e in self.svc.log if e["method"] == "POST" and e["path"] == EXCHANGE]
        CHECK.assertEqual(1, len(posts))
        CHECK.assertEqual({"permissions": {"checks": "write"}, "repositories": [REPO.split("/", 1)[1]]}, posts[0]["body"])

    def test_tq600a_13_vi_no_child_process_sees_the_key_or_the_jwt_in_its_environment(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The job's python and every openssl it starts are observed (variable NAMES only): neither HOLD_APP_JWT nor
        HOLD_APP_PRIVATE_KEY is in the environment of any of them, while the job still publishes (so the JWT reached python another way).

        Wrong versions caught: the JWT exported to python through the environment; the key left exported to the signing and base64 children.
        """
        self.seed("pass")
        with tempfile.TemporaryDirectory() as raw:
            dump = Path(raw) / "python-names.txt"
            with mock.patch.object(_app_harness, "OBSERVER", OBSERVER + NAMES_DUMP), mock.patch.dict(os.environ, {"ENV_DUMP": str(dump)}):
                executed, openssl_names = self._shimmed()
            python_names = [name for line in dump.read_text(encoding="utf-8").splitlines() for name in json.loads(line)] if dump.exists() else []
        CHECK.assertEqual("success", executed.conclusion, executed.text[-600:])
        CHECK.assertTrue(python_names and openssl_names, "no child was observed")
        CHECK.assertEqual([], [n for n in python_names if n in CREDENTIAL_NAMES], "python's environment")
        CHECK.assertEqual([], [n for n in openssl_names if n in CREDENTIAL_NAMES], "openssl's environment")

    def test_tq600a_13_vi_a_step_that_cannot_sign_says_so_and_creates_nothing(self):
        # covers: TQ-600a-13-vi
        # angle: failure
        """Every base64 call produces nothing, or the signature step does, or ONLY the header's or ONLY the payload's base64
        does (the signature is then non-empty): the job fails, the output says "could not sign", no check
        run is created and no request goes to the service with a half-built token.

        Wrong versions caught: an empty header or payload accepted as long as the signature exists; a generic message for a local failure.
        """
        cases = Cases()
        for label, options in {"base64": {"fail": "base64"}, "dgst": {"fail": "dgst"}, "header only": {"nth": 1}, "payload only": {"nth": 2}}.items():
            with cases.case(label):
                self.seed("pass")
                executed, _ = self._shimmed(**options)
                CHECK.assertEqual("failure", executed.conclusion, executed.text[-600:])
                CHECK.assertEqual([], executed.says("could not sign"), executed.text[-600:])
                CHECK.assertEqual([], self.svc.check_runs)
                CHECK.assertEqual([], self.svc.bearers, "nothing may be sent with an unsigned token")
        cases.check()

    def test_tq600a_13_vi_the_signed_jwt_has_the_shape_the_service_requires(self):
        # covers: TQ-600a-13-vi
        # angle: boundary
        """Through the real shell step: iat is about now-60 (within 30 s), exp is ahead by at most 10 minutes, no segment carries `=`
        padding, and the header names RS256. The key is also given with NO newline after the END line, as the secret store hands it over.

        Wrong versions caught: padded base64url; iat in the future or absent (clock skew refuses the token); a key that only signs when
        its PEM ends in a newline.
        """
        cases = Cases()
        for label, pem in (("with trailing newline", key_pairs()[0].private_pem), ("no newline after END", key_pairs()[0].private_pem.rstrip("\n"))):
            with cases.case(label):
                CHECK.assertEqual(label.startswith("no"), not pem.endswith("\n"))
                self.seed("pass")
                before = time.time()
                executed = self.execute(secrets=app_secrets(HOLD_APP_PRIVATE_KEY=pem))
                CHECK.assertEqual("success", executed.conclusion, executed.text[-600:])
                (header, claims), parts = _segments(self.svc.bearers[-1])
                CHECK.assertEqual("RS256", json.loads(header)["alg"])
                claims = json.loads(claims)
                CHECK.assertLess(abs(claims["iat"] - (before - 60)), 30)
                CHECK.assertTrue(before < claims["exp"] <= time.time() + 600)
                CHECK.assertEqual([], [p for p in parts if "=" in p], "base64url segments must be unpadded")
        cases.check()

    def test_tq600a_13_vi_a_request_with_no_response_says_so(self):
        # covers: TQ-600a-13-vi
        # angle: failure
        """The service is unreachable (nothing listens): `main --publish` with the JWT on stdin fails with "no response" in the output
        and never prints "HTTP 0".

        Wrong version caught: a connection failure reported as the made-up status "HTTP 0".
        """
        hold = import_production(HOLD_MODULE)
        with tempfile.TemporaryDirectory() as raw:
            event = write_event(raw, pr_event(42))
            env = {"GITHUB_API_URL": "http://127.0.0.1:1", "GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": REPO, "GITHUB_EVENT_PATH": str(event), "HOLD_APP_ID": "1", "HOLD_APP_KEY_SET": "1"}
            out = io.StringIO()
            with mock.patch.dict(os.environ, env), mock.patch("sys.stdin", io.StringIO("aaa.bbb.ccc\n")), contextlib.redirect_stdout(out):
                code = hold.main(["--publish"])
        CHECK.assertEqual(1, code)
        CHECK.assertIn("no response", out.getvalue().lower())
        CHECK.assertNotIn("HTTP 0", out.getvalue())
