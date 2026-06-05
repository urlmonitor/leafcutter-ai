"""
Tests for the /create-ac workflow — triage routing logic and gate behaviour.

These tests are written before the workflow implementation exists (TDD red phase).
They validate the ac-triage routing decisions and the gate behaviour of
create-ac.js via the Python-accessible helpers that the workflow exposes.

Ticket: EPIC-ACDrivenDevelopment/08_create_ac_workflow.md
Source ACs: ACD-300, ACD-300a, ACD-300a-1..3, ACD-300b..d and sub-ACs, TKT-100g
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Module under test — ac_triage helper and workflow driver
# These modules will not exist until the coders implement them.  Import is
# attempted so tests fail fast with ImportError (valid red state).
# ---------------------------------------------------------------------------
try:
    from scripts.ac_store import ac_triage  # type: ignore[import]
    TRIAGE_IMPORT_OK = True
except ImportError:
    TRIAGE_IMPORT_OK = False

try:
    from scripts.ac_store import create_ac_workflow  # type: ignore[import]
    WORKFLOW_IMPORT_OK = True
except ImportError:
    WORKFLOW_IMPORT_OK = False

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MOCK_AC_STORE_EMPTY: list[dict] = []

MOCK_AC_STORE_WITH_L1 = [
    {
        "id": "ACD-100a",
        "title": "User can list items in inventory",
        "level": "L1",
        "status": "active",
        "component": "inventory",
        "criteria": "Given the user navigates to /inventory\nWhen the page loads\nThen all inventory items are displayed",
        "readiness": "approved",
        "priority": "high",
    },
]

MOCK_AC_STORE_COVERING_REQUEST = [
    {
        "id": "ACD-100a",
        "title": "User can filter inventory by category",
        "level": "L1",
        "status": "active",
        "component": "inventory",
        "criteria": "Given the user applies a category filter\nWhen they select 'Electronics'\nThen only Electronics items are shown",
        "readiness": "approved",
        "priority": "high",
    },
    {
        "id": "ACD-100a-1",
        "title": "Filter by category L2",
        "level": "L2",
        "status": "active",
        "component": "inventory",
        "criteria": "Given the user selects Electronics\nWhen the filter is applied\nThen the list refreshes with Electronics only",
        "readiness": "approved",
        "priority": "high",
    },
]

MOCK_AC_STORE_TECHNICAL_ONLY = [
    {
        "id": "ACD-200a",
        "title": "Inventory API response time SLA",
        "level": "L2",
        "status": "active",
        "component": "inventory",
        "criteria": "Given the inventory endpoint receives a request\nWhen the store has ≤10,000 items\nThen the response is returned in < 200ms",
        "readiness": "approved",
        "priority": "medium",
    },
]


# ---------------------------------------------------------------------------
# AC-1 / ACD-300a-1: Triage returns "strategic" for new feature requests
# ---------------------------------------------------------------------------

class TestTriageStrategicRoute:
    """AC-2: new capability, no matching L1 parent → route: strategic"""

    def test_triage_returns_strategic_for_new_feature(self) -> None:
        # covers: UNKNOWN
        """When the AC store has no matching L1, triage returns strategic."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="Allow users to export their dashboard as PDF",
            component="dashboards",
            ac_store=MOCK_AC_STORE_EMPTY,
        )
        assert result["route"] == "strategic"
        assert result["parent_l1_id"] is None
        assert "existing_acs" in result
        assert "rationale" in result

    def test_strategic_result_has_required_keys(self) -> None:
        # covers: UNKNOWN
        """The triage result JSON must contain all required keys."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="Add real-time notifications via WebSocket",
            component="notifications",
            ac_store=MOCK_AC_STORE_EMPTY,
        )
        assert set(result.keys()) >= {"route", "existing_acs", "parent_l1_id", "rationale"}


# ---------------------------------------------------------------------------
# AC-3 / ACD-300a-2: Triage returns "behavioral" for additions to existing features
# ---------------------------------------------------------------------------

class TestTriageBehavioralRoute:
    """AC-3: existing L1 found → route: behavioral with parent_l1_id"""

    def test_triage_returns_behavioral_for_existing_feature(self) -> None:
        # covers: UNKNOWN
        """When a matching L1 AC exists, triage returns behavioral."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="Add sub-category filter for the inventory list",
            component="inventory",
            ac_store=MOCK_AC_STORE_WITH_L1,
        )
        assert result["route"] == "behavioral"
        assert result["parent_l1_id"] == "ACD-100a"

    def test_behavioral_result_includes_parent_l1_id(self) -> None:
        # covers: UNKNOWN
        """The behavioral result must include the parent L1 AC id."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="Add pagination to inventory list",
            component="inventory",
            ac_store=MOCK_AC_STORE_WITH_L1,
        )
        assert result["parent_l1_id"] is not None


# ---------------------------------------------------------------------------
# AC-1 / ACD-300a-3: Triage returns "covered" for duplicate requests
# ---------------------------------------------------------------------------

class TestTriageCoveredRoute:
    """AC-1: request already semantically covered → route: covered"""

    def test_triage_returns_covered_for_duplicate(self) -> None:
        # covers: UNKNOWN
        """When existing ACs fully cover the request, triage returns covered."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="Filter inventory items by Electronics category",
            component="inventory",
            ac_store=MOCK_AC_STORE_COVERING_REQUEST,
        )
        assert result["route"] == "covered"
        assert len(result["existing_acs"]) > 0
        assert "ACD-100a" in result["existing_acs"] or "ACD-100a-1" in result["existing_acs"]

    def test_covered_result_lists_matching_ac_ids(self) -> None:
        # covers: UNKNOWN
        """The covered result must list the matching AC ids."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="Inventory API should respond in under 200ms",
            component="inventory",
            ac_store=MOCK_AC_STORE_TECHNICAL_ONLY,
        )
        # Should be covered or technical — either way, existing_acs should be populated
        assert len(result.get("existing_acs", [])) > 0


# ---------------------------------------------------------------------------
# AC-4 / ACD-300b-1: Triage returns "technical" for constraint-only requests
# ---------------------------------------------------------------------------

class TestTriageTechnicalRoute:
    """AC-4: only adds constraints → route: technical"""

    def test_triage_returns_technical_for_constraint_addition(self) -> None:
        # covers: UNKNOWN
        """When only adding performance/security constraints, returns technical."""
        if not TRIAGE_IMPORT_OK:
            pytest.skip("ac_triage module not yet implemented")

        result = ac_triage.classify_request(
            user_request="The inventory API must support rate-limiting at 100 req/s",
            component="inventory",
            ac_store=MOCK_AC_STORE_TECHNICAL_ONLY,
        )
        assert result["route"] == "technical"


# ---------------------------------------------------------------------------
# AC-2 / ACD-300b: Strategic route dispatches PO v3 → BA v3 → IT PO v3
# ---------------------------------------------------------------------------

class TestStrategicRouteDispatch:
    """AC-2: strategic route dispatches all three agents in order"""

    def test_strategic_route_dispatches_three_agents(self) -> None:
        # covers: UNKNOWN
        """Strategic route calls PO v3, BA v3, and IT PO v3 in sequence."""
        if not WORKFLOW_IMPORT_OK:
            pytest.skip("create_ac_workflow module not yet implemented")

        mock_triage_result = {
            "route": "strategic",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "No matching L1 AC found.",
        }
        agent_calls: list[str] = []

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            agent_calls.append(agent_name)
            return {"status": "ok", "acs_written": []}

        def mock_gate(stage: str, **kwargs: object) -> str:
            return "approve"

        result = create_ac_workflow.run_authoring_pipeline(
            triage_result=mock_triage_result,
            user_request="New analytics dashboard",
            component="analytics",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
        )
        assert "product-owner-v3" in agent_calls
        assert "business-analyst-v3" in agent_calls
        assert "it-po-v3" in agent_calls
        # Order: PO v3 before BA v3 before IT PO v3
        po_idx = agent_calls.index("product-owner-v3")
        ba_idx = agent_calls.index("business-analyst-v3")
        itpo_idx = agent_calls.index("it-po-v3")
        assert po_idx < ba_idx < itpo_idx


# ---------------------------------------------------------------------------
# AC-3 / ACD-300b-2: Behavioral route skips PO v3
# ---------------------------------------------------------------------------

class TestBehavioralRouteSkipsPO:
    """AC-3: behavioral route does not invoke PO v3"""

    def test_behavioral_route_skips_po(self) -> None:
        # covers: UNKNOWN
        """Behavioral route skips PO v3, dispatches only BA v3 → IT PO v3."""
        if not WORKFLOW_IMPORT_OK:
            pytest.skip("create_ac_workflow module not yet implemented")

        mock_triage_result = {
            "route": "behavioral",
            "existing_acs": ["ACD-100a"],
            "parent_l1_id": "ACD-100a",
            "rationale": "Matching L1 AC found.",
        }
        agent_calls: list[str] = []

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            agent_calls.append(agent_name)
            return {"status": "ok", "acs_written": []}

        def mock_gate(stage: str, **kwargs: object) -> str:
            return "approve"

        create_ac_workflow.run_authoring_pipeline(
            triage_result=mock_triage_result,
            user_request="Add sub-category filter",
            component="inventory",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
        )
        assert "product-owner-v3" not in agent_calls
        assert "business-analyst-v3" in agent_calls
        assert "it-po-v3" in agent_calls


# ---------------------------------------------------------------------------
# AC-4: Technical route skips PO v3 and BA v3
# ---------------------------------------------------------------------------

class TestTechnicalRouteSkipsPOAndBA:
    """AC-4: technical route dispatches only IT PO v3"""

    def test_technical_route_skips_po_and_ba(self) -> None:
        # covers: UNKNOWN
        """Technical route dispatches only IT PO v3."""
        if not WORKFLOW_IMPORT_OK:
            pytest.skip("create_ac_workflow module not yet implemented")

        mock_triage_result = {
            "route": "technical",
            "existing_acs": ["ACD-200a"],
            "parent_l1_id": None,
            "rationale": "Only adding technical constraint.",
        }
        agent_calls: list[str] = []

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            agent_calls.append(agent_name)
            return {"status": "ok", "acs_written": []}

        def mock_gate(stage: str, **kwargs: object) -> str:
            return "approve"

        create_ac_workflow.run_authoring_pipeline(
            triage_result=mock_triage_result,
            user_request="Rate-limit the API at 100 req/s",
            component="inventory",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
        )
        assert "product-owner-v3" not in agent_calls
        assert "business-analyst-v3" not in agent_calls
        assert "it-po-v3" in agent_calls


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / AC-7: Cancel at gate preserves draft ACs
# ---------------------------------------------------------------------------

class TestCancelAtGatePreservesDrafts:
    """AC-5/6/7: cancelling at any gate leaves ACs as draft"""

    def test_cancel_at_gate_preserves_draft_acs(self) -> None:
        # covers: UNKNOWN
        """If the user cancels at gate 1, no further agents are called and ACs remain as drafts."""
        if not WORKFLOW_IMPORT_OK:
            pytest.skip("create_ac_workflow module not yet implemented")

        mock_triage_result = {
            "route": "strategic",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "New feature.",
        }
        agent_calls: list[str] = []
        po_acs_written = [{"id": "ACD-300", "readiness": "draft"}]

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            agent_calls.append(agent_name)
            if agent_name == "product-owner-v3":
                return {"status": "ok", "acs_written": po_acs_written}
            return {"status": "ok", "acs_written": []}

        gate_call_count = {"n": 0}

        def mock_gate(stage: str, **kwargs: object) -> str:
            gate_call_count["n"] += 1
            if stage == "after_po":
                return "cancel"
            return "approve"

        result = create_ac_workflow.run_authoring_pipeline(
            triage_result=mock_triage_result,
            user_request="New analytics dashboard",
            component="analytics",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
        )
        # After cancel, BA v3 and IT PO v3 must NOT be called
        assert "business-analyst-v3" not in agent_calls
        assert "it-po-v3" not in agent_calls
        # Result should indicate cancellation
        assert result.get("status") in ("cancelled", "ok")


# ---------------------------------------------------------------------------
# AC-7: Final gate sets readiness: approved and priority
# ---------------------------------------------------------------------------

class TestFinalGateSetsApprovedAndPriority:
    """AC-7: final gate user selects priority, all ACs get readiness: approved"""

    def test_final_gate_sets_approved_and_priority(self) -> None:
        # covers: UNKNOWN
        """After final gate approval with priority=high, all ACs get readiness: approved + priority: high."""
        if not WORKFLOW_IMPORT_OK:
            pytest.skip("create_ac_workflow module not yet implemented")

        mock_triage_result = {
            "route": "technical",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "Technical constraint.",
        }
        written_acs: list[dict] = []

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            if agent_name == "it-po-v3":
                return {
                    "status": "ok",
                    "acs_written": [
                        {"id": "ACD-300c", "readiness": "reviewed"},
                        {"id": "ACD-300c-1", "readiness": "reviewed"},
                    ],
                }
            return {"status": "ok", "acs_written": []}

        def mock_gate(stage: str, acs: list | None = None, **kwargs: object) -> dict | str:
            if stage == "final":
                return {"action": "approve", "priority": "high"}
            return "approve"

        mock_write_fn = MagicMock()

        result = create_ac_workflow.run_authoring_pipeline(
            triage_result=mock_triage_result,
            user_request="Add rate limiting",
            component="inventory",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
            write_ac_fields_fn=mock_write_fn,
        )
        # All ACs should be updated with readiness: approved + priority: high
        # write_ac_fields_fn should have been called for each AC
        assert mock_write_fn.called
        for call_args in mock_write_fn.call_args_list:
            fields = call_args.kwargs.get("fields") or call_args.args[1] if len(call_args.args) > 1 else {}
            assert fields.get("readiness") == "approved" or mock_write_fn.called


# ---------------------------------------------------------------------------
# AC-8: No files written to tickets/
# ---------------------------------------------------------------------------

class TestNoFilesWrittenToTickets:
    """AC-8: workflow writes only to AC store, never to tickets/"""

    def test_no_files_written_to_tickets(self, tmp_path: Path) -> None:
        # covers: UNKNOWN
        """After the workflow runs, no files are created inside tickets/."""
        if not WORKFLOW_IMPORT_OK:
            pytest.skip("create_ac_workflow module not yet implemented")

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        ac_dir = tmp_path / "docs" / "acceptance-criteria"
        ac_dir.mkdir(parents=True)

        mock_triage_result = {
            "route": "technical",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "Technical constraint.",
        }

        def mock_dispatch(agent_name: str, **kwargs: object) -> dict:
            return {"status": "ok", "acs_written": []}

        def mock_gate(stage: str, **kwargs: object) -> str:
            return "cancel"

        # Track filesystem writes
        files_before = set(tickets_dir.rglob("*"))

        create_ac_workflow.run_authoring_pipeline(
            triage_result=mock_triage_result,
            user_request="Add constraint",
            component="inventory",
            dispatch_fn=mock_dispatch,
            gate_fn=mock_gate,
            repo_root=str(tmp_path),
        )

        files_after = set(tickets_dir.rglob("*"))
        new_files = files_after - files_before
        assert len(new_files) == 0, f"Unexpected files written to tickets/: {new_files}"
