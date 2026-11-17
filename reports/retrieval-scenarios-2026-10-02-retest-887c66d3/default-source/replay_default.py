"""Authorized two-case default-source lane; no product changes or host resumes."""
from pathlib import Path
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
OUT=Path(__file__).resolve().parent
pin=json.loads((OUT/'source-pin.json').read_text(encoding='utf-8'))
SOURCE=Path(pin['source_root'])
sys.path.insert(0,str(SOURCE))
from tests.knowledge_live import retrieval_scenario_checks as runner
runner.OUT=OUT
runner.ROOT=SOURCE
os.environ['LEAFCUTTER_ENV_FILE']='C:/Users/Hendrik/Code/leafcutter/.env'
os.environ['LEAFCUTTER_RS_LIVE_CONSENT']='approved-RS-02-RS-03-24-calls'
async def main(identifier):
    if identifier not in {'RS-02','RS-03'}:
        raise SystemExit('Only the two authorized questions are permitted.')
    if (OUT/(identifier+'.live-started.json')).exists():
        raise SystemExit('One-shot guard already exists; no repeat permitted.')
    config=(OUT/'live-default.config.json').read_bytes()
    (OUT/'live-canary.config.json').write_bytes(config)
    runner.save(identifier+'.live-started.json',{'at':datetime.now(timezone.utc).isoformat(),'maximum_calls':8,'lane':'actual default source policy','code_sha':pin['code_sha']})
    try:
        await asyncio.wait_for(runner.live([identifier]),timeout=150)
    except Exception as error:
        runner.save(identifier+'.execution-error.json',{'exception_type':type(error).__name__,'detail':'Failure retained; no automatic retry or substituted result. Inspect local trace/checkpoints if no response receipt was saved.'})
        raise
if __name__=='__main__':
    asyncio.run(main(sys.argv[1]))
