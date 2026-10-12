"""Prepare real kernel host packets and grade externally produced needs responses.

This controller does not generate model answers. A separate blind host reads only
the emitted packet/input artifacts and writes response files for submission.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integrations.retrieval_needs_llm import build_llm_needs_task, make_experiment_service
from kernel.contracts import Actor, ActorKind, HostWorkRequest, RunStatus
from kernel.contracts.retrieval_needs import RetrievalNeedsRequest
from kernel.contracts.task import Scope
from kernel.interaction import SubmissionRejected
from scripts.evaluate_retrieval_needs_probe import make_request, read_json, write_json, write_text

LOGGER = logging.getLogger(__name__)
DATASET = ROOT / "docs/analysis/retrieval-needs-probe-2026-10-03/eval-cases.json"
COMPARISON = ROOT / "docs/analysis/retrieval-needs-llm-2026-10-03/evaluation-contract.json"


def file_hash(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        LOGGER.exception("Cannot fingerprint %s", path)
        raise


def copy_bytes(source, destination):
    """Preserve an operational artifact exactly, without adding evaluation data."""
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    except OSError:
        LOGGER.exception("Cannot preserve operational artifact %s", source)
        raise


def verify_baseline():
    comparison = read_json(COMPARISON)
    if file_hash(DATASET) != comparison["baseline_sha256"]:
        raise ValueError("The original evaluation set changed")
    return read_json(DATASET), comparison


def shared_grade(case, result):
    """The predeclared common semantic predicates; transport is graded separately."""
    checks = []

    def add(name, passed, actual, expected):
        checks.append({"name": name, "passed": bool(passed), "actual": actual, "expected": expected})

    expected, selected = case["expected"], result["selections"]
    add("original_question", result["original_question"] == case["question"], result["original_question"], case["question"])
    for dimension, values in expected.get("include", {}).items():
        add("include." + dimension, set(values) <= set(selected[dimension]), selected[dimension], values)
    for dimension, values in expected.get("exclude", {}).items():
        add("exclude." + dimension, not (set(values) & set(selected[dimension])), selected[dimension], {"forbidden": values})
    for dimension in ("detail_mode", "completeness", "hierarchy_scope", "scope_resolution", "status"):
        if dimension in expected:
            add(dimension, result[dimension] in expected[dimension], result[dimension], expected[dimension])
    if result["detail_mode"] == "fields" and "required_fields_if_fields" in expected:
        wanted = expected["required_fields_if_fields"]
        add("required_fields_when_projecting", set(wanted) <= set(selected["required_fields"]), selected["required_fields"], wanted)
    if expected.get("needs_outside_catalog"):
        add("unsupported_need_disclosed", result["status"] == "needs_resolution" and "needs_outside_catalog" in result["unresolved"],
            result["unresolved"], "Explicit unmet catalog dimension, unresolved; no synthetic confidence")
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def overlay_grade(case_id, result, comparison):
    checks = []
    for rule in comparison["overlay"]:
        if case_id not in rule["cases"]:
            continue
        passed = True
        if "forbid_required_fields" in rule:
            passed = not (set(rule["forbid_required_fields"]) & set(result["selections"]["required_fields"]))
        if "forbid_completeness" in rule:
            passed = result["completeness"] not in rule["forbid_completeness"]
        if rule.get("if_entity_type") in result["selections"]["entity_types"]:
            passed = rule["require_document_type"] in result["selections"]["document_types"]
        checks.append({"id": rule["id"], "passed": passed, "reason": rule["reason"]})
    return {"applicable": bool(checks), "passed": all(check["passed"] for check in checks), "checks": checks}


def freeze(output):
    files = ["scripts/evaluate_retrieval_needs_llm.py", "kernel/contracts/retrieval_needs.py",
             "kernel/capabilities/host/retrieval_needs.py", "integrations/retrieval_needs_llm.py",
             "kernel/capabilities/host/base.py", "kernel/capabilities/host/registry.py",
             "kernel/contracts/schema_ids.py", "kernel/contracts/schema_catalog.py", "kernel/contracts/__init__.py",
             "kernel/interaction/submissions.py", "kernel/schemas/leafcutter.retrieval_needs_request.v1.schema.json",
             "kernel/schemas/leafcutter.retrieval_needs_output.v1.schema.json"]
    try:
        base_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        LOGGER.exception("Cannot pin the kernel baseline")
        raise
    manifest = {"base_commit": base_commit, "dataset_sha256": file_hash(DATASET), "comparison_sha256": file_hash(COMPARISON),
                "files_sha256": {name: file_hash(ROOT / name) for name in files},
                "expected_labels_in_host_input": False, "automatic_context_enrichment": False,
                "controller_calls_models": False, "model_tokens_and_provider_calls": "unknown unless actually reported"}
    destination = output / "freeze.json"
    if destination.exists() and read_json(destination) != manifest:
        raise ValueError("Frozen experiment code/expectations changed")
    write_json(destination, manifest)


async def prepare(output, dataset):
    freeze(output)
    if (output / "host-location.json").exists():
        raise ValueError("Refusing to overwrite prepared host packets")
    host_root = Path(tempfile.mkdtemp(prefix="leafcutter-needs-llm-host-")).resolve()
    write_json(output / "host-location.json", {"root": str(host_root), "manifest": str(host_root / "manifest.json")})
    manifest = []
    for case in dataset["cases"]:
        request_payload = make_request(case, dataset).model_dump(mode="json")
        # The old typed catalog carried its own version; the host request owns
        # the schema version and accepts only the five offered-option mappings.
        request_payload["catalog"].pop("schema_version", None)
        request = RetrievalNeedsRequest.model_validate(request_payload)
        service = make_experiment_service(ROOT, host_root / "kernel-runs")
        try:
            scope = Scope(workspace_id="needs-llm-eval", repository_root=str(ROOT), read_roots=["docs"])
            task = build_llm_needs_task(request, scope, Actor(id="evaluation-controller", kind=ActorKind.HOST))
            envelope = await service.start_run(task)
            if envelope.status is not RunStatus.WAITING_HOST or not isinstance(envelope.pending_interaction, HostWorkRequest):
                raise ValueError(f"{case['id']} did not reach its actual host wait")
            packet = envelope.pending_interaction
            write_json(output / f"{case['id']}.started.json", envelope.model_dump(mode="json"))
            packet_path = host_root / f"packets/{case['id']}.packet.json"
            write_json(packet_path, packet.model_dump(mode="json"))
            write_json(output / f"host-packets/{case['id']}.packet.json", packet.model_dump(mode="json"))
            artifact_path = Path(packet.input_artifact_refs[0])
            copy_bytes(artifact_path, output / f"inputs/{case['id']}.input.json")
            actual = read_json(artifact_path)
            if actual["request"]["original_question"] != case["question"]:
                raise ValueError("The actual host artifact lost the original question")
            if actual["request"]["context"] != case["context"]:
                raise ValueError("The actual host context differs from the frozen input")
            enrichment = actual.get("context_enrichment") or {}
            if enrichment and (enrichment.get("status") != "disabled" or enrichment.get("files_scanned") != 0
                               or enrichment.get("evidence") or enrichment.get("sources_consulted")
                               or enrichment.get("caller_context", {}).get("conversation")
                               or enrichment.get("caller_context", {}).get("observations")):
                raise ValueError("Unexpected automatic enrichment would invalidate this comparison")
            manifest.append({"case_id": case["id"], "packet_path": str(packet_path.resolve()),
                             "input_artifact_refs": packet.input_artifact_refs,
                             "response_destination": str((host_root / f"responses/{case['id']}.json").resolve())})
        finally:
            await service._env.aclose()
    write_json(host_root / "manifest.json", manifest)
    write_json(output / "host-packets/manifest.json", manifest)
    print(f"Prepared {len(manifest)} real kernel host waits; controller model calls=0.", flush=True)


async def submit(output, dataset, comparison, actor_id):
    freeze(output)
    host_root = Path(read_json(output / "host-location.json")["root"])
    for case in dataset["cases"]:
        record_path = output / f"{case['id']}.result.json"
        if record_path.exists():
            raise ValueError(f"Refusing to resubmit {case['id']}")
        started = read_json(output / f"{case['id']}.started.json")
        packet = started["pending_interaction"]
        response = read_json(host_root / f"responses/{case['id']}.json")
        write_json(output / f"responses/{case['id']}.json", response)
        raw = {"run_id": started["run_id"], "interaction_id": packet["id"],
               "expected_state_revision": started["state_revision"], "actor": {"id": actor_id, "kind": "host"},
               "relayed_by": "isolated-evaluation-controller", "response_schema_id": packet["output_schema_id"],
               "response": response}
        write_json(output / f"{case['id']}.submission.json", raw)
        service = make_experiment_service(ROOT, host_root / "kernel-runs")
        try:
            try:
                envelope = await service.resume_run(started["run_id"], raw)
                error = None
            except SubmissionRejected as exc:
                LOGGER.warning("Host submission rejected for %s", case["id"])
                envelope = await service.get_run(started["run_id"])
                error = {"type": "SubmissionRejected", "message": str(exc)}
            result = dict(envelope.output.payload) if envelope.output is not None else None
            record = {"case_id": case["id"], "question": case["question"], "human_gold": case["human_gold"],
                      "actor_id": actor_id, "model_id": result.get("model_id") if result else None,
                      "underlying_model_requests": None, "tokens": None,
                      "error": error, "result": result, "envelope": envelope.model_dump(mode="json"),
                      "shared_semantics": shared_grade(case, result) if result else {"passed": False, "invalid": True, "checks": []},
                      "overlay": overlay_grade(case["id"], result, comparison) if result else {"applicable": False, "passed": False, "checks": []}}
            write_json(record_path, record)
            print(f"{case['id']}: {'PASS' if record['shared_semantics']['passed'] else 'INVALID' if error else 'FAIL'}", flush=True)
        finally:
            await service._env.aclose()
    summarize(output, dataset, comparison)


def summarize(output, dataset, comparison):
    records = [read_json(path) for path in sorted(output.glob("N*.result.json"))]
    prior = read_json(ROOT / "reports/retrieval-needs-probe-2026-10-03-live-approved/summary.json")
    cases = {case["id"]: case for case in dataset["cases"]}
    old = [{"case_id": record["case_id"], "shared_semantics": shared_grade(cases[record["case_id"]], record["result"]),
            "overlay": overlay_grade(record["case_id"], record["result"], comparison)} for record in prior["results"]]
    summary = {"cases": len(records), "shared_semantic_passes": sum(record["shared_semantics"]["passed"] for record in records),
               "accepted_host_operations": sum(record["envelope"]["usage_summary"]["host_operations"] or 0 for record in records),
               "jev_calls": sum(record["envelope"]["usage_summary"]["jev_calls"] or 0 for record in records),
               "original_jev_score_unchanged": "7/12 frozen original checks", "prior_jev_shared_and_overlay": old,
               "underlying_model_requests": None, "tokens": None, "results": records,
               "scenario_applicability": dataset["scenario_applicability"]}
    summary["prior_jev_shared_semantic_passes"] = sum(row["shared_semantics"]["passed"] for row in old)
    summary["overlay_totals"] = {
        name: {"passes": sum(row["overlay"]["applicable"] and row["overlay"]["passed"] for row in rows),
               "applicable": sum(row["overlay"]["applicable"] for row in rows)}
        for name, rows in (("host_llm", records), ("prior_jev", old))}
    write_json(output / "summary.json", summary)
    lines = ["# Isolated host-LLM retrieval-needs evaluation", "",
             f"Shared semantic predicates passed: **{summary['shared_semantic_passes']}/{len(records)}**. Accepted host operations: **{summary['accepted_host_operations']}**. Jev calls: **{summary['jev_calls']}**.", "",
             "The controller submitted actual externally produced host responses through kernel validation and resumed the original waits. Model identity, underlying model request count and tokens remain unknown unless supplied by an actual host receipt. A completed interpretation is not completed retrieval.", "",
             "The host was a blind fresh-context Codex agent, not a direct configured generative-provider endpoint. One host-agent turn may process multiple packets.", "",
             "| Engine | Shared semantic predicates | Separate prospective overlay |", "|---|---|---|",
             f"| Blind Codex host | {summary['shared_semantic_passes']}/{len(records)} | {summary['overlay_totals']['host_llm']['passes']}/{summary['overlay_totals']['host_llm']['applicable']} applicable cases |",
             f"| Saved Jev outputs | {summary['prior_jev_shared_semantic_passes']}/{len(old)} | {summary['overlay_totals']['prior_jev']['passes']}/{summary['overlay_totals']['prior_jev']['applicable']} applicable cases |", "",
             "The original Jev score remains **7/12** under its original frozen checks; this shared comparison and the separate overlay do not replace it.", "",
             "| Case | Shared semantics | Prospective minimality/consistency overlay | Differences |", "|---|---|---|---|"]
    for record in records:
        failures = [item["name"] for item in record["shared_semantics"]["checks"] if not item["passed"]]
        overlay = record["overlay"]
        overlay_text = "n/a" if not overlay["applicable"] else "PASS" if overlay["passed"] else "FAIL"
        lines.append(f"| {record['case_id']} | {'PASS' if record['shared_semantics']['passed'] else 'FAIL'} | {overlay_text} | {', '.join(failures) or record['error'] or 'None'} |")
    for record in records:
        lines.extend(["", f"## {record['case_id']}: {record['question']}", "", f"Expected: {record['human_gold']}", ""])
        if record["result"]:
            result = record["result"]
            lines.extend(["| Dimension | Selected | Uncertain |", "|---|---|---|"])
            for dimension, values in result["selections"].items():
                lines.append(f"| {dimension} | {', '.join(values) or 'None'} | {', '.join(result['uncertain'][dimension]) or 'None'} |")
            for dimension in ("detail_mode", "completeness", "hierarchy_scope", "scope_resolution", "status"):
                lines.append(f"| {dimension} | {result[dimension]} | |")
            lines.extend(["", f"Unresolved: {', '.join(result['unresolved']) or 'None'}.", f"Host rationale: {result['rationale']}"])
        lines.extend(["", f"[Actual host packet](host-packets/{record['case_id']}.packet.json) | [Exact operational input](inputs/{record['case_id']}.input.json) | [Host response](responses/{record['case_id']}.json) | [Kernel submission]({record['case_id']}.submission.json) | [Result and grade]({record['case_id']}.result.json)"])
    lines.extend(["", "## Comparison limits", "", "The prior Jev 7/12 score is unchanged. Shared semantic predicates remove provider-specific probability/transport assertions and use an explicit unsupported-need marker for the host path. The separate prospective overlay was authored before LLM outputs and applied to saved Jev outputs without rerunning Jev. Twelve host operations do not imply twelve underlying model calls. All 29 original scenarios retain their planning-only applicability dispositions; no full retrieval scenario is claimed.", ""])
    write_text(output / "results.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "submit", "summarize"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--actor-id", default="codex:/root/needs_llm_host")
    args = parser.parse_args()
    args.output = args.output.resolve()
    dataset, comparison = verify_baseline()
    if args.action == "prepare":
        asyncio.run(prepare(args.output, dataset))
    elif args.action == "submit":
        asyncio.run(submit(args.output, dataset, comparison, args.actor_id))
    else:
        summarize(args.output, dataset, comparison)


if __name__ == "__main__":
    main()
