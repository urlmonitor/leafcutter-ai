"""Real entity owners and registered bindings; only external graph/Jev ports are controlled."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from kernel.bootstrap import build_bindings, load_snapshot
from kernel.config import SourceConfig, repo_root
from kernel.contracts import schema_ids
from kernel.contracts.capability import Usage
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.task import RevisionInfo
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer
from knowledge.config import KnowledgeConfig
from knowledge.contracts import Entity, KnowledgeEvidence, KnowledgeRetrievalResult, SourceReference
from tests.kernel.capabilities.support import invocation
from tests.kernel.entity_context.support import AC_ID, build, config_for, recognize, write, write_frontmatter, write_repo
from tests.kernel.helpers import make_context
from tests.conftest import load_fixture

SHA = "a" * 40
ADR_ID = "ADR-012-retire-create-ticket-js"
GRAPH_FACT = "GRAPH_PORT_EVIDENCE_SENTINEL: the canonical record was read."
REPO_FACT = "NATIVE_REPOSITORY_SENTINEL: zephyr migration instructions are documented."


class RecordingKnowledgePort:
    """Neutral-port double with real typed results and independently recorded requests."""

    def __init__(self):
        self.calls = []
        self.status = "ok"
        self.capability_status = None
        self.failure = None
        self.foreign = False
        self.wrong_revision = False
        self.wrong_request = False
        self.empty = False
        self.capability_calls = 0
        self.response_entity = (AC_ID, "AcceptanceCriterion", "docs/acceptance-criteria/EC-1100a-1-i.yaml", "/criteria")

    async def capabilities(self):
        self.capability_calls += 1
        return {"graph": self.capability_status != "disabled", "semantic": False,
                "hybrid": False, "status": self.capability_status or "ready"}

    async def retrieve(self, request):
        self.calls.append(request)
        if self.failure is not None:
            raise self.failure
        identifier, kind, path, locator = self.response_entity
        source = SourceReference(repository_id="foreign" if self.foreign else "fixture",
                                 source_sha=("b" * 40 if self.wrong_revision else SHA),
                                 path=path, locator=locator)
        item = KnowledgeEvidence(entity=Entity(canonical_id=identifier, kind=kind,
                                 title="Independent graph record", source=source),
                                 content=GRAPH_FACT, disclosure_level=request.disclosure_level,
                                 field_locators={"content": locator})
        return KnowledgeRetrievalResult(request_id="wrong" if self.wrong_request else request.request_id,
            retrieval_id=f"recorded-{len(self.calls)}", source_sha=SHA, generation_id="published-a",
            status=self.status, requested_mode=request.mode, executed_mode=request.mode,
            evidence=[] if self.empty or self.status != "ok" else [item])


class SelectionRig:
    """Drive the real registration without importing the selector under test."""

    def __init__(self, root):
        self.root = root
        write_repo(root)
        write_frontmatter(root, f"docs/architecture/adrs/{ADR_ID}.md",
            {"title": "Retire the older ticket command", "type": "adr", "status": "active"},
            "# Architectural decision\n\nADR_TASK_BODY_SENTINEL\n")
        write(root, "docs/native-note.md", REPO_FACT + "\n")
        base = config_for()
        graph = SourceConfig(id="knowledge.graph", kind="graph_query", categories=["task_context"])
        self.config = base.model_copy(update={"sources": [*base.sources, graph],
            "knowledge": KnowledgeConfig(backend="neo4j", repository_id="fixture", repository_root=str(root))})
        build(root, self.config)
        self.port = RecordingKnowledgePort()
        self.jev = ScriptedJev(usage=Usage(provider="jev", model_id="controlled-selector", calls=1,
                                         input_tokens=17, output_tokens=3))
        self.choice = "get_entities"
        self.target = None
        self.probability, self.confidence = .99, .99
        self.jev.script("knowledge.operation_select", "operation", lambda q, b:
                        choice_answer(self.choice, self.probability, self.confidence))
        self.jev.script("knowledge.target_select", "target", lambda q, b:
                        choice_answer(self.target or "unoffered-target", .99, .99))
        self.jev.script("retrieval.rerank", "relevant.*", noul_answer(.99))

    def context(self, goal=AC_ID, *, components=(), caller=None):
        meanings = recognize(self.root, goal, config=self.config, context=caller)
        ctx = make_context(self.root, config=self.config, jev=self.jev)
        return replace(ctx, entity_context=meanings, scope=ctx.scope.model_copy(update={
            "component_ids": list(components), "revision": RevisionInfo(commit=SHA)}))

    def request(self, goal, *, source_ids=None, **kwargs):
        need = EvidenceNeed(id="selected.need", category="task_context", question=goal)
        payload = RetrievalRequestPayload(need=need,
            source_ids=["knowledge.graph"] if source_ids is None else source_ids, **kwargs)
        return invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload.model_dump(mode="json"))

    def run(self, goal=AC_ID, *, context=None, source_ids=None, **kwargs):
        ctx = context or self.context(goal)
        request = self.request(goal, source_ids=source_ids, **kwargs)
        bindings = build_bindings(load_snapshot(ctx.config, repo_root()), knowledge_retriever=self.port)
        result = asyncio.run(bindings.resolve("retrieve.repository", "1.0.0").ainvoke(request, ctx))
        return result, ctx, request

    def operation_batches(self):
        return [b for b in self.jev.batches if b.purpose == "knowledge.operation_select"]


class FiniteBudget:
    """Count actual reservations without resetting the requester's remaining allowance."""

    def __init__(self, remaining):
        self.remaining = remaining
        self.reservations = 0

    def available(self, resource):
        return self.remaining if resource == "jev" else None

    def reserve(self, resource):
        if resource != "jev":
            return True
        if self.remaining == 0:
            return False
        self.remaining -= 1
        self.reservations += 1
        return True


class PopulationKnowledgePort:
    """Actual knowledge policy/service with only immutable storage and source IO controlled."""

    def __init__(self, root):
        from knowledge.contracts import ProjectionSnapshot
        from knowledge.service import KnowledgeService

        self.root, self.calls, self.results, self.storage_calls = root, [], [], []
        self.source_reads = []
        self.nodes = []
        template = load_fixture("entity_context/owners")["yaml"]["docs/acceptance-criteria/EC-1100a-1-i.yaml"]
        for row in load_fixture("entity_graph_selection/cases")["population_nodes"]:
            ident = row["id"]
            path = f"docs/acceptance-criteria/{ident}.yaml"
            write(root, path, {**template, "id": ident, "level": row["level"],
                              "criteria": f"Then {ident} population fixture clause.", "depends_on": row["depends_on"]})
            source = SourceReference(repository_id="fixture", source_sha=SHA, path=path, locator="/criteria")
            self.nodes.append(Entity(canonical_id=ident, kind="AcceptanceCriterion", title=ident, source=source,
                properties={"level": row["level"], "structural_parent": row["parent"],
                            "has_children": row["has_children"], "depends_on": row["depends_on"]}))
        self.snapshot = ProjectionSnapshot(repository_id="fixture", source_sha=SHA, generation_id="pop-fixture",
            nodes=self.nodes, supported_kinds=["AcceptanceCriterion"],
            supported_fields={"AcceptanceCriterion": ["structural_parent", "has_children", "depends_on"]})
        self.service = KnowledgeService(self, source_resolver=self, cursor_secret=b"population-test-only")

    async def capabilities(self):
        return {"graph": True, "semantic": False, "hybrid": False, "status": "ready"}

    async def active(self, repository_id):
        return self.snapshot if repository_id == "fixture" else None

    async def get_generation(self, repository_id, generation_id):
        return self.snapshot if repository_id == "fixture" and generation_id == "pop-fixture" else None

    async def query(self, repository_id, generation_id, operation, arguments, limit):
        assert repository_id == "fixture" and generation_id == "pop-fixture"
        self.storage_calls.append((operation, arguments))
        ids = arguments["entity_ids"]
        if operation == "get_entities":
            rows = [node for node in self.nodes if node.canonical_id in ids]
        elif operation == "_get_ac_children":
            rows = [node for node in self.nodes if node.properties["structural_parent"] in ids]
        elif operation == "get_declared_dependents":
            rows = [node for node in self.nodes if set(ids) & set(node.properties["depends_on"])]
        else:
            raise AssertionError(f"unexpected storage operation {operation}")
        return rows[:limit]

    async def neighbors(self, *args):
        return [], []

    async def read(self, reference, max_bytes):
        from knowledge.adapters.source_excerpt import excerpt

        self.source_reads.append(reference.path)
        payload = (self.root / reference.path).read_bytes()
        return excerpt(payload, reference.locator)[:max_bytes].decode("utf-8")

    async def retrieve(self, request):
        self.calls.append(request)
        result = await self.service.retrieve(request)
        self.results.append(result)
        return result


def _choices(batch, question="operation"):
    return next(q.criteria for q in batch.questions if q.id == question)


def _detail(result):
    return str(result.model_dump(mode="json")).lower()
