"""Run a frozen independent evaluation of the isolated retrieval-needs node.

One actual HTTP request per selected case, local receipts only. Expected labels
are read solely by the grader and never included in the provider request.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integrations.retrieval_needs_probe import NeedsCatalog, NeedsRequest, ProbeLimits, build_needs_batch, run_needs_probe
from kernel.providers.base import JevError
from kernel.providers.jev_http import HttpTransport
from kernel.providers.jev_wire import question_to_wire
from kernel.secrets import load_secrets

LOGGER = logging.getLogger(__name__)
DEFAULT_SET = ROOT / "docs/analysis/retrieval-needs-probe-2026-10-03/eval-cases.json"


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        LOGGER.exception("Cannot read evaluation artifact %s", path)
        raise


def write_text(path, text):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        LOGGER.exception("Cannot save evaluation artifact %s", path)
        raise


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        LOGGER.exception("Cannot fingerprint %s", path)
        raise


def make_request(case, dataset):
    return NeedsRequest(
        original_question=case["question"], context=case["context"], known_ids=case["known_ids"],
        source_scope={"repository": "leafcutter", "source_revision": "planning-probe-only",
                      "read_roots": ["docs", "kernel", "knowledge", "integrations"],
                      "allow_retrieval": False},
        catalog=NeedsCatalog.model_validate(dataset["catalog"]),
    )


def grade(case, result, physical_calls):
    """Evaluate preauthored exact predicates; no model judge and no post-hoc gold."""
    checks = []

    def check(name, passed, actual, expected):
        checks.append({"name": name, "passed": bool(passed), "actual": actual, "expected": expected})

    expected = case["expected"]
    selected = result["selections"]
    check("one_actual_http_request", physical_calls == result["provider_calls"] == 1, physical_calls, 1)
    check("original_question_unchanged", result["original_question"] == case["question"], result["original_question"], case["question"])
    for dimension, values in expected.get("include", {}).items():
        check(f"include.{dimension}", set(values) <= set(selected[dimension]), selected[dimension], values)
    for dimension, values in expected.get("exclude", {}).items():
        check(f"exclude.{dimension}", not (set(values) & set(selected[dimension])), selected[dimension], {"forbidden": values})
    for dimension in ("detail_mode", "completeness", "hierarchy_scope", "scope_resolution", "status"):
        if dimension in expected:
            check(dimension, result[dimension] in expected[dimension], result[dimension], expected[dimension])
    if result["detail_mode"] == "fields" and "required_fields_if_fields" in expected:
        values = expected["required_fields_if_fields"]
        check("required_fields_when_projecting", set(values) <= set(selected["required_fields"]), selected["required_fields"], values)
    if expected.get("needs_outside_catalog"):
        value = result["response"]["answers"]["needs_outside_catalog"]["probability"]
        check("unsupported_need_disclosed", value >= 0.7 and "needs_outside_catalog" in result["unresolved"], value, ">=0.7 and unresolved")
    candidates = set(case["known_ids"])
    literal_targets = {value for value in selected["target_ids"] if value in case["question"]}
    check("no_unoffered_id", set(selected["target_ids"]) <= candidates | literal_targets,
          selected["target_ids"], "literal or independently supplied observed candidate")
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def stamp(dataset_path, limits):
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        LOGGER.exception("Cannot pin Git revision")
        raise
    files = ["integrations/retrieval_needs_models.py", "integrations/retrieval_needs_questions.py",
             "integrations/retrieval_needs_probe.py", "scripts/evaluate_retrieval_needs_probe.py"]
    return {"created_at": datetime.now(UTC).isoformat(), "base_commit": commit,
            "dataset_sha256": digest(dataset_path), "files_sha256": {name: digest(ROOT / name) for name in files},
            "limits": limits.model_dump(mode="json"), "max_live_cases": 12,
            "tracing": "local-only; no tracer or Langfuse client instantiated", "retries": 0,
            "retrieval_executed": False, "expected_labels_sent_to_provider": False}


async def one_case(case, dataset, output, limits, key, model):
    request = make_request(case, dataset)
    batch = build_needs_batch(request)
    prefix = output / case["id"]
    write_json(prefix.with_suffix(".request.json"), request.model_dump(mode="json"))
    write_json(prefix.with_suffix(".expected.json"), {"expected": case["expected"], "human_gold": case["human_gold"]})
    receipt = {"case_id": case["id"], "question": case["question"], "started_at": datetime.now(UTC).isoformat(),
               "wire_questions": len(batch.questions), "physical_http_requests": [], "physical_http_responses": [],
               "wire_request": {"model": model, "state": batch.state,
                                "questions": {spec.id: question_to_wire(spec) for spec in batch.questions}}}

    async def on_request(http_request):
        body = json.loads(http_request.content)
        receipt["physical_http_requests"].append({"url": str(http_request.url), "method": http_request.method,
                                                  "at": datetime.now(UTC).isoformat(), "body": body})
        write_json(prefix.with_suffix(".receipt.json"), receipt)

    async def on_response(response):
        await response.aread()
        try:
            body = response.json()
        except ValueError:
            LOGGER.warning("Provider returned non-JSON response for %s", case["id"])
            body = {"non_json_body": True}
        receipt["physical_http_responses"].append({"status": response.status_code,
                                                  "request_id": response.headers.get("x-typesafe-request-id"), "body": body})
        write_json(prefix.with_suffix(".receipt.json"), receipt)

    start = time.perf_counter()
    result = None
    error = None
    async with httpx.AsyncClient(timeout=limits.timeout_seconds, event_hooks={"request": [on_request], "response": [on_response]}) as client:
        transport = HttpTransport(api_key=key, model=model, timeout_seconds=limits.timeout_seconds, client=client)
        try:
            typed = await run_needs_probe(request, transport, limits=limits)
            result = typed.model_dump(mode="json")
        except JevError as exc:
            LOGGER.warning("Provider/probe failed for %s: %s", case["id"], type(exc).__name__)
            error = {"type": type(exc).__name__, "message": str(exc)}
    receipt["elapsed_seconds"] = round(time.perf_counter() - start, 3)
    receipt["finished_at"] = datetime.now(UTC).isoformat()
    write_json(prefix.with_suffix(".receipt.json"), receipt)
    scored = grade(case, result, len(receipt["physical_http_requests"])) if result else {"passed": False, "checks": [], "invalid_run": True}
    record = {"case_id": case["id"], "question": case["question"], "origin": case["origin"], "human_gold": case["human_gold"],
              "result": result, "error": error, "grade": scored,
              "physical_http_calls": len(receipt["physical_http_requests"]), "wire_questions": len(batch.questions),
              "elapsed_seconds": receipt["elapsed_seconds"]}
    write_json(prefix.with_suffix(".result.json"), record)
    print(f"{case['id']}: {'PASS' if scored['passed'] else 'INVALID' if error else 'FAIL'}; HTTP calls={record['physical_http_calls']}; questions={len(batch.questions)}", flush=True)
    return record


def summarize(output, dataset):
    records = [read_json(path) for path in sorted(output.glob("N*.result.json"))]
    receipts = [read_json(output / f"{item['case_id']}.receipt.json") for item in records]
    summary = {"cases": len(records), "semantic_passes": sum(item["grade"]["passed"] for item in records),
               "invalid_runs": sum(bool(item["error"]) for item in records),
               "physical_http_calls": sum(item["physical_http_calls"] for item in records),
               "received_http_responses": sum(len(receipt["physical_http_responses"]) for receipt in receipts),
               "full_retrieval_scenarios_passed": 0, "scenario_applicability": dataset["scenario_applicability"], "results": records}
    write_json(output / "summary.json", summary)
    lines = ["# Isolated Jev retrieval-needs evaluation", "", "This tests only the proposed needs-selection step. It performs no retrieval and produces no final answer.", "",
             f"HTTP send attempts: **{summary['physical_http_calls']}**. Received HTTP responses: **{summary['received_http_responses']}**. Frozen planning cases attempted: **{len(records)}/12**. All-predicate passes: **{summary['semantic_passes']}**. Invalid runs: **{summary['invalid_runs']}**. A request event alone does not establish that the provider received or processed it.", "",
             "Expected decisions were authored and independently reviewed before any live response. Each field is evaluated against one shared question/context in a single provider request. Thresholds remain 0.7 selected, 0.3 rejected; intermediate options remain uncertain.", "",
             "| Case | Question | Result | Differences from preauthored expectation |", "|---|---|---|---|"]
    for item in records:
        failures = [check["name"] for check in item["grade"]["checks"] if not check["passed"]]
        lines.append(f"| {item['case_id']} | {item['question']} | {'PASS' if item['grade']['passed'] else 'INVALID' if item['error'] else 'FAIL'} | {', '.join(failures) or str(item['error'] or 'None')} |")
    for item in records:
        lines.extend(["", f"## {item['case_id']}: {item['question']}", "", f"**Expected:** {item['human_gold']}", ""])
        result = item["result"]
        if result:
            lines.extend(["| Dimension | Selected | Uncertain |", "|---|---|---|"])
            for dimension, values in result["selections"].items():
                lines.append(f"| {dimension} | {', '.join(values) or 'None'} | {', '.join(result['uncertain'][dimension]) or 'None'} |")
            for dimension in ("detail_mode", "completeness", "hierarchy_scope", "scope_resolution", "status"):
                lines.append(f"| {dimension} | {result[dimension]} | See raw choice distribution in the result |")
            lines.extend(["", f"Unresolved: {', '.join(result['unresolved']) or 'None'}. Physical HTTP calls: **{item['physical_http_calls']}**; classification questions in that one call: **{item['wire_questions']}**; model **{result['response']['model_id']}**; provider request `{result['response']['request_id']}`.", ""])
            for check in item["grade"]["checks"]:
                if not check["passed"]:
                    lines.append(f"- **Mismatch {check['name']}:** expected `{json.dumps(check['expected'])}`; actual `{json.dumps(check['actual'])}`.")
        else:
            lines.append(f"No valid decision: `{item['error']}`. This is not a semantic-quality result.")
        lines.extend(["", f"[Request]({item['case_id']}.request.json) · [Actual wire request/response receipt]({item['case_id']}.receipt.json) · [Expected vs actual]({item['case_id']}.result.json)"])
    lines.extend(["", "## Limits of this evidence", "", "The 29 original scenarios have a planning-only applicability map in summary.json. No full downstream scenario has been run by this probe. Topic membership, explicit allowed hierarchy levels, query choice, source completeness, evidence authority, retrieval budgets and final-answer correctness remain later work. An all-descendants need is retained separately from the proposed execution depth bound. `decided` means the interpretation is ready for later retrieval, not that its population or answer has been established. `needs_resolution` does not itself dispatch a human question.", ""])
    write_text(output / "results.md", "\n".join(lines))
    return summary


async def run(args):
    dataset = read_json(args.dataset)
    cases = [case for case in dataset["cases"] if not args.cases or case["id"] in args.cases]
    if not cases or len(cases) > 12:
        raise ValueError("Select between 1 and 12 preauthored cases")
    limits = ProbeLimits(**dataset["thresholds"])
    current = stamp(args.dataset, limits)
    previous = args.output / "freeze.json"
    if previous.exists():
        old = read_json(previous)
        for field in ("base_commit", "dataset_sha256", "files_sha256", "limits"):
            if old[field] != current[field]:
                raise ValueError(f"Frozen {field} changed; use a separate explicitly authorized experiment")
    else:
        write_json(previous, current)
    for case in cases:
        if (args.output / f"{case['id']}.result.json").exists():
            raise ValueError(f"Refusing to rerun recorded case {case['id']}")
    if not args.live:
        write_json(args.output / "prepared.json", [make_request(case, dataset).model_dump(mode="json") for case in cases])
        print(f"Prepared {len(cases)} cases; zero provider calls.")
        return
    secrets = load_secrets(start_dir=ROOT)
    if secrets.jev_api_key is None:
        raise ValueError("Configured Jev credential unavailable; no live evaluation performed")
    config = read_json(ROOT / "config/kernel_config.default.json")
    for case in cases:
        record = await one_case(case, dataset, args.output, limits, secrets.jev_api_key.get_secret_value(), config["jev"]["model"])
        summarize(args.output, dataset)
        if record["error"]:
            raise RuntimeError("A provider/validation failure stopped the batch; no retry or chunk fallback was attempted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_SET)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
