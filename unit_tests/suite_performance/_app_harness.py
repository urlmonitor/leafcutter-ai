"""Executed-job harness for the hold App (TQ-600a-13-vi App criteria, -xi, -x). Not a test: underscore-named.

``run_app_job`` executes the job named ``Post-merge hold evaluation`` of ``.github/workflows/post-merge-hold.yml`` -- its
real ``run:`` steps, verbatim, through the shared workflow-step executor -- against an ``AppService`` (the recording fake of
the hosting service that also serves the App's token exchange and check-run endpoints).

What the harness supplies, and what is therefore a SIMPLIFICATION of the platform:

* ``${{ secrets.NAME }}`` is rewritten textually to an ``env`` lookup of ``HARNESS_SECRET_NAME`` (the executor has no
  ``secrets`` context). An unset or empty secret expands to the empty string, exactly as on the platform. The secret values
  are therefore present in the environment of EVERY step, not only the step that names them.
* ``environment: post-merge-hold`` is ignored by the executor (a deployment-branch policy is a property of the hosting
  service, recorded by TQ-600a-13-x); it is asserted structurally in ``test_tq_600a_13_vi_app_workflow.py``.
* a third-party ``uses:`` step (a token-minting action, say) is SKIPPED by the executor and its outputs are discarded, so a
  mint done by an action cannot be executed offline; the behavioural rows therefore require the mint to be a ``run:`` step.

``scan_for_credentials`` looks for the key, the minted tokens and every JWT in: every file under the scratch base (the
checkout, the GITHUB_ENV / GITHUB_OUTPUT files, the workspace, HOME), the captured step logs, and every request body and
PR comment the fake recorded.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ._app_fake import APP_ID, CHECK_NAME, AppService, key_pairs
from ._ending_harness import CHECK
from ._hold_harness import DNC_JOBS, OBSERVER, RED_JOBS, WORKFLOW, HoldRun, HoldTestCase, JobOutcome, fresh_base, make_run, scratch_default_branch
from ._notice_fakes import REPO

APP_JOB_NAME = "Post-merge hold evaluation"
MAIN_TIP = "a" * 40  # github.sha under pull_request_target: the tip of main, never the pull request's head
HEAD_SHA = "9" * 40
SECRET_PREFIX = "HARNESS_SECRET_"
_SECRET = re.compile(r"\$\{\{\s*secrets\.([A-Za-z_]\w*)\s*\}\}")
STATES = ("pass", "red", "did_not_complete", "stale", "disabled", "never_run", "could_not_read")
CRASH_SUFFIX = '\n\ndef select_verdict_run(*args, **kwargs):\n    raise RuntimeError("simulated crash in the verdict computation")\n'


def app_secrets(**override):
    """The two secrets of the environment ``post-merge-hold``; an override of ``""`` is an empty secret."""
    return {"HOLD_APP_ID": APP_ID, "HOLD_APP_PRIVATE_KEY": key_pairs()[0].private_pem, **override}


def real_now():
    return datetime.now(timezone.utc)


def seed_state(svc, state, now):
    """Reset ``svc`` and serve the run history (or failure) that gives the hold the named verdict state."""
    svc.reset()
    red = make_run(7, "failure", hours_ago=1, now=now)
    cancelled = make_run(7, "cancelled", hours_ago=1, now=now)
    older = make_run(6, "success", hours_ago=3, now=now)
    if state == "pass":
        svc.runs = [make_run(6, "success", hours_ago=1, now=now)]
    elif state == "red":
        svc.runs, svc.jobs = [older, red], {red["id"]: RED_JOBS}
    elif state == "did_not_complete":
        svc.runs, svc.jobs = [older, cancelled], {cancelled["id"]: DNC_JOBS}
    elif state == "stale":
        svc.runs = [make_run(6, "success", hours_ago=31, now=now)]
    elif state == "disabled":
        svc.workflow_state = "disabled_manually"
    elif state == "could_not_read":
        svc.failing = ["/runs"]
        svc.runs = [make_run(6, "success", hours_ago=1, now=now)]
    elif state != "never_run":
        CHECK.fail(f"unknown state {state!r}")


def secrets_as_env(workflow, dest):
    """Write a copy of ``workflow`` whose ``secrets.X`` expressions read ``env.HARNESS_SECRET_X``; return its path."""
    try:
        text = Path(workflow).read_text(encoding="utf-8")
        Path(dest).write_text(_SECRET.sub(lambda m: f"${{{{ env.{SECRET_PREFIX}{m.group(1)} }}}}", text), encoding="utf-8")
    except OSError as exc:
        message = f"cannot prepare the workflow copy: {exc}"
        raise AssertionError(message) from exc
    return Path(dest)


def run_app_job(svc, base, *, secrets=None, workflow=WORKFLOW, head_files=None, head_sha=HEAD_SHA, crash=False, pr_number=42):
    """Execute the evaluation job verbatim against ``svc`` with an ``opened`` event whose head differs from github.sha.

    ``secrets`` maps secret name -> value (default: both, valid); ``head_files`` is a scratch PR head the job must never
    read; ``crash`` makes the verdict computation raise (the staged default-branch ``_run_history.py`` is made to).
    """
    base = Path(base)
    default = scratch_default_branch(base)
    if crash:
        target = default / "scripts" / "ci" / "_run_history.py"
        target.write_text(target.read_text(encoding="utf-8") + CRASH_SUFFIX, encoding="utf-8")
    head = None
    if head_files:
        head = base / "pr-head"
        for rel, text in head_files.items():
            (head / rel).parent.mkdir(parents=True, exist_ok=True)
            (head / rel).write_text(text, encoding="utf-8")
    observer, state_dir, event = base / "observer", base / "state", base / "event.json"
    for folder in (observer, state_dir):
        folder.mkdir()
    (observer / "sitecustomize.py").write_text(OBSERVER, encoding="utf-8")
    payload = {"action": "opened", "number": pr_number, "pull_request": {"number": pr_number, "body": "A change.", "head": {"sha": head_sha}, "base": {"ref": "main"}}}
    event.write_text(json.dumps(payload), encoding="utf-8")
    log = base / "observed.json"
    env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "pull_request_target", "GITHUB_SHA": MAIN_TIP, "PYTHONPATH": str(observer), "PYTHONDONTWRITEBYTECODE": "1", "HOLD_OBSERVER_LOG": str(log), "HOME": str(state_dir)}
    env.update({f"{SECRET_PREFIX}{name}": value for name, value in (app_secrets() if secrets is None else secrets).items()})
    prepared = secrets_as_env(workflow, base / "workflow-under-test.yml")
    run = HoldRun(prepared, default, head, base / "scratch", env, svc.url)
    result = run.execute_job(APP_JOB_NAME)
    events = [e for part in sorted(base.glob(f"{log.name}.*")) for e in json.loads(part.read_text(encoding="utf-8"))]
    return JobOutcome(result, run, events, head, state_dir)


def scan_for_credentials(svc, base, outcome, needles=None):
    """Where the credential was found: ``['file <path>', 'log', 'recorded body']``; empty means nowhere."""
    wanted = [n for n in (needles if needles is not None else svc.credential_needles()) if n]
    found = []
    for path in sorted(Path(base).rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            found += [f"file {path.relative_to(base)}" for n in wanted if n.encode() in data]
    log = outcome.result.log_text()
    found += ["log" for n in wanted if n in log]
    recorded = json.dumps([e["body"] for e in svc.log], default=str)
    found += ["recorded body" for n in wanted if n in recorded]
    return sorted(set(found))


@dataclass
class Executed:
    outcome: JobOutcome
    leaks: list

    @property
    def conclusion(self):
        return self.outcome.result.conclusion

    @property
    def text(self):
        return self.outcome.result.log_text()

    def says(self, *phrases):
        """The phrases (compared case-insensitively) the job output lacks; empty means it said all of them."""
        return [p for p in phrases if p.lower() not in self.text.lower()]


class AppTestCase(HoldTestCase):
    """The hold test case over an ``AppService``; ``execute`` runs the real job and scans for credentials before cleanup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = AppService()

    def execute(self, **kwargs):
        with fresh_base() as raw:
            outcome = run_app_job(self.svc, Path(raw), **kwargs)
            return Executed(outcome, scan_for_credentials(self.svc, raw, outcome))

    def seed(self, state, now=None):
        seed_state(self.svc, state, now or real_now())

    def tmpdir(self):
        return tempfile.TemporaryDirectory()


def completed_runs(svc):
    """The check runs the fake holds, as ``(name, head_sha, status, conclusion)``."""
    return [(r["name"], r["head_sha"], r["status"], r["conclusion"]) for r in svc.check_runs]


__all__ = ["APP_JOB_NAME", "CHECK_NAME", "HEAD_SHA", "MAIN_TIP", "REPO", "STATES", "AppTestCase", "Executed", "app_secrets", "completed_runs", "real_now", "run_app_job", "scan_for_credentials", "seed_state"]
