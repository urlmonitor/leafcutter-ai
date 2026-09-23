"""
MODULE: unit_tests/ac_store/test_tkt_500f_5_i.py
GOAL: Tests for TKT-500f-5-i — an assigned_agent with NO entry at all in the
      agent registry is treated exactly like an ``is_ticket_phase: false``
      entry: never emitted as the ticket's phase agent, replaced by the same
      substitution rule TKT-500f-5 defines, announced by a warning that says
      "not found in the registry" (distinctly from the non-phase wording), and
      never allowed to abort generation with an unhandled error.
COVERS: TKT-500f-5-i

RED expectation at authoring time (2026-09-14): the generator does no registry
lookup whatsoever on the assigned_agent, so ``made-up-agent`` is copied straight
into the generated ticket's agents map as ``made-up-agent: needed``. Three of
the four tests below are RED. The fourth — "generation completes without an
unhandled error" — is GREEN on arrival precisely BECAUSE no lookup happens
today; it is the regression guard that stops the fix introducing the KeyError
it is meant to prevent, so its value is entirely forward-looking.

NOTE ON PATCHING: nothing is patched — see _tkt_500f_support's ARCHITECTURE
note on the 8b2b899ae module split.
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
    generate_written,
    make_ac,
)

#: An agent id deliberately absent from config/agent_registry.json. Asserted
#: absent in setUpModule below so this file cannot rot into a false pass if the
#: name is ever registered for real.
_UNKNOWN_AGENT = "made-up-agent"


def setUpModule() -> None:
    """Fail loudly if the "unknown" fixture agent has become a real registry entry.

    Raises:
        AssertionError: When ``made-up-agent`` is present in the real registry,
            which would silently turn every test in this file into a test of the
            known-agent path instead.
    """
    known = {e.get("id") for e in agent_registry_entries()}
    if _UNKNOWN_AGENT in known:
        raise AssertionError(  # noqa: TRY003
            f"{_UNKNOWN_AGENT!r} is now a real entry in "
            "config/agent_registry.json; pick a different absent id, or this "
            "whole file silently stops testing the unknown-agent path."
        )


class TestUnknownAgentSubstitution(unittest.TestCase):
    """TKT-500f-5-i: an agent absent from the registry is ineligible, not trusted."""

    def test_unknown_agent_is_not_named_as_the_ticket_phase_agent(self):
        # covers: TKT-500f-5-i
        # angle: criterion
        """An assigned_agent with no registry entry must never be dispatched.

        A missing entry is strictly less trustworthy than an
        ``is_ticket_phase: false`` entry — there is not even a record saying the
        name refers to an agent — so the ticket must not name it as a phase, and
        must not open a sign-off slot for it that nothing can ever fill.
        """
        generated = generate_dry_run(
            make_ac(assigned_agent=_UNKNOWN_AGENT, files_touched=[IMPL_PY]),
            "TKT-500f-5-i-unknown",
        )

        self.assertNotIn(
            _UNKNOWN_AGENT,
            generated.phase_agents(),
            f"{_UNKNOWN_AGENT!r} has no entry in config/agent_registry.json, so "
            "it must be treated as ineligible and substituted out rather than "
            f"emitted verbatim. Got: {sorted(generated.phase_agents())}",
        )
        self.assertNotIn(
            _UNKNOWN_AGENT,
            generated.signoff_agents(),
            f"{_UNKNOWN_AGENT!r} must not be given a ## Sign-offs checkbox — no "
            "agent exists to tick it, so the ticket could never complete. "
            f"Got: {sorted(generated.signoff_agents())}",
        )

    def test_unknown_agent_substitution_follows_the_same_rule_as_non_phase(self):
        # covers: TKT-500f-5-i
        # angle: criterion
        """Both branches of TKT-500f-5's rule must apply to the unknown path too.

        Template work goes to llm-expert, everything else to python-coder. Both
        are asserted in one test because the risk this descriptor guards is the
        absent-from-registry path quietly acquiring its OWN private default — a
        second code branch that happens to agree with the shared rule on one
        case and diverges on the other. Checking a single branch cannot see that.
        """
        cases = (
            (IMPL_PY, "python-coder", "llm-expert"),
            (TEMPLATE_MD, "llm-expert", "python-coder"),
            (SKILL_TEMPLATE_MD, "llm-expert", "python-coder"),
        )
        wrong: list[str] = []
        for surface, expected, forbidden in cases:
            generated = generate_dry_run(
                make_ac(assigned_agent=_UNKNOWN_AGENT, files_touched=[surface]),
                "TKT-500f-5-i-same-rule",
            )
            phases = generated.phase_agents()
            if expected not in phases or forbidden in phases:
                wrong.append(
                    f"{surface}: expected {expected!r} and not {forbidden!r}, "
                    f"got {sorted(phases)}"
                )

        self.assertEqual(
            wrong,
            [],
            "An unknown assigned_agent must be substituted by the SAME rule "
            "TKT-500f-5 defines — llm-expert for agent/skill-template surfaces, "
            "python-coder otherwise. A branch that agrees on one surface and "
            "diverges on another is the private-default failure this descriptor "
            f"guards. Wrong: {wrong}",
        )

    def test_unknown_agent_warning_names_registry_miss_substitute_and_ac_id(self):
        # covers: TKT-500f-5-i
        # angle: criterion
        """Three separate facts, plus the wording that distinguishes this case.

        The it_requirements are explicit that the unknown-agent warning must be
        distinguishable from the non-phase-agent warning: the remedy differs
        (register the agent, or fix a typo in the AC — versus reassign to a
        phase agent). So this asserts not only that a warning exists naming the
        original, the substitute and the AC id, but that its wording says the
        agent was NOT FOUND rather than reusing the is_ticket_phase phrasing.
        """
        ac_id = "TKT-500f-5-i-warning"
        generated = generate_dry_run(
            make_ac(assigned_agent=_UNKNOWN_AGENT, files_touched=[IMPL_PY]),
            ac_id,
        )
        warnings = generated.warnings

        self.assertTrue(
            warnings.strip(),
            "An assigned_agent that does not exist is almost always a typo in "
            "the AC. Substituting it silently hides the typo forever. No "
            "warning was recorded.",
        )
        self.assertIn(
            _UNKNOWN_AGENT,
            warnings,
            "The warning must name the original assigned_agent so the typo is "
            f"visible. Got: {warnings!r}",
        )
        self.assertIn(
            "python-coder",
            warnings,
            f"The warning must name the substitute actually used. Got: {warnings!r}",
        )
        self.assertIn(
            ac_id,
            warnings,
            f"The warning must name the AC id. Got: {warnings!r}",
        )
        self.assertIn(
            "not found",
            warnings.lower(),
            "The unknown-agent warning must state the agent was NOT FOUND in "
            "the registry. Reusing TKT-500f-5's 'is_ticket_phase: false' "
            "wording here sends the reader to a registry entry that does not "
            f"exist. Got: {warnings!r}",
        )

    def test_unknown_agent_generation_completes_without_unhandled_error(self):
        # covers: TKT-500f-5-i
        # angle: failure
        """A registry miss must degrade to a substitution, never to a crash.

        The natural implementation of the lookup — ``registry[agent_id]`` or
        ``next(e for e in entries if ...)`` — raises KeyError/StopIteration on
        exactly this input, which would turn one mistyped assigned_agent into a
        failed epic build for every leaf after it. Both the preview path and the
        real write path are exercised, and the write path is asserted to have
        produced a file on disk: an exit code of 0 from a run that wrote nothing
        would be a silent failure wearing a success code.
        """
        preview = generate_dry_run(
            make_ac(assigned_agent=_UNKNOWN_AGENT, files_touched=[IMPL_PY]),
            "TKT-500f-5-i-no-crash-preview",
        )
        self.assertIn(
            preview.exit_code,
            (0, None),
            "Previewing a ticket whose assigned_agent is absent from the "
            f"registry must not fail. Exit code: {preview.exit_code!r}",
        )
        self.assertTrue(
            preview.frontmatter,
            "Generation must still yield a ticket with parseable frontmatter, "
            f"not a truncated artifact. Got: {preview.text[:400]!r}",
        )

        written = generate_written(
            make_ac(assigned_agent=_UNKNOWN_AGENT, files_touched=[IMPL_PY]),
            "TKT-500f-5-i-no-crash-write",
        )
        self.assertIn(
            written.exit_code,
            (0, None),
            "Writing a ticket whose assigned_agent is absent from the registry "
            f"must not fail. Exit code: {written.exit_code!r}",
        )
        self.assertIsNotNone(
            written.written_path,
            "The registry miss must not stop the ticket being written — the "
            "criteria require generation to COMPLETE, and an exit code alone "
            "cannot tell a completed generation from an abandoned one.",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-5-i/test-writer]: Initial tests from the AC's four
  test_spec descriptors. setUpModule guards the fixture agent id against ever
  becoming real, because the entire file silently degrades to a duplicate of
  TKT-500f-5's suite the day someone registers "made-up-agent". The failure-angle
  test asserts a written artifact exists rather than only an exit code, since a
  zero exit from a run that produced no file is the shape of the silent failure
  the AC's "completes" clause is about.
====================================================================
"""
