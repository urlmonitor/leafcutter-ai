"""Additional read-only public continuation controls for the pinned retest."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
os.environ['LEAFCUTTER_ENV_FILE']='C:/Users/Hendrik/Code/leafcutter/.env'
from tests.knowledge_live import retrieval_scenario_checks as retained
retained.OUT=OUT
from knowledge.config import KnowledgeConfig,build_retriever
from knowledge.contracts import KnowledgeRetrievalRequest

async def main():
    if (OUT/'continuation-controls.json').exists():
        raise SystemExit('Receipt exists; refusing overwrite')
    active=json.loads((OUT/'active-controls.json').read_text())
    request=deepcopy(active['cases'][0]['request'])
    request['request_id']='retest-pages'
    request['budget'].update(max_results=5,max_candidates=200,max_rounds=10)
    port=build_retriever(KnowledgeConfig(backend='neo4j',repository_id='leafcutter',repository_root=str(ROOT)))
    pages=[]
    try:
        for number in range(1,5):
            started=time.perf_counter()
            result=await port.retrieve(KnowledgeRetrievalRequest.model_validate(request))
            pages.append({'page':number,'request':deepcopy(request),'actual_response':result.model_dump(mode='json'),'seconds':round(time.perf_counter()-started,3)})
            retained.save('continuation-controls.json',{'source':active['source'],'pages':pages,'actors':{'Jev':'not invoked','storage':'actual read-only Aura'},'entrypoint':'configured KnowledgeService.retrieve','complete_journey':False})
            if result.continuation is None:
                break
            request['continuation']=result.continuation
        leaves=deepcopy(active['cases'][0]['request'])
        leaves['request_id']='retest-terminal-leaves'
        leaves['answer_requirements']['scope']['inclusion']='terminal_leaves'
        leaves['answer_requirements']['original_question']='At the pinned source revision, list only terminal descendants of TQ-500f, excluding every parent, with work_status.'
        result=await port.retrieve(KnowledgeRetrievalRequest.model_validate(leaves))
        retained.save('leaf-control.json',{'request':leaves,'actual_response':result.model_dump(mode='json'),'scope':'typed terminal-leaf facet, not model interpretation of the original vague question'})
        print(json.dumps({'pages':[{'page':row['page'],'count':len(row['actual_response']['evidence']),'answer':row['actual_response']['answer']['status'],'exact_total':row['actual_response']['answer']['completeness']['exact_total'],'more':row['actual_response']['continuation'] is not None} for row in pages],'terminal_leaves':len(result.evidence),'leaf_answer':result.answer}))
    finally:
        await port.close()

if __name__=='__main__':
    asyncio.run(main())
