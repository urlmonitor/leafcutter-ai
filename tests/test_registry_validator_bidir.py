"""
MODULE: test_registry_validator_bidir
GOAL: Bidirectional spawn consistency tests for registry_validator.py.
BUSINESS CONTEXT: Verifies that validate_agent_registry() correctly detects
    spawn_allowlist / spawned_by mismatches, unknown agent references, and
    that special tokens (__ticket_phase_agents__, 'user') are handled correctly.
    Core validation tests (orphan templates, self-loops, load helpers) live
    in test_registry_validator.py.
ARCHITECTURE: Standard unittest. No database, no network. Uses
    tempfile.TemporaryDirectory for all mock package layouts. Mirrors the
    helper pattern from test_registry_validator.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_VALIDATOR_PATH = _SCRIPTS_DIR / "registry_validator.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_validator():
    """Load registry_validator.py as a module without side-effects.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location("registry_validator_bidir", _VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load registry_validator.py from {_VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_validator = _load_validator()
validate_agent_registry = _validator.validate_agent_registry


def _make_package(tmp: Path, registry: dict, templates: list[str]) -> Path:
    """Build a minimal mock package layout in tmp.

    Args:
        tmp: Temporary directory root.
        registry: Dict to write as agent_registry.json.
        templates: List of template stem names to create.

    Returns:
        Path to the package root.
    """
    config_dir = tmp / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "agent_registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    templates_dir = tmp / "templates" / "agents"
    templates_dir.mkdir(parents=True, exist_ok=True)
    for stem in templates:
        (templates_dir / f"{stem}.md").write_text(f"# {stem}", encoding="utf-8")
    return tmp


def _agent(id_: str, *, is_ticket_phase: bool = True,
           spawn_allowlist: list[str] | None = None,
           spawned_by: list[str] | None = None) -> dict:
    """Return a minimal valid agent dict for testing.

    Args:
        id_: The agent ID.
        is_ticket_phase: Whether the agent is a ticket phase agent.
        spawn_allowlist: Explicit allowlist; defaults to [].
        spawned_by: Explicit spawned_by; defaults to [].

    Returns:
        Dict compatible with agent_registry.schema.json.
    """
    return {
        "id": id_, "name": id_.title(), "tier": "phase",
        "role": "coding", "portable": True, "domain": None,
        "spawn_allowlist": spawn_allowlist or [],
        "spawned_by": spawned_by or [],
        "is_ticket_phase": is_ticket_phase,
        "selection_criteria": None,
        "template_path": f"templates/agents/{id_}.md",
        "skills_used": [],
    }


class TestBidirectionalMismatch(unittest.TestCase):
    """validate_agent_registry catches spawn_allowlist / spawned_by mismatches."""

    def test_allowlist_without_spawned_by(self):
        """Error when A lists B in spawn_allowlist but B omits A from spawned_by."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("a", spawn_allowlist=["b"], spawned_by=[])
            b = _agent("b", spawn_allowlist=[], spawned_by=[])  # Missing "a"
            _make_package(Path(tmp), {"agents": [a, b]}, ["a", "b"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("Bidirectional mismatch" in e for e in errors))

    def test_spawned_by_without_allowlist(self):
        """Error when B lists A in spawned_by but A omits B from spawn_allowlist."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("a", spawn_allowlist=[], spawned_by=[])  # Missing "b"
            b = _agent("b", spawn_allowlist=[], spawned_by=["a"])
            _make_package(Path(tmp), {"agents": [a, b]}, ["a", "b"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("Bidirectional mismatch" in e for e in errors))

    def test_unknown_in_allowlist(self):
        """Error when spawn_allowlist references an unknown agent ID."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("a", spawn_allowlist=["does-not-exist"], spawned_by=[])
            _make_package(Path(tmp), {"agents": [a]}, ["a"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("unknown agent" in e for e in errors))

    def test_unknown_in_spawned_by(self):
        """Error when spawned_by references an unknown agent ID."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("a", spawn_allowlist=[], spawned_by=["does-not-exist"])
            _make_package(Path(tmp), {"agents": [a]}, ["a"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("unknown agent" in e for e in errors))


class TestSpecialTokens(unittest.TestCase):
    """Special tokens and external callers are handled correctly."""

    def test_user_in_spawned_by_is_allowed(self):
        """'user' in spawned_by should not trigger a bidirectional error."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("a", spawn_allowlist=[], spawned_by=["user"])
            _make_package(Path(tmp), {"agents": [a]}, ["a"])
            errors = validate_agent_registry(Path(tmp))
            self.assertFalse(any("user" in e for e in errors))

    def test_special_token_skip(self):
        """__ticket_phase_agents__ in spawn_allowlist does not trigger errors."""
        with tempfile.TemporaryDirectory() as tmp:
            supervisor = _agent(
                "ticket-supervisor", is_ticket_phase=False,
                spawn_allowlist=["__ticket_phase_agents__"],
                spawned_by=["epic-supervisor"],
            )
            epic = _agent(
                "epic-supervisor", is_ticket_phase=False,
                spawn_allowlist=["ticket-supervisor"],
                spawned_by=["user"],
            )
            _make_package(
                Path(tmp),
                {"agents": [supervisor, epic]},
                ["ticket-supervisor", "epic-supervisor"],
            )
            errors = validate_agent_registry(Path(tmp))
            self.assertFalse(any("__ticket_phase_agents__" in e for e in errors))

    def test_clean_with_special_token(self):
        """Registry with __ticket_phase_agents__ passes validation end-to-end."""
        with tempfile.TemporaryDirectory() as tmp:
            supervisor = _agent(
                "ticket-supervisor", is_ticket_phase=False,
                spawn_allowlist=["__ticket_phase_agents__"],
                spawned_by=["epic-supervisor"],
            )
            epic = _agent(
                "epic-supervisor", is_ticket_phase=False,
                spawn_allowlist=["ticket-supervisor"],
                spawned_by=["user"],
            )
            phase = _agent(
                "python-coder", is_ticket_phase=True,
                spawn_allowlist=[],
                spawned_by=["ticket-supervisor"],
            )
            _make_package(
                Path(tmp),
                {"agents": [supervisor, epic, phase]},
                ["ticket-supervisor", "epic-supervisor", "python-coder"],
            )
            errors = validate_agent_registry(Path(tmp))
            self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
