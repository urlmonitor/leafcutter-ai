"""
Tests for the /create-ac workflow's final gate: approval sets readiness: approved and the priority.

Moved out of test_create_ac_workflow.py (AC-7 of EPIC-ACDrivenDevelopment/08_create_ac_workflow.md)
when ACD-300c-4-iv changed how the approval is applied: create_ac_workflow.run_authoring_pipeline
now approves only through the store's approval step (approve_acs.py --ids, run with cwd = repo_root)
and no longer writes readiness through write_ac_fields_fn. The outcome is therefore read back from the
records on disk in a tmp consumer-style store.

Source ACs: ACD-300, ACD-300c-4-iv
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from scripts.ac_store import create_ac_workflow

_AC_IDS = ("ACD-300c", "ACD-300c-1")
_TRIAGE: dict[str, object] = {"route": "technical", "existing_acs": [], "parent_l1_id": None, "rationale": "Technical constraint."}


def _write_reviewed_records(component_dir: Path) -> None:
    """Two reviewed records at priority low, with no test intent (nothing holds them back)."""
    component_dir.mkdir(parents=True)
    for ac_id in _AC_IDS:
        record = {
            "id": ac_id,
            "level": "L2",
            "readiness": "reviewed",
            "priority": "low",
            "criteria": "Given a request\nWhen it is rate limited\nThen it is refused\n",
            "amended_by": [],
        }
        (component_dir / f"{ac_id}.yaml").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")


class TestFinalGateSetsApprovedAndPriority:
    """AC-7: final gate user selects priority, all ACs get readiness: approved"""

    def test_final_gate_sets_approved_and_priority(self, tmp_path: Path) -> None:
        # covers: UNKNOWN
        """After final gate approval with priority=high, all ACs get readiness: approved + priority: high,
        written by the approval step (write_ac_fields_fn is never called)."""
        component_dir = tmp_path / "docs" / "acceptance-criteria" / "inventory"
        _write_reviewed_records(component_dir)

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            return {"status": "ok", "acs_written": list(_AC_IDS) if agent_name == "it-po" else []}

        def mock_gate(stage: str, acs: list | None = None, **kwargs: object) -> dict | str:
            return {"action": "approve", "priority": "high"} if stage == "final" else "approve"

        mock_write_fn = MagicMock()

        result = create_ac_workflow.run_authoring_pipeline(
            triage_result=_TRIAGE,
            user_request="Add rate limiting",
            component="inventory",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
            write_ac_fields_fn=mock_write_fn,
            repo_root=str(tmp_path),
        )

        assert result["status"] == "ok", result
        assert sorted(result["acs_approved"]) == sorted(_AC_IDS), result
        assert result["priority"] == "high", result
        for ac_id in _AC_IDS:
            on_disk = yaml.safe_load((component_dir / f"{ac_id}.yaml").read_text(encoding="utf-8"))
            assert on_disk["readiness"] == "approved", on_disk
            assert on_disk["priority"] == "high", on_disk
        assert not mock_write_fn.called, mock_write_fn.call_args_list
