"""
Tests for TQ-600a-13-xv (notice half) -- the pull requests whose hold could not be re-run are named, with the reason,
on the canonical `post-merge-red` notice when one is open.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

``post_merge_notice.py apply`` gains an optional ``--unrerunnable TEXT``: the JSON text of the ``reevaluate`` job's
``unrerunnable`` output (a list of {pr, head_sha, reason}); the workflow passes it from ``needs.reevaluate.outputs`` through
``env:`` (never inside a ``run:`` line). Absent, empty, ``[]`` or unparseable text names nothing and never stops the
verdict's own writes. For a red or did-not-complete run (the runs that create or update the notice) the description
carries ONE line per entry that names the pull request as ``#<pr>`` and contains the ``reason`` text verbatim. A green run
never creates a notice for it: with none open, a green run writes nothing at all.
"""

from __future__ import annotations

import json
import os
import re
import unittest
from unittest import mock

from ._ending_harness import Cases
from ._notice_fakes import LABEL, REPO, NoticeTestCase, captured_logs, make_verdict, old_description, run_record
from ._reeval_harness import expected_named

REFUSED = [(14, "D", 403)]
NAMED = expected_named(refused=REFUSED)
NAMED_TEXT = json.dumps(NAMED)


def _lines_naming(body, pr):
    return [line for line in body.splitlines() if re.search(rf"#{pr}\b", line)]


class TestTq600a13XvNoticeCarriesUnrerunnable(NoticeTestCase):
    needs_repo = True

    def _apply(self, verdict, run_id, unrerunnable):
        """Run ``post_merge_notice.main(apply ...)`` with ``--unrerunnable`` when given; returns (exit code, log)."""
        path = self.tmp / "post-merge-verdict.json"
        try:
            path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            message = f"cannot stage the verdict file: {exc}"
            raise AssertionError(message) from exc
        argv = ["apply", "--api-url", self.svc.url, "--repo", REPO, "--repo-dir", str(self.repo.path), "--run-id", str(run_id), "--verdict-file", str(path)]
        if unrerunnable is not None:
            argv += ["--unrerunnable", unrerunnable]
        with captured_logs() as lines, mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
            code = self.notice.main(argv)
        return code, "\n".join(lines)

    def _red(self, unrerunnable, *, open_notice=False):
        """Apply a red run 102 and return the description the notice was created or edited with."""
        self.svc.reset()
        self.svc.runs = [run_record(2, "failure", head_sha=self.repo.r)]
        if open_notice:
            self.svc.add_issue(5, title="Post-merge suite is red", body=old_description(101), labels=[LABEL])
        code, log = self._apply(make_verdict("red", run_id=102, head_sha=self.repo.r, failing=["tests/test_a.py::test_a"]), 102, unrerunnable)
        self.assertEqual(0, code, log)
        written = self.svc.writes_of("edit" if open_notice else "create")
        self.assertEqual(1, len(written), self.svc.writes())
        return written[0][1]["body"]

    def test_tq600a_13_xv_the_notice_names_each_unrerunnable_pull_request_with_its_reason(self):
        # covers: TQ-600a-13-xv
        # angle: seam
        """The REAL `unrerunnable` JSON (built by the harness serializer) goes into the REAL notice writer; the description names each PR.

        Rows: a notice created on a red run, and the canonical notice edited when one is already open. Each names #13 with
        older_than_30_days, #14 with rerun_refused_403 and #15 with no_hold_run, one line per pull request. Controls: no
        option, ``[]`` and empty text name no pull request and no reason.
        """
        rows = Cases()
        for label, open_notice in {"created": False, "edited, one open": True}.items():
            body = self._red(NAMED_TEXT, open_notice=open_notice)
            for entry in NAMED:
                with rows.case(f"{label}: #{entry['pr']}"):
                    named = _lines_naming(body, entry["pr"])
                    self.assertEqual(1, len(named), f"one line names #{entry['pr']}:\n{body}")
                    self.assertIn(entry["reason"], named[0])
        for label, text in {"option absent": None, "empty list": "[]", "empty text": ""}.items():
            body = self._red(text)
            with rows.case(f"control: {label}"):
                self.assertFalse([e for e in NAMED if _lines_naming(body, e["pr"]) or e["reason"] in body], body)
        rows.check()

    def test_tq600a_13_xv_unusable_unrerunnable_text_never_stops_the_notice_and_green_creates_nothing(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """Unparseable text still writes the red notice (naming nothing); a green run with no notice open writes nothing.

        The re-run job and the notice job are separate on purpose (the issue token and the re-run token never share a job),
        so a broken hand-over must degrade to "not named", never to "no notice".
        """
        rows = Cases()
        for label, text in {"not json": "not json", "wrong shape": '{"pr": 13}', "an entry without a pr": '[{"reason": "no_hold_run"}]'}.items():
            with rows.case(label):
                body = self._red(text)
                self.assertFalse([e for e in NAMED if e["reason"] in body], body)
        self.svc.reset()
        self.svc.runs = [run_record(3, "success", head_sha=self.repo.r)]
        code, log = self._apply(make_verdict("green", run_id=103, head_sha=self.repo.r), 103, NAMED_TEXT)
        with rows.case("green, none open"):
            self.assertEqual(0, code, log)
            self.assertEqual([], self.svc.write_attempts, "a green run never opens a notice for pull requests that could not be re-run")
        rows.check()


if __name__ == "__main__":
    unittest.main()
