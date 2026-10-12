"""
Tests for TQ-600a-13-xi (mutation half) -- adding a step that pushes a change, opens a pull request, edits a tracked file, or
dispatches, cancels, disables or re-runs another workflow makes the bound check fail.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xi.yaml

Each mutant is a MUTATED COPY of ``.github/workflows/post-merge-followup.yml`` (a step inserted with the real YAML serializer) whose
``notice`` or ``reevaluate`` job runs through the shared workflow-step executor on a RED verdict, against the recording fakes, in a
scratch repository whose origin is a local bare repository (one per mutant, so the mutants run side by side). The bound check is the
one ``test_tq_600a_13_xi.py`` applies: the writes the server recorded against the AC's list, and the repository's refs, index and
tracked files and the origin's refs against their state before. Only non-test jobs run: no pytest is started.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from ._ending_harness import CHECK, Cases
from ._notice_fakes import FakeIssueService, ScratchRepo, make_verdict, run_record
from ._reeval_harness import HOLD_FILE, SHAS, SUITE_NAME, ReevalService, app_secrets_env, seed_world, suite_history, write_event
from ._workflow_jobs import REPO_ROOT, JobResult, WorkflowRun
from ._xi_support import changed, collect_writes, git, make_origin, snapshot, verdict_on, world_of

FOLLOWUP = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
TUNABLES = "scripts/ci/post_merge_tunables.json"
COMMIT = "git -c user.name=ci -c user.email=ci@example.invalid commit -q"


def http_step(method, path, body=None):
    """A ``run:`` step that sends one request to the API with the job's own GITHUB_TOKEN (Python: the runner image has no curl guarantee)."""
    code = (
        "import json, os, urllib.error, urllib.request as u\n"
        f"r = u.Request(os.environ['GITHUB_API_URL'] + '/repos/' + os.environ['GITHUB_REPOSITORY'] + {path!r}, data=json.dumps({body!r}).encode(), method={method!r})\n"
        "r.add_header('Authorization', 'Bearer ' + os.environ['GITHUB_TOKEN'])\n"
        "try:\n    u.urlopen(r, timeout=10)\nexcept urllib.error.HTTPError:\n    pass\n"
    )
    return f"python - <<'PYTHON'\n{code}PYTHON\n"


# name -> (job, the run: texts of the inserted steps, in order). Each is a named must_catch of the AC.
MUTANTS = {
    "regenerates the durations file and pushes it": ("notice", [f"mkdir -p .github\nprintf '{{}}\\n' > .github/test_durations.json\ngit add .github/test_durations.json\n{COMMIT} -m regenerate\ngit push -q origin HEAD:refs/heads/regen-durations\n"]),
    "opens a pull request with a proposed fix": ("notice", [http_step("POST", "/pulls", {"title": "fix", "head": "fix", "base": "main"})]),
    "edits a tracked file and a later step commits it": ("notice", [f"printf ' ' >> {TUNABLES}\n", f"{COMMIT} -a -m tune\n"]),
    "edits a tracked file and leaves it modified": ("notice", [f"printf ' ' >> {TUNABLES}\n"]),
    "deletes a branch of the origin": ("notice", ["git push -q origin :refs/heads/side\n"]),
    "dispatches the suite workflow to retry it green": ("reevaluate", [http_step("POST", "/actions/workflows/post-merge-suite.yml/dispatches", {"ref": "main"})]),
    "re-runs the suite run to retry it green": ("reevaluate", [http_step("POST", "/actions/runs/102/rerun", {})]),
    "re-runs a hold run with the job's own GITHUB_TOKEN": ("reevaluate", [http_step("POST", "/actions/runs/1005/rerun", {})]),  # AMENDED 2026-10-12: only the App token may re-run
    "disables another workflow": ("reevaluate", [http_step("PUT", "/actions/workflows/ci.yml/disable", None)]),
}
CONTROLS = {"the unmutated notice job": ("notice", []), "the unmutated re-evaluation job": ("reevaluate", [])}


def mutated_copy(job, texts, destination):
    """Write ``post-merge-followup.yml`` with ``texts`` appended to ``job``'s steps (real serializer); return the new step names."""
    doc = yaml.safe_load(FOLLOWUP.read_text(encoding="utf-8"))
    names = [f"MUTANT step {index}" for index in range(len(texts))]
    doc["jobs"][job]["steps"] += [{"name": name, "run": text} for name, text in zip(names, texts, strict=True)]
    destination.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return names


class TestTq600a13XiAddedStepIsCaught(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.repo = ScratchRepo(cls.tmp / "repo")
        shutil.copytree(REPO_ROOT / "scripts" / "ci", cls.repo.path / "scripts" / "ci", ignore=shutil.ignore_patterns("__pycache__"))
        git(cls.repo.path, "add", "scripts/ci")
        git(cls.repo.path, "commit", "-q", "-m", "add the ci scripts the workflow runs")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _run(self, key, job, texts):
        """Execute one job of one (mutated) workflow copy; return ``(violations, steps, conclusion, writes)``."""
        base = Path(tempfile.mkdtemp(dir=self.tmp))
        proj = base / "proj"
        shutil.copytree(self.repo.path, proj, symlinks=True)
        bare = make_origin(proj, base / "origin.git")
        before = snapshot(proj, bare, untracked=False)
        workflow = base / "followup.yml"
        names = mutated_copy(job, texts, workflow)
        svc = FakeIssueService() if job == "notice" else ReevalService()
        try:
            if job == "notice":
                svc.runs = [run_record(2, "failure", head_sha=self.repo.r), run_record(1, "success", head_sha=self.repo.g)]
            else:
                seed_world(svc)
                suite_history(svc, "success", "failure")
            event = write_event(base, SUITE_NAME, 102, SHAS["A"] if job == "reevaluate" else self.repo.r)
            env = {"GITHUB_EVENT_PATH": str(event), "PYTHONDONTWRITEBYTECODE": "1", "VARS_POST_MERGE_REEVAL_RERUN": "true", **app_secrets_env()}  # re-runs on and the App secrets present: the control must really write
            run = WorkflowRun(workflow, proj, base / "scratch", env, svc.url)
            verdict = base / "post-merge-verdict.json"
            verdict.write_text(json.dumps(make_verdict("red", run_id=102, head_sha=self.repo.r, failing=("tests/test_shared.py::test_a",))), encoding="utf-8")
            run.artifacts.upload("post-merge-verdict", [("post-merge-verdict.json", verdict)])
            needs = {"reevaluate": JobResult("reevaluate", "success", outputs={"unrerunnable": "[]"})} if job == "notice" else None
            result = run.execute_job(job, needs)
            hold_runs = {r["id"] for r in svc.workflows[HOLD_FILE] if r["event"] == "pull_request_target"} if job == "reevaluate" else ()
            writes = collect_writes(svc)
            world = world_of(svc, hold_runs=hold_runs)
            violations = [f"{w.method} {w.path}: {why}" for w in writes if (why := verdict_on(w, world))]
            violations += [f"git: {name} changed" for name in changed(before, snapshot(result.workspace, bare, untracked=False))]
        finally:
            svc.close()
        return violations, {name: result.steps.get(name) for name in names}, result.conclusion, writes

    def test_tq600a_13_xi_an_added_fix_step_is_caught(self):
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """Insert each named step into a copy of the follow-up workflow and execute the job on a red verdict: the bound check goes red
        for every mutant, and stays green (over a non-empty set of writes) for the unmutated jobs.

        Wrong versions caught: a red-run step that regenerates the durations file (a timing baseline is the same push) and pushes it;
        one that opens a pull request; one that edits a tracked file (committed by a later step, or left modified); one that deletes a branch of
        the origin; a re-evaluation step that dispatches, re-runs or disables another workflow to 'retry it green'.
        Not caught here by design: a step that only READS (no write is a violation) -- the controls prove the check is not simply
        always red.
        """
        specs = {**CONTROLS, **MUTANTS}
        with ThreadPoolExecutor(max_workers=len(specs)) as pool:
            results = dict(zip(specs, pool.map(lambda key: self._run(key, *specs[key]), specs), strict=True))
        cases = Cases()
        for key in CONTROLS:
            violations, _steps, conclusion, writes = results[key]
            with cases.case(f"{key}: passes the bound"):
                CHECK.assertEqual([], violations)
            with cases.case(f"{key}: succeeded and wrote something (a bound over no writes proves nothing)"):
                CHECK.assertEqual("success", conclusion)
                CHECK.assertTrue(writes, "the control recorded no write")
        for key in MUTANTS:
            violations, steps, _conclusion, _writes = results[key]
            with cases.case(f"{key}: the inserted step really ran"):
                CHECK.assertTrue(steps and all(outcome in ("success", "failure") for outcome in steps.values()), steps)
            with cases.case(f"{key}: the bound check goes red"):
                CHECK.assertNotEqual([], violations, "the added step was not caught")
        cases.check()


if __name__ == "__main__":
    unittest.main()
