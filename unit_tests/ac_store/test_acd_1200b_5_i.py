"""
MODULE: test_acd_1200b_5_i
GOAL: Unit tests for ACD-1200b-5-i — the approval mechanism must leave
      already-approved and non-reviewed (e.g. draft) leaves UNCHANGED.
BUSINESS CONTEXT: Verifies that scripts/ac_store/approve_acs.py correctly skips
      already-approved leaves (idempotent no-op) and draft leaves (below the
      reviewed threshold), while only promoting reviewed leaves to approved.
ARCHITECTURE: Tests write real YAML files in a TemporaryDirectory; no mocks.
      Stdout and stderr are captured via contextlib.redirect_stdout/redirect_stderr
      so that the reporting behaviour (promoted vs. no-op vs. skipped) is asserted
      directly against the text emitted by approve_acs.

TICKET: TICKET-20260720-ACD-1200b-5-i.md
COVERS: ACD-1200b-5-i
"""

from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# Import the public API and the internal helpers under test.
# If approve_acs does not yet exist, the tests fail with ImportError — the
# intended red state. If the module exists but lacks a function, the test
# fails with AttributeError. Both are valid red states.
from approve_acs import approve_acs  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — identical layout to the sibling file (test_acd_1200b_5.py)
# ---------------------------------------------------------------------------


def _write_goal_ac(
    ac_root: Path,
    goal_id: str,
    covered_by: list[str],
) -> Path:
    """Write a minimal goal AC YAML whose covered_by field lists leaf children."""
    subdir = ac_root / "ac-driven-dev" / "ACD-test-goals"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{goal_id}.yaml"
    data: dict = {
        "id": goal_id,
        "title": f"Goal AC {goal_id}",
        "level": "L1",
        "status": "active",
        "work_status": "todo",
        "readiness": "approved",
        "covered_by": covered_by,
        "amended_by": [],
    }
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")
    return path


def _write_leaf_ac(
    ac_root: Path,
    ac_id: str,
    readiness: str = "reviewed",
    extra_fields: dict | None = None,
) -> Path:
    """Write a minimal leaf AC YAML with the given readiness value and return its path."""
    subdir = ac_root / "ac-driven-dev" / "ACD-test-goals"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "amended_by": [],
        "id": ac_id,
        "level": "L2",
        "readiness": readiness,
        "status": "active",
        "title": f"Leaf AC {ac_id}",
        "work_status": "todo",
    }
    if extra_fields:
        data.update(extra_fields)
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests — AC-1..AC-5 (ACD-1200b-5-i): idempotency + draft-skip behavior
# ---------------------------------------------------------------------------


class TestApproveAcsIdempotence:
    """Tests for approve_acs() — idempotency and draft-skip behaviour.

    Exercises that:
    - Already-approved leaves are left byte-for-byte unchanged (no re-stamp).
    - Draft leaves (below the reviewed threshold) are never promoted to approved.
    - Only reviewed leaves are promoted.
    - The run reports which leaves were promoted vs. left unchanged.
    """

    def test_mixed_readiness_only_reviewed_promoted(self) -> None:
        # covers: ACD-1200b-5-i
        """AC-1/2/3: Mixed goal — only the reviewed leaf is promoted.

        Given: a goal with 3 leaves:
               - LEAF-A at readiness: approved
               - LEAF-B at readiness: reviewed
               - LEAF-C at readiness: draft
        When:  approve_acs("GOAL-001", ac_root) is called.
        Then:  LEAF-B is promoted to readiness: approved.
               LEAF-A byte sequence is identical before and after (no re-stamp,
                 no duplicate amended_by entry, no field mutated).
               LEAF-C readiness is still 'draft' (never jumped to approved).

        What must be implemented for this test to pass:
        - _promote_leaf must skip (byte-stable no-op) when readiness is already 'approved'.
        - _promote_leaf must skip (no write) when readiness is 'draft' (not reviewed).
        - Only 'reviewed' leaves are eligible for promotion.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(
                ac_root, "GOAL-001", covered_by=["LEAF-A", "LEAF-B", "LEAF-C"]
            )
            leaf_a = _write_leaf_ac(ac_root, "LEAF-A", readiness="approved")
            leaf_b = _write_leaf_ac(ac_root, "LEAF-B", readiness="reviewed")
            leaf_c = _write_leaf_ac(ac_root, "LEAF-C", readiness="draft")

            # Snapshot LEAF-A bytes BEFORE calling approve_acs
            bytes_a_before = leaf_a.read_bytes()

            approve_acs("GOAL-001", ac_root)

            data_b = yaml.safe_load(leaf_b.read_text(encoding="utf-8"))
            data_c = yaml.safe_load(leaf_c.read_text(encoding="utf-8"))
            bytes_a_after = leaf_a.read_bytes()

            # LEAF-B (reviewed) must be promoted to approved
            assert data_b["readiness"] == "approved", (
                f"LEAF-B (was reviewed) must be promoted to 'approved'; "
                f"got {data_b['readiness']!r}"
            )

            # LEAF-A (already approved) must be byte-stable — no re-stamp
            assert bytes_a_before == bytes_a_after, (
                "LEAF-A (already approved) must not be modified by approve_acs — "
                "byte sequence changed, indicating an unwanted write"
            )

            # LEAF-C (draft) must remain unchanged — never jumped to approved
            assert data_c["readiness"] == "draft", (
                f"LEAF-C (draft) must remain at 'draft' after approve_acs; "
                f"got {data_c['readiness']!r} — draft must never be jumped to approved"
            )

    def test_draft_not_promoted(self) -> None:
        # covers: ACD-1200b-5-i
        """AC-3: A draft leaf is never jumped straight to approved.

        Given: a goal with exactly one leaf at readiness: draft.
        When:  approve_acs("GOAL-001", ac_root) is called.
        Then:  the leaf's readiness is still 'draft' (not promoted to approved).

        What must be implemented for this test to pass:
        - _promote_leaf must detect readiness != 'reviewed' and emit SKIP without
          writing the file, ensuring the leaf's readiness is not mutated.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(ac_root, "GOAL-001", covered_by=["LEAF-001"])
            leaf = _write_leaf_ac(ac_root, "LEAF-001", readiness="draft")

            approve_acs("GOAL-001", ac_root)

            data = yaml.safe_load(leaf.read_text(encoding="utf-8"))
            assert data["readiness"] == "draft", (
                f"Draft leaf must remain at 'draft' after approve_acs; "
                f"got {data['readiness']!r} — draft must never be promoted directly to approved"
            )

    def test_all_approved_zero_promotions_no_write(self) -> None:
        # covers: ACD-1200b-5-i
        """AC-5: All-approved goal — no file modified, run succeeds, zero promotions.

        Given: a goal with 2 leaves both at readiness: approved.
        When:  approve_acs("GOAL-001", ac_root) is called.
        Then:  (a) both file byte sequences are unchanged after the call (no write),
               (b) the function completes without raising any exception,
               (c) stdout does NOT contain the word 'promoted' (only 'no-op' messages
                   or silence — zero promotions occurred).

        What must be implemented for this test to pass:
        - When all leaves are already at readiness: approved, _promote_leaf must
          skip without writing.
        - No 'promoted' line may appear in stdout; only 'no-op' messages are allowed.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(ac_root, "GOAL-001", covered_by=["LEAF-001", "LEAF-002"])
            leaf1 = _write_leaf_ac(ac_root, "LEAF-001", readiness="approved")
            leaf2 = _write_leaf_ac(ac_root, "LEAF-002", readiness="approved")

            bytes1_before = leaf1.read_bytes()
            bytes2_before = leaf2.read_bytes()

            captured_stdout = io.StringIO()
            with redirect_stdout(captured_stdout):
                # (b) must not raise
                approve_acs("GOAL-001", ac_root)

            stdout_text = captured_stdout.getvalue()
            bytes1_after = leaf1.read_bytes()
            bytes2_after = leaf2.read_bytes()

            # (a) file bytes must be unchanged
            assert bytes1_before == bytes1_after, (
                "LEAF-001 must not be modified when already approved — "
                "byte sequence changed, indicating an unwanted re-stamp"
            )
            assert bytes2_before == bytes2_after, (
                "LEAF-002 must not be modified when already approved — "
                "byte sequence changed, indicating an unwanted re-stamp"
            )

            # (c) no 'promoted' message — only no-op messages are expected
            assert "promoted" not in stdout_text, (
                f"stdout must not contain 'promoted' when all leaves are already approved; "
                f"got stdout: {stdout_text!r}"
            )

    def test_run_reports_promoted_and_unchanged(self) -> None:
        # covers: ACD-1200b-5-i
        """AC-4: The run reports which leaves were promoted and which were left unchanged.

        Given: a goal with 3 leaves:
               - LEAF-X at readiness: reviewed
               - LEAF-Y at readiness: approved
               - LEAF-Z at readiness: draft
        When:  approve_acs("GOAL-001", ac_root) is called with stdout and stderr captured.
        Then:  stdout contains 'promoted' and 'LEAF-X' (reviewed leaf promoted),
               stdout contains 'no-op' and 'LEAF-Y' (approved leaf left unchanged),
               stderr contains 'LEAF-Z' or 'draft' (draft leaf skipped and reported).

        What must be implemented for this test to pass:
        - _promote_leaf must print "promoted {ac_id} ..." to stdout for reviewed leaves.
        - _promote_leaf must print "no-op {ac_id}: ..." to stdout for approved leaves.
        - _promote_leaf must print a SKIP message to stderr for non-reviewed, non-approved
          leaves (e.g. draft), naming the leaf so callers can identify it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(
                ac_root, "GOAL-001", covered_by=["LEAF-X", "LEAF-Y", "LEAF-Z"]
            )
            _write_leaf_ac(ac_root, "LEAF-X", readiness="reviewed")
            _write_leaf_ac(ac_root, "LEAF-Y", readiness="approved")
            _write_leaf_ac(ac_root, "LEAF-Z", readiness="draft")

            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()
            with redirect_stdout(captured_stdout):
                with redirect_stderr(captured_stderr):
                    approve_acs("GOAL-001", ac_root)

            stdout_text = captured_stdout.getvalue()
            stderr_text = captured_stderr.getvalue()

            # LEAF-X (reviewed → approved): must appear in stdout as "promoted"
            assert "promoted" in stdout_text and "LEAF-X" in stdout_text, (
                f"stdout must report 'promoted' for LEAF-X (reviewed→approved); "
                f"got stdout: {stdout_text!r}"
            )

            # LEAF-Y (already approved): must appear in stdout as "no-op"
            assert "no-op" in stdout_text and "LEAF-Y" in stdout_text, (
                f"stdout must report 'no-op' for LEAF-Y (already approved); "
                f"got stdout: {stdout_text!r}"
            )

            # LEAF-Z (draft): must be reported as skipped — implementation uses stderr
            assert "LEAF-Z" in stderr_text or "draft" in stderr_text, (
                f"stderr must mention LEAF-Z or 'draft' to indicate the draft leaf was "
                f"skipped and left unchanged; got stderr: {stderr_text!r}"
            )
