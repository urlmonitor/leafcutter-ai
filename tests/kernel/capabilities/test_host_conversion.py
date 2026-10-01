"""
MODULE: tests.kernel.capabilities.test_host_conversion
GOAL: Test how each host operation converts a schema-valid host output into a CapabilityResult:
    options and criteria stay proposals, findings become host-reported inferences, research
    evidence is host-reported with kernel hashes and no fabricated verification, and a formulated
    question keeps the kernel choices and is still turned into a human-only question by Leafcutter.
BUSINESS CONTEXT: Whatever the host claims is a claim, not a fact or an approval (Rev 3 sections
    10.4, 11.5 and 11.6); these tests state each claim as raw JSON and assert what the kernel kept.
ARCHITECTURE: Pure unit tests over real contract models and the real operations; hosts are raw
    JSON so a test can send exactly the lies the models would refuse to build.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from kernel.contracts import FindingKind, ResultStatus, Verification, schema_ids
from kernel.contracts.enums import NeedStatus, SemanticType, SourceKind
from kernel.interaction.packets import build_human_question
from tests.kernel.capabilities.host_support import (
    FAKE_HASH,
    OPTIONS_REQUEST,
    QUESTION_REQUEST,
    RESEARCH_REQUEST,
    SYNTHESIS_REQUEST,
    convert,
    criterion,
    evidence_json,
    finding_json,
    option,
)


class TestOptionsConversion(unittest.TestCase):
    """Options and criteria are always proposals."""

    def test_options_and_criteria_are_proposed_and_attributed_to_the_host_capability(self) -> None:
        result = convert("host.generate_options", OPTIONS_REQUEST,
                         {"options": [option("opt-a"), option("opt-b")],
                          "proposed_criteria": [criterion("crit-a")]})
        self.assertIs(result.status, ResultStatus.COMPLETED)
        self.assertEqual(result.output_schema_id, schema_ids.OPTIONS)
        for item in (*result.output_payload["options"], *result.output_payload["proposed_criteria"]):
            self.assertEqual((item["proposal_status"], item["approval_status"],
                              item["approved_by"], item["proposed_by"]),
                             ("proposed", "proposed", None, "host.generate_options"))
        self.assertTrue(any("proposals until a human approves" in x for x in result.limitations))

    def test_a_pre_approved_option_never_becomes_a_result(self) -> None:
        approved = option("opt-a", proposal_status="approved", approval_status="approved",
                          approved_by="host-1")
        result = convert("host.generate_options", OPTIONS_REQUEST, {"options": [approved]})
        self.assertIs(result.status, ResultStatus.FAILED)
        self.assertEqual(result.error.code, "host_output_invalid")
        self.assertIsNone(result.output_payload)

    def test_surplus_options_unrequested_criteria_and_weights_are_dropped_with_limitations(
            self) -> None:
        request = {**OPTIONS_REQUEST, "max_options": 1, "propose_criteria": False}
        result = convert("host.generate_options", request,
                         {"options": [option("opt-a"), option("opt-b")],
                          "proposed_criteria": [criterion(weight_rule="double this one")]})
        self.assertEqual([o["id"] for o in result.output_payload["options"]], ["opt-a"])
        self.assertEqual(result.output_payload["proposed_criteria"], [])
        text = " ".join(result.limitations)
        self.assertIn("beyond the requested maximum of 1", text)
        self.assertIn("did not ask for criteria", text)

    def test_weights_the_host_sets_on_requested_criteria_are_removed(self) -> None:
        result = convert("host.generate_options", OPTIONS_REQUEST, {
            "options": [], "proposed_criteria": [criterion(weight_rule="x2", decision_basis="me")]})
        (kept,) = result.output_payload["proposed_criteria"]
        self.assertEqual((kept["weight_rule"], kept["decision_basis"]), (None, None))
        self.assertIn("weight rules", " ".join(result.limitations))

    def test_an_option_reusing_an_existing_id_is_dropped(self) -> None:
        request = {**OPTIONS_REQUEST, "existing_option_ids": ["opt-a"]}
        result = convert("host.generate_options", request,
                         {"options": [option("opt-a"), option("opt-b")]})
        self.assertEqual([o["id"] for o in result.output_payload["options"]], ["opt-b"])


class TestSynthesisConversion(unittest.TestCase):
    """Findings are host-reported inferences."""

    KNOWN = {"ev-00000000000000aa"}

    def findings(self, known: set[str] | None = None, **request: object):
        body = {"findings": [
            finding_json(supporting_evidence_ids=["ev-00000000000000aa"]),
            finding_json("Another claim", kind="human_input",
                         supporting_evidence_ids=["ev-00000000000000bb"])],
            "agreements": ["both agree"], "disagreements": ["they differ on cost"]}
        return convert("host.synthesize", {**SYNTHESIS_REQUEST, **request}, body,
                       known=self.KNOWN if known is None else known)

    def test_findings_are_inferences_with_a_host_reported_limitation(self) -> None:
        result = self.findings(limits={"max_findings": 5})
        self.assertEqual(len(result.findings), 2)
        for finding in result.findings:
            self.assertIs(finding.kind, FindingKind.INFERENCE)
            self.assertEqual(finding.producer, "host.synthesize")
            self.assertTrue(any("not verified by the kernel" in x for x in finding.limitations))
        self.assertEqual(result.output_payload["disagreements"], ["they differ on cost"])
        self.assertIn("inferences by the host", " ".join(result.limitations))

    def test_ids_are_kernel_derived_and_repeatable(self) -> None:
        first, second = self.findings(limits={"max_findings": 5}), self.findings(
            limits={"max_findings": 5})
        self.assertEqual([f.id for f in first.findings][0].split("-")[0], "find")
        self.assertEqual({f.claim for f in first.findings}, {f.claim for f in second.findings})
        self.assertEqual(len({f.id for f in first.findings}), 2)

    def test_a_citation_of_unknown_evidence_is_dropped_with_a_limitation(self) -> None:
        result = self.findings(limits={"max_findings": 5})
        self.assertEqual(result.findings[0].supporting_evidence_ids, ["ev-00000000000000aa"])
        self.assertEqual(result.findings[1].supporting_evidence_ids, [])
        self.assertIn("ev-00000000000000bb", " ".join(result.limitations))

    def test_findings_beyond_the_requested_maximum_are_dropped(self) -> None:
        result = self.findings(limits={"max_findings": 1})
        self.assertEqual(len(result.findings), 1)
        self.assertIn("beyond the requested maximum of 1", " ".join(result.limitations))


class TestResearchConversion(unittest.TestCase):
    """A research bundle is host-reported, unverified and carries no fabricated hash."""

    LOCATOR = "docs/cache.md#L1-L3"

    def bundle(self, *items: dict, **extra: object) -> dict:
        return {"evidence": list(items), "evidence_ids": [i["id"] for i in items], **extra}

    def test_evidence_is_host_reported_with_its_locator_and_a_kernel_hash(self) -> None:
        item = evidence_json(self.LOCATOR, "The cache lives in sqlite.", digest=FAKE_HASH)
        result = convert("host.research", RESEARCH_REQUEST, self.bundle(item))
        (evidence,) = result.evidence
        self.assertIs(evidence.verification, Verification.HOST_REPORTED)
        self.assertIs(evidence.source.kind, SourceKind.HOST_RESEARCH)
        self.assertEqual(evidence.source.locator, self.LOCATOR)
        self.assertIsNone(evidence.source.source_version)
        self.assertNotEqual(evidence.content_hash, FAKE_HASH)
        self.assertEqual(evidence.excerpt, "The cache lives in sqlite.")
        self.assertEqual(evidence.provenance.producer, "host.research")
        self.assertTrue(any("not verified" in x for x in evidence.limitations))
        self.assertEqual(result.output_payload["evidence_ids"], [evidence.id])
        self.assertIn("replaced by the kernel's own", " ".join(result.limitations))

    def test_the_same_answer_converts_to_the_same_evidence(self) -> None:
        item = evidence_json(self.LOCATOR, "The cache lives in sqlite.")
        first = convert("host.research", RESEARCH_REQUEST, self.bundle(item))
        second = convert("host.research", RESEARCH_REQUEST, self.bundle(item))
        self.assertEqual([e.id for e in first.evidence], [e.id for e in second.evidence])

    def test_a_host_cannot_claim_to_be_human_input(self) -> None:
        item = evidence_json(self.LOCATOR, "The user said yes.", semantic_type="human_input")
        (evidence,) = convert("host.research", RESEARCH_REQUEST, self.bundle(item)).evidence
        self.assertIsNot(evidence.semantic_type, SemanticType.HUMAN_INPUT)

    def test_coverage_is_clamped_to_the_asked_need_and_the_evidence_found(self) -> None:
        none = convert("host.research", RESEARCH_REQUEST, {
            "evidence": [], "coverage": {"need-1": "satisfied", "other": "satisfied"}})
        self.assertEqual(none.output_payload["coverage"], {"need-1": NeedStatus.UNAVAILABLE.value})
        self.assertIn("not asked for", " ".join(none.limitations))
        found = convert("host.research", RESEARCH_REQUEST, self.bundle(
            evidence_json(self.LOCATOR, "x"), coverage={"need-1": "open"}))
        self.assertEqual(found.output_payload["coverage"], {"need-1": NeedStatus.PARTIAL.value})

    def test_a_reference_to_unknown_evidence_is_dropped_and_known_evidence_kept(self) -> None:
        bundle = {"evidence": [], "evidence_ids": ["ev-00000000000000aa", "ev-00000000000000bb"]}
        result = convert("host.research", RESEARCH_REQUEST, bundle, known={"ev-00000000000000aa"})
        self.assertEqual(result.output_payload["evidence_ids"], ["ev-00000000000000aa"])

    def test_inline_findings_become_host_reported_inferences_citing_the_new_ids(self) -> None:
        item = evidence_json(self.LOCATOR, "The cache lives in sqlite.")
        bundle = self.bundle(item, findings=[finding_json(supporting_evidence_ids=[item["id"]])])
        result = convert("host.research", RESEARCH_REQUEST, bundle)
        (finding,) = result.findings
        self.assertIs(finding.kind, FindingKind.INFERENCE)
        self.assertEqual(finding.supporting_evidence_ids, [result.evidence[0].id])
        self.assertEqual(result.output_payload["finding_ids"], [finding.id])

    def test_new_evidence_of_the_submission_is_kept_beside_the_bundle(self) -> None:
        extra = {"title": "Note", "excerpt": "Also seen in the ADR.", "locator": "docs/adr.md#L1"}
        result = convert("host.research", RESEARCH_REQUEST, {"evidence": []},
                         new_evidence=[extra])
        self.assertEqual([e.excerpt for e in result.evidence], ["Also seen in the ADR."])
        self.assertIs(result.evidence[0].verification, Verification.HOST_REPORTED)


class TestQuestionConversion(unittest.TestCase):
    """The host words the question; the kernel still creates the interaction."""

    def reworded(self, **over: object) -> dict:
        return {"question": "Where should the cache be stored?", "free_text_allowed": False,
                "choices": [{"id": "sqlite", "label": "SQLite file", "consequences": "One file."},
                            {"id": "files", "label": "Plain files"}], **over}

    def test_the_wording_is_adopted_and_the_choices_keep_their_ids(self) -> None:
        result = convert("host.formulate_question", QUESTION_REQUEST, self.reworded())
        body = result.output_payload
        self.assertEqual(body["question"], "Where should the cache be stored?")
        self.assertEqual([c["id"] for c in body["choices"]], ["sqlite", "files"])
        self.assertEqual(body["choices"][0]["label"], "SQLite file")

    def test_added_or_removed_choices_and_changed_flags_are_reverted(self) -> None:
        offered = self.reworded(free_text_allowed=True, choices=[
            {"id": "sqlite", "label": "SQLite"}, {"id": "approve-all", "label": "Approve all"}])
        result = convert("host.formulate_question", QUESTION_REQUEST, offered)
        body = result.output_payload
        self.assertEqual([c["id"] for c in body["choices"]], ["sqlite", "files"])
        self.assertFalse(body["free_text_allowed"])
        self.assertIn("added, removed or renamed choices", " ".join(result.limitations))
        self.assertIn("free_text_allowed", " ".join(result.limitations))

    def test_the_kernel_turns_the_result_into_a_human_only_question(self) -> None:
        result = convert("host.formulate_question", QUESTION_REQUEST, self.reworded())
        request = SimpleNamespace(
            payload_schema=schema_ids.HUMAN_QUESTION_REQUEST, payload=result.output_payload,
            question=None, goal=None, context_refs=[])
        state = {"requests": {"req": request}, "evidence": {}}
        item = SimpleNamespace(id="work-0000000000000001", request_id="req")
        question = build_human_question(state, item, 3, datetime.now(timezone.utc))
        self.assertEqual(question.required_actor_kind, "human")
        self.assertEqual(question.question, "Where should the cache be stored?")
        self.assertEqual([c.id for c in question.choices], ["sqlite", "files"])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 12:10 [python-coder]: Hosts are simulated as raw JSON (including lying hashes and
#   statuses) rather than through the contract models, because the models would refuse to build
#   exactly the claims a host might send. (#KernelBootstrapV0/P8)
# ====================================================================
