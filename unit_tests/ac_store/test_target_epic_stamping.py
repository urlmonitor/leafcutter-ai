"""
MODULE: test_target_epic_stamping
GOAL: Unit tests for stamp_target_epic() in goal_to_epic.py.
      Covers: clean stamp (no existing target_epic), idempotent re-run,
      conflict detection (existing different value), conflict-yes path,
      conflict-skip path, and exclusion guard (excluded AC files not touched).
TICKET: EPIC-GoalToEpic/04_target-epic-stamping.md
COVERS: ACD-1200d-1, ACD-1200d-1-i, ACD-1200d-2
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# This import will fail (ImportError) until python-coder adds stamp_target_epic()
# to goal_to_epic.py — that is the intended red state.
from goal_to_epic import stamp_target_epic  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac_yaml(
    ac_root: Path,
    ac_id: str,
    target_epic: str | None = None,
    extra_fields: dict | None = None,
) -> Path:
    """Write a minimal AC YAML file and return its path.

    Args:
        ac_root: Root of the AC YAML store (temp dir in tests).
        ac_id: The AC identifier (e.g. "ACD-050a-1").
        target_epic: If provided, include a target_epic field.
        extra_fields: Additional fields to include in the YAML.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "ac-driven-dev" / "ACD-1200-goal-to-epic"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "readiness": "approved",
    }
    if target_epic is not None:
        data["target_epic"] = target_epic
    if extra_fields:
        data.update(extra_fields)
    # Write using yaml.dump so it's a valid YAML file
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _read_target_epic(path: Path) -> str | None:
    """Read the target_epic field from an AC YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("target_epic")
    return None


# ---------------------------------------------------------------------------
# AC-1: Targeted field write, idempotency, case-exact match (ACD-1200d-1)
# ---------------------------------------------------------------------------


class TestCleanStamp:
    """Tests for stamping ACs with no existing target_epic (ACD-1200d-1).

    stamp_target_epic(included_ids, epic_name, store_root) must:
    - Write target_epic: <epic_name> to each included AC YAML via targeted
      field write (not yaml.dump round-trip that strips comments/reorders).
    - Case-exactly match the epic_name value provided.
    - Be idempotent: re-running with the same epic name is a no-op.
    - Only touch AC IDs that appear in included_ids.
    - Only begin stamping after epic folder creation (caller guarantees this;
      stamp_target_epic does not check for folder existence).
    """

    def test_ac1_stamps_all_included_acs(self) -> None:
        # covers: ACD-1200d-1
        """AC-1: All included AC YAML files receive target_epic matching the epic name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac1_path = _write_ac_yaml(store_root, "ACD-050a-1")
            ac2_path = _write_ac_yaml(store_root, "ACD-050a-2-i")
            ac3_path = _write_ac_yaml(store_root, "ACD-050b-1")

            included_ids = ["ACD-050a-1", "ACD-050a-2-i", "ACD-050b-1"]
            stamp_target_epic(
                included_ids=included_ids,
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            assert _read_target_epic(ac1_path) == "EPIC-ValidateApiInputs", (
                "ACD-050a-1 must have target_epic: EPIC-ValidateApiInputs"
            )
            assert _read_target_epic(ac2_path) == "EPIC-ValidateApiInputs", (
                "ACD-050a-2-i must have target_epic: EPIC-ValidateApiInputs"
            )
            assert _read_target_epic(ac3_path) == "EPIC-ValidateApiInputs", (
                "ACD-050b-1 must have target_epic: EPIC-ValidateApiInputs"
            )

    def test_ac1_case_exact_match(self) -> None:
        # covers: ACD-1200d-1
        """AC-1: target_epic value is case-exactly equal to the epic_name argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(store_root, "ACD-050a-1")

            stamp_target_epic(
                included_ids=["ACD-050a-1"],
                epic_name="EPIC-MyExactCaseName",
                store_root=store_root,
            )

            value = _read_target_epic(ac_path)
            assert value == "EPIC-MyExactCaseName", (
                f"target_epic must be 'EPIC-MyExactCaseName' exactly, got {value!r}"
            )

    def test_ac1_targeted_field_write_preserves_other_fields(self) -> None:
        # covers: ACD-1200d-1
        """AC-1: targeted field write preserves all other fields in the YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(
                store_root,
                "ACD-050a-1",
                extra_fields={
                    "some_custom_field": "custom_value",
                    "nested": {"key": "val"},
                },
            )

            stamp_target_epic(
                included_ids=["ACD-050a-1"],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            data = yaml.safe_load(ac_path.read_text(encoding="utf-8"))
            assert data.get("id") == "ACD-050a-1", "id field must be preserved"
            assert data.get("title") == "AC ACD-050a-1", "title field must be preserved"
            assert data.get("some_custom_field") == "custom_value", (
                "custom fields must be preserved"
            )
            assert data.get("nested") == {"key": "val"}, "nested fields must be preserved"
            assert data.get("target_epic") == "EPIC-ValidateApiInputs", (
                "target_epic must be set"
            )

    def test_ac1_idempotent_same_value_no_op(self) -> None:
        # covers: ACD-1200d-1
        """AC-1: Idempotency — re-stamping with the same epic_name is a no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(
                store_root, "ACD-050a-1", target_epic="EPIC-ValidateApiInputs"
            )
            mtime_after_first = ac_path.stat().st_mtime

            # Re-run with the same value — should be a no-op (file not rewritten)
            stamp_target_epic(
                included_ids=["ACD-050a-1"],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            mtime_after_second = ac_path.stat().st_mtime
            # File modification time must not change on idempotent re-run
            assert mtime_after_first == mtime_after_second, (
                "Re-stamping with the same value must be a no-op (no file rewrite)"
            )
            assert _read_target_epic(ac_path) == "EPIC-ValidateApiInputs", (
                "target_epic value must remain unchanged after idempotent re-run"
            )

    def test_ac1_idempotent_no_duplicate_fields(self) -> None:
        # covers: ACD-1200d-1
        """AC-1: Idempotent re-run does not produce duplicate target_epic fields in YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(
                store_root, "ACD-050a-1", target_epic="EPIC-ValidateApiInputs"
            )

            stamp_target_epic(
                included_ids=["ACD-050a-1"],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            content = ac_path.read_text(encoding="utf-8")
            occurrences = content.count("target_epic")
            assert occurrences == 1, (
                f"target_epic must appear exactly once after idempotent re-run, got {occurrences}"
            )


# ---------------------------------------------------------------------------
# AC-2: Conflict detection — existing different target_epic (ACD-1200d-1-i)
# ---------------------------------------------------------------------------


class TestConflictDetection:
    """Tests for conflict detection when an AC already has a different target_epic (ACD-1200d-1-i).

    stamp_target_epic() must:
    - Detect when an included AC already has a target_epic that differs from epic_name.
    - Prompt per-AC: "ACD-xxx already belongs to EPIC-OldName. Overwrite with
      EPIC-NewName? (yes / skip)"
    - On "yes": overwrite with the new epic_name.
    - On "skip": retain the original target_epic value.
    - Generate the ticket regardless of the user's tag decision (no ticket generation
      here — but the function must not raise on skip/yes).
    """

    def test_ac2_conflict_detected_per_ac(self) -> None:
        # covers: ACD-1200d-1-i
        """AC-2: Conflict detection fires per-AC when existing target_epic differs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac_yaml(store_root, "ACD-050a-1", target_epic="EPIC-OldBatch")

            # Simulate user choosing "yes" to overwrite
            with patch("builtins.input", return_value="yes") as mock_input:
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            # Prompt must have been shown (conflict detected)
            mock_input.assert_called_once()
            call_args = mock_input.call_args[0][0]
            assert "ACD-050a-1" in call_args, "Prompt must name the conflicting AC"
            assert "EPIC-OldBatch" in call_args, "Prompt must name the existing epic"
            assert "EPIC-ValidateApiInputs" in call_args, "Prompt must name the new epic"

    def test_ac2_conflict_prompt_format(self) -> None:
        # covers: ACD-1200d-1-i
        """AC-2: Prompt format is 'ACD-xxx already belongs to EPIC-OldName. Overwrite with EPIC-NewName? (yes / skip)'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac_yaml(store_root, "ACD-050a-1", target_epic="EPIC-OldBatch")

            with patch("builtins.input", return_value="skip") as mock_input:
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            prompt = mock_input.call_args[0][0]
            # Prompt must contain required elements per AC-2 spec
            assert "already belongs to" in prompt.lower() or "overwrite" in prompt.lower(), (
                f"Prompt must indicate conflict, got: {prompt!r}"
            )
            assert "yes" in prompt.lower() and "skip" in prompt.lower(), (
                f"Prompt must offer 'yes' and 'skip' options, got: {prompt!r}"
            )

    def test_ac2_yes_overwrites_existing_target_epic(self) -> None:
        # covers: ACD-1200d-1-i
        """AC-2: User 'yes' answer overwrites the existing target_epic value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(
                store_root, "ACD-050a-1", target_epic="EPIC-OldBatch"
            )

            with patch("builtins.input", return_value="yes"):
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            assert _read_target_epic(ac_path) == "EPIC-ValidateApiInputs", (
                "After 'yes', target_epic must be overwritten with the new epic name"
            )

    def test_ac2_skip_retains_original_target_epic(self) -> None:
        # covers: ACD-1200d-1-i
        """AC-2: User 'skip' answer retains the original target_epic value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(
                store_root, "ACD-050a-1", target_epic="EPIC-OldBatch"
            )

            with patch("builtins.input", return_value="skip"):
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            assert _read_target_epic(ac_path) == "EPIC-OldBatch", (
                "After 'skip', target_epic must retain the original value"
            )

    def test_ac2_conflict_prompt_is_per_ac_not_batched(self) -> None:
        # covers: ACD-1200d-1-i
        """AC-2: Conflict prompt fires once per conflicting AC, not once for the batch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac_yaml(store_root, "ACD-050a-1", target_epic="EPIC-OldBatch")
            _write_ac_yaml(store_root, "ACD-050a-2-i", target_epic="EPIC-AnotherOld")
            _write_ac_yaml(store_root, "ACD-050b-1")  # No conflict — no existing target_epic

            # Two conflicting ACs → two prompts; one clean AC → no prompt for it
            with patch("builtins.input", side_effect=["yes", "skip"]) as mock_input:
                stamp_target_epic(
                    included_ids=["ACD-050a-1", "ACD-050a-2-i", "ACD-050b-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            assert mock_input.call_count == 2, (
                f"Exactly 2 conflict prompts expected (one per conflicting AC), "
                f"got {mock_input.call_count}"
            )

    def test_ac2_no_raise_on_conflict_regardless_of_decision(self) -> None:
        # covers: ACD-1200d-1-i
        """AC-2: stamp_target_epic does not raise on conflict — regardless of yes/skip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac_yaml(store_root, "ACD-050a-1", target_epic="EPIC-OldBatch")

            # 'yes' path must not raise
            with patch("builtins.input", return_value="yes"):
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            # Reset for 'skip' path
            _write_ac_yaml(store_root, "ACD-050a-1", target_epic="EPIC-OldBatch")

            # 'skip' path must not raise
            with patch("builtins.input", return_value="skip"):
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )


# ---------------------------------------------------------------------------
# AC-3: Exclusion guard — excluded ACs are never touched (ACD-1200d-2)
# ---------------------------------------------------------------------------


class TestExclusionGuard:
    """Tests that ACs not in included_ids are never modified (ACD-1200d-2).

    stamp_target_epic() must:
    - Never write to AC YAML files whose IDs are NOT in included_ids.
    - Not add target_epic to excluded ACs.
    - Not modify the mtime of excluded AC files.
    """

    def test_ac3_excluded_acs_not_touched(self) -> None:
        # covers: ACD-1200d-2
        """AC-3: ACs not in included_ids are never modified during stamping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            # Included: will be stamped
            _write_ac_yaml(store_root, "ACD-050a-1")
            # Excluded: must NOT be touched
            excluded_path = _write_ac_yaml(store_root, "ACD-050a-2-i")
            excluded_mtime = excluded_path.stat().st_mtime

            stamp_target_epic(
                included_ids=["ACD-050a-1"],  # Only ACD-050a-1 is included
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            assert excluded_path.stat().st_mtime == excluded_mtime, (
                "Excluded AC file must not be modified (mtime unchanged)"
            )
            assert _read_target_epic(excluded_path) is None, (
                "Excluded AC must not receive target_epic field"
            )

    def test_ac3_excluded_ac_retains_no_target_epic(self) -> None:
        # covers: ACD-1200d-2
        """AC-3: Excluded ACs that had no target_epic retain no target_epic after run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac_yaml(store_root, "ACD-050a-1")
            excluded_path = _write_ac_yaml(store_root, "ACD-050b-1")

            # Only include ACD-050a-1; exclude ACD-050b-1
            stamp_target_epic(
                included_ids=["ACD-050a-1"],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            assert _read_target_epic(excluded_path) is None, (
                "Excluded AC (ACD-050b-1) must have no target_epic after stamping"
            )

    def test_ac3_excluded_ac_with_existing_target_epic_not_overwritten(self) -> None:
        # covers: ACD-1200d-2
        """AC-3: Excluded ACs that already have a target_epic are NOT touched (no prompt, no overwrite)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac_yaml(store_root, "ACD-050a-1")
            excluded_path = _write_ac_yaml(
                store_root, "ACD-050b-1", target_epic="EPIC-OtherEpic"
            )

            with patch("builtins.input") as mock_input:
                stamp_target_epic(
                    included_ids=["ACD-050a-1"],  # ACD-050b-1 is excluded
                    epic_name="EPIC-ValidateApiInputs",
                    store_root=store_root,
                )

            # No prompt for excluded AC, regardless of whether it had a target_epic
            mock_input.assert_not_called(), (
                "No conflict prompt should fire for excluded ACs"
            )
            assert _read_target_epic(excluded_path) == "EPIC-OtherEpic", (
                "Excluded AC's existing target_epic must be preserved unchanged"
            )

    def test_ac3_multiple_excluded_acs_none_touched(self) -> None:
        # covers: ACD-1200d-2
        """AC-3: Multiple excluded ACs are all untouched regardless of inclusion of others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            included_path = _write_ac_yaml(store_root, "ACD-050a-1")
            excl1_path = _write_ac_yaml(store_root, "ACD-050a-2-i")
            excl2_path = _write_ac_yaml(store_root, "ACD-050b-1")
            excl1_mtime = excl1_path.stat().st_mtime
            excl2_mtime = excl2_path.stat().st_mtime

            stamp_target_epic(
                included_ids=["ACD-050a-1"],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            # Included AC gets stamped
            assert _read_target_epic(included_path) == "EPIC-ValidateApiInputs"
            # Both excluded ACs remain unchanged
            assert excl1_path.stat().st_mtime == excl1_mtime, (
                "ACD-050a-2-i (excluded) mtime must not change"
            )
            assert excl2_path.stat().st_mtime == excl2_mtime, (
                "ACD-050b-1 (excluded) mtime must not change"
            )
            assert _read_target_epic(excl1_path) is None
            assert _read_target_epic(excl2_path) is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for stamp_target_epic()."""

    def test_empty_included_ids_is_noop(self) -> None:
        # covers: ACD-1200d-1
        """Empty included_ids → no files written, no errors raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(store_root, "ACD-050a-1")
            mtime_before = ac_path.stat().st_mtime

            stamp_target_epic(
                included_ids=[],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            assert ac_path.stat().st_mtime == mtime_before, (
                "Empty included_ids must not modify any files"
            )

    def test_ac_id_not_found_in_store_is_skipped_not_raised(self) -> None:
        # covers: ACD-1200d-1
        """AC IDs in included_ids that do not exist in store_root are silently skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac_yaml(store_root, "ACD-050a-1")

            # ACD-MISSING does not exist — should not cause an exception
            stamp_target_epic(
                included_ids=["ACD-050a-1", "ACD-MISSING-999"],
                epic_name="EPIC-ValidateApiInputs",
                store_root=store_root,
            )

            # Known AC should still be stamped
            assert _read_target_epic(ac_path) == "EPIC-ValidateApiInputs"
