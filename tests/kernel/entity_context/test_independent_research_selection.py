"""Evaluator regression: indexing an artifact must not add it to automatic precedent search."""
import asyncio
from dataclasses import replace

import pytest

from kernel.capabilities.research.planning import resolve_sources
from kernel.capabilities.research.state import Plan
from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.entity_context import recognize_entities
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation
from tests.kernel.entity_context.support import build, task_for, write_repo
from tests.kernel.helpers import make_context


@pytest.mark.parametrize("source_id,identity,sentinel", [
    ("repo.native_decisions", "dec-0123456789abcdef", "DECISION_BODY_SENTINEL"),
    ("repo.flows", "eval/meaning", '"source": "eval"'),
])
def test_indexed_artifact_sources_require_explicit_research_selection(tmp_path, source_id, identity, sentinel):
    # covers: DK-300d-3
    # Regression baseline: full kernel run exposed lookalike precedent expansion.
    write_repo(tmp_path)
    defaults = load_kernel_config()
    source = next(s for s in defaults.sources if s.id == source_id)
    assert source.automatic_research is False
    category = source.categories[0]
    ordinary = SourceConfig(id="ordinary", kind="repo_text", categories=[category], roots=["docs/glossary.md"])
    owners = SourceConfig(id="owner_config", kind="repo_text", categories=["task_context"],
                          roots=["config", "docs/components.json", "docs/roadmap.json"])
    config = defaults.model_copy(update={"sources": [ordinary, owners, source],
        "entity_context": defaults.entity_context.model_copy(update={"source_ids": []})})
    build(tmp_path, config)
    meanings = recognize_entities(task_for(tmp_path, identity), config)
    assert any(card.identity == identity and card.provenance.source_id == source_id for card in meanings.entities)
    jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(.95))
    ctx = make_context(tmp_path, config=config, jev=jev)
    question = "Explain " + identity + " and " + sentinel
    need = EvidenceNeed(id="needed", category=category, question=question)
    automatic = Plan(question, "bounded", [need], [])
    base = resolve_sources(ctx, [need], automatic)
    assert base.requests and all(source_id not in request.payload["source_ids"] for request in base.requests)
    automatic_payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
    automatic_inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, automatic_payload)
    automatic_result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(automatic_inv, ctx))
    assert all(item.source.id != source_id for item in automatic_result.evidence)
    restricted = Plan(question, "bounded", [need], [source_id])
    explicit = resolve_sources(ctx, [need], restricted)
    hinted = resolve_sources(replace(ctx, entity_context=meanings), [need], automatic)
    for result in (explicit, hinted):
        assert any(source_id in request.payload["source_ids"] for request in result.requests)
        bodies = []
        for request in result.requests:
            inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, request.payload)
            retrieved = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
            bodies.extend(item.excerpt for item in retrieved.evidence)
        assert any(sentinel in body for body in bodies), {"requests": [r.payload for r in result.requests], "bodies": bodies}
    denied_source = source.model_copy(update={"deny_globs": ["**/*"]})
    denied_config = config.model_copy(update={"sources": [ordinary, owners, denied_source]})
    denied_ctx = replace(ctx, config=denied_config, entity_context=meanings)
    denied = resolve_sources(denied_ctx, [need], automatic)
    assert all(source_id not in request.payload["source_ids"] for request in denied.requests)
    assert all(not request.payload["explicit_locators"] for request in denied.requests)
