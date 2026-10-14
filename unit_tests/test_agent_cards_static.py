"""
MODULE: test_agent_cards_static
GOAL: Agent cards are STATIC. Adding or changing an acceptance criterion in the
      AC store must never change any generated card, and no card carries an
      '## AC Assignments' section.
TDD: written BEFORE the implementation (red baseline).

Every test drives the REAL generator (`generate_agent_cards.build_agent_cards`)
against a temp package root; none of them spawns build.py and none greps the
generator's source. AC fixtures are written with `yaml.safe_dump` (block lists,
dashes at column 0), as the real store is.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

ASSIGNED_AGENT = "python-coder"
OTHER_AGENT = "plain-agent"
HEADING = "## AC Assignments"

_TEMPLATE_FM = {
    ASSIGNED_AGENT: {
        "name": ASSIGNED_AGENT,
        "description": "Standards-enforcing Python implementation agent.",
        "model": "sonnet",
        "tools": "Bash, Read, Edit, Write, Agent",
        "portable": True,
        "signoff": True,
        "skills_used": ["signoff", "doc-enforcer"],
    },
    OTHER_AGENT: {
        "name": OTHER_AGENT,
        "description": "An agent no AC is assigned to.",
        "model": "haiku",
        "tools": "Read",
        "portable": False,
        "signoff": False,
        "skills_used": ["signoff"],
    },
}


def _ac_record(ac_id: str, agent: str, title: str, status: str = "active") -> dict:
    return {
        "id": ac_id,
        "title": title,
        "status": status,
        "assigned_agent": agent,
        "criteria": [
            "Given a precondition",
            "When the action happens",
            "Then the outcome is observed",
        ],
        "covered_by": [],
    }


def _write_ac(root: Path, record: dict, component: str = "demo-component") -> Path:
    ac_dir = root / "docs" / "acceptance-criteria" / component
    ac_dir.mkdir(parents=True, exist_ok=True)
    path = ac_dir / f"{record['id']}.yaml"
    # The real serializer: block lists, dashes at column 0.
    path.write_text(
        yaml.safe_dump(record, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _make_package_root(root: Path) -> None:
    templates = root / "templates" / "agents"
    templates.mkdir(parents=True, exist_ok=True)
    registry = []
    for agent_id, fm in _TEMPLATE_FM.items():
        text = "---\n" + yaml.safe_dump(fm, default_flow_style=False, sort_keys=False) + "---\n"
        (templates / f"{agent_id}.md").write_text(text, encoding="utf-8")
        registry.append({
            "id": agent_id,
            "name": agent_id.title(),
            "tier": "phase",
            "priority": 6,
            "spawned_by": ["ticket-supervisor"],
            "spawn_allowlist": ["research-agent"],
            "skills_used": fm["skills_used"],
        })
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "agent_registry.json").write_text(json.dumps(registry), encoding="utf-8")


def _generate(root: Path) -> dict[str, str]:
    """Run the real card build phase; return {agent_id: card_text}."""
    from generate_agent_cards import build_agent_cards

    build_agent_cards(target_root=root, config={}, dry_run=False, force=True)
    cards_dir = root / "docs" / "agents" / "cards"
    return {
        p.name[: -len(".card.md")]: p.read_text(encoding="utf-8")
        for p in sorted(cards_dir.glob("*.card.md"))
    }


class _StaticCardBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _make_package_root(self.root)
        _write_ac(self.root, _ac_record("DEMO-100", ASSIGNED_AGENT, "First assigned criterion"))
        _write_ac(self.root, _ac_record("DEMO-101", ASSIGNED_AGENT, "Second assigned criterion"))


class TestAddingAnAcDoesNotChangeAnyCard(_StaticCardBase):
    """The statement that matters most: cards are no longer dynamic."""

    def test_adding_an_ac_to_an_agent_with_assignments_leaves_every_card_byte_identical(self):
        # covers: UNKNOWN
        # angle: criterion
        """Agent already has ACs; add another; regenerate; ALL cards identical."""
        before = _generate(self.root)
        self.assertEqual(
            sorted(before), sorted([ASSIGNED_AGENT, OTHER_AGENT]),
            "precondition: both fixture agents must have produced a card",
        )

        _write_ac(self.root, _ac_record("DEMO-102", ASSIGNED_AGENT, "Third, newly added criterion"))
        after = _generate(self.root)

        self.assertEqual(
            before[ASSIGNED_AGENT], after[ASSIGNED_AGENT],
            "adding an AC changed the card of the agent it is assigned to",
        )
        self.assertEqual(before, after, "adding an AC changed at least one card")

    def test_retitling_an_ac_leaves_the_card_byte_identical(self):
        # covers: UNKNOWN
        # angle: discrimination
        """Wrong version caught: stripping only the heading/ids but still emitting titles."""
        before = _generate(self.root)
        _write_ac(self.root, _ac_record("DEMO-100", ASSIGNED_AGENT, "A completely retitled criterion"))
        self.assertEqual(before, _generate(self.root))

    def test_removing_an_ac_leaves_the_card_byte_identical(self):
        # covers: UNKNOWN
        # angle: boundary
        """The shrink direction of the same invariant (the 'many -> fewer' edge)."""
        before = _generate(self.root)
        (self.root / "docs" / "acceptance-criteria" / "demo-component" / "DEMO-101.yaml").unlink()
        self.assertEqual(before, _generate(self.root))


class TestNoAcAssignmentsInGeneratedCards(_StaticCardBase):
    def test_no_generated_card_contains_an_ac_assignments_section(self):
        # covers: UNKNOWN
        # angle: criterion
        """Real generator output, every card, no '## AC Assignments' heading."""
        cards = _generate(self.root)
        self.assertTrue(cards, "generator produced no cards")
        for agent_id, text in cards.items():
            self.assertNotIn(HEADING, text, f"{agent_id}.card.md still has the AC Assignments section")

    def test_an_assigned_ac_does_not_appear_in_its_agents_card(self):
        # covers: UNKNOWN
        # angle: discrimination
        """Distinct from the heading check: a renamed heading would still leak the AC."""
        card = _generate(self.root)[ASSIGNED_AGENT]
        for needle in (
            "DEMO-100", "DEMO-101",
            "First assigned criterion", "Second assigned criterion",
        ):
            self.assertNotIn(needle, card, f"AC content {needle!r} leaked into the card")

    def test_an_ac_assigned_to_one_agent_does_not_leak_into_another_agents_card(self):
        # covers: UNKNOWN
        # angle: failure
        """Control row: the unassigned agent's card must also be free of every AC."""
        card = _generate(self.root)[OTHER_AGENT]
        self.assertNotIn("DEMO-100", card)
        self.assertNotIn("DEMO-101", card)

    def test_ac_files_whose_stem_ends_in_yaml_characters_do_not_reach_cards(self):
        # covers: H-1 regression
        # angle: boundary
        """Inverts the old H-1 stem-fallback test: id-less ACs named like 'data.yaml'
        / 'ml-100a.yaml' produce no card content at all now."""
        ac_dir = self.root / "docs" / "acceptance-criteria" / "demo-component"
        for stem in ("ml-100a", "data", "my-yaml", "ACD-200m"):
            record = {"assigned_agent": ASSIGNED_AGENT, "status": "active", "title": f"stem {stem}"}
            (ac_dir / f"{stem}.yaml").write_text(
                yaml.safe_dump(record, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        card = _generate(self.root)[ASSIGNED_AGENT]
        for stem in ("ml-100a", "data", "my-yaml", "ACD-200m"):
            self.assertNotIn(f"stem {stem}", card)
            self.assertNotIn(f"- {stem}:", card)


class TestAcStoreIsNotReadByCardGeneration(unittest.TestCase):
    """H-1 regression, INVERTED: cards are static, so no AC id ever reaches a card.

    Previously this asserted _scan_ac_assignments derived AC ids from the
    filename stem (Path.stem, not str.rstrip('.yaml')). That scan is being
    removed along with the '## AC Assignments' section, so the stem fallback has
    no behaviour left to pin. What remains true -- and what these tests assert
    on the real build_agent_cards output -- is that stem-named AC files produce
    NO card content, whether or not the YAML carries an explicit id.

    Self-contained on purpose: its own single-agent package root, independent of
    _StaticCardBase / _make_package_root (which build two agents and seed DEMO-*
    ACs that these assertions must not see).
    """

    _STEMS = ("ml-100a", "data", "my-yaml", "ACD-200m")

    def _build(self, tmp: str) -> str:
        from generate_agent_cards import build_agent_cards

        root = Path(tmp)
        (root / "templates" / "agents").mkdir(parents=True)
        (root / "templates" / "agents" / "test-agent.md").write_text(
            "---\n" + yaml.safe_dump(
                {"name": "test-agent", "description": "Test agent.", "model": "sonnet", "tools": "Bash"},
                default_flow_style=False, sort_keys=False,
            ) + "---\n",
            encoding="utf-8",
        )
        (root / "config").mkdir()
        (root / "config" / "agent_registry.json").write_text(
            json.dumps([{"id": "test-agent", "name": "Test Agent", "tier": "phase",
                         "spawned_by": [], "spawn_allowlist": [], "skills_used": []}]),
            encoding="utf-8",
        )
        ac_dir = root / "docs" / "acceptance-criteria"
        ac_dir.mkdir(parents=True)
        for stem in self._STEMS:
            (ac_dir / f"{stem}.yaml").write_text(
                yaml.safe_dump({"assigned_agent": "test-agent", "status": "active",
                                "title": f"Stem AC {stem}"},
                               default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        (ac_dir / "ACD-999z.yaml").write_text(
            yaml.safe_dump({"id": "ACD-999z", "assigned_agent": "test-agent", "status": "active",
                            "title": "Explicit ID Test"},
                           default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        build_agent_cards(target_root=root, config={}, dry_run=False, force=True)
        return (root / "docs" / "agents" / "cards" / "test-agent.card.md").read_text(encoding="utf-8")

    def test_id_less_stem_named_acs_do_not_appear_in_the_card(self):
        # covers: H-1 regression
        # angle: boundary
        """Inverted H-1: filenames like 'data.yaml' / 'ml-100a.yaml' leave no trace in the card."""
        with tempfile.TemporaryDirectory() as tmp:
            card = self._build(tmp)
        for stem in self._STEMS:
            self.assertNotIn(f"Stem AC {stem}", card)
            self.assertNotIn(f"- {stem}:", card)

    def test_ac_with_explicit_id_does_not_appear_in_the_card(self):
        # covers: H-1 regression
        # angle: criterion
        """Inverted H-1: an AC with an explicit id is likewise absent from the card."""
        with tempfile.TemporaryDirectory() as tmp:
            card = self._build(tmp)
        self.assertNotIn("ACD-999z", card)
        self.assertNotIn("Explicit ID Test", card)
        self.assertNotIn("## AC Assignments", card)


class TestStaticSectionsStillRender(_StaticCardBase):
    """Regression guard: removing too much is the likelier failure.

    NOTE: this class is a preservation guard, not a new-behaviour test, so it is
    expected to already be green before the implementation exists.
    """

    def test_description_facts_table_tools_skills_and_diagram_still_render(self):
        # covers: UNKNOWN
        # angle: criterion
        """Every static section survives, with its exact content."""
        card = _generate(self.root)[ASSIGNED_AGENT]

        self.assertTrue(card.startswith("---\n"), "frontmatter missing")
        self.assertIn("agent_id: python-coder", card)
        self.assertIn("**Standards-enforcing Python implementation agent.**", card)

        for row in (
            "| Model | sonnet |",
            "| Tier | phase |",
            "| Priority | 6 |",
            "| Portable | Yes |",
            "| Sign-off capable | Yes |",
        ):
            self.assertIn(row, card, f"facts table lost {row!r}")

        for heading in (
            "## When to Use",
            "## Knowledge Flow",
            "## Spawn and Dependency",
            "## Input / Output Contract",
            "## Tools Available",
            "## Skills Used",
            "## Configuration",
            "## Contributor Notes",
        ):
            self.assertEqual(card.count(heading), 1, f"{heading!r} must appear exactly once")

        self.assertIn("```mermaid", card)
        self.assertIn("flowchart TD", card)
        for tool in ("Bash", "Read", "Edit", "Write", "Agent"):
            self.assertIn(tool, card)
        self.assertIn("doc-enforcer", card)

    def test_facts_differ_per_agent_so_the_table_is_not_a_constant(self):
        # covers: UNKNOWN
        # angle: discrimination
        """Control row: the second agent renders ITS facts, not the first agent's."""
        card = _generate(self.root)[OTHER_AGENT]
        self.assertIn("| Model | haiku |", card)
        self.assertIn("| Portable | No |", card)
        self.assertIn("| Sign-off capable | No |", card)


class TestRegenerationIsIdempotent(_StaticCardBase):
    def test_regenerating_twice_over_an_unchanged_store_is_identical(self):
        # covers: UNKNOWN
        # angle: criterion
        """A clean tree stays clean: two builds, same store, same bytes."""
        first = _generate(self.root)
        second = _generate(self.root)
        self.assertEqual(first, second)

    def test_second_non_forced_build_writes_nothing(self):
        # covers: UNKNOWN
        # angle: criterion
        """The compare-before-write path: an unchanged store means zero files rewritten."""
        from generate_agent_cards import build_agent_cards

        _generate(self.root)
        written = build_agent_cards(target_root=self.root, config={}, dry_run=False, force=False)
        self.assertEqual(written, 0, "an unchanged store must not rewrite any card")

    def test_non_forced_build_after_adding_an_ac_writes_nothing(self):
        # covers: UNKNOWN
        # angle: criterion
        """The permanently-dirty-tree symptom itself, measured as files written."""
        from generate_agent_cards import build_agent_cards

        _generate(self.root)
        _write_ac(self.root, _ac_record("DEMO-102", ASSIGNED_AGENT, "Newly added criterion"))
        written = build_agent_cards(target_root=self.root, config={}, dry_run=False, force=False)
        self.assertEqual(written, 0, "adding an AC must not cause any card rewrite")


if __name__ == "__main__":
    unittest.main()
