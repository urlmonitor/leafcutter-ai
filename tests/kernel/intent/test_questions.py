"""
MODULE: tests.kernel.intent.test_questions
GOAL: Test the clarification questions: plain wording, concrete choices, no internal ids or
    jargon, the ".?" typo gone, a follow-up that differs from the first question, and answered
    questions read back as text.
BUSINESS CONTEXT: Live runs asked "Which approach or capability should handle: <goal>.?" with no
    choices and "routing had insufficient context" as the reason: unanswerable for a person
    (Rev 3 section 11.6). A clarification must name what the kernel can do and let the person
    pick or answer freely.
ARCHITECTURE: Pure builders; the question payload is validated by the real schema catalog.
"""

from __future__ import annotations

import unittest

from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.intent import ANSWER_KINDS
from kernel.intent.classify import ClarificationAnswer
from kernel.intent.questions import (
    answer_of,
    capability_question,
    intent_question,
    repeated_message,
    unclear_message,
)
from kernel.scheduler.guards import request_dedup_key
from tests.kernel.helpers import make_descriptor, narrow

JARGON = ("routing", "insufficient", "capability", "schema", "work item", "__", "decision_report",
          "evidence_bundle", "options.v1", "kernel.")


def _body(proposal) -> HumanQuestionRequestPayload:
    return HumanQuestionRequestPayload.model_validate(proposal.payload)


class TestIntentQuestion(unittest.TestCase):
    """What kind of answer: the supported kinds as choices, in user terms."""

    def test_the_answer_kinds_are_the_choices_and_free_text_stays_allowed(self) -> None:
        body = _body(intent_question("Implement a critical acceptance criterion."))
        self.assertEqual([c.id for c in body.choices], ["decision", "evidence", "ideas", "change"])
        self.assertTrue(set(c.id for c in body.choices) <= set(ANSWER_KINDS))
        self.assertTrue(body.free_text_allowed)

    def test_no_internal_ids_or_jargon_and_no_dot_question_mark(self) -> None:
        proposal = intent_question("Implement a critical acceptance criterion.")
        body = _body(proposal)
        texts = [body.question, body.why_research_cannot_settle,
                 *(c.label + " " + c.consequences for c in body.choices)]
        for text in texts:
            for word in JARGON:
                self.assertNotIn(word, text.lower(), f"{word!r} in {text!r}")
        self.assertNotIn(".?", body.question)
        self.assertIn("Implement a critical acceptance criterion.", body.question)

    def test_the_goal_is_shortened_in_the_question(self) -> None:
        body = _body(intent_question("word " * 200))
        self.assertLess(len(body.question), 600)

    def test_the_follow_up_quotes_the_answer_and_is_a_different_request(self) -> None:
        first = intent_question("Do the thing")
        follow = intent_question("Do the thing", ClarificationAnswer("hmm, the usual"))
        self.assertIn("hmm, the usual", _body(follow).question)
        self.assertNotEqual(request_dedup_key(first, None), request_dedup_key(follow, None))


class TestCapabilityQuestion(unittest.TestCase):
    """Which ability fits: the eligible capabilities in user terms."""

    def setUp(self) -> None:
        self.candidates = [
            make_descriptor(id="decision", binding="decision",
                            description="Decides a bounded question. It asks for evidence."),
            make_descriptor(id="research", binding="research",
                            description="Gathers inspectable evidence for a question.")]

    def test_choices_are_the_candidates_with_their_first_sentence(self) -> None:
        body = _body(capability_question("Pick one.", self.candidates))
        self.assertEqual([(c.id, c.label) for c in body.choices],
                         [("decision", "Decides a bounded question"),
                          ("research", "Gathers inspectable evidence for a question")])
        self.assertTrue(body.free_text_allowed)

    def test_the_question_names_no_capability_id_and_has_no_dot_question_mark(self) -> None:
        body = _body(capability_question("Pick one.", self.candidates))
        self.assertNotIn(".?", body.question)
        self.assertNotIn("decision", body.question.lower().replace("decides", ""))
        for word in JARGON:
            self.assertNotIn(word, (body.question + body.why_research_cannot_settle).lower())

    def test_without_candidates_the_question_asks_for_free_text(self) -> None:
        body = _body(capability_question("Pick one.", []))
        self.assertEqual(body.choices, [])
        self.assertTrue(body.free_text_allowed)

    def test_the_follow_up_differs_from_the_first_question(self) -> None:
        first = capability_question("Pick one.", self.candidates)
        follow = capability_question("Pick one.", self.candidates, ClarificationAnswer("maybe"))
        self.assertNotEqual(request_dedup_key(first, None), request_dedup_key(follow, None))


class TestAnswers(unittest.TestCase):
    """An answered question reads back as text the router can use."""

    def setUp(self) -> None:
        self.asked = intent_question("Do the thing").payload

    def test_a_chosen_option_reads_as_its_label_and_keeps_the_id(self) -> None:
        answer = answer_of(self.asked, {"choice_id": "evidence"})
        self.assertEqual((narrow(answer).choice_id, narrow(answer).text), ("evidence", "Find facts in this repository"))

    def test_free_text_wins(self) -> None:
        answer = answer_of(self.asked, {"free_text": "Decide which one"})
        self.assertEqual((narrow(answer).text, narrow(answer).choice_id), ("Decide which one", None))

    def test_unanswered_is_none(self) -> None:
        self.assertIsNone(answer_of(self.asked, None))
        self.assertIsNone(answer_of(self.asked, {}))


class TestMessages(unittest.TestCase):
    """Plain end messages with a rephrasing suggestion; no internal wording."""

    def test_unclear_and_repeated_messages_are_plain_and_suggest_a_rephrasing(self) -> None:
        for text in (unclear_message(), repeated_message()):
            self.assertTrue(text.startswith("unclear_request: "))
            self.assertTrue("rephras" in text.lower() or "more specific" in text.lower())
            self.assertIn("for example", text)
            self.assertNotIn("without new information", text)
            self.assertNotIn("no_progress", text)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: The jargon list pins the words the live questions leaked
#   ("routing", "insufficient", ids); it is checked against the question, the reason and the
#   choice texts. (#KernelBootstrapV0/INTENT)
# ====================================================================
