"""Real public kernel/source composition for needs integration acceptance.

Only Jev answers, the cooperating host, and database storage are controlled.
The needs packet, durable host ledger, source projection, disclosure and answer
assessment are production code. Expected answers are never fed to retrieval.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput, schema_ids
from kernel.contracts.task import RevisionInfo
from kernel.providers.fakes import choice_answer
from knowledge.adapters.git_source import GitSourceResolver
from knowledge.config import KnowledgeConfig
from knowledge.errors import BackendUnavailable
from knowledge.query_admission import QueryAdmission
from knowledge.query_catalog import QueryCatalog
from knowledge.service import KnowledgeService
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import ScenarioCase
from tests.kernel.interaction.support import raw_submission

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "public-needs-acceptance"
DIMENSIONS = ("entity_types", "target_ids", "required_fields", "document_types", "relationships")


@lru_cache(maxsize=1)
def source_snapshot():
    """Map a bounded immutable source subset; global publication is tested separately."""
    import yaml
    from knowledge.contracts import ProjectionSnapshot
    from knowledge.projection.canonical_loader import _entity
    from knowledge.projection.answer_fields import mapped_fields, structural_parent
    from scripts.knowledge_query import NodeRecord

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", revision,
                                    "docs/acceptance-criteria"], cwd=ROOT, text=True).splitlines()
    paths = [path for path in paths if Path(path).stem.startswith("TQ-500f")
             or Path(path).stem in {"KM-500c-1", "KM-500c-2"}]
    with tempfile.TemporaryDirectory(prefix="public-needs-source-") as directory:
        root = Path(directory)
        records = {}
        for path in paths:
            data = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            record = yaml.safe_load(data)
            records[record["id"]] = record
        parents = {structural_parent(record) for record in records.values()}
        nodes = [_entity(NodeRecord(Path(path).stem, "acs", records[Path(path).stem]["title"], "", Path(path)),
                         root, REPOSITORY, revision, records, parents) for path in paths]
    return ProjectionSnapshot(repository_id=REPOSITORY, source_sha=revision,
        generation_id="bounded-actual-ac-subset-" + revision, nodes=nodes, edges=[],
        supported_kinds=["AcceptanceCriterion"], supported_fields=mapped_fields(["AcceptanceCriterion"]),
        supported_relationships=["parent", "depends_on"])


class SnapshotStorage:
    """Storage-only double: filter actual mapper output; never implement answer policy."""

    def __init__(self):
        self.calls = []
        self.unavailable = False
        self.stale = False
        self.omit_field = None

    async def active(self, repository_id):
        if self.unavailable:
            raise BackendUnavailable()
        if self.stale or repository_id != REPOSITORY:
            return None
        return source_snapshot()

    async def get_generation(self, repository_id, generation_id):
        snapshot = await self.active(repository_id)
        return snapshot if snapshot and snapshot.generation_id == generation_id else None

    async def get_revision(self, repository_id, source_sha):
        snapshot = await self.active(repository_id)
        return snapshot if snapshot and snapshot.source_sha == source_sha else None

    async def capabilities(self):
        return {"graph": True, "semantic": False, "hybrid": False}

    async def query(self, repository_id, generation_id, operation, arguments, limit):
        self.calls.append((repository_id, generation_id, operation, arguments))
        snapshot = await self.active(repository_id)
        assert snapshot and generation_id == snapshot.generation_id
        identifiers = set(arguments["entity_ids"])
        if operation == "get_entities":
            selected = [node for node in snapshot.nodes if node.canonical_id in identifiers]
        elif operation == "_get_ac_children":
            selected = [node for node in snapshot.nodes if node.properties.get("structural_parent") in identifiers]
        else:
            raise AssertionError(f"Unexpected storage read: {operation}")
        rows = [node.model_copy(deep=True) for node in selected[:limit]]
        if self.omit_field:
            for row in rows:
                row.properties.pop(self.omit_field, None)
        return rows

    async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
        return [], []


class PublicNeedsHarness(ScenarioCase):
    """Real registry, scheduler, file stores and fresh service instance at each turn."""

    def configure(self, catalog_enabled=False):
        self.setUp()
        self.route_choice = "research"
        self.storage = SnapshotStorage()
        self.catalog = QueryCatalog(self.run_root / "catalog") if catalog_enabled else None
        self.catalog_before = self.catalog.descriptors() if self.catalog else None
        self.admission = QueryAdmission(self.catalog, self.storage, REPOSITORY) if self.catalog else None
        self.config = self.config.model_copy(update={
            "knowledge": KnowledgeConfig(backend="neo4j", repository_id=REPOSITORY, repository_root=str(ROOT)),
            "sources": [SourceConfig(id="knowledge.graph", kind="graph_query", categories=["task_context"])],
            "context_enrichment": self.config.context_enrichment.model_copy(update={"enabled": False}),
            "entity_context": self.config.entity_context.model_copy(update={"enabled": False}),
        })
        self.operation = "get_entities"
        self.jev.script("knowledge.operation_select", "operation", lambda question, batch: choice_answer(self.operation))
        return self

    def service(self):
        service = super().service()
        self.env.bindings = build_bindings(self.snapshot,
            knowledge_retriever=KnowledgeService(self.storage,
                source_resolver=GitSourceResolver(ROOT, REPOSITORY), query_catalog=self.catalog),
            query_catalog=self.catalog, query_admission=self.admission)
        return service

    def question(self, question):
        """Public caller supplies a question and trusted scope, no operation or answer fields."""
        scope = make_scope(ROOT, component_ids=[], read_roots=["docs"], source_ids=["knowledge.graph"])
        scope = scope.model_copy(update={"revision": RevisionInfo(commit=source_snapshot().source_sha)})
        return TaskInput(goal=question, caller=Actor(id="independent-proof", kind=ActorKind.HOST),
            scope=scope, permissions=["read_repo"], input_payload_schema=schema_ids.RESEARCH_REQUEST,
            requested_output_schema=schema_ids.EVIDENCE_BUNDLE,
            input_payload={"question": question, "evidence_needs_only": True,
                "evidence_needs": [{"id": "need.question", "category": "task_context", "priority": "required", "question": question}]})


def packet_request(envelope):
    """Read the actual artifact emitted by the production host packet."""
    packet = envelope.pending_interaction
    return json.loads(Path(packet.input_artifact_refs[0]).read_text(encoding="utf-8"))["request"]


def controlled_needs(request, identifier="KM-500c-2", fields=("criteria",), **overrides):
    """Explicit model double for wiring tests, never claimed as semantic evaluation."""
    return {"original_question": request["original_question"], "source_scope": request["source_scope"],
        "selections": {"entity_types": ["ac"], "target_ids": [identifier] if identifier else [],
            "required_fields": list(fields), "document_types": ["ac_yaml"], "relationships": []},
        "uncertain": {dimension: [] for dimension in DIMENSIONS}, "detail_mode": "fields",
        "completeness": "single_entity", "hierarchy_scope": "not_applicable", "scope_resolution": "sufficient",
        "status": "decided", "engine": "host_llm", "rationale": "Controlled provider fixture; no model ran.",
        **overrides}


def host_submission(envelope, response):
    return raw_submission(envelope.pending_interaction.model_dump(mode="json"), envelope.run_id,
                          response=response, actor_id="host:controlled-needs")


async def interpret_public_question(harness, question, identifier="KM-500c-2", fields=("criteria",), **overrides):
    pending = await harness.service().start_run(harness.question(question))
    assert pending.status is RunStatus.WAITING_HOST, pending.model_dump_json()
    assert pending.pending_interaction.operation == "interpret_retrieval_needs"
    response = controlled_needs(packet_request(pending), identifier, fields, **overrides)
    final = await harness.service().resume_run(pending.run_id, host_submission(pending, response))
    return final, await harness.checkpoint_values(final.run_id)


def answer_assessments(values):
    return [json.loads(item.diagnostics["knowledge_answer"]) for item in values["results"].values()
            if "knowledge_answer" in item.diagnostics]
