"""
Tests for TQ-600a-13-xi, the hold App's slice of the allowed-write list -- the hold's evaluation job, run along its pass and held
paths against the recording fake, makes only these writes: the credential exchange (JWT), the check-run create and completion
(installation token, name exactly `Post-merge suite status`, head sha equal to the event's), and its single PR comment (GITHUB_TOKEN).
Anything else -- a commit status, a check run from the GITHUB_TOKEN, a check run under another name or on another sha, an issue or
comment write by the installation token, a ref, contents or workflow write -- fails the test.

Not covered here (belongs to -xi's own build): the client allowlist in scripts/ci/_github_rest.py that REFUSES such a write before
sending it (that file has no allowlist yet), the scope descriptor over every family workflow, and the mutation descriptor.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xi.yaml and TQ-600a-13-vi.yaml
"""

from __future__ import annotations

import re

from ._app_fake import CHECK_NAME
from ._app_harness import HEAD_SHA, AppTestCase, real_now
from ._ending_harness import CHECK, Cases
from ._notice_fakes import REPO

PR = 42
CHECK_RUNS = re.compile(rf"/repos/{re.escape(REPO)}/check-runs(/\d+)?")
PR_COMMENT = re.compile(rf"/repos/{re.escape(REPO)}/issues/(?:{PR}/comments|comments/\d+)")
EXCHANGE = "/app/installations/777/access_tokens"


class TestTq600a13xiAppWrites(AppTestCase):
    def _violations(self):
        """Every recorded non-GET request that is not on the allowed list, described."""
        bad = []
        for entry in self.svc.log:
            if entry["method"] == "GET":
                continue
            kind, path, body = self.svc.auth_kind(entry), entry["path"], entry["body"] or {}
            check_write = CHECK_RUNS.fullmatch(path) is not None
            if entry["method"] == "POST" and path == EXCHANGE and kind == "jwt":
                continue
            if check_write and kind == "install" and entry["method"] in ("POST", "PATCH"):
                if entry["method"] == "POST" and (body.get("name"), body.get("head_sha")) != (CHECK_NAME, HEAD_SHA):
                    bad.append(f"check run created as {body.get('name')!r} on {body.get('head_sha')!r}")
                continue
            if PR_COMMENT.fullmatch(path) and kind == "github_token":
                continue
            bad.append(f"{entry['method']} {path} authorised by {kind}")
        return bad

    def test_tq600a_13_xi_the_hold_job_writes_only_the_allowed_set(self):
        # covers: TQ-600a-13-xi
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """Run the real evaluation job on a pass path and on a held path: every recorded write is on the allowed list, and each path
        made the check-run create and completion (so the subset check is over a non-empty set), and the held path also commented.
        The installation token made no write but those two; the GITHUB_TOKEN made no check-run or status write.

        Wrong versions caught: a commit status or a check run written with the GITHUB_TOKEN; a check run under another name or on
        github.sha; the installation token used for the PR comment or an issue write; an extra step that pushes, dispatches or
        re-runs (any such request is an unlisted write).
        """
        cases = Cases()
        for state in ("pass", "red"):
            with cases.case(state):
                self.seed(state, real_now())
                executed = self.execute()
                CHECK.assertEqual("success" if state == "pass" else "failure", executed.conclusion, executed.text[-600:])
                CHECK.assertEqual([], self._violations())
                CHECK.assertEqual((1, 1), (len(self.svc.check_posts()), len(self.svc.check_patches())))
                commented = [e for e in self.svc.log if e["method"] == "POST" and PR_COMMENT.fullmatch(e["path"])]
                CHECK.assertEqual(state == "red", bool(commented), "a held pull request gets its one comment; a pass gets none")
        cases.check()
