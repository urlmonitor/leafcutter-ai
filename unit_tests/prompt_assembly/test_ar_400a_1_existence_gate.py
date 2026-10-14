"""AR-400a-1 -- an instruction to use an ability that exists nowhere stops the build,
naming the specialist, the ability and the line (TDD red phase: the gate is not wired).

Doors: the real validator CLI (fresh subprocess over a COPIED package slice), the build's
decision point ``build._validate_all`` (returns 1 == abort), and -- for the one "refuses
before anything is deployed" claim that only a real build can prove -- a real ``build.py``
spawn over a full package copy, declared ``shared_layout_mutator`` (it mutates the package
before building, so it must not share the reference layout). The refusing build exits before
any deploy phase, so on the GREEN tree it is cheap; it is slow only while red.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402


class TestExistenceGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)

    def _ghost_probe(self):
        return H.plant_agent(self.root, "probe-agent", sentence=H.GHOST_SENTENCE, line=40)

    def test_nonexistent_ability_instruction_fails_validator_naming_agent_ability_file_line(self):
        # covers: AR-400a-1
        # angle: criterion
        """Probe-agent grants nothing; line 40 says to load an ability nobody ships. The CLI
        exits 1 with ONE ERROR (never [WARNING]) naming probe-agent, ghost-ability, the file
        and line 40, kind 'ability does not exist'; the old cross-reference is not left wired.
        Control: the slice before planting exits 0."""
        rc0, out0 = H.cli(self.root)
        self.assertEqual(rc0, 0, out0)  # control: clean slice passes
        path = self._ghost_probe()
        self.assertEqual(path.read_text(encoding="utf-8").splitlines()[39], H.GHOST_SENTENCE)
        rc, out = H.cli(self.root)
        hits = H.findings(out, H.GHOST, "probe-agent")
        self.assertEqual(len(hits), 1, f"expected exactly one finding for probe-agent: {out}")
        self.assertTrue(hits[0].startswith("ERROR:"), hits[0])
        self.assertNotIn("[WARNING]", hits[0])
        self.assertTrue(H.names_line(hits[0], "templates/agents/probe-agent.md", 40), hits[0])
        self.assertEqual(rc, 1, f"a finding must exit non-zero: {out}")
        xref = [ln for ln in H.lines_of(out) if "skills_invoked" in ln]
        self.assertEqual(xref, [], f"old check_skills_invoked_xref still wired: {xref[:3]}")

    @pytest.mark.shared_layout_mutator
    def test_build_refuses_before_deploy_on_nonexistent_ability(self):
        # covers: AR-400a-1
        # angle: deployed
        """A REAL ``build.py --target-dir <tmp>`` over a full package copy holding the ghost
        probe exits non-zero printing the same finding (specialist, ability, line 40), and
        wrote no compiled agent into the target -- refusal precedes every deploy phase."""
        root = H.make_build_package(self._tmp.name + "/full")
        H.plant_agent(root, "probe-agent", sentence=H.GHOST_SENTENCE, line=40)
        target = Path(self._tmp.name) / "target"
        target.mkdir()
        cp = subprocess.run([sys.executable, str(root / "scripts" / "build.py"), "--target-dir", str(target)],
                            capture_output=True, text=True, timeout=600, check=False)
        out = cp.stdout + "\n" + cp.stderr
        hits = H.findings(out, H.GHOST, "probe-agent")
        self.assertTrue(hits, f"build printed no ghost-ability finding for probe-agent: {out[-1500:]}")
        self.assertTrue(any(H.names_line(h, "templates/agents/probe-agent.md", 40) for h in hits), hits)
        self.assertNotEqual(cp.returncode, 0, out[-1500:])
        self.assertEqual([p.name for p in target.rglob("*.md")], [], "build deployed agents despite the finding")
        self.assertEqual(list(target.rglob("probe-agent*")), [])

    def test_examined_counts_equal_definitions_and_guides_present(self):
        # covers: AR-400a-1
        # angle: boundary
        """The run states definitions-examined and guides-examined, each equal to the count
        derived independently from the copied tree. One extra specialist and one extra
        guide are planted so a hard-coded or stale figure cannot match; the two expected
        figures differ so swapped figures cannot match either."""
        H.plant_agent(self.root, "probe-agent")
        H.plant_skill(self.root, "probe-skill")
        defs, guides = H.expected_counts(self.root)
        self.assertNotEqual(defs, guides)
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn(defs, H.reported(out, "definition"), f"definitions-examined {defs} not stated: {out}")
        self.assertIn(guides, H.reported(out, "guide"), f"guides-examined {guides} not stated: {out}")

    def test_adding_and_granting_ghost_ability_clears_the_finding(self):
        # covers: AR-400a-1
        # angle: discrimination
        """Wrong version caught: a check that flags every Load sentence (or flags once and
        never clears). Paired: the SAME probe fails first, then adding ghost-ability to the
        package and granting it to probe-agent makes the same run exit 0 with no finding."""
        self._ghost_probe()
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 1, out)
        self.assertEqual(len(H.findings(out, H.GHOST, "probe-agent")), 1, out)  # positive case fails
        H.plant_skill(self.root, H.GHOST)
        H.grant_to(self.root, "probe-agent", H.GHOST)
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 0, out)
        self.assertEqual(H.findings(out, H.GHOST), [], out)


if __name__ == "__main__":
    unittest.main()
