"""
MODULE: tests.kernel.helpers
GOAL: Shared builders and doubles for the kernel tests: fixture loading, descriptors, evidence,
    invocations, a scripted capability executor and a fully faked ExecutionContext.
BUSINESS CONTEXT: Every kernel phase tests against the same ports with the same doubles, so the
    scheduler, graphs and adapters can be exercised offline and deterministically.
ARCHITECTURE: Imported explicitly (no conftest). Builders return real contract models, never
    mocks, so contract validators run in every test that uses them.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

from kernel.capabilities.base import ExecutionContext, UnlimitedBudget
from kernel.config import KernelConfig, load_kernel_config
from kernel.contracts.base import CorrelationIds, content_hash, evidence_id, new_id, utc_now
from kernel.contracts.capability import CapabilityDescriptor, CapabilityResult
from kernel.contracts.enums import RequestKind, ResultStatus
from kernel.contracts.evidence import Evidence
from kernel.contracts.task import Scope
from kernel.contracts.work import CapabilityInvocation, RequestBody
from kernel.observability.tracer import RecordingTracer
from kernel.persistence.memory import MemoryArtifactStore
from kernel.providers.fakes import ScriptedJev

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json(relative: str) -> dict:
    """Load a JSON fixture below tests/kernel/fixtures."""
    return json.loads((FIXTURES_DIR / relative).read_text(encoding="utf-8"))


def make_descriptor(**overrides: object) -> CapabilityDescriptor:
    """Return the native retrieval descriptor fixture with field overrides applied."""
    data = load_json("registry/descriptor_native.json")
    data.update(overrides)
    return CapabilityDescriptor.model_validate(data)


def make_scope(root: Path, **overrides: object) -> Scope:
    """Return a Scope rooted at `root`."""
    return Scope(workspace_id="ws", repository_root=str(root), **overrides)


def make_evidence(locator: str = "docs/a.md#L1-L2", excerpt: str = "Use sqlite.") -> Evidence:
    """Return a valid, content-addressed Evidence item."""
    digest = content_hash(excerpt)
    return Evidence(
        id=evidence_id(locator, digest), category="prior_decisions",
        semantic_type="repository_fact", excerpt=excerpt, content_hash=digest,
        source={"id": "repo.decisions", "kind": "repository_file", "locator": locator},
        provenance={"producer": "test"},
    )


def make_request_body(kind: RequestKind = RequestKind.EVIDENCE,
                      payload_schema: str = "leafcutter.retrieval_request.v1",
                      output_schema: str = "leafcutter.evidence_bundle.v1",
                      payload: dict | None = None) -> RequestBody:
    """Return a RequestBody; defaults describe a retrieval request."""
    body = payload if payload is not None else load_json(
        f"valid/{payload_schema}/valid_basic.json")
    return RequestBody(kind=kind, goal="goal", payload_schema=payload_schema, payload=body,
                       requested_output_schema=output_schema)


def make_invocation(capability_id: str = "retrieve.repository",
                    version: str = "1.0.0") -> CapabilityInvocation:
    """Return a CapabilityInvocation with a retrieval payload."""
    return CapabilityInvocation(
        id=new_id("inv"), work_item_id=new_id("work"), capability_id=capability_id,
        capability_version=version, input_payload_schema="leafcutter.retrieval_request.v1",
        input_payload=load_json("valid/leafcutter.retrieval_request.v1/valid_basic.json"),
        input_fingerprint="fp-0001", created_at=utc_now())


def completed_result(invocation: CapabilityInvocation) -> CapabilityResult:
    """Return a minimal completed result for the invocation."""
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.COMPLETED, output_schema_id="leafcutter.evidence_bundle.v1",
        output_payload={})


class ScriptedExecutor:
    """CapabilityExecutor double: returns the next scripted result (or builds one)."""

    def __init__(self, results: Sequence[CapabilityResult] | None = None,
                 factory: Callable[[CapabilityInvocation], CapabilityResult] | None = None
                 ) -> None:
        """Script results in order, or give a factory that builds one per invocation."""
        self._results = list(results or [])
        self._factory = factory or completed_result
        self.invocations: list[CapabilityInvocation] = []
        self.contexts: list[ExecutionContext] = []

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: ExecutionContext
                      ) -> CapabilityResult:
        """Record the call and return the next scripted result."""
        self.invocations.append(invocation)
        self.contexts.append(ctx)
        if self._results:
            return self._results.pop(0)
        return self._factory(invocation)


def make_context(root: Path, *, jev: ScriptedJev | None = None,
                 evidence: Sequence[Evidence] = (), config: KernelConfig | None = None,
                 cancelled: bool = False) -> ExecutionContext:
    """Return an ExecutionContext wired to doubles (scripted Jev, recording tracer, memory)."""
    known = {e.id: e for e in evidence}

    def lookup(ids: Sequence[str]) -> list[Evidence]:
        """Return known evidence for ids in order, skipping unknown ids."""
        return [known[i] for i in ids if i in known]

    return ExecutionContext(
        run_id=new_id("run"), scope=make_scope(root), config=config or load_kernel_config(),
        jev=jev or ScriptedJev(), tracer=RecordingTracer(), corr=CorrelationIds(),
        artifacts=MemoryArtifactStore(), budget=UnlimitedBudget(), evidence_lookup=lookup,
        clock=utc_now, cancel_probe=lambda: cancelled)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Builders return real contract models so validators run in
#   every test; fixtures hold the larger dicts (tests README fixture convention).
#   (#KernelBootstrapV0/P1)
# ====================================================================
