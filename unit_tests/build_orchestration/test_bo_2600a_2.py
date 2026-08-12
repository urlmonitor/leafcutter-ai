"""
MODULE: unit_tests/build_orchestration/test_bo_2600a_2.py
GOAL: RED test stubs for BO-2600a-2 — The select_connected CLI exposes
      --exclude-structural-parent.

=== Interface contract under test ===

Target: the `select_connected` subcommand of
    scripts/build_orchestration/fast_lane.py

New behaviour (BO-2600a-2):
    The subcommand gains a store_true flag --exclude-structural-parent.
    When supplied, the flag is forwarded to resolve_connected_build_set as
    exclude_structural_parent=True, so the structural parent dep is not
    expanded into the build set.
    When omitted (default False) the subcommand behaves exactly as today.
    A missing --ac id still exits non-zero with the ValueError-derived message.

=== Red baseline ===

test_cli_exclude_structural_parent_flag_propagates
    RED — argparse exits 2 with "unrecognized arguments: --exclude-structural-parent"
    because the flag is not yet registered on the select_connected subparser.

test_cli_default_matches_existing_behavior
    Likely GREEN today (current CLI already works for select_connected without
    the flag).  Included as a regression guard to verify that adding the flag
    does not accidentally change the default behaviour.
    Noted in red_baseline with "passes immediately — may be under-specified".

test_cli_missing_ac_exits_nonzero
    Likely GREEN today (current CLI already catches ValueError and exits 1).
    Included to prevent a regression where adding the flag handler breaks the
    existing error path.
    Noted in red_baseline with "passes immediately — may be under-specified".

=== Fixture authenticity ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
literals), following the pattern from test_fast_lane_connected.py and
test_bo_2600a_1.py.

AC ids used:
    BO-9000a       (L1) — parent of BO-9000a-1 and BO-9000a-2
    BO-9000a-1     (L2) — depends_on: [BO-9000a, BO-8888a-1]
    BO-9000a-2     (L2) — no deps (reachable only via expanding BO-9000a)
    BO-8888a       (L1) — parent of BO-8888a-1
    BO-8888a-1     (L2) — no deps (genuine peer dep of BO-9000a-1)

    derive_parent_id("BO-9000a-1") == "BO-9000a"   → structural parent dep
    derive_parent_id("BO-9000a-1") != "BO-8888a-1" → genuine peer dep
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"

for _p in (_MODULE_DIR, _AC_STORE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_SCRIPT_PATH = _MODULE_DIR / "fast_lane.py"

# Import derive_parent_id for fixture invariant checks.
from ac_parent_id import derive_parent_id  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    readiness: str = "approved",
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate).

    Mirrors the helper in test_fast_lane_connected.py and test_bo_2600a_1.py.
    No hand-typed YAML — always serialised via yaml.safe_dump.

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier.
        level: "L0", "L1", "L2", or "L3".
        work_status: "todo" or "done".
        readiness: "approved", "draft", or "reviewed" (default: "approved").
        depends_on: List of AC ids this AC depends on.
        covered_by: List of child AC ids (for parent nodes).

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    # Fixture-authenticity mandate: yaml.safe_dump, never a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run fast_lane.py as a subprocess CLI.

    Args:
        args: CLI args after the script name.

    Returns:
        Tuple (returncode, stdout, stderr).
    """
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Tests for BO-2600a-2
# ---------------------------------------------------------------------------


class TestSelectConnectedExcludeStructuralParentCli(unittest.TestCase):
    """CLI tests for select_connected --exclude-structural-parent (BO-2600a-2).

    test_cli_exclude_structural_parent_flag_propagates is RED until python-coder
    adds the --exclude-structural-parent flag to the select_connected subparser
    in fast_lane.py and threads args.exclude_structural_parent into
    resolve_connected_build_set.

    The other two tests (default behavior; missing-id error path) are regression
    guards that verify existing CLI behavior is preserved after the change.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_shared_fixture(self) -> None:
        """Build the shared AC tree used by tests 1 and 2.

        Tree layout:
            BO-9000a  (L1) — covered_by: [BO-9000a-1, BO-9000a-2]
              BO-9000a-1  (L2) — depends_on: [BO-9000a, BO-8888a-1]
              BO-9000a-2  (L2) — no deps

            BO-8888a  (L1) — covered_by: [BO-8888a-1]
              BO-8888a-1  (L2) — no deps  (genuine peer dep)

        Fixture invariants:
            derive_parent_id("BO-9000a-1") == "BO-9000a"   ← structural parent dep
            derive_parent_id("BO-9000a-1") != "BO-8888a-1" ← genuine peer dep
        """
        assert derive_parent_id("BO-9000a-1") == "BO-9000a", (
            "Fixture invariant: 'BO-9000a' must be the structural parent of "
            "'BO-9000a-1' — ensure the fixture IDs are correct."
        )
        assert derive_parent_id("BO-9000a-1") != "BO-8888a-1", (
            "Fixture invariant: 'BO-8888a-1' must NOT be the structural parent "
            "of 'BO-9000a-1' — it is a genuine peer dep."
        )

        _write_ac(
            self.ac_root,
            "BO-9000a",
            level="L1",
            work_status="todo",
            covered_by=["BO-9000a-1", "BO-9000a-2"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-9000a", "BO-8888a-1"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-2",
            level="L2",
            work_status="todo",
        )
        _write_ac(
            self.ac_root,
            "BO-8888a",
            level="L1",
            work_status="todo",
            covered_by=["BO-8888a-1"],
        )
        _write_ac(
            self.ac_root,
            "BO-8888a-1",
            level="L2",
            work_status="todo",
        )

    def test_cli_exclude_structural_parent_flag_propagates(self) -> None:
        # covers: BO-2600a-2
        """AC-1/AC-2: --exclude-structural-parent flag is accepted and propagated.

        When select_connected is invoked with --exclude-structural-parent:
          - It must exit 0 (success).
          - The output JSON list must include the target leaf BO-9000a-1
            (enters via the subtree union, unaffected by the flag).
          - The output must include genuine peer dep BO-8888a-1
            (dep != derive_parent_id(node), so NOT skipped).
          - The output must NOT include BO-9000a-2
            (only reachable by expanding BO-9000a, the structural parent dep of
            BO-9000a-1; that expansion is skipped when the flag is set).

        DEFECT (red state): --exclude-structural-parent is not yet registered on
        the select_connected subparser.  argparse will exit 2 with:
          "error: unrecognized arguments: --exclude-structural-parent"

        To make this green:
          1. Add `sc.add_argument("--exclude-structural-parent", action="store_true", ...)`
             to the select_connected subparser in _build_cli_parser().
          2. In main(), change the select_connected handler to:
               resolve_connected_build_set(
                   args.ac,
                   ac_root=Path(args.ac_root),
                   exclude_structural_parent=args.exclude_structural_parent,
               )
        """
        self._build_shared_fixture()

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--exclude-structural-parent",
            "--ac", "BO-9000a-1",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            returncode,
            0,
            f"select_connected --exclude-structural-parent must exit 0 on success. "
            f"Got {returncode}.\nstdout={stdout!r}\nstderr={stderr!r}\n"
            "DEFECT: --exclude-structural-parent is not yet registered on the "
            "select_connected subparser in fast_lane.py.",
        )

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(
                f"CLI must print a JSON list to stdout. Got JSONDecodeError: {exc!r}\n"
                f"stdout={stdout!r}\nstderr={stderr!r}\n"
                "DEFECT: --exclude-structural-parent flag is missing from the CLI."
            )

        self.assertIsInstance(result, list, "CLI output must be a JSON list.")

        self.assertIn(
            "BO-9000a-1",
            result,
            "Target leaf BO-9000a-1 must be in the result — it enters via the "
            "subtree union and is unaffected by --exclude-structural-parent. "
            "(BO-2600a-2 AC-1/AC-2)",
        )

        self.assertIn(
            "BO-8888a-1",
            result,
            "Genuine peer dep BO-8888a-1 must be in the result — "
            "derive_parent_id('BO-9000a-1') == 'BO-9000a' != 'BO-8888a-1', "
            "so it is NOT the structural parent and must NOT be skipped. "
            "(BO-2600a-2 AC-2: only structural parent dep is excluded.)",
        )

        self.assertNotIn(
            "BO-9000a-2",
            result,
            "BO-9000a-2 must NOT be in the result when --exclude-structural-parent "
            "is set. The only path to BO-9000a-2 is via expanding BO-9000a (the "
            "structural parent dep of BO-9000a-1); that expansion is skipped when "
            "the flag is set. "
            "(BO-2600a-2 AC-2: resolve_connected_build_set called with "
            "exclude_structural_parent=True.)",
        )

    def test_cli_default_matches_existing_behavior(self) -> None:
        # covers: BO-2600a-2
        """AC-3: without --exclude-structural-parent, output matches existing behavior.

        When select_connected is invoked WITHOUT --exclude-structural-parent:
          - exclude_structural_parent defaults to False (existing behavior).
          - The structural parent dep BO-9000a IS expanded into its leaves.
          - BO-9000a-2 IS included (only reachable via expanding BO-9000a).

        This test verifies that adding the flag does not change the default
        behavior for callers who omit it.

        NOTE: this test may pass today because the existing select_connected CLI
        already works without the flag (the default behavior is unchanged).
        It is included as a regression guard for AC-3 — python-coder must not
        accidentally make exclude_structural_parent=True the default.
        """
        self._build_shared_fixture()

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", "BO-9000a-1",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            returncode,
            0,
            f"select_connected (no flag) must exit 0. "
            f"Got {returncode}.\nstderr={stderr!r}",
        )

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(
                f"CLI must print a JSON list to stdout. Got JSONDecodeError: {exc!r}\n"
                f"stdout={stdout!r}"
            )

        self.assertIsInstance(result, list, "CLI output must be a JSON list.")

        self.assertIn(
            "BO-9000a-1",
            result,
            "Target leaf BO-9000a-1 must be in the result (existing behavior). "
            "(BO-2600a-2 AC-3)",
        )

        # Key regression assertion: with flag absent, BO-9000a (the structural parent
        # dep) IS expanded into its leaves, so BO-9000a-2 MUST be in the result.
        self.assertIn(
            "BO-9000a-2",
            result,
            "BO-9000a-2 must be in the result when --exclude-structural-parent is "
            "NOT set (default=False): BO-9000a (structural parent dep of BO-9000a-1) "
            "is expanded into its leaves, adding BO-9000a-2 to the build set. "
            "(BO-2600a-2 AC-3: default behavior preserved — structural parent dep "
            "IS expanded when the flag is absent.)",
        )

    def test_cli_missing_ac_exits_nonzero(self) -> None:
        # covers: BO-2600a-2
        """AC-4: --ac with an unknown id exits non-zero with the ValueError-derived message.

        When select_connected is invoked with an unknown --ac id:
          - The CLI must exit non-zero (exit code 1).
          - The output (stdout or stderr) must name the missing id.

        This test ensures the existing ValueError propagation path is not broken
        after adding the --exclude-structural-parent flag.

        NOTE: this test may pass today because the existing select_connected CLI
        already catches ValueError and exits 1 with the missing id in the message.
        It is included as a regression guard for AC-4.
        """
        missing_id = "BO-NONEXISTENT-CLI-BO2600a-2"

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", missing_id,
            "--ac-root", str(self.ac_root),
        ])

        self.assertNotEqual(
            returncode,
            0,
            f"select_connected must exit non-zero for an unknown --ac id. "
            f"Got exit code 0.\nstdout={stdout!r}\nstderr={stderr!r}\n"
            "(BO-2600a-2 AC-4: missing AC id still exits non-zero.)",
        )

        combined = stdout + stderr
        self.assertIn(
            missing_id,
            combined,
            f"The CLI output must name the missing id '{missing_id}'. "
            f"Got combined output: {combined!r}\n"
            "(BO-2600a-2 AC-4: ValueError-derived message names the missing id.)",
        )

    def test_cli_exclude_flag_does_not_affect_missing_id_error_path(self) -> None:
        # covers: BO-2600a-2
        """AC-4 + AC-1: --exclude-structural-parent + missing --ac still exits non-zero.

        Even when --exclude-structural-parent is supplied, a missing --ac id must
        still exit non-zero with the id named in the output.

        This discriminating test verifies that the flag handler does not accidentally
        swallow the ValueError raised by resolve_connected_build_set for an unknown id.

        DEFECT (red state): --exclude-structural-parent is not yet registered on
        the select_connected subparser; argparse will exit 2 instead of 1.
        argparse exit 2 IS still non-zero — but the assertion on the missing id in
        the output distinguishes the correct (ValueError message) from incorrect
        (argparse "unrecognized arguments" message) output.
        """
        missing_id = "BO-NONEXISTENT-CLI-BO2600a-2-FLAG"

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--exclude-structural-parent",
            "--ac", missing_id,
            "--ac-root", str(self.ac_root),
        ])

        self.assertNotEqual(
            returncode,
            0,
            f"select_connected --exclude-structural-parent with missing --ac must "
            f"exit non-zero. Got exit code 0.\nstdout={stdout!r}\nstderr={stderr!r}",
        )

        combined = stdout + stderr
        # When the flag is not yet registered, argparse exits 2 with a message
        # about "unrecognized arguments" (which does NOT name the missing ac id).
        # After implementation, the ValueError-derived message MUST name the missing id.
        # Post-implementation assertion (will fail today because argparse message
        # names the flag, not the missing ac id):
        self.assertIn(
            missing_id,
            combined,
            f"After implementation, the output must name the missing id '{missing_id}'. "
            f"Got combined output: {combined!r}\n"
            "DEFECT: --exclude-structural-parent is not yet registered; argparse "
            "currently exits 2 with 'unrecognized arguments: --exclude-structural-parent' "
            "instead of the ValueError-derived message naming the missing AC id. "
            "(BO-2600a-2 AC-4: missing AC id path must work with the flag present.)",
        )


if __name__ == "__main__":
    unittest.main()
