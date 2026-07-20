"""
MODULE: test_bo_2200b_3_i
GOAL: Verify AC BO-2200b-3-i — a short but genuine documentation file passes the
      documentation-verifier's placeholder detection, while heading-only stubs and
      token-filled stubs (e.g. {summary} or <placeholder>) correctly trigger a blocker.

The AC requires that placeholder detection keys on placeholder SIGNATURES
(heading-only, residual tokens, TODO/TBD), NOT on length/brevity.
A legitimately short doc with real prose must pass; brevity alone is not a stub.

These tests pin three properties that must be explicit in the
documentation-verifier template (templates/agents/documentation-verifier.md):

  1. The template explicitly states that brevity/being-short is NOT a rejection
     criterion (signature-based detection, not length-based) — checks for the
     word "brevity" or the phrase "short but genuine" anywhere in the template.
  2. The template cites `{summary}` as a canonical example of a residual
     template token that is a placeholder signature.
  3. The template's Step 6 section explicitly uses the word "brevity" or the
     phrase "short but genuine" within the placeholder-detection step itself,
     so the implementing LLM has no ambiguity about the edge case.

All three tests will be RED until the llm-expert refines the template wording
per AC BO-2200b-3-i. Test 2 additionally checks for `<placeholder>` as an
example in the template.

TICKET: tickets/00_inbox/epics/EPIC-DocumentationCoverageGuarantee/12_TICKET-20260715-BO-2200b-3-i.md
COVERS: BO-2200b-3-i
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC_VERIFIER_TEMPLATE = (
    _REPO_ROOT / "templates" / "agents" / "documentation-verifier.md"
)


def _load_template() -> str:
    """Load the documentation-verifier.md template text."""
    assert _DOC_VERIFIER_TEMPLATE.exists(), (
        f"documentation-verifier.md not found at {_DOC_VERIFIER_TEMPLATE}. "
        "Has templates/agents/documentation-verifier.md been created?"
    )
    return _DOC_VERIFIER_TEMPLATE.read_text(encoding="utf-8")


class TestAC1TemplateBrevityExplicit(unittest.TestCase):
    """AC BO-2200b-3-i: template must explicitly state brevity is not a rejection criterion."""

    def test_ac1_template_explicitly_states_brevity_is_not_a_placeholder_signal(self):
        # covers: BO-2200b-3-i
        """AC-1: The documentation-verifier template must contain the word 'brevity'
        or the phrase 'short but genuine' in the context of placeholder detection,
        explicitly stating that a legitimately short doc must pass.

        The AC implementation note reads verbatim:
          'A legitimately short doc must pass; brevity is not a stub.
           Avoid instructing any naive minimum-character rule.'

        The word 'brevity' specifically (not 'brief', which also appears as
        'Agent Contracts brief' in the template) is the marker of the explicit
        signature-vs-length guidance the AC requires.

        Until llm-expert adds 'brevity' or 'short but genuine' to the template,
        this test fails with AssertionError.
        """
        template = _load_template()
        # "brevity" is the AC implementation note's exact word; it does NOT appear
        # in the current template (the word "brief" appears only as a noun meaning
        # "Agent Contracts brief" — not as an adjective about doc length).
        # "short but genuine" is the AC title phrase; also not currently present.
        brevity_pattern = re.compile(
            r"\brevity\b|short\s+but\s+genuine",
            re.IGNORECASE,
        )
        match = brevity_pattern.search(template)
        self.assertIsNotNone(
            match,
            "documentation-verifier.md does not contain 'brevity' or 'short but genuine'. "
            "The AC BO-2200b-3-i implementation note explicitly requires this wording so "
            "the implementing LLM agent knows that being short is NOT a rejection trigger. "
            "llm-expert must add an explicit statement — e.g. 'brevity is not a stub; a "
            "short but genuine doc with at least one real content line passes Step 6d' — "
            "in the template body (e.g. in Step 6d or an introductory note before Step 6).",
        )


class TestAC1TemplateExampleTokensExplicit(unittest.TestCase):
    """AC BO-2200b-3-i: template must cite canonical placeholder token examples."""

    def test_ac1_template_cites_summary_as_residual_token_example(self):
        # covers: BO-2200b-3-i
        """AC-1: The documentation-verifier template must cite `{summary}` (or a
        syntactically equivalent `{...}` token) as a canonical example of a residual
        template token in the context of Step 6 placeholder detection.

        The AC criteria read:
          'contains only residual template tokens such as `{summary}` or `<placeholder>`'

        The current template Step 6c describes the grep pattern `{[^}]*}` but does not
        cite `{summary}` as a named example that makes the AC's intention explicit.

        Until llm-expert adds `{summary}` as an illustrative example in the template
        (e.g. 'residual template tokens such as `{summary}` or `<placeholder>`'), this
        test fails with AssertionError.
        """
        template = _load_template()
        # The AC explicitly names "{summary}" as a canonical example.
        # The template must reflect this example so the implementing LLM has the
        # same concrete case to reason from.
        self.assertIn(
            "{summary}",
            template,
            "documentation-verifier.md does not cite '{summary}' as a canonical example "
            "of a residual template token. The AC BO-2200b-3-i criteria name it explicitly "
            "('such as `{summary}` or `<placeholder>`'). llm-expert must add this example "
            "in the template — e.g. in Step 6c or a preamble to Step 6 — so the agent "
            "can detect this class of placeholder without ambiguity.",
        )

    def test_ac1_template_cites_angle_bracket_placeholder_as_example(self):
        # covers: BO-2200b-3-i
        """AC-1: The documentation-verifier template must cite `<placeholder>` as a
        canonical example of residual placeholder content.

        The AC criteria read:
          'contains only residual template tokens such as `{summary}` or `<placeholder>`'

        The current template references the helper's `\\bPLACEHOLDER\\b` pattern (via Step
        6a) but does not cite `<placeholder>` as a named example in the Step 6 guidance.
        Without this example, the implementing LLM may not recognise angle-bracket style
        placeholders as in scope.

        Until llm-expert adds `<placeholder>` as an illustrative example in the template,
        this test fails with AssertionError.
        """
        template = _load_template()
        self.assertIn(
            "<placeholder>",
            template,
            "documentation-verifier.md does not cite '<placeholder>' as a canonical example "
            "of residual placeholder content. The AC BO-2200b-3-i criteria name it explicitly. "
            "llm-expert must add this example to the template (e.g. in the Step 6a guidance "
            "or a preamble note before Step 6) so the agent recognises angle-bracket style "
            "placeholders as placeholder content.",
        )


class TestAC1TemplateStep6ExplicitPositiveCase(unittest.TestCase):
    """AC BO-2200b-3-i: template Step 6 must contain an explicit positive example
    or statement showing that a SHORT genuine doc PASSES placeholder detection.

    The AC title is 'A short but genuine doc passes'. The template must make this
    explicit so the LLM executing the check doesn't apply implicit length heuristics.
    """

    def test_ac1_template_step6_positive_case_short_doc_passes_explicitly(self):
        # covers: BO-2200b-3-i
        """AC-1: The documentation-verifier template Step 6 (the placeholder-detection
        section) must contain a positive statement about the passing case for a short
        genuine doc, using the word 'brevity' or the phrase 'short but genuine'.

        The AC says:
          'when a required doc's changed content is short but genuine ... the verifier
           does NOT reject it for being brief, and returns status: ok.'

        This requires the template to EXPLICITLY say the passing case. The current
        template's Step 6d says 'A file passes 6d if it has at least one non-blank,
        non-heading line of real content' — this is correct logic but does NOT mention
        'brevity' or 'short but genuine', leaving the LLM agent to potentially infer
        a length-based heuristic from the spirit of the check.

        Until llm-expert adds explicit wording like 'Brevity is not a stub' or 'A short
        but genuine file passes' in Step 6 or its preamble, this test fails.

        NOTE: This test is intentionally stricter than the overall template search in
        TestAC1TemplateBrevityExplicit — it requires the brevity statement in the Step 6
        section, not just anywhere in the file (e.g. not just in adopter_notes).
        """
        template = _load_template()

        # Find the Step 6 section — it begins with '### Step 6' and ends at the next
        # '### Step' heading (or '## ' section heading).
        step6_match = re.search(
            r"###\s+Step\s+6\b.*?(?=###\s+Step\s+7\b|##\s+\w|$)",
            template,
            re.DOTALL | re.IGNORECASE,
        )
        self.assertIsNotNone(
            step6_match,
            "Could not locate '### Step 6' section in documentation-verifier.md. "
            "The template must contain a Step 6 placeholder detection section.",
        )

        step6_text = step6_match.group(0)
        brevity_in_step6 = re.search(
            r"\brevity\b|short\s+but\s+genuine",
            step6_text,
            re.IGNORECASE,
        )
        self.assertIsNotNone(
            brevity_in_step6,
            "documentation-verifier.md Step 6 does not explicitly say 'brevity' or "
            "'short but genuine' in the placeholder detection instructions. "
            "The AC BO-2200b-3-i requires the implementing LLM to see this explicitly "
            "in the detection section so it does not apply a naive length heuristic. "
            "llm-expert must add wording such as: 'Brevity is not a stub — a short but "
            "genuine file that passes all four sub-checks above returns status: ok.' "
            "Searched Step 6 text (first 500 chars): "
            f"{step6_text[:500]!r}",
        )


if __name__ == "__main__":
    unittest.main()
