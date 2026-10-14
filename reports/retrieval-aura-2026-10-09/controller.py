"""One-shot real-Aura public proof; validate is entirely offline.

prepare verifies an explicitly identified published generation and freezes source
oracles. start/resume perform actual bounded model and graph reads. No action
publishes a graph, activates a catalog, exports telemetry or substitutes a model.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from proof_support import (BASE, ROOT, BUDGET, CASES, case_config, exact_sha, git, host_count,
    read, readiness, run_directory, runtime_fingerprint, save, sha256, source_oracles,
    task_input, totals, utc_now, verify_frozen, verify_limits)

sys.path.insert(0, str(ROOT))


def environment(config: Path, env_file: Path):
    """Compose real production ports; RecordingTracer is the only override."""
    from kernel.bootstrap import EnvironmentOverrides, build_environment
    from kernel.observability.tracer import RecordingTracer

    if os.environ.get("LEAFCUTTER_KERNEL_RUN_ROOT"):
        raise ValueError("Unset the process run-root override before this isolated evaluation")
    configured = os.environ.get("LEAFCUTTER_ENV_FILE")
    if configured and Path(configured).resolve() != env_file.resolve():
        raise ValueError("Kernel and knowledge environment-file references must agree")
    os.environ["LEAFCUTTER_ENV_FILE"] = str(env_file.resolve())
    tracer = RecordingTracer()
    env = build_environment(config_path=config, env_file=env_file,
                            overrides=EnvironmentOverrides(tracer=tracer))
    if env.jev_factory is None:
        raise ValueError("Actual configured Jev is unavailable; no scripted replacement is allowed")
    return env, tracer


def validate_offline():
    """Validate all public request/config shapes without building an environment."""
    from kernel.config import KernelConfig
    from kernel.contracts import TaskInput
    from kernel.contracts.schema_catalog import validate_payload

    directory = BASE / "offline-validation-unused"
    for case in CASES:
        KernelConfig.model_validate(case_config(case, directory))
        task = TaskInput.model_validate(task_input(case, "0" * 40))
        validate_payload(task.input_payload_schema, task.input_payload)
        assert task.permissions == ["read_repo"]
        assert "knowledge" not in task.input_payload and "answer_requirements" not in task.input_payload
    for invalid in ("HEAD", "main", "", None):
        try:
            exact_sha(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Implicit or invalid source revision accepted")
    assert BUDGET["runs"] * BUDGET["jev_calls_per_run"] == BUDGET["jev_calls_total"]
    assert BUDGET["runs"] * BUDGET["host_results_per_run"] == BUDGET["host_results_total"]
    print(json.dumps({"validated_cases": len(CASES), "backend_calls": 0, "provider_calls": 0,
                      "source_oracles_frozen": False, "limits": BUDGET}))


async def prepare(args):
    """Verify publication before deriving immutable oracles or any host/model dispatch."""
    from kernel.contracts import TaskInput

    source = exact_sha(args.source_sha)
    writer = exact_sha(args.writer_sha)
    if not args.generation_id or not args.publication_run_url or not args.env_file:
        raise ValueError("Explicit generation, writer SHA, publication run URL and env-file reference are required")
    if not args.publication_run_url.startswith("https://github.com/urlmonitor/leafcutter-ai/actions/runs/"):
        raise ValueError("An attributable canonical publication workflow URL is required")
    git("cat-file", "-e", source + "^{commit}")
    git("cat-file", "-e", writer + "^{commit}")
    output = run_directory(args.run)
    if output.exists():
        raise ValueError("This one-shot preparation already exists; preserve it")
    output.mkdir(parents=True)
    env_file = Path(args.env_file).resolve()
    if not env_file.is_file():
        raise ValueError("External environment-file reference is unavailable")
    probe = output / "readiness-config.json"
    save(probe, case_config(CASES[0], output))
    env, _ = environment(probe, env_file)
    try:
        observed = await asyncio.wait_for(readiness(env, source, args.generation_id), 30)
    except Exception as exc:
        save(output / "preparation-failure.json", {"observed_at": utc_now(),
            "error_type": type(exc).__name__, "provider_calls": 0, "oracles_frozen": False})
        raise
    finally:
        await env.aclose()
    save(output / "readiness.json", observed)
    oracles = source_oracles(source)
    save(output / "source-oracles.json", oracles)
    hashes = {}
    for case in CASES:
        directory = output / case["id"]
        save(directory / "config.json", case_config(case, output, observed["database"]))
        task = TaskInput.model_validate(task_input(case, "0" * 40 if case["negative"] else source))
        save(directory / "request.json", task)
        hashes[case["id"]] = {name: sha256(directory / name) for name in ("config.json", "request.json")}
    plan = {"prepared_at": utc_now(), "source_mode": "real Aura + immutable GitSourceResolver",
        "repository_id": "leafcutter", "source_sha": source, "generation_id": args.generation_id,
        "writer_code_sha": writer, "publication_run_url": args.publication_run_url,
        "publication_metadata_source": "Explicit orchestrator-supplied workflow provenance; readiness independently read.",
        "database": observed["database"], "env_file_reference": str(env_file),
        "cases": list(CASES), "case_hashes": hashes, "limits": BUDGET,
        "oracle_sha256": sha256(output / "source-oracles.json"),
        "expectations": {"interpretation": "Named AC; criteria and authored test_spec required; immutable source scope.",
            "execution": "All chosen fields fulfilled with matching source/generation/locators; complete canonical criteria/spec.",
            "functional_success": "Interpretation sufficient AND execution fulfilled AND final public run completed.",
            "negative": "A04 must actually execute a retrieval and return stale for its unavailable exact revision."},
        "host_policy": "Fresh blind host sees only actual packet and input refs; no gold, tests, old responses or scores.",
        "rerun_policy": "No favorable model retries; interrupted attempts remain evidence, not automatically repeated."}
    save(output / "plan.json", plan)
    save(output / "working-source-freeze.json", runtime_fingerprint())
    print(json.dumps({"prepared": str(output), "source_sha": source, "generation_id": args.generation_id,
                      "provider_calls": 0, "host_packets": 0}))


def case_for(case_id: str) -> dict:
    """Require one of the four originally frozen cases."""
    return next(case for case in CASES if case["id"] == case_id)


async def record(output: Path, case: dict, step: str, env, tracer, envelope):
    """Retain raw outcomes, checkpoints and exact host handoffs for independent scoring."""
    from kernel.contracts import ALL_MODELS, RunStatus
    from kernel.persistence import open_checkpointer
    from kernel.scheduler import STATE_MODELS, build_kernel_graph, run_config

    directory = output / case["id"] / step
    save(directory / "envelope.json", envelope)
    save(directory / "trace.json", tracer.calls)
    save(output / case["id"] / "current.json", envelope, replace=True)
    save(output / case["id"] / "current-step.json", {"step": step}, replace=True)
    async with open_checkpointer(env.run_root, extra_types=[*ALL_MODELS, *STATE_MODELS]) as saver:
        checkpoint = await build_kernel_graph(saver).aget_state(
            run_config(envelope.run_id, env.config.limits.langgraph_recursion_limit))
    values = {key: checkpoint.values.get(key) for key in ("requests", "results", "evidence", "findings", "invocations")}
    save(directory / "state.json", values)
    if envelope.status is RunStatus.WAITING_HOST:
        packet = envelope.pending_interaction
        host = directory / "host"
        save(host / "packet.json", packet)
        inputs = []
        for index, reference in enumerate(packet.input_artifact_refs):
            original = Path(reference)
            target = host / "inputs" / f"{index}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(original.read_bytes())
            inputs.append({"original_ref": reference, "archived_path": str(target), "sha256": sha256(target)})
        pending = {"case_id": case["id"], "step": step, "packet_path": str(host / "packet.json"),
            "input_artifact_refs": list(packet.input_artifact_refs), "archived_inputs": inputs,
            "response_destination": str(host / "response.json"),
            "dispatch_provenance_destination": str(host / "dispatch.json"), "model_id": None}
        save(directory / "pending-host.json", pending)
        print("HOST", json.dumps(pending), flush=True)
    catalog = output / case["id"] / "catalog"
    if catalog.exists():
        raise ValueError("Read-only proof unexpectedly created a catalog artifact")
    verify_limits(output)
    manifests = []
    for current in output.glob("A*/current.json"):
        result = read(current)
        if result["status"] == "waiting_host":
            cursor = read(current.parent / "current-step.json")["step"]
            manifests.append(read(current.parent / cursor / "pending-host.json"))
    save(output / "host-manifest.json", manifests, replace=True)
    print(json.dumps({"case": case["id"], "status": envelope.status.value, **totals(output)}), flush=True)


def submission(output: Path, case_id: str) -> tuple[dict, str]:
    """Use the exact current durable wait and fresh external response, never old host bytes."""
    current = read(output / case_id / "current.json")
    if current["status"] != "waiting_host":
        raise ValueError("This case has no current host wait; human clarifications are not fabricated")
    if host_count(current) >= BUDGET["host_results_per_run"]:
        raise ValueError("Per-case accepted-host ceiling reached")
    if totals(output)["accepted_host_results"] >= BUDGET["host_results_total"]:
        raise ValueError("Global accepted-host ceiling reached")
    previous = read(output / case_id / "current-step.json")["step"]
    pending = read(output / case_id / previous / "pending-host.json")
    response = read(Path(pending["response_destination"]))
    provenance = read(Path(pending["dispatch_provenance_destination"]))
    packet = current["pending_interaction"]
    if (provenance["interaction_id"] != packet["id"]
            or provenance["run_id"] != current["run_id"]
            or provenance["packet_sha256"] != sha256(Path(pending["packet_path"]))):
        raise ValueError("Host dispatch provenance does not match this exact wait")
    request = {"run_id": current["run_id"], "interaction_id": packet["id"],
        "expected_state_revision": current["state_revision"],
        "actor": {"id": "host:blind-aura-proof", "kind": "host"},
        "response_schema_id": packet["output_schema_id"], "response": response}
    return request, f"resume-{current['state_revision']:04}"


async def execute(args):
    """Start or resume one public run once, preserving interruption and refusal evidence."""
    from kernel.contracts import TaskInput
    from kernel.service import KernelService

    output, case = run_directory(args.run), case_for(args.case)
    verify_frozen(output, case["id"])
    plan = read(output / "plan.json")
    if sha256(output / "source-oracles.json") != plan["oracle_sha256"]:
        raise ValueError("Frozen source oracle changed")
    verify_limits(output)
    if case["id"] in totals(output)["usage_incomplete_cases"]:
        raise ValueError("An interrupted case requires explicit reconciliation, not automatic replay")
    if args.action == "start":
        if (output / case["id"] / "started").exists():
            raise ValueError("Case start already attempted; no automatic repeat")
        payload, step = read(output / case["id"] / "request.json"), "started"
    else:
        payload, step = submission(output, case["id"])
    directory = output / case["id"] / step
    save(directory / "attempt.json", {"action": args.action, "started_at": utc_now()})
    if args.action == "resume":
        save(directory / "submission.json", payload)
    env, tracer = environment(output / case["id"] / "config.json", Path(plan["env_file_reference"]))
    try:
        checked = await asyncio.wait_for(readiness(env, plan["source_sha"], plan["generation_id"]), 30)
        if checked["database"] != plan["database"]:
            raise ValueError("Database identity changed after preparation")
        save(directory / "readiness.json", checked)
        operation = (KernelService(env).start_run(TaskInput.model_validate(payload)) if args.action == "start"
                     else KernelService(env).resume_run(payload["run_id"], payload))
        envelope = await asyncio.wait_for(operation, timeout=160)
        await record(output, case, step, env, tracer, envelope)
    except Exception as exc:
        save(directory / "failure.json", {"observed_at": utc_now(), "error_type": type(exc).__name__,
            "outcome": ("Inconclusive: active source or generation drifted from the frozen publication."
                if type(exc).__name__ == "ActiveGenerationDrift" else
                "Unfinished or rejected attempt; usage may be incomplete; do not replay automatically.")})
        save(directory / "failure-trace.json", tracer.calls)
        raise
    finally:
        await env.aclose()


def record_dispatch(args):
    """Bind actual orchestrator-reported agent dispatch metadata to one exact host packet."""
    output = run_directory(args.run)
    if not args.case or not args.agent_id or not args.dispatched_at:
        raise ValueError("Case, actual agent ID and actual UTC dispatch time are required")
    timestamp = datetime.fromisoformat(args.dispatched_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Dispatch timestamp must include its timezone")
    current = read(output / args.case / "current.json")
    if current["status"] != "waiting_host":
        raise ValueError("There is no host wait to associate with this dispatch")
    step = read(output / args.case / "current-step.json")["step"]
    pending = read(output / args.case / step / "pending-host.json")
    save(Path(pending["dispatch_provenance_destination"]), {
        "case_id": args.case, "run_id": current["run_id"],
        "interaction_id": current["pending_interaction"]["id"], "agent_id": args.agent_id,
        "dispatched_at": timestamp.isoformat(), "registered_at": utc_now(), "model_id": args.model_id,
        "packet_sha256": sha256(Path(pending["packet_path"])), "inputs": pending["archived_inputs"],
        "provenance_source": "Actual dispatch metadata supplied by the supervising orchestrator",
        "blindness_policy": "Only current host packets/input refs; no oracle, old responses or grading feedback"})
    print(json.dumps({"recorded_host_dispatch": pending["dispatch_provenance_destination"]}))


async def main():
    """Dispatch explicit offline preparation, bounded execution or read-only scoring."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "prepare", "start", "resume", "dispatch", "score"))
    parser.add_argument("--run")
    parser.add_argument("--case", choices=[case["id"] for case in CASES])
    parser.add_argument("--source-sha")
    parser.add_argument("--generation-id")
    parser.add_argument("--writer-sha")
    parser.add_argument("--publication-run-url")
    parser.add_argument("--env-file")
    parser.add_argument("--agent-id")
    parser.add_argument("--dispatched-at")
    parser.add_argument("--model-id")
    args = parser.parse_args()
    if args.action == "validate":
        validate_offline()
        return
    if not args.run:
        parser.error("--run is required")
    if args.action == "prepare":
        await prepare(args)
    elif args.action == "dispatch":
        record_dispatch(args)
    elif args.action == "score":
        from score_support import score
        score(run_directory(args.run))
    elif not args.case:
        parser.error("--case is required for start/resume")
    else:
        await execute(args)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__,
            "outcome": "Stopped. Inspect preserved local receipts; do not retry automatically."}), file=sys.stderr)
        raise SystemExit(1) from None

