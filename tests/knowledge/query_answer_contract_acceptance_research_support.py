"""Shared source and kernel support for independent research-assessment acceptance.

Only database selection, Jev and tracing are controlled boundaries. Canonical
projection, Git disclosure, neutral assessment, scheduling and persistence are real.
"""
import asyncio
from functools import lru_cache
import json
import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import Actor, ActorKind, TaskInput, schema_ids
from kernel.providers.fakes import choice_answer
from knowledge.adapters.git_source import GitSourceResolver
from knowledge.config import KnowledgeConfig
from knowledge.contracts import ProjectionSnapshot
from knowledge.projection.canonical_loader import load_snapshot
from knowledge.query_catalog import QueryCatalog
from knowledge.service import KnowledgeService
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import ScenarioCase
from tests.knowledge.query_answer_contract_acceptance_support import (
    ROOT, REPOSITORY_ID, SOURCE_SHA, ProjectionStorage,
)
from tests.knowledge.test_query_answer_contract_acceptance_assessment import (
    reviewed_historical_report,
)


@lru_cache(maxsize=1)
def source_projection():
    """Project actual immutable source once; expected assertions never feed projection."""
    fingerprint = hashlib.sha256(b''.join((ROOT / name).read_bytes() for name in (
        'knowledge/projection/canonical_loader.py', 'knowledge/projection/answer_fields.py'))).hexdigest()
    path = Path(tempfile.gettempdir()) / 'leafcutter-research-assessment-projection-cache.json'
    if path.exists():
        cached = json.loads(path.read_text(encoding='utf-8'))
        if cached.get('producer') == fingerprint and cached['snapshot']['source_sha'] == SOURCE_SHA:
            snapshot = ProjectionSnapshot.model_validate(cached['snapshot'])
            if snapshot.repository_id == REPOSITORY_ID:
                return snapshot
    snapshot = load_snapshot(ROOT, REPOSITORY_ID, SOURCE_SHA)
    path.write_text(json.dumps({'producer': fingerprint, 'snapshot': snapshot.model_dump(mode='json')}), encoding='utf-8')
    return snapshot


class CanonicalSelection(ProjectionStorage):
    """Control graph selection only, while retaining actual canonical record contents."""

    async def query(self, repository_id, generation_id, operation, arguments, limit):
        self.calls.append((repository_id, generation_id, operation, arguments))
        assert repository_id == REPOSITORY_ID
        assert generation_id == self.snapshot.generation_id
        assert operation in {'get_acceptance_criteria', 'get_entities'}
        if self.unavailable:
            from knowledge.errors import BackendUnavailable
            raise BackendUnavailable()
        if operation == 'get_entities':
            selected = set(arguments['entity_ids'])
            return [node for node in self.nodes if node.canonical_id in selected][:limit]
        return self.nodes[:limit]


async def complete_requested_synthesis(case, result):
    """Answer the actual v01 host-synthesis wait without inventing missing facts."""
    from kernel.contracts import RunStatus
    from tests.kernel.integration.scenario_support import FakeHostResponder
    if result.status != RunStatus.WAITING_HOST:
        return result
    assert result.pending_interaction.operation == "synthesize_evidence"
    host = FakeHostResponder({schema_ids.FINDINGS: {
        "findings": [], "unknowns": ["The supplied evidence does not settle missing required facts."],
    }})
    answer = host.answer(result)
    final = await case.service().resume_run(result.run_id, answer)
    assert final.status != RunStatus.WAITING_HOST, "Synthesis must not repeat or manufacture coverage."
    return final


class ResearchAssessmentCase(ScenarioCase):
    """Shared actual source, configured kernel and registered retrieval test support."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source_projection()  # fixture setup is outside every product request deadline


    def setUp(self):
        super().setUp()
        self.repo = ROOT
        self.route_choice = 'research'
        self.params['answer'] = 1.0
        self.config = self.config.model_copy(update={
            'knowledge': KnowledgeConfig(backend='neo4j', repository_id=REPOSITORY_ID,
                                         repository_root=str(ROOT)),
            'sources': [SourceConfig(id='knowledge.graph', kind='graph_query', categories=['task_context'])],
        })
        self.requests, self.neutral_results = [], []
        self.selected = 'KM-500c-2'
        self.unavailable = False
        self.catalog = QueryCatalog(self.run_root / 'query-catalog')
        async def pin(repository_id, source_sha='latest'):
            return source_projection().model_dump(exclude={'nodes', 'edges'})
        self.admission = SimpleNamespace(pin=pin)
        self.jev.script('knowledge.query_readiness', 'readiness', choice_answer('ready'))
        self.jev.script('knowledge.query_target', 'kind', choice_answer('AcceptanceCriterion'))
        self.jev.script('knowledge.query_select', 'query', choice_answer('get_acceptance_criteria'))
        self.requirements = {'original_question': 'Inspect acceptance criteria and supplied evidence.',
            'required_fields': ['canonical_id'], 'scope': {'population': 'returned_entities'},
            'require_complete': True}


    def service(self):
        service = super().service()
        owner = self
        class ActualNeutralPort:
            async def capabilities(self):
                return {'graph': True, 'semantic': False, 'hybrid': False}

            async def retrieve(self, request):
                owner.requests.append(request)
                snapshot = await asyncio.to_thread(source_projection)
                storage = CanonicalSelection(snapshot, [owner.selected], unavailable=owner.unavailable)
                neutral = KnowledgeService(storage, source_resolver=GitSourceResolver(ROOT, REPOSITORY_ID),
                                           cursor_secret=b'independent-research-acceptance')
                result = await neutral.retrieve(request)
                owner.neutral_results.append(result)
                return result
        self.env.bindings = build_bindings(self.snapshot, knowledge_retriever=ActualNeutralPort(),
                                          query_catalog=self.catalog, query_admission=self.admission)
        return service


    def task_with(self, packet, *, requirements=True):
        need = {'id': 'need.assessment', 'category': 'task_context', 'priority': 'required',
                'question': 'Inspect acceptance criteria and supplied evidence.'}
        payload = {'question': need['question'], 'evidence_needs': [need],
                   'evidence_needs_only': True, 'assessment': packet}
        if requirements:
            payload['answer_requirements'] = self.requirements
        return TaskInput(goal=need['question'], caller=Actor(id='independent-qa', kind=ActorKind.HOST),
            scope=make_scope(ROOT, component_ids=['knowledge_management'], revision={'commit': SOURCE_SHA}),
            permissions=['read_repo'], input_payload_schema=schema_ids.RESEARCH_REQUEST,
            input_payload=payload, requested_output_schema=schema_ids.EVIDENCE_BUNDLE)


    async def assessment_output(self, result):
        result = await complete_requested_synthesis(self, result)
        assert result.output is not None, result.model_dump_json()
        bundle = result.output.payload
        assert 'assessments' in bundle, bundle
        assert 'need.assessment' in bundle['assessments'], bundle
        output = bundle['assessments']['need.assessment']
        assert output['source_sha'] == SOURCE_SHA
        assert output['discovery'] == 'actual disclosed declarations'
        assert 'not independently verified' in output['evidence_basis']
        values = await self.checkpoint_values(result.run_id)
        child = [json.loads(item.diagnostics['knowledge_assessment'])
                 for item in values['results'].values() if 'knowledge_assessment' in item.diagnostics]
        assert child, 'Caller output alone must not conceal loss at the child capability seam.'
        assert any(item == output for item in child), (child, output)
        return output, bundle


    async def verification_packet(self):
        report = await asyncio.to_thread(reviewed_historical_report)
        return {'kind': 'verification', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
                'declarations': ['invented/packet-reference.py'], 'evidence': [report],
                'transport_control': {'nested': ['  leading and trailing\n\t ', {'quote': '\t literal \n'}]}}


    async def invoke_registered_retrieval(self, payload):
        """Use the real registered executor for explicit per-call disclosure budgets."""
        from dataclasses import replace
        from kernel.contracts.task import RevisionInfo
        from tests.kernel.helpers import make_context, make_invocation
        self.service()
        context = make_context(ROOT, config=self.config, jev=self.jev)
        context = replace(context, scope=context.scope.model_copy(update={
            'revision': RevisionInfo(commit=SOURCE_SHA), 'component_ids': ['knowledge_management']}))
        invocation = make_invocation().model_copy(update={'input_payload': payload})
        return await self.env.bindings.resolve('retrieve.repository', '1.0.0').ainvoke(invocation, context)
