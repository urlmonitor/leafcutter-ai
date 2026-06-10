"""
MODULE: test_frontend_coder_llm_trigger
GOAL: Regression test verifying that the frontend-coder agent has an LLM-type
    trigger condition in agent_registry.json that fires for tickets describing
    UI work even when files_touched contains only non-frontend extensions.

AC reference: BP-700b-2-i (07_TICKET-20260608-BP-700b-2-i.md)

Gherkin scenario:
    Given a ticket has files_touched containing only ".ts" files (not .tsx)
    But the ticket body says "create a React component for the settings page"
    When the dispatch system evaluates the unified frontend agent's trigger conditions
    Then the LLM-type trigger condition fires (matching "ticket involves creating
        or modifying frontend/UI components, markup, or styles")
    And the dispatch system does not rely solely on the DSL file-extension check

Tests run without invoking Claude Code — they validate the registry JSON directly
and assert that LLM trigger conditions are present and correctly structured.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Resolve paths relative to the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_registry() -> dict:
    """Load and parse agent_registry.json."""
    assert _REGISTRY_PATH.exists(), f"agent_registry.json not found at {_REGISTRY_PATH}"
    try:
        with _REGISTRY_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"Could not load agent_registry.json: {exc}")


def _find_agent(registry: dict, agent_id: str) -> dict:
    """Return the registry entry for agent_id, or fail with a clear message."""
    agents = registry.get("agents", [])
    for entry in agents:
        if entry.get("id") == agent_id:
            return entry
    available = [e.get("id") for e in agents]
    pytest.fail(
        f"Agent '{agent_id}' not found in agent_registry.json. "
        f"Available IDs: {available}"
    )


# ---------------------------------------------------------------------------
# Tests — AC BP-700b-2-i
# ---------------------------------------------------------------------------


def test_frontend_coder_has_llm_type_trigger():
    """
    # covers: BP-700b-2-i
    frontend-coder must have at least one trigger_condition of type 'llm'
    so the dispatch system can fire for UI-describing tickets regardless of
    whether files_touched contains frontend file extensions.

    AC: 'the LLM-type trigger condition fires'
    """
    # covers: BP-700b-2-i
    registry = _load_registry()
    entry = _find_agent(registry, "frontend-coder")

    selection_criteria = entry.get("selection_criteria", {})
    assert selection_criteria, (
        "frontend-coder registry entry must have a 'selection_criteria' block."
    )

    trigger_conditions = selection_criteria.get("trigger_conditions", [])
    assert trigger_conditions, (
        "frontend-coder 'selection_criteria' must have a 'trigger_conditions' list. "
        "The list is empty — add DSL and LLM trigger entries."
    )

    llm_triggers = [t for t in trigger_conditions if t.get("type") == "llm"]
    assert llm_triggers, (
        "frontend-coder must have at least one trigger_condition with type='llm'. "
        "The DSL-only check cannot fire when files_touched contains only '.ts' files. "
        f"Current trigger_conditions: {trigger_conditions}"
    )


def test_frontend_coder_llm_trigger_covers_ui_component_work():
    """
    # covers: BP-700b-2-i
    The LLM trigger expression must explicitly cover 'creating or modifying
    frontend/UI components, markup, or styles' — matching the AC scenario:
    'ticket body says create a React component for the settings page'.
    """
    # covers: BP-700b-2-i
    registry = _load_registry()
    entry = _find_agent(registry, "frontend-coder")

    trigger_conditions = entry.get("selection_criteria", {}).get("trigger_conditions", [])
    llm_triggers = [t for t in trigger_conditions if t.get("type") == "llm"]

    assert llm_triggers, (
        "No LLM trigger conditions found — see test_frontend_coder_has_llm_type_trigger."
    )

    # At least one LLM trigger must reference UI component / frontend work.
    # Expected expression: "ticket involves creating or modifying frontend/UI
    # components, markup, or styles"
    ui_keywords = ["frontend", "UI", "component", "markup", "styles", "interface"]
    expressions = [t.get("expression", "") for t in llm_triggers]

    matching = [
        expr for expr in expressions
        if any(kw.lower() in expr.lower() for kw in ui_keywords)
    ]
    assert matching, (
        "At least one LLM trigger condition must reference UI component or frontend work "
        "(expected keywords: frontend, UI, component, markup, styles, interface). "
        f"LLM trigger expressions found: {expressions}"
    )


def test_frontend_coder_has_dsl_trigger_for_file_extensions():
    """
    # covers: BP-700b-2-i
    The DSL trigger must be present (for cases where files_touched DOES contain
    frontend extensions) — but it is NOT the sole dispatch mechanism.

    AC: 'the dispatch system does not rely solely on the DSL file-extension check'
    This test ensures BOTH DSL and LLM triggers are present, proving the system
    is not DSL-only.
    """
    # covers: BP-700b-2-i
    registry = _load_registry()
    entry = _find_agent(registry, "frontend-coder")

    trigger_conditions = entry.get("selection_criteria", {}).get("trigger_conditions", [])

    dsl_triggers = [t for t in trigger_conditions if t.get("type") == "dsl"]
    llm_triggers = [t for t in trigger_conditions if t.get("type") == "llm"]

    assert dsl_triggers, (
        "frontend-coder must have at least one DSL trigger for file-extension matching. "
        f"Current triggers: {trigger_conditions}"
    )
    assert llm_triggers, (
        "frontend-coder must also have LLM triggers so the DSL is not the sole mechanism. "
        "AC BP-700b-2-i requires that the dispatch system does NOT rely solely on "
        "the DSL file-extension check."
    )
    # Assert both coexist — dual-mechanism dispatch
    assert len(dsl_triggers) >= 1 and len(llm_triggers) >= 1, (
        f"Expected both DSL and LLM triggers; found DSL={len(dsl_triggers)}, "
        f"LLM={len(llm_triggers)}."
    )


def test_frontend_coder_dsl_trigger_does_not_include_ts():
    """
    # covers: BP-700b-2-i
    The DSL trigger must NOT include plain '.ts' files — only frontend-specific
    extensions (.tsx, .jsx, .vue, .svelte, .html, .css, .scss).

    AC Given clause: 'a ticket has files_touched containing only ".ts" files (not .tsx)'
    — this scenario should NOT trigger the DSL check.
    """
    # covers: BP-700b-2-i
    registry = _load_registry()
    entry = _find_agent(registry, "frontend-coder")

    trigger_conditions = entry.get("selection_criteria", {}).get("trigger_conditions", [])
    dsl_triggers = [t for t in trigger_conditions if t.get("type") == "dsl"]

    for dsl in dsl_triggers:
        expression = dsl.get("expression", "")
        # The DSL expression must not include standalone '.ts' (TypeScript) —
        # only .tsx (TypeScript JSX) should be included.
        # Simple check: if '.ts' appears it must be part of '.tsx', not standalone.
        has_standalone_ts = (
            "*.ts " in expression
            or "*.ts\n" in expression
            or expression.strip().endswith("*.ts")
            or "contains *.ts " in expression
        )
        assert not has_standalone_ts, (
            "The DSL trigger expression includes '*.ts' (plain TypeScript files). "
            "This would incorrectly trigger frontend-coder for back-end TypeScript work. "
            "Only '.tsx' (TypeScript JSX) should be in the DSL trigger. "
            f"Expression: {expression}"
        )


def test_frontend_coder_default_status_is_not_needed():
    """
    # covers: BP-700b-2-i
    The default_status for frontend-coder must be 'not_needed', meaning the
    agent is only dispatched when a trigger condition evaluates to true.

    Without a default_status of 'not_needed', the LLM trigger mechanism is
    irrelevant because the agent would always be dispatched.
    """
    # covers: BP-700b-2-i
    registry = _load_registry()
    entry = _find_agent(registry, "frontend-coder")

    selection_criteria = entry.get("selection_criteria", {})
    default_status = selection_criteria.get("default_status")

    assert default_status == "not_needed", (
        f"frontend-coder 'selection_criteria.default_status' must be 'not_needed' "
        f"so it is only dispatched when a trigger fires. "
        f"Current value: {default_status!r}"
    )


# ---------------------------------------------------------------------------
# DECISION HISTORY
# ---------------------------------------------------------------------------
# - 2026-06-10 [ticket-supervisor/EPIC-Oneagenthandlesboththelookandthecodefor/07]:
#   Tests written to verify AC BP-700b-2-i: LLM trigger fires for tickets
#   describing UI work without frontend file extensions in files_touched.
#   Five tests cover: LLM trigger presence, UI-covering expression, dual-mechanism
#   dispatch (not DSL-only), .ts exclusion from DSL, and default_status=not_needed.
# ---------------------------------------------------------------------------
