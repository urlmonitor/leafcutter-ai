"""MODULE: retrieval_needs_llm
GOAL: Run the isolated host interpreter through the real kernel wait/resume lifecycle.
BUSINESS CONTEXT: Compare LLM interpretation with the frozen Jev experiment honestly.
ARCHITECTURE: Experiment-only environment/snapshot; no production registry or provider client.
"""
from __future__ import annotations

from pathlib import Path

from kernel.bootstrap import KernelEnvironment, build_bindings
from kernel.config import KernelConfig, load_kernel_config
from kernel.contracts import Actor, CapabilityDescriptor, RegistrySnapshot, Scope, TaskInput, schema_ids
from kernel.contracts.base import canonical_json, fail, sha256_hex
from kernel.contracts.retrieval_needs import RetrievalNeedsRequest, prepare_request
from kernel.observability.redaction import Redactor
from kernel.observability.tracer import NoOpTracer
from kernel.persistence import FileArtifactStore, FileGapStore, FileRunStore
from kernel.providers.base import JevBatch, JevResult, JevUnavailable
from kernel.secrets import SecretSettings
from kernel.service import KernelService


class _ForbiddenJev:
    """Satisfy the kernel port dependency while refusing any unexpected classifier call."""

    async def assess(self, batch: JevBatch) -> JevResult:
        """Fail explicitly: the fixed host-only experiment must make zero Jev calls."""
        raise JevUnavailable("Jev calls are disabled in the isolated host-needs experiment")


def experiment_snapshot() -> RegistrySnapshot:
    """Construct only the explicitly requested experiment registration, never approval."""
    descriptor = CapabilityDescriptor.model_validate({
        "id": "host.retrieval_needs", "name": "Experimental host needs interpretation",
        "description": "User-requested isolated host interpreter experiment; no classifier promotion or production admission.",
        "version": "1.0.0", "request_kinds": ["capability"],
        "operations": ["interpret_retrieval_needs"],
        "accepts_schemas": [schema_ids.RETRIEVAL_NEEDS_REQUEST],
        "produces_schemas": [schema_ids.RETRIEVAL_NEEDS_OUTPUT],
        "execution_mode": "host_handoff", "binding": "host.retrieval_needs",
        "side_effect_class": "run_artifacts", "permissions_required": [], "routing": "fixed",
        "availability": {"status": "experimental", "reason": "Isolated user-requested experiment only"},
        "cost_hints": {"jev_calls": 0, "host_operations": 1},
        "admission": {"kind": "native_registration", "decision_ref": "ADR-053",
                      "admitted_on": "2026-10-03", "admitted_by": "experiment-harness:user-requested"},
    })
    digest = sha256_hex(canonical_json(descriptor.model_dump(mode="json")))
    return RegistrySnapshot(registry_id="experiment.retrieval-needs", registry_version=1,
        content_hash=digest, source_path="experiment-only:no-production-registry", descriptors=[descriptor])


def _config(root: Path, run_root: Path) -> KernelConfig:
    """Disable external reads and exports while preserving the actual host input content."""
    body = load_kernel_config(default_path=root / "config/kernel_config.default.json", env={}).model_dump(mode="json")
    body["paths"]["run_root"] = str(run_root.resolve())
    body["context_enrichment"]["enabled"] = False
    body["context_enrichment"]["source_ids"] = []
    body["knowledge"]["backend"] = "none"
    body["memory"]["backend"] = "null"
    body["langfuse"]["enabled"] = False
    body["host"].update(enabled=True, fallback_on_no_match=False, formulate_questions=False, max_input_chars=50000)
    body["limits"].update(max_jev_calls=0, max_host_operations=1, max_retries=0)
    body["data_policy"].update(telemetry_excerpts="truncated", telemetry_max_field_chars=10000)
    return KernelConfig.model_validate(body)


def make_experiment_service(root: Path, run_root: Path) -> KernelService:
    """Compose a real local kernel service without credentials, source reads or LLM clients.

    Run artifacts/checkpoints are written only under the caller-supplied run_root.
    The caller executes host work from the packet and closes service._env afterwards.
    """
    root, run_root = root.resolve(), run_root.resolve()
    config = _config(root, run_root)
    snapshot = experiment_snapshot()
    env = KernelEnvironment(config=config, secrets=SecretSettings(), snapshot=snapshot,
        bindings=build_bindings(snapshot), repo_root=root, run_root=run_root,
        run_store=FileRunStore(run_root), gap_store=FileGapStore(run_root),
        artifacts=FileArtifactStore(run_root), tracer=NoOpTracer(),
        redactor=Redactor({}, config.data_policy, config.retrieval.deny_globs), jev_factory=_ForbiddenJev)
    return KernelService(env)


def build_llm_needs_task(request: RetrievalNeedsRequest, scope: Scope, caller: Actor) -> TaskInput:
    """Build the typed root with literal candidates and zero repository-read permission."""
    prepared = prepare_request(RetrievalNeedsRequest.model_validate(request.model_dump(mode="json")))
    body = prepared.model_dump(mode="json")
    if len(canonical_json(body)) > 50000:
        fail("The bounded host-needs input exceeds 50000 characters")
    return TaskInput(goal=prepared.original_question, caller=caller, scope=scope, permissions=[],
        input_payload_schema=schema_ids.RETRIEVAL_NEEDS_REQUEST, input_payload=body,
        requested_output_schema=schema_ids.RETRIEVAL_NEEDS_OUTPUT)


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 00:00 [python-coder]: Use the existing kernel graph and durable host ledger in an isolated environment. (#TICKETLESS reason=user-requested-isolated-host-experiment)
