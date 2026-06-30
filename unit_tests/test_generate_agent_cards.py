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


# ---------------------------------------------------------------------------
# Test 8 — render_references: missing doc_link renders (missing) annotation
#           (INF-600b-1-i)
# ---------------------------------------------------------------------------

class TestMissingDocLinkRendering(unittest.TestCase):
    """INF-600b-1-i: Missing doc_links are rendered as plain text with (missing) annotation."""

    def setUp(self):
        # covers: INF-600b-1-i
        from generate_agent_cards import render_references  # noqa: F401
        self.render_references = render_references

    def test_ac1_missing_doclink_rendered_as_plain_text_with_missing_marker(self):
        # covers: INF-600b-1-i
        """INF-600b-1-i: Non-existent doc_links entry is plain text annotated with '(missing)'."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            card_path = package_root / "docs" / "agents" / "cards" / "python-coder.card.md"
            card_path.parent.mkdir(parents=True)

            registry_entry = {
                "id": "python-coder",
                "doc_links": [
                    {"path": "docs/architecture/nonexistent-doc.md", "label": "Nonexistent Doc"},
                ],
            }

            result = self.render_references(
                registry_entry=registry_entry,
                card_path=card_path,
                package_root=package_root,
            )

        self.assertIn("## References", result, "References section must be present")
        self.assertIn(
            "(missing)",
            result,
            msg="Missing doc_link must be annotated with '(missing)' in the References section.",
        )
        # Must NOT render as a hyperlink (no Markdown link syntax [label](path))
        self.assertNotIn(
            "[Nonexistent Doc]",
            result,
            msg="Non-existent doc must NOT be rendered as a Markdown hyperlink.",
        )
        # Must contain the raw path as plain text
        self.assertIn(
            "docs/architecture/nonexistent-doc.md",
            result,
            msg="Missing doc path must appear as plain text in the References section.",
        )

    def test_ac2_missing_doclink_emits_warning_with_agent_id_and_path(self):
        # covers: INF-600b-1-i
        """INF-600b-1-i: _log.warning() is called with agent_id and missing path string."""
        import tempfile
        import logging
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            card_path = package_root / "docs" / "agents" / "cards" / "python-coder.card.md"
            card_path.parent.mkdir(parents=True)

            registry_entry = {
                "id": "python-coder",
                "doc_links": [
                    {"path": "docs/architecture/nonexistent-doc.md", "label": "Nonexistent Doc"},
                ],
            }

            import generate_agent_cards
            with patch.object(generate_agent_cards._log, "warning") as mock_warn:
                self.render_references(
                    registry_entry=registry_entry,
                    card_path=card_path,
                    package_root=package_root,
                )
                # Must have called _log.warning at least once
                self.assertTrue(
                    mock_warn.called,
                    msg="_log.warning must be called when a doc_link references a missing file.",
                )
                # The warning args must include the agent_id and the missing path
                found_warning = False
                for call_args in mock_warn.call_args_list:
                    args = call_args[0]  # positional args tuple
                    # args[0] is the format string; args[1] is agent_id; args[2] is path_str
                    if len(args) >= 3:
                        if (
                            args[1] == "python-coder"
                            and "docs/architecture/nonexistent-doc.md" in str(args[2])
                        ):
                            found_warning = True
                            break
                self.assertTrue(
                    found_warning,
                    msg=(
                        "WARNING must be emitted with agent_id='python-coder' and "
                        "path='docs/architecture/nonexistent-doc.md'. "
                        f"Actual calls: {mock_warn.call_args_list}"
                    ),
                )

    def test_ac3_card_generation_does_not_fail_when_doclink_missing(self):
        # covers: INF-600b-1-i
        """INF-600b-1-i: generate_card() does not raise when doc_links references a non-existent file."""
        import tempfile
        from pathlib import Path
        from generate_agent_cards import generate_card

        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            card_path = package_root / "docs" / "agents" / "cards" / "python-coder.card.md"
            card_path.parent.mkdir(parents=True)

            registry_entry = dict(PYTHON_CODER_REGISTRY)
            registry_entry["doc_links"] = [
                {"path": "docs/architecture/nonexistent-doc.md", "label": "Nonexistent Doc"},
            ]

            try:
                result = generate_card(
                    agent_id="python-coder",
                    template_frontmatter=PYTHON_CODER_TEMPLATE_FM,
                    registry_entry=registry_entry,
                    card_path=card_path,
                    package_root=package_root,
                )
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"generate_card raised {type(exc).__name__} when doc_link is missing: {exc}"
                )

            self.assertIsInstance(
                result,
                str,
                msg="generate_card must return a string even when doc_links reference a missing file.",
            )
            self.assertGreater(
                len(result),
                0,
                msg="generate_card must return non-empty card string when doc_link is missing.",
            )
            # The card should contain the (missing) marker
            self.assertIn(
                "(missing)",
                result,
                msg="Card output must include '(missing)' marker for non-existent doc_link.",
            )


# ---------------------------------------------------------------------------
# Test 9 — H-1 regression: _scan_ac_assignments uses Path.stem for id fallback
# Defect: filename.rstrip(".yaml") strips a CHARACTER SET, not a suffix.
# e.g. "ml-100a.yaml" -> "ml-100" (the trailing 'a' is in {., y, a, m, l})
#      "data.yaml"    -> "dat"   (the trailing 'a' is stripped)
# Fix: use Path(filename).stem which derives the true stem.
# ---------------------------------------------------------------------------

class TestScanAcAssignmentsStemFallback(unittest.TestCase):
    """H-1 regression: AC id fallback uses Path.stem, not str.rstrip."""

    def setUp(self):
        # covers: H-1 regression
        from generate_agent_cards import _scan_ac_assignments
        self._scan_ac_assignments = _scan_ac_assignments

    def test_ac_id_fallback_preserves_full_stem_for_yaml_suffix(self):
        # covers: H-1 regression
        """H-1: When AC YAML omits 'id', derived id equals full filename stem (no truncation)."""
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            docs_root = Path(tmp)
            ac_dir = docs_root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True)

            # Filenames whose stems end in chars that appear in ".yaml" —
            # rstrip(".yaml") would corrupt these; Path.stem must not.
            test_cases = [
                # (filename, expected_stem)
                ("ml-100a.yaml", "ml-100a"),   # trailing 'a' is in {a,y,m,l,.}
                ("data.yaml", "data"),           # trailing 'a' is in {a,y,m,l,.}
                ("my-yaml.yaml", "my-yaml"),     # entire suffix overlap
                ("ACD-200m.yaml", "ACD-200m"),  # trailing 'm' is in {a,y,m,l,.}
            ]

            for filename, expected_stem in test_cases:
                ac_content = yaml.dump({
                    "assigned_agent": "test-agent",
                    "status": "active",
                    "title": "Test AC",
                    # intentionally omitting 'id' to trigger the fallback
                })
                (ac_dir / filename).write_text(ac_content, encoding="utf-8")

            results = self._scan_ac_assignments("test-agent", docs_root)
            found_ids = {r["id"] for r in results}

            for filename, expected_stem in test_cases:
                self.assertIn(
                    expected_stem,
                    found_ids,
                    msg=(
                        f"Filename '{filename}': expected fallback id '{expected_stem}' "
                        f"but got ids: {found_ids}. "
                        "Path.stem must be used — not str.rstrip('.yaml')."
                    ),
                )

    def test_ac_id_from_yaml_field_is_unaffected(self):
        # covers: H-1 regression
        """H-1: When AC YAML supplies 'id', it is used as-is (stem fallback not triggered)."""
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            docs_root = Path(tmp)
            ac_dir = docs_root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True)

            ac_content = yaml.dump({
                "id": "ACD-999z",
                "assigned_agent": "test-agent",
                "status": "active",
                "title": "Explicit ID Test",
            })
            (ac_dir / "ACD-999z.yaml").write_text(ac_content, encoding="utf-8")

            results = self._scan_ac_assignments("test-agent", docs_root)
            self.assertEqual(len(results), 1)
            self.assertEqual(
                results[0]["id"],
                "ACD-999z",
                msg="Explicit id field in YAML must be returned unchanged.",
            )


# ---------------------------------------------------------------------------
# Test 10 — H-2 regression: _resolve_source_to_path Strategy 3 ambiguity
# Defect: first os.walk match returned non-deterministically when multiple
# files share the same basename (e.g. every skill dir has SKILL.md).
# Fix: collect ALL matches; return path only when exactly 1 unique match
# exists; return None for zero or more-than-one matches.
# ---------------------------------------------------------------------------

class TestResolveSourceToPathAmbiguity(unittest.TestCase):
    """H-2 regression: Strategy 3 resolves uniquely or returns None on ambiguity."""

    def setUp(self):
        # covers: H-2 regression
        from generate_agent_cards import _resolve_source_to_path
        self._resolve_source_to_path = _resolve_source_to_path

    def test_ambiguous_basename_returns_none(self):
        # covers: H-2 regression
        """H-2: When a basename matches files in two locations, resolver returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            # Create two files with the same basename in different directories
            dir_a = package_root / "skills" / "signoff"
            dir_b = package_root / "skills" / "doc-enforcer"
            dir_a.mkdir(parents=True)
            dir_b.mkdir(parents=True)
            (dir_a / "SKILL.md").write_text("# signoff skill", encoding="utf-8")
            (dir_b / "SKILL.md").write_text("# doc-enforcer skill", encoding="utf-8")

            result = self._resolve_source_to_path("SKILL.md", package_root)

            self.assertIsNone(
                result,
                msg=(
                    "When SKILL.md exists in two directories, _resolve_source_to_path "
                    "must return None (ambiguous) — not a non-deterministic first match."
                ),
            )

    def test_unique_basename_returns_that_path(self):
        # covers: H-2 regression
        """H-2: When a basename matches exactly one file, that path is returned."""
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            # Create a unique file
            docs_dir = package_root / "docs" / "architecture"
            docs_dir.mkdir(parents=True)
            unique_file = docs_dir / "unique-document.md"
            unique_file.write_text("# Unique", encoding="utf-8")

            result = self._resolve_source_to_path("unique-document.md", package_root)

            self.assertEqual(
                result,
                unique_file,
                msg=(
                    "When unique-document.md exists in exactly one location, "
                    "_resolve_source_to_path must return that path."
                ),
            )

    def test_absent_basename_returns_none(self):
        # covers: H-2 regression
        """H-2: When a basename matches no file anywhere, resolver returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            # Empty tree — nothing to match
            result = self._resolve_source_to_path("nonexistent-file.md", package_root)

            self.assertIsNone(
                result,
                msg="With no matching file on disk, resolver must return None.",
            )

    def test_three_matches_returns_none(self):
        # covers: H-2 regression
        """H-2: When a basename matches three locations, resolver returns None (not first match)."""
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            for subdir in ("a", "b", "c"):
                d = package_root / subdir
                d.mkdir()
                (d / "README.md").write_text(f"# {subdir}", encoding="utf-8")

            result = self._resolve_source_to_path("README.md", package_root)

            self.assertIsNone(
                result,
                msg=(
                    "When README.md exists in three directories, resolver must return "
                    "None — not a first/arbitrary match."
                ),
            )


if __name__ == "__main__":
    unittest.main()
