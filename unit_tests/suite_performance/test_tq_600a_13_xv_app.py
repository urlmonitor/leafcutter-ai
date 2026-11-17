"""
Tests for TQ-600a-13-xv (App credential half, AMENDED 2026-10-12, owner decision) -- the re-runs are requested with the dedicated hold App's
installation token, minted in the `reevaluate` job for `{actions: write}` on this repository only; every read stays on the GITHUB_TOKEN.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml and TQ-600a-13-xi.yaml

The JWT-minting shell step needs ``openssl`` and a private key, so the Python side is also driven in-process by injecting the JWT on
stdin, the way the -vi App tests do (``run_reeval(jwt=...)``); the executed-job rows run the REAL step against the same fake, whose
App plane verifies a real RS256 signature.
"""

from __future__ import annotations

import json
import re
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from ._app_fake import APP_ID, MASK, mask_lines, without_masks
from ._ending_harness import Cases
from ._hold_harness import scratch_default_branch
from ._notice_fakes import REPO
from ._reeval_harness import PROOF_NAME, SHAS, SUITE_NAME, ReevalService, app_secrets_env, run_reeval, seed_world, suite_history, write_event
from ._workflow_jobs import REPO_ROOT, WorkflowRun

FOLLOWUP = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
WOULD_RERUN = [(11, "A"), (14, "D"), (16, "F")]  # the completed holds the fan-out re-runs (runs 1005, 1009, 1011)
INSTALL_LOOKUP = f"/repos/{REPO}/installation"
RUN_READ = re.compile(rf"/repos/{re.escape(REPO)}/actions/runs/\d+")
ACTIONS_WRITE = {"permissions": {"actions": "write"}, "repositories": [REPO.split("/")[1]]}
DUMP_ENV = textwrap.dedent(  # a sitecustomize that records the environment every python child starts with
    """
    import json, os
    if os.environ.get("REEVAL_ENV_DUMP"):
        with open(os.environ["REEVAL_ENV_DUMP"] + "." + str(os.getpid()), "w", encoding="utf-8") as handle:
            json.dump(dict(os.environ), handle)
    """
)


def _named(reason):
    """Every PR the fan-out names when each would-be re-run is named ``reason`` (C is too old and E has no hold run, as always)."""
    named = {13: (SHAS["C"], "older_than_30_days"), 15: (SHAS["E"], "no_hold_run")}
    named.update({pr: (SHAS[key], reason) for pr, key in WOULD_RERUN})
    return [{"pr": pr, "head_sha": sha, "reason": why} for pr, (sha, why) in sorted(named.items())]


class _Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = ReevalService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def _run(self, name=SUITE_NAME, run_id=102, head_sha=SHAS["A"], *, history=("success", "failure"), installed=True, exchange_status=None, grant=None, on_rerun=None, **kwargs):
        self.svc.reset()
        seed_world(self.svc)
        suite_history(self.svc, *history)
        self.svc.installed, self.svc.exchange_status = installed, exchange_status
        self.svc.grant_override, self.svc.on_rerun = grant or {}, on_rerun
        with tempfile.TemporaryDirectory() as raw:
            return run_reeval(self.svc, Path(raw), name, run_id, head_sha, **kwargs)

    def _leaks(self, result):
        """Where a credential (key body, minted token, JWT) shows in what the job printed or wrote to its output file."""
        text = without_masks(result.log) + "\n".join(result.lines)  # the masking command is the one place a value is printed (the runner hides it)
        return [needle[:8] for needle in self.svc.credential_needles() if needle in text]


class TestRerunUsesTheAppToken(_Case):
    def test_tq600a_13_xv_the_reruns_carry_the_installation_token_minted_for_actions_write_on_this_repository(self):
        # covers: TQ-600a-13-xv
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """An App re-run of a pull_request_target hold run is requested and accepted; the token is minted once, for `{actions: write}` on
        this repository only; every re-run POST is authorised by that token; every read (the history, the pull requests, the hold runs
        and the client's own pre-read of each run) stays on the GITHUB_TOKEN, the only other credential being the JWT of the installation
        lookup. Wrong versions caught: a re-run POST with the GITHUB_TOKEN; a token minted with more permissions, without a repository
        limit, or once per re-run; a read made with the installation token; the credential printed or written to the output file."""
        rows = Cases()
        result = self._run()
        with rows.case("the three completed holds are re-run and the job succeeds"):
            self.assertEqual(0, result.code, result.log)
            self.assertEqual([1005, 1009, 1011], self.svc.rerun_ids())
            self.assertEqual([], self.svc.other_writes())
        with rows.case("every re-run was authorised by the minted installation token"):
            self.assertEqual({"install"}, {auth for _, auth in self.svc.rerun_attempts()})
        with rows.case("one exchange, for actions: write on this repository only"):
            self.assertEqual([ACTIONS_WRITE], self.svc.exchanges)
            self.assertEqual(1, len(self.svc.minted))
        with rows.case("reads stay on the GITHUB_TOKEN (the installation lookup is the JWT's alone; the installation token reads nothing)"):
            reads = {path: auth for path, auth in self.svc.read_auth}
            self.assertEqual("jwt", reads.pop(INSTALL_LOOKUP))
            self.assertEqual({"github_token"}, set(reads.values()))
            self.assertTrue([p for p, _ in self.svc.read_auth if RUN_READ.fullmatch(p)], "the client read each run before re-running it")
        with rows.case("nothing secret in the log or the output file"):
            self.assertEqual([], self._leaks(result))
        rows.check()

    def test_tq600a_13_xv_a_proof_completion_reruns_its_hold_with_the_app_token(self):
        # covers: TQ-600a-13-xv
        # angle: seam
        """The fix-proof branch re-runs through the same App token, and a completion that re-runs nothing mints nothing."""
        rows = Cases()
        result = self._run(PROOF_NAME, 700)
        with rows.case("the proof's hold is re-run by the installation token"):
            self.assertEqual(0, result.code, result.log)
            self.assertEqual([(1005, "install")], self.svc.rerun_attempts())
            self.assertEqual([ACTIONS_WRITE], self.svc.exchanges)
        result = self._run(history=("failure", "failure"))
        with rows.case("an unchanged verdict re-runs nothing and mints nothing"):
            self.assertEqual(0, result.code, result.log)
            self.assertEqual([], self.svc.write_attempts)
            self.assertEqual([], self.svc.bearers)
        rows.check()


class TestNoCredentialFailsClosedAndVisible(_Case):
    def test_tq600a_13_xv_a_missing_or_unusable_credential_names_every_would_be_rerun_and_posts_nothing(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """No JWT (HOLD_APP_* missing: the step prints an empty line), a JWT the service rejects, an App that is not installed, and an
        exchange the service refuses: every would-be re-run is named `rerun_no_credential` (no one is silently skipped), the job
        still succeeds so the notice can carry the list, and not one re-run POST is made. With no JWT the service is not contacted
        for a credential at all. Wrong versions caught: a fallback to the GITHUB_TOKEN; the failure swallowed (a short list); the
        failure fatal (the notice never learns of it)."""
        rows = Cases()
        for label, kwargs in {
            "no JWT": {"jwt": ""},
            "a JWT the service rejects": {"jwt": "aaa.bbb.ccc"},
            "the App is not installed": {"installed": False},
            "the exchange is refused (403)": {"exchange_status": 403},
            "the exchange fails (500)": {"exchange_status": 500},
        }.items():
            result = self._run(**kwargs)
            with rows.case(f"{label}: every would-be re-run is named"):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual(_named("rerun_no_credential"), sorted(result.unrerunnable or [], key=lambda e: e["pr"]))
            with rows.case(f"{label}: no re-run POST, no installation token"):
                self.assertEqual([], self.svc.rerun_ids())
                self.assertEqual([], self.svc.minted)
                self.assertNotIn("install", {a["auth"] for a in self.svc.write_attempts})
            with rows.case(f"{label}: the reads were still done and nothing leaked"):
                self.assertNotEqual([], self.svc.reads_of("/pulls"))
                self.assertEqual([], self._leaks(result))
        with rows.case("no JWT: the service is not asked for a credential at all"):
            self._run(jwt="")
            self.assertEqual([], self.svc.write_attempts)
            self.assertEqual([], self.svc.bearers)
        rows.check()

    def test_tq600a_13_xv_a_proof_completion_without_a_credential_names_its_pull_request(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """The fix-proof branch fails closed the same way: no JWT -> its one hold is named `rerun_no_credential`, no POST."""
        result = self._run(PROOF_NAME, 700, jwt="")
        self.assertEqual(0, result.code, result.log)
        self.assertEqual([{"pr": None, "head_sha": SHAS["A"], "reason": "rerun_no_credential"}], result.unrerunnable)
        self.assertEqual([], self.svc.write_attempts)


def _step(doc):
    job = doc["jobs"]["reevaluate"]
    (step,) = [s for s in job["steps"] if s.get("id") == "reeval"]
    return job, step


class TestTheStepKeepsTheKeySecret(unittest.TestCase):
    """The shell step mints the JWT exactly as the hold workflow does: the key unset at once, the JWT only on stdin."""

    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load(FOLLOWUP.read_text(encoding="utf-8"))

    def test_tq600a_13_xv_the_step_unsets_the_key_before_any_child_and_pipes_the_jwt_on_stdin(self):
        # covers: TQ-600a-13-xv
        # covers: TQ-600a-13-xi
        # angle: seam
        """Structural by necessity (the platform's secret scoping and the step's text): the step holds the two secrets only in its own
        `env:`, never at job or workflow level; the run text has no dollar-brace expression, unsets HOLD_APP_PRIVATE_KEY before the
        first child process, never exports, traces or persists anything, and hands the JWT to python on stdin (`printf | python`),
        never as an argument, an environment variable or a file."""
        rows = Cases()
        job, step = _step(self.doc)
        text = step["run"]
        code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        with rows.case("the secrets are in this step's env only, and the job is in the hold's environment"):
            self._assert_secrets_scoped_to_step(job, step)
        with rows.case("no dollar-brace expression in the run text"):
            self.assertNotIn("${{", text)
        with rows.case("the key leaves the environment before any child process"):
            self._assert_key_unset_before_any_child(code)
        with rows.case("the key reaches openssl through a process substitution, never a file or an argument"):
            self._assert_key_reaches_openssl_by_substitution(text, code)
        with rows.case("the JWT goes to python on stdin and nowhere else"):
            self._assert_jwt_only_on_stdin(text, step)
        with rows.case("no shell tracing"):
            self.assertIsNone(re.search(r"(?m)(^|[;&|\s])set\s+-[a-zA-Z]*x|bash\s+-[a-zA-Z]*x|\bxtrace\b", text))
        with rows.case("the gate still decides: the signing is inside the gate's branch"):
            self.assertRegex(text, r'if \[ "\$REEVAL_RERUN_ENABLED" = "true" \]')
            self.assertLess(text.index('"$REEVAL_RERUN_ENABLED" = "true"'), text.index("openssl dgst"))
        rows.check()

    def _assert_secrets_scoped_to_step(self, job, step):
        self.assertEqual("post-merge-hold", job.get("environment"))
        self.assertEqual({"HOLD_APP_ID", "HOLD_APP_PRIVATE_KEY"}, set(re.findall(r"secrets\.(\w+)", yaml.safe_dump(job))))
        self.assertEqual({"HOLD_APP_ID", "HOLD_APP_PRIVATE_KEY"}, {k for k, v in step["env"].items() if "secrets." in str(v)})
        self.assertNotIn("secrets.", yaml.safe_dump(job.get("env") or {}))

    def _assert_key_unset_before_any_child(self, code):
        unset = next(i for i, line in enumerate(code) if line.strip() == "unset HOLD_APP_PRIVATE_KEY")
        self.assertEqual([], [line for line in code[:unset] if re.search(r"\b(openssl|python3?|date|tr|curl)\b", line) and not line.lstrip().startswith("b64()")], "no child before the unset")
        self.assertEqual("key=$HOLD_APP_PRIVATE_KEY", code[unset - 1].strip(), "the key moves into an UNEXPORTED shell variable first")

    def _assert_key_reaches_openssl_by_substitution(self, text, code):
        self.assertIn("-sign <(printf '%s' \"$key\")", text)
        self.assertNotRegex(text, r"(?m)^\s*export\b")
        self.assertEqual([], [word for word in ("GITHUB_ENV", "mktemp", ">>") if word in "\n".join(code)])

    def _assert_jwt_only_on_stdin(self, text, step):
        jwt_uses = [line.strip() for line in text.splitlines() if "$jwt" in line and not line.lstrip().startswith("#")]
        self.assertEqual(2, len(jwt_uses), jwt_uses)
        self.assertEqual("printf '::add-mask::%s\\n' \"$jwt\"", next(u for u in jwt_uses if "add-mask" in u).rstrip(";"), "L-1: the JWT is registered for masking by a printf builtin, never echoed")
        self.assertTrue(jwt_uses[1].startswith("printf '%s\\n' \"$jwt\" | ") and "post_merge_reeval.py" in jwt_uses[1], jwt_uses)
        self.assertLess(text.index("::add-mask::"), text.index("post_merge_reeval.py"), "masked before it is used")
        self.assertLess(text.index("jwt=\"$header.$payload.$sig\""), text.index("::add-mask::"), "masked once it exists")
        self.assertNotIn("jwt", json.dumps(step.get("env") or {}).lower())


class TestTheExecutedStep(unittest.TestCase):
    def _execute(self, extra_env, *, dump=None):
        svc = ReevalService()
        self.addCleanup(svc.close)
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            seed_world(svc)
            suite_history(svc, "success", "failure")
            event = write_event(base, SUITE_NAME, 102, SHAS["A"])
            env = {"GITHUB_EVENT_PATH": str(event), "VARS_POST_MERGE_REEVAL_RERUN": "true", **extra_env}
            if dump:
                observer = base / "observer"
                observer.mkdir()
                (observer / "sitecustomize.py").write_text(DUMP_ENV, encoding="utf-8")
                env.update({"PYTHONPATH": str(observer), "REEVAL_ENV_DUMP": str(base / "env.json")})
            result = WorkflowRun(FOLLOWUP, scratch_default_branch(base), base / "scratch", env, svc.url).execute_job("reevaluate")
            dumped = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(base.glob("env.json.*"))]
        return svc, result, dumped

    def test_tq600a_13_xv_the_executed_step_mints_with_openssl_and_the_python_child_never_sees_the_key_or_the_jwt(self):
        # covers: TQ-600a-13-xv
        # angle: reachability
        """Execute `reevaluate` verbatim with the environment's two secrets: the shell signs a real RS256 JWT (the fake verifies the
        signature), the three holds are re-run with the installation token, and the python child's environment holds neither the
        private key nor the JWT nor the secrets' names; the job log shows no credential."""
        rows = Cases()
        svc, result, dumped = self._execute(app_secrets_env(), dump=True)
        with rows.case("re-runs requested with the minted token"):
            self.assertEqual("success", result.conclusion, result.log_text()[-1500:])
            self.assertEqual([(1005, "install"), (1009, "install"), (1011, "install")], svc.rerun_attempts())
            self.assertEqual([ACTIONS_WRITE], svc.exchanges)
        key = "".join(line for line in app_secrets_env()["SECRETS_HOLD_APP_PRIVATE_KEY"].splitlines() if "-----" not in line)
        with rows.case("the python child ran and its environment was observed"):
            self.assertEqual(1, len(dumped))
        with rows.case("no key and no JWT in the child's environment (the harness's own SECRETS_* carriers, which stand in for the platform's secret store, are not the step's)"):
            blob = json.dumps([{k: v for k, v in env.items() if not k.startswith("SECRETS_")} for env in dumped])
            self.assertNotIn(key[:24], blob)
            self.assertNotIn("HOLD_APP_PRIVATE_KEY", blob)
            self.assertEqual([], [b[:8] for b in svc.bearers if b.count(".") == 2 and b in blob])
        log = result.log_text()
        jwts = sorted({b for b in svc.bearers if b.count(".") == 2})
        with rows.case("L-1: the JWT and the minted token are each registered for masking exactly once, the JWT first, before use"):
            self.assertEqual(jwts + svc.minted, mask_lines(log))
            self.assertLess(log.index(f"{MASK}{jwts[0]}"), log.index(f"{MASK}{svc.minted[0]}"))
        with rows.case("no credential anywhere else in the job log (the masking commands aside)"):
            self.assertEqual([], [n[:8] for n in svc.credential_needles() if n in without_masks(log)])
        rows.check()

    def test_tq600a_13_xv_a_missing_secret_in_the_executed_step_names_every_would_be_rerun_and_posts_nothing(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """HOLD_APP_PRIVATE_KEY empty, HOLD_APP_ID empty, both unset, HOLD_APP_ID malformed, or a key that is not a key: the executed job
        still succeeds, outputs every would-be re-run as `rerun_no_credential` and the server sees no re-run."""
        rows = Cases()
        for label, secrets in {
            "empty key": app_secrets_env(HOLD_APP_PRIVATE_KEY=""),
            "empty app id": app_secrets_env(HOLD_APP_ID=""),
            "neither secret": {},
            "malformed app id": app_secrets_env(HOLD_APP_ID="not-a-number"),
            "a key that is not a key": app_secrets_env(HOLD_APP_PRIVATE_KEY="not a private key"),
        }.items():
            svc, result, _ = self._execute(secrets)
            with rows.case(label):
                self.assertEqual("success", result.conclusion, result.log_text()[-1500:])
                self.assertEqual([], svc.rerun_ids())
                self.assertEqual([], svc.minted)
                self.assertEqual(_named("rerun_no_credential"), sorted(json.loads(result.outputs["unrerunnable"]), key=lambda e: e["pr"]))
        rows.check()

    def test_tq600a_13_xv_the_app_id_in_the_secrets_is_the_one_the_jwt_names(self):
        # covers: TQ-600a-13-xv
        # angle: seam
        """Control for the rows above: the JWT's `iss` is HOLD_APP_ID (the fake rejects a JWT whose `iss` is another App)."""
        svc, result, _ = self._execute(app_secrets_env(HOLD_APP_ID=str(int(APP_ID) + 1)))
        self.assertEqual("success", result.conclusion, result.log_text()[-1500:])
        self.assertEqual([], svc.rerun_ids())
        self.assertEqual(_named("rerun_no_credential"), sorted(json.loads(result.outputs["unrerunnable"]), key=lambda e: e["pr"]))


if __name__ == "__main__":
    unittest.main()
