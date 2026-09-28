"""
MODULE: unit_tests/ac_store/test_tkt_500f_5.py
GOAL: Tests for TKT-500f-5 — an AC-to-ticket generator must never emit an agent
      whose registry entry has ``is_ticket_phase: false`` as the generated
      ticket's phase agent. It substitutes a real phase agent (llm-expert for
      agent/skill-template work, python-coder otherwise) and records a warning
      naming the substitute, the original assigned_agent and the AC id. An
      ``is_ticket_phase: true`` agent passes through untouched and silently.
COVERS: TKT-500f-5

RED expectation at authoring time (2026-09-14): neither generator reads
``is_ticket_phase`` at all — ``grep -rn is_ticket_phase scripts/`` matches only
generate_agent_diagram.py, injection_builders.py, leafcutter_inventory.py and
registry_validator.py, none of which is on the ticket-generation path. A probe
run confirms ``assigned_agent: workflow-architect`` (is_ticket_phase: false)
emits ``workflow-architect: needed`` verbatim into the generated ticket's
agents map, with no warning. Five of the six tests below are therefore RED; the
pass-through control is GREEN on arrival by construction, which is what makes
it a control.

SCOPE OF "NAMES THAT AGENT": the assertions below read the frontmatter
``agents:`` map and the ``## Sign-offs`` checkbox list — the two places that
decide what the ticket-supervisor actually dispatches. The body's Context
paragraph echoes the AC's own ``assigned_agent`` as prose; that echo is a
record of what the AC said, not a dispatch instruction, so it is deliberately
out of scope here.

NOTE ON PATCHING: nothing is patched. See _tkt_500f_support's ARCHITECTURE note
— after the 8b2b899ae module split, a ``patch("goal_to_epic.X")`` rebinds a
re-exported name that nothing calls and silently runs the real code instead.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _tkt_500f_support import (  # noqa: E402
    IMPL_PY,
    SKILL_TEMPLATE_MD,
    TEMPLATE_MD,
    agent_registry_entries,
    generate_dry_run,
    make_ac,
)

_NON_PHASE_AGENT = "workflow-architect"
_PHASE_AGENT = "python-coder"


class TestNonPhaseAgentSubstitution(unittest.TestCase):
    """TKT-500f-5: a non-ticket-phase assigned_agent is replaced, loudly."""

    def test_non_phase_agent_is_not_named_as_the_ticket_phase_agent(self):
        # covers: TKT-500f-5
        # angle: criterion
        """An is_ticket_phase:false agent must not reach the ticket's agents map.

        ``workflow-architect`` is chosen because the AC names it and because the
        real registry records ``is_ticket_phase: false`` for it. The generated
        ticket must not dispatch it — neither as an ``agents:`` entry nor as a
        ``## Sign-offs`` checkbox — because the ticket-supervisor has no phase
        slot to run it in, so a ticket that names it stalls.
        """
        generated = generate_dry_run(
            make_ac(assigned_agent=_NON_PHASE_AGENT, files_touched=[IMPL_PY]),
            "TKT-500f-5-non-phase",
        )

        self.assertNotIn(
            _NON_PHASE_AGENT,
            generated.phase_agents(),
            f"{_NON_PHASE_AGENT!r} has is_ticket_phase: false in "
            "config/agent_registry.json, so it must not appear as a dispatched "
            f"phase in the generated agents map. Got: {sorted(generated.phase_agents())}",
        )
        self.assertNotIn(
            _NON_PHASE_AGENT,
            generated.signoff_agents(),
            f"{_NON_PHASE_AGENT!r} must not be given a ## Sign-offs checkbox "
            "either — a sign-off slot for an agent that never runs is an "
            f"unsatisfiable gate. Got: {sorted(generated.signoff_agents())}",
        )

    def test_template_editing_work_substitutes_llm_expert(self):
        # covers: TKT-500f-5
        # angle: criterion
        """Agent-template and skill-template work substitutes ``llm-expert``.

        This is the first branch of the substitution rule. Both template
        surfaces the rule names (``templates/agents/*`` and
        ``templates/skills/*``) are asserted, because an implementation that
        matched only ``templates/agents/`` would satisfy a single-surface test
        while routing every skill-template ticket to python-coder.
        """
        offenders: list[str] = []
        for surface in (TEMPLATE_MD, SKILL_TEMPLATE_MD):
            generated = generate_dry_run(
                make_ac(assigned_agent=_NON_PHASE_AGENT, files_touched=[surface]),
                f"TKT-500f-5-tmpl-{surface.split('/')[1]}",
            )
            if "llm-expert" not in generated.phase_agents():
                offenders.append(f"{surface} -> {sorted(generated.phase_agents())}")

        self.assertEqual(
            offenders,
            [],
            "Work whose edit surface is an agent or skill template must "
            f"substitute llm-expert for {_NON_PHASE_AGENT!r}. These surfaces "
            f"did not get it: {offenders}",
        )

    def test_all_other_work_substitutes_python_coder(self):
        # covers: TKT-500f-5
        # angle: criterion
        """Non-template work substitutes ``python-coder`` — the second branch.

        Asserting both branches is the point: an implementation that returns a
        single constant substitute passes whichever branch matches that constant
        and fails the other. This test also asserts llm-expert is NOT chosen, so
        a constant ``llm-expert`` return cannot slip through on the strength of
        the previous test alone.
        """
        generated = generate_dry_run(
            make_ac(assigned_agent=_NON_PHASE_AGENT, files_touched=[IMPL_PY]),
            "TKT-500f-5-other-work",
        )

        self.assertIn(
            _PHASE_AGENT,
            generated.phase_agents(),
            "Work that is not agent/skill-template editing must substitute "
            f"python-coder. files_touched={generated.frontmatter.get('files_touched')}, "
            f"phase agents={sorted(generated.phase_agents())}",
        )
        self.assertNotIn(
            "llm-expert",
            generated.phase_agents(),
            "llm-expert is the template-work branch only; choosing it for a "
            "plain .py edit surface means the substitute is a constant rather "
            f"than a decision. Phase agents: {sorted(generated.phase_agents())}",
        )

    def test_substitution_warning_names_substitute_and_original_agent(self):
        # covers: TKT-500f-5
        # angle: criterion
        """The warning must carry all three facts, asserted separately.

        A bare "substitution occurred" string serves none of the warning's
        diagnostic purpose: the reader needs to know WHICH agent was rejected,
        WHAT replaced it, and on WHICH AC — otherwise the only way to act on the
        warning is to re-derive it by hand. Each fact is therefore its own
        assertion, so a message missing one of them cannot pass on the strength
        of the other two.
        """
        ac_id = "TKT-500f-5-warning"
        generated = generate_dry_run(
            make_ac(assigned_agent=_NON_PHASE_AGENT, files_touched=[IMPL_PY]),
            ac_id,
        )
        warnings = generated.warnings

        self.assertTrue(
            warnings.strip(),
            "Substituting the phase agent silently is the failure mode this "
            "clause exists to prevent: the ticket no longer matches the AC's "
            "assigned_agent and nothing says so. No warning was recorded.",
        )
        self.assertIn(
            _NON_PHASE_AGENT,
            warnings,
            "The warning must name the AC's ORIGINAL assigned_agent so the "
            f"author can fix the AC. Got: {warnings!r}",
        )
        self.assertIn(
            _PHASE_AGENT,
            warnings,
            "The warning must name the SUBSTITUTE that was used instead. "
            f"Got: {warnings!r}",
        )
        self.assertIn(
            ac_id,
            warnings,
            "The warning must name the AC id — a substitution notice that does "
            "not say which AC it came from is unactionable in a batch run that "
            f"generates dozens of tickets. Got: {warnings!r}",
        )

    def test_phase_agent_passes_through_unchanged_with_no_warning(self):
        # covers: TKT-500f-5
        # angle: boundary
        """The second Given: a real phase agent survives untouched and silently.

        This is the control that stops the substitution firing on everything. An
        implementation that substitutes unconditionally satisfies the four tests
        above and fails here; so does one that warns on every generation, which
        would turn the warning channel into noise nobody reads.
        """
        generated = generate_dry_run(
            make_ac(assigned_agent=_PHASE_AGENT, files_touched=[IMPL_PY]),
            "TKT-500f-5-passthrough",
        )

        self.assertIn(
            _PHASE_AGENT,
            generated.phase_agents(),
            f"{_PHASE_AGENT!r} has is_ticket_phase: true and must be named as "
            f"the phase agent unchanged. Got: {sorted(generated.phase_agents())}",
        )
        self.assertNotIn(
            "substitut",
            generated.warnings.lower(),
            "No substitution warning may be recorded when the assigned agent is "
            f"already a valid ticket phase. Got: {generated.warnings!r}",
        )

    def test_substitution_reads_is_ticket_phase_from_the_real_registry(self):
        # covers: TKT-500f-5
        # angle: real_artifact
        """The decision must track config/agent_registry.json, not a name list.

        The two agent sets below are read out of the REAL registry file rather
        than hand-typed, then EVERY member of each is driven through the
        generator. A hard-coded allow/deny list — the obvious shortcut, e.g.
        special-casing ``workflow-architect`` — passes every other test in this
        file and fails here on the other 35 non-phase agents. It also means a
        newly registered phase agent inherits the behaviour for free, which is
        the property this angle exists to pin down.
        """
        entries = agent_registry_entries()
        non_phase = sorted(
            e["id"] for e in entries if e.get("is_ticket_phase") is not True
        )
        phase = sorted(e["id"] for e in entries if e.get("is_ticket_phase") is True)
        self.assertTrue(non_phase and phase, "registry must contain both kinds")

        wrongly_kept = [
            agent_id
            for agent_id in non_phase
            if agent_id
            in generate_dry_run(
                make_ac(assigned_agent=agent_id, files_touched=[IMPL_PY]),
                "TKT-500f-5-registry-negative",
            ).phase_agents()
        ]
        wrongly_dropped = [
            agent_id
            for agent_id in phase
            if agent_id
            not in generate_dry_run(
                make_ac(assigned_agent=agent_id, files_touched=[IMPL_PY]),
                "TKT-500f-5-registry-positive",
            ).phase_agents()
        ]

        self.assertEqual(
            wrongly_kept,
            [],
            "Every agent the real registry marks is_ticket_phase: false must be "
            "substituted out. These survived as phase agents, which means the "
            "decision is not being read from config/agent_registry.json. "
            "Special-casing a single name (workflow-architect, say) passes the "
            f"rest of this file and leaves exactly this list behind: {wrongly_kept}",
        )
        self.assertEqual(
            wrongly_dropped,
            [],
            "Every agent the real registry marks is_ticket_phase: true must "
            "pass through unchanged. These were dropped, which means the "
            f"substitution is over-firing on agents it should leave alone: "
            f"{wrongly_dropped}",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-5/test-writer]: Initial tests from the AC's six test_spec
  descriptors, one test per descriptor. Assertions read the frontmatter agents
  map and the ## Sign-offs list rather than scanning the whole ticket text,
  because the Context paragraph legitimately echoes the AC's assigned_agent as
  prose and a whole-text search would make the pass-through control and the
  substitution tests contradict each other. The real_artifact test iterates the
  entire registry (60 entries, ~0.5s in-process) instead of sampling, so a
  hard-coded name list has nowhere to hide.
====================================================================
"""
