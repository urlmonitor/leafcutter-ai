"""Independent public kernel assessment tests; external providers remain controlled."""
import asyncio
import contextvars
import json
from pathlib import Path
from types import SimpleNamespace
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput, schema_ids
from kernel.providers.fakes import choice_answer
from knowledge.query_catalog import QueryCatalog
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import answer_human
from tests.knowledge.query_answer_contract_acceptance_support import ROOT, REPOSITORY_ID, SOURCE_SHA
from tests.knowledge.query_answer_contract_acceptance_research_support import ResearchAssessmentCase, source_projection
from tests.knowledge.test_query_answer_contract_acceptance_assessment import DECLARATIONS, actual_source


class TestResearchAssessmentHandoff(ResearchAssessmentCase):
    """The client-visible bundle, not an internal packet, is the acceptance boundary."""







    def test_research_returns_actual_declarations_and_historical_report_proof(self):
        # covers: KM-500f-2
        # angle: reachability
        # angle: criterion
        # angle: seam
        self._asyncioRunner.run(self._scenario_research_returns_actual_declarations_and_historical_report_proof(), context=contextvars.copy_context())

    async def _scenario_research_returns_actual_declarations_and_historical_report_proof(self):
        packet = await self.verification_packet()
        result = await self.service().start_run(self.task_with(packet))
        output, bundle = await self.assessment_output(result)
        assert self.requests and all(request.assessment == packet for request in self.requests)
        assert set(output['declared_references']) == set(DECLARATIONS)
        assert 'invented/packet-reference.py' not in output['declared_references']
        receipt = output['receipts'][0]
        assert receipt['source']['source_sha'] == SOURCE_SHA
        assert receipt['tested_sha'] == '9f70de80ebcafe59ff55cce6732deb92069f9541'
        assert receipt['research_fulfillment'] == 'partial'
        assert receipt['provider_execution'] == 'not run'
        assert receipt['provenance_verified'] is False
        assert output['independent_execution_verified'] is False
        assert bundle['coverage']['need.assessment'] != 'satisfied'

    def test_missing_or_foreign_supplied_source_cannot_become_sufficient(self):
        # covers: KM-500f-2
        # covers: KM-500f-4
        # covers: KM-500f-5
        # angle: discrimination
        self._asyncioRunner.run(self._scenario_missing_or_foreign_supplied_source_cannot_become_sufficient(), context=contextvars.copy_context())

    async def _scenario_missing_or_foreign_supplied_source_cannot_become_sufficient(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                packet = await self.verification_packet()
                if missing:
                    packet['evidence'][0].pop('source')
                else:
                    packet['evidence'][0]['source']['repository_id'] = 'foreign-supplied-source'
                result = await self.service().start_run(self.task_with(packet))
                output, bundle = await self.assessment_output(result)
                assert output['receipts'] == []
                assert output['executed_proof'] == 'unverified'
                assert output['status'] != 'fulfilled'
                assert output['limitations']
                assert bundle['coverage']['need.assessment'] != 'satisfied'

    def test_assessment_survives_clarification_and_reopened_service(self):
        # covers: KM-500e-1
        # covers: KM-500f-2
        # angle: seam
        # angle: real_artifact
        # angle: reachability
        self._asyncioRunner.run(self._scenario_assessment_survives_clarification_and_reopened_service(), context=contextvars.copy_context())

    async def _scenario_assessment_survives_clarification_and_reopened_service(self):
        packet = await self.verification_packet()
        self.catalog = QueryCatalog(self.run_root / 'query-catalog')
        async def pin(repository_id, source_sha='latest'):
            snapshot = await asyncio.to_thread(source_projection)
            return snapshot.model_dump(exclude={'nodes', 'edges'})
        self.admission = SimpleNamespace(pin=pin)
        self.jev.script('knowledge.query_readiness', 'readiness', choice_answer('ready'))
        self.jev.script('knowledge.query_target', 'kind', choice_answer('AcceptanceCriterion'))
        self.jev.script('knowledge.query_select', 'query', choice_answer('get_acceptance_criteria'))
        self.requirements['scope'] = {'population': 'ac_descendants', 'root_id': 'KM-500c', 'levels': ['L2']}
        pending = await self.service().start_run(self.task_with(packet))
        assert pending.status == RunStatus.WAITING_HUMAN, pending.model_dump_json()
        assert self.requests == []
        values = await self.checkpoint_values(pending.run_id)
        states = [item.continuation.state for item in values['work_items'].values() if item.continuation]
        from itertools import zip_longest
        def differences(left, right, path=''):
            if type(left) is not type(right):
                return [path + ':type']
            if isinstance(left, dict):
                return [p for key in left.keys() | right.keys()
                        for p in differences(left.get(key), right.get(key), path + '/' + key)]
            if isinstance(left, list):
                return [p for index, (a, b) in enumerate(zip_longest(left, right))
                        for p in differences(a, b, path + '/' + str(index))]
            return [] if left == right else [path]
        compared = [differences(state.get('assessment'), packet) for state in states]
        assert any(state.get('assessment') == packet for state in states), compared
        import subprocess, sys, os
        from kernel.contracts.run import RunEnvelope
        path = self.run_root / 'independent-assessment-restart.json'
        path.write_text(json.dumps({'pending': pending.model_dump(mode='json'),
            'config': self.config.model_dump(mode='json'), 'run_root': str(self.run_root)}), encoding='utf-8')
        process = await asyncio.to_thread(subprocess.run, [sys.executable, '-m', __name__, str(path)],
            cwd=ROOT, text=True, encoding='utf-8', capture_output=True, timeout=90)
        assert process.returncode == 0, process.stdout + process.stderr
        returned = json.loads(process.stdout)
        assert returned['pid'] != os.getpid()
        resumed = RunEnvelope.model_validate(returned['envelope'])
        output, _ = await self.assessment_output(resumed)
        assert output['receipts'][0]['tested_sha'] != SOURCE_SHA
        assert returned['requests'] and all(request['assessment'] == packet for request in returned['requests'])
        assert all(request['revision'] == SOURCE_SHA for request in returned['requests'])
        assert all(request['answer_requirements']['scope']['inclusion'] == 'root_excluded'
                   for request in returned['requests'])

    def test_research_readiness_uses_actual_facts_instead_of_packet_candidate(self):
        # covers: KM-500f-3
        # angle: discrimination
        # angle: criterion
        # angle: reachability
        # angle: seam
        self._asyncioRunner.run(self._scenario_research_readiness_uses_actual_facts_instead_of_packet_candidate(), context=contextvars.copy_context())

    async def _scenario_research_readiness_uses_actual_facts_instead_of_packet_candidate(self):
        self.selected = 'TQ-500f-2'
        self.requirements['required_fields'] = ['work_status', 'priority']
        source = {'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
                  'path': 'controlled-supplied-policy.json', 'locator': ''}
        policy = {'id': 'explicit-controlled-policy', 'clauses': [
            {'id': 'done', 'field': 'work_status', 'equals': 'done'}], 'deployment_required': True}
        packet = {'kind': 'readiness', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
            'evidence': [{'evidence_id': 'policy', 'kind': 'policy', 'source': source, 'content': json.dumps(policy)},
                {'evidence_id': 'contradictory-candidate', 'kind': 'candidate', 'source': source,
                 'content': json.dumps({'canonical_id': self.selected, 'work_status': 'done', 'priority': 'invented'})}]}
        result = await self.service().start_run(self.task_with(packet))
        output, bundle = await self.assessment_output(result)
        recommendation = output['recommendations'][0]
        assert recommendation['canonical_facts']['work_status'] == 'todo'
        import yaml
        source = yaml.safe_load((await asyncio.to_thread(actual_source, 'TQ-500f-2'))['content'])
        assert recommendation['canonical_facts']['priority'] == source['priority']
        assert recommendation['supplied_facts'] == {}
        assert recommendation['readiness'] == 'not_ready'
        assert recommendation['deployment'] == 'unverified'
        assert bundle['coverage']['need.assessment'] != 'satisfied'

    def test_research_returns_bounded_actual_source_interpretation(self):
        # covers: KM-500f-4
        # angle: real_artifact
        # angle: criterion
        # angle: reachability
        # angle: seam
        self._asyncioRunner.run(self._scenario_research_returns_bounded_actual_source_interpretation(), context=contextvars.copy_context())

    async def _scenario_research_returns_bounded_actual_source_interpretation(self):
        evidence = await asyncio.to_thread(actual_source, 'retrieval-service')
        quote = 'async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:'
        assert quote in evidence['content']
        packet = {'kind': 'implementation', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
                  'evidence': [evidence], 'stages': [{'name': 'Public retrieval entry',
                      'evidence_id': evidence['evidence_id'], 'quote': quote}]}
        result = await self.service().start_run(self.task_with(packet))
        output, bundle = await self.assessment_output(result)
        assert output['stages'][0]['quote'] == quote
        assert output['stages'][0]['source'] == evidence['source']
        assert output['stages'][0]['interpretation'] is True
        assert output['runtime_cause'] is None
        assert output['complete_code_graph'] is False
        assert output['status'] == 'partial'
        assert bundle['coverage']['need.assessment'] != 'satisfied'

    def test_research_preserves_inspected_fixture_and_missing_comparison_gap(self):
        # covers: KM-500f-5
        # angle: real_artifact
        # angle: criterion
        # angle: reachability
        # angle: seam
        # angle: discrimination
        self._asyncioRunner.run(self._scenario_research_preserves_inspected_fixture_and_missing_comparison_gap(), context=contextvars.copy_context())

    async def _scenario_research_preserves_inspected_fixture_and_missing_comparison_gap(self):
        evidence = await asyncio.to_thread(actual_source, 'boundary-tests', 'fixture')
        quote = next(line.strip() for line in evidence['content'].splitlines() if line.strip().startswith('assert '))
        packet = {'kind': 'regression', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
            'evidence': [evidence], 'inspections': [{'evidence_id': evidence['evidence_id'], 'quote': quote,
                'test_id': 'source-inspection-only', 'behavior': 'Inspected assertion, not observed execution',
                'seeded_facts': 'Declared in inspected source', 'expected_result': quote,
                'comparison_case': '', 'actual_boundaries': ['Git source reader', 'public kernel', 'neutral assessment'],
                'simulated_boundaries': ['Jev', 'storage selection', 'trace sink', 'test execution not run']}]}
        result = await self.service().start_run(self.task_with(packet))
        output, bundle = await self.assessment_output(result)
        assert output['recommendations'][0]['quote'] == quote
        assert output['recommendations'][0]['source'] == evidence['source']
        assert output['recommendations'][0]['executed_branch_proof'] == 'unverified'
        assert output['design_gaps'] and output['status'] == 'partial'
        assert output['minimal'] is False and output['exhaustive'] is False
        assert bundle['coverage']['need.assessment'] != 'satisfied'

    def test_research_outage_never_relabels_supplied_report_as_discovered_proof(self):
        # covers: KM-500f-2
        # angle: failure
        self._asyncioRunner.run(self._scenario_research_outage_never_relabels_supplied_report_as_discovered_proof(), context=contextvars.copy_context())

    async def _scenario_research_outage_never_relabels_supplied_report_as_discovered_proof(self):
        self.unavailable = True
        packet = await self.verification_packet()
        result = await self.service().start_run(self.task_with(packet))
        output, bundle = await self.assessment_output(result)
        assert self.neutral_results and self.neutral_results[-1].status == 'unavailable'
        assert output['status'] == 'unresolved'
        assert output['receipts'] == [] and output['executed_proof'] == 'unverified'
        assert bundle['coverage']['need.assessment'] == 'unavailable'

    def test_public_retrieval_clipping_keeps_question_and_assessment_incomplete(self):
        # covers: KM-500e-2
        # covers: KM-500f-2
        # angle: boundary
        self._asyncioRunner.run(self._scenario_public_retrieval_clipping_keeps_question_and_assessment_incomplete(), context=contextvars.copy_context())

    async def _scenario_public_retrieval_clipping_keeps_question_and_assessment_incomplete(self):
        packet = await self.verification_packet()
        self.requirements['required_fields'] = ['criteria']
        task = TaskInput(goal='Inspect criterion and supplied evidence.',
            caller=Actor(id='independent-qa', kind=ActorKind.HOST),
            scope=make_scope(ROOT, component_ids=['knowledge_management'], revision={'commit': SOURCE_SHA}),
            permissions=['read_repo'], input_payload_schema=schema_ids.RETRIEVAL_REQUEST,
            input_payload={'need': {'id': 'need.assessment', 'category': 'task_context', 'priority': 'required',
                'question': 'Inspect criterion and supplied evidence.'}, 'source_ids': ['knowledge.graph'],
                'knowledge': {'operation': 'get_entities', 'mode': 'exact', 'revision': SOURCE_SHA,
                    'arguments': {'entity_ids': [self.selected]}, 'disclosure_level': 3},
                'assessment': packet, 'answer_requirements': self.requirements,
                'detail': 'excerpt', 'limits': {'max_chars': 1}},
            requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        result = await self.invoke_registered_retrieval(task.input_payload)
        bundle = result.output_payload
        output = bundle['assessments']['need.assessment']
        assert self.neutral_results[-1].answer.status == 'fulfilled', 'Control must reach kernel clipping after complete neutral disclosure.'
        assert bundle['truncated'] is True
        assert output['status'] != 'fulfilled'
        answers = [json.loads(result.diagnostics['knowledge_answer'])]
        assert answers and all(answer['status'] != 'fulfilled' for answer in answers)
        assert bundle['coverage']['need.assessment'] != 'satisfied'

    def test_kernel_does_not_restore_assessment_removed_by_neutral_wire_budget(self):
        # covers: KM-500f-4
        # covers: KM-500g-1-i
        # angle: boundary
        self._asyncioRunner.run(self._scenario_kernel_does_not_restore_assessment_removed_by_neutral_wire_budget(), context=contextvars.copy_context())

    async def _scenario_kernel_does_not_restore_assessment_removed_by_neutral_wire_budget(self):
        evidence = await asyncio.to_thread(actual_source, 'retrieval-service')
        quote = 'async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:'
        packet = {'kind': 'implementation', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
                  'evidence': [evidence], 'stages': [{'name': 'Bounded supplied stage ' + str(index),
                      'evidence_id': evidence['evidence_id'], 'quote': quote} for index in range(60)]}
        task = TaskInput(goal='Inspect bounded source interpretation.',
            caller=Actor(id='independent-qa', kind=ActorKind.HOST),
            scope=make_scope(ROOT, component_ids=['knowledge_management'], revision={'commit': SOURCE_SHA}),
            permissions=['read_repo'], input_payload_schema=schema_ids.RETRIEVAL_REQUEST,
            input_payload={'need': {'id': 'need.assessment', 'category': 'task_context', 'priority': 'required',
                'question': 'Inspect bounded source interpretation.'}, 'source_ids': ['knowledge.graph'],
                'knowledge': {'operation': 'get_entities', 'mode': 'exact', 'revision': SOURCE_SHA,
                    'arguments': {'entity_ids': [self.selected]}, 'disclosure_level': 1,
                    'budget': {'max_content_bytes': 2048, 'max_estimated_tokens': 4096}},
                'assessment': packet, 'detail': 'summary'},
            requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        result = await self.invoke_registered_retrieval(task.input_payload)
        assert self.neutral_results, result.model_dump_json()
        neutral = self.neutral_results[-1].assessment
        assert neutral['status'] == 'unresolved' and 'response_budget_exhausted' in neutral['limitations'], neutral
        assert result.output_payload is not None, result.model_dump_json()
        returned = result.output_payload['assessments']['need.assessment']
        assert returned['status'] == 'unresolved', returned
        assert not returned.get('stages'), 'Kernel restored evidence removed by the authoritative neutral wire budget.'
        assert len(json.dumps(returned).encode()) <= 2048




    def test_opaque_packet_rejects_non_json_without_disabling_label_normalization(self):
        # covers: KM-500e-2
        # angle: boundary
        from pydantic import ValidationError
        from kernel.contracts.payloads import ResearchRequestPayload
        ordinary = ResearchRequestPayload(question='  A normal question  ', assessment={'nested': ['  exact text\n']})
        assert ordinary.question == 'A normal question'
        assert ordinary.assessment['nested'][0] == '  exact text\n'
        packet = {'kind': 'verification', 'repository_id': REPOSITORY_ID,
                  'source_sha': SOURCE_SHA, 'evidence': [], 'unsupported_object': object()}
        with self.assertRaises(ValidationError):
            self.task_with(packet)


def _resume_assessment_in_child(path):
    """Reopen actual persisted research in a fresh interpreter; only external doubles reset."""
    import os
    from kernel.config import KernelConfig
    from kernel.contracts.run import RunEnvelope
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    TestResearchAssessmentHandoff.setUpClass()
    case = TestResearchAssessmentHandoff()
    case.setUp()
    try:
        case.run_root = Path(raw['run_root'])
        case.catalog = QueryCatalog(case.run_root / 'query-catalog')
        case.config = KernelConfig.model_validate(raw['config'])
        pending = RunEnvelope.model_validate(raw['pending'])
        answer = answer_human(pending, {'free_text': json.dumps({'scope': {'inclusion': 'root_excluded'}})})
        result = asyncio.run(case.service().resume_run(pending.run_id, answer))
        print(json.dumps({'pid': os.getpid(), 'envelope': result.model_dump(mode='json'),
                          'requests': [request.model_dump(mode='json') for request in case.requests]}))
    finally:
        case.doCleanups()


if __name__ == '__main__':
    import sys
    _resume_assessment_in_child(sys.argv[1])
