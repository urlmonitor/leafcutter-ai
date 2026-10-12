"""Focused independent checks closing individual approved clause proof gaps."""
import asyncio
import json

from knowledge import contracts as c
from knowledge.service import KnowledgeService
from tests.knowledge.test_core import Backend, entity, request
from tests.knowledge.test_query_answer_contract_acceptance_assessment import (
    actual_source, invoke_assess,
)
from tests.knowledge.query_answer_contract_acceptance_support import REPOSITORY_ID, SOURCE_SHA


def test_duplicate_selected_rows_count_once_and_missing_status_has_unknown_bucket():
    # angle: criterion
    # angle: reachability
    # angle: seam
    # covers: KM-500e-3
    # angle: discrimination
    first = entity(c, 'CONTROL-A')
    first.properties = {'work_status': 'done', 'source_fields': {'work_status': 'present'}, 'mapped_fields': ['work_status']}
    second = entity(c, 'CONTROL-B')
    second.properties = {'source_fields': {'work_status': 'present'}, 'mapped_fields': ['work_status']}
    backend = Backend(c, [first, first.model_copy(deep=True), second])
    actual = asyncio.run(KnowledgeService(backend).retrieve(request(c,
        arguments={'entity_ids': ['CONTROL-A', 'CONTROL-B']}, disclosure_level=1,
        answer_requirements={'original_question': 'Give work statuses for these two exact controlled IDs.',
            'required_fields': ['work_status'], 'scope': {'population': 'returned_entities'}, 'require_complete': True})))
    assert len(actual.evidence) == 2
    assert actual.answer.completeness.known_count == 2
    assert actual.answer.known_work_status_counts == {'done': 1, 'unknown': 1}
    assert actual.answer.work_status_counts is None
    assert actual.answer.status != 'fulfilled'


def test_rich_evaluation_executes_admitted_catalog_entry_with_pinned_digest(tmp_path):
    # covers: KM-500d-3
    # angle: seam
    from tests.knowledge.test_query_admission import admission, candidate
    from knowledge.evaluation import evaluate
    catalog, port, db = admission(tmp_path / 'catalog')
    receipt = asyncio.run(port.verify_and_activate(candidate(), repository_id='repo', source_sha='a' * 40))
    packet = {'evaluation_version': '2', 'reviewed_by': 'independent QA controlled catalog-entry check',
        'source_sha': 'a' * 40, 'cases': [{'id': 'catalog-runtime-consumer', 'state': 'runnable',
            'request': {'repository_id': 'repo', 'request_id': 'independent-catalog-eval', 'revision': 'a' * 40,
                'operation': 'get_component_tests', 'mode': 'graph', 'operation_digest': receipt['digest'],
                'arguments': {'component_ids': ['component']}},
            'assertions': [{'path': 'stats.operation_digest', 'equals': receipt['digest']},
                           {'path': 'evidence.0.entity.canonical_id', 'equals': 'test'}]}]}
    report = asyncio.run(evaluate(KnowledgeService(db, query_catalog=catalog), packet, query_catalog=catalog))
    assert report['denominators']['executed'] == 1
    assert report['cases'][0]['verdict'] == 'passed', report
    assert report['cases'][0]['actual']['stats']['operation_digest'] == receipt['digest']


def test_runtime_cause_requires_matching_supplied_attempt_and_remains_unverified(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-4
    # angle: discrimination
    evidence = actual_source('retrieval-service')
    quote = 'async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:'
    diagnostic = {'evidence_id': 'controlled-diagnostic', 'kind': 'runtime_diagnostic',
        'source': {'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
                   'path': 'controlled-supplied/attempt.json', 'locator': ''},
        'content': json.dumps({'request_id': 'controlled-request', 'attempt_id': 'controlled-attempt',
                              'source_sha': SOURCE_SHA, 'cause': 'Controlled reported diagnostic cause'})}
    packet = {'kind': 'implementation', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
        'request_id': 'controlled-request', 'attempt_id': 'controlled-attempt',
        'evidence': [evidence, diagnostic], 'stages': [{'name': 'Public entry',
            'evidence_id': evidence['evidence_id'], 'quote': quote}]}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0
    assert output['runtime_cause']['reported_cause'] == 'Controlled reported diagnostic cause'
    assert output['runtime_cause']['independently_verified'] is False
    packet['attempt_id'] = 'different-request-attempt'
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0 and output['runtime_cause'] is None
    assert output['limitations']


def test_inspected_regression_scope_and_comparison_are_explicit_supplied_interpretation(monkeypatch, tmp_path, capsys):
    # angle: criterion
    # angle: reachability
    # covers: KM-500f-5
    # angle: seam
    evidence = actual_source('boundary-tests', 'fixture')
    quote = next(line.strip() for line in evidence['content'].splitlines() if line.strip().startswith('assert '))
    change_scope = {'source_sha': SOURCE_SHA, 'inspected_paths': [evidence['source']['path']]}
    inspection = {'evidence_id': evidence['evidence_id'], 'quote': quote, 'test_id': 'inspected-assertion',
        'behavior': 'Candidate selected because the inspected assertion guards the proposed outcome.',
        'seeded_facts': 'Supplied fixture interpretation', 'expected_result': quote,
        'comparison_case': 'Controlled absent-evidence case must not produce the proposed outcome.',
        'actual_boundaries': ['Git source reader', 'public assessment CLI'],
        'simulated_boundaries': ['No execution of the cited test']}
    packet = {'kind': 'regression', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
              'evidence': [evidence], 'change_scope': change_scope, 'inspections': [inspection]}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0 and output['change_scope'] == change_scope
    recommendation = output['recommendations'][0]
    assert recommendation['comparison_case'] == inspection['comparison_case']
    assert recommendation['actual_boundaries'] == inspection['actual_boundaries']
    assert recommendation['simulated_boundaries'] == inspection['simulated_boundaries']
    assert recommendation['interpretation'] is True
    assert recommendation['executed_branch_proof'] == 'unverified'
    assert output['exhaustive'] is False and output['minimal'] is False
