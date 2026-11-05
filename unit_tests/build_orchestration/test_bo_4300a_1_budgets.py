"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
AC: BO-4300a-1 IT12 (amended, EPIC-WorkspaceMakerHardening N4 / A13 option 2).

WHAT THIS PROVES
====================================================================
Excluding the install build, `ensure` on a generated fixture project of 8,500
tracked files with the stub build is budgeted 30 s; `locate`, `list`, `verify`
and `where` 5 s each. The test PRINTS one `<verb> <seconds>` line per verb (the
recorded timings) and fails only when a verb exceeds TWICE its budget, naming
the verb and the measured time. It exceeds max_test_duration_seconds, so it is
`_MANUAL` and runs in the dedicated deployed-maker CI job.
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    make_project,
    run_maker,
)
from unit_tests.build_orchestration._workspace_maker_builders import _run_git

TRACKED_FILES = 8500
BUDGET_SECONDS = {"ensure": 30.0, "locate": 5.0, "list": 5.0, "verify": 5.0, "where": 5.0}
FAIL_FACTOR = 2.0


def over_limit(verb: str, measured: float) -> str | None:
    """Return the failure message when *measured* exceeds twice *verb*'s budget."""
    limit = BUDGET_SECONDS[verb] * FAIL_FACTOR
    if measured > limit:
        return f"{verb} took {measured:.2f}s, above 2x its {BUDGET_SECONDS[verb]:.0f}s budget ({limit:.0f}s)"
    return None


class TestVerbTimingsAreRecorded(unittest.TestCase):
    def test_verb_timings_are_recorded_and_fail_only_above_twice_budget_MANUAL(self):
        # covers: BO-4300a-1
        # angle: deployed
        """MUST BE IMPLEMENTED: time ensure/locate/list/verify/where against a project
        with 8,500 tracked files; print `<verb> <seconds>`; fail only above 2x budget."""
        with tempfile.TemporaryDirectory(prefix="bo4300a1-budget-") as d:
            tmp = Path(d)
            made = make_project(tmp)
            project = Path(made["project"])
            # The bulk commit below writes ~8,600 loose objects, over git's gc.auto
            # threshold (6,700), so it would start a DETACHED `gc --auto` that packs
            # and prunes those objects while the timed ensure hardlink-clones them
            # (`failed to create link ... No such file or directory`, CI run
            # 39945745604). Hold auto-gc off on the fixture project only and pack
            # it ONCE, synchronously, after the push: the timed clone then always
            # hardlinks a settled, packed repository (what a real 8,500-file
            # project is, and what the passing runs measured). ensure must still
            # set gc.auto 0 on the workspace itself (git clone copies no config).
            _run_git(["config", "gc.auto", "0"], project)
            _run_git(["config", "maintenance.auto", "false"], project)
            bulk = project / "bulk"
            for i in range(TRACKED_FILES):
                sub = bulk / f"d{i // 100:03d}"
                sub.mkdir(parents=True, exist_ok=True)
                (sub / f"f{i:05d}.txt").write_text(f"file {i}\n", encoding="utf-8")
            _run_git(["add", "-A"], project)
            _run_git(["commit", "-q", "-m", "bulk tracked tree"], project)
            _run_git(["push", "-q", "origin", "main"], project)
            _run_git(["gc", "-q"], project)

            timings: dict[str, float] = {}

            def timed(verb: str, args: list[str], cwd: Path) -> dict:
                result = run_maker([verb, *args], cwd=cwd, timeout=300)
                # run_maker records the wall time of the maker subprocess itself
                # (the stub install runs inside it; the generated 8,500-file tree is
                # built before and outside the timed call).
                self.assertIn("elapsed_seconds", result, msg="run_maker must record elapsed_seconds")
                timings[verb] = float(result["elapsed_seconds"])
                print(f"{verb} {timings[verb]:.2f}", flush=True)
                self.assertEqual("ok", result["answer"].get("status"), msg=f"{verb}: {result}")
                return result["answer"]

            ensured = timed("ensure", ["--kind", "scratch", "--slug", "budget"], project)
            location = ensured.get("workspace_path")
            self.assertTrue(location, msg=f"ensure named no workspace: {ensured}")
            # The timed ensure must be real: it CREATED a workspace holding the bulk tree.
            self.assertEqual("created", ensured.get("workspace_action"), msg=f"ensure was not a creation: {ensured}")
            listed = _run_git(["ls-files", "bulk"], Path(location)).stdout.splitlines()
            self.assertGreaterEqual(len(listed), TRACKED_FILES, msg=f"workspace tracks {len(listed)} bulk files")
            on_disk = sum(1 for p in (Path(location) / "bulk").rglob("*") if p.is_file())
            self.assertGreaterEqual(on_disk, TRACKED_FILES, msg=f"only {on_disk} bulk files checked out on disk")
            timed("locate", ["--kind", "scratch", "--slug", "budget"], project)
            timed("list", [], project)
            created = Path(location)
            verified = timed("verify", ["--path", str(created)], created)
            self.assertEqual(str(created), verified.get("path"), msg="verify must time the created workspace")
            timed("where", [], created)

        self.assertEqual(sorted(BUDGET_SECONDS), sorted(timings), msg="every verb must be timed")
        failures = [m for m in (over_limit(v, t) for v, t in timings.items()) if m]
        self.assertEqual([], failures, msg="; ".join(failures))

    def test_over_limit_names_the_verb_and_time_only_above_twice_budget(self):
        # covers: BO-4300a-1
        # angle: boundary
        """Control rows: exactly 2x passes; just above fails naming verb and time."""
        self.assertIsNone(over_limit("ensure", 60.0))
        self.assertIsNone(over_limit("where", 10.0))
        message = over_limit("locate", 10.5)
        self.assertIsNotNone(message)
        self.assertIn("locate", message)
        self.assertIn("10.50", message)
        self.assertIsNone(over_limit("list", 5.1), "above budget but under 2x must not fail")


if __name__ == "__main__":
    unittest.main()
