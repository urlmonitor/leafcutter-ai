"""AR-400d-2 / AR-400d-2-i -- a project-supplied ability the project does not have is reported ONCE at
informational severity and the install carries on; it is looked for only in the project's own
abilities area, never in .claude/skills (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400d-2.yaml and AR-400d-2-i.yaml. Real ``build.py`` runs over a copied package inside a scratch
consumer project (see ``_ar400_3b_fixtures``). The L3 uses ``--validate-only`` so the build's own
.claude/skills shim step (KI-BP-009) cannot touch the fixture directory it must keep separate.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402

NOT_FOUND = r"not found"


def _not_found_lines(out: str) -> list[str]:
    """EVERY line (any severity) about probe-coder / postgres being not found."""
    return [ln for ln in out.splitlines()
            if "probe-coder" in ln and F.names(ln, "postgres") and re.search(NOT_FOUND, ln, re.IGNORECASE)]


def _expected_compiled_agents(sc) -> list[str]:
    reg = H._registry(sc.root)["agents"]
    return sorted(a["id"] for a in reg if a.get("portable", True) and a.get("template_path", "").startswith("templates/agents/"))


class TestAbsentProjectAbility(unittest.TestCase):
    @pytest.mark.shared_layout_mutator
    def test_absent_project_ability_reported_once_at_info_and_build_passes(self):
        # covers: AR-400d-2
        # angle: criterion
        # must_catch: the line is printed with the warning prefix
        # must_catch: the line is printed once per reader (gate and compile)
        # must_catch: the build refuses
        """Empty .leafcutter/skills; probe-coder grants postgres ``provided_by: project``. The build
        exits 0, every agent is compiled in every platform root, and exactly ONE line (of any
        severity) names probe-coder, postgres, the project's .leafcutter/skills area and 'not
        found' -- and that line is neither a warning nor an error."""
        b = G.built("marked_absent")
        self.assertEqual(b.rc, 0, b.out[-1500:])
        allv = _not_found_lines(b.out)
        info = G.info_lines(b.out, "probe-coder", "postgres", NOT_FOUND)
        self.assertEqual(len(allv), 1, f"expected exactly one 'not found' line, got {allv}")
        self.assertEqual(info, [ln.strip() for ln in allv], "the line must be informational, not a warning or error")
        self.assertIn(".leafcutter/skills", info[0], "the line must say where it looked")
        agents = _expected_compiled_agents(b.sc)
        from _ar_300c_support import compiled_agent_roots  # noqa: PLC0415

        roots = compiled_agent_roots(b.sc.project)
        self.assertGreaterEqual(len(roots), 2)
        for root in roots:
            self.assertEqual([a for a in agents if not (root / f"{a}.md").is_file()], [], f"{root}: agents not compiled")

    @pytest.mark.shared_layout_mutator
    def test_compiled_prompt_states_project_ability_not_installed(self):
        # covers: AR-400d-2
        # angle: deployed
        """probe-coder's compiled prompt does not offer postgres as an available ability (no table
        row) and states the project-supplied postgres is not installed in this project."""
        b = G.built("marked_absent")
        for root, text in G.compiled(b.sc.project, "probe-coder").items():
            self.assertEqual(G.ability_rows(text, "postgres"), [], f"{root}: postgres offered as available")
            said = [ln for ln in text.splitlines()
                    if not ln.lstrip().startswith("|") and F.names(ln, "postgres") and "not installed" in ln.lower()]
            self.assertTrue(said, f"{root}: the prompt never says postgres is not installed")

    @pytest.mark.shared_layout_mutator
    def test_adding_the_ability_delivers_it_on_next_build(self):
        # covers: AR-400d-2
        # angle: discrimination
        """Create .leafcutter/skills/postgres/SKILL.md and rebuild with no other edit: postgres is
        listed as available (the project's copy) and the informational line is gone. The first build
        must have printed the line (so its disappearance is a real change, not a never-printed line)."""
        sc = G.fresh("marked_absent")
        rc1, out1 = G.build(sc)
        self.assertEqual(len(_not_found_lines(out1)), 1, out1[-1200:])
        G.project_skill(sc.project, "postgres", G.PROJECT_MARK)
        rc2, out2 = G.build(sc)
        self.assertEqual((rc1, rc2), (0, 0), out2[-1200:])
        self.assertEqual(_not_found_lines(out2), [], "the report must disappear once the ability is supplied")
        for root, text in G.compiled(sc.project, "probe-coder").items():
            rows = G.ability_rows(text, "postgres")
            self.assertEqual(len(rows), 1, f"{root}: {rows}")
            self.assertIn(G.PROJECT_MARK, rows[0])


class TestOnlyTheProjectArea(unittest.TestCase):
    def _claude_skills_fixture(self):
        sc = G.fresh("marked_absent")
        G.project_skill(sc.project, "postgres", G.PROJECT_MARK, area=".claude")
        return sc, sc.project / ".claude" / "skills"

    @pytest.mark.shared_layout_mutator
    def test_ability_only_in_claude_skills_is_reported_not_found(self):
        # covers: AR-400d-2-i
        # angle: criterion
        # must_catch: the lookup falls back to .claude/skills
        """A REAL (non-symlink) .claude/skills/postgres/SKILL.md and an empty .leafcutter/skills: the
        gate (the build's own pre-deploy validation, ``--validate-only``) reports postgres not found,
        names the .leafcutter/skills location by ABSOLUTE path, and never points at .claude/skills."""
        sc, claude = self._claude_skills_fixture()
        self.assertFalse(claude.is_symlink())
        self.assertNotEqual(claude.resolve(), (sc.project / ".leafcutter" / "skills").resolve())
        self.assertFalse((sc.project / ".leafcutter" / "skills" / "postgres").exists())
        rc, out = G.build(sc, "--validate-only")
        lines = G.info_lines(out, "probe-coder", "postgres", r"not found")
        self.assertEqual(len(lines), 1, f"expected one 'not found' line: {out[-1500:]}")
        self.assertIn(str(sc.project / ".leafcutter" / "skills"), lines[0], "the report must name the absolute location")
        self.assertNotIn(".claude", lines[0])
        self.assertEqual(rc, 0, out[-1200:])

    def test_fixture_claude_skills_is_not_a_symlink_to_the_project_area(self):
        # covers: AR-400d-2-i
        # angle: boundary
        """Guard on the fixture itself: .claude/skills is a real directory and its resolved path
        differs from .leafcutter/skills, so the first descriptor cannot pass vacuously."""
        sc, claude = self._claude_skills_fixture()
        self.assertTrue(claude.is_dir() and not claude.is_symlink())
        self.assertNotEqual(claude.resolve(), (sc.project / ".leafcutter" / "skills").resolve())
        self.assertTrue((claude / "postgres" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
