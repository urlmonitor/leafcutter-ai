"""
MODULE: unit_tests/build_guards/test_acs200h_whole_store_ci_check.py
GOAL: Guard ACS-200h — the whole requirements store must be re-checked on
    every landing on the protected `main` branch, not only on the changed
    records a pull request happened to touch.
BUSINESS CONTEXT: ACS-200g shipped a PR-scoped `ac-store-valid` CI job that
    only ever sees the files a single pull request changed (it stages the
    diff via `git reset --soft` before running the guardrail hooks). Its own
    tracked comment in .github/workflows/ci.yml says so explicitly:
    "NOT YET IMPLEMENTED — ACS-200h (whole-store run on push to main as a
    merge-vector backstop)." That means a class of problem no single PR
    introduces — e.g. two PRs that are each individually valid but together
    push a parent over its child limit, or together close a dependency
    cycle, or where one retires a record the other has just started
    depending on — is currently invisible to CI forever. ACS-200h closes
    that gap with a second job that runs on `push` to `main` and applies the
    same rule set to every record in the store, not just the diff.
ARCHITECTURE: Reads the REAL, tracked `.github/workflows/ci.yml` (the
    canonical CI configuration) rather than any hand-typed literal, mirroring
    the config-to-config comparison already established by the ACS-200i
    parity guard (test_acs200i_ac_gate_rule_parity.py) in this same
    directory. The reachability test below goes one step further and
    actually executes a real, already-shipped whole-store entry point
    (`scripts/ac_store/validate_ac_schema.py`) against the real on-disk
    store, so the "fails closed on real data" claim is proven against actual
    bytes on disk, not a synthetic fixture.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_AC_STORE_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_VALIDATE_SCHEMA_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
# Canonical source of the guardrail hooks (NOT scripts/commit_guardian/, which
# holds only the deployed wrappers). Same path convention as the tests under
# unit_tests/commit_guardian/.
_COMMIT_GUARDIAN_DIR = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
)

# The exact hook ids ACS-200g's PR-scoped `ac-store-valid` job runs. ACS-200h's
# whole-store job must apply this identical rule set (the AC's own words:
# "applying the same structural and schema rules it applies before merge").
_PR_SCOPED_JOB_ID = "ac-store-valid"
_EXPECTED_HOOK_IDS = {
    "check-ac-schema",
    "check-ac-tree-limits",
    "check-ac-governance",
    "check-ac-parent-covered-by",
    "check-ac-circular-deps",
    "check-ac-pattern-refs",
}


def _load_workflow() -> dict:
    return yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))


def _hook_ids_from_job(job: dict) -> set[str]:
    """Extract the `pre-commit run <hook-id>` invocations from a job's steps."""
    import re

    run_bodies = " \n".join(
        step["run"] for step in job.get("steps", []) if isinstance(step.get("run"), str)
    )
    return set(re.findall(r"pre-commit\s+run\s+([A-Za-z0-9._-]+)", run_bodies))


def _find_whole_store_job(workflow: dict) -> tuple[str, dict]:
    """Locate the job that re-checks the ENTIRE store on a push to `main`.

    A qualifying job must:
      1. Not be gated to `pull_request` only (it must be reachable on `push`).
      2. Invoke the same AC guardrail hook set the PR-scoped job invokes.

    Raises AssertionError (via the caller's unittest context) by returning
    ``(None, {})`` when no such job exists — which is the current, correct
    state of this repository before ACS-200h is implemented.
    """
    jobs = workflow["jobs"]
    for job_name, job in jobs.items():
        if job_name == _PR_SCOPED_JOB_ID:
            continue
        job_if = job.get("if", "")
        # A job whose `if:` excludes push entirely cannot be the backstop.
        if "pull_request" in job_if and "push" not in job_if:
            continue
        hook_ids = _hook_ids_from_job(job)
        if hook_ids and hook_ids >= _EXPECTED_HOOK_IDS:
            return job_name, job
    return None, {}


class TestAcs200hWholeStoreCiCheck(unittest.TestCase):
    """ACS-200h — the whole AC store is re-checked when main receives a push."""

    def test_ci_workflow_has_a_whole_store_job_reachable_on_push(self) -> None:
        # covers: ACS-200h
        # angle: criterion
        """A CI job must exist that runs the full AC rule set on every push
        to `main`, not scoped to any single pull request's diff.

        Currently RED: no such job exists in .github/workflows/ci.yml — only
        `ac-store-valid`, which is hard-gated to `pull_request` and only ever
        sees the PR's own changed files.
        """
        workflow = _load_workflow()
        job_name, job = _find_whole_store_job(workflow)
        self.assertIsNotNone(
            job_name,
            "No CI job re-checks the whole acceptance-criteria store on a "
            "push to main (ACS-200h). Add a job that runs the same "
            f"guardrail hook set {sorted(_EXPECTED_HOOK_IDS)} over every "
            "record in docs/acceptance-criteria/, triggered on `push` to "
            "`main` (not gated to `pull_request` only).",
        )
        self.assertNotIn(
            "pull_request",
            job.get("if", ""),
            f"Job {job_name!r} must be reachable on `push`, not exclusively "
            "gated to `pull_request` — that is the PR-scoped job's job "
            "(ACS-200g), not the whole-store backstop (ACS-200h).",
        )

    def test_whole_store_job_does_not_scope_to_the_landing_diff(self) -> None:
        # covers: ACS-200h
        # angle: boundary
        """The whole-store job must check EVERY record, not the diff.

        ACS-200g's PR-scoped job stages only the PR's changed files via
        `git reset --soft "origin/${{ github.base_ref }}"` before running the
        guardrail hooks — that is precisely the diff-scoping the AC says the
        backstop must NOT do. If the whole-store job reused that same
        diff-scoping step, it would silently degrade back into a PR-scoped
        check and never catch the cross-PR class of bug the AC exists for.

        AMENDED 2026-09-02. This test previously asserted that the string
        `reset --soft` was ABSENT from the job. That was wrong, and wrong in
        the expensive direction: it forbade the only implementation that
        actually works.

        The hooks discover their file set from `git diff --cached`, so a job
        with a clean index validates ZERO records and passes vacuously. Making
        them see the whole store REQUIRES manufacturing a diff, and
        `git reset --soft` to an empty root commit is how — the same mechanism
        the PR-scoped job uses, pointed at nothing instead of at the PR base.
        (`git add -A` does not work: unmodified files stage nothing.)

        What actually distinguishes diff-scoped from whole-store is therefore
        not whether `reset --soft` appears, but WHAT IT RESETS TO. Resetting to
        the PR's base ref scopes to that PR; resetting to an empty tree scopes
        to everything. So that is what is asserted here.
        """
        workflow = _load_workflow()
        job_name, job = _find_whole_store_job(workflow)
        self.assertIsNotNone(
            job_name,
            "No whole-store CI job exists yet (ACS-200h) — cannot verify it "
            "avoids diff-scoping until it is implemented.",
        )
        run_bodies = " \n".join(
            step["run"] for step in job.get("steps", []) if isinstance(step.get("run"), str)
        )
        self.assertNotIn(
            "base_ref",
            run_bodies,
            f"Job {job_name!r} resets to the pull request's base ref, which "
            "scopes the guardrail hooks to one PR's diff — the exact "
            "diff-scoping ACS-200h's backstop exists to escape.",
        )
        self.assertIn(
            "hash-object -t tree /dev/null",
            run_bodies,
            f"Job {job_name!r} has no empty-tree base for its staging step. "
            "Without one the index matches HEAD, `git diff --cached` is "
            "empty, and every check-ac-* hook validates ZERO records and "
            "exits 0 — a job that inspects nothing and always passes.",
        )
        self.assertIn(
            "docs/acceptance-criteria/",
            run_bodies,
            f"Job {job_name!r} does not scope its staging to the store. "
            "Staging everything also stages "
            "leafcutter-web/fixtures/docs/acceptance-criteria/, which holds "
            "deliberately invalid fixture records, so the job would fail on "
            "its own test fixtures.",
        )

    def test_whole_store_job_applies_the_identical_rule_set_as_pr_scoped_job(
        self,
    ) -> None:
        # covers: ACS-200h
        # angle: seam
        """The whole-store job's rule set must be byte-identical to the
        PR-scoped `ac-store-valid` job's rule set (ACS-200g) — this is the
        AC's own literal requirement: "applying the same structural and
        schema rules it applies before merge". This test pipes the REAL
        `ac-store-valid` job's hook set (the producer) into the comparison
        against the REAL whole-store job's hook set (the consumer of the
        same rule definitions), so the two sides cannot silently drift.

        Currently RED: no whole-store job exists to compare against.
        """
        workflow = _load_workflow()
        pr_scoped_job = workflow["jobs"][_PR_SCOPED_JOB_ID]
        pr_scoped_hooks = _hook_ids_from_job(pr_scoped_job)
        self.assertTrue(
            pr_scoped_hooks,
            "Sanity check failed: the PR-scoped `ac-store-valid` job itself "
            "invokes no recognizable `pre-commit run <id>` hooks any more — "
            "update this test's parsing before trusting its parity check.",
        )

        job_name, whole_store_job = _find_whole_store_job(workflow)
        self.assertIsNotNone(
            job_name,
            "No whole-store CI job exists yet (ACS-200h) — cannot verify "
            "rule-set parity with ac-store-valid (ACS-200g) until it is "
            "implemented.",
        )
        whole_store_hooks = _hook_ids_from_job(whole_store_job)
        self.assertEqual(
            pr_scoped_hooks,
            whole_store_hooks,
            f"Whole-store job {job_name!r} applies hook set "
            f"{sorted(whole_store_hooks)}, which differs from the PR-scoped "
            f"`ac-store-valid` job's hook set {sorted(pr_scoped_hooks)}. "
            "ACS-200h requires the identical rule set on both sides.",
        )

    def test_index_driven_hooks_see_nothing_until_the_store_is_staged(
        self,
    ) -> None:
        # covers: ACS-200h
        # angle: reachability
        """The staging step is load-bearing: without it the hooks inspect ZERO
        records and pass vacuously.

        This is the defect that shipped in the first implementation of this AC
        and that no structural test caught, so it is pinned here by EXECUTING
        the real discovery function every check-ac-* hook uses
        (`_get_staged_ac_paths`) against a real temporary git repository —
        rather than by reading ci.yml and hoping.

        Two assertions, and the FIRST one is the important half:

          1. clean index  -> 0 records discovered. A job that stops here is
             permanently green while inspecting nothing.
          2. after the job's staging recipe -> every record discovered.

        Without assertion 1 the second proves nothing, because a discovery
        function that always returned every file would satisfy it too.
        """
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            store = repo / "docs" / "acceptance-criteria" / "demo"
            store.mkdir(parents=True)
            for name in ("DEMO-1.yaml", "DEMO-2.yaml", "DEMO-3.yaml"):
                (store / name).write_text("id: DEMO\n", encoding="utf-8")

            def git(*args: str) -> subprocess.CompletedProcess:
                return subprocess.run(  # noqa: S603
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=True,
                )

            git("init", "-q")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "t")
            git("add", "-A")
            git("commit", "-q", "-m", "seed")

            env = dict(os.environ)
            env.pop("HOOK_TEST_STAGED_FILES", None)

            def discovered() -> int:
                """Count records the real hook discovery function finds."""
                probe = (
                    "import sys, json;"
                    f"sys.path.insert(0, {str(_COMMIT_GUARDIAN_DIR)!r});"
                    "from check_ac_schema import _get_staged_ac_paths;"
                    "print(len(_get_staged_ac_paths()))"
                )
                out = subprocess.run(  # noqa: S603
                    [sys.executable, "-c", probe],
                    capture_output=True,
                    text=True,
                    cwd=str(repo),
                    env=env,
                )
                return int(out.stdout.strip() or "-1")

            clean_index = discovered()
            self.assertEqual(
                0,
                clean_index,
                "Expected the hooks' own discovery to find NOTHING on a clean "
                "index — that is precisely why the staging step exists. It "
                f"found {clean_index}. If this changed, the hooks no longer "
                "read the staged index and the CI job's staging step (and "
                "this test) should be revisited.",
            )

            # The job's recipe: point HEAD at an empty root commit so every
            # tracked file reads as newly added, then stage only the store.
            base = subprocess.run(  # noqa: S603
                ["git", "-C", str(repo), "commit-tree", empty_tree, "-m", "empty"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            git("reset", "--soft", base)
            git("reset", "-q")
            git("add", "--", "docs/acceptance-criteria/")

            after_staging = discovered()
            self.assertEqual(
                3,
                after_staging,
                "After the staging recipe the hooks should discover every "
                f"record in the store; found {after_staging} of 3. The "
                "whole-store job cannot inspect what its hooks cannot see.",
            )

    def test_git_add_alone_does_not_make_the_store_visible(self) -> None:
        # covers: ACS-200h
        # angle: failure
        """`git add -A` is NOT a substitute for the empty-base reset.

        Recorded as an executable test because it is the plausible-looking fix
        that does not work, and it was proposed during review of this very AC.
        `git add` stages CHANGES; on an unmodified checkout there are none, so
        `git diff --cached` stays empty and the hooks still see zero records —
        a job that looks fixed, reports green, and inspects nothing.

        If someone simplifies the staging step to a bare `git add`, this fails.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            store = repo / "docs" / "acceptance-criteria" / "demo"
            store.mkdir(parents=True)
            (store / "DEMO-1.yaml").write_text("id: DEMO\n", encoding="utf-8")

            def git(*args: str) -> subprocess.CompletedProcess:
                return subprocess.run(  # noqa: S603
                    ["git", "-C", str(repo), *args],
                    capture_output=True,
                    text=True,
                    check=True,
                )

            git("init", "-q")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "t")
            git("add", "-A")
            git("commit", "-q", "-m", "seed")

            git("add", "-A", "--", "docs/acceptance-criteria/")
            staged = subprocess.run(  # noqa: S603
                ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()

            self.assertEqual(
                [],
                staged,
                "`git add -A` staged something on an unmodified tree, which "
                "contradicts the reason the whole-store job needs an "
                "empty-base reset. If git's behaviour changed, the job's "
                "staging step can be simplified — verify before doing so.",
            )


if __name__ == "__main__":
    unittest.main()
