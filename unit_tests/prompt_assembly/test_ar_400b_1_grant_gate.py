"""AR-400b-1 / AR-400b-1-i -- an instruction to use an ability the specialist's OWN definition does
not grant stops the build, naming both sides; the derived central registry is never the grant side
(TDD red phase: the grant comparison does not exist yet).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400b-1.yaml and AR-400b-1-i.yaml. Every test drives the REAL validator CLI in a fresh
subprocess over a COPIED package slice (see ``_ar400_3a_fixtures`` for the assumed finding shape).

Negative / control rows are paired with a row that MUST produce a finding, so a gate that does not
exist yet cannot make them pass vacuously.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

LOAD_KQ = "load the `knowledge-query` skill to search the graph"
LOAD_SIGNOFF = "load the `signoff` skill"
PROBE = "probe-agent"


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)


class TestOwnDeclarationIsTheGrantSide(_Base):
    def _probe(self):
        return F.plant(self.root, PROBE, [LOAD_KQ], grants=("signoff",), at_line=88)

    def test_ungranted_existing_ability_fails_naming_both_sides(self):
        # covers: AR-400b-1
        # angle: criterion
        """probe-agent grants only signoff; line 88 says to load knowledge-query (which exists).
        The CLI exits 1 with exactly ONE 'not granted' finding naming probe-agent, knowledge-query,
        the file, line 88 and the declared grant list (signoff) on the same line."""
        path = self._probe()
        self.assertEqual(path.read_text(encoding="utf-8").splitlines()[87], LOAD_KQ)
        rc, out = H.cli(self.root)
        hits = F.of_kind(out, F.UNGRANTED, "knowledge-query", PROBE)
        self.assertEqual(len(hits), 1, f"expected one 'not granted' finding: {out[-1500:]}")
        self.assertTrue(H.names_line(hits[0], F.agent_rel(PROBE), 88), hits[0])
        self.assertTrue(F.names(hits[0], "signoff"), f"finding must state the declared grant 'signoff': {hits[0]}")
        self.assertEqual(F.about(out, PROBE), hits, "probe-agent must have no finding besides the one")
        self.assertEqual(rc, 1, out[-800:])

    def test_adding_grant_to_own_declaration_clears_the_finding(self):
        # covers: AR-400b-1
        # angle: discrimination
        """Wrong version caught: a check that flags every instruction, or one that reads the derived
        registry (left STALE here -- only the own `skills:` frontmatter gains the grant). The same
        probe fails first; adding knowledge-query to its OWN definition makes the run pass."""
        self._probe()
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 1, out[-800:])
        self.assertEqual(len(F.of_kind(out, F.UNGRANTED, "knowledge-query", PROBE)), 1, out[-800:])
        F.add_template_grant(self.root, PROBE, "knowledge-query")
        rc, out = H.cli(self.root)
        self.assertEqual(F.about(out, PROBE), [], out[-800:])
        self.assertEqual(rc, 0, out[-800:])

    def test_granted_signoff_with_registry_lacking_it_produces_no_finding(self):
        # covers: AR-400b-1
        # angle: discrimination
        # must_catch: the comparison reads registry skills_invoked
        # must_catch: the comparison reads registry skills_used
        """The 2026-10-12 real false positive. probe-agent GRANTS signoff and says 'load the signoff
        skill', while its registry entry omits signoff from every ability field. Control row in the
        same run: probe-control grants nothing and says the same -> exactly one finding."""
        F.plant(self.root, PROBE, [LOAD_SIGNOFF], grants=("signoff",), registry_grants=())
        # skills_used is a RETIRED registry field (the validator refuses it), so "every ability
        # field" is skills_invoked alone: emptied here, skills_used absent.
        F.edit_registry(self.root, PROBE, skills_invoked=[])
        F.plant(self.root, "probe-control", [LOAD_SIGNOFF])
        rc, out = H.cli(self.root)
        self.assertEqual(len(F.of_kind(out, F.UNGRANTED, "signoff", "probe-control")), 1, out[-1200:])
        self.assertEqual(F.about(out, PROBE), [], "a registry that lacks signoff must not create a finding")
        self.assertEqual(rc, 1, out[-800:])


class TestHandEditedRegistryDoesNotSatisfyTheCheck(_Base):
    def _probe_with_registry_edit(self):
        F.plant(self.root, PROBE, [LOAD_KQ], grants=("signoff",))
        F.edit_registry(self.root, PROBE, skills_invoked=[
            {"skill_id": "signoff", "mode": "always"}, {"skill_id": "knowledge-query", "mode": "always"}])

    def test_hand_edited_registry_does_not_satisfy_the_grant_check(self):
        # covers: AR-400b-1-i
        # angle: discrimination
        # must_catch: the grant side is the union of declaration and registry
        """knowledge-query planted in probe-agent's registry skills_invoked ONLY: the declaration
        still grants just signoff, so the CLI still fails with the 'not granted' finding."""
        self._probe_with_registry_edit()
        rc, out = H.cli(self.root)
        self.assertEqual(len(F.of_kind(out, F.UNGRANTED, "knowledge-query", PROBE)), 1, out[-1200:])
        self.assertEqual(rc, 1, out[-800:])

    def test_finding_is_identical_with_and_without_the_registry_edit(self):
        # covers: AR-400b-1-i
        # angle: criterion
        """Run twice, without and with the hand edit: the finding lines are byte-identical, and
        neither run rewrites config/agent_registry.json."""
        F.plant(self.root, PROBE, [LOAD_KQ], grants=("signoff",))
        reg = self.root / "config" / "agent_registry.json"
        before = hashlib.sha256(reg.read_bytes()).hexdigest()
        _, out_plain = H.cli(self.root)
        self.assertEqual(hashlib.sha256(reg.read_bytes()).hexdigest(), before, "run 1 rewrote the registry")
        F.edit_registry(self.root, PROBE, skills_invoked=[
            {"skill_id": "signoff", "mode": "always"}, {"skill_id": "knowledge-query", "mode": "always"}])
        edited = hashlib.sha256(reg.read_bytes()).hexdigest()
        _, out_edit = H.cli(self.root)
        self.assertEqual(hashlib.sha256(reg.read_bytes()).hexdigest(), edited, "run 2 rewrote the registry")
        plain, with_edit = F.about(out_plain, PROBE), F.about(out_edit, PROBE)
        self.assertEqual(len(plain), 1, out_plain[-1200:])
        self.assertEqual(plain, with_edit, "the registry edit changed the finding")


if __name__ == "__main__":
    unittest.main()
