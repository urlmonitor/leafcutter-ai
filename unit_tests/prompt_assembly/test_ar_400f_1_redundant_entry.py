"""AR-400f-1 -- a hand-off entry already covered by "every ticket-phase agent" stops the build, naming the
entry and what covers it (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400f-1.yaml.
Doors under test, both REAL: the validator CLI (``python scripts/registry_validator.py``) and
``scripts/build.py --target-dir`` (fresh subprocess over a full package copy; it must refuse BEFORE any
deploy phase). The fixture is one copied package holding ``probe-supervisor`` whose ``spawn_allowlist``
declaration lists ``__ticket_phase_agents__``, ``brainstorm-lead`` and ``llm-expert`` (llm-expert is a
ticket-phase agent, brainstorm-lead is not); its derived registry copy omits llm-expert, so a check that
reads the registry copy instead of the declaration finds nothing.

Today the same case prints ``[WARNING] ...is redundantly listed...`` and the build continues.
"""

from __future__ import annotations

import os
import sys
import unittest

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402


class TestRedundantEntryAtBothDoors(unittest.TestCase):
    def test_redundant_ticket_phase_entry_fails_both_doors(self):
        # covers: AR-400f-1
        # angle: criterion
        # must_catch: the check still prints a warning and returns nothing
        # must_catch: the check reads the registry copy
        """Both the validator CLI and the build exit non-zero with exactly one finding that names
        probe-supervisor, llm-expert and ``__ticket_phase_agents__`` as a redundant hand-off entry;
        neither prints a ``[WARNING]`` about redundancy; the build deployed no compiled prompt."""
        run = X.redundant_run()
        for door in ("validator", "build"):
            rc, out = run[door]
            hits = X.hand_off_hits(out)
            self.assertEqual(len(hits), 1, f"{door}: expected one redundant-entry finding, got {hits}: {out[-900:]}")
            self.assertIn(X.REDUNDANT, hits[0].lower(), f"{door}: {hits[0]}")
            self.assertTrue(X.names_all(hits[0], X.SUP, "llm-expert", X.MACRO), f"{door}: {hits[0]}")
            self.assertEqual(X.redundancy_warnings(out), [], f"{door}: the finding must be a failure, not a warning")
            self.assertNotEqual(rc, 0, f"{door}: exit {rc} on a redundant declaration: {out[-900:]}")
        self.assertEqual(X.compiled_agent_roots(run["root"].parent), [], "the build deployed despite the finding")

    def test_uncovered_explicit_entry_is_not_a_finding(self):
        # covers: AR-400f-1
        # angle: discrimination
        # must_catch: every explicit entry beside the macro is flagged, covered or not
        """In the same runs brainstorm-lead (not a ticket-phase agent, so the macro does not cover it)
        produces no finding, while the control finding for llm-expert IS there -- so the silence is
        the check discriminating, not the check being absent."""
        run = X.redundant_run()
        self.assertFalse(X.is_phase(run["root"], "brainstorm-lead"), "precondition: brainstorm-lead is not ticket-phase")
        for door in ("validator", "build"):
            out = run[door][1]
            hits = X.hand_off_hits(out)
            self.assertEqual([h for h in hits if X.F.names(h, "brainstorm-lead")], [], f"{door}: {hits}")
            self.assertEqual(len([h for h in hits if X.F.names(h, "llm-expert")]), 1, f"{door}: control row missing: {hits}")

    @pytest.mark.shared_layout_mutator
    def test_removing_redundant_entry_passes_and_delivers_llm_expert_once(self):
        # covers: AR-400f-1
        # angle: deployed
        # must_catch: removing the entry drops llm-expert from the compiled hand-off list
        """Start from the failing declaration (the validator refuses it), remove llm-expert from the
        declaration only: the validator and a real ``build.py`` into a fresh project both pass, and the
        DEPLOYED probe-supervisor prompt in every platform root names llm-expert (through the covering
        entry) and brainstorm-lead each exactly once."""
        root = X.new_package()
        X.plant_redundant(root)
        rc, out = H.cli(root)
        self.assertNotEqual(rc, 0, "precondition: the redundant declaration must be refused")
        self.assertEqual(len(X.hand_off_hits(out)), 1, out[-900:])
        X.declare_spawn(root, X.SUP, [X.MACRO, "brainstorm-lead"])
        v_rc, v_out = H.cli(root)
        self.assertEqual((v_rc, X.hand_off_hits(v_out)), (0, []), v_out[-900:])
        b_rc, b_out = X.run_build(root, root.parent)
        self.assertEqual(b_rc, 0, b_out[-1500:])
        self.assertEqual(X.hand_off_hits(b_out), [], b_out[-900:])
        prompts = X.compiled_prompts(root.parent, X.SUP)
        self.assertGreaterEqual(len(prompts), 2, f"expected both platform roots, got {sorted(prompts)}")
        for where, text in prompts.items():
            ids = X.hand_off_ids(text, X.SUP)
            self.assertEqual(ids.count("llm-expert"), 1, f"{where}: llm-expert named {ids.count('llm-expert')}x")
            self.assertEqual(ids.count("brainstorm-lead"), 1, f"{where}: brainstorm-lead named {ids.count('brainstorm-lead')}x")


if __name__ == "__main__":
    unittest.main()
