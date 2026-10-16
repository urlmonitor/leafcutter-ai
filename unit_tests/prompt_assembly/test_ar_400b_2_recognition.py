"""AR-400b-2 / AR-400b-2-iv -- every way the package phrases "use this ability" is recognised as an
instruction, and an installer step that merely copies an ability into place is not (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400b-2.yaml and AR-400b-2-iv.yaml. The behavioural tests drive the REAL validator CLI over a
copied package slice. The budget test times the recognition rule itself over the real tree; the AC
contract (``delivers_to``) pins its Python shape as
``recognise(text, known_ids, agent_ids) -> list[{'ability_text','canonical_id','line','names_agent'}]``
in a module under scripts/ (found by parsing scripts/*.py for that top-level definition, so the
coder may name the module freely).
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

PROBE = "probe-agent"
EIGHT = [
    "Load `.claude/skills/a1/SKILL.md` and follow it.",
    "Invoke the `a2` skill before writing.",
    "Skill: a3",
    "| Question | `.claude/skills/a4/SKILL.md` -- invoke via `Bash` |",
    "Run the a5 skill on every new file.",
    "Resolve and load the a6 skill (read it in full before editing).",
    "Apply the `a7` skill before writing the file.",
    "Step 1 -- Load the A8 Skill",
]
NINTH = "The a9 skill's output is a table."
CONTROL_LINE = "Invoke the `a2` skill before writing."
BUDGET_SECONDS = 2.0


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)


class TestEightRealPhrasings(_Base):
    def test_eight_real_phrasings_each_yield_one_finding(self):
        # covers: AR-400b-2
        # angle: criterion
        # must_catch: only the path form is recognised (today's check_skill_refs behaviour)
        # must_catch: recognition is case-sensitive so 'A8' is missed
        # must_catch: the table-row form is missed
        """a1..a8 exist but probe-agent grants nothing; its body holds exactly the eight lines. The
        CLI reports exactly eight findings, one per line, each naming probe-agent, the ability and
        the line; line 8's finding names the canonical id 'a8' (and the text as written, 'A8')."""
        F.planted_skills(self.root, *[f"a{i}" for i in range(1, 9)])
        path = F.plant(self.root, PROBE, EIGHT)
        rc, out = H.cli(self.root)
        got = F.about(out, PROBE)
        self.assertEqual(len(got), 8, f"expected exactly eight findings for probe-agent: {got}")
        for i, text in enumerate(EIGHT, 1):
            line_no = F.line_of(path, text)
            mine = [f for f in got if F.names(f, f"a{i}") or (i == 8 and F.names(f, "A8"))]
            self.assertEqual(len(mine), 1, f"line {line_no} ({text!r}) -> {len(mine)} findings: {got}")
            self.assertTrue(H.names_line(mine[0], F.agent_rel(PROBE), line_no), mine[0])
        eighth = [f for f in got if F.names(f, "A8") or F.names(f, "a8")][0]
        self.assertIn("A8", eighth)
        self.assertTrue(F.names(eighth, "a8"), f"line 8 must name the canonical id a8: {eighth}")
        self.assertEqual(rc, 1, out[-800:])

    def test_descriptive_mention_is_not_an_instruction(self):
        # covers: AR-400b-2
        # angle: discrimination
        """A ninth line naming the existing, ungranted a9 without telling the reader to use it
        produces no finding. Control row in the same body: a real imperative about a2 produces
        exactly one, so a rule that flags every mention (or flags nothing) cannot pass."""
        F.planted_skills(self.root, "a2", "a9")
        F.plant(self.root, PROBE, [CONTROL_LINE, NINTH])
        rc, out = H.cli(self.root)
        got = F.about(out, PROBE)
        self.assertEqual(len(got), 1, f"only the a2 imperative may produce a finding: {got}")
        self.assertTrue(F.names(got[0], "a2"), got[0])
        self.assertEqual([f for f in got if F.names(f, "a9")], [])
        self.assertEqual(rc, 1, out[-800:])


def _recognition_module():
    """Import the scripts/ module that defines top-level ``recognise`` (AR-400b-2 delivers_to)."""
    scripts = F.REPO_ROOT / "scripts"
    for py in sorted(scripts.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        if any(isinstance(n, ast.FunctionDef) and n.name == "recognise" for n in tree.body):
            sys.path.insert(0, str(scripts))
            return importlib.import_module(py.stem)
    return None


def test_recognition_over_real_tree_completes_within_budget():
    # covers: AR-400b-2
    # angle: boundary
    """The recognition rule, run over every agent template and every templates/skills/**/*.md of the
    real tree (the validator's scan population), completes within 2 seconds, measured around the
    recognition calls only, and actually recognises instructions (a rule that returns [] is fast)."""
    mod = _recognition_module()
    assert mod is not None, "no module under scripts/ defines top-level recognise(text, known_ids, agent_ids)"
    root = F.REPO_ROOT
    known = {d.name for d in (root / "templates" / "skills").iterdir() if d.is_dir()}
    agents = {p.stem for p in (root / "templates" / "agents").glob("*.md") if not p.name.startswith("_")}
    files = sorted((root / "templates" / "agents").glob("*.md")) + sorted((root / "templates" / "skills").rglob("*.md"))
    assert len(files) >= 150, f"real tree population too small to time: {len(files)}"
    texts = [Path(p).read_text(encoding="utf-8") for p in files]
    total = 0
    started = time.perf_counter()
    for text in texts:
        found = mod.recognise(text, known, agents)
        assert isinstance(found, list)
        total += len(found)
    elapsed = time.perf_counter() - started
    assert total > 0, "recognise() found no instruction anywhere in the real tree"
    assert elapsed < BUDGET_SECONDS, f"recognition took {elapsed:.2f}s over {len(files)} files (budget {BUDGET_SECONDS}s)"


class TestInstallerStep(_Base):
    INSTALLER = [
        "Offer the user the optional webapp-testing ability; if they accept, run these steps.",
        "mkdir -p .claude/skills/webapp-testing",
        "cp leafcutter/templates/skills/webapp-testing/SKILL.md .claude/skills/webapp-testing/SKILL.md",
        "Print: webapp-testing installed at .claude/skills/webapp-testing/SKILL.md",
        "If `.claude/skills/webapp-testing/SKILL.md` already exists, skip the webapp-testing prompt.",
    ]
    ADDED = "After installing, load the `webapp-testing` skill and take a screenshot."

    def test_installer_steps_produce_no_finding(self):
        # covers: AR-400b-2-iv
        # angle: criterion
        # must_catch: a shell command line naming a skill path is treated as an instruction
        """probe-installer (grants nothing) carries the mkdir / cp / Print / 'already exists' lines
        for the existing webapp-testing ability: no finding. Control row in the same run:
        probe-control says 'load the webapp-testing skill' -> exactly one finding for it."""
        F.plant(self.root, "probe-installer", self.INSTALLER)
        F.plant(self.root, "probe-control", ["Load the `webapp-testing` skill first."])
        rc, out = H.cli(self.root)
        self.assertEqual(len(F.of_kind(out, F.UNGRANTED, "webapp-testing", "probe-control")), 1, out[-1200:])
        self.assertEqual(F.about(out, "probe-installer"), [], "installer steps are file operations, not instructions")
        self.assertEqual(rc, 1, out[-800:])

    def test_added_load_line_yields_exactly_one_finding_on_that_line(self):
        # covers: AR-400b-2-iv
        # angle: discrimination
        """Adding 'After installing, load the webapp-testing skill ...' to the installer body yields
        ONE finding, on that line only: the exemption is per line, not per specialist."""
        path = F.plant(self.root, "probe-installer", [*self.INSTALLER, self.ADDED])
        rc, out = H.cli(self.root)
        got = F.about(out, "probe-installer")
        self.assertEqual(len(got), 1, f"expected exactly one finding: {got}")
        self.assertTrue(F.names(got[0], "webapp-testing"), got[0])
        self.assertTrue(H.names_line(got[0], F.agent_rel("probe-installer"), F.line_of(path, self.ADDED)), got[0])
        self.assertEqual(rc, 1, out[-800:])


if __name__ == "__main__":
    unittest.main()
