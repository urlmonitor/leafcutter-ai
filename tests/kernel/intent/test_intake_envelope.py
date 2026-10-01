"""
MODULE: tests.kernel.intent.test_intake_envelope
GOAL: Prove through the real service the envelope and report side of the intake-intent change:
    token totals (known counts summed, unknown ones null), a plain explanation for a blocked run,
    gap records with exclusion reasons and a readable title, and the decision capability's routing
    description.
BUSINESS CONTEXT: Live envelopes reported null tokens although every Jev call carried usage, a bare
    "blocked" with no hint of what the kernel can do, and a gap titled with a sorted bag of words
    that listed every capability unranked (Rev 3 sections 14 and 16).
ARCHITECTURE: IntentCase over the production registry and file stores; the gap draft is read from
    the run root, the report from the path the envelope names.
"""

from __future__ import annotations

import unittest

from kernel.contracts import GapType, RunStatus, Usage, schema_ids
from kernel.persistence.gap_store import is_build_opportunity
from tests.kernel.intent.support import SURE, IntentCase

WEATHER = "How is the weather today?"
UNSERVED = "Summarise the open questions of the design"


class TestTokenTotals(IntentCase):
    """The envelope sums the token counts the provider reported."""

    async def test_known_counts_are_summed_into_the_envelope(self) -> None:
        self.scripted(Usage(provider="jev", model_id="m", input_tokens=100, output_tokens=10,
                            calls=1))
        self.intents = [("out_of_domain", *SURE)]
        envelope = await self.service().start_run(self.goal_task(WEATHER))
        summary = envelope.usage_summary
        self.assertEqual((summary.jev_calls, summary.input_tokens, summary.output_tokens),
                         (1, 100, 10))
        (entry,) = summary.usage
        self.assertEqual((entry.provider, entry.calls, entry.input_tokens, entry.output_tokens),
                         ("jev", 1, 100, 10))

    async def test_counts_add_up_over_several_calls_and_survive_a_status_read(self) -> None:
        self.scripted(Usage(provider="jev", model_id="m", input_tokens=100, output_tokens=10,
                            calls=1))
        self.intents = [("evidence", *SURE)]
        envelope = await self.service().start_run(self.goal_task("Where is the capability shape?"))
        self.assertGreater(envelope.usage_summary.jev_calls, 1)
        self.assertEqual(envelope.usage_summary.input_tokens,
                         100 * envelope.usage_summary.jev_calls)
        again = await self.service().get_run(envelope.run_id)
        self.assertEqual(again.usage_summary.input_tokens, envelope.usage_summary.input_tokens)

    async def test_unknown_counts_stay_null_not_zero(self) -> None:
        self.intents = [("out_of_domain", *SURE)]  # the default scripted usage reports no tokens
        envelope = await self.service().start_run(self.goal_task(WEATHER))
        summary = envelope.usage_summary
        self.assertEqual(summary.jev_calls, 1)
        self.assertIsNone(summary.input_tokens)
        self.assertIsNone(summary.output_tokens)
        self.assertIsNone(summary.usage[0].input_tokens)


class TestBlockedRunSaysWhatItCanDo(IntentCase):
    """A run no capability can serve is blocked with a plain explanation, not a bare status."""

    async def blocked(self):
        task = self.goal_task(UNSERVED, requested_output_schema=schema_ids.FINDINGS)
        return await self.service().start_run(task)

    async def test_the_envelope_names_what_the_kernel_can_do_and_how_to_rephrase(self) -> None:
        envelope = await self.blocked()
        self.assertEqual(envelope.status, RunStatus.BLOCKED)
        text = " | ".join(envelope.limitations)
        self.assertIn("decide between options", text)
        self.assertIn("find evidence in this repository", text)
        self.assertIn("generate ideas", text)
        self.assertIn("Try rephrasing", text)

    async def test_the_report_explains_why_the_run_stopped(self) -> None:
        envelope = await self.blocked()
        report = self.report_text(envelope)
        self.assertIn("## Why the run stopped", report)
        self.assertIn("What the kernel can do:", report)
        self.assertIn("Try rephrasing, for example", report)

    async def test_the_gap_lists_the_closest_capabilities_with_exclusion_reasons(self) -> None:
        envelope = await self.blocked()
        (gap,) = envelope.gaps
        self.assertEqual(gap.gap_type, GapType.UNSUPPORTED)
        self.assertTrue(is_build_opportunity(gap))
        self.assertLessEqual(len(gap.candidates_considered), 5)
        self.assertEqual(set(gap.candidates_considered), set(gap.candidate_exclusions))
        self.assertEqual(gap.candidate_exclusions["research"], "output_schema_mismatch")
        ranked = gap.candidates_considered
        self.assertLess(ranked.index("research"), ranked.index("retrieve.repository")
                        if "retrieve.repository" in ranked else len(ranked))

    async def test_the_gap_title_reads_like_the_goal_while_the_key_stays_normalised(self) -> None:
        envelope = await self.blocked()
        (gap,) = envelope.gaps
        self.assertEqual(gap.need_title, UNSERVED)
        self.assertNotEqual(gap.normalized_need, UNSERVED)  # the dedup identity is a token bag
        self.assertIn("summarise", gap.normalized_need)
        draft = (self.run_root / "gaps" / gap.proposal.draft_ref).read_text(encoding="utf-8")
        self.assertIn(f"# Capability gap draft: {UNSERVED}", draft)
        self.assertIn("- research (excluded: output_schema_mismatch)", draft)
        self.assertEqual(gap.proposal.title, f"Capability for: {UNSERVED}")


class TestDecisionDescription(IntentCase):
    """Jev routes by the literal description: it must cover generating options first."""

    def test_the_decision_capability_says_it_also_decides_what_to_do_and_generates_options(
            self) -> None:
        text = self.snapshot.get("decision").description
        self.assertIn("which option to pick", text)
        self.assertIn("what to do", text)
        self.assertIn("not known yet", text)
        self.assertIn("generated", text)
        self.assertNotIn("between known options", text)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: The blocked-run tests ask for an output nothing produces
#   (findings from a goal) so the gap is a true `unsupported` one with exclusion reasons.
#   (#KernelBootstrapV0/INTENT)
# ====================================================================
