"""Replay existing evaluation in a new receipt directory; no product behavior changes."""
from pathlib import Path
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
from tests.knowledge_live import retrieval_scenario_checks as runner
runner.OUT = OUT
OLD = ROOT / 'reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3'
os.environ['LEAFCUTTER_ENV_FILE'] = 'C:/Users/Hendrik/Code/leafcutter/.env'

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

async def prepare():
    from knowledge.config import KnowledgeConfig, build_retriever
    from kernel.config import load_kernel_config
    if (OUT/'readiness.json').exists():
        raise SystemExit('Fresh preparation already exists; refusing overwrite.')
    config = load(OLD/'live-canary.config.json')
    base = Path(os.environ['TEMP'])/'leafcutter-retrieval-scenarios-retest-887c66d3'
    config['paths']['run_root'] = str(base/'runs')
    config['paths']['registry'] = str(ROOT/'config/capability_registry.json')
    config['knowledge']['repository_root'] = str(ROOT)
    config['knowledge']['query_catalog_root'] = str(base/'readonly-catalog')
    runner.save('live-canary.config.json', config)
    current = load_kernel_config(OUT/'live-canary.config.json')
    runner.save('effective-config.json', current.model_dump(mode='json'))
    built = build_retriever(KnowledgeConfig(backend='neo4j', repository_id='leafcutter', repository_root=str(ROOT)))
    try:
        active = await built.backend.active('leafcutter')
        historical = await built.backend.get_revision('leafcutter','9d11594782abfb417d0f3a826bfb1f91f3a523ac')
        readiness = {'observed_at':datetime.now(timezone.utc).isoformat(),'active':active.model_dump(mode='json',exclude={'nodes','edges'}),'historical_rqe_source':historical.model_dump(mode='json',exclude={'nodes','edges'}),'mechanism_capabilities':await built.capabilities(),'database_writes':False,'provider_calls':0}
        runner.save('readiness.json',readiness)
        for rs in ['RS-02','RS-03']:
            request=load(OLD/'requests'/(rs+'.live.json'))
            request['scope']['revision']['commit']=active.source_sha
            request['scope']['repository_root']=str(ROOT)
            runner.save('requests/'+rs+'.live.json',request)
        load(ROOT/'docs/analysis/2026-10-02-retrieval-active-source-oracle.json')
        runner.save('oracle-identity-check.json',{'actual_hosted_source_sha':active.source_sha,'previous_hosted_source_sha':load(OLD/'readiness.json')['active']['source_sha'],'same_source':active.source_sha==load(OLD/'readiness.json')['active']['source_sha'],'oracle_path':'docs/analysis/2026-10-02-retrieval-active-source-oracle.json','oracle_file_sha256':hashlib.sha256((ROOT/'docs/analysis/2026-10-02-retrieval-active-source-oracle.json').read_bytes()).hexdigest(),'new_oracle_needed':active.source_sha!=load(OLD/'readiness.json')['active']['source_sha']})
        print(json.dumps({'source_sha':active.source_sha,'generation':active.generation_id,'mapper':active.mapper_version,'semantic_ready':active.semantic_ready,'max_claim_needs':current.research.max_claim_needs}),flush=True)
    finally:
        await built.close()
    files={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['kernel','knowledge','integrations'] for p in sorted((ROOT/folder).rglob('*.py'))}
    try:
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(
            ['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit('Cannot record checkout identity; no fingerprint was written.') from error
    runner.save('code-fingerprint.json',{'head':head,'dirty_candidate':dirty,'file_sha256':files,'combined_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'retained_runner_sha256':hashlib.sha256((ROOT/'tests/knowledge_live/retrieval_scenario_checks.py').read_bytes()).hexdigest(),'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    boundary=load(OLD/'live-boundary.json')
    for key in list(boundary):
        if key.startswith('actual_') or key in ['resolved_models','completed_at','retrieval_reached','resumes_performed']:
            boundary.pop(key)
    boundary.update(status='authorized_not_run',active_source_sha=active.source_sha,active_generation_id=active.generation_id,consent={'source':'New explicit user evaluation rerun request conveyed by coordinator','user_reply':'Then retest (fresh scoped repeat conveyed by coordinator)' ,'scope':'Fresh original RS-02 and RS-03 starts on merged code887c66d3; max12 calls each/24 total, max120active seconds/case; no graph writes, activation, embeddings or Langfuse','recorded_at':datetime.now(timezone.utc).isoformat()})
    runner.save('live-boundary.json',boundary)

async def main(mode):
    if mode=='prepare':
        return await prepare()
    if mode=='neutral':
        return await runner.neutral()
    if mode=='kernel-controls':
        return await runner.kernel_controls()
    if mode=='kernel-valid':
        return await runner.kernel_controls('clarify',('RS-03',),'kernel-valid-controls.json')
    if mode in {'live-RS-02','live-RS-03'}:
        identifier=mode.removeprefix('live-')
        if (OUT/(identifier+'.live-started.json')).exists():
            raise SystemExit('Live receipt exists; refusing repeated provider calls.')
        os.environ['LEAFCUTTER_RS_LIVE_CONSENT']='approved-RS-02-RS-03-24-calls'
        runner.save(identifier+'.live-started.json', {'started_at':datetime.now(timezone.utc).isoformat(),'consent':'authorized two-case retest','maximum_provider_calls':12})
        return await asyncio.wait_for(runner.live([identifier]), timeout=150)
    raise SystemExit('Unknown replay mode')

if __name__=='__main__':
    asyncio.run(main(sys.argv[1]))
