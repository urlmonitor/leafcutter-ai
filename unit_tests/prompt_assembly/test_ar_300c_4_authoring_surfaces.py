"""AR-300c-4 / AR-300c-5-iv: the authoring surfaces name ONE place to grant.

Regression guard. The documentation and prompt prose these ACs describe was
already updated; these tests pin it so the retired routes cannot return
unnoticed. They read the REAL surfaces on disk and decide, per sentence,
whether a retired route is INSTRUCTED (flagged) or PROHIBITED / described as
retired or derived (allowed). The instruction/prohibition classifier is proven
by in-test negative controls (synthetic text that instructs must be flagged;
synthetic text that forbids must not).

Retired routes: a ``{{my_skills_used}}`` / ``{{my_spawn_allowlist}}`` body
marker, a hand-written "Available Sub-Agents" / skills table, and a grant made
by editing skills_used / skills_invoked / spawn_allowlist in the central
registry (config/agent_registry.json).
"""

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AC_DIR = (
    ROOT / "docs" / "acceptance-criteria" / "agent-registry"
    / "AR-300-granted-abilities-arrive"
)
AC_IDS = ("AR-300c-4", "AR-300c-5-iv")
REFERENCE = ROOT / "docs" / "reference" / "agent-template-frontmatter.md"

_MARKER = re.compile(r"\{\{\s*my_(?:skills_used|spawn_allowlist)\s*\}\}")
_HANDWRITTEN = re.compile(
    r"\b(?:hand-?written|hand-?authored)\b.{0,60}\b(?:sub-?agents?|skills?)\b", re.I
)
_WRITE_TABLE = re.compile(
    r"\b(?:write|add|include|create|put)\b.{0,60}"
    r"(?:Available (?:Sub-Agents|Skills)|sub-?agents? (?:table|list)|skills table)",
    re.I,
)
_FIELD = re.compile(r"\b(?:skills_used|skills_invoked|spawn_allowlist)\b")
_REGISTRY = re.compile(r"registry", re.I)
_EDIT_VERB = re.compile(
    r"\b(?:edit|hand-edit|add|set|update|write|put|append|grant)\b", re.I
)
_PROHIBIT = re.compile(
    r"\b(?:do not|don't|never|must not|not|no longer|retired|derived|derive[sd]?|"
    r"forbidden|refuses?|strips?|stripped|warns?|violation|leave them empty|"
    r"remove it|regenerat\w+|overwrit\w+|only place|one place|instead)\b",
    re.I,
)
_BULLET = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def mentions_retired_route(sentence: str) -> bool:
    """True if the sentence refers to any retired grant route."""
    if _MARKER.search(sentence) or _HANDWRITTEN.search(sentence):
        return True
    if _WRITE_TABLE.search(sentence):
        return True
    return bool(
        _FIELD.search(sentence)
        and _REGISTRY.search(sentence)
        and _EDIT_VERB.search(sentence)
    )


def units(text: str):
    """Yield (sentence, lead_in) pairs; fenced code is excluded.

    A bullet item inherits the preceding non-bullet paragraph (e.g. "Do NOT:")
    and, for later items, the first item of its list, as lead-in context.
    """
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    last_plain = ""
    for block in blocks:
        lines = block.splitlines()
        if lines[0].lstrip().startswith("|"):
            for row in lines:
                yield row, ""
            continue
        if _BULLET.match(lines[0]):
            items: list[str] = []
            cur: list[str] = []
            for ln in lines:
                if _BULLET.match(ln) and cur:
                    items.append(" ".join(cur))
                    cur = []
                cur.append(ln.strip())
            items.append(" ".join(cur))
            for i, item in enumerate(items):
                lead = last_plain + (" " + items[0] if i else "")
                for sent in re.split(r"(?<=\.)\s+", item):
                    yield sent, lead
            continue
        flat = " ".join(ln.strip() for ln in lines)
        last_plain = flat
        for sent in re.split(r"(?<=\.)\s+", flat):
            yield sent, ""


def instructing_sentences(text: str):
    """Sentences that mention a retired route with no prohibition context."""
    out = []
    for sent, lead in units(text):
        if not mentions_retired_route(sent):
            continue
        if _PROHIBIT.search(sent) or _PROHIBIT.search(lead):
            continue
        out.append(sent.strip())
    return out


def authoring_surfaces():
    """Derive the surface list from the two ACs' doc_links / implemented_by."""
    paths = set()
    for ac_id in AC_IDS:
        data = yaml.safe_load((AC_DIR / f"{ac_id}.yaml").read_text(encoding="utf-8"))
        for link in data.get("doc_links") or []:
            paths.add(link["path"])
        paths.update(data.get("implemented_by") or [])
    return sorted(
        p for p in paths
        if p.endswith(".md") and not p.startswith("docs/acceptance-criteria/")
    )


class TestSurfacePopulationDerived(unittest.TestCase):
    def test_population_is_derived_and_nonempty(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: boundary
        surfaces = authoring_surfaces()
        self.assertGreaterEqual(len(surfaces), 6, surfaces)
        for required in (
            "docs/reference/agent-template-frontmatter.md",
            "docs/how-to/creating-an-agent-template.md",
            "templates/agents/llm-expert.md",
            "templates/skills/add-agent-to-package/SKILL.md",
            "templates/skills/add-skill-to-package/SKILL.md",
            "docs/how-to/deprecating-or-removing-artifacts.md",
        ):
            self.assertIn(required, surfaces)
        for rel in surfaces:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_empty_population_fails_the_sweep(self):
        # covers: AR-300c-5-iv
        # angle: failure
        with self.assertRaises(AssertionError):
            self._sweep([])

    def _sweep(self, surfaces):
        self.assertTrue(surfaces, "empty surface population: sweep is vacuous")


class TestReferenceNamesOnePlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REFERENCE.read_text(encoding="utf-8")
        m = re.search(
            r"### Granting Skills and Sub-Agents\n(.*?)(?=\n## )", cls.text, re.S
        )
        cls.section = m.group(1) if m else ""

    def test_ac1_reference_names_declaration_beside_tools(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: criterion
        self.assertTrue(self.section, "Granting Skills and Sub-Agents section missing")
        self.assertRegex(self.section, r"declared in ONE place")
        self.assertRegex(self.section, r"beside `tools:`")
        self.assertRegex(self.section, r"\n\s*skills:\n")
        self.assertRegex(self.section, r"\n\s*spawn_allowlist:\n")
        self.assertIn("__ticket_phase_agents__", self.section)
        self.assertRegex(
            self.section, r"Nothing beyond the\s+declaration is\s+needed"
        )

    def test_ac2_registry_fields_described_as_derived(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: criterion
        self.assertRegex(self.section, r"registry copy is derived")
        self.assertRegex(self.section, r"Do not edit the derived\s+fields by hand")
        for consequence in ("divergent", "declaration wins"):
            self.assertIn(consequence, " ".join(self.section.split()))
        derived_skills = [
            r for r in self.text.splitlines()
            if r.startswith("| `skills_invoked` | array of entry")
        ]
        self.assertEqual(len(derived_skills), 1)
        self.assertIn("**Derived**", derived_skills[0])
        self.assertIn("do not hand-edit", derived_skills[0])
        derived_spawn = [
            r for r in self.text.splitlines()
            if r.startswith("| `spawn_allowlist` | array of string")
        ]
        self.assertEqual(len(derived_spawn), 1)
        self.assertIn("**Derived**", derived_spawn[0])
        self.assertIn("do not hand-edit", derived_spawn[0])

    def test_ac3_agent_tool_pairing_stated(self):
        # covers: AR-300c-5-iv
        # angle: criterion
        flat = " ".join(self.section.split())
        self.assertIn("requires `Agent`", flat)
        self.assertIn("spawn-tool-grant", flat)
        self.assertIn("is_ticket_phase", flat)


class TestNoSurfaceInstructsRetiredRoutes(unittest.TestCase):
    def test_no_authoring_surface_instructs_a_retired_route(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: failure
        surfaces = authoring_surfaces()
        self.assertTrue(surfaces)
        findings = {}
        for rel in surfaces:
            hits = instructing_sentences((ROOT / rel).read_text(encoding="utf-8"))
            if hits:
                findings[rel] = hits
        self.assertEqual(findings, {}, "surfaces still instruct a retired route")

    def test_surfaces_actually_mention_retired_routes_as_prohibitions(self):
        # covers: AR-300c-4
        # angle: discrimination
        # Guards against a vacuous sweep: if the classifier saw no mention at
        # all in the real text, "no instructions" would be meaningless.
        total = 0
        for rel in authoring_surfaces():
            for sent, _lead in units((ROOT / rel).read_text(encoding="utf-8")):
                if mentions_retired_route(sent):
                    total += 1
        self.assertGreaterEqual(total, 8)

    def test_llm_expert_checklist_item_points_at_declaration(self):
        # covers: AR-300c-5-iv
        # angle: criterion
        text = (ROOT / "templates/agents/llm-expert.md").read_text(encoding="utf-8")
        m = re.search(r"\n4\. \*\*`spawn_allowlist` declared.*?(?=\n5\. )", text, re.S)
        self.assertIsNotNone(m, "checklist item 4 missing or not rewritten")
        item = " ".join(m.group(0).split())
        self.assertIn("frontmatter `spawn_allowlist:` key", item)
        self.assertIn("must list `Agent`", item)
        self.assertNotRegex(item, r"(?i)tier\b.*must include")


class TestClassifierNegativeControls(unittest.TestCase):
    """The instruction-vs-prohibition classifier must bite both ways."""

    INSTRUCTS = (
        "To grant a skill, add it to `skills_used` in `config/agent_registry.json`.",
        "Write a `{{my_spawn_allowlist}}` marker in the body of the agent.",
        "Add a hand-written Available Sub-Agents table to the body.",
        "Include a `## Your Available Sub-Agents` section listing each agent.",
        # a negation word in a DIFFERENT sentence must not excuse an instruction
        "Add `research-agent` to `spawn_allowlist` in the registry. "
        "This is not optional.",
    )
    FORBIDS = (
        "Do not hand-edit `skills_used` in `config/agent_registry.json`; "
        "it is derived.",
        "The `{{my_skills_used}}` marker is retired and stripped at compile time.",
        "Never write a hand-written Available Sub-Agents table in the body.",
        "`spawn_allowlist` in the registry is a derived copy; do not edit it.",
    )

    def test_instruction_is_flagged(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: discrimination
        for text in self.INSTRUCTS:
            self.assertTrue(instructing_sentences(text), text)

    def test_prohibition_is_not_flagged(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: discrimination
        for text in self.FORBIDS:
            self.assertEqual(instructing_sentences(text), [], text)

    def test_bullet_under_do_not_lead_in_is_allowed_but_bare_bullet_flagged(self):
        # covers: AR-300c-4
        # covers: AR-300c-5-iv
        # angle: discrimination
        forbidden = "Do NOT:\n\n- write a `{{my_skills_used}}` marker in the body.\n"
        instructed = "Steps:\n\n- write a `{{my_skills_used}}` marker in the body.\n"
        self.assertEqual(instructing_sentences(forbidden), [])
        self.assertTrue(instructing_sentences(instructed))

    def test_fenced_example_is_ignored(self):
        # covers: AR-300c-4
        # angle: boundary
        fenced = (
            "```json\n\"spawn_allowlist\": [],\n```\n\n"
            "Declare the agent in the template frontmatter.\n"
        )
        self.assertEqual(instructing_sentences(fenced), [])


if __name__ == "__main__":
    unittest.main()
