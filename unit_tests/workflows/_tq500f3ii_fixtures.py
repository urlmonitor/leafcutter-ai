"""
MODULE: unit_tests/workflows/_tq500f3ii_fixtures.py
GOAL: Shared label_responses/args fixtures for the TQ-500f-3-ii family --
    driving templates/workflows-js/build-feature.js (and its declared twin
    build-ticket.js) through a single-ticket test-writer -> [red-baseline
    gate] -> coder dispatch sequence via
    unit_tests/_workflow_engine_harness.py's run_workflow_under_e2().
BUSINESS CONTEXT: TQ-500f-3-ii wires the SAME verify_red_baseline reader the
    fast lane uses (TQ-500f-3-i) into the heavy lane's per-ticket phase
    driver, between the test-writer phase and the first coder dispatch.
    Today NO such gate exists in build-feature.js / build-ticket.js -- the
    only evidence is the test-writer's own self-reported
    ``red_baseline_verified`` claim in its sign-off. This module's fixtures
    therefore always supply a test-writer reply that CLAIMS red
    (``red_baseline_verified: true``) -- K1's whole point is that the real
    gate must not take that claim at face value.

TARGET IMPLEMENTATION CONTRACT (pinned by these tests, not yet built):
    The gate is dispatched as a depth-1 executor agent -- the SAME
    "run a real shell command, return {output, exit_code}" pattern
    build-feature.js already uses for repo-facts calls (see
    readTicketRecordBack / the "Resolve Target" phase, agentType:
    "status-checker") -- with:
        agentType: "status-checker"
        label:     "red-baseline-gate"   (RED_BASELINE_GATE_LABEL below)
    dispatched between the test-writer phase's own dispatch and the FIRST
    coder-phase dispatch (python-coder / sql-coder / frontend-coder), for
    every ticket that carries a source_ac.

    DESIGN CHANGE (superseding the first cut of this AC): build-feature.js
    and build-ticket.js both crossed the JS file-size limit once the gate's
    full decision logic (parsing gate_passed/reason, building halt payloads
    per reason) lived inline in driveTicketPhases(). That decision logic
    moves OUT of both JS files and INTO a new fast_lane.py CLI subcommand,
    ``heavy_lane_gate`` (see
    unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    for its full pinned contract) -- each JS driver keeps only a THIN
    dispatch + fail-closed parse of the one JSON object that subcommand
    prints. The gate dispatch's prompt must therefore embed
    ``python3 <gateScript> heavy_lane_gate --source-ac <ids> --test-root
    <worktree> --ac-root <ac-store>`` -- see ``extract_gate_invocation()``
    below (matches either subcommand name, since fast-lane-ship.js's own
    ``redBaselineInvocation`` template keeps calling ``verify_red_baseline``
    directly, unaffected by this heavy-lane-only change).
"""

from __future__ import annotations

import json
import re
from typing import Any

WORKTREE_ABS_PATH = "/tmp/tq500f3ii-worktree"
TICKET_ABS_PATH = "/tmp/tq500f3ii-worktree/tickets/01_todo/07_ticket.md"

RED_BASELINE_GATE_LABEL = "red-baseline-gate"

WORKTREE_FACTS_RESOLVED: dict[str, Any] = {
    "output": (
        '{"exists": true, "is_git_toplevel": true, "is_linked_worktree": true, '
        '"is_main_checkout": false, "same_repository": true, "branch": "fixture"}'
    ),
    "exit_code": 0,
}

# A command-line fragment recognisable in EITHER lane's captured prompt text:
# fast-lane-ship.js's own redBaselineInvocation embeds
# "python3 <path>/fast_lane.py verify_red_baseline --ac-ids <ids> --test-root <dir>";
# the heavy lane's gate dispatch (per the DESIGN CHANGE moving its decision
# logic into fast_lane.py itself -- see HEAVY_LANE_GATE_SUBCOMMAND below)
# embeds "python3 <path>/fast_lane.py heavy_lane_gate --source-ac <id> ...".
# Both subcommand names are matched so this ONE extractor keeps working
# whichever subcommand a given captured prompt actually names.
_GATE_INVOCATION_RE = re.compile(
    r"python3?\s+\S*fast_lane\.py\s+(?:verify_red_baseline|heavy_lane_gate)[^\n\"]*",
    re.IGNORECASE,
)


def resolve_target_response(
    ticket_path: str = TICKET_ABS_PATH, worktree_path: str = WORKTREE_ABS_PATH
) -> dict[str, Any]:
    return {
        "target_type": "ticket",
        "ticket_path": ticket_path,
        "worktree_path": worktree_path,
    }


def worktree_setup_response(worktree_path: str = WORKTREE_ABS_PATH) -> dict[str, Any]:
    return {"worktree_path": worktree_path, "status": "reused"}


def signoff_readback_response() -> dict[str, Any]:
    return {
        "readable": True,
        "lifecycle_status": "todo",
        "needed_phases": [],
        "depends_on": [],
        "signoffs": [],
        "signed_off_agents": [],
    }


def ticket_planner_response(
    ticket_path: str,
    ordered_phases: list[dict[str, str]],
    *,
    source_ac: str | list[str] | None,
    has_test_requirements: bool = True,
) -> dict[str, Any]:
    """label_responses["ticket-planner"] value.

    ``source_ac`` (NOT part of TICKET_PLANNER_SCHEMA today -- see
    build-feature.js's TICKET_PLANNER_SCHEMA, which names no such key) is the
    field TQ-500f-3-ii's it_requirements require the planner to report so the
    gate dispatch can be built from it. K3's fixture passes ``source_ac=None``
    to omit it entirely (a ticket with no source requirement).
    """
    payload: dict[str, Any] = {
        "ticket_path": ticket_path,
        "title": "TQ-500f-3-ii fixture ticket",
        "files_touched": ["some/module.py"],
        "has_test_requirements": has_test_requirements,
        "existing_test_files": [],
        "ordered_phases": ordered_phases,
    }
    if source_ac is not None:
        payload["source_ac"] = source_ac
    return payload


def test_writer_claims_red_response(
    tests_written: list[str] | None = None,
) -> dict[str, Any]:
    """The test-writer's own sign-off claim -- ALWAYS reports red, in every
    fixture in this family. K1's whole point is that the gate must not trust
    this claim; it re-runs the reader independently.
    """
    return {
        "status": "ok",
        "message": "wrote failing stubs",
        "tests_written": tests_written or ["unit_tests/fixture/test_foo.py"],
        "red_baseline_verified": True,
    }


def coder_ok_response() -> dict[str, Any]:
    return {"status": "ok", "message": "implemented"}


def red_baseline_gate_response(
    *,
    gate_passed: bool,
    applicable: bool = True,
    verified: bool | None = None,
    reason: str | None = None,
    refused: list[dict] | None = None,
    red: list[dict] | None = None,
) -> dict[str, Any]:
    """label_responses[RED_BASELINE_GATE_LABEL] value.

    Shaped as {"output": "<json text>", "exit_code": N} -- the SAME
    "run a shell command, return its raw stdout + exit code" envelope
    build-feature.js already uses for its other status-checker-executed shell
    commands (see readTicketRecordBack's sibling repo-facts calls). The
    JSON *text* inside "output" is heavy_lane_gate's own pinned reply shape
    (see test_tq500f3ii_heavy_lane_gate_subcommand.py): gate_passed plus the
    applicable/verified wrapper keys and every verify_red_baseline verdict
    field.

    Args:
        gate_passed: Whether the gate passed.
        applicable: Whether there was a source requirement to gate against
            at all. Defaults to True (the normal K1/K2 shape); a caller
            building the K3 "no source_ac" shape directly (most tests
            instead skip dispatching the gate for K3 -- see
            test_build_feature_records_reader_not_applicable_for_ticket_without_source_ac)
            would pass False.
        verified: Whether the gate positively verified a real red. Defaults
            to ``applicable and gate_passed`` when not given -- the natural
            reading of heavy_lane_gate's own pinned contract.
    """
    if verified is None:
        verified = applicable and gate_passed
    payload: dict[str, Any] = {
        "gate_passed": gate_passed,
        "applicable": applicable,
        "verified": verified,
        "reason": reason,
        "red": red or [],
        "green_at_baseline": [],
        "inconclusive": [],
        "preexisting": [],
        "refused": refused or [],
    }
    if not applicable:
        payload["outcome"] = "red-baseline reader not applicable: no source requirement"
    return {"output": json.dumps(payload), "exit_code": 0 if gate_passed else 1}


def base_label_responses(
    *,
    ticket_path: str,
    worktree_path: str,
    ordered_phases: list[dict[str, str]],
    source_ac: str | list[str] | None,
    gate_response: dict[str, Any] | None = None,
    coder_agent: str = "python-coder",
    has_test_requirements: bool = True,
) -> dict[str, Any]:
    """Full label_responses dict to drive one ticket through
    resolve-target -> worktree-setup -> ticket-planner -> test-writer ->
    [red-baseline-gate] -> <coder_agent>.
    """
    responses: dict[str, Any] = {
        "resolve-target": resolve_target_response(ticket_path, worktree_path),
        "worktree-facts-resolved": WORKTREE_FACTS_RESOLVED,
        "worktree-setup": worktree_setup_response(worktree_path),
        "ticket-planner": ticket_planner_response(
            ticket_path,
            ordered_phases,
            source_ac=source_ac,
            has_test_requirements=has_test_requirements,
        ),
        "signoff-readback": signoff_readback_response(),
        "test-writer": test_writer_claims_red_response(),
        coder_agent: coder_ok_response(),
    }
    if gate_response is not None:
        responses[RED_BASELINE_GATE_LABEL] = gate_response
    return responses


def calls_with_label(result, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def first_index_with_label(result, label: str) -> int | None:
    for i, c in enumerate(result.agent_calls):
        if c.label == label:
            return i
    return None


def first_index_with_agent_type_in(result, agent_types: set[str]) -> int | None:
    for i, c in enumerate(result.agent_calls):
        if c.agent_type in agent_types:
            return i
    return None


def extract_gate_invocation(prompt: str) -> str | None:
    """Extract the 'python3 ... fast_lane.py heavy_lane_gate|verify_red_baseline
    ...' command line embedded in a captured dispatch prompt, or None if absent.
    """
    match = _GATE_INVOCATION_RE.search(prompt or "")
    return match.group(0) if match else None
