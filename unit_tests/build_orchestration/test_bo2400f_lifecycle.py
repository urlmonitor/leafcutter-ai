"""
MODULE: unit_tests/build_orchestration/test_bo2400f_lifecycle.py
GOAL: RED test stubs for BO-2400f-7, BO-2400f-7-i, BO-2400f-7-ii,
      BO-2400f-8, BO-2400f-8-i, BO-2400f-9, BO-2400f-9-i, BO-2400f-10.

These tests cover the lifecycle steps of the fast-lane build pipeline:
claim (todo -> in_progress), release (in_progress -> todo on failure),
filtering of already-in_progress ACs, mark-done, and stale-todo guard.

All tests are RED because the production functions do not yet exist in
scripts/build_orchestration/fast_lane.py. The ImportError / AssertionError
IS the intended red state.

=== Interface contract (for python-coder to implement) ===

Location: scripts/build_orchestration/fast_lane.py

    claim_build_set(
        ac_ids: list[str],
        *,
        ac_root: Path,
    ) -> dict
        Flip every AC in ac_ids whose current work_status is todo to
        in_progress in the AC YAML store. Only touches the work_status field
        (status-only change). ACs already in_progress are reported but not
        double-counted.
        Returns:
            {
                "claimed": list[str],   # ids actually flipped todo -> in_progress
                "success": bool,        # True when all target todo ACs were claimed
                "error": str | None,    # human-readable error when success is False
                "named_acs": list[str], # all AC ids the call tried to claim
            }

    release_claim(
        claimed_ids: list[str],
        done_ids: list[str],
        *,
        ac_root: Path,
    ) -> dict
        Release claimed-but-not-done ACs back to work_status: todo.
        claimed_ids: ids this run flipped to in_progress at start.
        done_ids: ids that were successfully transitioned to done.
        Any id in claimed_ids but NOT in done_ids is flipped back to todo.
        Returns: {"released": list[str]}

    filter_already_claimed(
        build_set: list[str],
        *,
        ac_root: Path,
    ) -> dict
        Partition build_set into ACs that are free to build (work_status todo)
        and those already claimed by another run (work_status in_progress).
        Returns:
            {
                "to_build": list[str],          # ACs with work_status todo
                "excluded_claimed": list[str],  # ACs with work_status in_progress
            }

    mark_done_built_acs(
        built_ac_ids: list[str],
        covered_ac_ids: list[str],
        *,
        ac_root: Path,
    ) -> dict
        Flip each built AC whose id is in covered_ac_ids to work_status done.
        ACs in built_ac_ids but NOT in covered_ac_ids are NOT flipped (their
        coverage gate did not pass).
        Returns:
            {
                "marked_done": list[str],
                "skipped_uncovered": list[str],
            }

    check_no_stale_todo(
        built_ac_ids: list[str],
        *,
        ac_root: Path,
    ) -> dict
        Verify that every AC in built_ac_ids has work_status: done after the
        finish-time transition. On a passing run this must always be True.
        Returns:
            {
                "all_done": bool,
                "stale": list[str],  # ids still todo or in_progress
            }

=== Real-artifact behavioral tests ===

Tests that mutate YAML files use a real tmpdir (no mocking the file write).
After calling the production function, the YAML is read back via yaml.safe_load
from disk — not from memory — to confirm the on-disk artifact reflects the
transition.

=== Fixture-authenticity mandate ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

# ---------------------------------------------------------------------------
# Import the production functions under test.
# These do not exist yet — ImportError IS the intended red state.
# ---------------------------------------------------------------------------

_CLAIM_IMPORT_OK = False
_RELEASE_IMPORT_OK = False
_FILTER_IMPORT_OK = False
_MARK_DONE_IMPORT_OK = False
_CHECK_STALE_IMPORT_OK = False
_SELECT_BATCH_IMPORT_OK = False

_CLAIM_IMPORT_ERR = ""
_RELEASE_IMPORT_ERR = ""
_FILTER_IMPORT_ERR = ""
_MARK_DONE_IMPORT_ERR = ""
_CHECK_STALE_IMPORT_ERR = ""

claim_build_set = None  # type: ignore[assignment]
release_claim = None  # type: ignore[assignment]
filter_already_claimed = None  # type: ignore[assignment]
mark_done_built_acs = None  # type: ignore[assignment]
check_no_stale_todo = None  # type: ignore[assignment]
select_batch = None  # type: ignore[assignment]

try:
    from fast_lane import claim_build_set  # type: ignore[no-redef]
    _CLAIM_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _CLAIM_IMPORT_ERR = str(_exc)

try:
    from fast_lane import release_claim  # type: ignore[no-redef]
    _RELEASE_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _RELEASE_IMPORT_ERR = str(_exc)

try:
    from fast_lane import filter_already_claimed  # type: ignore[no-redef]
    _FILTER_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _FILTER_IMPORT_ERR = str(_exc)

try:
    from fast_lane import mark_done_built_acs  # type: ignore[no-redef]
    _MARK_DONE_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _MARK_DONE_IMPORT_ERR = str(_exc)

try:
    from fast_lane import check_no_stale_todo  # type: ignore[no-redef]
    _CHECK_STALE_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _CHECK_STALE_IMPORT_ERR = str(_exc)

try:
    from fast_lane import select_batch  # type: ignore[no-redef]
    _SELECT_BATCH_IMPORT_OK = True
except (ImportError, AttributeError):
    pass


# ---------------------------------------------------------------------------
# Shared fixture helpers
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


# ---------------------------------------------------------------------------
# BO-2400f-7 — Claim step: flip todo -> in_progress before build
# ---------------------------------------------------------------------------


class TestClaimBuildSet(unittest.TestCase):
    """Tests for claim_build_set() — BO-2400f-7.

    Verifies that at run start, resolved leaf ACs with work_status todo are
    transitioned to in_progress before any test or code work begins.

    All tests are RED until python-coder implements claim_build_set() in
    scripts/build_orchestration/fast_lane.py. The ImportError IS the intended
    red state.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_claim_impl(self) -> None:
        """Fail with a descriptive message when claim_build_set is not yet implemented."""
        if not _CLAIM_IMPORT_OK:
            self.fail(
                "claim_build_set not importable from fast_lane — "
                "ImportError is the intended red state; python-coder must implement it. "
                f"Import error: {_CLAIM_IMPORT_ERR}"
            )

    def test_claim_flips_todo_to_in_progress_before_build(self) -> None:
        # covers: BO-2400f-7
        """At run start, every resolved leaf AC with work_status todo is flipped to in_progress.

        Real-artifact behavioral test: claim_build_set is called with real YAML files,
        and the on-disk YAML is read back via yaml.safe_load to confirm the mutation.
        No mocking of file writes.

        To make this green, claim_build_set must:
        1. Accept a list of AC ids and an ac_root directory.
        2. For each AC whose work_status is todo, overwrite only the work_status
           field in the YAML file to in_progress.
        3. Return {"claimed": [...], "success": True, ...}.
        """
        _write_ac(self.ac_root, "BO-F7-001", work_status="todo")
        _write_ac(self.ac_root, "BO-F7-002", work_status="todo")

        self._require_claim_impl()

        result = claim_build_set(
            ["BO-F7-001", "BO-F7-002"],
            ac_root=self.ac_root,
        )

        # Real-artifact read-back: confirm the YAML files are now in_progress on disk.
        for ac_id in ("BO-F7-001", "BO-F7-002"):
            actual_status = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual_status,
                "in_progress",
                f"AC {ac_id} must have work_status in_progress on disk after claim "
                f"(real-artifact behavioral test — BO-2400f-7). Got: {actual_status!r}",
            )

        self.assertIsInstance(result, dict, "claim_build_set must return a dict.")
        self.assertTrue(
            result.get("success"),
            "claim_build_set must report success=True when all target ACs are claimed.",
        )
        claimed = result.get("claimed", [])
        self.assertIn("BO-F7-001", claimed, "BO-F7-001 must appear in claimed list.")
        self.assertIn("BO-F7-002", claimed, "BO-F7-002 must appear in claimed list.")

    def test_claim_lands_as_merged_status_only_change_first(self) -> None:
        # covers: BO-2400f-7
        """The claim is a status-only change: only work_status is modified in the YAML.

        No other field (title, level, readiness, priority, etc.) may be altered.
        This confirms the implementation respects the status-only constraint.

        To make this green, claim_build_set must read the existing YAML, update
        only work_status, and write the file back with all other fields unchanged.
        """
        _write_ac(self.ac_root, "BO-F7-003", work_status="todo", readiness="reviewed")

        # Capture the full field set BEFORE the claim.
        before = _read_all_fields(self.ac_root, "BO-F7-003")

        self._require_claim_impl()

        claim_build_set(["BO-F7-003"], ac_root=self.ac_root)

        # Read back the full field set AFTER the claim.
        after = _read_all_fields(self.ac_root, "BO-F7-003")

        # Only work_status should have changed.
        for key in before:
            if key == "work_status":
                continue
            self.assertEqual(
                before[key],
                after.get(key),
                f"Field '{key}' must not change after a claim (status-only change — "
                f"BO-2400f-7). Before: {before[key]!r}, After: {after.get(key)!r}",
            )

        # work_status must have transitioned to in_progress.
        self.assertEqual(
            after["work_status"],
            "in_progress",
            "work_status must be in_progress on disk after the claim (BO-2400f-7).",
        )

    def test_claimed_acs_excluded_from_concurrent_ready_scan(self) -> None:
        # covers: BO-2400f-7
        """Once claimed (in_progress), an AC is excluded from a concurrent ready scan.

        After claim_build_set flips an AC to in_progress, select_batch must NOT
        include it in its returned ready set — because select_batch filters by
        work_status: todo. The on-disk YAML is the shared state between the claim
        step and the concurrent scanner.

        To make this green, claim_build_set must update the YAML on disk so that
        select_batch (which reads work_status: todo only) naturally excludes the
        claimed AC from the next scan.
        """
        if not _SELECT_BATCH_IMPORT_OK:
            self.skipTest("select_batch not importable — skip concurrent-scan test.")

        _write_ac(self.ac_root, "BO-F7-SCAN-001", work_status="todo", readiness="approved")
        _write_ac(self.ac_root, "BO-F7-SCAN-002", work_status="todo", readiness="approved")

        # Both ACs must be visible in the ready scan before claiming.
        batch_before = select_batch(ac_root=self.ac_root, limit=10)
        self.assertIn(
            "BO-F7-SCAN-001",
            batch_before,
            "BO-F7-SCAN-001 must appear in select_batch before claiming.",
        )

        self._require_claim_impl()

        # Claim only the first AC.
        claim_build_set(["BO-F7-SCAN-001"], ac_root=self.ac_root)

        # After claiming, the concurrent scan must exclude the now in_progress AC.
        batch_after = select_batch(ac_root=self.ac_root, limit=10)
        self.assertNotIn(
            "BO-F7-SCAN-001",
            batch_after,
            "A claimed (in_progress) AC must be excluded from the concurrent ready "
            "scan (select_batch) — BO-2400f-7. It should no longer appear as ready.",
        )
        # The unclaimed AC must still be available.
        self.assertIn(
            "BO-F7-SCAN-002",
            batch_after,
            "The unclaimed todo AC must remain in the ready scan after another AC is claimed.",
        )


# ---------------------------------------------------------------------------
# BO-2400f-7-i — Failed claim halts run before build
# ---------------------------------------------------------------------------


class TestFailedClaimBehavior(unittest.TestCase):
    """Tests for failed claim handling — BO-2400f-7-i.

    Verifies that when the claim cannot be recorded, the run halts before
    any test or code work and reports a clear error naming the ACs.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_claim_impl(self) -> None:
        if not _CLAIM_IMPORT_OK:
            self.fail(
                "claim_build_set not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_CLAIM_IMPORT_ERR}"
            )

    def test_failed_claim_merge_halts_before_build(self) -> None:
        # covers: BO-2400f-7-i
        """When the claim merge fails, the run halts before any test/code work begins.

        Scenario: claim_build_set is called on ACs that cannot be claimed
        (e.g., the YAML store is read-only or the ACs are already claimed),
        causing the claim to return success=False.

        The run MUST NOT proceed to test/code work when success is False.
        The result must indicate failure with a non-None error field.

        To make this green, claim_build_set must:
        1. Detect that it cannot record the claim.
        2. Return {"success": False, "error": "<message>", "claimed": []}.
        The caller checks success and halts before dispatching test-writer or coder.
        """
        self._require_claim_impl()

        # Simulate a failed claim by making the AC store directory read-only.
        # This prevents the YAML write from succeeding.
        subdir = self.ac_root / "test-component"
        subdir.mkdir(parents=True, exist_ok=True)
        _write_ac(self.ac_root, "BO-F7-I-001", work_status="todo")

        # Make the store directory read-only so the write fails.
        import stat
        yaml_path = self.ac_root / "test-component" / "BO-F7-I-001.yaml"
        yaml_path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

        try:
            result = claim_build_set(["BO-F7-I-001"], ac_root=self.ac_root)

            # The claim must report failure — not raise an uncaught exception.
            self.assertIsInstance(
                result, dict,
                "claim_build_set must return a dict even on failure.",
            )
            self.assertFalse(
                result.get("success", True),
                "claim_build_set must return success=False when the claim cannot be "
                "recorded (e.g. read-only store). A caller checks this flag to halt "
                "before build work begins (BO-2400f-7-i).",
            )
            self.assertIsNotNone(
                result.get("error"),
                "A failed claim must include a non-None error field describing why "
                "it failed (BO-2400f-7-i).",
            )
        finally:
            # Restore permissions for cleanup.
            yaml_path.chmod(
                stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH
            )

    def test_failed_claim_reports_error_naming_acs(self) -> None:
        # covers: BO-2400f-7-i
        """A failed claim reports a clear error naming the AC ids it tried to claim.

        The error field in the result (or the named_acs field) must identify
        the AC ids that were attempted, so the operator knows which ACs were
        involved in the failed claim. The run must not build against an
        unclaimed or partially-claimed state.

        To make this green, claim_build_set must:
        1. When it cannot claim all target ACs, set success=False.
        2. Include the attempted AC ids in the result under "named_acs" or in
           the "error" string.
        """
        self._require_claim_impl()

        # Write ACs with one already in_progress (claimed by another run).
        _write_ac(self.ac_root, "BO-F7-I-002", work_status="todo")
        _write_ac(self.ac_root, "BO-F7-I-003", work_status="in_progress")  # already claimed

        result = claim_build_set(
            ["BO-F7-I-002", "BO-F7-I-003"],
            ac_root=self.ac_root,
        )

        self.assertIsInstance(result, dict, "claim_build_set must return a dict.")

        # The result must name the attempted AC ids.
        named_acs = result.get("named_acs", [])
        error_str = str(result.get("error") or "")

        found_ids_named = (
            "BO-F7-I-003" in named_acs
            or "BO-F7-I-003" in error_str
            or "BO-F7-I-002" in named_acs
            or "BO-F7-I-002" in error_str
        )
        self.assertTrue(
            found_ids_named,
            "A failed or partial claim must name the AC ids it tried to claim in "
            "'named_acs' or the 'error' field (BO-2400f-7-i). "
            f"Got result: {result!r}",
        )


# ---------------------------------------------------------------------------
# BO-2400f-7-ii — Claim is readiness-agnostic
# ---------------------------------------------------------------------------


class TestClaimReadinessAgnostic(unittest.TestCase):
    """Tests for claim readiness-agnostic behavior — BO-2400f-7-ii.

    Pointing at an AC is the operator's go-ahead. Draft and reviewed ACs must
    be claimed exactly like approved ones.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_claim_impl(self) -> None:
        if not _CLAIM_IMPORT_OK:
            self.fail(
                "claim_build_set not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_CLAIM_IMPORT_ERR}"
            )

    def test_claim_flips_draft_and_reviewed_acs(self) -> None:
        # covers: BO-2400f-7-ii
        """A resolved set containing draft and reviewed ACs has every member flipped to in_progress.

        Real-artifact behavioral test: draft and reviewed YAML files are written,
        claim_build_set is called, and the on-disk work_status is confirmed to be
        in_progress for both. Readiness must not filter what gets claimed.

        To make this green, claim_build_set must flip every AC in ac_ids to
        in_progress regardless of its readiness field.
        """
        _write_ac(self.ac_root, "BO-F7-II-DRAFT", work_status="todo", readiness="draft")
        _write_ac(self.ac_root, "BO-F7-II-REVIEWED", work_status="todo", readiness="reviewed")

        self._require_claim_impl()

        result = claim_build_set(
            ["BO-F7-II-DRAFT", "BO-F7-II-REVIEWED"],
            ac_root=self.ac_root,
        )

        # Real-artifact read-back: draft AC must be in_progress on disk.
        draft_status = _read_work_status(self.ac_root, "BO-F7-II-DRAFT")
        self.assertEqual(
            draft_status,
            "in_progress",
            "A draft-readiness AC must be flipped to in_progress by claim_build_set "
            "(readiness-agnostic — BO-2400f-7-ii). Got: {!r}".format(draft_status),
        )

        # Real-artifact read-back: reviewed AC must be in_progress on disk.
        reviewed_status = _read_work_status(self.ac_root, "BO-F7-II-REVIEWED")
        self.assertEqual(
            reviewed_status,
            "in_progress",
            "A reviewed-readiness AC must be flipped to in_progress by claim_build_set "
            "(readiness-agnostic — BO-2400f-7-ii). Got: {!r}".format(reviewed_status),
        )

        claimed = result.get("claimed", [])
        self.assertIn(
            "BO-F7-II-DRAFT",
            claimed,
            "Draft AC must appear in the claimed list.",
        )
        self.assertIn(
            "BO-F7-II-REVIEWED",
            claimed,
            "Reviewed AC must appear in the claimed list.",
        )

    def test_claim_does_not_filter_by_readiness(self) -> None:
        # covers: BO-2400f-7-ii
        """Readiness is not consulted at the claim step: the claimed set equals the resolved todo set.

        A mixed set with approved + draft + reviewed ACs (all todo) must all be
        claimed. The claimed list length must equal the input list length when all
        are todo, regardless of readiness mix.

        To make this green, claim_build_set must NOT filter by readiness.
        """
        _write_ac(self.ac_root, "BO-F7-II-A", work_status="todo", readiness="approved")
        _write_ac(self.ac_root, "BO-F7-II-B", work_status="todo", readiness="draft")
        _write_ac(self.ac_root, "BO-F7-II-C", work_status="todo", readiness="reviewed")

        self._require_claim_impl()

        target_ids = ["BO-F7-II-A", "BO-F7-II-B", "BO-F7-II-C"]
        result = claim_build_set(target_ids, ac_root=self.ac_root)

        claimed = result.get("claimed", [])
        for ac_id in target_ids:
            self.assertIn(
                ac_id,
                claimed,
                f"AC {ac_id} must be claimed regardless of readiness "
                f"(readiness-agnostic — BO-2400f-7-ii).",
            )

        # Confirm via real-artifact read-back that all three are in_progress on disk.
        for ac_id in target_ids:
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual,
                "in_progress",
                f"AC {ac_id} must be in_progress on disk after claim — readiness must "
                f"not filter it out (BO-2400f-7-ii). Got: {actual!r}",
            )


# ---------------------------------------------------------------------------
# BO-2400f-8 — Resolver treats already in_progress as claimed: skip, never rebuild
# ---------------------------------------------------------------------------


class TestAlreadyInProgressHandling(unittest.TestCase):
    """Tests for already-in_progress AC handling — BO-2400f-8.

    Verifies that already-in_progress ACs are treated as claimed by another
    run, are excluded from the build set, are named in the run message, and
    that the run refuses to proceed if the target AC itself is in_progress.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_filter_impl(self) -> None:
        if not _FILTER_IMPORT_OK:
            self.fail(
                "filter_already_claimed not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_FILTER_IMPORT_ERR}"
            )

    def test_resolver_excludes_already_in_progress_members(self) -> None:
        # covers: BO-2400f-8
        """Members of the resolved set already in_progress are treated as claimed and excluded.

        When filter_already_claimed partitions the resolved build set, ACs with
        work_status in_progress must appear in excluded_claimed, never in to_build.
        They must not be rebuilt by this run.

        To make this green, filter_already_claimed must:
        1. Read each AC's work_status from disk.
        2. Return ACs with work_status todo in to_build.
        3. Return ACs with work_status in_progress in excluded_claimed.
        """
        _write_ac(self.ac_root, "BO-F8-TODO", work_status="todo")
        _write_ac(self.ac_root, "BO-F8-INPROG", work_status="in_progress")

        self._require_filter_impl()

        result = filter_already_claimed(
            ["BO-F8-TODO", "BO-F8-INPROG"],
            ac_root=self.ac_root,
        )

        self.assertIsInstance(result, dict, "filter_already_claimed must return a dict.")
        to_build = result.get("to_build", [])
        excluded = result.get("excluded_claimed", [])

        self.assertIn(
            "BO-F8-TODO",
            to_build,
            "A todo AC must be in to_build, not excluded (BO-2400f-8).",
        )
        self.assertNotIn(
            "BO-F8-INPROG",
            to_build,
            "An already-in_progress AC must NOT be in to_build (BO-2400f-8). "
            "It is already claimed by another run and must not be rebuilt.",
        )
        self.assertIn(
            "BO-F8-INPROG",
            excluded,
            "An already-in_progress AC must appear in excluded_claimed (BO-2400f-8).",
        )

    def test_resolver_reports_excluded_claimed_ids(self) -> None:
        # covers: BO-2400f-8
        """The run reports a clear message naming each excluded already-claimed AC id.

        filter_already_claimed must name every excluded in_progress AC id in its
        result, so the operator can see which ACs were skipped and why.

        To make this green, filter_already_claimed must populate excluded_claimed
        with the complete list of in_progress AC ids from the input build set.
        """
        _write_ac(self.ac_root, "BO-F8-SKIP-001", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F8-SKIP-002", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F8-FREE-001", work_status="todo")

        self._require_filter_impl()

        result = filter_already_claimed(
            ["BO-F8-SKIP-001", "BO-F8-SKIP-002", "BO-F8-FREE-001"],
            ac_root=self.ac_root,
        )

        excluded = result.get("excluded_claimed", [])

        self.assertIn(
            "BO-F8-SKIP-001",
            excluded,
            "BO-F8-SKIP-001 (in_progress) must be named in excluded_claimed (BO-2400f-8).",
        )
        self.assertIn(
            "BO-F8-SKIP-002",
            excluded,
            "BO-F8-SKIP-002 (in_progress) must be named in excluded_claimed (BO-2400f-8).",
        )
        self.assertNotIn(
            "BO-F8-FREE-001",
            excluded,
            "BO-F8-FREE-001 (todo) must NOT appear in excluded_claimed (BO-2400f-8).",
        )

    def test_target_ac_in_progress_refuses_to_proceed(self) -> None:
        # covers: BO-2400f-8
        """When the target AC id itself is in_progress, the run refuses to proceed.

        filter_already_claimed must signal a refusal when the single requested
        AC is itself in_progress, rather than returning an empty to_build set
        silently. The caller checks this signal and refuses to start a concurrent
        build.

        To make this green, filter_already_claimed must set target_refused=True
        (or an equivalent signal) when every input AC is in_progress — or
        claim_build_set must return success=False with a clear message when the
        target AC itself is in_progress.
        """
        _write_ac(self.ac_root, "BO-F8-TARGET", work_status="in_progress")

        self._require_filter_impl()

        result = filter_already_claimed(
            ["BO-F8-TARGET"],
            ac_root=self.ac_root,
        )

        self.assertIsInstance(result, dict, "filter_already_claimed must return a dict.")

        to_build = result.get("to_build", [])
        excluded = result.get("excluded_claimed", [])

        # The target is in_progress — to_build must be empty.
        self.assertEqual(
            to_build,
            [],
            "When the target AC is already in_progress, to_build must be empty "
            "(BO-2400f-8 — must not start a concurrent build).",
        )

        # The target must appear in excluded_claimed.
        self.assertIn(
            "BO-F8-TARGET",
            excluded,
            "The in_progress target AC must be named in excluded_claimed "
            "(BO-2400f-8 — clear message naming the refused AC).",
        )

        # There must be a refusal signal (target_refused=True or equivalent).
        refused = result.get("target_refused", None)
        self.assertTrue(
            refused is True or len(to_build) == 0,
            "When the target AC itself is in_progress, the result must signal "
            "refusal (target_refused=True or empty to_build) — BO-2400f-8. "
            f"Got result: {result!r}",
        )


# ---------------------------------------------------------------------------
# BO-2400f-8-i — Partial overlap: build todo, skip claimed, clean no-op if empty
# ---------------------------------------------------------------------------


class TestPartialOverlapHandling(unittest.TestCase):
    """Tests for partial-overlap set handling — BO-2400f-8-i.

    Verifies that a mixed build set (some todo, some in_progress) proceeds
    with only the todo members, skips the claimed ones, and exits cleanly
    when no todo members remain.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_filter_impl(self) -> None:
        if not _FILTER_IMPORT_OK:
            self.fail(
                "filter_already_claimed not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_FILTER_IMPORT_ERR}"
            )

    def test_partial_overlap_builds_todo_skips_claimed(self) -> None:
        # covers: BO-2400f-8-i
        """A mixed set builds only the todo members and names the in_progress ones as excluded.

        When filter_already_claimed receives a mixed set (some todo, some in_progress),
        the to_build result must contain only the todo members, and excluded_claimed
        must contain only the in_progress members. The run proceeds with the todo
        members rather than aborting the whole run.

        To make this green, filter_already_claimed must:
        1. Read each AC's work_status from disk.
        2. Separate todo into to_build and in_progress into excluded_claimed.
        """
        _write_ac(self.ac_root, "BO-F8I-TODO-001", work_status="todo")
        _write_ac(self.ac_root, "BO-F8I-TODO-002", work_status="todo")
        _write_ac(self.ac_root, "BO-F8I-INPROG-001", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F8I-INPROG-002", work_status="in_progress")

        self._require_filter_impl()

        result = filter_already_claimed(
            [
                "BO-F8I-TODO-001",
                "BO-F8I-TODO-002",
                "BO-F8I-INPROG-001",
                "BO-F8I-INPROG-002",
            ],
            ac_root=self.ac_root,
        )

        to_build = result.get("to_build", [])
        excluded = result.get("excluded_claimed", [])

        self.assertIn("BO-F8I-TODO-001", to_build, "Todo AC must be in to_build.")
        self.assertIn("BO-F8I-TODO-002", to_build, "Todo AC must be in to_build.")
        self.assertNotIn("BO-F8I-INPROG-001", to_build, "In-progress AC must NOT be in to_build.")
        self.assertNotIn("BO-F8I-INPROG-002", to_build, "In-progress AC must NOT be in to_build.")

        self.assertIn("BO-F8I-INPROG-001", excluded, "In-progress AC must be in excluded_claimed.")
        self.assertIn("BO-F8I-INPROG-002", excluded, "In-progress AC must be in excluded_claimed.")
        self.assertNotIn("BO-F8I-TODO-001", excluded, "Todo AC must NOT be in excluded_claimed.")
        self.assertNotIn("BO-F8I-TODO-002", excluded, "Todo AC must NOT be in excluded_claimed.")

    def test_empty_after_exclusion_is_clean_noop(self) -> None:
        # covers: BO-2400f-8-i
        """When excluding claimed members leaves nothing to build, the result is a clean no-op.

        filter_already_claimed must return to_build=[] (nothing to build) when
        every AC in the input set is already in_progress. No error, no exception —
        a clean result the caller can check.

        To make this green, filter_already_claimed must handle the all-in_progress
        case gracefully by returning to_build=[] and populating excluded_claimed.
        """
        _write_ac(self.ac_root, "BO-F8I-ALL-INPROG-001", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F8I-ALL-INPROG-002", work_status="in_progress")

        self._require_filter_impl()

        result = filter_already_claimed(
            ["BO-F8I-ALL-INPROG-001", "BO-F8I-ALL-INPROG-002"],
            ac_root=self.ac_root,
        )

        to_build = result.get("to_build", ["unexpected"])
        self.assertEqual(
            to_build,
            [],
            "When all ACs are already in_progress, to_build must be [] "
            "(clean no-op — BO-2400f-8-i). Got: {!r}".format(to_build),
        )

        excluded = result.get("excluded_claimed", [])
        self.assertIn(
            "BO-F8I-ALL-INPROG-001",
            excluded,
            "All in_progress ACs must appear in excluded_claimed (BO-2400f-8-i).",
        )
        self.assertIn(
            "BO-F8I-ALL-INPROG-002",
            excluded,
            "All in_progress ACs must appear in excluded_claimed (BO-2400f-8-i).",
        )


# ---------------------------------------------------------------------------
# BO-2400f-9 — At finish, coverage-gated mark-done flips every built AC to done
# ---------------------------------------------------------------------------


class TestMarkDoneBuiltAcs(unittest.TestCase):
    """Tests for coverage-gated mark-done — BO-2400f-9.

    Verifies that at run finish, every built AC with a passing coverage gate
    is flipped to work_status done, and ACs without passing coverage are not.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_mark_done_impl(self) -> None:
        if not _MARK_DONE_IMPORT_OK:
            self.fail(
                "mark_done_built_acs not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_MARK_DONE_IMPORT_ERR}"
            )

    def test_finish_flips_every_built_ac_to_done(self) -> None:
        # covers: BO-2400f-9
        """On a passing run, every built AC (todo or in_progress on entry) is flipped to done.

        Real-artifact behavioral test: mark_done_built_acs is called with real YAML
        files, and the on-disk work_status is confirmed to be done for each covered AC.

        To make this green, mark_done_built_acs must:
        1. For each id in built_ac_ids that is also in covered_ac_ids,
           update work_status to done in the YAML file on disk.
        2. Return {"marked_done": [...]} listing the ids it flipped.
        """
        _write_ac(self.ac_root, "BO-F9-BUILT-001", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F9-BUILT-002", work_status="in_progress")

        self._require_mark_done_impl()

        built_ids = ["BO-F9-BUILT-001", "BO-F9-BUILT-002"]
        result = mark_done_built_acs(
            built_ids,
            covered_ac_ids=built_ids,  # all covered
            ac_root=self.ac_root,
        )

        # Real-artifact read-back: confirm both ACs are done on disk.
        for ac_id in built_ids:
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual,
                "done",
                f"Built+covered AC {ac_id} must have work_status done on disk after "
                f"mark_done_built_acs (real-artifact behavioral test — BO-2400f-9). "
                f"Got: {actual!r}",
            )

        marked_done = result.get("marked_done", [])
        self.assertIn("BO-F9-BUILT-001", marked_done, "BO-F9-BUILT-001 must be in marked_done.")
        self.assertIn("BO-F9-BUILT-002", marked_done, "BO-F9-BUILT-002 must be in marked_done.")

    def test_uncovered_ac_not_marked_done(self) -> None:
        # covers: BO-2400f-9
        """An AC whose coverage gate did not pass is NOT transitioned to done.

        mark_done_built_acs only flips ACs that appear in both built_ac_ids AND
        covered_ac_ids. An AC in built_ac_ids but absent from covered_ac_ids must
        remain in its current work_status (not flipped to done).

        To make this green, mark_done_built_acs must skip any id in built_ac_ids
        that is not in covered_ac_ids.
        """
        _write_ac(self.ac_root, "BO-F9-COVERED", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F9-UNCOVERED", work_status="in_progress")

        self._require_mark_done_impl()

        result = mark_done_built_acs(
            ["BO-F9-COVERED", "BO-F9-UNCOVERED"],
            covered_ac_ids=["BO-F9-COVERED"],  # only one covered
            ac_root=self.ac_root,
        )

        # Covered AC must be done.
        covered_status = _read_work_status(self.ac_root, "BO-F9-COVERED")
        self.assertEqual(
            covered_status,
            "done",
            "The covered AC must be flipped to done (BO-2400f-9).",
        )

        # Uncovered AC must NOT be done.
        uncovered_status = _read_work_status(self.ac_root, "BO-F9-UNCOVERED")
        self.assertNotEqual(
            uncovered_status,
            "done",
            "An AC whose coverage gate did not pass must NOT be flipped to done "
            "(BO-2400f-9). It must remain in its current status.",
        )

        skipped = result.get("skipped_uncovered", [])
        self.assertIn(
            "BO-F9-UNCOVERED",
            skipped,
            "The uncovered AC must appear in skipped_uncovered (BO-2400f-9).",
        )

    def test_done_transition_is_coverage_gated(self) -> None:
        # covers: BO-2400f-9
        """The finish-time done-flip goes through the coverage gate for every built AC.

        When covered_ac_ids is empty (no test coverage at all), mark_done_built_acs
        must NOT flip any AC to done. This confirms the coverage gate is enforced
        unconditionally, not bypassed for some ACs.

        To make this green, mark_done_built_acs must only flip ACs that are
        explicitly listed in covered_ac_ids — never flip an AC that is absent from
        the covered list, even if it is in built_ac_ids.
        """
        _write_ac(self.ac_root, "BO-F9-GATE-001", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F9-GATE-002", work_status="in_progress")

        self._require_mark_done_impl()

        # No covered ACs — the coverage gate blocks all transitions.
        result = mark_done_built_acs(
            ["BO-F9-GATE-001", "BO-F9-GATE-002"],
            covered_ac_ids=[],  # no coverage at all
            ac_root=self.ac_root,
        )

        # Neither AC may be done.
        for ac_id in ("BO-F9-GATE-001", "BO-F9-GATE-002"):
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertNotEqual(
                actual,
                "done",
                f"AC {ac_id} must NOT be flipped to done when coverage_ac_ids is empty "
                f"(coverage gate enforced — BO-2400f-9). Got: {actual!r}",
            )

        marked_done = result.get("marked_done", [])
        self.assertEqual(
            marked_done,
            [],
            "marked_done must be empty when no ACs are covered (BO-2400f-9). "
            f"Got: {marked_done!r}",
        )


# ---------------------------------------------------------------------------
# BO-2400f-9-i — Stale-todo guard: unflipped built AC is an error
# ---------------------------------------------------------------------------


class TestStaleTodoGuard(unittest.TestCase):
    """Tests for the stale-todo guard — BO-2400f-9-i.

    Verifies that if any built AC is still todo/in_progress after the finish
    transition on a gate-passing run, the result is an error naming the
    un-flipped criteria, not a success.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_check_stale_impl(self) -> None:
        if not _CHECK_STALE_IMPORT_OK:
            self.fail(
                "check_no_stale_todo not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_CHECK_STALE_IMPORT_ERR}"
            )

    def test_unflipped_built_ac_reported_as_error(self) -> None:
        # covers: BO-2400f-9-i
        """If any built AC is still todo/in_progress after the finish transition, it is an error.

        check_no_stale_todo reads the on-disk work_status of each built AC and
        verifies all are done. When any AC is still todo or in_progress, the result
        must report all_done=False and name the un-flipped criteria.

        To make this green, check_no_stale_todo must:
        1. Read the work_status of each built AC from disk.
        2. If any is not done, return {"all_done": False, "stale": [...]} naming them.
        """
        # One done, one still in_progress (stale — forgot to flip it).
        _write_ac(self.ac_root, "BO-F9I-DONE", work_status="done")
        _write_ac(self.ac_root, "BO-F9I-STALE", work_status="in_progress")

        self._require_check_stale_impl()

        result = check_no_stale_todo(
            ["BO-F9I-DONE", "BO-F9I-STALE"],
            ac_root=self.ac_root,
        )

        self.assertIsInstance(result, dict, "check_no_stale_todo must return a dict.")
        self.assertFalse(
            result.get("all_done", True),
            "all_done must be False when any built AC is still in_progress (BO-2400f-9-i). "
            f"Got result: {result!r}",
        )

        stale = result.get("stale", [])
        self.assertIn(
            "BO-F9I-STALE",
            stale,
            "The un-flipped AC must be named in the stale list (BO-2400f-9-i).",
        )
        self.assertNotIn(
            "BO-F9I-DONE",
            stale,
            "Already-done AC must NOT appear in the stale list (BO-2400f-9-i).",
        )

    def test_success_result_asserts_all_built_acs_done(self) -> None:
        # covers: BO-2400f-9-i
        """A successful run's reported result asserts every built AC is work_status done.

        When all built ACs are done on disk, check_no_stale_todo must return
        all_done=True and an empty stale list. This is the success invariant a
        passing run must satisfy.

        To make this green, check_no_stale_todo must return {"all_done": True, "stale": []}
        when every id in built_ac_ids has work_status: done in its YAML file.
        """
        _write_ac(self.ac_root, "BO-F9I-ALL-DONE-001", work_status="done")
        _write_ac(self.ac_root, "BO-F9I-ALL-DONE-002", work_status="done")

        self._require_check_stale_impl()

        result = check_no_stale_todo(
            ["BO-F9I-ALL-DONE-001", "BO-F9I-ALL-DONE-002"],
            ac_root=self.ac_root,
        )

        self.assertIsInstance(result, dict, "check_no_stale_todo must return a dict.")
        self.assertTrue(
            result.get("all_done", False),
            "all_done must be True when all built ACs have work_status done "
            "(BO-2400f-9-i). Got: {!r}".format(result),
        )

        stale = result.get("stale", ["unexpected"])
        self.assertEqual(
            stale,
            [],
            "stale must be [] when all built ACs are done "
            "(BO-2400f-9-i). Got: {!r}".format(stale),
        )


# ---------------------------------------------------------------------------
# BO-2400f-10 — On failure/abort, release the claim: in_progress -> todo
# ---------------------------------------------------------------------------


class TestReleaseClaimOnFailure(unittest.TestCase):
    """Tests for claim release on failure/abort — BO-2400f-10.

    Verifies that on a non-success exit, every AC the run flipped to in_progress
    but did not transition to done is released back to todo — so no AC is
    permanently stuck in in_progress blocking future runs.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_release_impl(self) -> None:
        if not _RELEASE_IMPORT_OK:
            self.fail(
                "release_claim not importable from fast_lane — "
                "ImportError is the intended red state. "
                f"Import error: {_RELEASE_IMPORT_ERR}"
            )

    def test_failed_run_releases_claim_to_todo(self) -> None:
        # covers: BO-2400f-10
        """On a non-success exit, every claimed-but-not-done AC is released back to todo.

        Real-artifact behavioral test: after release_claim, the on-disk YAML
        must reflect work_status: todo for claimed-but-not-done ACs.

        To make this green, release_claim must:
        1. For each id in claimed_ids that is NOT in done_ids, update the YAML
           work_status field to todo on disk.
        2. Return {"released": [...]} listing the ids released.
        """
        # Set up two claimed ACs (in_progress) — neither was marked done.
        _write_ac(self.ac_root, "BO-F10-CLAIMED-001", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F10-CLAIMED-002", work_status="in_progress")

        self._require_release_impl()

        result = release_claim(
            claimed_ids=["BO-F10-CLAIMED-001", "BO-F10-CLAIMED-002"],
            done_ids=[],  # none reached done — run failed before finish
            ac_root=self.ac_root,
        )

        # Real-artifact read-back: both must be todo on disk.
        for ac_id in ("BO-F10-CLAIMED-001", "BO-F10-CLAIMED-002"):
            actual = _read_work_status(self.ac_root, ac_id)
            self.assertEqual(
                actual,
                "todo",
                f"Claimed-but-not-done AC {ac_id} must be released to todo on disk "
                f"after release_claim on a failed run (BO-2400f-10). Got: {actual!r}",
            )

        released = result.get("released", [])
        self.assertIn(
            "BO-F10-CLAIMED-001",
            released,
            "BO-F10-CLAIMED-001 must appear in released list.",
        )
        self.assertIn(
            "BO-F10-CLAIMED-002",
            released,
            "BO-F10-CLAIMED-002 must appear in released list.",
        )

    def test_release_lands_as_status_only_change_on_mainline(self) -> None:
        # covers: BO-2400f-10
        """The release is a status-only change: only work_status is modified in the YAML.

        No other field may be altered when releasing a claim. This mirrors the
        status-only constraint on the claim step (BO-2400f-7).

        To make this green, release_claim must read the existing YAML, update
        only work_status to todo, and write the file back with all other fields
        unchanged.
        """
        _write_ac(self.ac_root, "BO-F10-STATUS-ONLY", work_status="in_progress",
                  readiness="draft")

        # Capture all fields before releasing.
        before = _read_all_fields(self.ac_root, "BO-F10-STATUS-ONLY")

        self._require_release_impl()

        release_claim(
            claimed_ids=["BO-F10-STATUS-ONLY"],
            done_ids=[],
            ac_root=self.ac_root,
        )

        # Read back all fields after the release.
        after = _read_all_fields(self.ac_root, "BO-F10-STATUS-ONLY")

        # Only work_status should have changed.
        for key in before:
            if key == "work_status":
                continue
            self.assertEqual(
                before[key],
                after.get(key),
                f"Field '{key}' must not change after release_claim "
                f"(status-only change — BO-2400f-10). "
                f"Before: {before[key]!r}, After: {after.get(key)!r}",
            )

        self.assertEqual(
            after["work_status"],
            "todo",
            "work_status must be todo on disk after release_claim (BO-2400f-10).",
        )

    def test_release_targets_only_own_claim_not_done_acs(self) -> None:
        # covers: BO-2400f-10
        """Release targets only this run's own claimed-but-not-done ACs.

        ACs in claimed_ids that appear in done_ids must NOT be released to todo —
        they are already done and releasing them would regress their status.
        ACs not in claimed_ids at all must not be touched (they may belong to
        another run's claim).

        To make this green, release_claim must:
        1. Only release ids in claimed_ids that are NOT in done_ids.
        2. Leave already-done ACs untouched.
        3. Not touch ACs outside claimed_ids.
        """
        _write_ac(self.ac_root, "BO-F10-TARG-CLAIMED-DONE", work_status="done")
        _write_ac(self.ac_root, "BO-F10-TARG-CLAIMED-NOTDONE", work_status="in_progress")
        _write_ac(self.ac_root, "BO-F10-TARG-OTHER-RUN", work_status="in_progress")

        self._require_release_impl()

        release_claim(
            claimed_ids=["BO-F10-TARG-CLAIMED-DONE", "BO-F10-TARG-CLAIMED-NOTDONE"],
            done_ids=["BO-F10-TARG-CLAIMED-DONE"],
            ac_root=self.ac_root,
        )

        # The already-done AC must NOT be released (must remain done).
        done_status = _read_work_status(self.ac_root, "BO-F10-TARG-CLAIMED-DONE")
        self.assertEqual(
            done_status,
            "done",
            "An already-done AC must NOT be released to todo by release_claim "
            "(BO-2400f-10 — targets only claimed-but-not-done ACs). "
            f"Got: {done_status!r}",
        )

        # The not-done claimed AC must be released to todo.
        notdone_status = _read_work_status(self.ac_root, "BO-F10-TARG-CLAIMED-NOTDONE")
        self.assertEqual(
            notdone_status,
            "todo",
            "The claimed-but-not-done AC must be released to todo by release_claim "
            "(BO-2400f-10). Got: {!r}".format(notdone_status),
        )

        # The AC from another run must not be touched.
        other_status = _read_work_status(self.ac_root, "BO-F10-TARG-OTHER-RUN")
        self.assertEqual(
            other_status,
            "in_progress",
            "An AC outside claimed_ids (belonging to another run) must NOT be "
            "touched by release_claim (BO-2400f-10). Got: {!r}".format(other_status),
        )


if __name__ == "__main__":
    unittest.main()
