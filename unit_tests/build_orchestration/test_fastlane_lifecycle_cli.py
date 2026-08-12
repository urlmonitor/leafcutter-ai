"""
MODULE: unit_tests/build_orchestration/test_fastlane_lifecycle_cli.py
GOAL: RED entry-point-level tests for the lifecycle CLI subcommands
      (claim, release, mark_done) of fast_lane.py.

These tests exercise the CLI subcommands via subprocess — NOT by direct function
import. The direct-function layer is already tested in test_bo2400f_lifecycle.py.
This file adds the missing ENTRY-POINT layer: tests that call the CLI as a real
process and assert on exit code, JSON stdout, and on-disk YAML state.

=== Why this file is RED ===

The subcommands tested here — `claim`, `release`, `mark_done` — are NOT yet
registered in _build_cli_parser() in scripts/build_orchestration/fast_lane.py.
The parser currently knows only: select_batch, select_connected,
verify_red_baseline, verify_green_and_coverage.

When any of those subcommands is called via the CLI, argparse exits with code 2
("argument subcommand: invalid choice: 'claim' (choose from ...)").
The tests assert exit_code=0 (or specific non-zero), so they all fail.

=== CLI contract under test (for python-coder to implement) ===

1. claim --ac-ids <csv> --ac-root <DIR>
     Partitions ids via filter-already-claimed semantics:
       - ids with work_status todo  → to_build (flipped to in_progress on disk)
       - ids with work_status in_progress → excluded_claimed (untouched)
     If to_build is empty AND excluded_claimed non-empty → prints JSON with
       target_refused: true, claimed: [], exits NON-zero.
     Otherwise → flips todo→in_progress on disk, prints JSON
       {claimed:[...], excluded_claimed:[...], target_refused:false}, exits 0.

2. release --ac-ids <csv> --ac-root <DIR>
     Flips each in_progress AC → todo on disk.
     Idempotent: a todo id is a no-op (not an error).
     Prints JSON {released:[...]}, exits 0.

3. mark_done --ac-ids <csv> --ac-root <DIR> --test-root <DIR>
     Coverage-gated: for each AC id, scans test-root for a test tagged
     `# covers: <id>`, runs it; only flips in_progress→done when the test passes.
     Then runs the stale-todo guard.
     Prints JSON {marked_done:[...], all_done:bool, stale:[...]}.
     Exits 0 when all_done is true (no stale); non-zero otherwise.

=== Real-artifact behavioral mandate ===

All tests that mutate YAML use a real tmpdir (no mocking file writes).
After the CLI call, YAML is read back via yaml.safe_load to confirm on-disk state.

=== Fixture-authenticity mandate ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML).
The passing covers-test fixture is produced with textwrap.dedent and
Path.write_text — not an inline heredoc or inline literal.
"""

from __future__ import annotations

import json
import subprocess
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
_FAST_LANE_SCRIPT = _REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"


# ---------------------------------------------------------------------------
# Shared fixture helpers (mirror test_bo2400f_lifecycle.py conventions)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    work_status: str = "todo",
    readiness: str = "approved",
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate).

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier.
        work_status: "todo", "in_progress", or "done".
        readiness: "approved", "draft", or "reviewed".

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic CLI test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "covered_by": [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    # Fixture-authenticity mandate: use yaml.safe_dump, not a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _read_work_status(ac_root: Path, ac_id: str) -> str:
    """Read work_status from an AC YAML file on disk (real-artifact read-back).

    Uses yaml.safe_load — reads from disk, not memory — to verify
    the actual on-disk artifact state after a CLI mutation.

    Args:
        ac_root: Root of the AC store.
        ac_id: AC id whose YAML to read.

    Returns:
        The work_status string from the on-disk YAML.
    """
    yaml_path = ac_root / "test-component" / f"{ac_id}.yaml"
    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data["work_status"]


def _run_cli(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Invoke fast_lane.py as a CLI subprocess and return (exit_code, stdout, stderr).

    This exercises the REAL entry point — not a direct function import. The
    subprocess sees the same argparse error that a real operator would see when
    an unregistered subcommand is invoked.

    Args:
        args: Argument list passed after the script path.
        timeout: Maximum seconds to wait (default 10 — all lifecycle ops are fast).

    Returns:
        (exit_code, stdout, stderr) tuple.
    """
    result = subprocess.run(
        [sys.executable, str(_FAST_LANE_SCRIPT)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def _write_passing_covers_test(test_root: Path, ac_id: str) -> Path:
    """Write a minimal passing unittest file tagged with # covers: <ac_id>.

    The file is produced by Path.write_text with textwrap.dedent (not a
    hand-typed inline literal) — fixture-authenticity mandate: the producer
    is the real writer, so the test exercises the real format.

    Args:
        test_root: Root of the synthetic test tree.
        ac_id: AC id the test should cover (tagged via # covers: comment).

    Returns:
        Path to the written test file.
    """
    test_dir = test_root / "unit_tests" / "fastlane_covers"
    test_dir.mkdir(parents=True, exist_ok=True)
    # Ensure the directories are importable by pytest/unittest discover.
    init_ut = test_root / "unit_tests" / "__init__.py"
    init_covers = test_dir / "__init__.py"
    if not init_ut.exists():
        init_ut.write_text("", encoding="utf-8")
    if not init_covers.exists():
        init_covers.write_text("", encoding="utf-8")

    safe_name = ac_id.lower().replace("-", "_")
    test_file = test_dir / f"test_covers_{safe_name}.py"
    # Use textwrap.dedent to produce correctly-indented Python; write via
    # Path.write_text — NOT an inline heredoc (which would be a mutation
    # via a shell tool and trigger the file-mutation hook).
    code = textwrap.dedent(f"""\
        import unittest

        class TestCovers{safe_name.upper()}(unittest.TestCase):
            def test_covers_passing(self):
                # covers: {ac_id}
                self.assertTrue(True, "Synthetic passing covers test for {ac_id}")

        if __name__ == "__main__":
            unittest.main()
    """)
    test_file.write_text(code, encoding="utf-8")
    return test_file


# ---------------------------------------------------------------------------
# BO-2400f-7 / BO-2400f-8 / BO-2400f-8-i — `claim` CLI subcommand
# ---------------------------------------------------------------------------


class TestClaimCLISubcommand(unittest.TestCase):
    """Entry-point tests for the `claim` CLI subcommand.

    All tests are RED because `claim` is not yet registered in
    _build_cli_parser() in fast_lane.py. The argparse error
    ("invalid choice: 'claim'") exits with code 2 (non-zero), causing
    assertions on exit_code=0 to fail — the intended red state.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac7_claim_flips_todo_to_in_progress_on_disk(self) -> None:
        # covers: BO-2400f-7
        """CLI `claim` flips todo ACs to in_progress on disk and reports claimed ids.

        Real-artifact behavioral test: after invoking `python fast_lane.py claim ...`
        via subprocess, the YAML files are read back via yaml.safe_load to confirm
        the on-disk work_status changed to in_progress.

        RED because `claim` is not a registered CLI subcommand. Argparse exits 2
        before any YAML is touched, failing the exit_code==0 assertion.

        To make green, python-coder must:
        1. Register `claim` in _build_cli_parser() with --ac-ids and --ac-root args.
        2. In main(), handle the claim subcommand: call filter_already_claimed to
           partition ids, call claim_build_set on the to_build subset, print
           JSON {claimed:[], excluded_claimed:[], target_refused:false}, exit 0.
        """
        _write_ac(self.ac_root, "CLI-CLAIM-001", work_status="todo")
        _write_ac(self.ac_root, "CLI-CLAIM-002", work_status="todo")

        exit_code, stdout, stderr = _run_cli([
            "claim",
            "--ac-ids", "CLI-CLAIM-001,CLI-CLAIM-002",
            "--ac-root", str(self.ac_root),
        ])

        # Assert CLI exits successfully.
        self.assertEqual(
            exit_code,
            0,
            f"CLI `claim` must exit 0 when claiming todo ACs (BO-2400f-7). "
            f"Got exit_code={exit_code}. stderr={stderr!r}. "
            f"(RED: argparse 'invalid choice: claim' exits 2 — subcommand not yet registered.)",
        )

        # Assert JSON output has correct shape.
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(
                f"CLI `claim` must print JSON to stdout (BO-2400f-7). "
                f"Got stdout={stdout!r}. stderr={stderr!r}"
            )

        claimed = result.get("claimed", [])
        self.assertIn("CLI-CLAIM-001", claimed,
                      "CLI-CLAIM-001 must appear in claimed list (BO-2400f-7).")
        self.assertIn("CLI-CLAIM-002", claimed,
                      "CLI-CLAIM-002 must appear in claimed list (BO-2400f-7).")
        self.assertFalse(
            result.get("target_refused", True),
            "target_refused must be false when ACs are successfully claimed (BO-2400f-7). "
            f"Got result: {result!r}",
        )

        # Real-artifact read-back: confirm YAML files are in_progress on disk.
        for ac_id in ("CLI-CLAIM-001", "CLI-CLAIM-002"):
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual,
                "in_progress",
                f"AC {ac_id} must be in_progress on disk after CLI `claim` "
                f"(real-artifact behavioral test — BO-2400f-7). Got: {actual!r}",
            )

    def test_ac8_claim_all_in_progress_target_refused_nonzero_exit(self) -> None:
        # covers: BO-2400f-8
        """CLI `claim` on a fully-in_progress set exits non-zero with target_refused=true.

        When every AC in the set is already in_progress, the run refuses to proceed.
        The CLI must exit with a non-zero code and print JSON with target_refused=true
        and claimed=[]. It must NOT double-flip any AC (in_progress stays in_progress).

        RED because `claim` is not a registered CLI subcommand yet. Argparse exits 2,
        no JSON is printed. The assertNotEqual(exit_code, 0) would pass (2 != 0), but
        the json.loads(stdout) assertion fails because stdout is empty.
        """
        _write_ac(self.ac_root, "CLI-REFUSED-001", work_status="in_progress")
        _write_ac(self.ac_root, "CLI-REFUSED-002", work_status="in_progress")

        exit_code, stdout, stderr = _run_cli([
            "claim",
            "--ac-ids", "CLI-REFUSED-001,CLI-REFUSED-002",
            "--ac-root", str(self.ac_root),
        ])

        # Non-zero exit required when whole set is already claimed.
        self.assertNotEqual(
            exit_code,
            0,
            "CLI `claim` must exit NON-zero when whole set is already in_progress "
            "(target_refused — BO-2400f-8). Got exit_code=0.",
        )

        # JSON output must include target_refused=true and claimed=[].
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(
                "CLI `claim` must print JSON even on refusal (BO-2400f-8). "
                f"Got stdout={stdout!r}. stderr={stderr!r}. "
                "(RED: stdout is empty because argparse writes error to stderr only.)"
            )

        self.assertTrue(
            result.get("target_refused", False),
            "target_refused must be true when whole set is already in_progress "
            f"(BO-2400f-8). Got result: {result!r}",
        )
        claimed = result.get("claimed", ["unexpected"])
        self.assertEqual(
            claimed,
            [],
            f"claimed must be [] when target is refused (BO-2400f-8). Got: {claimed!r}",
        )

        # Real-artifact: in_progress ACs must NOT be double-flipped.
        for ac_id in ("CLI-REFUSED-001", "CLI-REFUSED-002"):
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual,
                "in_progress",
                f"AC {ac_id} must remain in_progress — CLI `claim` must NOT "
                f"double-flip an already-claimed AC (BO-2400f-8). Got: {actual!r}",
            )

    def test_ac8i_claim_mixed_set_only_todo_are_claimed(self) -> None:
        # covers: BO-2400f-8-i
        """CLI `claim` on a mixed set claims only todo ACs; in_progress land in excluded_claimed.

        A mix of todo and in_progress ACs must produce:
          - claimed: [<todo-ids>]
          - excluded_claimed: [<in_progress-ids>]
          - target_refused: false
          - exit code 0

        Only the todo ACs are flipped to in_progress on disk. The in_progress AC
        must remain in_progress (not touched).

        RED because `claim` is not a registered CLI subcommand yet. Argparse exits 2,
        failing the exit_code==0 assertion.
        """
        _write_ac(self.ac_root, "CLI-MIX-TODO", work_status="todo")
        _write_ac(self.ac_root, "CLI-MIX-INPROG", work_status="in_progress")

        exit_code, stdout, stderr = _run_cli([
            "claim",
            "--ac-ids", "CLI-MIX-TODO,CLI-MIX-INPROG",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            exit_code,
            0,
            f"CLI `claim` on a mixed set must exit 0 (BO-2400f-8-i). "
            f"Got exit_code={exit_code}. stderr={stderr!r}",
        )

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(
                f"CLI `claim` must print JSON (BO-2400f-8-i). Got stdout={stdout!r}"
            )

        claimed = result.get("claimed", [])
        excluded = result.get("excluded_claimed", [])

        self.assertIn("CLI-MIX-TODO", claimed,
                      "The todo AC must appear in claimed (BO-2400f-8-i).")
        self.assertNotIn("CLI-MIX-INPROG", claimed,
                         "The in_progress AC must NOT be in claimed (BO-2400f-8-i).")
        self.assertIn("CLI-MIX-INPROG", excluded,
                      "The in_progress AC must appear in excluded_claimed (BO-2400f-8-i).")
        self.assertFalse(
            result.get("target_refused", True),
            "target_refused must be false when some ACs are available to claim "
            f"(BO-2400f-8-i). Got result: {result!r}",
        )

        # Real-artifact: only the todo AC was flipped to in_progress.
        todo_status = _read_work_status(self.ac_root, "CLI-MIX-TODO")
        self.assertEqual(
            todo_status,
            "in_progress",
            "The todo AC must be in_progress on disk after CLI `claim` (BO-2400f-8-i). "
            f"Got: {todo_status!r}",
        )
        inprog_status = _read_work_status(self.ac_root, "CLI-MIX-INPROG")
        self.assertEqual(
            inprog_status,
            "in_progress",
            "The already-in_progress AC must remain in_progress on disk "
            f"(not double-flipped — BO-2400f-8-i). Got: {inprog_status!r}",
        )


# ---------------------------------------------------------------------------
# BO-2400f-10 — `release` CLI subcommand
# ---------------------------------------------------------------------------


class TestReleaseCLISubcommand(unittest.TestCase):
    """Entry-point tests for the `release` CLI subcommand.

    All tests are RED because `release` is not yet registered in
    _build_cli_parser(). Argparse exits 2 on any `release` invocation.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac10_release_flips_in_progress_to_todo_on_disk(self) -> None:
        # covers: BO-2400f-10
        """CLI `release` flips in_progress ACs back to todo on disk.

        Real-artifact behavioral test: after invoking `python fast_lane.py release ...`
        via subprocess, the YAML files are read back via yaml.safe_load to confirm
        work_status reverted to todo on disk.

        RED because `release` is not a registered CLI subcommand yet. Argparse exits 2,
        failing the exit_code==0 assertion.

        To make green, python-coder must:
        1. Register `release` in _build_cli_parser() with --ac-ids and --ac-root.
        2. In main(), handle the release subcommand: call release_claim with
           claimed_ids=<all ac-ids>, done_ids=[], print JSON {released:[...]}, exit 0.
        """
        _write_ac(self.ac_root, "CLI-REL-001", work_status="in_progress")
        _write_ac(self.ac_root, "CLI-REL-002", work_status="in_progress")

        exit_code, stdout, stderr = _run_cli([
            "release",
            "--ac-ids", "CLI-REL-001,CLI-REL-002",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            exit_code,
            0,
            f"CLI `release` must exit 0 (BO-2400f-10). "
            f"Got exit_code={exit_code}. stderr={stderr!r}. "
            f"(RED: argparse 'invalid choice: release' exits 2 — not yet registered.)",
        )

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(
                f"CLI `release` must print JSON (BO-2400f-10). "
                f"Got stdout={stdout!r}. stderr={stderr!r}"
            )

        released = result.get("released", [])
        self.assertIn("CLI-REL-001", released,
                      "CLI-REL-001 must appear in released list (BO-2400f-10).")
        self.assertIn("CLI-REL-002", released,
                      "CLI-REL-002 must appear in released list (BO-2400f-10).")

        # Real-artifact read-back: confirm both are todo on disk.
        for ac_id in ("CLI-REL-001", "CLI-REL-002"):
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual,
                "todo",
                f"AC {ac_id} must be todo on disk after CLI `release` "
                f"(real-artifact behavioral test — BO-2400f-10). Got: {actual!r}",
            )

    def test_ac10_release_idempotent_on_todo_ac(self) -> None:
        # covers: BO-2400f-10
        """CLI `release` is idempotent: a no-op on an AC already in todo status.

        Releasing a todo AC must not error — exits 0, AC remains todo on disk.
        The released list may include or omit the id (implementation choice).

        RED because `release` is not a registered CLI subcommand yet.
        """
        _write_ac(self.ac_root, "CLI-REL-IDEM", work_status="todo")

        exit_code, stdout, stderr = _run_cli([
            "release",
            "--ac-ids", "CLI-REL-IDEM",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            exit_code,
            0,
            f"CLI `release` on an already-todo AC must exit 0 "
            f"(idempotent — BO-2400f-10). Got exit_code={exit_code}. stderr={stderr!r}",
        )

        # Real-artifact: todo AC must remain todo (not double-flipped to done or lost).
        actual = _read_work_status(self.ac_root, "CLI-REL-IDEM")
        self.assertEqual(
            actual,
            "todo",
            f"A todo AC must remain todo after CLI `release` "
            f"(idempotent — BO-2400f-10). Got: {actual!r}",
        )


# ---------------------------------------------------------------------------
# BO-2400f-9 / BO-2400f-9-i — `mark_done` CLI subcommand
# ---------------------------------------------------------------------------


class TestMarkDoneCLISubcommand(unittest.TestCase):
    """Entry-point tests for the `mark_done` CLI subcommand.

    All tests are RED because `mark_done` is not yet registered in
    _build_cli_parser(). Argparse exits 2 on any `mark_done` invocation.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        self.test_root = Path(self._tmp.name) / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac9_mark_done_with_passing_covers_test(self) -> None:
        # covers: BO-2400f-9
        """CLI `mark_done` flips in_progress→done on disk when a passing covers test exists.

        Real-artifact behavioral test:
        1. A minimal passing unittest file tagged `# covers: CLI-DONE-001` is written
           to the test-root (produced by Path.write_text — real-format fixture).
        2. `python fast_lane.py mark_done --ac-ids CLI-DONE-001 ...` is invoked.
        3. The YAML file is read back to confirm work_status is done on disk.

        RED because `mark_done` is not a registered CLI subcommand yet. Argparse exits 2,
        failing the exit_code==0 assertion.

        To make green, python-coder must:
        1. Register `mark_done` in _build_cli_parser() with --ac-ids, --ac-root,
           --test-root args.
        2. In main(), handle mark_done: find covering tests via test-root scan,
           run them (subprocess or pytest), call mark_done_built_acs() with the
           covered ids, call check_no_stale_todo(), print JSON, exit 0/non-zero.
        """
        _write_ac(self.ac_root, "CLI-DONE-001", work_status="in_progress")
        _write_passing_covers_test(self.test_root, "CLI-DONE-001")

        exit_code, stdout, stderr = _run_cli([
            "mark_done",
            "--ac-ids", "CLI-DONE-001",
            "--ac-root", str(self.ac_root),
            "--test-root", str(self.test_root),
        ])

        self.assertEqual(
            exit_code,
            0,
            f"CLI `mark_done` must exit 0 when all ACs are done (BO-2400f-9). "
            f"Got exit_code={exit_code}. stderr={stderr!r}. "
            f"(RED: argparse 'invalid choice: mark_done' exits 2 — not yet registered.)",
        )

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(
                f"CLI `mark_done` must print JSON (BO-2400f-9). "
                f"Got stdout={stdout!r}. stderr={stderr!r}"
            )

        self.assertIn(
            "CLI-DONE-001",
            result.get("marked_done", []),
            "CLI-DONE-001 must appear in marked_done (BO-2400f-9).",
        )
        self.assertTrue(
            result.get("all_done", False),
            "all_done must be true when all ACs are marked done (BO-2400f-9). "
            f"Got result: {result!r}",
        )
        self.assertEqual(
            result.get("stale", ["unexpected"]),
            [],
            "stale must be [] when all ACs are done (BO-2400f-9). "
            f"Got: {result.get('stale')!r}",
        )

        # Real-artifact read-back: confirm done on disk.
        actual = _read_work_status(self.ac_root, "CLI-DONE-001")
        self.assertEqual(
            actual,
            "done",
            "AC CLI-DONE-001 must be done on disk after CLI `mark_done` with "
            "a passing covers test (real-artifact behavioral test — BO-2400f-9). "
            f"Got: {actual!r}",
        )

    def test_ac9i_mark_done_without_covers_test_reports_stale_nonzero(self) -> None:
        # covers: BO-2400f-9-i
        """CLI `mark_done` exits non-zero and reports stale when covers test is missing.

        When an AC in the input set has no covering test in the test-root,
        `mark_done` must NOT flip it to done. It must:
        - Report the AC in the stale list.
        - Set all_done: false.
        - Exit non-zero (stale-todo guard).

        Real-artifact behavioral test: after the call, the YAML must NOT show
        work_status done on disk.

        RED because `mark_done` is not a registered CLI subcommand yet.
        The test's json.loads(stdout) assertion fails because stdout is empty
        (argparse writes only to stderr on error).
        """
        _write_ac(self.ac_root, "CLI-STALE-001", work_status="in_progress")
        # Intentionally do NOT write a covers test for CLI-STALE-001 in the test-root.

        exit_code, stdout, stderr = _run_cli([
            "mark_done",
            "--ac-ids", "CLI-STALE-001",
            "--ac-root", str(self.ac_root),
            "--test-root", str(self.test_root),
        ])

        # Non-zero exit when any built AC is still not done (stale-todo guard).
        self.assertNotEqual(
            exit_code,
            0,
            "CLI `mark_done` must exit NON-zero when an AC has no covers test "
            "and remains not-done (stale-todo guard — BO-2400f-9-i). "
            f"Got exit_code=0 (unexpectedly). stderr={stderr!r}",
        )

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(
                "CLI `mark_done` must print JSON even on stale-guard failure "
                f"(BO-2400f-9-i). Got stdout={stdout!r}. stderr={stderr!r}. "
                "(RED: stdout is empty because argparse writes error to stderr only.)"
            )

        self.assertFalse(
            result.get("all_done", True),
            "all_done must be false when an AC has no covers test (BO-2400f-9-i). "
            f"Got result: {result!r}",
        )
        self.assertIn(
            "CLI-STALE-001",
            result.get("stale", []),
            "CLI-STALE-001 must appear in stale list (BO-2400f-9-i).",
        )

        # Real-artifact: AC must NOT have been flipped to done.
        actual = _read_work_status(self.ac_root, "CLI-STALE-001")
        self.assertNotEqual(
            actual,
            "done",
            "AC CLI-STALE-001 must NOT be flipped to done when its covers test "
            "is missing (coverage-gated — BO-2400f-9-i). "
            f"Got: {actual!r}",
        )


if __name__ == "__main__":
    unittest.main()
