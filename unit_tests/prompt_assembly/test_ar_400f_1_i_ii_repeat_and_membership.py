"""AR-400f-1-i (the same specialist listed twice in one declaration) and AR-400f-1-ii (redundancy is
judged against ticket-phase membership on each build) -- TDD red phase.

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400f-1-i.yaml
and AR-400f-1-ii.yaml. Doors: the validator CLI and ``build.py --validate-only`` (the build's validation
phase, no deploy), both real; the commit-time transform is run through its real entry point.

f-1-i feeds the RAW declaration (a repeat) to the doors: the derived registry copy is de-duplicated, so a
check over it can never see the repeat. f-1-ii holds the declaration constant and flips only
``is_ticket_phase`` in the registry.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402

CODER = "probe-coder"


class TestRepeatedEntry(unittest.TestCase):
    def _assert_one_repeat(self, root, entry: str) -> None:
        for door, (rc, out) in X.two_doors(root).items():
            hits = X.hand_off_hits(out, X.TWICE)
            self.assertEqual(len(hits), 1, f"{door}: expected one finding, got {hits}: {out[-900:]}")
            self.assertTrue(X.names_all(hits[0], CODER, entry), f"{door}: {hits[0]}")
            self.assertEqual(X.hand_off_hits(out, X.REDUNDANT), [], f"{door}: a repeat is not a covered entry: {out[-600:]}")
            self.assertNotEqual(rc, 0, f"{door}: exit {rc} on a repeated entry")

    def test_entry_listed_twice_fails_naming_specialist_and_entry(self):
        # covers: AR-400f-1-i
        # angle: criterion
        # must_catch: the check reads the de-duplicated registry copy and sees nothing
        """probe-coder declares [research-agent, research-agent] and no covering entry. The registry copy
        holds research-agent once (control: the repeat is invisible there); both doors stop with one
        finding naming probe-coder and research-agent as listed twice."""
        root = X.new_package()
        X.plant_handoff(root, CODER, ["research-agent", "research-agent"])
        self.assertEqual(X.declared_spawn_of(root, CODER), ["research-agent", "research-agent"])
        self.assertEqual(X.registry_spawn_of(root, CODER), ["research-agent"], "control: the derived copy hides the repeat")
        self._assert_one_repeat(root, "research-agent")

    def test_macro_listed_twice_fails_the_same_way(self):
        # covers: AR-400f-1-i
        # angle: boundary
        """A declaration listing ``__ticket_phase_agents__`` twice stops both doors with one finding of
        the same kind. Control row: the same specialist declaring the macro ONCE passes both doors with
        no finding, so the check flags the repeat and not the macro."""
        root = X.new_package()
        X.plant_handoff(root, CODER, [X.MACRO, X.MACRO])
        self._assert_one_repeat(root, X.MACRO)
        X.declare_spawn(root, CODER, [X.MACRO])
        for door, (rc, out) in X.two_doors(root).items():
            self.assertEqual((rc, X.hand_off_hits(out)), (0, []), f"{door}: a single macro must pass: {out[-900:]}")


class TestMembershipJudgedOnEachBuild(unittest.TestCase):
    @staticmethod
    def _mine(out: str) -> list[str]:
        """The redundant-entry findings about probe-supervisor (flipping brainstorm-lead to ticket-phase
        also makes the REAL ticket-supervisor's explicit brainstorm-lead entry redundant)."""
        return [h for h in X.hand_off_hits(out) if X.F.names(h, X.SUP)]

    def _root(self):
        """probe-supervisor declares [macro, brainstorm-lead]; brainstorm-lead is NOT ticket-phase."""
        root = X.new_package()
        X.plant_handoff(root, X.SUP, [X.MACRO, "brainstorm-lead"])
        self.assertFalse(X.is_phase(root, "brainstorm-lead"))
        return root

    def test_entry_becomes_redundant_when_target_turns_ticket_phase(self):
        # covers: AR-400f-1-ii
        # angle: criterion
        """The build passes with brainstorm-lead listed beside the macro. Then brainstorm-lead is marked
        ticket-phase in the registry ONLY (the declaration is byte-identical) and both doors stop with
        the redundant-entry finding for probe-supervisor / brainstorm-lead."""
        root = self._root()
        for door, (rc, out) in X.two_doors(root).items():
            self.assertEqual((rc, X.hand_off_hits(out)), (0, []), f"{door}: baseline must pass: {out[-900:]}")
        declaration = (root / X.F.agent_rel(X.SUP)).read_bytes()
        X.set_phase(root, "brainstorm-lead", True)
        self.assertEqual((root / X.F.agent_rel(X.SUP)).read_bytes(), declaration)
        for door, (rc, out) in X.two_doors(root).items():
            hits = self._mine(out)  # the real ticket-supervisor lists brainstorm-lead beside the macro too
            self.assertEqual(len(hits), 1, f"{door}: expected one finding, got {hits}: {out[-900:]}")
            self.assertIn(X.REDUNDANT, hits[0].lower())
            self.assertTrue(X.names_all(hits[0], X.SUP, "brainstorm-lead"), f"{door}: {hits[0]}")
            self.assertNotEqual(rc, 0, f"{door}: exit {rc} once the entry became redundant")
            self.assertEqual(X.redundancy_warnings(out), [], f"{door}: must be a failure, not a warning")

    def test_reverting_membership_passes_and_keeps_the_hand_off(self):
        # covers: AR-400f-1-ii
        # angle: discrimination
        # must_catch: the redundant entry is auto-stripped from the declaration or the registry
        """Flip brainstorm-lead to ticket-phase (refused), run the commit-time transform, flip it back:
        the declaration and the derived copy still list brainstorm-lead (nothing was stripped), both doors
        pass, and probe-supervisor's compiled hand-off list names brainstorm-lead exactly once."""
        root = self._root()
        X.set_phase(root, "brainstorm-lead", True)
        self.assertEqual(len(self._mine(H.cli(root)[1])), 1, "precondition: the flipped state must be refused")
        self.assertEqual(X.E.run_hook(root).returncode, 0)
        self.assertEqual(X.declared_spawn_of(root, X.SUP), [X.MACRO, "brainstorm-lead"], "the declaration was edited")
        self.assertEqual(X.registry_spawn_of(root, X.SUP), [X.MACRO, "brainstorm-lead"], "the derived copy was stripped")
        X.set_phase(root, "brainstorm-lead", False)
        for door, (rc, out) in X.two_doors(root).items():
            self.assertEqual((rc, X.hand_off_hits(out)), (0, []), f"{door}: reverted membership must pass: {out[-900:]}")
        agents = X.H._registry(root)["agents"]
        text = X.compile_template(root / X.F.agent_rel(X.SUP), agents, root / "config" / "agent_registry.json")
        self.assertEqual(X.hand_off_ids(text, X.SUP).count("brainstorm-lead"), 1)


if __name__ == "__main__":
    unittest.main()
