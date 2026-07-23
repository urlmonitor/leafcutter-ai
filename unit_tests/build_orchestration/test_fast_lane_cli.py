"""
MODULE: unit_tests/build_orchestration/test_fast_lane_cli.py
GOAL: BEHAVIORAL tests for DEFECT H-2 — fast_lane.py has no CLI entry point.
      These tests run the module as a CLI via subprocess and assert real JSON
      output and correct exit codes.  They are RED now because no CLI exists.

=== DEFECT H-2 (Fast Lane CLI missing) ===

The review confirmed that scripts/build_orchestration/fast_lane.py has no
if __name__ == "__main__" block and no CLI entry point.  Running it as a
script with subcommand args produces no output and exits 0 without printing
any JSON.

=== CLI CONTRACT defined by these tests (for python-coder to implement) ===

Subcommand 1 — select_batch:

    python3 fast_lane.py select_batch \\
        --ac-root <path>    # root of the AC YAML store
        --limit <N>         # maximum number of ACs to return

    Output: one JSON-encoded line to stdout — a list of AC id strings.
    Exit code: 0 always (selection is deterministic; an empty store returns []).
    Example stdout: ["BO-2400a-1", "BO-2400a-2"]

Subcommand 2 — verify_red_baseline:

    python3 fast_lane.py verify_red_baseline \\
        --ac-ids <id1,id2,...>   # comma-separated AC ids
        --test-root <path>       # root dir to scan for test files

    Output: one JSON-encoded line to stdout — a dict with keys:
        {
            "all_red": bool,
            "offender": str | null,          -- nodeid of first passing test
            "offender_ac_id": str | null     -- covers tag of the offending test
        }
    Exit code:
        0  when all_red is True  (all linked tests are failing — coder may run)
        1  when all_red is False (at least one test passes — coder MUST NOT run)

Subcommand 3 — verify_green_and_coverage:

    python3 fast_lane.py verify_green_and_coverage \\
        --ac-ids <id1,id2,...>   # comma-separated AC ids
        --test-root <path>       # root dir to scan for test files
        --ac-root <path>         # root of the AC YAML store

    Output: one JSON-encoded line to stdout — a dict with keys:
        {
            "green": bool,
            "coverage_ok": bool,
            "uncovered_ac_ids": list[str],
            "failing_tests": list[str]
        }
    Exit code:
        0  when both green and coverage_ok are True
        1  when either condition fails

=== Fixture-authenticity mandate (BO-2500c) ===

  All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML).
  All test fixtures are real .py files with genuine test bodies.
  No mocking of subprocess pass/fail signals.

=== Red baseline ===

  All tests are RED until python-coder adds a CLI entry point to
  scripts/build_orchestration/fast_lane.py that dispatches the three
  subcommands above.  The failures manifest as:
    - JSONDecodeError / AssertionError when parsing empty stdout
    - AssertionError on unexpected exit codes
"""
from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _write_approved_ac(
    ac_root: Path,
    ac_id: str,
    *,
    priority: str = "medium",
    estimated_complexity: str = "S",
    work_status: str = "todo",
) -> Path:
    """Write a minimal approved, active, leaf L2 AC YAML.

    Uses yaml.safe_dump (fixture-authenticity mandate — no hand-typed YAML).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC.
        priority: AC priority field ("critical", "high", "medium", "low").
        estimated_complexity: AC complexity field ("S", "M", "L", "XL").
        work_status: AC work status ("todo", "done").

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": priority,
        "estimated_complexity": estimated_complexity,
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file to test_root using textwrap.dedent.

    Args:
        test_root: Directory to place the test file.
        filename: Filename (e.g. "test_my_feature.py").
        content: Python source; leading whitespace is dedented automatically.

    Returns:
        Path to the written test file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run fast_lane.py as a CLI via subprocess and return (returncode, stdout, stderr).

    Args:
        args: List of CLI args following the script name.

    Returns:
        Tuple of (exit code, stdout text, stderr text).
    """
    import subprocess

    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# TestSelectBatchCli — DEFECT H-2 / select_batch subcommand
# ---------------------------------------------------------------------------


class TestSelectBatchCli(unittest.TestCase):
    """CLI tests for the select_batch subcommand.

    Contract: python3 fast_lane.py select_batch --ac-root <path> --limit <N>
      - Prints a JSON list of AC ids to stdout
      - Exits 0
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_h2_select_batch_cli_prints_json_list(self) -> None:
        # covers: BO-2400a-2
        """select_batch CLI must print a JSON list to stdout and exit 0.

        DEFECT H-2: fast_lane.py has no CLI; running it with subcommand args
        produces no output. JSONDecodeError on empty stdout is the current red state.

        To make this green, add a CLI entry point that:
        1. Accepts 'select_batch' as a subcommand
        2. Accepts --ac-root and --limit arguments
        3. Calls select_batch(ac_root=..., limit=...) from the module
        4. Prints json.dumps(result) to stdout
        5. Exits 0
        """
        _write_approved_ac(self.ac_root, "BO-CLI-001")
        _write_approved_ac(self.ac_root, "BO-CLI-002", priority="high")

        returncode, stdout, stderr = _run_cli([
            "select_batch",
            "--ac-root", str(self.ac_root),
            "--limit", "5",
        ])

        self.assertEqual(
            returncode,
            0,
            f"select_batch CLI must exit 0. Got {returncode}.\nstderr: {stderr}",
        )

        # The stdout must be valid JSON
        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(
                f"select_batch CLI must print a JSON list to stdout. "
                f"Current output is not valid JSON: {exc!r}\n"
                f"stdout={stdout!r}\nstderr={stderr!r}\n"
                f"DEFECT H-2: no CLI entry point in fast_lane.py"
            )

        self.assertIsInstance(
            result,
            list,
            f"select_batch CLI must print a JSON LIST of AC ids, got {type(result).__name__}. "
            f"stdout={stdout!r}",
        )

    def test_h2_select_batch_cli_returns_correct_ac_ids(self) -> None:
        # covers: BO-2400a-2
        """select_batch CLI must return the AC ids that are approved and ready.

        The output must be a JSON list containing the approved ACs' ids.
        High-priority AC must sort before medium-priority AC (deterministic order).
        """
        _write_approved_ac(self.ac_root, "BO-CLI-010", priority="medium")
        _write_approved_ac(self.ac_root, "BO-CLI-011", priority="high")

        returncode, stdout, _stderr = _run_cli([
            "select_batch",
            "--ac-root", str(self.ac_root),
            "--limit", "10",
        ])

        self.assertEqual(returncode, 0, "select_batch CLI must exit 0.")

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"select_batch output is not valid JSON: {exc!r}\nstdout={stdout!r}")

        self.assertIn("BO-CLI-010", result, "Approved medium-priority AC must be in the batch.")
        self.assertIn("BO-CLI-011", result, "Approved high-priority AC must be in the batch.")

        # High-priority sorts before medium-priority
        idx_high = result.index("BO-CLI-011")
        idx_medium = result.index("BO-CLI-010")
        self.assertLess(
            idx_high,
            idx_medium,
            "High-priority AC must appear before medium-priority in the batch "
            "(deterministic sort: priority asc → complexity asc → id asc).",
        )

    def test_h2_select_batch_cli_empty_store_returns_empty_list(self) -> None:
        # covers: BO-2400a-2
        """select_batch CLI must return [] for an empty AC store and exit 0.

        The CLI must handle an empty or non-existent store gracefully.
        """
        self.ac_root.mkdir(parents=True, exist_ok=True)

        returncode, stdout, _stderr = _run_cli([
            "select_batch",
            "--ac-root", str(self.ac_root),
            "--limit", "5",
        ])

        self.assertEqual(returncode, 0, "select_batch CLI must exit 0 even on empty store.")

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"select_batch output is not valid JSON on empty store: {exc!r}\nstdout={stdout!r}")

        self.assertEqual(
            result,
            [],
            "select_batch CLI must return [] for an empty store (no ready ACs).",
        )

    def test_h2_select_batch_cli_respects_limit(self) -> None:
        # covers: BO-2400a-2
        """select_batch CLI must respect the --limit argument (cohesion cap).

        With 4 ready ACs and --limit 2, the output must contain at most 2 ids.
        """
        for i in range(4):
            _write_approved_ac(self.ac_root, f"BO-CLI-CAP-{i:03d}", priority="high")

        returncode, stdout, _stderr = _run_cli([
            "select_batch",
            "--ac-root", str(self.ac_root),
            "--limit", "2",
        ])

        self.assertEqual(returncode, 0, "select_batch CLI must exit 0.")

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"select_batch output is not valid JSON: {exc!r}\nstdout={stdout!r}")

        self.assertLessEqual(
            len(result),
            2,
            f"select_batch CLI must return at most 2 ACs when --limit 2 is given. "
            f"Got {len(result)}.",
        )


# ---------------------------------------------------------------------------
# TestVerifyRedBaselineCli — DEFECT H-2 / verify_red_baseline subcommand
# ---------------------------------------------------------------------------


class TestVerifyRedBaselineCli(unittest.TestCase):
    """CLI tests for the verify_red_baseline subcommand.

    Contract: python3 fast_lane.py verify_red_baseline --ac-ids <ids> --test-root <path>
      - Prints a JSON dict {all_red, offender, offender_ac_id} to stdout
      - Exits 0 when all_red is True (all batch tests fail — gate passes)
      - Exits 1 when all_red is False (a test passes — gate blocks coder)
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.test_root = root / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_h2_red_baseline_cli_prints_json_verdict(self) -> None:
        # covers: BO-2400a-3
        """verify_red_baseline CLI must print a JSON dict verdict to stdout.

        DEFECT H-2: no CLI exists — the subprocess produces no JSON output.
        JSONDecodeError on empty stdout is the current red state.

        To make this green, add a CLI that:
        1. Accepts 'verify_red_baseline' subcommand
        2. Accepts --ac-ids (comma-separated) and --test-root arguments
        3. Calls verify_red_baseline(ac_ids=[...], test_root=...) from the module
        4. Prints json.dumps(result) to stdout
        5. Exits 0 when all_red is True, exits 1 when all_red is False
        """
        ac_id = "BO-CLI-RED-001"
        _write_test_file(
            self.test_root,
            "test_red_cli_fixture.py",
            f"""\
            def test_fails_before_implementation():
                # covers: {ac_id}
                assert False, "not yet implemented"
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_red_baseline",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
        ])

        # The stdout must be valid JSON regardless of the verdict
        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(
                f"verify_red_baseline CLI must print a JSON dict to stdout. "
                f"Current output is not valid JSON: {exc!r}\n"
                f"stdout={stdout!r}\nstderr={stderr!r}\n"
                f"DEFECT H-2: no CLI entry point in fast_lane.py"
            )

        for key in ("all_red", "offender", "offender_ac_id"):
            self.assertIn(
                key,
                result,
                f"verify_red_baseline JSON output must contain key '{key}'. "
                f"Got keys: {list(result.keys())}",
            )

    def test_h2_red_baseline_cli_exits_0_when_all_red(self) -> None:
        # covers: BO-2400a-3
        """verify_red_baseline CLI must exit 0 when all tests fail (gate passes).

        When all linked tests fail (as expected before implementation), the
        gate passes and the coder may be dispatched.  Exit 0 signals gate-pass.
        """
        ac_id = "BO-CLI-RED-002"
        _write_test_file(
            self.test_root,
            "test_red_exits_0_fixture.py",
            f"""\
            def test_genuinely_fails():
                # covers: {ac_id}
                assert False, "intentional failure — pre-implementation"
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_red_baseline",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError:
            self.fail(
                f"verify_red_baseline CLI must print valid JSON. "
                f"stdout={stdout!r}\nstderr={stderr!r}"
            )

        self.assertTrue(
            result.get("all_red"),
            "all_red must be True when all linked tests fail.",
        )
        self.assertEqual(
            returncode,
            0,
            "verify_red_baseline CLI must exit 0 when all_red is True "
            "(gate passes — coder may be dispatched). "
            f"Got exit code {returncode}.\nstdout={stdout!r}",
        )

    def test_h2_red_baseline_cli_exits_1_when_test_passes(self) -> None:
        # covers: BO-2400a-3
        """verify_red_baseline CLI must exit 1 when any test already passes (gate blocks).

        A passing test before implementation means the test is under-specified
        or implementation already exists.  Exit 1 signals gate-block — the
        coder must NOT be dispatched.
        """
        ac_id = "BO-CLI-RED-003"
        _write_test_file(
            self.test_root,
            "test_passes_before_impl_fixture.py",
            f"""\
            def test_already_passes():
                # covers: {ac_id}
                pass  # passes before implementation — gate must block
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_red_baseline",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError:
            self.fail(
                f"verify_red_baseline CLI must print valid JSON even on gate-block. "
                f"stdout={stdout!r}\nstderr={stderr!r}"
            )

        self.assertFalse(
            result.get("all_red"),
            "all_red must be False when a test already passes before implementation.",
        )
        self.assertEqual(
            returncode,
            1,
            "verify_red_baseline CLI must exit 1 when all_red is False "
            "(gate blocks — coder must NOT be dispatched). "
            f"Got exit code {returncode}.\nstdout={stdout!r}",
        )

    def test_h2_red_baseline_cli_names_offender_in_verdict(self) -> None:
        # covers: BO-2400a-3
        """verify_red_baseline CLI verdict must name the offending test when gate blocks.

        The JSON output must include a non-None 'offender' field with the
        test function name when all_red is False.
        """
        ac_id = "BO-CLI-RED-004"
        _write_test_file(
            self.test_root,
            "test_offender_named_fixture.py",
            f"""\
            def test_named_offender_passes():
                # covers: {ac_id}
                pass  # this is the offender
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_red_baseline",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError:
            self.fail(f"verify_red_baseline CLI must print valid JSON. stdout={stdout!r}")

        offender = result.get("offender")
        self.assertIsNotNone(
            offender,
            "The 'offender' field must be set (non-None) when all_red is False.",
        )
        self.assertIn(
            "test_named_offender_passes",
            str(offender),
            "The offender field must name the test function that passed.",
        )


# ---------------------------------------------------------------------------
# TestVerifyGreenAndCoverageCli — DEFECT H-2 / verify_green_and_coverage
# ---------------------------------------------------------------------------


class TestVerifyGreenAndCoverageCli(unittest.TestCase):
    """CLI tests for the verify_green_and_coverage subcommand.

    Contract: python3 fast_lane.py verify_green_and_coverage \\
                  --ac-ids <ids> --test-root <path> --ac-root <path>
      - Prints a JSON dict {green, coverage_ok, uncovered_ac_ids, failing_tests}
      - Exits 0 when both green and coverage_ok are True
      - Exits 1 when either condition fails
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_active_ac(self, ac_id: str) -> None:
        """Write a minimal active AC YAML for done_proof coverage checks."""
        subdir = self.ac_root / "test-component"
        subdir.mkdir(parents=True, exist_ok=True)
        data: dict = {
            "id": ac_id,
            "title": f"Synthetic active AC {ac_id}",
            "component": "build-orchestration",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "readiness": "approved",
            "priority": "medium",
            "estimated_complexity": "S",
            "depends_on": [],
            "amended_by": [],
            "covered_by": [],
            "implemented_by": [],
            "superseded_by": None,
        }
        (subdir / f"{ac_id}.yaml").write_text(
            yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
        )

    def test_h2_green_coverage_cli_prints_json_verdict(self) -> None:
        # covers: BO-2400a-4
        """verify_green_and_coverage CLI must print a JSON dict verdict to stdout.

        DEFECT H-2: no CLI exists — no JSON output. JSONDecodeError is the red state.

        To make this green, add a CLI that:
        1. Accepts 'verify_green_and_coverage' subcommand
        2. Accepts --ac-ids, --test-root, --ac-root arguments
        3. Calls verify_green_and_coverage(ac_ids=[...], test_root=..., ac_root=...) from the module
        4. Prints json.dumps(result) to stdout
        5. Exits 0 when green and coverage_ok are both True; exits 1 otherwise
        """
        ac_id = "BO-CLI-GRN-001"
        self._write_active_ac(ac_id)
        _write_test_file(
            self.test_root,
            "test_green_passes_fixture.py",
            f"""\
            def test_passes_after_implementation():
                # covers: {ac_id}
                pass  # implementation done; test passes
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_green_and_coverage",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
            "--ac-root", str(self.ac_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(
                f"verify_green_and_coverage CLI must print a JSON dict to stdout. "
                f"Current output is not valid JSON: {exc!r}\n"
                f"stdout={stdout!r}\nstderr={stderr!r}\n"
                f"DEFECT H-2: no CLI entry point in fast_lane.py"
            )

        for key in ("green", "coverage_ok", "uncovered_ac_ids", "failing_tests"):
            self.assertIn(
                key,
                result,
                f"verify_green_and_coverage JSON output must contain key '{key}'. "
                f"Got keys: {list(result.keys())}",
            )

    def test_h2_green_coverage_cli_exits_0_when_both_pass(self) -> None:
        # covers: BO-2400a-4
        """CLI must exit 0 when all tests pass AND every AC has a covering test.

        Both conditions must be True for the gate to pass and staging to proceed.
        """
        ac_id = "BO-CLI-GRN-002"
        self._write_active_ac(ac_id)
        _write_test_file(
            self.test_root,
            "test_green_and_covered_fixture.py",
            f"""\
            def test_passes_and_is_covered():
                # covers: {ac_id}
                pass
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_green_and_coverage",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
            "--ac-root", str(self.ac_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError:
            self.fail(f"verify_green_and_coverage CLI must print valid JSON. stdout={stdout!r}")

        self.assertTrue(result.get("green"), "green must be True when all tests pass.")
        self.assertTrue(result.get("coverage_ok"), "coverage_ok must be True when all ACs are covered.")
        self.assertEqual(
            returncode,
            0,
            "verify_green_and_coverage CLI must exit 0 when both green and coverage_ok are True. "
            f"Got exit code {returncode}.",
        )

    def test_h2_green_coverage_cli_exits_1_when_tests_fail(self) -> None:
        # covers: BO-2400a-4
        """CLI must exit 1 when any test is still failing (green=False).

        A failing test after the coder ran means the implementation is incomplete.
        The gate must block commit staging.
        """
        ac_id = "BO-CLI-GRN-003"
        self._write_active_ac(ac_id)
        _write_test_file(
            self.test_root,
            "test_still_failing_fixture.py",
            f"""\
            def test_not_yet_passing():
                # covers: {ac_id}
                assert False, "coder did not implement this"
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_green_and_coverage",
            "--ac-ids", ac_id,
            "--test-root", str(self.test_root),
            "--ac-root", str(self.ac_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError:
            self.fail(f"verify_green_and_coverage CLI must print valid JSON. stdout={stdout!r}")

        self.assertFalse(result.get("green"), "green must be False when tests are still failing.")
        self.assertEqual(
            returncode,
            1,
            "verify_green_and_coverage CLI must exit 1 when green is False "
            "(commit staging must be blocked). "
            f"Got exit code {returncode}.",
        )

    def test_h2_green_coverage_cli_exits_1_when_ac_uncovered(self) -> None:
        # covers: BO-2400a-4
        """CLI must exit 1 when any AC id has no covering test (coverage_ok=False).

        An AC with no covers-tagged test is not proven — commit staging must
        be blocked even if all existing tests pass.
        """
        ac_id_covered = "BO-CLI-GRN-004a"
        ac_id_uncovered = "BO-CLI-GRN-004b"
        self._write_active_ac(ac_id_covered)
        self._write_active_ac(ac_id_uncovered)
        _write_test_file(
            self.test_root,
            "test_one_uncovered_fixture.py",
            f"""\
            def test_covers_first_ac_only():
                # covers: {ac_id_covered}
                pass  # only covers one AC; second AC has no test
            """,
        )

        returncode, stdout, stderr = _run_cli([
            "verify_green_and_coverage",
            "--ac-ids", f"{ac_id_covered},{ac_id_uncovered}",
            "--test-root", str(self.test_root),
            "--ac-root", str(self.ac_root),
        ])

        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError:
            self.fail(f"verify_green_and_coverage CLI must print valid JSON. stdout={stdout!r}")

        self.assertFalse(
            result.get("coverage_ok"),
            "coverage_ok must be False when any AC has no covering test.",
        )
        self.assertEqual(
            returncode,
            1,
            "verify_green_and_coverage CLI must exit 1 when coverage_ok is False "
            "(one AC is uncovered). "
            f"Got exit code {returncode}.",
        )


if __name__ == "__main__":
    unittest.main()
