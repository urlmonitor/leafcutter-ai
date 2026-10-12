"""Independent public clause-comparison tests for e2 AC-6 and AC-7.

The disagreeing texts are explicit controlled supplied-evidence fixtures, not
claims about existing repository requirements. The actual-source control reads Git.
"""
import copy
import pytest

from tests.knowledge.test_query_answer_contract_acceptance_assessment import invoke_assess, actual_source
from tests.knowledge.query_answer_contract_acceptance_support import REPOSITORY_ID, SOURCE_SHA


def comparison_packet():
    """Supply attributed conflicting statements without any preferred authority."""
    texts = ['Publish only after the review is approved.', 'Publish before the review is approved.']
    evidence = [{'evidence_id': 'controlled-' + str(index), 'kind': 'source_excerpt', 'content': text,
        'source': {'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
                   'path': 'controlled-supplied/requirement-' + str(index) + '.md', 'locator': '#clause'}}
        for index, text in enumerate(texts)]
    return {'kind': 'clause_comparison', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
        'evidence': evidence, 'clauses': [{'clause_id': 'clause-' + str(index),
            'evidence_id': item['evidence_id'], 'quote': item['content']} for index, item in enumerate(evidence)],
        'interpretation': {'relation': 'conflict', 'clause_ids': ['clause-0', 'clause-1'],
                           'rationale': 'The supplied statements impose opposite review orderings.'}}


def test_public_comparison_keeps_each_clause_source_and_labels_candidate_inference(monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # angle: reachability
    packet = comparison_packet()
    before = copy.deepcopy(packet)
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0, output
    assert [item['quote'] for item in output['clauses']] == [item['quote'] for item in packet['clauses']]
    assert [item['source'] for item in output['clauses']] == [item['source'] for item in packet['evidence']]
    assert output['interpretation']['relation'] == 'conflict'
    assert output['interpretation']['inferred'] is True
    assert output['interpretation']['authoritative'] is False
    assert output['equivalence_established'] is False
    assert output['authoritative_clause_id'] is None
    assert packet == before


def test_similarity_without_compared_supported_interpretation_establishes_no_authority(monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # angle: discrimination
    packet = comparison_packet()
    packet.pop('interpretation')
    packet['similarity'] = 1.0
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0, output
    assert output['interpretation'] is None
    assert output['equivalence_established'] is False
    assert output['authoritative_clause_id'] is None
    assert output['status'] == 'unresolved'


@pytest.mark.parametrize('control', ['missing_quote', 'foreign_source'])
def test_unsupported_clause_cannot_participate_in_conflict_or_duplicate_claim(monkeypatch, tmp_path, capsys, control):
    # covers: KM-500e-2
    # angle: boundary
    packet = comparison_packet()
    if control == 'missing_quote':
        packet['clauses'][1]['quote'] = 'A sentence absent from the supplied evidence.'
    else:
        packet['evidence'][1]['source']['source_sha'] = 'f' * 40
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0, output
    assert output['interpretation'] is None
    assert len(output['clauses']) == 1
    assert output['status'] == 'unresolved' and output['limitations']
    assert output['authoritative_clause_id'] is None


def test_actual_canonical_source_clauses_remain_literal_under_duplicate_proposal(monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # angle: real_artifact
    evidence = [actual_source('TQ-500f-2'), actual_source('TQ-500f-2-i')]
    clauses = []
    for index, item in enumerate(evidence):
        quote = next(line.strip() for line in item['content'].splitlines() if line.strip().startswith('Then '))
        clauses.append({'clause_id': 'actual-' + str(index), 'evidence_id': item['evidence_id'], 'quote': quote})
    packet = {'kind': 'clause_comparison', 'repository_id': REPOSITORY_ID, 'source_sha': SOURCE_SHA,
        'evidence': evidence, 'clauses': clauses,
        'interpretation': {'relation': 'duplicate', 'clause_ids': [item['clause_id'] for item in clauses],
                           'rationale': 'Caller proposes overlap; this is not a proven equivalence.'}}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, packet)
    assert code == 0, output
    assert [item['quote'] for item in output['clauses']] == [item['quote'] for item in clauses]
    assert output['interpretation']['inferred'] is True
    assert output['equivalence_established'] is False
    assert output['authoritative_clause_id'] is None
