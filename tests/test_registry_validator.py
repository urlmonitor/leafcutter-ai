"""
MODULE: test_registry_validator
GOAL: Unit tests for registry_validator.py — core validation (missing file,
    orphan templates, orphan entries, self-loops, load helpers).
BUSINESS CONTEXT: Verifies that validate_agent_registry() correctly detects
    orphan templates, orphan registry entries, self-loops, and that
    load_registry / get_ticket_phase_agents return correct subsets. Bidirectional
    spawn consistency tests live in test_registry_validator_bidir.py.
ARCHITECTURE: Standard unittest. No database, no network. Uses
    tempfile.TemporaryDirectory for all mock package layouts. Helpers shared
    via _registry_test_helpers imported at module level.
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
    spec = importlib.util.spec_from_file_location("registry_validator", _VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load registry_validator.py from {_VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_validator = _load_validator()
validate_agent_registry = _validator.validate_agent_registry
load_registry = _validator.load_registry
get_ticket_phase_agents = _validator.get_ticket_phase_agents
validate_verification_flags = _validator.validate_verification_flags


def _make_package(tmp: Path, registry: dict, templates: list[str]) -> Path:
    """Build a minimal mock package layout in tmp.

    Args:
        tmp: Temporary directory root.
        registry: Dict to write as agent_registry.json.
        templates: List of template stem names (without .md) to create.

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
           spawned_by: list[str] | None = None,
           portable: bool = True,
           skills_used: list[str] | None = None) -> dict:
    """Return a minimal valid agent dict for testing.

    Args:
        id_: The agent ID.
        is_ticket_phase: Whether the agent is a ticket phase agent.
        spawn_allowlist: Explicit allowlist; defaults to [].
        spawned_by: Explicit spawned_by; defaults to [].
        portable: Whether the agent is portable; defaults to True.
        skills_used: List of skill IDs; defaults to [].

    Returns:
        Dict compatible with agent_registry.schema.json.
    """
    return {
        "id": id_, "name": id_.title(), "tier": "phase",
        "role": "coding", "portable": portable, "domain": None,
        "spawn_allowlist": spawn_allowlist or [],
        "spawned_by": spawned_by or [],
        "is_ticket_phase": is_ticket_phase,
        "selection_criteria": None,
        "template_path": f"templates/agents/{id_}.md",
        "skills_used": skills_used if skills_used is not None else [],
    }


class TestMissingFile(unittest.TestCase):
    """validate_agent_registry handles missing or malformed registry."""

    def test_missing_registry(self):
        """Error reported when agent_registry.json does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            errors = validate_agent_registry(Path(tmp))
            self.assertEqual(len(errors), 1)
            self.assertIn("agent_registry.json not found", errors[0])

    def test_invalid_json(self):
        """Error reported when agent_registry.json is malformed JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config").mkdir()
            (Path(tmp) / "config" / "agent_registry.json").write_text(
                "{ bad json }", encoding="utf-8"
            )
            errors = validate_agent_registry(Path(tmp))
            self.assertEqual(len(errors), 1)
            self.assertIn("not valid JSON", errors[0])


class TestCleanRegistry(unittest.TestCase):
    """validate_agent_registry returns [] for consistent registries."""

    def test_clean(self):
        """No errors for matching templates and consistent spawn graph."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("a", spawn_allowlist=["b"], spawned_by=["supervisor"])
            b = _agent("b", spawn_allowlist=[], spawned_by=["a"])
            sup = _agent("supervisor", is_ticket_phase=False,
                         spawn_allowlist=["a"], spawned_by=["user"])
            registry = {"agents": [a, b, sup]}
            _make_package(Path(tmp), registry, ["a", "b", "supervisor"])
            errors = validate_agent_registry(Path(tmp))
            self.assertEqual(errors, [], errors)


class TestOrphanTemplate(unittest.TestCase):
    """validate_agent_registry detects orphan template files."""

    def test_orphan_template(self):
        """Error for template file with no registry entry."""
        with tempfile.TemporaryDirectory() as tmp:
            registry = {"agents": [_agent("agent-a")]}
            _make_package(Path(tmp), registry, ["agent-a", "orphan-agent"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("orphan-agent" in e for e in errors))

    def test_partial_skipped(self):
        """Template files starting with _ are not required in registry."""
        with tempfile.TemporaryDirectory() as tmp:
            registry = {"agents": [_agent("agent-a")]}
            _make_package(Path(tmp), registry, ["agent-a", "_signoff_block"])
            errors = validate_agent_registry(Path(tmp))
            self.assertFalse(any("_signoff_block" in e for e in errors))


class TestOrphanEntry(unittest.TestCase):
    """validate_agent_registry detects registry entries with missing templates."""

    def test_orphan_entry(self):
        """Error for registry entry whose template_path does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            registry = {"agents": [_agent("agent-a")]}
            (Path(tmp) / "config").mkdir()
            (Path(tmp) / "config" / "agent_registry.json").write_text(
                json.dumps(registry), encoding="utf-8"
            )
            (Path(tmp) / "templates" / "agents").mkdir(parents=True)
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("does not exist" in e for e in errors))


class TestSelfLoop(unittest.TestCase):
    """validate_agent_registry catches self-loops in spawn graph."""

    def test_self_loop(self):
        """Error reported when agent lists itself in spawn_allowlist."""
        with tempfile.TemporaryDirectory() as tmp:
            a = _agent("agent-a", spawn_allowlist=["agent-a"])
            _make_package(Path(tmp), {"agents": [a]}, ["agent-a"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(any("self-loop" in e for e in errors))


class TestLoadHelpers(unittest.TestCase):
    """load_registry and get_ticket_phase_agents behave correctly."""

    def test_load_registry_returns_list(self):
        """load_registry returns the agents array from a valid registry."""
        with tempfile.TemporaryDirectory() as tmp:
            registry = {"agents": [_agent("agent-a")]}
            _make_package(Path(tmp), registry, ["agent-a"])
            result = load_registry(Path(tmp))
            self.assertEqual(len(result), 1)

    def test_load_registry_empty_on_missing(self):
        """load_registry returns [] when file does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_registry(Path(tmp)), [])

    def test_phase_agents_filtered(self):
        """get_ticket_phase_agents returns only is_ticket_phase=True agents."""
        with tempfile.TemporaryDirectory() as tmp:
            phase = _agent("phase", is_ticket_phase=True)
            util = _agent("util", is_ticket_phase=False)
            _make_package(Path(tmp), {"agents": [phase, util]}, ["phase", "util"])
            result = get_ticket_phase_agents(Path(tmp))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], "phase")


class TestSkillsUsed(unittest.TestCase):
    """validate_agent_registry validates skills_used against templates/skills/."""

    def test_valid_skills_used_passes(self):
        """No error when skills_used references an existing skill directory."""
        with tempfile.TemporaryDirectory() as tmp:
            agent = _agent("agent-a", skills_used=["my-skill"])
            _make_package(Path(tmp), {"agents": [agent]}, ["agent-a"])
            # Create the skill directory
            (Path(tmp) / "templates" / "skills" / "my-skill").mkdir(parents=True)
            errors = validate_agent_registry(Path(tmp))
            self.assertEqual(errors, [], errors)

    def test_missing_skill_dir_reports_error(self):
        """Error when skills_used references a non-existent skill directory."""
        with tempfile.TemporaryDirectory() as tmp:
            agent = _agent("agent-a", skills_used=["nonexistent-skill"])
            _make_package(Path(tmp), {"agents": [agent]}, ["agent-a"])
            errors = validate_agent_registry(Path(tmp))
            self.assertTrue(
                any("nonexistent-skill" in e for e in errors),
                f"Expected skill error, got: {errors}",
            )

    def test_domain_agent_skills_not_validated(self):
        """Domain agents' skills_used are not checked against templates/skills/."""
        with tempfile.TemporaryDirectory() as tmp:
            domain_agent = _agent(
                "domain-a", portable=False, skills_used=["domain-only-skill"]
            )
            _make_package(Path(tmp), {"agents": [domain_agent]}, ["domain-a"])
            errors = validate_agent_registry(Path(tmp))
            # Domain agent template not found is still expected (portable agents only check)
            # but the skill error should NOT appear
            self.assertFalse(
                any("domain-only-skill" in e for e in errors),
                f"Domain skill should not be validated: {errors}",
            )

    def test_empty_skills_used_passes(self):
        """Empty skills_used array does not cause errors."""
        with tempfile.TemporaryDirectory() as tmp:
            agent = _agent("agent-a", skills_used=[])
            _make_package(Path(tmp), {"agents": [agent]}, ["agent-a"])
            errors = validate_agent_registry(Path(tmp))
            self.assertEqual(errors, [], errors)


class TestVerificationFlags(unittest.TestCase):
    """validate_verification_flags tests for Edit/Write requires_verification."""

    def test_missing_flag_on_edit_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir = Path(tmp) / "templates" / "agents"
            tmpl_dir.mkdir(parents=True)
            (tmpl_dir / "agent.md").write_text("---\ntools: [Edit]\n---\n", encoding="utf-8")
            errors = validate_verification_flags(tmpl_dir)
            self.assertEqual(len(errors), 1)
            self.assertIn("lacks requires_verification: true", errors[0])

    def test_flag_on_readonly_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir = Path(tmp) / "templates" / "agents"
            tmpl_dir.mkdir(parents=True)
            (tmpl_dir / "agent.md").write_text("---\ntools: [Read, Bash]\nrequires_verification: true\n---\n", encoding="utf-8")
            errors = validate_verification_flags(tmpl_dir)
            self.assertEqual(len(errors), 1)
            self.assertIn("lacks Edit/Write in tools", errors[0])

    def test_bash_missing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir = Path(tmp) / "templates" / "agents"
            tmpl_dir.mkdir(parents=True)
            (tmpl_dir / "agent.md").write_text("---\ntools: [Edit]\nrequires_verification: true\n---\n", encoding="utf-8")
            errors = validate_verification_flags(tmpl_dir)
            self.assertEqual(len(errors), 1)
            self.assertIn("lacks Bash in tools", errors[0])

    def test_valid_flag_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir = Path(tmp) / "templates" / "agents"
            tmpl_dir.mkdir(parents=True)
            (tmpl_dir / "agent.md").write_text("---\ntools: [Edit, Bash]\nrequires_verification: true\n---\n", encoding="utf-8")
            errors = validate_verification_flags(tmpl_dir)
            self.assertEqual(errors, [])


class TestRealRegistry(unittest.TestCase):
    """Smoke test: validate the actual agent_registry.json."""

    def test_real_registry_is_valid(self):
        """The actual agent_registry.json should pass all validation checks."""
        package_root = _REPO_ROOT
        if not package_root.exists():
            self.skipTest(f"leafcutter not found at {package_root}")
        errors = validate_agent_registry(package_root)
        self.assertEqual(errors, [], "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
