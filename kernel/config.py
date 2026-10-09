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

from pydantic import ValidationError, model_validator

from integrations.knowledge_config import KnowledgeBindingConfig
from kernel.config_context import ContextEnrichmentConfig
from kernel.config_entity import EntityContextConfig
from kernel.config_memory import MemoryConfig
from kernel.config_retrieval import RetrievalConfig
from kernel.config_sections import (
    DataPolicyConfig,
    DecisionConfig,
    HostConfig,
    IntentConfig,
    JevConfig,
    LangfuseConfig,
    LimitsConfig,
    PathsConfig,
    ResearchConfig,
    RoutingConfig,
    SourceConfig,
    _Section,
)
from kernel.contracts.base import fail

logger = logging.getLogger(__name__)

CONFIG_ENV_VAR = "LEAFCUTTER_KERNEL_CONFIG"
DEFAULT_CONFIG_NAME = "kernel_config.default.json"
SCHEMA_CONFIG_NAME = "kernel_config.schema.json"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


class ConfigError(Exception):
    """The kernel configuration could not be read or failed validation."""

    def __init__(self, source: Path | str, detail: str) -> None:
        """Build the message from the config source and detail.

        Args:
            source: Configured evidence source or failing configuration path.
            detail: Human-readable failure detail.
        """
        super().__init__(f"invalid kernel config {source}: {detail}")
        self.source = str(source)
        self.detail = detail


class KernelConfig(_Section):
    """Complete kernel configuration."""

    knowledge: KnowledgeBindingConfig
    """How optional knowledge retrieval is bound to the kernel."""
    paths: PathsConfig
    """Where run state and the capability registry live."""
    limits: LimitsConfig
    """Bounds on how much a run may do."""
    routing: RoutingConfig
    """Thresholds for choosing a capability."""
    intent: IntentConfig
    """Thresholds for classifying what the caller asked for."""
    context_enrichment: ContextEnrichmentConfig
    """Bounds of the initial context pass."""
    entity_context: EntityContextConfig
    """Bounds of entity recognition on the caller's text."""
    decision: DecisionConfig
    """Thresholds that turn Jev's probabilities into decision outcomes."""
    research: ResearchConfig
    """Thresholds and category meanings for planning research."""
    retrieval: RetrievalConfig
    """Bounds and ranking settings for repository retrieval."""
    sources: list[SourceConfig]
    """The catalog of places evidence may come from."""
    jev: JevConfig
    """Settings of the Jev provider."""
    host: HostConfig
    """Settings for handing work to the host client."""
    data_policy: DataPolicyConfig
    """What may leave the process in Jev calls and telemetry."""
    langfuse: LangfuseConfig
    """Settings for exporting traces."""
    memory: MemoryConfig
    """Decision store and precedent lookup settings."""

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
    """Read a JSON object from path, raising ConfigError on IO or parse problems.

    Args:
        path: Configuration file path.

    Returns:
        dict: Result of the documented operation.
    """
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
    """Return base with override merged in; nested objects merge, everything else replaces.

    Args:
        base: Default configuration object.
        override: Configuration overrides to merge.

    Returns:
        dict: Result of the documented operation.
    """
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

    Keyword options: env supplies an environment mapping (default os.environ);
    default_path selects an alternative defaults file for tests.

    Args:
        override: Override file; falls back to the LEAFCUTTER_KERNEL_CONFIG env var.

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
# - 2026-10-09 [python-coder]: The section models moved to config_sections.py and
#   config_retrieval.py (re-exported here) to fit the file-size limit after field purposes were
#   added; the committed config schema carries them.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-02 [python-coder]: research.max_claim_needs (25); max_targeted_needs caps gaps only.
#   (#KernelResearchEveryAddedOption)
# - 2026-10-01 [python-coder]: The `memory` section (backend, precedent thresholds) lives in
#   kernel/config_memory.py because this file is at the size limit. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: Round F: ordering, pool, rerank depth, review limits. (#KernelV01/F)
# - 2026-10-01 [python-coder]: Round E: decision.reserve_* keep Jev budget for a final assessment,
#   retrieval.rerank_max_per_need bounds the rerank batch per need, satisfied_* and self_reference_*
#   tighten coverage and demote reviews of the asking run, path_match_weight weighs path matches
#   against content hits; research.max_targeted_needs is 2. (#KernelV01/E)
# - 2026-10-01 [python-coder]: Added decision.design_judgement_threshold, progress_epsilon and
#   max_research_rounds so the design-decision ending is configuration. (#KernelV01/A)
# - 2026-10-01 23:00 [python-coder]: Added decision.require_option_grounding, max_grounding_evidence,
#   retrieval.coverage_relevance_threshold and per-source deny_globs. (#KernelBootstrapV0/GROUND)
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

# - 2026-10-01 20:00 [python-coder]: Bind optional knowledge through existing scoped retrieval contracts. (#TICKET-20261001-KM-400e-3)

# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Separate catalog permission from automatic research eligibility so meaning owners do not bypass precedent filtering. (#DK-300/entity-context)
