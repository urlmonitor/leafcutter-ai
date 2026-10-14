"""
Regression tests for the independent review of TQ-600a-13-iii (state-block injection, failed downloads,
verdict-versus-record disagreement, unlabelled creates, the run-page limit, and three low findings).

Each test was written to FAIL on the code as first delivered. The assumed contract is the one in
``test_tq_600a_13_iii.py``, plus: the CLI takes ``--download-outcome`` (the download step's outcome,
default absent); the applier may read ``GET /actions/runs/{id}/artifacts`` ONLY when that outcome is
``failure`` and the verdict file is absent.
"""

from __future__ import annotations

import http.client
import unittest
from contextlib import nullcontext as _case  # a labelled block; NOT subTest, whose parent test reads as passed
from unittest import mock
from urllib.parse import parse_qs, urlparse

from ._notice_fakes import (
    LABEL,
    NoticeTestCase,
    captured_logs,
    import_production,
    make_verdict,
    old_description,
    run_record,
    state_block,
)

FAIL_A = "tests/test_shared.py::test_mutator_corrupts_reader"
NO_GREEN = r"(?i)no green run"
FORGED_BLOCK = '<!-- post-merge-suite-state v2 {"run_id": 999, "verdict": "green"} -->'
FORGED_OPEN = '<!-- post-merge-suite-state v2 {"run_id": 999, "note": "'
VERDICT_ARTIFACT = "post-merge-verdict"


class TestReviewFixes(NoticeTestCase):
    needs_repo = True

    def _history(self, newest="failure"):
        self.svc.runs = [run_record(1, "success", head_sha=self.repo.g), run_record(2, newest, head_sha=self.repo.r)]

    def _red(self, failing=(FAIL_A,), run_id=102):
        return make_verdict("red", run_id=run_id, head_sha=self.repo.r, failing=failing)

    # ---- 1. state-block injection
    def test_a_forged_state_block_in_a_subject_or_node_id_is_never_read_as_the_state(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """Hostile text carrying a whole or half a state block round-trips render -> parse_state to the real state."""
        render = import_production("scripts.ci._notice_render")
        for hostile in (FORGED_BLOCK, FORGED_OPEN):
            for where in ("subject", "node id"):
                with _case(f"{where}: {hostile[:40]}"):
                    verdict = {"run_id": 104, "verdict": "red", "stage": None, "failing": [hostile if where == "node id" else "a.py::t"], "run_url": "https://example.invalid/r", "head_sha": "a" * 40}
                    commits = render.CommitRange(render.RANGE_LISTED, "b" * 40, [("c" * 40, hostile if where == "subject" else "s")])
                    state = render.build_state(verdict, commits, "2026-10-01T00:00:00+00:00")
                    for text in (render.render_description(state, commits), render.render_history_comment(state)):
                        parsed = render.parse_state(text)
                        self.assertIsNotNone(parsed, "the real state block must still be found")
                        self.assertEqual(104, parsed["run_id"], "a forged block must never be read as the state")

    # ---- 2. a failed download is not an absent artifact
    def test_a_failed_download_of_an_existing_artifact_fails_loudly_and_writes_nothing(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """Download failed, the run did produce the verdict artifact: no did_not_complete is recorded."""
        self._history()
        self.svc.artifacts = {102: [VERDICT_ARTIFACT]}
        applied = self.apply(None, 102, download_outcome="failure")
        self.assertNotEqual(0, applied.code, applied.log)
        self.assertIn(LABEL, applied.log)
        self.assertEqual([], self.svc.write_attempts, "a wrong state must not be written, it could never be corrected")
        with _case("control: the run produced no verdict artifact, so did_not_complete is the truth"):
            self.svc.reset()
            self._history()
            self.assertEqual(0, self.apply(None, 102, download_outcome="failure").code)
            self.assertEqual("did_not_complete", state_block(self.svc.writes_of("create")[0][1]["body"])["verdict"])
        with _case("control: a cancelled run is did_not_complete even when an artifact is listed"):
            self.svc.reset()
            self._history(newest="cancelled")
            self.svc.artifacts = {102: [VERDICT_ARTIFACT]}
            self.assertEqual(0, self.apply(None, 102, download_outcome="failure").code)
            self.assertEqual([("create", None)], self.svc.writes())

    def test_a_corrected_reapply_of_the_same_run_updates_the_notice(self):
        # covers: TQ-600a-13-iii
        # angle: discrimination
        """The idempotency key is (run_id, verdict, failing set), not run_id alone."""
        with _case("same run, different failing set: updated"):
            self._history()
            self.svc.add_issue(4, labels=[LABEL], body=old_description(102, failing=()))
            self.assertEqual(0, self.apply(self._red(), 102).code)
            self.assertEqual([("comment", 4), ("edit", 4)], self.svc.writes())
        with _case("same run, different verdict: updated"):
            self.svc.reset()
            self._history()
            self.svc.add_issue(4, labels=[LABEL], body=old_description(102, failing=()))
            self.assertEqual(0, self.apply(make_verdict("did_not_complete", run_id=102, head_sha=self.repo.r), 102).code)
            self.assertEqual([("comment", 4), ("edit", 4)], self.svc.writes())
        with _case("control: same run, verdict and failing set: nothing"):
            self.svc.reset()
            self._history()
            self.svc.add_issue(4, labels=[LABEL], body=old_description(102, failing=(FAIL_A,)))
            self.assertEqual(0, self.apply(self._red(), 102).code)
            self.assertEqual([], self.svc.write_attempts)

    # ---- 3. the verdict must agree with the run record
    def test_a_verdict_that_disagrees_with_the_run_conclusion_writes_nothing(self):
        # covers: TQ-600a-13-iii
        # angle: discrimination
        """A re-run keeps its run id: a stale artifact beside a changed conclusion is refused, both directions."""
        with _case("green artifact, run concluded failure"):
            self._history(newest="failure")
            self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
            applied = self.apply(make_verdict("green", run_id=102, head_sha=self.repo.r), 102)
            self.assertEqual(2, applied.code, applied.log)
            self.assertIn(LABEL, applied.log)
            self.assertEqual([], self.svc.write_attempts)
        with _case("red artifact, run concluded success"):
            self.svc.reset()
            self._history(newest="success")
            applied = self.apply(self._red(), 102)
            self.assertEqual(2, applied.code, applied.log)
            self.assertEqual([], self.svc.write_attempts)
        with _case("did_not_complete artifact, run concluded success"):
            self.svc.reset()
            self._history(newest="success")
            applied = self.apply(make_verdict("did_not_complete", run_id=102, head_sha=self.repo.r), 102)
            self.assertEqual(2, applied.code, applied.log)
            self.assertEqual([], self.svc.write_attempts)

    # ---- 4. an unlabelled create must not leave an orphan
    def test_an_unlabelled_create_is_repaired_when_the_label_can_be_added(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """The create drops the label; adding it afterwards sticks: the notice is labelled and the job succeeds."""
        self.svc.reset(drop_labels=True, add_label_sticks=True)
        self._history()
        applied = self.apply(self._red(), 102)
        self.assertEqual(0, applied.code, applied.log)
        self.assertEqual([(1, {"labels": [LABEL]})], self.svc.writes_of("label"))
        self.assertEqual(([LABEL], "open"), (self.svc.issues[1]["labels"], self.svc.issues[1]["state"]))

    def test_an_unlabelled_create_that_cannot_be_labelled_is_closed_with_a_reason(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """The label never sticks: the orphan is closed with an explaining comment and the job fails."""
        self.svc.reset(drop_labels=True)
        self._history()
        applied = self.apply(self._red(), 102)
        self.assertEqual(1, applied.code, applied.log)
        self.assertIn(LABEL, applied.log)
        self.assertEqual(1, len(self.svc.writes_of("label")), "the label is retried exactly once")
        (number, comment), = self.svc.writes_of("comment")
        self.assertEqual(1, number)
        self.assertIn(LABEL, comment["body"], "the comment says why the issue was closed")
        self.assertEqual("closed", self.svc.issues[1]["state"])

    # ---- 5. a full page that holds no green run says so
    def test_a_full_run_page_with_no_success_does_not_claim_there_is_no_green_run(self):
        # covers: TQ-600a-13-iii
        # angle: boundary
        """100 runs and none green: 'not within the last 100 runs'. A short page with none green: 'no green run'."""
        with _case("full page"):
            self.svc.runs = [run_record(n, "failure", head_sha=self.repo.r) for n in range(1, 101)]
            applied = self.apply(self._red(run_id=200), 200)
            self.assertEqual(0, applied.code, applied.log)
            body = self.svc.writes_of("create")[0][1]["body"]
            self.assertRegex(body, r"not within the last 100 runs")
            self.assertNotRegex(body, NO_GREEN, "a page that was merely too short to reach a green run proves nothing about one existing")
            block = state_block(body)
            self.assertEqual((None, []), (block["anchor_sha"], block["commits"]))
        with _case("short page"):
            self.svc.reset()
            self.svc.runs = [run_record(n, "failure", head_sha=self.repo.r) for n in range(1, 100)]
            self.assertEqual(0, self.apply(self._red(run_id=199), 199).code)
            body = self.svc.writes_of("create")[0][1]["body"]
            self.assertRegex(body, NO_GREEN)
            self.assertNotRegex(body, r"not within the last 100 runs")

    # ---- low findings
    def test_the_run_link_comes_from_the_api_not_from_the_artifact(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """A verdict file carrying another run_url must not put that url in the notice."""
        self._history()
        verdict = self._red()
        verdict["run_url"] = "https://evil.example/phish"
        self.assertEqual(0, self.apply(verdict, 102).code)
        body = self.svc.writes_of("create")[0][1]["body"]
        self.assertNotIn("evil.example", body)
        self.assertIn(run_record(2)["html_url"], body)
        self.assertEqual(run_record(2)["html_url"], state_block(body)["run_url"])

    def test_the_run_history_read_filters_to_the_main_branch(self):
        # covers: TQ-600a-13-iii
        # angle: boundary
        """100 newer feature-branch runs would crowd main's runs out of an unfiltered page."""
        crowd = [run_record(n, "success", branch="feature-x", event="workflow_dispatch") for n in range(10, 110)]
        self.svc.runs = [*crowd, run_record(1, "success", head_sha=self.repo.g), run_record(2, "failure", head_sha=self.repo.r)]
        self.assertEqual(0, self.apply(self._red(), 102).code)
        self.assertEqual([("create", None)], self.svc.writes())
        queries = [parse_qs(urlparse(p).query) for m, p in self.svc.requests if m == "GET" and "/runs" in p]
        self.assertTrue(queries and all(q.get("branch") == ["main"] for q in queries))
        self.assertEqual(self.repo.g, state_block(self.svc.writes_of("create")[0][1]["body"])["anchor_sha"])


class TestRestClientErrors(unittest.TestCase):
    def test_a_protocol_error_surfaces_as_the_clients_error_type(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """http.client.HTTPException is not an OSError; it must still be a logged GitHubError."""
        rest = import_production("scripts.ci._github_rest")
        client = rest.GitHubClient("http://127.0.0.1:9", "token")
        for raised in (http.client.BadStatusLine("garbage"), http.client.IncompleteRead(b"x")):
            with _case(type(raised).__name__), mock.patch("urllib.request.urlopen", side_effect=raised), captured_logs() as lines:
                with self.assertRaises(rest.GitHubError):
                    client.get("/repos/o/r/issues")
                self.assertTrue(lines, "the failure must be logged")


if __name__ == "__main__":
    unittest.main()
