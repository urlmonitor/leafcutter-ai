"""DK-300d-5: explicit reads, native fallback and unsupported population completeness."""

import asyncio
from dataclasses import replace

import pytest

from kernel.bootstrap import build_bindings, load_snapshot
from kernel.capabilities.research import ResearchExecutor
from kernel.config import SourceConfig, repo_root
from kernel.contracts import schema_ids
from kernel.contracts.enums import NeedStatus, RequestKind
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import ResearchRequestPayload
from tests.conftest import load_fixture
from tests.kernel.capabilities.support import child, invocation, resume, script_research
from tests.kernel.entity_context.graph_selection_support import (
    ADR_ID, GRAPH_FACT, REPO_FACT, _choices, _detail,
)
from tests.kernel.entity_context.support import AC_ID, write

CASES = load_fixture("entity_graph_selection/cases")


@pytest.mark.parametrize("reference", ["", " tickets/TICKET-EC-1100.md", " " + AC_ID])
def test_ticket_priority_enumeration_is_never_offered_as_graph_supported(selection, reference):
    # covers: DK-300d-5-i
    # angle: discrimination
    goal = "List ALL tickets with high or critical priority, not a sample." + reference
    selection.choice = "unsupported"
    result, _, _ = selection.run(goal)
    assert not selection.port.calls, "an incidental recognized identity is not the requested Ticket population"
    assert result.status.value != "completed"
    assert "unsupported" in _detail(result)
    assert not result.requests, "an unsupported population cannot trigger query construction or admission"
    assert all("priority" not in operation for batch in selection.operation_batches() for operation in _choices(batch))
    if reference:
        assert len(selection.operation_batches()) == 1, "Jev must assess question fit despite an incidental exact target"


@pytest.mark.parametrize("mode", ["exact", "hybrid"])
def test_explicit_graph_request_bypasses_operation_selection(selection, mode):
    # covers: DK-300d-5
    # angle: seam
    explicit = {"mode": "exact", "operation": "get_entities", "arguments": {"entity_ids": [AC_ID]},
                "disclosure_level": 3}
    if mode == "hybrid":
        explicit.update(mode="hybrid", operation="find_similar_decisions", arguments={"query_text": "storage precedent"})
    selection.choice = "execute_arbitrary_cypher"
    result, _, _ = selection.run(ADR_ID, knowledge=explicit)
    assert selection.jev.call_count == 0
    assert len(selection.port.calls) == 1
    assert selection.port.calls[0].arguments == explicit["arguments"]
    assert selection.port.calls[0].operation == explicit["operation"]
    assert selection.port.calls[0].mode == mode
    assert selection.port.calls[0].disclosure_level == 3
    assert any(item.excerpt == GRAPH_FACT for item in result.evidence)
    assert not result.usage


@pytest.mark.parametrize("permitted", [True, False])
def test_repository_fallback_executes_native_retrieval_with_same_scope(selection, permitted):
    # covers: DK-300d-5
    # angle: reachability
    goal = "Find the zephyr migration instructions for " + AC_ID
    write(selection.root, "forbidden/note.md", "FORBIDDEN_NATIVE_SENTINEL zephyr migration instructions")
    allowed = SourceConfig(id="repo.allowed", kind="repo_text", categories=["task_context"],
                           roots=["docs/native-note.md"])
    forbidden = allowed.model_copy(update={"id": "repo.forbidden", "roots": ["forbidden"]})
    ctx = selection.context(goal)
    sources = [*ctx.config.sources, allowed, forbidden]
    requested = ["knowledge.graph", "repo.allowed"]
    ctx = replace(ctx, config=ctx.config.model_copy(update={"sources": sources}),
                  scope=ctx.scope.model_copy(update={"source_ids": requested if permitted else ["knowledge.graph"]}))
    selection.choice = "repository_fallback"
    result, _, _ = selection.run(goal, context=ctx, source_ids=requested)
    batches = selection.operation_batches()
    assert len(batches) == 1
    assert ("repository_fallback" in _choices(batches[0])) == permitted
    assert not selection.port.calls
    if permitted:
        assert any(REPO_FACT in (item.excerpt or "") for item in result.evidence)
        assert all("forbidden" not in item.source.locator for item in result.evidence)
        assert any(goal in str(batch.state) for batch in selection.jev.batches if batch.purpose == "retrieval.rerank")
        assert sum(u.calls for u in result.usage) == selection.jev.call_count
    else:
        assert not result.evidence and result.status.value != "completed"
        assert not any(batch.purpose == "retrieval.rerank" for batch in selection.jev.batches)


@pytest.mark.parametrize("mode", CASES["ordinary_modes"])
def test_ordinary_repository_request_keeps_legacy_path(selection, mode):
    # covers: DK-300d-5
    # angle: boundary
    goal = "Find zephyr migration instructions"
    ctx = selection.context(goal)
    if mode == "disabled":
        ctx = replace(ctx, config=ctx.config.model_copy(update={
            "knowledge": ctx.config.knowledge.model_copy(update={"backend": "none"})}))
        selection.port.capability_status = "disabled"
    elif mode == "unavailable":
        selection.port.capability_status = "unavailable"
    if mode == "empty_graph":
        selection.port.empty = True
        explicit = {"mode": "exact", "operation": "get_entities", "arguments": {"entity_ids": [AC_ID]}}
        empty, _, _ = selection.run(context=ctx, knowledge=explicit)
        selection.port.status = "unavailable"
        unavailable, _, _ = selection.run(context=ctx, knowledge=explicit)
        assert empty.status.value == "completed" and not empty.evidence
        assert unavailable.status.value != "completed" and "unavailable" in _detail(unavailable)
    else:
        result, _, _ = selection.run(goal, context=ctx, source_ids=["eval.entities"])
        assert any(REPO_FACT in (item.excerpt or "") for item in result.evidence)
        assert not selection.port.calls
    assert not selection.operation_batches()


@pytest.mark.parametrize("graph_first", [True, False])
def test_ticket_completeness_limitation_survives_sibling_merge_and_resume(selection, graph_first):
    # covers: DK-300d-5-i
    # angle: seam
    goal = "Which tickets have high or critical priority? List all matching tickets. Context: " + AC_ID
    selection.choice = "unsupported_population"
    ctx = selection.context(goal)
    script_research(selection.jev, {"evaluable": .99, "answer": .99})
    need = EvidenceNeed(id="need.population", category="task_context", question=goal, priority="required")
    body = ResearchRequestPayload(question=goal, evidence_needs=[need], evidence_needs_only=True)
    parent = invocation("research", schema_ids.RESEARCH_REQUEST, body.model_dump(mode="json"))
    research = ResearchExecutor()
    planned = asyncio.run(research.ainvoke(parent, ctx))
    assert len(planned.requests) == 2, "the actual planner must retain graph and native siblings"
    binding = build_bindings(load_snapshot(ctx.config, repo_root()), knowledge_retriever=selection.port)
    children = []
    for request in planned.requests:
        current = invocation("retrieve.repository", request.payload_schema, request.payload)
        result = asyncio.run(binding.resolve("retrieve.repository", "1.0.0").ainvoke(current, ctx))
        is_graph = "knowledge.graph" in request.payload["source_ids"]
        if is_graph:
            assert not result.evidence and "unsupported" in _detail(result)
        else:
            assert result.evidence, "the completeness guard must face a genuinely useful native sibling"
            assert result.output_payload["coverage"][need.id] == "satisfied"
        children.append((is_graph, child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                                         result.output_payload, status=result.status)))
    ordered = [outcome for _, outcome in sorted(children, key=lambda pair: pair[0], reverse=graph_first)]
    collected = asyncio.run(research.ainvoke(resume(parent, planned, ordered), ctx))
    assert collected.status.value != "completed", "ranked sibling hits cannot establish an exhaustive population"
    if collected.status.value == "waiting":
        assert collected.continuation_state["coverage"][need.id] != NeedStatus.SATISFIED.value
        synthesis = child(ctx, RequestKind.SYNTHESIS, schema_ids.FINDINGS,
                          {"findings": [], "unknowns": [], "disagreements": []})
        collected = asyncio.run(research.ainvoke(resume(parent, collected, [*ordered, synthesis]), ctx))
    assert collected.status.value == "partial"
    assert collected.output_payload["coverage"][need.id] != "satisfied"
    assert any(term in _detail(collected) for term in ("unsupported", "exhaustive", "completeness"))
    assert collected.evidence, "retain useful bounded evidence while refusing the completeness claim"
    assert not selection.port.calls
