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


class DecisionConfig(_Section):
    """Decision-graph thresholds."""

    sufficiency_threshold: Probability
    satisfies_threshold: Probability
    preference_threshold: Probability
    conflict_threshold: Probability
    missing_min_probability: Probability


class ResearchConfig(_Section):
    """Research-graph thresholds and category descriptions offered to Jev."""

    need_required_threshold: Probability
    need_supporting_threshold: Probability
    evaluable_threshold: Probability
    allow_synthesis: bool
    category_descriptions: dict[EvidenceCategory, str]

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


class SourceConfig(_Section):
    """One entry of the source catalog (where evidence may come from)."""

    id: str
    kind: Literal["repo_text", "knowledge_map", "host_research"]
    categories: list[EvidenceCategory] = Field(min_length=1)
    roots: list[str] = Field(default_factory=list)
    surfaces: list[str] = Field(default_factory=list)


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
    decision: DecisionConfig
    research: ResearchConfig
    retrieval: RetrievalConfig
    sources: list[SourceConfig]
    jev: JevConfig
    host: HostConfig
    data_policy: DataPolicyConfig
    langfuse: LangfuseConfig

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
# - 2026-09-30 23:59 [python-coder]: Added jev.transport and limits.max_scheduler_iterations
#   (null = derive from the LangGraph recursion limit). (#KernelBootstrapV0/INT)
# - 2026-09-30 22:00 [python-coder]: Config models have no field defaults so the default JSON is
#   the only place a threshold value exists; max_cost_usd and price use null for unknown.
#   (#KernelBootstrapV0/P1)
# ====================================================================
