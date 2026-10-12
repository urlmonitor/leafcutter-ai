"""
Tests for TQ-600a-13-xi (structural half) -- the platform-enforced `permissions:` of every family workflow.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xi.yaml (it_requirements 3), and the
records that specify each job's scopes: -ii (the correctness suite), -xii (the timing suite), -iii and -xv (the follow-up's notice and
re-evaluation jobs), -vi (the hold), -xvi (the fix proof).

Structural by necessity: a ``permissions:`` block is enforced only by the hosting platform and cannot be executed offline. It is the
second half of a pair -- the client allowlist (test_tq_600a_13_xi_client.py) is the behavioural half. The SPECIFIED set per job is
derived below from the records, NOT read back from the workflow files, so a file edited to grant more fails here.
"""

from __future__ import annotations

import re
import unittest

import yaml

from ._ending_harness import CHECK, Cases
from ._workflow_jobs import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
READ = {"contents": "read"}
# file -> job id -> the exact permissions the records give that job. A job a record does not name is NOT in the table: it fails.
SPECIFIED = {
    "post-merge-suite.yml": {  # -ii: `contents: read` on every job, `actions: read` additionally on the verdict job (-xiii reads earlier verdicts)
        "run": READ,
        "retry": READ,
        "verdict": {**READ, "actions": "read"},
    },
    "post-merge-timing.yml": {"run": READ, "retry": READ, "verdict": READ},  # -xii mirrors -ii; the timing lane reads no earlier verdict
    "post-merge-followup.yml": {
        "reevaluate": {"actions": "read", "pull-requests": "read", **READ},  # AMENDED 2026-10-12 (-xv, -xi): the GITHUB_TOKEN holds NO `actions: write`; the re-run is the App token's
        "notice": {"issues": "write", "actions": "read", **READ},  # -iii: issues write, actions read, contents read; no pull-requests, no actions write
        "timing-notice": {"issues": "write", "actions": "read", **READ},  # -xii: the same machinery under --lane timing
    },
    "post-merge-hold.yml": {"hold": {**READ, "actions": "read", "issues": "write", "pull-requests": "write"}},  # -vi: the one job allowed pull-requests: write
    "post-merge-fix-proof.yml": {
        "prepare": {"actions": "read", "issues": "read", **READ},  # -xvi: reads only (+ the sparse checkout)
        "prove": {},  # -xvi: runs the pull request's code, so it holds nothing to steal
    },
}
FORBIDDEN_ANYWHERE = {"checks", "statuses", "packages", "deployments", "id-token", "security-events", "attestations"}


def load_family():
    """Every ``post-merge-*.yml`` under ``.github/workflows``, parsed; file name -> (document, text with comments gone)."""
    found = {}
    for path in sorted(WORKFLOWS.glob("post-merge-*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        found[path.name] = (doc, yaml.safe_dump(doc))  # the dump has no comments: a `secrets.` in prose is not a reference
    return found


def effective(doc, job):
    """What the job holds: its own block, or the workflow's when it has none (a missing workflow block is read-all, never {})."""
    if "permissions" in job:
        return job["permissions"] or {}
    return doc.get("permissions", "read-all")


def _check_job(cases, name, doc, job_id, job):
    """The rows of one job; returns its ``(file, job, scope)`` write grants."""
    held = effective(doc, job)
    with cases.case(f"{name}/{job_id}: permissions equal the specified set"):
        CHECK.assertEqual(SPECIFIED.get(name, {}).get(job_id, "no specified set"), held)
    writers = []
    if isinstance(held, dict):
        writers = [(name, job_id, scope) for scope, level in held.items() if level == "write"]
        with cases.case(f"{name}/{job_id}: no forbidden scope"):
            CHECK.assertEqual(set(), set(held) & FORBIDDEN_ANYWHERE)
    checkouts = [step for step in job.get("steps") or [] if str(step.get("uses", "")).startswith("actions/checkout")]
    for step in checkouts:
        with cases.case(f"{name}/{job_id}: a checkout that persists no credential"):
            CHECK.assertIs(False, (step.get("with") or {}).get("persist-credentials"), step)
    return writers


def _check_every_job(cases, family):
    """The workflow-level and per-job rows of the whole family; returns every write grant found."""
    writers = []
    for name, (doc, _text) in family.items():
        with cases.case(f"{name}: workflow-level permissions are exactly {{}}"):
            CHECK.assertEqual({}, doc.get("permissions", "read-all"))
        jobs = doc.get("jobs") or {}
        with cases.case(f"{name}: the jobs are exactly the specified ones"):
            CHECK.assertEqual(sorted(SPECIFIED.get(name, {})), sorted(jobs))
        for job_id, job in jobs.items():
            writers += _check_job(cases, name, doc, job_id, job)
    return writers


def _check_writers(cases, writers):
    with cases.case("AMENDED 2026-10-12: actions: write is on NO job of the family (the re-run is the App installation token's)"):
        CHECK.assertEqual([], [w for w in writers if w[2] == "actions"])
    with cases.case("pull-requests: write is the hold's alone; contents: write is nobody's"):
        CHECK.assertEqual([("post-merge-hold.yml", "hold")], [w[:2] for w in writers if w[2] == "pull-requests"])
        CHECK.assertEqual([], [w for w in writers if w[2] == "contents"])


def _check_fix_proof_has_no_secrets(cases, family):
    proof_doc, proof_text = family.get("post-merge-fix-proof.yml", ({}, ""))
    with cases.case("the fix proof workflow has no secrets reference at all"):
        CHECK.assertNotIn("secrets.", proof_text)
        CHECK.assertEqual(["prove"], [j for j, body in (proof_doc.get("jobs") or {}).items() if j == "prove" and not effective(proof_doc, body)])


def _check_secrets_only_in_app_jobs(cases, family):
    with cases.case("only the hold job and the `reevaluate` job name secrets, and only the two App secrets, through the environment"):
        named = {(name, job_id): sorted(set(re.findall(r"secrets\.(\w+)", yaml.safe_dump(job)))) for name, (doc, _) in family.items() for job_id, job in (doc.get("jobs") or {}).items() if "secrets." in yaml.safe_dump(job)}
        both = ["HOLD_APP_ID", "HOLD_APP_PRIVATE_KEY"]
        CHECK.assertEqual({("post-merge-hold.yml", "hold"): both, ("post-merge-followup.yml", "reevaluate"): both}, named)
        for name, job_id in named:
            job = family[name][0]["jobs"][job_id]
            CHECK.assertEqual("post-merge-hold", job.get("environment"), f"{name}/{job_id}: the secrets are reached through the post-merge-hold environment (main only)")
            CHECK.assertNotIn("secrets.", yaml.safe_dump(job.get("env") or {}), f"{name}/{job_id}: no secret at job-level env")
        CHECK.assertNotIn("secrets.", yaml.safe_dump({k: v for k, v in family["post-merge-followup.yml"][0].items() if k != "jobs"}), "no secret at workflow level")


class TestTq600a13XiWorkflowScopes(unittest.TestCase):
    def test_tq600a_13_xi_workflow_scopes_are_minimal(self):
        # covers: TQ-600a-13-xi
        # angle: seam
        """Load EVERY ``post-merge-*.yml``; each job's permissions equal its specified set exactly.

        Rows: the family is the five files the records name (a sixth, unspecified one fails); each file declares workflow-level
        ``permissions: {}``; each job's effective permissions equal the specified set (an extra scope, a missing scope, an upgrade from read
        to write all differ); no job outside the table exists; ``actions: write`` is on NO job of the whole family (AMENDED
        2026-10-12); a ``secrets.`` reference is in the hold job and the ``reevaluate`` job only, both in environment ``post-merge-hold``;
        ``pull-requests: write`` only on the hold; no job holds ``contents: write``, ``checks`` or ``statuses``; the fix
        proof workflow names no ``secrets.`` reference in its YAML and its ``prove`` job references no secret or token; no checkout of
        the family persists a git credential.

        Wrong versions caught: a workflow that omits ``permissions: {}`` and inherits read-all; ``actions: write`` on a second job
        (the notice job, the timing notice, the hold); the proof job gaining any scope or a ``secrets.`` reference; any job holding
        ``contents: write``, ``pull-requests: write`` outside the hold, ``checks`` or ``statuses``.
        """
        family = load_family()
        cases = Cases()
        with cases.case("the family is the specified five workflows"):
            CHECK.assertEqual(sorted(SPECIFIED), sorted(family))
        writers = _check_every_job(cases, family)
        _check_writers(cases, writers)
        _check_fix_proof_has_no_secrets(cases, family)
        _check_secrets_only_in_app_jobs(cases, family)
        cases.check()


if __name__ == "__main__":
    unittest.main()
