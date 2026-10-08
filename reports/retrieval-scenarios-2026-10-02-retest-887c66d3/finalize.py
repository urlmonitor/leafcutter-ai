"""Grade saved retest receipts offline; never call a provider or graph."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

oracle=load(ROOT/'docs/analysis/2026-10-02-retrieval-active-source-oracle.json')
readiness=load(OUT/'readiness.json')
assert readiness['active']['source_sha']==oracle['source']['commit']
active=load(OUT/'active-controls.json')
previous=ROOT/'reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3'
oldactive=load(previous/'active-controls.json')
byid={row['case_id']:row['actual_response'] for row in active['cases']}
expected={r['id']:r for r in oracle['tq_500f']['records']}
def ids(result):
    return {e['entity']['canonical_id'] for e in result['evidence']}
def yes(value):
    return bool(value)
checks={}
a=byid['RQE-01-P']
checks['RQE-01-P']=yes(ids(a)==set(expected) and a['answer']['completeness']['exact_total']==15 and a['answer']['work_status_counts']=={'done':5,'todo':10} and all(e['entity']['properties']['work_status']==expected[e['entity']['canonical_id']]['work_status'] and e['entity']['source']['content_hash']==expected[e['entity']['canonical_id']]['sha256'] and e['field_locators']['work_status']=='/work_status' for e in a['evidence']))
a=byid['RQE-01-N']
checks['RQE-01-N']=yes(a['answer']['status']=='partial' and a['answer']['work_status_counts'] is None and len(a['answer']['missing_fields'])==15)
try:
    raw=subprocess.check_output(['git','show',oracle['source']['commit']+':'+oracle['km_500c_2']['path']],cwd=ROOT)
except (OSError, subprocess.CalledProcessError) as exc:
    raise RuntimeError('Cannot read the pinned criterion source for offline grading') from exc
assert hashlib.sha256(raw).hexdigest()==oracle['km_500c_2']['raw_yaml_sha256']
import yaml
criterion=yaml.safe_load(raw)['criteria']
a=byid['RQE-02-P']
checks['RQE-02-P']=yes(ids(a)=={'KM-500c-2'} and a['evidence'][0]['content']==criterion and a['evidence'][0]['entity']['source']['locator']=='/criteria' and a['answer']['status']=='fulfilled')
a=byid['RQE-02-N']
checks['RQE-02-N']=yes(a['answer']['status']=='partial' and a['answer']['completeness']['exact_total'] is None and any(f['field']=='criteria' and f['reason']=='truncated' for f in a['answer']['missing_fields']))
a=byid['RQE-03-P']
checks['RQE-03-P']=yes(ids(a)==set(oracle['tq_500f']['direct_incoming_depends_on_tq_500f_2']) and a['answer']['completeness']['exact_total']==5)
a=byid['RQE-03-N']
checks['RQE-03-N']=yes(len(a['evidence'])==4 and a['answer']['status']=='partial' and a['answer']['completeness']['exact_total'] is None)
a=byid['RQE-06-P']
checks['RQE-06-P']=yes(a['answer']['status']=='partial' and a['answer']['work_status_counts'] is None and a['assessment'] is None and a['observation']['state']=='disabled')
a=byid['RQE-06-N']
checks['RQE-06-N']=yes(a['status']=='unavailable' and a['answer']['status']=='unresolved' and not a['evidence'] and a['source_sha'] is None and a['answer']['completeness']['exact_total'] is None)
pages=load(OUT/'continuation-controls.json')['pages']
page_ids=[e['entity']['canonical_id'] for p in pages for e in p['actual_response']['evidence']]
page_pass=yes(len(pages)==3 and [len(p['actual_response']['evidence']) for p in pages]==[5,5,5] and set(page_ids)==set(expected) and len(set(page_ids))==len(page_ids) and all(p['actual_response']['answer']['status']=='partial' and p['actual_response']['answer']['completeness']['exact_total'] is None for p in pages) and pages[-1]['actual_response']['continuation'] is None)
leaf=load(OUT/'leaf-control.json')['actual_response']
expected_leaves={i for i in expected if not any(j.startswith(i+'-') for j in expected)}
leaf_pass=yes(len(expected_leaves)==11 and ids(leaf)==expected_leaves and leaf['answer']['completeness']['exact_total']==11)
old_equal=all(r['actual_response']['answer']==oldactive['cases'][i]['actual_response']['answer'] and r['actual_response']['evidence']==oldactive['cases'][i]['actual_response']['evidence'] for i,r in enumerate(active['cases']))
live={case:load(OUT/(case+'.live-response.json')) for case in ['RS-02','RS-03']}
summary=[]
for case,row in live.items():
    response=row['actual_response']; generations=[c for c in row['trace'] if c['kind']=='generation']
    summary.append({'scenario_id':case,'original_question':row['request']['goal'],'status':response['status'],'answer':response['output'],'question':response['pending_interaction']['question'],'seconds':row['seconds'],'usage':response['usage_summary'],'generation_names':[c['name'] for c in generations],'actual_provider_calls':sum(c['data']['metadata']['calls'] for c in generations),'routing':[c['data']['payload'] for c in row['trace'] if c['name']=='routing.assessed'],'context_enrichment':[c['data']['payload'] for c in row['trace'] if c['name']=='context.enriched'],'graph_query_executed':False,'retrieval_capability_entered':any(c['name']=='capability.retrieve.repository' for c in row['trace'])})
assert sum(row['actual_provider_calls'] for row in summary)==8
boundary=load(OUT/'live-boundary.json')
boundary.update(status='completed_waiting_human',completed_at=datetime.now(timezone.utc).isoformat(),actual_calls_total=8,actual_calls_by_case={r['scenario_id']:r['actual_provider_calls'] for r in summary},resolved_models=['jev-1.13.0'],retrieval_capability_entered=True,graph_query_executed=False,retrieval_reached=False,resumes_performed=0,stage_of_stop='knowledge.answer_contract -> answer_scope clarification -> waiting_human',actual_retrieved_excerpt_count=0,actual_transmission_categories=['Original questions and the research need descriptions selected from configured categories.','Offered answer-contract field names, population/inclusion/root choices and bounded classification instructions.','Configured source/contract readiness metadata; no retrieved repository excerpts or graph-query results.'],actual_transmission_basis='Derived from saved generation question IDs/outputs and the pinned producer code. RecordingTracer stores outbound-state fingerprints, not full outbound payloads.',actual_input_tokens=sum(r['usage']['input_tokens'] for r in summary),actual_output_tokens=sum(r['usage']['output_tokens'] for r in summary),actual_cost_usd_estimated=sum(r['usage']['cost_usd_known'] for r in summary))
boundary['human_prompts']={r['scenario_id']:r['question'] for r in summary}
save('live-boundary.json',boundary)
from kernel.config import load_kernel_config
default=load_kernel_config().model_dump(mode='json')
configured=load(OUT/'effective-config.json')
policy={'canary_source_policy':configured['sources'],'default_source_policy':default['sources'],'default_knowledge_backend':default['knowledge']['backend'],'context_enrichment_enabled':configured['context_enrichment']['enabled'],'actual_enrichment_files_scanned':{r['scenario_id']:r['context_enrichment'][0]['files_scanned'] for r in summary},'limitation':'These are graph-only canaries. Default configured sources differ; no all-source/default-entry quality claim. Another separately authorized test of the real adapter default is needed for that question.'}
save('source-policy-comparison.json',policy)
old=load(previous/'execution.json')
scenarios=[]
for original in old['scenarios']:
    row={k:original[k] for k in ['scenario_id','title','original_catalog_question_and_fixture','target_path_gap']}
    row['previous_observed_verdict']=original['observed_answer_or_facet_verdict']
    row['full_target_journey_execution']='live_start' if row['scenario_id'] in live else 'not_run'
    row['full_target_pass_demonstrated']=False
    row['facet_observations']=[r['case_id'] for r in active['cases'] if row['scenario_id'] in r['scenario_ids']]
    row['observed_answer_or_facet_verdict']=original['observed_answer_or_facet_verdict'] if row['facet_observations'] else 'Not run in this retest.'
    if row['scenario_id']=='RS-02':
        row['observed_answer_or_facet_verdict']='Live reaches research and answer-contract planning, then technical population clarification; no count or evidence.'
        row['target_path_gap']='Genuine population/root ambiguity remains; clarification uses duplicate jargon and JSON rather than a focused natural question. No live human resume.'
    if row['scenario_id']=='RS-03':
        row['observed_answer_or_facet_verdict']='Live reaches research and recognizes KM-500c-2, but population gating asks a count-scope question; no exact-ID query or answer.'
        row['target_path_gap']='Answer-contract gate stops first. Exact-ID catalog/binding gap remains separately visible in scripted offered-query control.'
    scenarios.append(row)
prior=load(OUT/'prior-artifact-fingerprints.json')
assert all(digest(ROOT/p)==expected_hash for p,expected_hash in prior.items())
fingerprint=load(OUT/'code-fingerprint.json')
assert all(digest(ROOT/p)==expected_hash for p,expected_hash in fingerprint['file_sha256'].items())
result={'recorded_at':datetime.now(timezone.utc).isoformat(),'code_sha':fingerprint['head'],'code_sources_unchanged_during_retest':True,'source':readiness['active'],'oracle':'docs/analysis/2026-10-02-retrieval-active-source-oracle.json','oracle_matches_source':True,'live':summary,'active_grades':checks,'active_passed':sum(checks.values()),'active_total':len(checks),'additional_controls':{'pagination':page_pass,'terminal_leaves':leaf_pass},'historical_denominators':load(OUT/'historical-controls.json')['report']['denominators'],'active_answers_and_evidence_equal_previous':old_equal,'scripted_kernel_starts':3,'live_provider_calls':8,'live_full_target_passes':0,'full_target_scenarios_live_started':2,'full_target_scenarios_not_run':27,'prior_receipts_preserved':len(prior),'source_policy_ref':'source-policy-comparison.json','post_run_harness_error':{'process_exit':1,'error':'TypeError: AnswerAssessment is not JSON serializable in final console summary','query_receipts_saved_before_error':True,'raw_log':'continuation-checks.log','queries_rerun':False},'scenarios':scenarios,'limits':['No live human/host resumes or further model calls.','Scripted choices prove controls, not semantic quality.','Graph-only canary source policy differs from default repo_text sources.','Historical mapper3 failures are projection-precondition mismatch, not eight current wrong answers.','No graph writes, indexing, query activation, embeddings or Langfuse export.','Missing/proposed target features are not simulated as passing cases.']}
save('execution.json',result)
print(json.dumps({'active_passed':result['active_passed'],'additional_controls':result['additional_controls'],'live_calls':8,'historical':result['historical_denominators'],'all29':len(scenarios),'old_files_preserved':len(prior)}))
