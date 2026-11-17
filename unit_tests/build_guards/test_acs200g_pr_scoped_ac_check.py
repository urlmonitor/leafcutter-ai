"""
MODULE: unit_tests/build_guards/test_acs200g_pr_scoped_ac_check.py
GOAL: Cover ACS-200g — every pull request that changes the requirements
    store must have those changes checked against the store's own rules
    before merge, as a hard, blocking CI check.
BUSINESS CONTEXT: ACS-200g is the direct dependency ACS-200h is built on top
    of (ACS-200h's `expects_from` names ACS-200g's contract verbatim: "The
    same rule set and the same check, run over the whole store instead of
    over the changed records."). Unlike ACS-200h, ACS-200g's CI job
    (`ac-store-valid` in .github/workflows/ci.yml) already exists in this
    worktree — but as of authoring this file, zero tests in the repository
    tag `# covers: ACS-200g` (confirmed via a grep across unit_tests/), so
    this AC has never had dedicated coverage of its own. This file adds
    that coverage.
ARCHITECTURE: The reachability test below invokes the REAL deployed
    guardrail script (.leafcutter/scripts/commit_guardian/check_ac_schema.py
    — the same script `pre-commit run check-ac-schema` resolves to, per the
    tracked .pre-commit-config.yaml `entry:` line) via subprocess against a
    genuinely malformed AC record written to a real temp file, using the
    script's own documented `HOOK_TEST_STAGED_FILES` test seam rather than a
    mocked staging step. This is the real entry point ac-store-valid uses,
    exercised end-to-end.

NOTE ON EXPECTED BASELINE OUTCOME: ACS-200g's `ac-store-valid` job already
    ships in this worktree (see the "NOT YET IMPLEMENTED — ACS-200h" comment
    directly in .github/workflows/ci.yml, which frames ACS-200g as the
    already-done half). These tests may therefore be GREEN at baseline
    rather than red — that is expected and is not a TDD-order violation for
    THIS ticket, whose implementation target is ACS-200h. It is recorded
    here explicitly rather than silently, per the project's TDD-order
    convention (see CLAUDE.md "TDD Order — test-writer Must Precede
    python-coder").
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from unit_tests.build_guards import _acs200g_fixture as fx

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_DEPLOYED_SCHEMA_HOOK = (
    _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "check_ac_schema.py"
)
_PR_SCOPED_JOB_ID = "ac-store-valid"


class TestAcs200gPrScopedAcCheck(unittest.TestCase):
    """ACS-200g — a blocking, PR-scoped acceptance-criteria CI check."""

    def test_pr_scoped_job_is_hard_blocking_not_advisory(self) -> None:
        # covers: ACS-200g
        # angle: criterion
        """The AC requires "a hard, blocking check — not an advisory or
        informational one that a pull request can be merged despite". A CI
        job with `continue-on-error: true` on any step is advisory: its
        failure is swallowed and the job still reports success.
        """
        workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn(
            _PR_SCOPED_JOB_ID,
            workflow["jobs"],
            f"Expected a {_PR_SCOPED_JOB_ID!r} job in .github/workflows/ci.yml.",
        )
        job = workflow["jobs"][_PR_SCOPED_JOB_ID]
        self.assertNotEqual(
            True,
            job.get("continue-on-error"),
            f"Job {_PR_SCOPED_JOB_ID!r} sets continue-on-error at the job "
            "level, making it advisory rather than blocking (ACS-200g).",
        )
        for step in job.get("steps", []):
            self.assertNotEqual(
                True,
                step.get("continue-on-error"),
                f"Step {step.get('name')!r} in job {_PR_SCOPED_JOB_ID!r} sets "
                "continue-on-error, making the guardrail check advisory "
                "rather than blocking (ACS-200g).",
            )

    tree_before: tuple[str, str]
    tree_after: tuple[str, str]
    cache_before: tuple[bool, int | None, int | None]
    cache_after: tuple[bool, int | None, int | None]
    runs: dict[str, fx.HookRun]
    fixture_cache_ids: dict[str, set[str]]
    fixture_roots: list[Path]
    staged_names: dict[str, str]

    @classmethod
    def setUpClass(cls) -> None:
        """Run both hook scenarios once, each in its own fresh fixture repo.

        ACS-200g-3: the fixture is a small git-initialised temp repo, so the
        hook indexes four records, not the whole real store. Real-tree and
        real-cache snapshots are taken immediately around the runs, and the
        comparisons happen after the fixtures are removed.

        The real-cache check stays strict (existence, mtime_ns, size); the
        fixture-cache id-set assertion is the main proof. If strictness proves
        flaky in CI because another test rebuilds the real cache, relax it to
        "not created when it did not exist" and record that here.
        """
        assert _DEPLOYED_SCHEMA_HOOK.is_file(), (
            f"Expected the deployed guardrail script at {_DEPLOYED_SCHEMA_HOOK} "
            "- run `python scripts/build.py --target-dir .` if this worktree "
            "has not been built."
        )
        git_dir = fx.real_git_dir()
        cls.tree_before = fx.tree_snapshot()
        cls.cache_before = fx.cache_snapshot(git_dir)
        cls.runs = {}
        cls.fixture_cache_ids = {}
        cls.fixture_roots = []
        cls.staged_names = {}
        for label, staged_id in (("blocking", fx.MALFORMED_ID), ("control", fx.VALID_IDS[0])):
            root = Path(tempfile.mkdtemp(prefix="acs200g3_"))
            cls.fixture_roots.append(root)
            try:
                paths = fx.build_fixture(root)
                cls.runs[label] = fx.run_hook(root, paths[staged_id], label)
                cls.staged_names[label] = staged_id
                cache = root / ".git" / fx.CACHE_NAME
                cls.fixture_cache_ids[label] = (
                    set(json.loads(cache.read_text(encoding="utf-8"))["index"])
                    if cache.is_file()
                    else set()
                )
            finally:
                fx.remove_tree(root)
        cls.cache_after = fx.cache_snapshot(git_dir)
        cls.tree_after = fx.tree_snapshot()

    def test_check_reachable_via_real_entry_point_blocks_on_a_malformed_record(
        self,
    ) -> None:
        # covers: ACS-200g-3
        # angle: reachability
        # must_catch: a malformed record passes
        # must_catch: the hook crashes on import in the fixture and fails open with exit 0
        # must_catch: the output does not name ZZTEST-999 or the rule it breaks
        """ACS-200g-3: run the COPIED deployed check_ac_schema.py as a script
        (HOOK_ROOT = cwd = fixture), staging only the ZZTEST-999 record.
        Exit code is exactly 1, the output names the record and a missing
        required field, and the hook did not fail open.
        """
        run = self.runs["blocking"]
        self.assertEqual(
            1, run.returncode, f"Expected exit 1 (blocking), got {run.returncode}:\n{run.output}"
        )
        self.assertIn(fx.MALFORMED_ID, run.output)
        self.assertRegex(
            run.output,
            r"'(title|criteria|component|components|status)' is a required property",
            f"Output must name a required field the record lacks:\n{run.output}",
        )
        self.assertNotIn("unexpected error (fail-open)", run.output)

    def test_check_passes_a_valid_fixture_record_via_real_entry_point(self) -> None:
        # covers: ACS-200g-3
        # angle: discrimination
        # must_catch: the fixture store or schema is unreadable so every staged record is blocked
        # must_catch: a sibling module is missing from the copied hook directory
        # must_catch: the valid fixture records are themselves invalid under the real schema
        """ACS-200g-3 control: same fixture and entry point, staging one valid
        record. Exit 0, no failed-validation line, no line naming the record.
        """
        run = self.runs["control"]
        self.assertEqual(0, run.returncode, f"Expected exit 0 for a valid record:\n{run.output}")
        self.assertNotIn("failed validation", run.output)
        self.assertNotIn(self.staged_names["control"], run.output)
        self.assertNotIn("unexpected error (fail-open)", run.output)

    def test_check_reads_only_fixture_records_not_the_real_store(self) -> None:
        # covers: ACS-200g-3
        # angle: discrimination
        # must_catch: HOOK_ROOT still points at the real repo
        # must_catch: cwd still points at the real repo so the cache is written to the real git dir
        # must_catch: fixture is not git-initialised so the cache falls back to the system temp dir
        """ACS-200g-3: the fixture's own index cache exists and its index keys
        are exactly the four fixture ids - no real-store id, so the number of
        records read is independent of the real store's size.
        """
        for label in ("blocking", "control"):
            self.assertEqual(
                set(fx.FIXTURE_IDS),
                self.fixture_cache_ids[label],
                f"{label} run: fixture index cache must hold exactly the four "
                "fixture ids (empty = no fixture cache; extra = real store read).",
            )

    def test_each_fixture_hook_run_finishes_under_ten_seconds_cold(self) -> None:
        # covers: ACS-200g-3
        # angle: boundary
        # must_catch: the hook indexes the whole real store on a cold run (about 22 s)
        # must_catch: the 30 s timeout is raised instead of narrowing the store
        # must_catch: the cache is pre-warmed so the measured run is not cold
        """ACS-200g-3: each run (fresh fixture, so no cache) finishes in under
        10 s while the subprocess timeout stays at 30 s. The real index cache
        is not touched to simulate a cold runner.
        """
        self.assertEqual(30, fx.HOOK_TIMEOUT_SECONDS)
        for label, run in self.runs.items():
            self.assertLess(
                run.seconds,
                fx.COLD_RUN_BOUND_SECONDS,
                f"{label} run took {run.seconds:.2f}s, bound is {fx.COLD_RUN_BOUND_SECONDS}s",
            )

    def test_check_leaves_real_tree_and_real_index_cache_untouched(self) -> None:
        # covers: ACS-200g-3
        # angle: criterion
        # must_catch: real index cache written
        # must_catch: fixture or malformed record written inside the real working tree
        # must_catch: tmp repo left behind after the check
        """ACS-200g-3: real `git status --porcelain=v1 --untracked-files=all`,
        the SHA-256 of `git diff HEAD --binary` and the real index cache
        (exists, mtime_ns, size) are equal before and after, and every
        fixture directory is gone.
        """
        self.assertEqual(self.tree_before, self.tree_after, "real working tree changed")
        self.assertEqual(
            self.cache_before, self.cache_after, "real index cache created/changed/deleted"
        )
        for root in self.fixture_roots:
            self.assertFalse(root.exists(), f"fixture left behind: {root}")

    def test_pr_scoped_job_covers_every_rule_family_named_in_the_ac(self) -> None:
        # covers: ACS-200g
        # angle: criterion
        """The AC names six rule families explicitly: record schema and
        required fields, the parent/child back-link, the per-parent child
        limit, absence of dependency cycles, resolvable shared-pattern
        references, and authorship governance. All six must be invoked by
        the PR-scoped job.
        """
        import re

        workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
        job = workflow["jobs"][_PR_SCOPED_JOB_ID]
        run_bodies = " \n".join(
            step["run"] for step in job.get("steps", []) if isinstance(step.get("run"), str)
        )
        invoked_hooks = set(re.findall(r"pre-commit\s+run\s+([A-Za-z0-9._-]+)", run_bodies))
        expected_hooks = {
            "check-ac-schema",
            "check-ac-tree-limits",
            "check-ac-governance",
            "check-ac-parent-covered-by",
            "check-ac-circular-deps",
            "check-ac-pattern-refs",
        }
        missing = expected_hooks - invoked_hooks
        self.assertEqual(
            set(),
            missing,
            f"Job {_PR_SCOPED_JOB_ID!r} is missing hook(s) {sorted(missing)} "
            "required to cover every rule family ACS-200g's criteria names.",
        )


if __name__ == "__main__":
    unittest.main()
