"""
MODULE: tests.kernel.intent.test_report_text
GOAL: Test the plain-language report wording: why a blocked or partial run stopped, what the
    kernel can do, a rephrasing suggestion, and the readable evidence and idea sections.
BUSINESS CONTEXT: A bare "blocked" told a user nothing; ideas must be presented as proposals and
    never as decisions (Rev 3 section 10.4).
ARCHITECTURE: Pure template functions over limitation strings and output payload dicts.
"""

from __future__ import annotations

import unittest

from kernel.contracts import schema_ids
from kernel.intent.report_text import (
    GUARDS,
    can_do_hint,
    guard_hit,
    has_plain_reason,
    output_sections,
    stop_explanation,
)


class TestStopExplanation(unittest.TestCase):
    """Blocked and partial runs say why and what to do."""

    def test_a_blocked_run_says_what_the_kernel_can_do_and_how_to_rephrase(self) -> None:
        text = "\n".join(stop_explanation("blocked", ["no_capability: nothing serves this"]))
        self.assertIn("Why the run stopped", text)
        self.assertIn("decide between options", text)
        self.assertIn("find evidence in this repository", text)
        self.assertIn("generate ideas", text)
        self.assertIn("Try rephrasing, for example", text)

    def test_a_decline_reason_is_quoted_without_its_code(self) -> None:
        text = "\n".join(stop_explanation(
            "blocked", ["out_of_scope_write: The kernel is read-only; nothing is edited."]))
        self.assertIn("- The kernel is read-only; nothing is edited.", text)
        self.assertNotIn("out_of_scope_write", text)

    def test_finished_runs_get_no_explanation(self) -> None:
        self.assertEqual(stop_explanation("completed", []), [])
        self.assertEqual(stop_explanation("failed", ["boom: x"]), [])

    def test_the_hint_line_has_the_can_do_code_and_is_skipped_after_a_plain_reason(self) -> None:
        self.assertTrue(can_do_hint().startswith("can_do: "))
        self.assertIn("generate ideas", can_do_hint())
        self.assertTrue(has_plain_reason(["out_of_domain: not about software"]))
        self.assertTrue(has_plain_reason(["unclear_request: rephrase"]))
        self.assertFalse(has_plain_reason(["no_capability: nothing serves this"]))


class TestGuardStops(unittest.TestCase):
    """Round 6 told a budget stop to "try rephrasing"; a guard stop now says what was hit."""

    BUDGET = ["jev call budget exhausted", "budget_exhausted: jev call budget exhausted"]

    def test_a_budget_stop_names_the_budget_the_config_key_and_the_remedies(self) -> None:
        text = "\n".join(stop_explanation("blocked", self.BUDGET))
        self.assertIn("The run stopped because the Jev call budget was reached", text)
        self.assertIn("`limits.max_jev_calls`", text)
        for remedy in ("raise `limits.max_jev_calls`", "narrow the question",
                       "decide from the ranked options"):
            self.assertIn(remedy, text)
        self.assertNotIn("rephras", text.lower())
        self.assertNotIn("What the kernel can do", text)

    def test_every_guard_names_its_own_config_key(self) -> None:
        for guard, (_, key) in GUARDS.items():
            with self.subTest(guard=guard):
                self.assertIn(f"`{key}`", "\n".join(stop_explanation(
                    "partial", [f"unresolved_at_{guard}: some goal"])))

    def test_the_guard_is_found_in_limitations_codes_reasons_and_diagnostics(self) -> None:
        self.assertEqual(guard_hit(self.BUDGET), "budget_exhausted")
        self.assertEqual(guard_hit(["unavailable: budget_exhausted"]), "budget_exhausted")
        self.assertEqual(guard_hit(["unresolved_at_max_host_operations: goal"]),
                         "max_host_operations")
        self.assertEqual(guard_hit([], ["guard: max_active_seconds"]), "max_active_seconds")
        self.assertIsNone(guard_hit(["no_capability: nothing serves this"], ["guard: unknown"]))

    def test_a_guard_stop_needs_no_rephrasing_hint(self) -> None:
        self.assertTrue(has_plain_reason(self.BUDGET))
        self.assertTrue(has_plain_reason([], ["guard: no_progress"]))
        self.assertFalse(has_plain_reason(["no_capability: nothing serves this"]))

    def test_other_blocked_runs_still_suggest_rephrasing(self) -> None:
        text = "\n".join(stop_explanation("blocked", ["no_capability: nothing serves this"]))
        self.assertIn("Try rephrasing", text)


class TestOutputSections(unittest.TestCase):
    """Evidence and idea outputs are readable; ideas are proposals."""

    def test_ideas_are_presented_as_proposals_not_decisions(self) -> None:
        payload = {"options": [{"id": "o1", "title": "Add span links", "description": "Link spans",
                                "proposal_status": "proposed"}],
                   "proposed_criteria": [{"id": "c1", "question": "Is it cheap?"}]}
        text = "\n".join(output_sections(schema_ids.OPTIONS, payload))
        self.assertIn("## Ideas (proposals, not decisions)", text)
        self.assertIn("**Add span links** (proposed): Link spans", text)
        self.assertIn("None of them is approved or chosen", text)
        self.assertIn("Is it cheap?", text)

    def test_an_evidence_bundle_lists_findings_and_sources(self) -> None:
        payload = {"findings": [{"claim": "Tests live in tests/kernel"}],
                   "evidence": [{"source": {"locator": "docs/testing/README.md#L1-L9"}},
                                {"source": {"locator": "docs/testing/README.md#L1-L9"}}]}
        text = "\n".join(output_sections(schema_ids.EVIDENCE_BUNDLE, payload))
        self.assertIn("## Findings", text)
        self.assertIn("- Tests live in tests/kernel", text)
        self.assertEqual(text.count("docs/testing/README.md#L1-L9"), 1)

    def test_an_empty_bundle_says_no_findings_and_other_schemas_add_nothing(self) -> None:
        text = "\n".join(output_sections(schema_ids.EVIDENCE_BUNDLE, {"evidence": []}))
        self.assertIn("No findings", text)
        self.assertEqual(output_sections(schema_ids.HUMAN_ANSWER, {"choice_id": "x"}), [])
        self.assertEqual(output_sections(schema_ids.OPTIONS, None), [])

    def test_a_decision_report_now_has_a_decision_section(self) -> None:
        """The old expectation (nothing for a decision report) was stale: round 8 defect c."""
        text = "\n".join(output_sections(schema_ids.DECISION_REPORT, {"status": "resolved"}))
        self.assertIn("## Decision", text)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Guard and budget stops name what was hit and the config key that
#   raises it instead of suggesting a rephrasing. (#KernelV01/E)
# - 2026-10-01 22:00 [python-coder]: The report keeps the JSON output block and adds these
#   readable sections before it; nothing here is model-written. (#KernelBootstrapV0/INTENT)
# ====================================================================
