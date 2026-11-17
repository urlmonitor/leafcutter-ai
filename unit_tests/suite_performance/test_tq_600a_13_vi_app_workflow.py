"""
Tests for TQ-600a-13-vi (and -x), App workflow half -- STRUCTURAL BY NECESSITY. What these pin cannot be executed offline: the job's
name as the hosting service reports it, the deployment environment that holds the secrets, and the platform's secret scoping. The
behaviour (what the job publishes and when) is covered by the executed-job tests in this family; these cover only the file shape
that the executor ignores or cannot judge.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml, TQ-600a-13-x.yaml, TQ-600a-13-xi.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

.github/workflows/post-merge-hold.yml
  exactly one job, `name: Post-merge hold evaluation`; no job (by id or name) called `Post-merge suite status`;
  no job-level `if`, `needs`, `strategy`; `environment: post-merge-hold` (string, or mapping with name) on that job;
  permissions exactly contents/actions read, issues/pull-requests write (no `checks`, no `statuses`: the App's permission is its own);
  `secrets.` is referenced ONLY as HOLD_APP_ID and HOLD_APP_PRIVATE_KEY, only inside steps that come after the checkout step, never in
  the checkout step, never at workflow or job `env:`; any `uses:` other than actions/checkout is pinned to a 40-hex commit sha;
  no `run:` text writes to GITHUB_ENV or GITHUB_OUTPUT and none turns on shell tracing (`set -x`, `bash -x`).
======================================================================
"""

from __future__ import annotations

import re

from ._app_harness import APP_JOB_NAME
from ._ending_harness import CHECK, Cases
from ._hold_harness import WORKFLOW
from ._workflow_jobs import load_workflow

_SECRET_REF = re.compile(r"secrets\.([A-Za-z_]\w*)")
_TRACING = re.compile(r"(?m)(^|[;&|\s])set\s+-[a-zA-Z]*x|bash\s+-[a-zA-Z]*x|\bxtrace\b")
_SHA_PIN = re.compile(r"@[0-9a-f]{40}$")
OLD_NAME = "Post-merge suite status"


def _as_text(value):
    return " ".join(str(v) for v in value.values()) if isinstance(value, dict) else str(value or "")


class TestTq600a13viAppWorkflowShape:
    def _doc(self):
        return load_workflow(WORKFLOW)

    def test_tq600a_13_vi_the_evaluation_job_is_renamed_and_cannot_be_skipped(self):
        # covers: TQ-600a-13-vi
        # covers: TQ-600a-13-x
        # angle: discrimination
        """Exactly one job, named `Post-merge hold evaluation`; no job carries `Post-merge suite status` (by id or name), so no
        Actions-sourced check shares the name the App's check run publishes; no matrix, no job-level `if`, no `needs` (a skipped
        evaluation job publishes no App check at all, which breaks the every-pull-request clause).

        Wrong versions caught: the job still named `Post-merge suite status`; the job gaining a matrix, an `if:` or a `needs:`;
        a second job added that reuses the required name.
        """
        cases = Cases()
        jobs = self._doc()["jobs"]
        with cases.case("one job, renamed"):
            CHECK.assertEqual([APP_JOB_NAME], [(job or {}).get("name") for job in jobs.values()])
        with cases.case("nothing carries the required name"):
            CHECK.assertEqual([], [key for key, job in jobs.items() if OLD_NAME in (key, (job or {}).get("name"))])
        with cases.case("cannot be skipped"):
            CHECK.assertEqual([], [(key, bad) for key, job in jobs.items() for bad in ("if", "needs", "strategy") if bad in (job or {})])
        cases.check()

    def test_tq600a_13_vi_the_secrets_are_scoped_to_the_evaluation_job_and_never_traced(self):
        # covers: TQ-600a-13-vi
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """Structural: the job runs in environment `post-merge-hold` (the deployment-branch policy that makes the secrets reachable
        from main only is a recorded observation of -x, not provable here); the job's permissions stay exactly the four, with no
        `checks` or `statuses`; the only secrets referenced are HOLD_APP_ID and HOLD_APP_PRIVATE_KEY, each only in a step after the
        checkout, never in the checkout, never in workflow or job `env:`; a third-party action is pinned to a commit sha; no step
        redirects to GITHUB_ENV or GITHUB_OUTPUT (an action's own output file cannot be observed offline) or traces the shell.

        Wrong versions caught: the secrets given to the checkout or to workflow-level env (every step, including any head content,
        would see them); a floating action tag holding the key; `set -x` echoing the key into the log; the token handed to a later
        step through GITHUB_ENV; `checks: write` added to the GITHUB_TOKEN.
        """
        cases = Cases()
        doc = self._doc()
        (job,) = doc["jobs"].values()
        steps = job.get("steps") or []
        with cases.case("environment"):
            environment = job.get("environment")
            CHECK.assertEqual("post-merge-hold", environment.get("name") if isinstance(environment, dict) else environment)
        with cases.case("permissions"):
            CHECK.assertEqual({"contents": "read", "actions": "read", "issues": "write", "pull-requests": "write"}, job.get("permissions"))
            CHECK.assertEqual({}, doc.get("permissions"))
        with cases.case("secret references"):
            CHECK.assertEqual(set(), set(_SECRET_REF.findall(_as_text(doc.get("env")) + _as_text(job.get("env")) + _as_text(doc.get("on")))), "no secret at workflow or job level")
            used = [(i, name) for i, step in enumerate(steps) for name in _SECRET_REF.findall(str(step))]
            CHECK.assertEqual({"HOLD_APP_ID", "HOLD_APP_PRIVATE_KEY"}, {name for _, name in used})
            checkout = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/checkout"))
            CHECK.assertEqual([], [(i, n) for i, n in used if i <= checkout], "no secret in or before the checkout step")
        with cases.case("third-party actions are pinned"):
            CHECK.assertEqual([], [s["uses"] for s in steps if "uses" in s and not s["uses"].startswith("actions/checkout") and not _SHA_PIN.search(s["uses"])])
        with cases.case("no persistence or tracing in run text"):
            runs = "\n".join(str(s.get("run", "")) for s in steps)
            CHECK.assertEqual([], [w for w in ("GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY") if w in runs])
            CHECK.assertIsNone(_TRACING.search(runs), "shell tracing would echo the key into the log")
        cases.check()
