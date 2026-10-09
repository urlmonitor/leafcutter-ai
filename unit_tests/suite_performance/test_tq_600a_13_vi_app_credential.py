"""
Tests for TQ-600a-13-vi, App credential half -- the credential is minted per run, never written to the checkout, the workspace,
GITHUB_ENV, GITHUB_OUTPUT or any log, is used only for the hold's own check-run writes; and the no-pull-request-code invariant holds
unchanged with the App step in place (the App step never runs pull-request content). The job is EXECUTED against the recording
fake; afterwards the scratch tree, the output files, the captured logs and every recorded body are scanned for the key, every JWT
and every minted token.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml

ASSUMED PRODUCTION CONTRACT: see test_tq_600a_13_vi_app.py and test_tq_600a_13_vi_app_failure.py. The installation token authorises
only POST /check-runs and PATCH /check-runs/{id}; the JWT authorises only GET /repos/{repo}/installation and the access_tokens POST;
every other request (reads, the PR comment) uses the GITHUB_TOKEN.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from types import SimpleNamespace

import yaml

from ._app_fake import CHECK_NAME, GITHUB_TOKEN, key_pairs
from ._app_harness import APP_JOB_NAME, HEAD_SHA, AppTestCase, real_now, run_app_job, scan_for_credentials
from ._ending_harness import CHECK, Cases
from ._hold_harness import RED_JOBS, WORKFLOW, make_run
from ._notice_fakes import REPO
from ._workflow_jobs import find_job, load_workflow

ALWAYS_PASS = "import sys\nprint('HEAD MODULE ALWAYS PASSES')\nsys.exit(0)\n"
POISON = "from pathlib import Path\nPath('POISON-WAS-EXECUTED').write_text('x')\nprint('HEAD POISON RAN')\n"
HEAD_FILES = {"scripts/ci/post_merge_hold.py": ALWAYS_PASS, "scripts/ci/_github_rest.py": POISON, "scripts/ci/mint.sh": "echo HEAD MINT RAN\n"}
_CHECK_RUN_WRITE = re.compile(r"/repos/[^/]+/[^/]+/check-runs(/\d+)?")


class TestTq600a13viAppCredential(AppTestCase):
    def test_tq600a_13_vi_the_app_credential_is_never_persisted(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """A full pass and a full held evaluation, each scanned afterwards: neither the private key (whole, in lines, or its first and
        last 24 characters) nor any JWT nor the minted token is in any file under the scratch base (checkout, workspace, HOME,
        GITHUB_ENV / GITHUB_OUTPUT files), in any step log, or in any body the service recorded. A planted copy of the key IS found by
        the same scan, so a clean result is not the scanner's blindness. Each evaluation minted its own token. The token authorised
        exactly the check-run create and completion; the JWT only the installation lookup and the exchange; the GITHUB_TOKEN no
        check-run write.

        Wrong versions caught: the token exported to GITHUB_ENV or GITHUB_OUTPUT for a later step; the key written to a file in the
        workspace to sign the JWT and not removed; the token or a JWT echoed to a log; one credential reused across evaluations;
        the installation token used for a read or the PR comment; the GITHUB_TOKEN used for a check run.
        """
        cases = Cases()
        with cases.case("the scanner can see a planted key"):
            with tempfile.TemporaryDirectory() as raw:
                planted = Path(raw) / "workspace" / "key.pem"
                planted.parent.mkdir()
                planted.write_text(key_pairs()[0].private_pem, encoding="utf-8")
                outcome = SimpleNamespace(result=SimpleNamespace(log_text=lambda: ""))
                CHECK.assertTrue(scan_for_credentials(self.svc, raw, outcome), "scan_for_credentials missed a planted private key")
        now = real_now()
        red = make_run(7, "failure", hours_ago=0.5, now=now)
        executions = []
        for label, runs, jobs in (("pass", [make_run(6, "success", hours_ago=1, now=now)], {}), ("held", [make_run(6, "success", hours_ago=3, now=now), red], {red["id"]: RED_JOBS})):
            with cases.case(label):
                self.serve(runs, jobs)
                executed = self.execute()
                executions.append(executed)
                CHECK.assertEqual("success" if label == "pass" else "failure", executed.conclusion, executed.text[-600:])
                CHECK.assertEqual([], executed.leaks)
        with cases.case("who authorised what"):
            CHECK.assertEqual(2, len(set(self.svc.minted)), "one fresh token per evaluation")
            kinds = {}
            for entry in self.svc.log:
                kinds.setdefault(self.svc.auth_kind(entry), set()).add((entry["method"], "check-run" if _CHECK_RUN_WRITE.fullmatch(entry["path"]) else entry["path"]))
            CHECK.assertEqual({("POST", "check-run"), ("PATCH", "check-run")}, kinds.get("install"))
            CHECK.assertEqual({("GET", f"/repos/{REPO}/installation"),("POST", "/app/installations/777/access_tokens")}, kinds.get("jwt"))
            CHECK.assertEqual([], [e for e in kinds.get("github_token", set()) if e[1] == "check-run"], "the GITHUB_TOKEN must never write a check run")
            CHECK.assertEqual({"install", "jwt", "github_token"}, set(kinds), "no request may go out unauthenticated or with another credential")
            CHECK.assertEqual(GITHUB_TOKEN, next(e["auth"] for e in self.svc.log if e["path"].endswith("post-merge-suite.yml")))
        cases.check()

    def test_tq600a_13_vi_the_app_step_never_runs_pull_request_content(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The no-pull-request-code invariant, extended to the App step. The default-branch copy of the job runs for a pull request
        whose HEAD carries an always-pass hold module, a poisoned REST client and a mint script. With a red history the job still
        fails, the App's check run on the head completes as failure, no checkout names a ref, nothing of the head was opened, none
        of its code ran (no marker file, no output), and no credential leaked. The control (green history) passes.

        Wrong versions caught: the checkout gains `ref: <head sha>` so the token-bearing steps run the head's code; the mint or
        the module is taken from the head; the token is passed to a step that runs head content.
        """
        cases = Cases()
        now = real_now()
        red = make_run(7, "failure", hours_ago=1, now=now)
        with cases.case("red history, head carries poisoned code"):
            self.serve([make_run(6, "success", hours_ago=3, now=now), red], {red["id"]: RED_JOBS})
            with tempfile.TemporaryDirectory() as raw:
                outcome = run_app_job(self.svc, Path(raw), head_files=HEAD_FILES)
                head = str(outcome.head_dir)
                CHECK.assertEqual("failure", outcome.result.conclusion, outcome.result.log_text()[-900:])
                CHECK.assertEqual([], [c for c in outcome.run.checkouts if c["ref"]], "no checkout may name a ref")
                CHECK.assertEqual([], [e["path"] for e in outcome.opened() if e["path"].startswith(head)])
                text = outcome.result.log_text()
                CHECK.assertEqual([], [m for m in ("ALWAYS PASSES", "HEAD POISON RAN", "HEAD MINT RAN") if m in text])
                CHECK.assertEqual([], [str(p) for p in Path(raw).rglob("POISON-WAS-EXECUTED")])
                CHECK.assertEqual([], scan_for_credentials(self.svc, raw, outcome))
            CHECK.assertEqual([(CHECK_NAME, HEAD_SHA, "completed", "failure")], [(r["name"], r["head_sha"], r["status"], r["conclusion"]) for r in self.svc.check_runs])
        with cases.case("control: green history"):
            self.seed("pass")
            executed = self.execute(head_files=HEAD_FILES)
            CHECK.assertEqual("success", executed.conclusion, executed.text[-600:])
        cases.check()

    def test_tq600a_13_vi_the_app_trust_check_goes_red_when_the_checkout_takes_the_head(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The trust descriptor above must be able to fail. Take the real workflow, give its checkout `ref: <head sha>`, serialize it
        with yaml.safe_dump and execute it with the secrets: the emulated checkout materialises the head's always-pass module, the
        job ends success on a RED history, and the checkout names the head. If this stays held, the executor no longer honours `ref`.

        Wrong version caught: the checkout step gaining `ref:` while holding the App credential.
        """
        doc = load_workflow(WORKFLOW)
        found = find_job(doc, APP_JOB_NAME)
        CHECK.assertIsNotNone(found, f"{WORKFLOW.name} has no job named {APP_JOB_NAME!r}")
        checkouts = [s for s in found[1]["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
        CHECK.assertTrue(checkouts, "the module must reach the runner through actions/checkout")
        checkouts[0].setdefault("with", {})["ref"] = HEAD_SHA
        red = make_run(7, "failure", hours_ago=1, now=real_now())
        self.serve([make_run(6, "success", now=real_now()), red], {red["id"]: RED_JOBS})
        with tempfile.TemporaryDirectory() as raw:
            mutated, run_dir = Path(raw) / "mutated.yml", Path(raw) / "run"
            run_dir.mkdir()
            mutated.write_text(yaml.safe_dump(doc), encoding="utf-8")
            outcome = run_app_job(self.svc, run_dir, workflow=mutated, head_files=HEAD_FILES)
        CHECK.assertEqual("success", outcome.result.conclusion, "the head's always-pass module should have released the hold")
        CHECK.assertEqual([HEAD_SHA], [c["ref"] for c in outcome.run.checkouts])
