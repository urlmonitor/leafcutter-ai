"""
MODULE: kernel.config
GOAL: Validated kernel configuration loaded from config/kernel_config.default.json with an
    optional override, plus the generated JSON Schema.
BUSINESS CONTEXT: Every threshold, limit and path the kernel uses lives in one reviewed file and
    is recorded in traces; no numeric threshold is hard-coded in logic (Rev 3 sections 9 and
    13.2). The repo convention is JSON defaults plus a schema in config/, not a second framework.
ARCHITECTURE: Pydantic models carry no defaults on purpose: the default JSON is the single source
    of values. load_kernel_config deep-merges the override, validates, and returns a frozen model.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from kernel.config_memory import MemoryConfig
from kernel.contracts.base import fail
from kernel.contracts.enums import EvidenceCategory

logger = logging.getLogger(__name__)

CONFIG_ENV_VAR = "LEAFCUTTER_KERNEL_CONFIG"
DEFAULT_CONFIG_NAME = "kernel_config.default.json"
SCHEMA_CONFIG_NAME = "kernel_config.schema.json"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


class ConfigError(Exception):
    """The kernel configuration could not be read or failed validation."""

    def __init__(self, source: Path | str, detail: str) -> None:
        """Build the message from the config source and detail."""
        super().__init__(f"invalid kernel config {source}: {detail}")
        self.source = str(source)
        self.detail = detail


class _Section(BaseModel):
    """Frozen, extra-forbidding base for config sections (no defaults by design)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class PathsConfig(_Section):
    """File-system locations (relative to the repository root unless absolute)."""

    run_root: str
    registry: str


class LimitsConfig(_Section):
    """Run limits (Rev 3 section 13.2)."""

    max_work_items: int = Field(ge=1)
    max_depth: int = Field(ge=1)
    max_concurrent_native: int = Field(ge=1)
    max_concurrent_host: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    no_progress_limit: int = Field(ge=1)
    max_jev_calls: int = Field(ge=0)
    max_host_operations: int = Field(ge=0)
    max_active_seconds: float = Field(gt=0)
    max_cost_usd: float | None = Field(ge=0)
    capability_timeout_seconds: float = Field(gt=0)
    langgraph_recursion_limit: int = Field(ge=1)
    max_scheduler_iterations: int | None = Field(ge=1)


class RoutingConfig(_Section):
    """Routing thresholds."""

    min_selected_probability: Probability
    min_confidence: Probability
    on_insufficient_context: Literal["human", "block"]


class IntentConfig(_Section):
    """Thresholds for the intake answer-kind classification and the clarification cap."""

    min_selected_probability: Probability
    min_confidence: Probability
    max_clarifications: int = Field(ge=0)


class DecisionConfig(_Section):
    """Decision-graph thresholds."""

    sufficiency_threshold: Probability
    satisfies_threshold: Probability
    preference_threshold: Probability
    conflict_threshold: Probability
    missing_min_probability: Probability
    #: Options generated for an unknown option set must cite the evidence they rest on; an
    #: ungrounded option is refused (True) or only flagged as a limitation (False).
    require_option_grounding: bool
    #: Most evidence items attached to one options request (bounds the host input).
    max_grounding_evidence: int = Field(ge=1)
    #: A criterion counts as a design judgement (a property of the proposed options that research
    #: cannot settle) when Jev's probability for that reading reaches this value.
    design_judgement_threshold: Probability
    #: No material progress: every score moved by at most this between assessments after new evidence.
    progress_epsilon: float = Field(ge=0.0, le=1.0)
    #: Most research rounds one decision may request before it hands the ranked options to a human.
    max_research_rounds: int = Field(ge=1)
    #: Final decision assessments whose Jev calls stay reserved (research must leave them).
    reserve_assessments: int = Field(ge=0)
    #: Options added to the size of the reserved assessment (a human may add one when ranked).
    reserve_extra_options: int = Field(ge=0)
    #: Calls kept beyond the reserved assessments for routing a child request and other overhead.
    reserve_margin_calls: int = Field(ge=0)


class ResearchConfig(_Section):
    """Research-graph thresholds and category descriptions offered to Jev."""

    need_required_threshold: Probability
    need_supporting_threshold: Probability
    evaluable_threshold: Probability
    allow_synthesis: bool
    category_descriptions: dict[EvidenceCategory, str]
    #: A need counts as satisfied only when Jev judges the kept evidence answers its question.
    answer_aware_coverage: bool
    #: Probability the answer judgement must reach for a relevance-satisfied need to stay so.
    answer_threshold: Probability
    #: Most extra needs built from named gaps and human-added option claims in one research run
    #: (claims first, then gaps). Every need costs about one rerank call, so this bounds a round.
    max_targeted_needs: int = Field(ge=0)

    @model_validator(mode="after")
    def _all_categories(self) -> ResearchConfig:
        """Every evidence category needs a description and thresholds must be ordered."""
        missing = set(EvidenceCategory) - set(self.category_descriptions)
        if missing:
            fail(f"category_descriptions missing {sorted(m.value for m in missing)}")
        if self.need_supporting_threshold > self.need_required_threshold:
            fail("need_supporting_threshold must not exceed need_required_threshold")
        return self


class RetrievalConfig(_Section):
    """Repository retrieval bounds."""

    relevance_threshold: Probability
    top_k: int = Field(ge=1)
    max_candidates: int = Field(ge=1)
    excerpt_context_lines: int = Field(ge=0)
    max_excerpt_chars: int = Field(ge=1)
    max_file_bytes: int = Field(ge=1)
    deny_globs: list[str]
    #: Relevance a kept item needs to count towards a need's coverage (lower ones stay context).
    coverage_relevance_threshold: Probability
    #: Sections (headings, top-level keys, top-level defs) returned per file, best first.
    sections_per_file: int = Field(ge=1)
    #: Longest section (lines) scored whole; a longer one is cut into windows of this many lines.
    max_section_lines: int = Field(ge=10)
    #: Fewest candidates a source may offer when it is small (capped by `max_candidates`).
    source_candidate_floor: int = Field(ge=1)
    #: Candidates a source may offer per scanned file (bounded by `max_candidates`).
    source_candidate_ratio: float = Field(gt=0)
    #: Most explicit locators fetched per request (`retrieval_request.explicit_locators`).
    max_explicit_locators: int = Field(ge=0)
    #: Most search terms one retrieval query carries (goal first, then hints, then need filler).
    max_query_terms: int = Field(ge=1)
    #: Candidates one rerank batch sends to Jev (`max_candidates` is the pool); with
    #: `jev.max_questions_per_call` at least this large a batch is one call.
    rerank_max_per_need: int = Field(ge=1)
    #: Batches one need may judge; further ones only until it has enough evidence (rerank_min_items).
    rerank_max_batches: int = Field(ge=1)
    #: A need is `satisfied` only with at least this many kept items at or above
    #: `coverage_relevance_threshold` ...
    satisfied_min_items: int = Field(ge=1)
    #: ... or with a single kept item whose relevance reaches this stronger bar.
    satisfied_strong_threshold: Probability
    #: A candidate repeating this share of the goal near-verbatim reviews the run asking, not
    #: evidence for it, and is demoted (0 disables this and the review test).
    self_reference_ratio: Probability
    #: Factor on the relevance of a self-referencing candidate (cited ones are exempt).
    self_reference_penalty: Probability
    #: Score per rarity unit of each distinctive path word (a file NAMED after the topic).
    path_match_weight: int = Field(ge=0)
    #: BM25 term-count saturation and length-normalisation strength (0 = none); orders only.
    bm25_k1: float = Field(gt=0)
    bm25_b: Probability
    #: Sections of one file the FIRST rerank batch may hold (later pool places: sections_per_file).
    pool_sections_per_file: int = Field(ge=1)
    #: Candidates per source guaranteed in the first batch if they score this share of the best.
    pool_fair_share: int = Field(ge=0)
    pool_fair_min_ratio: Probability
    #: A need judges more batches until this many items passed `relevance_threshold` ...
    rerank_min_items: int = Field(ge=0)
    #: ... and skips one when the best unjudged candidate scores below this share of the judged.
    rerank_stop_ratio: Probability
    #: Goal share a document quotes (beside a run or trace id), or file-name marker, to review its run.
    review_quote_ratio: Probability
    review_path_markers: list[str]
    #: A JSON registry is pinned when this many query words are names in its vocabulary.
    registry_pin_min_terms: int = Field(ge=1)


class SourceConfig(_Section):
    """One entry of the source catalog (where evidence may come from)."""

    id: str
    kind: Literal["repo_text", "knowledge_map", "host_research"]
    categories: list[EvidenceCategory] = Field(min_length=1)
    roots: list[str] = Field(default_factory=list)
    surfaces: list[str] = Field(default_factory=list)
    deny_globs: list[str] = Field(default_factory=list)  # added to `retrieval.deny_globs`
    max_file_bytes: int | None = Field(default=None, ge=1)  # null: `retrieval.max_file_bytes`


class JevConfig(_Section):
    """Jev provider settings."""

    model: str
    transport: Literal["classifier", "http"]
    timeout_seconds: float = Field(gt=0)
    max_questions_per_call: int = Field(ge=1)
    max_state_chars: int = Field(ge=1)
    retry_backoff_seconds: float = Field(ge=0)
    price_per_input_token_usd: float | None = Field(ge=0)


class HostConfig(_Section):
    """Host-handoff settings."""

    enabled: bool
    fallback_on_no_match: bool
    max_repair_attempts: int = Field(ge=0)
    formulate_questions: bool
    max_input_chars: int = Field(ge=1)


class DataPolicyConfig(_Section):
    """What may leave the process (Jev, Langfuse)."""

    send_repo_excerpts_to_jev: bool
    telemetry_excerpts: Literal["truncated", "hash", "none"]
    telemetry_max_field_chars: int = Field(ge=1)


class LangfuseConfig(_Section):
    """Langfuse export settings (credentials come from secrets, never from here)."""

    enabled: bool
    environment: str
    trace_name: str
    flush_on_exit: bool


class KernelConfig(_Section):
    """Complete kernel configuration."""

    paths: PathsConfig
    limits: LimitsConfig
    routing: RoutingConfig
    intent: IntentConfig
    decision: DecisionConfig
    research: ResearchConfig
    retrieval: RetrievalConfig
    sources: list[SourceConfig]
    jev: JevConfig
    host: HostConfig
    data_policy: DataPolicyConfig
    langfuse: LangfuseConfig
    memory: MemoryConfig

    @model_validator(mode="after")
    def _unique_sources(self) -> KernelConfig:
        """Source ids must be unique."""
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            fail("duplicate source ids")
        return self


def repo_root() -> Path:
    """Return the repository root (the parent of the kernel package directory)."""
    return Path(__file__).resolve().parents[1]


def default_config_path() -> Path:
    """Return the path of config/kernel_config.default.json."""
    return repo_root() / "config" / DEFAULT_CONFIG_NAME


def _read_object(path: Path) -> dict:
    """Read a JSON object from path, raising ConfigError on IO or parse problems."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(path, f"cannot read file: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(path, f"not valid UTF-8 text: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(path, f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(path, "top level must be a JSON object")
    return data


def deep_merge(base: Mapping, override: Mapping) -> dict:
    """Return base with override merged in; nested objects merge, everything else replaces."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_kernel_config(override: Path | None = None, *, env: Mapping[str, str] | None = None,
                       default_path: Path | None = None) -> KernelConfig:
    """Load defaults, merge the optional override and validate.

    Args:
        override: Override file; falls back to the LEAFCUTTER_KERNEL_CONFIG env var.
        env: Environment mapping (defaults to os.environ).
        default_path: Alternative defaults file (tests).

    Returns:
        KernelConfig: The validated, frozen configuration.

    Raises:
        ConfigError: A file is unreadable, invalid JSON, or fails validation.
    """
    environment = os.environ if env is None else env
    data = _read_object(default_path or default_config_path())
    data.pop("$schema", None)
    override_path = override or (Path(environment[CONFIG_ENV_VAR])
                                 if environment.get(CONFIG_ENV_VAR) else None)
    if override_path is not None:
        extra = _read_object(Path(override_path))
        extra.pop("$schema", None)
        data = deep_merge(data, extra)
    try:
        return KernelConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(override_path or default_path or default_config_path(),
                          str(exc)) from exc


def kernel_config_schema() -> dict:
    """Return the JSON Schema generated from KernelConfig."""
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": SCHEMA_CONFIG_NAME,
            **KernelConfig.model_json_schema(mode="validation")}


def render_config_schema() -> str:
    """Return the deterministic text committed as config/kernel_config.schema.json."""
    return json.dumps(kernel_config_schema(), indent=2, sort_keys=True) + "\n"


def write_config_schema(path: Path) -> None:
    """Write the generated schema to path."""
    try:
        path.write_text(render_config_schema(), encoding="utf-8", newline="\n")
    except OSError:
        logger.exception("could not write config schema to %s", path)
        raise


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The `memory` section (backend, precedent thresholds) lives in
#   kernel/config_memory.py because this file is at the size limit. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: Round F: ordering, pool, rerank depth, review limits. (#KernelV01/F)
# - 2026-10-01 [python-coder]: Round E: decision.reserve_* keep Jev budget for a final assessment,
#   retrieval.rerank_max_per_need bounds the rerank batch per need, satisfied_* and self_reference_*
#   tighten coverage and demote reviews of the asking run, path_match_weight weighs path matches
#   against content hits; research.max_targeted_needs is 2. (#KernelV01/E)
# - 2026-10-01 [python-coder]: Added decision.design_judgement_threshold, progress_epsilon and
#   max_research_rounds so the design-decision ending is configuration. (#KernelV01/A)
# - 2026-10-01 23:00 [python-coder]: Added decision.require_option_grounding and
#   max_grounding_evidence, retrieval.coverage_relevance_threshold and a per-source deny_globs
#   so grounding, coverage and secret exclusion are configuration, not code.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: Added the `intent` section (answer-kind classification
#   thresholds and the cap on clarification questions per request) so no threshold is hard-coded
#   in the intake logic. (#KernelBootstrapV0/INTENT)
# - 2026-10-01 16:45 [python-coder]: A non-UTF-8 file is a ConfigError like bad JSON; the CLI
#   maps that to exit 5 with a JSON error instead of a traceback. (#KernelBootstrapV0/FIXC)
# - 2026-09-30 23:59 [python-coder]: Added jev.transport and limits.max_scheduler_iterations
#   (null = derive from the LangGraph recursion limit). (#KernelBootstrapV0/INT)
# - 2026-09-30 22:00 [python-coder]: Config models have no field defaults so the default JSON is
#   the only place a threshold value exists; max_cost_usd and price use null for unknown.
#   (#KernelBootstrapV0/P1)
# ====================================================================
