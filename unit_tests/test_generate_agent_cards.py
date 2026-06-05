"""
MODULE: test_generate_agent_cards
GOAL: Unit tests for the generate_agent_cards.py module (INF-600b).
      Tests are written BEFORE implementation (TDD red-baseline).
TICKET: EPIC-SelfDescribingAgents/02-card-generator.md
COVERS: INF-600b
"""

from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Fixtures — shared template and registry data
# ---------------------------------------------------------------------------

# Post-Ticket-1 python-coder template frontmatter (fully-populated agent)
PYTHON_CODER_TEMPLATE_FM = {
    "name": "python-coder",
    "description": "Standards-enforcing Python implementation agent.",
    "model": "sonnet",
    "tools": "Bash, Read, Edit, Write, Agent",
    "portable": True,
    "signoff": True,
    "config_keys": {
        "test_command_live_trader": {"required": False},
        "test_output_dir": {"required": False},
        "collector_enforcer_paths": {"required": False},
    },
    "inputs": [
        {"name": "ticket_path", "type": "path", "description": "Path to ticket .md file"},
        {"name": "ticket body", "type": "markdown", "description": "ACs, Implementation Tasks, Agent Contracts"},
    ],
    "outputs": [
        {"name": "Edited/new .py files", "type": "file", "description": "Python implementation files"},
        {"name": "Sign-off comment", "type": "comment", "description": "status: ok | handoff | blocker"},
    ],
    "mutates": [
        {"name": "Ticket frontmatter", "type": "file", "description": "agents.python-coder: signed_off | failed"},
    ],
    "pre_flight_reads": [
        "ticket body",
        "cited ADRs",
        "docs/conventions/*.md",
    ],
    "behavioral_patterns": [
        {
            "name": "Contract-Aware Mode",
            "trigger": "Ticket has ## Agent Contracts with ### python-coder",
            "behavior": "Contract becomes primary spec, superseding Implementation Tasks.",
            "related_agent": "ticket-supervisor",
        },
        {
            "name": "Stop-and-Ask (SQL)",
            "trigger": "Task requires .sql edits",
            "behavior": "Halts immediately; defers to sql-coder.",
            "related_agent": "sql-coder",
        },
    ],
    "skills_invoked": [
        {"skill_id": "signoff", "mode": "always"},
        {"skill_id": "doc-enforcer", "mode": "always"},
        {"skill_id": "complexity-reduction", "mode": "conditional", "condition": "when flagged"},
        {"skill_id": "collector-enforcer", "mode": "conditional", "condition": "when paths under collector/"},
    ],
}

# Post-Ticket-1 python-coder registry entry
PYTHON_CODER_REGISTRY = {
    "id": "python-coder",
    "name": "Python Coder",
    "tier": "phase",
    "priority": 6,
    "is_ticket_phase": True,
    "model": "sonnet",
    "spawned_by": ["ticket-supervisor", "sql-coder"],
    "spawn_allowlist": ["research-agent", "test-runner"],
    "auto_dispatch": [
        {"type": "dsl", "expression": "files_touched contains *.py"},
        {"type": "llm", "expression": "ticket involves creating, modifying, or refactoring Python code"},
    ],
    "knowledge_channels": [
        {
            "channel": 1,
            "source": "Root CLAUDE.md",
            "injection_mode": "always",
            "description": "Project instructions, error handling policy, shell conventions",
        },
        {
            "channel": 8,
            "source": "Ticket frontmatter",
            "injection_mode": "ticket-scoped",
            "description": "Agents map, files_touched, depends_on, ACs, Agent Contracts section",
        },
    ],
    "skills_invoked": [
        {"skill_id": "signoff", "mode": "always"},
        {"skill_id": "doc-enforcer", "mode": "always"},
    ],
    "skills_used": ["signoff"],
}

# Minimal agent template frontmatter (pre-Ticket-5: no new structured fields)
MINIMAL_AGENT_FM = {
    "name": "minimal-agent",
    "description": "A minimal agent with only legacy fields.",
    "model": "sonnet",
    "tools": "Bash, Read",
    "portable": True,
    "signoff": True,
    "skills_used": ["signoff"],
}

MINIMAL_AGENT_REGISTRY = {
    "id": "minimal-agent",
    "name": "Minimal Agent",
    "tier": "phase",
    "priority": 6,
    "is_ticket_phase": True,
    "spawned_by": ["ticket-supervisor"],
    "spawn_allowlist": [],
    "skills_used": ["signoff"],
}


# ---------------------------------------------------------------------------
# Test 1 — Card generated for python-coder matches prototype sections
# ---------------------------------------------------------------------------

class TestCardGeneratedForPythonCoder(unittest.TestCase):
    """INF-600b: Agent cards produced by generator contain required sections."""

    def setUp(self):
        # covers: INF-600b
        # Import under test — will raise ImportError until python-coder implements it.
        from generate_agent_cards import generate_card  # noqa: F401
        self.generate_card = generate_card

    def test_card_generated_for_python_coder_matches_prototype_sections(self):
        # covers: INF-600b
        """INF-600b: Generated card for python-coder contains all required section headings."""
        result = self.generate_card(
            agent_id="python-coder",
            template_frontmatter=PYTHON_CODER_TEMPLATE_FM,
            registry_entry=PYTHON_CODER_REGISTRY,
        )
        required_sections = [
            "## When to Use",
            "## Knowledge Flow",
            "## Input / Output Contract",
            "## Skills Used",
            "## Configuration",
            "## Contributor Notes",
        ]
        for section in required_sections:
            self.assertIn(
                section,
                result,
                msg=f"Expected section '{section}' not found in generated card.",
            )

    def test_card_has_yaml_frontmatter(self):
        # covers: INF-600b
        """INF-600b: Generated card begins with YAML frontmatter block."""
        result = self.generate_card(
            agent_id="python-coder",
            template_frontmatter=PYTHON_CODER_TEMPLATE_FM,
            registry_entry=PYTHON_CODER_REGISTRY,
        )
        self.assertTrue(
            result.startswith("---"),
            msg="Card must begin with YAML frontmatter '---'.",
        )
        self.assertIn("agent_id: python-coder", result)
        self.assertIn("type: card", result)


# ---------------------------------------------------------------------------
# Test 2 — Minimal agent card (pre-Ticket-5 state, no new structured fields)
# ---------------------------------------------------------------------------

class TestCardGeneratedForMinimalAgent(unittest.TestCase):
    """INF-600b: Generator handles agents lacking new structured fields without error."""

    def setUp(self):
        # covers: INF-600b
        from generate_agent_cards import generate_card  # noqa: F401
        self.generate_card = generate_card

    def test_card_generated_for_minimal_agent(self):
        # covers: INF-600b
        """INF-600b: Generator produces a card for minimal agent without raising."""
        try:
            result = self.generate_card(
                agent_id="minimal-agent",
                template_frontmatter=MINIMAL_AGENT_FM,
                registry_entry=MINIMAL_AGENT_REGISTRY,
            )
        except (KeyError, AttributeError) as exc:
            self.fail(
                f"generate_card raised {type(exc).__name__} for a minimal agent: {exc}"
            )
        self.assertIn("## Skills Used", result)


# ---------------------------------------------------------------------------
# Test 3 — skills_invoked takes precedence over skills_used
# ---------------------------------------------------------------------------

class TestSkillsPrecedence(unittest.TestCase):
    """INF-600b: skills_invoked data wins over skills_used when both present."""

    def setUp(self):
        # covers: INF-600b
        from generate_agent_cards import generate_card  # noqa: F401
        self.generate_card = generate_card

    def test_skills_invoked_takes_precedence_over_skills_used(self):
        # covers: INF-600b
        """INF-600b: When both skills_invoked and skills_used are present, card uses skills_invoked."""
        fm = dict(PYTHON_CODER_TEMPLATE_FM)
        fm["skills_invoked"] = [{"skill_id": "signoff", "mode": "always"}, {"skill_id": "doc-enforcer", "mode": "always"}]

        registry = dict(PYTHON_CODER_REGISTRY)
        registry["skills_used"] = ["signoff"]  # legacy field
        registry["skills_invoked"] = fm["skills_invoked"]

        result = self.generate_card(
            agent_id="python-coder",
            template_frontmatter=fm,
            registry_entry=registry,
        )
        # The skills section should contain "doc-enforcer" (from skills_invoked)
        self.assertIn("doc-enforcer", result)
        # Should NOT double-list "signoff" — count occurrences in Skills section
        skills_section_start = result.find("## Skills Used")
        self.assertGreater(skills_section_start, -1, "Skills section must exist")
        skills_section = result[skills_section_start:]
        # Find next section boundary
        next_section = skills_section.find("## ", 3)
        if next_section > 0:
            skills_section = skills_section[:next_section]
        signoff_count = skills_section.count("signoff")
        self.assertLessEqual(
            signoff_count,
            1,
            msg="'signoff' appears more than once in Skills section — double-listing detected.",
        )


# ---------------------------------------------------------------------------
# Test 4 — Knowledge Flow table populated from registry knowledge_channels
# ---------------------------------------------------------------------------

class TestKnowledgeFlowTable(unittest.TestCase):
    """INF-600b: Knowledge Flow section contains table rows from knowledge_channels array."""

    def setUp(self):
        # covers: INF-600b
        from generate_agent_cards import generate_card  # noqa: F401
        self.generate_card = generate_card

    def test_knowledge_flow_table_populated_from_registry(self):
        # covers: INF-600b
        """INF-600b: Knowledge Flow table contains a row for each registry knowledge_channel."""
        registry = dict(PYTHON_CODER_REGISTRY)
        registry["knowledge_channels"] = [
            {
                "channel": 1,
                "source": "Root CLAUDE.md",
                "injection_mode": "always",
                "description": "Project instructions",
            }
        ]
        result = self.generate_card(
            agent_id="python-coder",
            template_frontmatter=PYTHON_CODER_TEMPLATE_FM,
            registry_entry=registry,
        )
        self.assertIn("## Knowledge Flow", result)
        # The table row should reference channel 1 or its source
        self.assertIn("Root CLAUDE.md", result)


# ---------------------------------------------------------------------------
# Test 5 — dry_run writes no files to docs/agents/cards/
# ---------------------------------------------------------------------------

class TestDryRunWritesNoFiles(unittest.TestCase):
    """INF-600b: With dry_run=True, no .card.md files are written."""

    def test_dry_run_writes_no_files(self):
        # covers: INF-600b
        """INF-600b: dry_run=True prevents any writes to docs/agents/cards/."""
        from generate_agent_cards import build_agent_cards  # noqa: F401

        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            # Create minimal template structure
            templates_dir = target_root / "templates" / "agents"
            templates_dir.mkdir(parents=True)
            # Create a minimal agent template file
            (templates_dir / "test-agent.md").write_text(
                "---\nname: test-agent\ndescription: Test.\nmodel: sonnet\ntools: Bash\n---\n",
                encoding="utf-8",
            )
            # Create minimal registry
            config_dir = target_root / "config"
            config_dir.mkdir(parents=True)
            import json
            (config_dir / "agent_registry.json").write_text(
                json.dumps([{"id": "test-agent", "name": "Test Agent", "tier": "phase", "spawned_by": [], "spawn_allowlist": [], "skills_used": []}]),
                encoding="utf-8",
            )

            written = build_agent_cards(
                target_root=target_root,
                config={},
                dry_run=True,
                force=False,
            )

            # In dry_run mode, no actual files should be written
            cards_dir = target_root / "docs" / "agents" / "cards"
            card_files = list(cards_dir.glob("*.card.md")) if cards_dir.exists() else []
            self.assertEqual(
                len(card_files),
                0,
                msg=f"dry_run=True must not write any files; found: {card_files}",
            )
            # But it should report what it would write (count > 0)
            self.assertGreater(
                written,
                0,
                msg="dry_run=True should still return count of files it would write.",
            )


# ---------------------------------------------------------------------------
# Test 6 — behavioral_patterns produce a table in Contributor Notes
# ---------------------------------------------------------------------------

class TestBehavioralPatternsTable(unittest.TestCase):
    """INF-600b: Contributor Notes section renders behavioral_patterns as a table."""

    def setUp(self):
        # covers: INF-600b
        from generate_agent_cards import generate_card  # noqa: F401
        self.generate_card = generate_card

    def test_behavioral_patterns_produce_table(self):
        # covers: INF-600b
        """INF-600b: behavioral_patterns array produces a markdown table row in Contributor Notes."""
        fm = dict(PYTHON_CODER_TEMPLATE_FM)
        fm["behavioral_patterns"] = [
            {
                "name": "Stop-and-Ask",
                "trigger": "Task requires SQL edits",
                "behavior": "Halts and defers to sql-coder",
                "related_agent": "sql-coder",
            }
        ]
        result = self.generate_card(
            agent_id="python-coder",
            template_frontmatter=fm,
            registry_entry=PYTHON_CODER_REGISTRY,
        )
        self.assertIn("## Contributor Notes", result)
        self.assertIn("Stop-and-Ask", result)

    def test_empty_behavioral_patterns_renders_no_conditional_behaviors_message(self):
        # covers: INF-600b
        """INF-600b: Empty behavioral_patterns renders the fallback no-behaviors message."""
        fm = dict(PYTHON_CODER_TEMPLATE_FM)
        fm["behavioral_patterns"] = []
        result = self.generate_card(
            agent_id="python-coder",
            template_frontmatter=fm,
            registry_entry=PYTHON_CODER_REGISTRY,
        )
        self.assertIn("## Contributor Notes", result)
        self.assertIn(
            "No conditional behaviors",
            result,
            msg=(
                "Empty behavioral_patterns must render fallback message "
                "'No conditional behaviors — this agent follows a single fixed execution path'"
            ),
        )


# ---------------------------------------------------------------------------
# Test 7 — build_agent_cards integration test
# ---------------------------------------------------------------------------

class TestBuildPhaseIntegration(unittest.TestCase):
    """INF-600b: build_agent_cards() returns written file count and creates card file."""

    def test_build_phase_integration(self):
        # covers: INF-600b
        """INF-600b: build_agent_cards returns integer count and card file exists after run."""
        from generate_agent_cards import build_agent_cards  # noqa: F401
        import json

        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            # Create minimal template
            templates_dir = target_root / "templates" / "agents"
            templates_dir.mkdir(parents=True)
            (templates_dir / "test-agent.md").write_text(
                "---\nname: test-agent\ndescription: Test agent.\nmodel: sonnet\ntools: Bash\nskills_used:\n  - signoff\n---\n",
                encoding="utf-8",
            )
            # Create registry
            config_dir = target_root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "agent_registry.json").write_text(
                json.dumps([{
                    "id": "test-agent",
                    "name": "Test Agent",
                    "tier": "phase",
                    "spawned_by": ["ticket-supervisor"],
                    "spawn_allowlist": [],
                    "skills_used": ["signoff"],
                }]),
                encoding="utf-8",
            )

            written = build_agent_cards(
                target_root=target_root,
                config={},
                dry_run=False,
                force=False,
            )

            self.assertIsInstance(written, int, msg="build_agent_cards must return an integer.")
            self.assertGreater(written, 0, msg="build_agent_cards must write at least 1 card file.")
            card_path = target_root / "docs" / "agents" / "cards" / "test-agent.card.md"
            self.assertTrue(
                card_path.exists(),
                msg=f"Expected card file not found at {card_path}",
            )


if __name__ == "__main__":
    unittest.main()
