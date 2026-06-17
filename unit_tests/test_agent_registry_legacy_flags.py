"""
MODULE: test_agent_registry_legacy_flags
GOAL: Unit tests verifying that epic-supervisor and ticket-supervisor are
    marked as legacy_only in agent_registry.json, and that their template
    files still exist (not deleted).
TICKET: EPIC-FlattenSupervisorChain/06_deprecate_supervisors.md

Tests run without invoking Claude Code — they validate the registry JSON
directly and assert file presence.
"""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Resolve paths relative to the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"
_EPIC_SUPERVISOR_TEMPLATE = _REPO_ROOT / "templates" / "agents" / "epic-supervisor.md"
_TICKET_SUPERVISOR_TEMPLATE = _REPO_ROOT / "templates" / "agents" / "ticket-supervisor.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_registry() -> dict:
    """Load and parse agent_registry.json."""
    assert _REGISTRY_PATH.exists(), f"agent_registry.json not found at {_REGISTRY_PATH}"
    with _REGISTRY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _find_agent(registry: dict, agent_id: str) -> dict:
    """Return the registry entry for agent_id, or raise AssertionError."""
    agents = registry.get("agents", [])
    for entry in agents:
        if entry.get("id") == agent_id:
            return entry
    raise AssertionError(
        f"Agent '{agent_id}' not found in agent_registry.json. "
        f"Available IDs: {[e.get('id') for e in agents]}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_epic_supervisor_has_legacy_only_flag():
    """epic-supervisor entry in agent_registry.json must have legacy_only == True."""
    registry = _load_registry()
    entry = _find_agent(registry, "epic-supervisor")
    assert entry.get("legacy_only") is True, (
        f"Expected epic-supervisor to have 'legacy_only': true in agent_registry.json, "
        f"but got: {entry.get('legacy_only')!r}"
    )


def test_epic_supervisor_has_deprecated_flag():
    """epic-supervisor entry must also retain the existing deprecated == True flag."""
    registry = _load_registry()
    entry = _find_agent(registry, "epic-supervisor")
    assert entry.get("deprecated") is True, (
        f"Expected epic-supervisor to have 'deprecated': true in agent_registry.json, "
        f"but got: {entry.get('deprecated')!r}"
    )


def test_ticket_supervisor_has_legacy_only_flag():
    """ticket-supervisor entry in agent_registry.json must have legacy_only == True."""
    registry = _load_registry()
    entry = _find_agent(registry, "ticket-supervisor")
    assert entry.get("legacy_only") is True, (
        f"Expected ticket-supervisor to have 'legacy_only': true in agent_registry.json, "
        f"but got: {entry.get('legacy_only')!r}"
    )


def test_legacy_agents_still_have_template_files():
    """Both supervisor template files must still exist (not deleted)."""
    assert _EPIC_SUPERVISOR_TEMPLATE.exists(), (
        f"epic-supervisor template not found at {_EPIC_SUPERVISOR_TEMPLATE}. "
        "Template files must not be deleted — they remain for backward compatibility."
    )
    assert _TICKET_SUPERVISOR_TEMPLATE.exists(), (
        f"ticket-supervisor template not found at {_TICKET_SUPERVISOR_TEMPLATE}. "
        "Template files must not be deleted — they remain for backward compatibility."
    )


def test_epic_supervisor_template_has_deprecation_notice():
    """epic-supervisor template body must contain the legacy-mode deprecation notice."""
    assert _EPIC_SUPERVISOR_TEMPLATE.exists(), (
        f"Template not found: {_EPIC_SUPERVISOR_TEMPLATE}"
    )
    content = _EPIC_SUPERVISOR_TEMPLATE.read_text(encoding="utf-8")
    assert "Legacy agent" in content, (
        "epic-supervisor.md template is missing the 'Legacy agent' deprecation notice. "
        "Expected the '[!NOTE]' callout block inserted by ticket 06."
    )
    assert "build-epic.js" in content, (
        "epic-supervisor.md template must reference 'build-epic.js' in its deprecation notice."
    )


def test_ticket_supervisor_template_has_deprecation_notice():
    """ticket-supervisor template body must contain the legacy-mode deprecation notice."""
    assert _TICKET_SUPERVISOR_TEMPLATE.exists(), (
        f"Template not found: {_TICKET_SUPERVISOR_TEMPLATE}"
    )
    content = _TICKET_SUPERVISOR_TEMPLATE.read_text(encoding="utf-8")
    assert "Legacy agent" in content, (
        "ticket-supervisor.md template is missing the 'Legacy agent' deprecation notice. "
        "Expected the '[!NOTE]' callout block inserted by ticket 06."
    )
    assert "build-ticket.js" in content, (
        "ticket-supervisor.md template must reference 'build-ticket.js' in its deprecation notice."
    )
