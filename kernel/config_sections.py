"""
MODULE: kernel.config_sections
GOAL: The validated sections of the kernel configuration (limits, routing, decision, research,
    sources, Jev, host, data policy, Langfuse) and their shared base.
BUSINESS CONTEXT: Every threshold and limit the kernel uses is reviewed configuration, never a
    constant in logic; each field's description says what it bounds or decides.
ARCHITECTURE: Frozen, extra-forbidding Pydantic sections with no field defaults (the default JSON
    is the single source of values). Split out of `kernel.config`, which re-exports these names,
    to stay under the file-size limit; the retrieval section is in `kernel.config_retrieval`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kernel.contracts.base import fail
from kernel.contracts.enums import EvidenceCategory


class _Section(BaseModel):
    """Frozen, extra-forbidding base for config sections (no defaults by design)."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_attribute_docstrings=True)


Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class PathsConfig(_Section):
    """File-system locations (relative to the repository root unless absolute)."""

    run_root: str
    """Folder where each run's state and artifacts are written."""
    registry: str
    """Path of the capability registry that lists what the kernel can route to."""


class LimitsConfig(_Section):
    """Run limits (Rev 3 section 13.2)."""

    max_work_items: int = Field(ge=1)
    """Most work items one run may create, bounding runaway planning."""
    max_depth: int = Field(ge=1)
    """Deepest chain of child requests a run may spawn."""
    max_concurrent_native: int = Field(ge=1)
    """Most native capabilities running at once."""
    max_concurrent_host: int = Field(ge=1)
    """Most host handoffs outstanding at once."""
    max_retries: int = Field(ge=0)
    """How often one work item is retried before it is marked failed."""
    no_progress_limit: int = Field(ge=1)
    """Consecutive scheduler rounds without progress after which the run stops."""
    max_jev_calls: int = Field(ge=0)
    """Most Jev calls one run may make."""
    max_host_operations: int = Field(ge=0)
    """Most host operations one run may hand off."""
    max_active_seconds: float = Field(gt=0)
    """Most active seconds a run may spend before it stops."""
    max_cost_usd: float | None = Field(ge=0)
    """Most estimated spend per run in US dollars; null means no cost cap."""
    capability_timeout_seconds: float = Field(gt=0)
    """Longest a single capability may run before it is cut off."""
    langgraph_recursion_limit: int = Field(ge=1)
    """Step limit handed to the graph engine, a backstop against endless graph loops."""
    max_scheduler_iterations: int | None = Field(ge=1)
    """Most scheduler rounds per run; null derives the limit from the graph recursion limit."""


class RoutingConfig(_Section):
    """Routing thresholds."""

    min_selected_probability: Probability
    """Lowest probability the chosen capability needs before routing selects it."""
    min_confidence: Probability
    """Lowest provider confidence routing accepts for its answer."""
    on_insufficient_context: Literal["human", "block"]
    """What routing does when the context cannot decide: ask a human or block the run."""


class IntentConfig(_Section):
    """Thresholds for the intake answer-kind classification and the clarification cap."""

    min_selected_probability: Probability
    """Lowest probability the chosen answer kind needs at intake."""
    min_confidence: Probability
    """Lowest provider confidence intake accepts for its classification."""
    max_clarifications: int = Field(ge=0)
    """Most clarifying questions intake may ask for one request."""


class DecisionConfig(_Section):
    """Decision-graph thresholds."""

    sufficiency_threshold: Probability
    (
        "Probability that evidence suffices for a criterion at which the criterion counts as "
        "answered; below it the criterion stays uncertain."
    )
    satisfies_threshold: Probability
    (
        "Probability that an option satisfies a criterion at which it passes (at or below one "
        "minus this it fails)."
    )
    preference_threshold: Probability
    """Probability that the choice turns on a human preference at which the human is asked."""
    conflict_threshold: Probability
    (
        "Probability that evidence conflicts at which the conflict must be resolved before "
        "deciding."
    )
    missing_min_probability: Probability
    """Lowest probability a kind of missing knowledge needs to be recorded as missing."""
    require_option_grounding: bool
    (
        "Options generated for an unknown option set must cite the evidence they rest on; an "
        "ungrounded option is refused (True) or only flagged as a limitation (False)."
    )
    max_grounding_evidence: int = Field(ge=1)
    """Most evidence items attached to one options request (bounds the host input)."""
    design_judgement_threshold: Probability
    (
        "A criterion counts as a design judgement (a property of the proposed options that "
        "research cannot settle) when Jev's probability for that reading reaches this value."
    )
    progress_epsilon: float = Field(ge=0.0, le=1.0)
    (
        "No material progress: every score moved by at most this between assessments after new "
        "evidence."
    )
    max_research_rounds: int = Field(ge=1)
    (
        "Most research rounds one decision may request before it hands the ranked options to a "
        "human."
    )
    reserve_assessments: int = Field(ge=0)
    """Final decision assessments whose Jev calls stay reserved (research must leave them)."""
    reserve_extra_options: int = Field(ge=0)
    """Options added to the size of the reserved assessment (a human may add one when ranked)."""
    reserve_margin_calls: int = Field(ge=0)
    """Calls kept beyond the reserved assessments for routing a child request and other overhead."""


class ResearchConfig(_Section):
    """Research-graph thresholds and category descriptions offered to Jev."""

    need_required_threshold: Probability
    """Probability that an evidence category is needed at which it becomes a required need."""
    need_supporting_threshold: Probability
    (
        "Probability that an evidence category is needed at which it becomes a supporting need "
        "(must not exceed the required threshold)."
    )
    evaluable_threshold: Probability
    (
        "Lowest probability that the gathered evidence is enough to evaluate the question; below "
        "it research reports the shortfall."
    )
    allow_synthesis: bool
    """Whether research may ask the host to synthesise findings from the evidence."""
    category_descriptions: dict[EvidenceCategory, str]
    (
        "What each evidence category means, offered to Jev when it chooses which categories to "
        "search."
    )
    answer_aware_coverage: bool
    """A need counts as satisfied only when Jev judges the kept evidence answers its question."""
    answer_threshold: Probability
    """Probability the answer judgement must reach for a relevance-satisfied need to stay so."""
    max_targeted_needs: int = Field(ge=0)
    """Most gap needs planned per research run; the rest are named, not researched."""
    max_claim_needs: int = Field(ge=0)
    """Most claim checks for human-added options planned per run; the rest are named."""

    @model_validator(mode="after")
    def _all_categories(self) -> ResearchConfig:
        """Every evidence category needs a description and thresholds must be ordered."""
        missing = set(EvidenceCategory) - set(self.category_descriptions)
        if missing:
            fail(f"category_descriptions missing {sorted(m.value for m in missing)}")
        if self.need_supporting_threshold > self.need_required_threshold:
            fail("need_supporting_threshold must not exceed need_required_threshold")
        return self


class SourceConfig(_Section):
    """One entry of the source catalog (where evidence may come from)."""

    id: str
    """Unique id of the source, cited by evidence and by source restrictions."""
    kind: Literal["repo_text", "knowledge_map", "graph_query", "host_research"]
    """How the source is read: repository text, knowledge map, graph query or host research."""
    categories: list[EvidenceCategory] = Field(min_length=1)
    """Evidence categories the source can serve."""
    automatic_research: bool = True  # false: select only through explicit sources or locators
    (
        "Whether research may choose this source on its own; false means only explicit sources "
        "or locators select it."
    )
    roots: list[str] = Field(default_factory=list)
    """Folders or files the source reads, relative to the repository root."""
    surfaces: list[str] = Field(default_factory=list)
    """Named knowledge-map surfaces the source exposes."""
    deny_globs: list[str] = Field(default_factory=list)  # added to `retrieval.deny_globs`
    """Path patterns this source must never read, added to the global retrieval deny list."""
    max_file_bytes: int | None = Field(default=None, ge=1)  # null: `retrieval.max_file_bytes`
    """Largest file this source reads; null uses the global retrieval limit."""


class JevConfig(_Section):
    """Jev provider settings."""

    model: str
    """Name of the model Jev asks."""
    transport: Literal["classifier", "http"]
    """How Jev is reached: the local classifier or an HTTP service."""
    timeout_seconds: float = Field(gt=0)
    """Longest one Jev call may take."""
    max_questions_per_call: int = Field(ge=1)
    """Most questions batched into one Jev call."""
    max_state_chars: int = Field(ge=1)
    """Most characters of run state sent with a Jev call, bounding the input."""
    retry_backoff_seconds: float = Field(ge=0)
    """Base delay before retrying a failed Jev call, doubled per retry."""
    price_per_input_token_usd: float | None = Field(ge=0)
    """Price of one input token in US dollars, used to estimate cost; null when unknown."""


class HostConfig(_Section):
    """Host-handoff settings."""

    enabled: bool
    """Whether work may be handed to the host client at all."""
    fallback_on_no_match: bool
    """Whether a request no native capability matches falls back to the host."""
    max_repair_attempts: int = Field(ge=0)
    """How often a malformed host submission may be sent back for repair."""
    formulate_questions: bool
    """Whether the host rewords questions for the human; false asks the original wording."""
    max_input_chars: int = Field(ge=1)
    """Most characters of input placed in one host packet."""


class DataPolicyConfig(_Section):
    """What may leave the process (Jev, Langfuse)."""

    send_repo_excerpts_to_jev: bool
    """Whether repository text may leave the process in Jev calls."""
    telemetry_excerpts: Literal["truncated", "hash", "none"]
    """How excerpts appear in telemetry: truncated, only a hash, or not at all."""
    telemetry_max_field_chars: int = Field(ge=1)
    """Longest text field written to telemetry before it is cut."""


class LangfuseConfig(_Section):
    """Langfuse export settings (credentials come from secrets, never from here)."""

    enabled: bool
    """Whether traces are exported to Langfuse."""
    environment: str
    """Langfuse environment label the traces are filed under."""
    trace_name: str
    """Name given to each run's trace."""
    flush_on_exit: bool
    """Whether pending traces are sent before the process exits."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Split out of config.py with a purpose on every field, so the
#   committed kernel_config schema says what each limit or threshold decides.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# ====================================================================
