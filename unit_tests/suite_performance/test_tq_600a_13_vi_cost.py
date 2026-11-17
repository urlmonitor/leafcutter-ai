"""
Tests for TQ-600a-13-vi, cost half -- one evaluation makes a small FIXED number of reads that does not grow with
the repository, starts no test session and no build, opens nothing under tests/ or unit_tests/, and stores no
verdict between evaluations. Shown by counting what the fake service receives and by observing the job's OWN
Python process (a sitecustomize audit hook: child processes, file opens, imports), never by patching.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

.github/workflows/post-merge-hold.yml -- the job named exactly `Post-merge hold evaluation`; its ``run:`` steps are executed
verbatim by the shared executor, so the step must work with only what the job environment gives it: GITHUB_API_URL,
GITHUB_TOKEN, GITHUB_REPOSITORY and GITHUB_EVENT_PATH (the workflow may pass them through env: as
``${{ github.api_url }}`` / ``${{ github.token }}`` / ``${{ github.repository }}`` / ``${{ github.event_path }}``; the executor
now resolves those four). The step runs ``python scripts/ci/post_merge_hold.py ...`` on the system Python, stdlib only, from a
checkout that holds ONLY ``scripts/ci`` of the default branch; exit 0 on state "pass", non-zero on every other state,
and it prints the verdict's ``reason`` (so the output names the run by link and conclusion).
Read counts, per path, excluding comment-list pages (-vii): pass = workflow + runs; held (a failed run) = workflow +
runs + jobs + notices.
======================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ._app_harness import AppTestCase
from ._ending_harness import CHECK, Cases
from ._hold_harness import RED_JOBS, fresh_base, make_run, run_hold_job
from ._notice_fakes import old_description

PASS_READS = ["runs", "workflow"]
HELD_READS = ["jobs", "notices", "runs", "workflow"]
NOTICE_QUERY = {"labels": ["post-merge-red"], "state": ["all"], "sort": ["updated"], "direction": ["desc"], "per_page": ["30"]}


def _real_now():
    return datetime.now(timezone.utc)


def _writes(events):
    return [e for e in events if e["kind"] == "open" and any(c in e["mode"] for c in "wax+")]


def _under_tests(events):
    return [e["path"] for e in events if e["kind"] == "open" and {"tests", "unit_tests"} & set(Path(e["path"]).parts)]


class TestTq600a13viCost(AppTestCase):  # the job mints the hold App's token, so the service must serve the App plane
    def _execute(self):
        """Run the real job once; return (outcome, the reads it made, what it left in its HOME)."""
        self.svc.requests.clear()
        with fresh_base() as raw:
            outcome = run_hold_job(self.svc, Path(raw))
            left = sorted(p.name for p in outcome.state_dir.rglob("*"))
        return outcome, self.svc.read_kinds(), left

    def _history(self, count, *, now):
        """``count`` runs, newest first, the newest one green and started 1 h ago."""
        return [make_run(number, "success", hours_ago=1 + (count - number), now=now) for number in range(count, 0, -1)]

    def test_tq600a_13_vi_the_check_costs_a_fixed_number_of_reads_and_no_tests(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """Pass path: exactly the workflow-state read and one run-history read, zero child processes, nothing opened under
        tests/ or unit_tests/, no pytest import, nothing written. Serve 500 issues and 500 runs: the SAME request count.
        Flip the latest run to failure and evaluate the same pull request again: held, with exactly reads (1)-(4), the
        notice read carrying the stated query, and nothing stored between the two evaluations.

        Wrong versions caught: the check runs the test runner to confirm the result (a child process / a pytest import);
        it pages through every run or issue (the request count grows with the repository); it caches the first verdict per
        pull request (the flip stays green); the step opens a file under tests/ or unit_tests/.
        """
        cases = Cases()
        now = _real_now()
        with cases.case("pass path, small repository"):
            self.serve(self._history(3, now=now))
            outcome, kinds, left = self._execute()
            CHECK.assertEqual("success", outcome.result.conclusion, outcome.result.log_text()[-1200:])
            CHECK.assertEqual(PASS_READS, kinds)
            CHECK.assertEqual([], outcome.processes())
            CHECK.assertEqual([], _under_tests(outcome.events))
            CHECK.assertFalse({"pytest", "_pytest"} & outcome.imported(), "the check must not import the test runner")
            CHECK.assertEqual(([], []), (_writes(outcome.events), left), "nothing is written or stored by an evaluation")
        with cases.case("pass path, 500 runs and 500 issues"):
            self.svc.reset()
            self.serve(self._history(500, now=now))
            for number in range(1, 501):
                self.svc.add_issue(number, body=old_description(number), labels=["post-merge-red"], state="closed")
            outcome, kinds, _ = self._execute()
            CHECK.assertEqual("success", outcome.result.conclusion, outcome.result.log_text()[-1200:])
            CHECK.assertEqual(PASS_READS, kinds, "the number of reads must not grow with the repository")
        with cases.case("the same pull request after the latest run turned red"):
            self.svc.reset()
            red = make_run(501, "failure", hours_ago=0.5, now=now)
            self.serve([red, *self._history(500, now=now)], {red["id"]: RED_JOBS})
            for number in range(1, 501):
                self.svc.add_issue(number, body=old_description(number), labels=["post-merge-red"])
            outcome, kinds, left = self._execute()
            CHECK.assertEqual(("failure", []), (outcome.result.conclusion, outcome.processes()))
            CHECK.assertEqual(HELD_READS, kinds)
            CHECK.assertEqual(NOTICE_QUERY, dict(next(q for kind, q in self.svc.reads() if kind == "notices")))
            jobs_query = next(q for kind, q in self.svc.reads() if kind == "jobs")
            CHECK.assertEqual(["latest"], jobs_query.get("filter"))
            CHECK.assertEqual(([], []), (_writes(outcome.events), left))
        cases.check()
