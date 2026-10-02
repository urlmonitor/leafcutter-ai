"""
MODULE: test_kernel_bridge
GOAL: Public kernel binding reaches the injected knowledge port with scoped evidence.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

import asyncio
from dataclasses import replace


def _run(
    tmp_path,
    status="ok",
    foreign=False,
    wrong_sha=False,
    wrong_request=False,
    max_chars=None,
    progressive=False,
    ambiguous=False,
):
    from knowledge.config import KnowledgeConfig
    from knowledge.contracts import (
        Entity,
        KnowledgeEvidence,
        KnowledgeRetrievalResult,
        SourceReference,
    )
    from kernel.bootstrap import build_bindings, load_snapshot
    from kernel.config import load_kernel_config
    from kernel.contracts.task import RevisionInfo
    from tests.kernel.helpers import make_context, make_invocation

    config = load_kernel_config().model_copy(
        update={"knowledge": KnowledgeConfig(repository_id="repo", repository_root=str(tmp_path))}
    )
    calls = []

    class FakePort:
        """Fakeport."""

        async def capabilities(self):
            """Capabilities."""
            return {"graph": True, "semantic": ambiguous, "hybrid": ambiguous}

        async def retrieve(self, request):
            """Retrieve."""
            calls.append(request)
            item = KnowledgeEvidence(
                entity=Entity(
                    canonical_id="KM-400a-1",
                    kind="AcceptanceCriterion",
                    title="Approved rule",
                    source=SourceReference(
                        repository_id="foreign" if foreign else "repo",
                        source_sha=("b" if wrong_sha else "a") * 40,
                        path="docs/ac.yaml",
                        locator="/criteria",
                    ),
                ),
                content=None
                if progressive and request.disclosure_level == 0
                else "  approved text\n",
                disclosure_level=request.disclosure_level,
            )
            return KnowledgeRetrievalResult(
                status=status,
                request_id="wrong" if wrong_request else request.request_id,
                retrieval_id="retrieval-test",
                source_sha="a" * 40,
                generation_id="gen-a",
                requested_mode=request.mode,
                executed_mode=request.mode,
                evidence=[item] if status == "ok" else [],
            )

    if progressive or ambiguous:
        from kernel.config import SourceConfig

        config = config.model_copy(
            update={
                "sources": [
                    SourceConfig(
                        id="knowledge.graph",
                        kind="graph_query",
                        categories=["prior_decisions", "task_context", "existing_patterns"],
                    )
                ]
            }
        )
    ctx = make_context(tmp_path, config=config)
    ctx = replace(
        ctx,
        scope=ctx.scope.model_copy(
            update={"revision": RevisionInfo(commit="a" * 40), "read_roots": ["docs"]}
        ),
    )
    invocation = make_invocation()
    payload = dict(invocation.input_payload)
    payload["knowledge"] = {
        "mode": "exact",
        "operation": "get_entities",
        "arguments": {"entity_ids": ["KM-400a-1"]},
        "disclosure_level": 3,
    }
    if max_chars is not None:
        payload["limits"] = {"max_chars": max_chars}
    if progressive or ambiguous:
        payload.pop("knowledge")
        payload["source_ids"] = ["knowledge.graph"]
        ctx = replace(
            ctx,
            scope=ctx.scope.model_copy(
                update={"component_ids": [] if ambiguous else ["knowledge_management"]}
            ),
        )
        if ambiguous:
            from kernel.providers.fakes import ScriptedJev, choice_answer

            jev = ScriptedJev().script(
                "knowledge.retrieval_mode", "knowledge.mode", choice_answer("hybrid")
            )
            ctx = replace(ctx, jev=jev)
    invocation = invocation.model_copy(update={"input_payload": payload})
    from kernel.config import repo_root

    bindings = build_bindings(load_snapshot(config, repo_root()), knowledge_retriever=FakePort())
    result = asyncio.run(bindings.resolve("retrieve.repository", "1.0.0").ainvoke(invocation, ctx))
    return result, calls, ctx


def test_registered_binding_consumes_scoped_fake_port(tmp_path):
    # angle: criterion
    # covers: KM-400e-3
    # angle: reachability
    """Test registered binding consumes scoped fake port."""
    result, calls, ctx = _run(tmp_path)
    assert len(calls) == 1
    assert calls[0].repository_id == "repo"
    assert calls[0].revision == "a" * 40
    assert len(result.evidence) == 1
    assert result.evidence[0].excerpt == "  approved text\n"
    assert result.evidence[0].source.source_version.commit == "a" * 40
    assert result.output_payload["evidence_ids"] == [result.evidence[0].id]
    assert result.diagnostics["knowledge_retrieval_id"] == "retrieval-test"
    assert ctx.budget.reserved["jev"] == 0
    assert any(call.name == "knowledge.retrieve" for call in ctx.tracer.calls)


def test_unavailable_backend_does_not_become_empty_success(tmp_path):
    # angle: criterion
    # covers: KM-400e-4
    # angle: failure
    """Test unavailable backend does not become empty success."""
    result, calls, _ = _run(tmp_path, status="unavailable")
    assert len(calls) == 1
    assert not result.evidence
    assert "unavailable" in result.output_payload["coverage"].values()
    assert result.output_payload["unavailable_sources"]
    assert result.status.value != "completed"


def test_foreign_backend_evidence_is_rejected_at_kernel_seam(tmp_path):
    # covers: KM-400a-5
    # covers: KM-400e-3
    # angle: boundary
    """Test foreign backend evidence is rejected at kernel seam."""
    result, _, _ = _run(tmp_path, foreign=True)
    assert not result.evidence
    assert result.status.value in {"failed", "blocked", "partial"}


def test_port_response_revision_must_match_published_result(tmp_path):
    # covers: KM-400a-5
    # angle: boundary
    """Test port response revision must match published result."""
    result, _, _ = _run(tmp_path, wrong_sha=True)
    assert not result.evidence
    assert result.status.value == "failed"


def test_port_response_must_belong_to_this_request(tmp_path):
    # covers: KM-400e-3
    # angle: boundary
    """Test port response must belong to this request."""
    result, _, _ = _run(tmp_path, wrong_request=True)
    assert not result.evidence
    assert result.status.value == "failed"


def test_small_caller_excerpt_cap_is_never_widened(tmp_path):
    # covers: KM-400d-4
    # angle: boundary
    """Test small caller excerpt cap is never widened."""
    result, _, _ = _run(tmp_path, max_chars=5)
    assert sum(len(item.excerpt or "") for item in result.evidence) <= 5
    assert result.output_payload["truncated"]


def test_registered_graph_request_progresses_from_discovery_to_selected_source(tmp_path):
    # covers: KM-400d-1
    # covers: KM-400e-3
    # angle: reachability
    """Test registered graph request progresses from discovery to selected source."""
    result, calls, _ = _run(tmp_path, progressive=True)
    assert len(calls) == 2
    assert calls[0].disclosure_level == 0
    assert calls[1].operation == "get_entities"
    assert calls[1].disclosure_level == 3
    assert calls[1].arguments["entity_ids"] == ["KM-400a-1"]
    assert calls[1].revision == calls[0].revision
    assert calls[1].budget.max_content_bytes < calls[0].budget.max_content_bytes
    assert result.evidence[0].excerpt == "  approved text\n"


def test_graph_conversion_preserves_relationship_and_correction_provenance():
    # covers: KM-400e-3
    """Test graph conversion preserves relationship and correction provenance."""
    from integrations.knowledge_capability import to_kernel_evidence
    from knowledge.contracts import Entity, KnowledgeEvidence, Relation, SourceReference

    source = SourceReference(repository_id="repo", source_sha="a" * 40, path="docs/decision.yaml")
    edge = Relation(source_id="new", target_id="old", edge_type="corrects", source=source)
    item = KnowledgeEvidence(
        entity=Entity(canonical_id="new", kind="Decision", title="Correction", source=source),
        disclosure_level=1,
        seed_id="old",
        path=[edge],
        relationships=[edge],
        related=[{"canonical_id": "old", "status": "corrected"}],
        signals={"vector_score": 0.8},
    )
    result = to_kernel_evidence(item, retrieval_id="retrieval")
    rendered = " ".join(result.limitations)
    assert "corrects" in rendered and "corrected" in rendered and "old" in rendered
    assert "a" * 40 in rendered and "vector_score" in rendered
    assert result.excerpt is None and result.provenance.relevance is None


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)


def test_ambiguous_registered_request_uses_existing_jev_once(tmp_path):
    """Ambiguous retrieval uses the existing budgeted decision port."""
    # angle: criterion
    # angle: reachability
    # covers: KM-400e-2
    result, calls, ctx = _run(tmp_path, ambiguous=True)
    assert ctx.jev.call_count == 1
    assert calls[0].mode == "hybrid"
    assert result.evidence
    assert result.diagnostics["knowledge_requested_mode"] == "hybrid"
    assert "Jev" in result.diagnostics["knowledge_reason"]
    assert result.diagnostics["knowledge_allowed_fallback"] == "none"
    assert "max_rounds" in result.diagnostics["knowledge_budget"]
    assert ctx.budget.reserved["jev"] == 1


def test_cumulative_followup_budget_retains_useful_discovery(tmp_path):
    """A token allowance smaller than another envelope stops instead of raising validation."""
    # covers: KM-400d-4
    from integrations.knowledge_followups import disclose_selected
    from knowledge.contracts import (
        Entity,
        KnowledgeEvidence,
        KnowledgeRetrievalRequest,
        KnowledgeRetrievalResult,
        SourceReference,
    )
    from tests.kernel.helpers import make_context

    request = KnowledgeRetrievalRequest(
        request_id="budget",
        repository_id="repo",
        operation="get_entities",
        arguments={"entity_ids": ["X"]},
        budget={"max_estimated_tokens": 256},
    )
    calls = []

    async def observe(port, current, ctx):
        calls.append(current)
        return KnowledgeRetrievalResult(
            request_id=current.request_id,
            retrieval_id="one",
            status="ok",
            requested_mode="exact",
            executed_mode="exact",
            source_sha="a" * 40,
            generation_id="gen",
            evidence=[
                KnowledgeEvidence(
                    entity=Entity(
                        canonical_id="X",
                        kind="ADR",
                        title="X",
                        source=SourceReference(
                            repository_id="repo", source_sha="a" * 40, path="docs/a.md"
                        ),
                    )
                )
            ],
        )

    _, result, _ = asyncio.run(
        disclose_selected(None, request, make_context(tmp_path), 3, observe, lambda *args: True)
    )
    assert len(calls) == 1 and result.evidence and result.truncated
    assert "budget" in " ".join(result.warnings)


def test_deadline_cancels_underlying_port_work(tmp_path):
    """A slow port is cancelled and reported unavailable at the actual adapter boundary."""
    # covers: KM-400d-4
    from integrations.knowledge_execution import _bounded_call
    from knowledge.contracts import KnowledgeRetrievalRequest
    from knowledge.errors import KnowledgeError
    from tests.kernel.helpers import make_context
    import pytest

    stopped = []

    class SlowPort:
        """Record cancellation of slow backend work."""

        async def retrieve(self, request):
            """Wait until cancelled by the request budget."""
            try:
                await asyncio.sleep(10)
            finally:
                stopped.append(True)

    request = KnowledgeRetrievalRequest(
        request_id="deadline",
        repository_id="repo",
        arguments={"entity_ids": ["X"]},
        budget={"deadline_ms": 1},
    )
    with pytest.raises(KnowledgeError, match="deadline"):
        asyncio.run(_bounded_call(SlowPort(), request, make_context(tmp_path)))
    assert stopped


def test_tracer_outage_preserves_retrieval_and_records_loss(tmp_path):
    """Trace export failure cannot turn useful retrieval into negative evidence."""
    # covers: KM-400e-4
    from integrations.knowledge_execution import _observed_call
    from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
    from tests.kernel.helpers import make_context

    class Tracer:
        """Reject trace creation like an unavailable telemetry exporter."""

        def span(self, *args, **kwargs):
            """Simulate a telemetry infrastructure outage."""
            raise OSError("offline")

    class Port:
        """Complete retrieval independently of telemetry."""

        async def retrieve(self, request):
            """Return successful no-match, not an outage."""
            return KnowledgeRetrievalResult(
                request_id=request.request_id,
                retrieval_id="trace-test",
                status="ok",
                requested_mode="exact",
                executed_mode="exact",
            )

    request = KnowledgeRetrievalRequest(
        request_id="trace", repository_id="repo", arguments={"entity_ids": ["X"]}
    )
    ctx = replace(make_context(tmp_path), tracer=Tracer())
    result = asyncio.run(_observed_call(Port(), request, ctx))
    assert result.status == "ok" and "telemetry unavailable" in result.warnings


def test_kernel_evidence_identity_stable_across_retrieval_runs():
    """Attribution is content-addressed while retrieval provenance remains run-specific."""
    # covers: KM-400d-5
    from integrations.knowledge_capability import to_kernel_evidence
    from knowledge.contracts import Entity, KnowledgeEvidence, SourceReference

    item = KnowledgeEvidence(
        entity=Entity(
            canonical_id="A",
            kind="ADR",
            title="A",
            source=SourceReference(repository_id="repo", source_sha="a" * 40, path="docs/a.md"),
        ),
        content="same source",
        disclosure_level=3,
    )
    first = to_kernel_evidence(item, retrieval_id="one")
    second = to_kernel_evidence(item, retrieval_id="two")
    assert first.id == second.id
    assert first.provenance.strategy != second.provenance.strategy
