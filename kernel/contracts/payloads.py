"""
MODULE: kernel.contracts.payloads
GOAL: Payload models for the twelve registered schema ids (Rev 3 section 7.11 plus the goal,
    human-question and human-answer payloads the kernel needs).
BUSINESS CONTEXT: Named payloads must be validated, not free-form dicts; these models are the
    single definition exported as JSON Schema for clients and checked against fixtures.
ARCHITECTURE: One model per schema id; schema_catalog maps id -> model. Structural checks live
    here, reference checks (cited ids exist) in schema_catalog.validate_semantics.
"""

from __future__ import annotations

from kernel.contracts.verbatim import VerbatimJson, VerbatimString

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from kernel.contracts.base import KernelModel, fail
from kernel.contracts.decision import CriterionAssessment, Criterion, Option, Rationale
from kernel.contracts.enums import ApprovalStatus, DecisionStatus, ProposalStatus
from kernel.contracts.evidence import EvidenceBundlePayload, EvidenceNeed, Finding
from kernel.contracts.run import TraceRefs
from kernel.contracts.payloads_human import (  # noqa: F401
    AddedOption,
    CriterionEdit,
    HumanAnswerPayload,
    HumanQuestionRequestPayload,
    unique_ids as _unique,
)


class GoalRequestPayload(KernelModel):
    """leafcutter.goal_request.v1: a free-form goal for the root capability request."""

    goal: VerbatimString = Field(min_length=1, max_length=16000)
    (
        "The caller's goal in their own words, kept verbatim for intent classification and the "
        "record."
    )
    clarifications: list[VerbatimString] = Field(default_factory=list)
    (
        "The caller's answers to earlier clarifying questions, verbatim, so intent is not "
        "paraphrased."
    )
    context_summary: str | None = None
    """The caller's short summary of surrounding context, offered as background for the goal."""


class DecisionRequestPayload(KernelModel):
    """leafcutter.decision_request.v1."""

    question: str = Field(min_length=1)
    """The decision question the kernel must answer."""
    options: list[Option] = Field(default_factory=list)
    """Candidate answers the caller already has; empty when the kernel should find them."""
    criteria: list[Criterion] = Field(default_factory=list)
    """What an option must satisfy; give them here or set criteria_missing."""
    criteria_missing: bool = False
    (
        "Set when the caller supplies no criteria, so the kernel proposes some for approval; it "
        "contradicts a non-empty criteria list."
    )
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence the caller already holds, so research does not fetch it again."""
    constraint_ids: list[str] = Field(default_factory=list)
    """Ids of evidence items that state constraints the chosen option must respect."""
    approval_required: bool = False
    """Whether a human must approve the selected option before the decision counts as resolved."""
    decision_scope: str | None = None
    (
        "Free-text note on what the decision covers; recorded with the request and not "
        "interpreted by the kernel."
    )

    @model_validator(mode="after")
    def _criteria_or_flag(self) -> DecisionRequestPayload:
        """Criteria must be given or explicitly flagged missing; ids must be unique."""
        if not self.criteria and not self.criteria_missing:
            fail("supply criteria or set criteria_missing=true")
        if self.criteria and self.criteria_missing:
            fail("criteria_missing=true contradicts supplied criteria")
        _unique([o.id for o in self.options], "option")
        _unique([c.id for c in self.criteria], "criterion")
        return self


class DecisionReportPayload(KernelModel):
    """leafcutter.decision_report.v1."""

    status: DecisionStatus
    (
        "Where the decision stands, so the caller knows whether to act, supply more, or wait for "
        "a human."
    )
    recommendation: str | None = None
    """The plain-language answer to the question, shown to the caller when there is one."""
    selected_option_id: str | None = None
    """Id of the option the decision picked; set only on a resolved report."""
    criterion_assessments: list[CriterionAssessment] = Field(default_factory=list)
    """How options fared against each criterion, so the choice can be audited."""
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    """Evidence that backs the recommendation, for the caller to inspect."""
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    """Evidence that argues against the recommendation, kept visible rather than dropped."""
    open_questions: list[str] = Field(default_factory=list)
    """What is still unanswered; an unresolved report lists what would settle it."""
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    """Whether a human has approved the outcome, for decisions that require approval."""
    limitations: list[str] = Field(default_factory=list)
    (
        "Known weaknesses of the result (cut-off retrieval, missing sources) the reader should "
        "weigh."
    )
    rationale: Rationale | None = None
    """Short explanation of why the option was chosen, with who wrote it."""
    trace_refs: TraceRefs | None = None
    """Where to inspect this run's trace, for finding out how the result came about."""

    @model_validator(mode="after")
    def _resolved_selects(self) -> DecisionReportPayload:
        """Only a resolved report selects an option; an unresolved one lists open questions."""
        resolved = self.status is DecisionStatus.RESOLVED
        if resolved and self.selected_option_id is None:
            fail("a resolved report must select an option")
        if not resolved and self.selected_option_id is not None:
            fail("an unresolved report cannot select an option")
        return self


class OptionContext(KernelModel):
    """One option the decision researches for: what it is and what it already cites."""

    option_id: str = Field(min_length=1)
    """Id of the option research is gathering evidence for."""
    title: str = Field(min_length=1)
    """The option's short name, used as query text."""
    description: str | None = None
    """What the option means, used as query text beside the title."""
    cited_refs: list[str] = Field(default_factory=list)
    """Evidence ids plus any file paths or symbol names the option's text mentions."""
    human_added: bool = False
    """True for an option a human added: its claims are unverified and research checks them."""


class ResearchRequestPayload(KernelModel):
    """leafcutter.research_request.v1."""

    question: str = Field(min_length=1)
    """The question research must find evidence for."""
    answer_requirements: dict[str, JsonValue] | None = None
    """Original answer obligations; the neutral adapter validates their typed contract."""
    assessment: dict[str, VerbatimJson] | None = None
    """Scoped supplied evidence interpreted conditionally by the neutral retrieval port."""
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list)
    """Specific pieces of evidence to find; empty means Jev chooses the categories to search."""
    source_restrictions: list[str] = Field(default_factory=list)
    (
        "Ids of the only sources research may use; empty means no restriction beyond the run's "
        "scope."
    )
    existing_evidence_ids: list[str] = Field(default_factory=list)
    """Evidence already held, so research does not fetch or count it twice."""
    expected_coverage: Literal["all_required", "best_effort"] = "all_required"
    (
        "Whether every required need must be satisfied (all_required) or partial coverage is "
        "acceptable (best_effort)."
    )
    evidence_needs_only: bool = False
    """Research exactly the given needs: Jev adds no further evidence categories."""
    option_context: list[OptionContext] = Field(default_factory=list)
    """The options the decision has so far (empty before options exist); research reads it."""
    criteria_context: list[str] = Field(default_factory=list)
    """The approved criteria's questions, used as query text beside the goal."""
    gaps: list[str] = Field(default_factory=list)
    (
        "Open unknowns (synthesis gaps, research unknowns, option-design feasibility facts); the "
        "first research.max_targeted_needs of them become targeted needs."
    )
    jev_reserve: int = Field(default=0, ge=0)
    (
        "Jev calls the requester keeps for itself afterwards (its final assessment); research "
        "plans no more needs than the rest of its budget affords and never spends into this "
        "reserve."
    )


class RetrievalLimits(KernelModel):
    """Result limits for one retrieval request."""

    top_k: int | None = Field(default=None, ge=1)
    """Most evidence items to return; null uses the configured default."""
    max_chars: int | None = Field(default=None, ge=1)
    """Most characters of evidence to return in total; null uses the configured default."""


class RetrievalRequestPayload(KernelModel):
    """leafcutter.retrieval_request.v1."""

    knowledge: dict[str, VerbatimJson] | None = None
    """Neutral knowledge request fields, fully validated by the capability adapter."""
    answer_requirements: dict[str, JsonValue] | None = None
    """Preserved across research, clarification and progressive source disclosure."""
    assessment: dict[str, VerbatimJson] | None = None
    """Scoped supplied evidence interpreted conditionally by the neutral retrieval port."""
    need: EvidenceNeed
    """The evidence need to retrieve for; its question and category steer the search."""
    source_ids: list[str] = Field(default_factory=list)
    """Sources to search; empty means every eligible source."""
    detail: Literal["excerpt", "summary", "locator"] = "excerpt"
    """How much of each hit to return: an excerpt, a summary, or its locator only."""
    limits: RetrievalLimits = Field(default_factory=RetrievalLimits)
    """Bounds on how much evidence the request may return."""
    explicit_locators: list[str] = Field(default_factory=list)
    (
        "Exact places to fetch before ranking: `path`, `path#Lx-Ly`, `path#heading`, "
        "`path::Symbol`."
    )
    query_hints: list[str] = Field(default_factory=list)
    """Texts to search for before the need's own wording: the goal first, then criteria, options."""
    max_rerank_batches: int | None = Field(default=None, ge=1)
    (
        "Most rerank batches this request may judge (the requester's Jev budget affords no more "
        "than this beside its reserve); null means the configured `retrieval.rerank_max_batches`."
    )
    jev_reserve: int = Field(default=0, ge=0)
    """Jev calls retained for the requester; graph planning must not spend this reserve."""


class OptionsRequestPayload(KernelModel):
    """leafcutter.options_request.v1."""

    problem: VerbatimString = Field(min_length=1)
    """The decision problem to generate options for, verbatim from the caller."""
    clarifications: list[VerbatimString] = Field(default_factory=list)
    """Human answers to earlier questions, verbatim, that narrow which options to generate."""
    constraint_ids: list[str] = Field(default_factory=list)
    """Ids of evidence items stating constraints every generated option must respect."""
    existing_option_ids: list[str] = Field(default_factory=list)
    """Ids of options the caller already has, so generators do not duplicate them."""
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence the generated options may rest on."""
    max_options: int = Field(default=5, ge=0)
    """Most new options to propose."""
    propose_criteria: bool = False
    """Whether to also propose criteria for human approval."""
    require_grounding: bool = False
    """Every proposed option must cite, in `source_refs`, evidence ids from `evidence_ids`."""
    findings: list[str] = Field(default_factory=list)
    """Accepted synthesis findings as `[id] claim`, so the host does not re-derive them."""


class OptionsPayload(KernelModel):
    """leafcutter.options.v1: every option is a proposal, never pre-approved."""

    options: list[Option] = Field(default_factory=list)
    """Candidate options the host generated; every one is a proposal awaiting approval."""
    named_options: list[Option] = Field(default_factory=list)
    (
        "Options the goal names, verified by the kernel (supplied, never proposals). Kernel-set "
        "only."
    )
    proposed_criteria: list[Criterion] = Field(default_factory=list)
    """Criteria the host suggests; every one is a proposal awaiting approval."""
    unresolved_feasibility: list[str] = Field(default_factory=list)
    """Feasibility facts the host could not settle; they become targeted research."""

    @model_validator(mode="after")
    def _all_proposed(self) -> OptionsPayload:
        """Generated options must carry proposal_status=proposed and unique ids."""
        if any(o.proposal_status is not ProposalStatus.PROPOSED for o in self.options):
            fail("every generated option must have proposal_status=proposed")
        if any(c.proposal_status is not ProposalStatus.PROPOSED
               for c in self.proposed_criteria):
            fail("every generated criterion must have proposal_status=proposed")
        _unique([o.id for o in [*self.options, *self.named_options]], "option")
        _unique([c.id for c in self.proposed_criteria], "criterion")
        return self


class SynthesisLimits(KernelModel):
    """Analysis limits for a synthesis request."""

    max_findings: int | None = Field(default=None, ge=1)
    """Most findings the synthesis may return."""
    max_chars: int | None = Field(default=None, ge=1)
    """Most characters the synthesis may return."""


class SynthesisRequestPayload(KernelModel):
    """leafcutter.synthesis_request.v1."""

    operation: str = Field(min_length=1)
    """The kind of analysis wanted, which selects the host's instructions."""
    question: str = Field(min_length=1)
    """The question the synthesis must answer from the evidence."""
    evidence_ids: list[str] = Field(default_factory=list)
    """The evidence to analyse; the synthesis may cite only these."""
    output_requirements: list[str] = Field(default_factory=list)
    """Extra instructions the host must follow in its output."""
    limits: SynthesisLimits = Field(default_factory=SynthesisLimits)
    """Bounds on the size of the synthesis."""


class FindingsPayload(KernelModel):
    """leafcutter.findings.v1."""

    findings: list[Finding] = Field(default_factory=list)
    """Source-linked claims the synthesis reached, each citing its evidence."""
    agreements: list[str] = Field(default_factory=list)
    """Points on which the evidence sources agree."""
    disagreements: list[str] = Field(default_factory=list)
    """Points on which sources conflict; the decision keeps them as context rather than choosing."""
    constraints: list[str] = Field(default_factory=list)
    """Constraints the evidence puts on any option."""
    assumptions: list[str] = Field(default_factory=list)
    """Premises taken without evidence, listed so a reader can challenge them."""
    unknowns: list[str] = Field(default_factory=list)
    """What the evidence could not establish; the next research round aims queries at these."""


__all__ = [
    "AddedOption", "CriterionEdit", "DecisionReportPayload", "DecisionRequestPayload",
    "EvidenceBundlePayload", "FindingsPayload", "GoalRequestPayload", "HumanAnswerPayload",
    "HumanQuestionRequestPayload", "OptionContext", "OptionsPayload", "OptionsRequestPayload",
    "ResearchRequestPayload", "RetrievalLimits", "RetrievalRequestPayload",
    "SynthesisLimits", "SynthesisRequestPayload",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Field purposes added; the human question/answer payloads moved to
#   payloads_human.py (re-exported here) to keep this file under 400 lines.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-02 [python-coder]: human_answer.v1 accepts the pair {choice_id, free_text}: a choice
#   with a condition; other mixes stay rejected. (#KernelChoiceWithCondition)
# - 2026-10-01 [python-coder]: Research now reads option_context; the request also carries
#   criteria_context and gaps (what a synthesis could not find), OptionContext.human_added marks
#   unverified claims, and retrieval_request.query_hints lets queries lead with the goal.
#   (#KernelV01/D)
# - 2026-10-01 [python-coder]: ResearchRequestPayload.option_context (OptionContext) tells research
#   which options the decision weighs and what they cite; not consumed yet. (#KernelV01/A)
# - 2026-10-02 [python-coder]: OptionsPayload.named_options (kernel-verified, supplied) and
#   HumanAnswerPayload.added_options (human-supplied at approval). (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: HumanQuestionRequestPayload.evidence_ids and
#   OptionsRequestPayload.findings carry cited evidence to the approval question and accepted
#   synthesis findings to the options packet. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: OptionsRequestPayload.require_grounding and
#   ResearchRequestPayload.evidence_needs_only support grounded option generation: the first says
#   options must cite the supplied evidence, the second keeps the grounding research to the
#   categories the decision asked for. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:30 [python-coder]: human_answer.v1 gains a structured approval answer
#   (approved ids, edited criteria) and the question gains `structured_allowed`; both additive,
#   free text stays as a recorded fallback. (#KernelBootstrapV0/P6)
# - 2026-09-30 22:00 [python-coder]: goal_request, human_question_request and human_answer are
#   added to the nine Rev 3 section 7.11 schemas because the root request, human interaction
#   and human answer need registered payloads (design part 2). (#KernelBootstrapV0/P1)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================

# - 2026-10-01 20:00 [python-coder]: Bind optional knowledge through existing scoped retrieval contracts. (#TICKET-20261001-KM-400e-3)
