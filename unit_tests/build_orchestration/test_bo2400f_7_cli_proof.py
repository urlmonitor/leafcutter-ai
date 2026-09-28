"""
MODULE: unit_tests/build_orchestration/test_bo2400f_7_cli_proof.py
GOAL: BO-2400f-7 proof tests driven through fast_lane's real CLI entry point
      (``fast_lane.main(["claim", ...])``), not through a direct function
      import.
BUSINESS CONTEXT: BO-2900's reachability guard refuses a `done` AC whose proof
      reaches the code by direct import, because a function that works when
      called directly proves nothing about the command the lane actually
      shells out to. These three tests are the guard-observable proof for
      BO-2400f-7 and carry its `# covers:` tags; the fine-grained
      `TestClaimBuildSet` unit tests of `claim_build_set`'s own contract
      remain in test_bo2400f_lifecycle.py without the tag — a different and
      still-useful thing to assert, just not the reachability proof.
ARCHITECTURE: Split out of test_bo2400f_lifecycle.py (2026-09-28) purely to
      satisfy the check-file-size ratchet guard once that file was already at
      its 400-line limit; no test logic changed in the split. See this
      module's own DECISION HISTORY below.

=== Why these are module-level functions, not TestCase methods ===

The reachability guard's observation runner resolves a test with
``getattr(module, function_name)`` and calls it — so a ``unittest.TestCase``
method is not reachable by it at all, and is reported as "isolated
re-execution did not pass". That is a defect in the runner (it should resolve
methods too, and is filed as such), but it is not the reason these tests are
written this way: even once the runner can call a method, the CLI-not-direct-
import requirement above still requires driving ``main``. Module-level is
what makes the proof observable today.

Each test manages its own temp store rather than relying on setUp, since a
module-level function has none.

=== Fixture-authenticity mandate ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring (mirrors test_bo2400f_lifecycle.py's bootstrap)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

# ---------------------------------------------------------------------------
# Import the fast_lane module and select_batch — RED until both exist.
# ---------------------------------------------------------------------------

_FAST_LANE_MODULE_OK = False
fast_lane = None  # type: ignore[assignment]

try:
    import fast_lane  # type: ignore[no-redef]
    _FAST_LANE_MODULE_OK = True
except ImportError:
    pass

_SELECT_BATCH_IMPORT_OK = False
select_batch = None  # type: ignore[assignment]

try:
    from fast_lane import select_batch  # type: ignore[no-redef]
    _SELECT_BATCH_IMPORT_OK = True
except (ImportError, AttributeError):
    pass


# ---------------------------------------------------------------------------
# Shared fixture helpers (mirror test_bo2400f_lifecycle.py conventions)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str = "L2",
    work_status: str = "todo",
    readiness: str = "approved",
    depends_on: Optional[list] = None,
    covered_by: Optional[list] = None,
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate).

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier (e.g. "BO-F7-001").
        level: Level string ("L2" or "L3").
        work_status: "todo", "in_progress", or "done".
        readiness: "approved", "draft", or "reviewed".
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
    # Fixture-authenticity mandate: use yaml.safe_dump, not a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _read_work_status(ac_root: Path, ac_id: str) -> str:
    """Read the work_status field from an AC YAML file on disk.

    Uses yaml.safe_load — reads from disk, not from memory — to verify the
    real-artifact state after a mutation call.

    Args:
        ac_root: Root of the AC store.
        ac_id: AC id whose YAML to read.

    Returns:
        The work_status string from the on-disk YAML.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        KeyError: If work_status is absent from the YAML.
    """
    yaml_path = ac_root / "test-component" / f"{ac_id}.yaml"
    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data["work_status"]


def _read_all_fields(ac_root: Path, ac_id: str) -> dict:
    """Read and return all YAML fields for an AC from disk.

    Args:
        ac_root: Root of the AC store.
        ac_id: AC id whose YAML to read.

    Returns:
        Dict of all fields from the on-disk YAML.
    """
    yaml_path = ac_root / "test-component" / f"{ac_id}.yaml"
    with yaml_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _claim_via_cli(ac_ids: list[str], ac_root: Path) -> int:
    """Run the real ``claim`` subcommand the fast lane shells out to.

    Returns the CLI's exit code. ``main`` returns an int rather than raising
    SystemExit when handed an explicit argv, so no exit trapping is needed.
    """
    return fast_lane.main(
        ["claim", "--ac-ids", ",".join(ac_ids), "--ac-root", str(ac_root)]
    )


def test_claim_through_cli_flips_todo_to_in_progress() -> None:
    # covers: BO-2400f-7
    """Running the real claim command flips resolved todo ACs to in_progress.

    The lane's own claim step is ``fast_lane.py claim --ac-ids ... --ac-root
    ...``. This drives that command and reads the YAML back off disk.
    """
    if not _FAST_LANE_MODULE_OK:
        raise AssertionError("fast_lane module not importable — cannot drive its CLI.")
    with tempfile.TemporaryDirectory() as tmp:
        ac_root = Path(tmp) / "acs"
        ac_root.mkdir(parents=True, exist_ok=True)
        _write_ac(ac_root, "BO-F7-CLI-001", work_status="todo")
        _write_ac(ac_root, "BO-F7-CLI-002", work_status="todo")

        exit_code = _claim_via_cli(["BO-F7-CLI-001", "BO-F7-CLI-002"], ac_root)

        assert exit_code == 0, (
            f"claim must exit 0 when every target AC is claimed; got {exit_code}."
        )
        for ac_id in ("BO-F7-CLI-001", "BO-F7-CLI-002"):
            actual = _read_work_status(ac_root, ac_id)
            assert actual == "in_progress", (
                f"AC {ac_id} must be in_progress on disk after the real claim "
                f"command (BO-2400f-7). Got: {actual!r}"
            )


def test_claim_through_cli_is_a_status_only_change() -> None:
    # covers: BO-2400f-7
    """The real claim command alters work_status and nothing else.

    Same status-only constraint the unit test asserts, but proven through the
    command the lane runs — so argument parsing and the CLI's own write path
    are inside the proof rather than beside it.
    """
    if not _FAST_LANE_MODULE_OK:
        raise AssertionError("fast_lane module not importable — cannot drive its CLI.")
    with tempfile.TemporaryDirectory() as tmp:
        ac_root = Path(tmp) / "acs"
        ac_root.mkdir(parents=True, exist_ok=True)
        _write_ac(ac_root, "BO-F7-CLI-003", work_status="todo", readiness="reviewed")

        before = _read_all_fields(ac_root, "BO-F7-CLI-003")

        exit_code = _claim_via_cli(["BO-F7-CLI-003"], ac_root)
        assert exit_code == 0, f"claim must exit 0; got {exit_code}."

        after = _read_all_fields(ac_root, "BO-F7-CLI-003")

        for key in before:
            if key == "work_status":
                continue
            assert before[key] == after.get(key), (
                f"Field {key!r} must not change after a claim (status-only change — "
                f"BO-2400f-7). Before: {before[key]!r}, After: {after.get(key)!r}"
            )
        assert after["work_status"] == "in_progress", (
            "work_status must be in_progress on disk after the real claim command."
        )


def test_claim_through_cli_excludes_ac_from_concurrent_ready_scan() -> None:
    # covers: BO-2400f-7
    """An AC claimed via the real command drops out of a concurrent ready scan.

    The on-disk YAML is the shared state between the claim step and any other
    run scanning for work, so a claim made through the CLI must be visible to
    that scanner exactly as one made in-process would be.
    """
    if not _FAST_LANE_MODULE_OK:
        raise AssertionError("fast_lane module not importable — cannot drive its CLI.")
    if not _SELECT_BATCH_IMPORT_OK:
        raise AssertionError("select_batch not importable — cannot run the scan half.")
    with tempfile.TemporaryDirectory() as tmp:
        ac_root = Path(tmp) / "acs"
        ac_root.mkdir(parents=True, exist_ok=True)
        _write_ac(ac_root, "BO-F7-CLI-SCAN-1", work_status="todo", readiness="approved")
        _write_ac(ac_root, "BO-F7-CLI-SCAN-2", work_status="todo", readiness="approved")

        before = select_batch(ac_root=ac_root, limit=10)
        assert "BO-F7-CLI-SCAN-1" in before, (
            "BO-F7-CLI-SCAN-1 must be visible in the ready scan before it is claimed."
        )

        exit_code = _claim_via_cli(["BO-F7-CLI-SCAN-1"], ac_root)
        assert exit_code == 0, f"claim must exit 0; got {exit_code}."

        after = select_batch(ac_root=ac_root, limit=10)
        assert "BO-F7-CLI-SCAN-1" not in after, (
            "A claimed (in_progress) AC must be excluded from the concurrent ready "
            "scan (BO-2400f-7). It should no longer appear as ready."
        )
        assert "BO-F7-CLI-SCAN-2" in after, (
            "The unclaimed todo AC must remain ready after a sibling is claimed."
        )


# DECISION HISTORY
# ================================================================================
# - 2026-09-28 14:00 [python-coder]: Split out of test_bo2400f_lifecycle.py,
#   which had grown past its 400-line check-file-size ratchet limit after this
#   commit added these three tests. No test logic changed — this file's three
#   BO-2400f-7 proof tests, their `_claim_via_cli` helper, and the fixture
#   helpers they need are a verbatim relocation. (#TICKETLESS reason=file-size-ratchet-split)
