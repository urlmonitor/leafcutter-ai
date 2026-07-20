"""
MODULE: test_acd_1200b_5
GOAL: Unit tests for ACD-1200b-5: the approve_acs mechanism that promotes
      reviewed leaf ACs to approved without hand-editing YAML.
BUSINESS CONTEXT: Verifies that scripts/ac_store/approve_acs.py correctly
      promotes reviewed leaf ACs of a goal to approved (append-only, idempotent)
      following the same store-mutation convention as mark_ac_done.py.
ARCHITECTURE: Tests write real YAML files in a TemporaryDirectory; no mocks.
      The module under test (approve_acs.py) does not yet exist — all three
      tests are intentionally RED (ImportError) until python-coder implements it.

TICKET: TICKET-20260720-ACD-1200b-5.md
COVERS: ACD-1200b-5
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# This import will fail (ImportError) until python-coder implements
# approve_acs in scripts/ac_store/approve_acs.py — that is the intended red state.
from approve_acs import approve_acs  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
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
# Tests — AC-1, AC-2, AC-3, AC-4 (ACD-1200b-5)
# ---------------------------------------------------------------------------


class TestApproveACs:
    """Tests for approve_acs() — the approval mechanism for reviewed leaf ACs.

    All three tests exercise approve_acs(goal_ac_id, ac_root) where:
    - goal_ac_id: the ID of the goal AC whose covered_by lists the leaf children.
    - ac_root: the root directory of the AC store (TemporaryDirectory fixture).
    """

    def test_reviewed_leaves_promoted_to_approved(self) -> None:
        # covers: ACD-1200b-5
        """AC-1: Two reviewed leaf children under a goal are promoted to approved.

        Given: a goal AC (GOAL-001) with covered_by: [LEAF-001, LEAF-002], and
               both leaf ACs at readiness: reviewed.
        When:  approve_acs(goal_ac_id='GOAL-001', ac_root=...) is called.
        Then:  both leaf AC YAML files must have readiness: approved.

        What must be implemented for this test to pass:
        - scripts/ac_store/approve_acs.py must define approve_acs(goal_ac_id, ac_root).
        - It must locate the goal AC by scanning ac_root for a YAML whose id == goal_ac_id.
        - It must read the goal AC's covered_by field to obtain the list of leaf IDs.
        - For each leaf ID with readiness == 'reviewed', it must write readiness: approved
          into the stored YAML file (in-place, not by full rewrite).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(ac_root, "GOAL-001", covered_by=["LEAF-001", "LEAF-002"])
            leaf1 = _write_leaf_ac(ac_root, "LEAF-001", readiness="reviewed")
            leaf2 = _write_leaf_ac(ac_root, "LEAF-002", readiness="reviewed")

            approve_acs("GOAL-001", ac_root)

            data1 = yaml.safe_load(leaf1.read_text(encoding="utf-8"))
            data2 = yaml.safe_load(leaf2.read_text(encoding="utf-8"))

            assert data1["readiness"] == "approved", (
                f"LEAF-001 must be promoted to 'approved', got {data1['readiness']!r}"
            )
            assert data2["readiness"] == "approved", (
                f"LEAF-002 must be promoted to 'approved', got {data2['readiness']!r}"
            )

    def test_amended_by_appended_no_other_field_changed(self) -> None:
        # covers: ACD-1200b-5
        """AC-2 + AC-3: Exactly one amended_by entry appended; no other field mutated.

        Given: a goal AC (GOAL-001) with covered_by: [LEAF-001], and
               LEAF-001 at readiness: reviewed with known fields.
        When:  approve_acs(goal_ac_id='GOAL-001', ac_root=...) is called.
        Then:  LEAF-001's amended_by list grows by exactly one entry,
               LEAF-001's readiness changes from reviewed to approved,
               and every other field of LEAF-001 remains byte-for-byte unchanged.

        What must be implemented for this test to pass:
        - approve_acs must append exactly one entry to amended_by (not zero, not two).
        - The entry should record the promotion (e.g. {action: approved, agent: ...}).
        - No field other than readiness and amended_by may be written or re-ordered.
        - The file must NOT be fully rewritten (preserves field order and comments).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(ac_root, "GOAL-001", covered_by=["LEAF-001"])
            leaf_path = _write_leaf_ac(ac_root, "LEAF-001", readiness="reviewed")

            # Snapshot all fields before promotion
            data_before = yaml.safe_load(leaf_path.read_text(encoding="utf-8"))
            fields_before = set(data_before.keys())
            amended_by_before_count = len(data_before.get("amended_by", []))

            approve_acs("GOAL-001", ac_root)

            data_after = yaml.safe_load(leaf_path.read_text(encoding="utf-8"))
            amended_by_after = list(data_after.get("amended_by", []))

            # Exactly one amended_by entry was appended
            assert len(amended_by_after) == amended_by_before_count + 1, (
                f"Expected exactly one new amended_by entry. "
                f"Before: {amended_by_before_count}, after: {len(amended_by_after)}"
            )

            # readiness was promoted
            assert data_after["readiness"] == "approved", (
                f"readiness must be 'approved' after promotion, "
                f"got {data_after['readiness']!r}"
            )

            # No field other than readiness and amended_by was mutated
            for field, value_before in data_before.items():
                if field in ("readiness", "amended_by"):
                    continue
                assert data_after.get(field) == value_before, (
                    f"Field {field!r} must not be altered by approve_acs "
                    f"(was {value_before!r}, now {data_after.get(field)!r})"
                )

            # No new fields were introduced
            new_fields = set(data_after.keys()) - fields_before
            assert not new_fields, (
                f"approve_acs must not introduce new YAML fields: {new_fields}"
            )

    def test_idempotent_second_run_noop(self) -> None:
        # covers: ACD-1200b-5
        """AC-4: A second run is byte-stable and does not duplicate amended_by entries.

        Given: a goal AC (GOAL-001) with covered_by: [LEAF-001, LEAF-002], and
               both leaf ACs initially at readiness: reviewed.
        When:  approve_acs is called once (first run), then called again (second run).
        Then:  the files are byte-for-byte identical after the second run,
               and each leaf's amended_by list has exactly one entry (not two).

        What must be implemented for this test to pass:
        - approve_acs must skip any leaf AC where readiness is already 'approved'.
        - The file must not be touched at all on the second run (byte-stable).
        - The amended_by list must not gain a duplicate entry.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_goal_ac(ac_root, "GOAL-001", covered_by=["LEAF-001", "LEAF-002"])
            leaf1 = _write_leaf_ac(ac_root, "LEAF-001", readiness="reviewed")
            leaf2 = _write_leaf_ac(ac_root, "LEAF-002", readiness="reviewed")

            # First run — promotes both leaves
            approve_acs("GOAL-001", ac_root)
            bytes_leaf1_run1 = leaf1.read_bytes()
            bytes_leaf2_run1 = leaf2.read_bytes()

            # Second run — must be a no-op
            approve_acs("GOAL-001", ac_root)
            bytes_leaf1_run2 = leaf1.read_bytes()
            bytes_leaf2_run2 = leaf2.read_bytes()

            assert bytes_leaf1_run1 == bytes_leaf1_run2, (
                "LEAF-001 must be byte-stable after a second approve_acs run "
                "(already-approved leaf must not be re-written)"
            )
            assert bytes_leaf2_run1 == bytes_leaf2_run2, (
                "LEAF-002 must be byte-stable after a second approve_acs run "
                "(already-approved leaf must not be re-written)"
            )

            # Confirm no duplicate amended_by entries
            data1 = yaml.safe_load(leaf1.read_text(encoding="utf-8"))
            data2 = yaml.safe_load(leaf2.read_text(encoding="utf-8"))
            assert len(data1.get("amended_by", [])) == 1, (
                f"LEAF-001 must have exactly one amended_by entry after two runs, "
                f"got {len(data1.get('amended_by', []))}"
            )
            assert len(data2.get("amended_by", [])) == 1, (
                f"LEAF-002 must have exactly one amended_by entry after two runs, "
                f"got {len(data2.get('amended_by', []))}"
            )
