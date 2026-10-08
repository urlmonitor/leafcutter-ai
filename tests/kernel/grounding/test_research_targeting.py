"""
MODULE: tests.kernel.grounding.test_research_targeting
GOAL: Behavioural tests of targeted research: option-cited paths become explicit locators on the
    retrieval children, queries are goal-first with criteria and option text, the gaps a synthesis
    names and the claims of human-added options become evidence needs with their own queries, and
    the decision hands both to the next research round.
BUSINESS CONTEXT: Live run run-5d246775f5e54f11 never retrieved `kernel/contracts/decision.py`
    although an option cited it and a synthesis named it as missing, and every round searched the
    goal text again (trace review findings 4 and 5; wave 2 item 1).
ARCHITECTURE: Research is run through ResearchExecutor with mandated needs (no planning Jev
    call); the requests it emits are read back as retrieval_request.v1 payloads. The decision
    side runs DecisionExecutor with the design-ending rig and reads the research request it emits.
"""

from __future__ import annotations

from typing import Any

from kernel.config import KernelConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import (
    EvidenceCategory,
    NeedStatus,
    Priority,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import (
    OptionContext,
    ResearchRequestPayload,
    RetrievalRequestPayload,
)
from tests.kernel.capabilities.support import child, evidence_item, invocation, resume
from tests.kernel.capabilities.test_design_ending import FLAT, DesignCase
from tests.kernel.capabilities.test_research_graph import QUESTION, ResearchCase, _bundle

CATS = EvidenceCategory
CITED_EVIDENCE = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
OPTIONS = [
    OptionContext(option_id="A", title="Kernel-contract YAML per decision",
                  description="One YAML file per decision validated by kernel/contracts/decision.py",
                  cited_refs=[CITED_EVIDENCE.id, "kernel/contracts/decision.py",
                              "docs/concepts/colony.md#L10-L20", "kernel/config.py::ResearchConfig",
                              "ParseRecord", "parse_record"]),
    OptionContext(option_id="B", title="Reuse the AC store", cited_refs=["tests/README.md"])]
NEEDS = [EvidenceNeed(id="need.prior_decisions", category=CATS.PRIOR_DECISIONS,
                      question="Which earlier decisions bear on: " + QUESTION),
         EvidenceNeed(id="need.existing_patterns", category=CATS.EXISTING_PATTERNS,
                      question="How do existing modules handle: " + QUESTION)]


def _config(research: dict | None = None, retrieval: dict | None = None) -> KernelConfig:
    """Return the default config with research and retrieval overrides."""
    base = load_kernel_config()
    return base.model_copy(update={
        "research": base.research.model_copy(update=research or {}),
        "retrieval": base.retrieval.model_copy(update=retrieval or {})})


CITED_FILES = ("kernel/contracts/decision.py", "docs/concepts/colony.md", "kernel/config.py",
               "tests/README.md")


class TargetingCase(ResearchCase):
    """Run research on a mandated-needs request and read back the children.

    The cited files exist in the throwaway repository: an explicit locator is requested only when
    its file does (round E), so a cited path that is not there never reaches a child.
    """

    def setUp(self) -> None:
        super().setUp()
        for rel in CITED_FILES:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# cited\n", encoding="utf-8")

    def children(self, config: KernelConfig | None = None, **fields: Any
                 ) -> dict[str, RetrievalRequestPayload]:
        """Return the retrieval children keyed by need id for a request with these fields."""
        payload = ResearchRequestPayload(question=QUESTION, evidence_needs=NEEDS,
                                         evidence_needs_only=True, **fields)
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, payload.model_dump(mode="json"))
        result = self.run_research(inv, self.ctx(config))
        self.assertEqual(result.status, ResultStatus.WAITING)
        kids = [RetrievalRequestPayload.model_validate(r.payload) for r in result.requests]
        return {k.need.id: k for k in kids}


class TestOptionContextIsConsumed(TargetingCase):
    """Wave 2 item 1: option_context drives locators and query hints."""

    def test_cited_paths_become_explicit_locators_on_every_native_child(self) -> None:
        for kid in self.children(option_context=OPTIONS).values():
            self.assertEqual(kid.explicit_locators, [
                "kernel/contracts/decision.py", "docs/concepts/colony.md#L10-L20",
                "kernel/config.py::ResearchConfig", "tests/README.md"])

    def test_evidence_ids_and_bare_symbols_stay_context_only(self) -> None:
        kid = self.children(option_context=OPTIONS)["need.prior_decisions"]
        for ref in (CITED_EVIDENCE.id, "ParseRecord", "parse_record"):
            self.assertNotIn(ref, kid.explicit_locators)

    def test_the_child_also_names_the_sources_that_hold_the_cited_paths(self) -> None:
        kid = self.children(option_context=OPTIONS)["need.prior_decisions"]
        self.assertEqual(kid.source_ids[:1], ["repo.decisions"])  # the need's own source first
        self.assertIn("repo.patterns", kid.source_ids)  # holds kernel/contracts/decision.py
        self.assertIn("repo.tests", kid.source_ids)  # holds tests/README.md

    def test_locators_are_bounded_by_max_explicit_locators(self) -> None:
        kids = self.children(_config(retrieval={"max_explicit_locators": 2}),
                             option_context=OPTIONS)
        self.assertEqual(kids["need.prior_decisions"].explicit_locators,
                         ["kernel/contracts/decision.py", "docs/concepts/colony.md#L10-L20"])

    def test_queries_are_goal_first_then_criteria_then_option_text(self) -> None:
        kid = self.children(option_context=OPTIONS,
                            criteria_context=["Does ingestion via paths.json still work?"]
                            )["need.prior_decisions"]
        self.assertEqual(kid.query_hints[0], QUESTION)
        self.assertEqual(kid.query_hints[1], "Does ingestion via paths.json still work?")
        text = " ".join(kid.query_hints)
        self.assertIn("Kernel-contract YAML per decision", text)
        self.assertIn("Reuse the AC store", text)

    def test_without_option_context_there_are_no_locators_and_the_goal_is_the_hint(self) -> None:
        kid = self.children()["need.prior_decisions"]
        self.assertEqual(kid.explicit_locators, [])
        self.assertEqual(kid.query_hints, [QUESTION])


class TestLocatorsMustBeRealFiles(TargetingCase):
    """Round 6 requested the garbage locator `-NNN.yaml`; only real repository paths are asked for."""

    def test_a_placeholder_fragment_and_a_missing_file_are_dropped(self) -> None:
        option = OptionContext(
            option_id="A", title="Per-decision YAML",
            description="Named like docs/decisions/ADR-NNN.yaml or -NNN.yaml",
            cited_refs=["-NNN.yaml", "docs/decisions/ADR-NNN.yaml", "kernel/config.py"])
        for kid in self.children(option_context=[option]).values():
            self.assertEqual(kid.explicit_locators, ["kernel/config.py"])

    def test_a_dropped_locator_is_logged_at_debug_not_requested(self) -> None:
        option = OptionContext(option_id="A", title="x", cited_refs=["docs/missing/none.md"])
        with self.assertLogs("kernel.capabilities.research.targeting", level="DEBUG") as logged:
            kids = self.children(option_context=[option])
        self.assertTrue(all(k.explicit_locators == [] for k in kids.values()))
        self.assertIn("no such file", "\n".join(logged.output))

    def test_a_locator_outside_the_repository_is_dropped(self) -> None:
        option = OptionContext(option_id="A", title="x", cited_refs=["../outside/secret.md"])
        self.assertTrue(all(k.explicit_locators == []
                            for k in self.children(option_context=[option]).values()))


class TestTargetedNeeds(TargetingCase):
    """Fix 4: named gaps and human-added claims become needs with their own queries."""

    GAP = "kernel/contracts/decision.py was not among the evidence"

    def test_a_named_gap_becomes_a_supporting_need_with_its_own_query_and_locator(self) -> None:
        kids = self.children(gaps=[self.GAP, "no evidence on how approvals are recorded"])
        gap = kids["need.gap.1"]
        self.assertEqual(gap.need.priority, Priority.SUPPORTING)
        self.assertIn(self.GAP, gap.need.question)
        self.assertEqual(gap.query_hints, [self.GAP])
        self.assertEqual(gap.explicit_locators, ["kernel/contracts/decision.py"])
        other = kids["need.gap.2"]
        self.assertEqual(other.explicit_locators, [])
        self.assertEqual(other.query_hints, ["no evidence on how approvals are recorded"])

    def test_targeted_needs_are_bounded_by_config(self) -> None:
        gaps = [f"missing fact number {n}" for n in range(6)]
        kids = self.children(_config(research={"max_targeted_needs": 2}), gaps=gaps)
        self.assertEqual(sorted(k for k in kids if k.startswith("need.gap")),
                         ["need.gap.1", "need.gap.2"])

    def test_a_human_added_option_has_its_claims_researched(self) -> None:
        added = OptionContext(option_id="opt.added.1", title="Kernel-contract YAML per decision",
                              description="ids are kernel-minted and validated at commit",
                              cited_refs=["kernel/contracts/decision.py"], human_added=True)
        kids = self.children(option_context=[OPTIONS[1], added])
        claim = kids["need.claim.opt.added.1"]
        self.assertEqual(claim.need.priority, Priority.SUPPORTING)
        self.assertIn("kernel-minted", claim.need.question)
        self.assertEqual(claim.explicit_locators, ["kernel/contracts/decision.py"])
        self.assertNotIn("need.claim.B", kids)  # only human-added options carry unverified claims

    def test_the_default_caps_targeted_needs_at_two(self) -> None:
        gaps = [f"missing fact number {n}" for n in range(6)]
        added = OptionContext(option_id="opt.added.1", title="Added", human_added=True)
        kids = self.children(gaps=gaps, option_context=[added])
        targeted = sorted(k for k in kids if k.startswith(("need.gap", "need.claim")))
        # claims have their own cap (max_claim_needs); max_targeted_needs (2) caps gaps only
        self.assertEqual(targeted, ["need.claim.opt.added.1", "need.gap.1", "need.gap.2"])

    def test_a_decision_without_gaps_or_added_options_gets_no_extra_need(self) -> None:
        self.assertEqual(sorted(self.children(option_context=OPTIONS)),
                         ["need.existing_patterns", "need.prior_decisions"])


class TestSynthesisUnknowns(ResearchCase):
    """The unknowns a synthesis names survive into the evidence bundle."""

    def test_unknowns_reach_the_final_bundle(self) -> None:
        self.params["evaluable"] = 0.3
        ctx, inv = self.ctx(), self.goal()
        waiting = self.run_research(inv, ctx)
        kids = [child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([CITED_EVIDENCE], {"need.prior_decisions": NeedStatus.SATISFIED}))]
        asked = self.run_research(resume(inv, waiting, kids), ctx)
        findings = child(ctx, RequestKind.SYNTHESIS, schema_ids.FINDINGS, {
            "findings": [], "unknowns": ["no file-type filter vocabulary was found"]})
        done = self.run_research(resume(inv, asked, [findings]), ctx)
        self.assertEqual(self.bundle(done).unknowns, ["no file-type filter vocabulary was found"])


class TestDecisionHandsGapsToResearch(DesignCase):
    """The decision keeps the unknowns of a round and passes them, with its criteria, on."""

    def test_the_next_research_request_carries_gaps_criteria_and_options(self) -> None:
        inv, ctx, first = self.start()
        first_request = ResearchRequestPayload.model_validate(first.requests[0].payload)
        self.assertEqual(first_request.criteria_context[0], "Are the diffs small and reviewable?")
        self.assertEqual([o.title for o in first_request.option_context[:1]],
                         ["One YAML file per decision"])
        extra = evidence_item("docs/more.md#L1-L2", "Another fact.", CATS.INTERNAL_PRINCIPLES)
        ctx = self.ctx(self.evidence + [extra])
        bundle = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                       {"evidence_ids": [extra.id],
                        "unknowns": ["kernel/contracts/decision.py is not among the evidence"]})
        self.params.update(sufficient=0.7, satisfies={k: v + 0.1 for k, v in FLAT.items()})
        second = self.run_decision(resume(inv, first, [bundle]), ctx)  # scores moved: not flat
        self.assertEqual(second.requests[0].kind, RequestKind.EVIDENCE)
        again = ResearchRequestPayload.model_validate(second.requests[0].payload)
        self.assertEqual(again.gaps, ["kernel/contracts/decision.py is not among the evidence"])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round E: the cited files exist in the fixture repository (a locator
#   must be a real file), garbage and missing locators are dropped, and the default caps
#   targeted needs at two. (#KernelV01/E)
# - 2026-10-01 [python-coder]: Tests for V0.1 wave 2 (targeted queries, answer-aware coverage).
#   (#KernelV01/D)
# ====================================================================
