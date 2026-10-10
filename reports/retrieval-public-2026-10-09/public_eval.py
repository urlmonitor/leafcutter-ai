"""Bounded public-run controller: real Jev and external blind host responses.

No model answers or expected labels are synthesized here. Local mode replaces
database storage only with actual committed source bytes; Aura mode uses the
normal configured Neo4j adapter. All graph/catalog writes remain unauthorized.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from report_support.layout import receipt_path, require_unarchived_controller

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from kernel.bootstrap import EnvironmentOverrides, KernelEnvironment, build_environment
from kernel.contracts import ALL_MODELS, Actor, ActorKind, RunStatus, Scope, TaskInput, schema_ids
from kernel.contracts.run import RunEnvelope
from kernel.contracts.task import RevisionInfo
from kernel.observability.tracer import RecordingTracer
from kernel.persistence import open_checkpointer
from kernel.scheduler import STATE_MODELS, build_kernel_graph, run_config
from kernel.service import KernelService

DIRECTORY = Path(__file__).resolve().parent
OUTPUT = DIRECTORY / "public-evaluation"
ENV_FILE = ROOT.parents[1] / ".env"


def plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    raise TypeError(type(value).__name__)


def read(path):
    return json.loads(receipt_path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = receipt_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=plain) + "\n", encoding="utf-8")


def working_source_fingerprint():
    """Pin actual dirty runtime bytes separately from the committed data revision."""
    try:
        names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard",
            "kernel", "integrations", "knowledge", "config/capability_registry.json", "config/capability_registry.schema.json"],
            cwd=ROOT, text=True).splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Cannot enumerate runtime source; no valid evaluation fingerprint can be recorded") from exc
    paths = sorted({name for name in names if name.endswith((".py", ".json"))})
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths if (ROOT / name).is_file()}
    return {"files_sha256": hashes, "aggregate_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def accepted_hosts(envelope):
    """Count completed host-result usage, not host dispatch-budget reservations."""
    return sum(entry.get("calls", 0) for entry in envelope["usage_summary"]["usage"] if entry["provider"] == "host")


def config(case: dict[str, Any], mode: str, host_root: Path, revision: str) -> tuple[Path, TaskInput]:
    """Build the saved configuration and typed public task.

    Args:
        case: Predeclared public scenario.
        mode: Local-source or Aura backend selection.
        host_root: Bounded external-host artifact directory.
        revision: Committed source revision requested by the case.

    Returns:
        The configuration path and public task input."""
    body = read(ROOT / "config/kernel_config.default.json")
    body["paths"]["run_root"] = str(host_root / "kernel" / case["id"])
    body["knowledge"].update(backend="neo4j", repository_root=str(ROOT),
        repository_id="leafcutter" if mode == "aura" else "public-needs-acceptance",
        query_catalog_root=str(host_root / "catalog" / case["id"]) if case["catalog"] else None)
    body["sources"] = [{"id": "knowledge.graph", "kind": "graph_query", "categories": ["task_context"]}]
    body["entity_context"]["enabled"] = False
    body["context_enrichment"]["enabled"] = False
    body["langfuse"]["enabled"] = False
    body["memory"]["backend"] = "null"
    body["limits"].update(max_jev_calls=12, max_host_operations=3, max_retries=0, max_active_seconds=150)
    body["jev"].update(timeout_seconds=30)
    path = OUTPUT / f"{case['id']}.config.json"
    save(path, body)
    scope = Scope(workspace_id="public-retrieval-proof", repository_root=str(ROOT), read_roots=["docs"],
                  source_ids=["knowledge.graph"], revision=RevisionInfo(commit=revision))
    task = TaskInput(goal=case["question"], caller=Actor(id="public-retrieval-evaluator", kind=ActorKind.HOST),
        scope=scope, permissions=["read_repo"], input_payload_schema=schema_ids.RESEARCH_REQUEST,
        requested_output_schema=schema_ids.EVIDENCE_BUNDLE,
        input_payload={"question": case["question"], "evidence_needs_only": True,
            "evidence_needs": [{"id": "need.question", "category": "task_context", "priority": "required", "question": case["question"]}]})
    save(OUTPUT / f"{case['id']}.request.json", task)
    return receipt_path(path), task


def environment(case_id: str, mode: str) -> tuple[KernelEnvironment, RecordingTracer]:
    """Create the configured runtime and recording tracer.

    Args:
        case_id: Scenario whose saved configuration is loaded.
        mode: Local-source or Aura backend selection.

    Returns:
        The environment and its recording tracer."""
    tracer = RecordingTracer()
    seams = EnvironmentOverrides(tracer=tracer)
    if mode == "local":
        from knowledge.adapters.git_source import GitSourceResolver
        from knowledge.query_admission import QueryAdmission
        from knowledge.query_catalog import QueryCatalog
        from knowledge.service import KnowledgeService
        from tests.knowledge.public_retrieval_needs_support import REPOSITORY, SnapshotStorage
        body = read(OUTPUT / f"{case_id}.config.json")
        storage = SnapshotStorage()
        catalog = QueryCatalog(body["knowledge"]["query_catalog_root"]) if body["knowledge"]["query_catalog_root"] else None
        seams.knowledge_retriever = KnowledgeService(storage,
            source_resolver=GitSourceResolver(ROOT, REPOSITORY), query_catalog=catalog)
        seams.query_catalog = catalog
        seams.query_admission = QueryAdmission(catalog, storage, REPOSITORY) if catalog else None
    env = build_environment(config_path=receipt_path(OUTPUT / f"{case_id}.config.json"), env_file=ENV_FILE, overrides=seams)
    if env.jev_factory is None:
        raise ValueError("Live Jev credentials unavailable; no scripted replacement allowed")
    return env, tracer


async def receipt(case_id: str, step: str, env: KernelEnvironment, tracer: RecordingTracer, envelope: RunEnvelope) -> None:
    """Record the run state and any pending external-host interaction.

    Args:
        case_id: Scenario identifier.
        step: Start or resume attempt label.
        env: Active kernel environment.
        tracer: Recorded provider calls.
        envelope: Actual public run result."""
    save(OUTPUT / f"{case_id}.{step}.json", envelope)
    save(OUTPUT / f"{case_id}.current.json", envelope)
    save(OUTPUT / f"{case_id}.{step}.trace.json", tracer.calls)
    async with open_checkpointer(env.run_root, extra_types=[*ALL_MODELS, *STATE_MODELS]) as saver:
        state = await build_kernel_graph(saver).aget_state(run_config(envelope.run_id, env.config.limits.langgraph_recursion_limit))
    save(OUTPUT / f"{case_id}.{step}.state.json", {name: state.values.get(name) for name in ("requests", "results", "evidence", "findings", "invocations")})
    if envelope.status is RunStatus.WAITING_HOST:
        location = Path(read(OUTPUT / "location.json")["host_root"])
        packet_path = location / "packets" / f"{case_id}.{step}.json"
        save(packet_path, envelope.pending_interaction)
        record = {"case_id": case_id, "step": step, "packet_path": str(packet_path),
            "input_artifact_refs": envelope.pending_interaction.input_artifact_refs,
            "response_destination": str(location / "responses" / f"{case_id}.{step}.json")}
        save(OUTPUT / f"{case_id}.pending-host.json", record)
        print("HOST", json.dumps(record), flush=True)
    print(case_id, envelope.status.value, "actual_jev_calls", envelope.usage_summary.jev_calls,
          "accepted_host_operations", accepted_hosts(envelope.model_dump(mode="json")), flush=True)


def remaining_host_budget():
    accepted = sum(accepted_hosts(read(path)) for path in OUTPUT.rglob("P*.current.json"))
    if accepted >= 16:
        raise ValueError("Approved sixteen-public-host-operation ceiling reached")


async def prepare(mode: str) -> None:
    """Prepare each declared public scenario once.

    Args:
        mode: Local-source or Aura backend selection."""
    if (OUTPUT / "location.json").exists():
        raise ValueError("One-shot public preparation exists; no silent repeat")
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Cannot resolve the source revision; public evaluation preparation stopped") from exc
    host_root = Path(tempfile.mkdtemp(prefix="leafcutter-public-host-"))
    save(OUTPUT / "location.json", {"host_root": str(host_root), "source_mode": mode, "code_revision": revision,
        "model_transport": "production TypeSafeJevAdapter + blind external host packets", "expected_labels_sent": False})
    save(OUTPUT / "working-source-freeze.json", working_source_fingerprint())
    records = []
    for case in read(DIRECTORY / "plan.json")["public_cases"]:
        requested = "0" * 40 if case["id"] == "P06" else revision
        _, task = config(case, mode, host_root, requested)
        env, tracer = environment(case["id"], mode)
        try:
            result = await asyncio.wait_for(KernelService(env).start_run(task), timeout=160)
            await receipt(case["id"], "started", env, tracer, result)
            if result.status is RunStatus.WAITING_HOST:
                records.append(read(OUTPUT / f"{case['id']}.pending-host.json"))
        finally:
            await env.aclose()
    save(host_root / "manifest.json", records)
    print("Host-only manifest:", host_root / "manifest.json")


async def resume(case_id: str, human: bool) -> None:
    """Resume an unchanged run with its predeclared external response.

    Args:
        case_id: Public scenario to resume.
        human: Whether to supply the predeclared human clarification."""
    current = read(OUTPUT / f"{case_id}.current.json")
    location = read(OUTPUT / "location.json")
    if read(OUTPUT / "working-source-freeze.json") != working_source_fingerprint():
        raise ValueError("Runtime working source changed after public packet preparation")
    packet = current["pending_interaction"]
    if packet is None:
        raise ValueError("Run is already terminal")
    if human:
        if current["status"] != "waiting_human":
            raise ValueError("No pending human clarification")
        case = next(case for case in read(DIRECTORY / "plan.json")["public_cases"] if case["id"] == case_id)
        response = {"free_text": case["clarification"]}
        actor = {"id": "human:predeclared-scenario-input", "kind": "human"}
    else:
        remaining_host_budget()
        if current["status"] != "waiting_host":
            raise ValueError("No pending host response")
        pending = read(OUTPUT / f"{case_id}.pending-host.json")
        response = read(Path(pending["response_destination"]))
        actor = {"id": "host:blind-public-retrieval", "kind": "host"}
    submission = {"run_id": current["run_id"], "interaction_id": packet["id"],
        "expected_state_revision": current["state_revision"], "actor": actor,
        "response_schema_id": packet["output_schema_id"], "response": response}
    step = f"resume-{current['state_revision']}"
    save(OUTPUT / f"{case_id}.{step}.submission.json", submission)
    env, tracer = environment(case_id, location["source_mode"])
    try:
        result = await asyncio.wait_for(KernelService(env).resume_run(current["run_id"], submission), timeout=160)
        await receipt(case_id, step, env, tracer, result)
    finally:
        await env.aclose()


async def main():
    require_unarchived_controller()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "resume"))
    parser.add_argument("--mode", choices=("local", "aura"), default="local")
    parser.add_argument("--case", choices=[f"P{i:02}" for i in range(1, 7)])
    parser.add_argument("--human", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        await prepare(args.mode)
    elif args.case:
        await resume(args.case, args.human)
    else:
        parser.error("resume requires --case")


if __name__ == "__main__":
    asyncio.run(main())
