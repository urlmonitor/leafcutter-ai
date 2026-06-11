"""
MODULE: test_registry_no_version_suffix
GOAL: Verify that no agent id in config/agent_registry.json carries any version
    suffix (e.g. -v1, -v2, -v3, or any -vN pattern).
BUSINESS CONTEXT: AC ACD-1100b-3-i — after the v2.0 migration all legacy versioned
    agent ids were renamed to canonical names. This test is the standing guard that
    prevents regression: any new agent added with a version suffix will fail immediately
    rather than silently violating the naming convention.
ARCHITECTURE: Read-only test; loads agent_registry.json from the repo root and asserts
    against the in-memory data structure. No network access, no DB, no side-effects.
    Follows the same repo-root-relative path resolution pattern as
    test_agent_registry_legacy_flags.py.

TICKET: EPIC-AcPipelineConsolidation/07_TICKET-20260610-ACD-1100b-3-i.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"

# Pattern covering the three explicit substrings and the general /-v[0-9]+$/ suffix
_VERSION_SUBSTRINGS = ("-v1", "-v2", "-v3")
_VERSION_SUFFIX_RE = re.compile(r"-v[0-9]+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_registry() -> dict:
    """Load and parse agent_registry.json, asserting the file exists and is valid JSON."""
    assert _REGISTRY_PATH.exists(), (
        f"agent_registry.json not found at {_REGISTRY_PATH}. "
        "The file must exist for this test to run."
    )
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _extract_agent_ids(registry: dict) -> list[str]:
    """Return the list of all agent id values from the registry."""
    agents = registry.get("agents", [])
    return [entry.get("id", "") for entry in agents]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_registry_parses_as_valid_json():
    """The registry file must parse without errors (AC: 'registry remains valid JSON')."""
    registry = _load_registry()
    assert isinstance(registry, dict), (
        f"Expected agent_registry.json to deserialise to a dict, got {type(registry).__name__}"
    )
    assert "agents" in registry, (
        "agent_registry.json must contain an 'agents' key at the top level."
    )


def test_no_agent_id_has_trailing_version_suffix():
    """No agent id may match the pattern /-v[0-9]+$/ (no trailing version suffix)."""
    registry = _load_registry()
    agent_ids = _extract_agent_ids(registry)

    violations = [
        agent_id
        for agent_id in agent_ids
        if _VERSION_SUFFIX_RE.search(agent_id)
    ]

    assert not violations, (
        f"The following agent id(s) carry a trailing version suffix "
        f"(/-v[0-9]+$/) in violation of AC ACD-1100b-3-i: {violations}. "
        "Rename these agents to their canonical (unversioned) names."
    )


def test_no_agent_id_contains_v1_substring():
    """No agent id may contain the substring '-v1'."""
    registry = _load_registry()
    agent_ids = _extract_agent_ids(registry)

    violations = [
        agent_id for agent_id in agent_ids if "-v1" in agent_id
    ]

    assert not violations, (
        f"The following agent id(s) contain the forbidden substring '-v1': {violations}. "
        "Rename these agents to their canonical (unversioned) names."
    )


def test_no_agent_id_contains_v2_substring():
    """No agent id may contain the substring '-v2'."""
    registry = _load_registry()
    agent_ids = _extract_agent_ids(registry)

    violations = [
        agent_id for agent_id in agent_ids if "-v2" in agent_id
    ]

    assert not violations, (
        f"The following agent id(s) contain the forbidden substring '-v2': {violations}. "
        "Rename these agents to their canonical (unversioned) names."
    )


def test_no_agent_id_contains_v3_substring():
    """No agent id may contain the substring '-v3'."""
    registry = _load_registry()
    agent_ids = _extract_agent_ids(registry)

    violations = [
        agent_id for agent_id in agent_ids if "-v3" in agent_id
    ]

    assert not violations, (
        f"The following agent id(s) contain the forbidden substring '-v3': {violations}. "
        "Rename these agents to their canonical (unversioned) names."
    )


def test_all_agent_ids_are_non_empty_strings():
    """Every entry in the agents array must have a non-empty string id field."""
    registry = _load_registry()
    agents = registry.get("agents", [])

    missing_ids = [
        idx
        for idx, entry in enumerate(agents)
        if not isinstance(entry.get("id"), str) or not entry.get("id")
    ]

    assert not missing_ids, (
        f"The following agent entries (by index) are missing a non-empty 'id' field: "
        f"{missing_ids}. Every agent must have a valid id."
    )


def test_version_suffix_invariant_covers_all_explicit_substrings():
    """
    Combined regression guard: asserts that none of the three explicit version
    substrings (-v1, -v2, -v3) appears in any agent id. This is the union of
    test_no_agent_id_contains_v1/v2/v3_substring run in a single parametrised
    assertion for completeness.
    """
    registry = _load_registry()
    agent_ids = _extract_agent_ids(registry)

    all_violations: dict[str, list[str]] = {}
    for substr in _VERSION_SUBSTRINGS:
        hits = [aid for aid in agent_ids if substr in aid]
        if hits:
            all_violations[substr] = hits

    assert not all_violations, (
        f"Version-suffix invariant violated. "
        f"Agent id(s) containing forbidden substrings: {all_violations}"
    )
