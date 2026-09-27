"""
MODULE: test_ge_120f_1_i_b
AC: GE-120f-1-i -- rework companion to test_ge_120f_1_i.py (that module
    sits at 372/400 counted lines, no headroom left for this test).
GOAL: Coordinator-directed rework closing pr-reviewer's H-1 finding
    (fb_2026-09-25_79587943): `_classify_demonstration()` returns
    `DEMONSTRATION_ENTRY_POINT` when `hook.get("entry")` is falsy -- a hook
    declaring `negative_control` with NO registered `entry` is silently
    certified as a genuine entry-point demonstration with no ground truth to
    support that claim. Correct behaviour: `demonstration = "n/a"`,
    `currently.state = "blocked"`, evidence/reason saying there is no
    registered entry point to demonstrate through; the run fails; the sweep
    continues to any other examined hook.

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i, coordinator rework for pr-reviewer H-1]: Initial red test.
  `test_ge_120f_1_i.py` was left untouched (no counted-line headroom left;
  that module's own test_spec already names fixed test names inside it
  specifically). Invokes the real deployed runner as a real subprocess (via
  `_deployed_check_harness.DeployedCheckHarness`, GE-120c-1's own harness)
  against a real fixture manifest -- never asserts on source text.
====================================================================
"""
# @ac-tag: GE-120f-1-i

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root

sys.path.insert(0, str(_THIS_DIR))

import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402
import _ge_120f_1_fixtures as fx  # type: ignore[import]  # noqa: E402
import _ge_120f_1_i_fixtures as fxi  # type: ignore[import]  # noqa: E402


class TestGE120f1iNoRegisteredEntryPoint(unittest.TestCase):
    """Shared, expensive fixture: one real deployed-only working copy via the
    real scripts/build.py -- mirrors test_ge_120f_1_i.py's own RUNTIME
    BUDGET convention."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(cls._tmp.name)
        cls.copy_dir = tmp_root / "copy"
        cls.harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        cls.harness.create_second_copy(cls.copy_dir)
        cls.deployed_cg_dir = cls.copy_dir / ".leafcutter" / "scripts" / "commit_guardian"
        cls.fixtures_dir = cls.copy_dir / "_ge120f1ib_fixtures"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # covers: GE-120f-1-i
    def test_ge120f1i_a_hook_with_no_registered_entry_point_is_blocked_not_demonstrated(
        self,
    ) -> None:
        """pr-reviewer H-1 (fb_2026-09-25_79587943). A hook that declares a
        `negative_control` (a bad input the check genuinely refuses) plus a
        discriminating acceptable command, but NO `entry` field at all, has
        no independent ground truth to compare the performed invocation
        against. `_classify_demonstration()` today defaults an absent
        `entry` to `DEMONSTRATION_ENTRY_POINT` -- silently certifying a
        genuine entry-point demonstration with nothing to support that
        claim, the exact fail-open shape this AC forbids (its own
        error-handling policy: "A failed invocation is blocked, never a
        silent absence and never a passing"). Correct behaviour:
        demonstration="n/a", currently.state="blocked", not "passing", and
        the sweep's own exit code is non-zero. A sibling hook WITH a real
        `entry` in the SAME run must still read passing -- the fix must not
        regress a genuinely demonstrated check, and the sweep must continue
        past the blocked hook rather than aborting."""
        # covers: GE-120f-1-i
        # angle: failure
        no_entry_id = "ge120f1ib-fixture-no-entry"
        healthy_id = "ge120f1ib-fixture-no-entry-healthy-sibling"
        no_entry_script = self.deployed_cg_dir / "_ge120f1ib_no_entry.py"
        healthy_script = self.deployed_cg_dir / "_ge120f1ib_no_entry_healthy.py"
        manifest_path = self.fixtures_dir / "no_entry_manifest.json"

        fx.write_script(no_entry_script, fx.reject_script("NOENTRY"))
        fx.write_script(healthy_script, fx.reject_script("NOENTRY_HEALTHY"))

        # Deliberately NO "entry" key -- the shape H-1 names. Still declares
        # a discriminating acceptable command so the pairing logic does not
        # short-circuit to `pair_cannot_discriminate` for an unrelated
        # reason -- this must be blocked BECAUSE of the missing `entry`.
        no_entry_hook = {
            "id": no_entry_id,
            "tier": "judgment",
            "name": "GE-120f-1-i fixture check with no registered entry",
            "negative_control": {
                "input": "BADINPUT",
                "command": fxi.direct_command(no_entry_script),
                "expected_result": "non-zero exit",
            },
            "command": fxi.direct_command(no_entry_script, "GOODINPUT"),
            "pass_criteria": "zero exit",
        }
        healthy_command = fxi.direct_command(healthy_script)
        healthy_hook = fxi.hook_with(
            healthy_id, entry=healthy_command, command=healthy_command,
            accept_command=fxi.direct_command(healthy_script, "GOODINPUT"),
        )
        fx.write_fixture_manifest(manifest_path, [no_entry_hook, healthy_hook])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", no_entry_id, "--check-id", healthy_id],
        )
        results = fx.parse_results(outcome.output)
        self.assertIn(no_entry_id, results, f"No record. Output:\n{outcome.output}")
        self.assertIn(healthy_id, results, f"No record. Output:\n{outcome.output}")

        self.assertEqual(
            results[no_entry_id]["demonstration"], "n/a",
            "No `entry` means no ground truth to compare against -- the "
            f"invocation cannot be classified a demonstration. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[no_entry_id]["state"], "blocked",
            "A hook declaring no `entry` must be blocked, never certified "
            f"passing with no ground truth. Output:\n{outcome.output}",
        )
        self.assertNotEqual(
            results[no_entry_id]["state"], "passing",
            f"Output:\n{outcome.output}",
        )
        self.assertNotEqual(
            outcome.exit_code, 0,
            f"The sweep must fail when an examined hook is blocked. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[healthy_id]["state"], "passing",
            "The sweep must continue to the remaining hooks -- a sibling "
            f"hook declaring a real `entry` must still read passing. Output:\n{outcome.output}",
        )


if __name__ == "__main__":
    unittest.main()
