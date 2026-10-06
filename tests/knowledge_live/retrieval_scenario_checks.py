"""Manual, read-only scenario evaluation; never changes product code or graph data."""
from __future__ import annotations
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/retrieval-scenarios-2026-10-02"

def json_value(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)

def scrub(value):
    if isinstance(value, dict):
        return {key: ({"redacted": True, "length": len(item), "sha256": hashlib.sha256(item.encode()).hexdigest()}
                      if key == "continuation" and isinstance(item, str) else scrub(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value

def save(name, data):
    destination = OUT / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(scrub(data), indent=2, ensure_ascii=False, default=json_value), encoding="utf-8")

async def neutral():
    from knowledge.config import KnowledgeConfig, build_retriever
    from knowledge.contracts import KnowledgeRetrievalRequest
    from knowledge.evaluation import evaluate
    from knowledge.service import KnowledgeService
    from tests.knowledge.query_answer_contract_acceptance_corpus import ControlledStorageBoundary, ControlledDisclosureBoundary
    built = build_retriever(KnowledgeConfig(backend="neo4j", repository_id="leafcutter", repository_root=str(ROOT)))
    storage = ControlledStorageBoundary(built.backend)
    service = KnowledgeService(storage, built.source_resolver, cursor_secret=b"scenario-evaluation-local-only")
    port = ControlledDisclosureBoundary(service, storage)
    try:
        raw = (ROOT / "docs/analysis/2026-10-01-repository-query-evaluation-runnable.json").read_text(encoding="utf-8")
        pack = json.loads(raw.replace("independent-answer-qa-a9a29716a5d6", "leafcutter"))
        historical = await built.backend.get_revision("leafcutter", pack["source_sha"])
        for case in pack["cases"]:
            if case["id"].startswith("RQE-05"):
                manifest = historical.model_dump(mode="json", exclude={"nodes", "edges"})
                if case["id"].endswith("-N"):
                    manifest["supported_kinds"] = [kind for kind in manifest["supported_kinds"] if kind != "Test"]
                    manifest["supported_relationships"] = [edge for edge in manifest["supported_relationships"] if edge != "covered_by"]
                case["assessment"]["manifest"] = manifest
        save("historical-control-requests.json", pack)
        result = await evaluate(port, pack)
        save("historical-controls.json", {
            "recorded_at": datetime.now(timezone.utc).isoformat(), "entry_point": "knowledge.evaluation.evaluate -> KnowledgeService.retrieve / public supplied-evidence assess",
            "actors": {"Jev": "not invoked", "database": "actual read-only Aura", "trace": "disabled"},
            "source": historical.model_dump(mode="json", exclude={"nodes", "edges"}),
            "adaptations": ["Authorized repository namespace changed from original isolated QA namespace to leafcutter.",
                "Capability-fit controls use the actually retained historical manifest, with Test/covered_by withheld only for the negative.",
                "Named controls reuse existing evidence-withholding/outage adapter; no oracle values fill results."],
            "report": result})
        active = await built.backend.active("leafcutter")
        cases = []
        wanted = {"RQE-01-P": ["RS-05", "RS-20"], "RQE-01-N": ["RS-19"],
                  "RQE-02-P": ["RS-03", "RS-22"], "RQE-02-N": ["RS-27"],
                  "RQE-03-P": ["RS-11"], "RQE-03-N": ["RS-15", "RS-27"],
                  "RQE-06-P": ["RS-28"], "RQE-06-N": ["RS-25"]}
        for case in pack["cases"]:
            if case["id"] not in wanted:
                continue
            request = deepcopy(case["request"])
            request["revision"] = active.source_sha
            started = time.perf_counter()
            answer = await port.retrieve(KnowledgeRetrievalRequest.model_validate(request))
            row = {"case_id": case["id"], "scenario_ids": wanted[case["id"]],
                   "scope": "existing typed-service facet; not natural-language or whole target journey",
                   "request": request, "actual_response": answer.model_dump(mode="json"),
                   "seconds": round(time.perf_counter()-started, 3),
                   "independent_verdict": "pending PO/oracle review"}
            cases.append(row)
            save("active-controls.json", {"source": active.model_dump(mode="json", exclude={"nodes", "edges"}), "cases": cases,
                "actors": {"Jev": "not invoked", "database": "actual read-only Aura", "negative boundaries": "named withholding/outage only"},
                "entry_point": "KnowledgeService.retrieve via existing ControlledDisclosureBoundary",
                "database_writes": False})
        print(json.dumps({"historical": result["denominators"], "active_cases": len(cases)}))
    finally:
        await service.close()

async def live(identifiers):
    if os.environ.get("LEAFCUTTER_RS_LIVE_CONSENT") != "approved-RS-02-RS-03-24-calls":
        raise SystemExit("Explicit two-case repository-context transmission consent is absent; no client constructed.")
    if not identifiers or any(item not in {"RS-02", "RS-03"} for item in identifiers):
        raise SystemExit("Only the two explicitly prepared live canaries are allowed.")
    from kernel.bootstrap import build_environment, EnvironmentOverrides
    from kernel.contracts import TaskInput
    from kernel.observability.tracer import RecordingTracer
    from kernel.service import KernelService
    for identifier in identifiers:
        tracer = RecordingTracer()
        env = build_environment(config_path=OUT/"live-canary.config.json",
            env_file=Path("C:/Users/Hendrik/Code/leafcutter/.env"),
            overrides=EnvironmentOverrides(tracer=tracer))
        task = TaskInput.model_validate_json((OUT/"requests"/(identifier+".live.json")).read_text(encoding="utf-8"))
        started = time.perf_counter()
        try:
            result = await KernelService(env).start_run(task)
            save(identifier+".live-response.json", {"scenario_id": identifier, "request": task.model_dump(mode="json"),
                "entry_point": "KernelService.start_run via actual build_environment", "actors": {"Jev":"real TypeSafe jev-latest",
                "host":"not substituted; waits retained", "human":"not substituted; waits retained","tracer":"local RecordingTracer; no remote export"},
                "actual_response": result.model_dump(mode="json"), "seconds":round(time.perf_counter()-started,3),
                "trace": [asdict(call) for call in tracer.calls], "independent_verdict":"pending independent review"})
            print(json.dumps({"scenario_id": identifier, "status":result.status.value,"seconds":round(time.perf_counter()-started,3)}),flush=True)
        finally:
            await env.aclose()

async def kernel_controls(selection="get_entities", identifiers=("RS-02", "RS-03"), filename="kernel-controls.json"):
    from kernel.bootstrap import build_environment, EnvironmentOverrides
    from kernel.contracts import TaskInput
    from kernel.observability.tracer import RecordingTracer
    from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer
    from kernel.service import KernelService
    rows=[]
    for identifier in identifiers:
        jev=ScriptedJev()
        jev.script("kernel.route", "route.*", choice_answer("research"))
        jev.script("research.plan_needs", "need.*", lambda q,b: noul_answer(0.99 if q.id=="need.task_context" else 0.01))
        jev.script("research.assess", "conflict", noul_answer(0.01))
        jev.script("research.assess", "evaluable", noul_answer(0.95))
        jev.script("research.assess", "answers.*", noul_answer(0.95))
        required = "work_status" if identifier=="RS-02" else "criteria"
        jev.script("knowledge.answer_contract", "field.*", lambda q,b: noul_answer(0.99 if q.id=="field."+required else 0.01))
        jev.script("knowledge.answer_contract", "population", choice_answer("clarify" if identifier=="RS-02" else "returned_entities"))
        jev.script("knowledge.answer_contract", "inclusion", choice_answer("clarify"))
        jev.script("knowledge.answer_contract", "root", choice_answer("clarify" if identifier=="RS-02" else "KM-500c-2"))
        jev.script("knowledge.answer_contract", "level.*", noul_answer(0.01))
        jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
        jev.script("knowledge.query_target", "kind", choice_answer("AcceptanceCriterion"))
        jev.script("knowledge.query_select", "query", choice_answer(selection))
        tracer=RecordingTracer()
        env=build_environment(config_path=OUT/"live-canary.config.json",
            overrides=EnvironmentOverrides(tracer=tracer,jev_factory=lambda:jev))
        task=TaskInput.model_validate_json((OUT/"requests"/(identifier+".live.json")).read_text(encoding="utf-8"))
        started=time.perf_counter()
        try:
            response=await KernelService(env).start_run(task)
            row={"scenario_id":identifier, "request":task.model_dump(mode="json"),
                "actual_response":response.model_dump(mode="json"),"seconds":round(time.perf_counter()-started,3),
                "entry_point":"KernelService.start_run via actual build_environment",
                "actors":{"Jev":"ScriptedJev; fixed finite interpretations/choices, not live quality",
                    "database":"actual Aura immutable generation","host":"none","human":"none","tracer":"local RecordingTracer"},
                "jev_batches":[batch.model_dump(mode="json") for batch in jev.batches],
                "trace":[asdict(call) for call in tracer.calls],"independent_verdict":"pending review"}
            rows.append(row)
            save(filename,{"cases":rows,"limitations":["Scripted judgments prove mechanism behavior only; not question understanding or semantic sufficiency."]})
            print(json.dumps({"scenario_id":identifier,"status":response.status.value,"output":response.output.model_dump(mode="json") if response.output else None}),flush=True)
        finally:
            await env.aclose()

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["neutral","live","kernel-controls","kernel-valid"])
    parser.add_argument("--case", action="append", default=[])
    args=parser.parse_args()
    asyncio.run(neutral() if args.mode=="neutral" else kernel_controls() if args.mode=="kernel-controls" else kernel_controls("clarify", ("RS-03",), "kernel-valid-controls.json") if args.mode=="kernel-valid" else live(args.case))
