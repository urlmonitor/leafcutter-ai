"""TQ-600a-13-ix, review follow-ups: every failure still ends a failed check, and nothing outside the run history reads as it.

* M-1: the App's two clients (installation token, check run) are built with the configured, bounded timeout.
* M-2: ``--publish`` over an unreadable run history never concludes the check run ``success``.
* M-3: the fix-proof ``prepare`` step, which shares ``read_runs``, takes a failed or wrong-shape read as "no proof".
* M-4: a defect on the CONTENT path (a malformed job element, a malformed notice) is held, never the run-history headline.
* L-1: ``workflow_runs`` holding anything but objects is an unexpected shape; L-2: a foreign exception's cause is its type
  and a short path-free message; L-3: a TLS certificate error is not retried.
"""

from __future__ import annotations

import os
import ssl
import urllib.error
from unittest import mock

from ._app_harness import AppTestCase
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL
from ._ix_harness import (
    CAUSE, HEADLINE, NOTICES_PATH, RUNS_PATH, TIMEOUT, TIMEOUT_ENV, FaultCase, Sleeps, closed_port_url, evaluate, jobs_path, raw,
)
from ._notice_fakes import REPO, import_production

RED_RUN = 107
NO_PROOF = {"candidate": "false"}


class _Spy:
    """A ``GitHubClient`` factory that records the timeout each client is built with."""

    def __init__(self, module):
        self.seen, self._real = [], module.GitHubClient

    def __call__(self, *args, **kwargs):
        client = self._real(*args, **kwargs)
        self.seen.append(client._timeout)
        return client


class AppClientsAreBounded(FaultCase):
    def test_tq600a_13_ix_the_app_clients_use_the_configured_timeout(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix (it_requirements): the installation-token client and the check-run client are built with the env timeout."""
        publish = import_production("scripts.ci._hold_publish")
        token = import_production("scripts.ci._app_token")  # the installation-token client is built by the shared minting helper (TQ-600a-13-xv)
        spy, refused = _Spy(publish), closed_port_url()
        with mock.patch.object(publish, "GitHubClient", spy), mock.patch.object(token, "GitHubClient", spy), mock.patch.dict(os.environ, {TIMEOUT_ENV: str(TIMEOUT)}):
            for call in (lambda: publish._mint_token(refused, REPO, "jwt"), lambda: publish._create_check(refused, "token", REPO, "9" * 40)):
                with self.assertRaises(publish.PublishError):
                    call()
        CHECK.assertEqual([TIMEOUT, TIMEOUT], spy.seen, "both App clients must carry POST_MERGE_HOLD_TIMEOUT_SECONDS")


class PublishFailsClosed(AppTestCase):
    def test_tq600a_13_ix_publish_over_an_unreadable_history_never_concludes_success(self):
        # covers: TQ-600a-13-ix
        # angle: reachability
        """AC TQ-600a-13-ix: the job's real ``--publish`` path, run history unreadable: the job fails and the check run is not success."""
        self.seed("could_not_read")
        executed = self.execute()
        conclusions = [run["conclusion"] for run in self.svc.check_runs]
        CHECK.assertEqual("failure", executed.conclusion, executed.text[-900:])
        CHECK.assertEqual([], executed.says("run history could not be read"), executed.text[-900:])
        CHECK.assertTrue(conclusions and not {"success", "neutral", "skipped"} & set(conclusions), f"check run conclusions {conclusions}")


class FixProofPrepare(FaultCase):
    def _decide(self):
        client = import_production("scripts.ci._github_rest").GitHubClient(self.svc.url, "fake-token", timeout=TIMEOUT)
        return import_production("scripts.ci.post_merge_fix_proof")._decide(client, REPO, DECL)

    def test_tq600a_13_ix_the_fix_proof_prepare_step_takes_an_unreadable_history_as_no_proof(self):
        # covers: TQ-600a-13-ix
        # angle: failure
        """AC TQ-600a-13-ix: ``prepare`` (shares ``read_runs``) logs a warning and says no proof on a failed or wrong-shape read; control proves."""
        cases = Cases()
        for label, fault in [("wrong shape", raw(b'{"total_count": 0}')), ("a list", raw(b"[]")), ("non-object entries", raw(b'{"workflow_runs": [5]}')), ("not JSON", raw(b"<html>"))]:
            with cases.case(label):
                self.svc.reset()
                self.stage()
                self.svc.fail("GET", RUNS_PATH, fault)
                with self.assertLogs("post_merge_fix_proof", level="WARNING"):
                    outputs, reason = self._decide()
                CHECK.assertEqual(NO_PROOF, outputs, reason)
                CHECK.assertRegex(reason, r"(?i)could not be read.*no proof")
        with cases.case("control: a readable red history is a candidate"):
            self.svc.reset()
            self.stage()
            outputs, reason = self._decide()
            CHECK.assertEqual("true", outputs.get("candidate"), reason)
        cases.check()


class ContentDefectsAreNotAnUnreadableHistory(FaultCase):
    def _red(self, path, fault):
        self.svc.reset()
        self.stage(proof=False)
        self.svc.fail("GET", path, fault)
        return evaluate(self.svc.url, sleeps=Sleeps())

    def test_tq600a_13_ix_a_malformed_jobs_element_holds_the_run_as_did_not_complete(self):
        # covers: TQ-600a-13-ix
        # angle: discrimination
        """AC TQ-600a-13-ix: a job whose ``steps`` is not a list of objects is did_not_complete / unknown, never the run-history headline."""
        verdict = self._red(jobs_path(RED_RUN), raw(b'{"jobs": [{"name": "t", "steps": "oops"}]}'))
        CHECK.assertEqual(("did_not_complete", "unknown"), (verdict["state"], verdict.get("stage")), str(verdict))
        CHECK.assertNotRegex(verdict["reason"], HEADLINE)
        CHECK.assertRegex(verdict["reason"], r"(?i)jobs[^.\n]*could not be read")

    def test_tq600a_13_ix_a_malformed_notice_holds_the_run_as_red_with_a_note(self):
        # covers: TQ-600a-13-ix
        # angle: discrimination
        """AC TQ-600a-13-ix: a notice whose body is not text leaves the run held as red, noted, never could_not_read."""
        body = b'[{"number": 12, "state": "open", "html_url": "u", "body": 5, "labels": []}]'
        verdict = self._red(NOTICES_PATH, raw(body))
        CHECK.assertEqual("red", verdict["state"], str(verdict))
        CHECK.assertNotRegex(verdict["reason"], HEADLINE)
        CHECK.assertRegex(verdict["reason"], r"(?i)notice[^.\n]*could not be read")


class ShapeAndCauseWording(FaultCase):
    def test_tq600a_13_ix_a_runs_list_of_non_objects_is_an_unexpected_shape(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: ``workflow_runs`` holding anything but objects is could_not_read (unexpected shape); an empty list stays never_run."""
        cases = Cases()
        for label, body in [("a number", b'{"workflow_runs": [5]}'), ("a null", b'{"workflow_runs": [null]}'), ("a mix", b'{"workflow_runs": [{"id": 1}, "x"]}')]:
            with cases.case(label):
                self.svc.reset()
                self.green()
                self.svc.fail("GET", RUNS_PATH, raw(body))
                verdict = evaluate(self.svc.url, sleeps=Sleeps())
                CHECK.assertEqual("could_not_read", verdict["state"], str(verdict))
                CHECK.assertRegex(f"{verdict['cause']} {verdict['reason']}", CAUSE["list"])
        with cases.case("an empty list is a readable history"):
            self.svc.reset()
            self.svc.fail("GET", RUNS_PATH, raw(b'{"workflow_runs": []}'))
            CHECK.assertEqual("never_run", evaluate(self.svc.url, sleeps=Sleeps())["state"])
        cases.check()

    def test_tq600a_13_ix_a_foreign_exception_cause_is_its_type_and_a_short_path_free_message(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: ``cause_of`` of a non-GitHubError names the exception type and no file-system path, and is short."""
        cause = import_production("scripts.ci._hold_reads").cause_of(ValueError("cannot open /home/runner/work/secret/tunables.json " + "x" * 400))
        CHECK.assertTrue(cause.startswith("ValueError"), cause)
        CHECK.assertNotIn("/home", cause)
        CHECK.assertNotIn("tunables.json", cause)
        CHECK.assertLess(len(cause), 120)

    def test_tq600a_13_ix_a_tls_certificate_error_is_not_retried(self):
        # covers: TQ-600a-13-ix
        # angle: discrimination
        """AC TQ-600a-13-ix: a certificate that does not verify is asked once and is could_not_read; a refused connection still is retried."""
        failure = urllib.error.URLError(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"))
        sleeps = Sleeps()
        with mock.patch("urllib.request.urlopen", side_effect=failure) as opened:
            verdict = evaluate("https://api.example.invalid", sleeps=sleeps)
        CHECK.assertEqual("could_not_read", verdict["state"], str(verdict))
        CHECK.assertEqual((1, []), (opened.call_count, list(sleeps)), "a TLS certificate error is permanent: one attempt, no delay")
        CHECK.assertRegex(f"{verdict['cause']} {verdict['reason']}", r"(?i)certificate")
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(ConnectionRefusedError(111, "refused"))) as opened:
            evaluate("https://api.example.invalid", sleeps=Sleeps())
        CHECK.assertEqual(2, opened.call_count, "control: a refused connection is retried once")
