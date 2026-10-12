"""Render the preserved public baseline receipts without changing their judgments."""
import html
import json
import subprocess
from pathlib import Path

from report_support.layout import href, receipt_path

import yaml

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
OUT = BASE / "public-evaluation"


def read(path):
    return json.loads(receipt_path(path).read_text(encoding="utf-8"))


def dump(path, value):
    path = receipt_path(path)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def esc(value):
    return html.escape(str(value))


def details(title, value):
    return f"<details><summary>{esc(title)}</summary><pre>{esc(json.dumps(value, indent=2, ensure_ascii=False))}</pre></details>"


def main():
    records = []
    for case in read(BASE / "plan.json")["public_cases"]:
        ident = case["id"]
        envelope = read(OUT / f"{ident}.current.json")
        states = sorted(OUT.rglob(f"{ident}.*.state.json"), key=lambda path: path.stat().st_mtime)
        state = read(states[-1])
        results = list(state["results"].values())
        needs = [result["output_payload"] for result in results
                 if result["output_schema_id"] == "leafcutter.retrieval_needs_output.v1"]
        diagnostics = [result["diagnostics"] for result in results if "knowledge_status" in result["diagnostics"]]
        traces = [item for path in sorted(OUT.rglob(f"{ident}.*.trace.json")) for item in read(path)]
        choices = [item["data"] for item in traces if item["name"] == "jev.knowledge.operation_select"]
        executions = [item["data"]["metadata"] for item in traces if item["name"] == "knowledge.retrieve"]
        payload = envelope["output"]["payload"]
        records.append({"id": ident, "question": case["question"], "catalog_enabled": case["catalog"],
            "status": envelope["status"], "complete_answer": envelope["status"] == "completed",
            "original_expectation": case["assertion"], "needs": needs, "selector": choices,
            "source_executions": executions, "diagnostics": diagnostics,
            "evidence": payload.get("evidence", []), "findings": payload.get("findings", []),
            "assessments": payload["assessments"], "limitations": payload["limitations"],
            "jev_calls": envelope["usage_summary"]["jev_calls"],
            "accepted_host_results": sum(entry["calls"] for entry in envelope["usage_summary"]["usage"] if entry["provider"] == "host"),
            "receipt": href(f"public-evaluation/{ident}.current.json")})
    source_path = "docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml"
    revision = read(OUT / "location.json")["code_revision"]
    try:
        source_bytes = subprocess.check_output(["git", "show", f"{revision}:{source_path}"], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Cannot read the pinned source; baseline rendering stopped without replacement evidence") from exc
    source = yaml.safe_load(source_bytes)
    comparison = {"source_sha": revision, "path": source_path, "criteria": source["criteria"],
                  "test_spec": source["test_spec"], "finding": "Canonical test_spec exists; unknown availability in P01/P02 is disclosure loss, not canonical absence."}
    dump(BASE / "baseline-source-comparison.json", comparison)
    summary = {"mode": "Real TypeSafe Jev plus independent blind host; local storage over 18 actual committed AC mappings and real Git source disclosure. No live Neo4j positive claim.",
        "source_sha": revision, "working_source_hash": read(OUT / "working-source-freeze.json")["aggregate_sha256"],
        "complete_positive_answers": sum(record["complete_answer"] for record in records[:5]), "positive_cases": 5,
        "negative_stale_control_passed": records[5]["status"] == "partial" and not records[5]["evidence"],
        "honest_noncomplete_cases": sum(record["status"] == "partial" for record in records),
        "actual_jev_calls": sum(record["jev_calls"] for record in records),
        "accepted_host_results": sum(record["accepted_host_results"] for record in records),
        "host_model_id": None, "host_provider_request_count": None, "jev_model_id": "jev-1.13.0",
        "scope": {"graph_writes": 0, "catalog_writes": 0, "telemetry_exports": 0, "prompt_or_threshold_changes": 0},
        "cases": records,
        "known_gaps": [
            "P01/P02: criteria are retrieved and synthesized with citations, but requested authored test_spec does not survive disclosure; final answer remains partial.",
            "P03/P04: correct proposed get_ac_descendants operation falls below unchanged probability gate (0.76/0.75 versus 0.80); no source query executes.",
            "P05: host chooses discovery_needed without a known root; runtime cannot establish that exhaustive population. The frozen clarification expectation is unmet. Choosing discovery is not necessarily wrong; the missing discovery capability is a functional gap.",
            "Controlled test separately demonstrates default six-result budget cannot enumerate all fifteen TQ-500f descendants. Live baseline did not reach this stage.",
            "Aura connection works but canonical publication failed before a ready generation, so no live graph positive was run."
        ]}
    dump(BASE / "baseline-summary.json", summary)
    intro = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Public retrieval: observed baseline</title>
    <style>body{{font:16px/1.55 system-ui;max-width:1080px;margin:40px auto;padding:0 22px;color:#1e293b;background:#f8fafc}}h1,h2{{line-height:1.2}}section{{background:white;border:1px solid #dbe3ed;border-radius:12px;padding:24px;margin:24px 0}}.badge{{padding:4px 10px;background:#fef3c7;border-radius:6px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:14px;border-radius:6px;font-size:12px}}summary{{cursor:pointer;font-weight:600;margin-top:12px}}a{{color:#1d4ed8}}li{{margin:8px 0}}.note{{background:#e0f2fe;padding:16px;border-radius:10px}}small{{color:#64748b}}</style>
    <h1>What retrieval actually did</h1><p>Preserved baseline, 9 October 2026. <b>0 of 5 positive cases reached a complete answer.</b> The stale-source control passed; all six runs reported their limitations.</p>
    <p class=note>Actual TypeSafe Jev decisions + independent blind host responses. Repository evidence comes from 18 committed AC files through the real mapper and Git disclosure, with local storage replacing Neo4j. This proves the public workflow against that source subset, not a successful live Aura query.</p>
    <p>{summary['actual_jev_calls']} actual Jev calls · {summary['accepted_host_results']} accepted host results · no graph/catalog writes · no telemetry export.</p>
    <p><a href=baseline-summary.json>Machine report</a> · <a href=public-evaluation/working-source-freeze.json>Exact working-code hashes</a> · <a href=baseline-source-comparison.json>Actual canonical fields</a> · <a href=public-evaluation/host-artifacts/manifest.json>Archived host receipts</a></p>
    <p>Source revision <code>{esc(revision)}</code>. Host model identity and provider-call counts were not available; no model identity was invented.</p>
    <h2>Separate interpretation evaluation</h2><p>The unchanged 12 accepted gold cases and four independently authored holdouts passed semantic checks after their 16 responses were accepted through real host waits. This is field-interpretation evidence, not an end-to-end answer score. An initial controller actor-ID error rejected the same bytes before interpretation; corrected envelopes reused them without regeneration.</p><p><a href=needs-evaluation/controller-envelope-repair/summary.json>Authoritative 12 + 4 receipt</a></p>"""
    chunks = [intro]
    for record in records:
        needs = record["needs"][-1]
        fields = needs["selections"]
        operations = [choice["output"]["answers"]["operation"] for choice in record["selector"]]
        bound = [{"operation": item.get("knowledge_selected_operation"), "arguments": item.get("knowledge_selected_arguments")}
                 for item in record["diagnostics"] if "knowledge_selected_operation" in item]
        chunks.append(f"<section id={record['id']}><h2>{record['id']} · <span class=badge>{esc(record['status'])}</span></h2><p><b>{esc(record['question'])}</b></p><small>Catalog/admission {'enabled' if record['catalog_enabled'] else 'disabled'}; caller supplied a question and trusted source scope, no operation or answer fields.</small><ol>")
        chunks.append(f"<li><b>Host interpreted the need.</b> Types: {esc(', '.join(fields['entity_types']))}; targets: {esc(', '.join(fields['target_ids']) or 'none known')}; fields: {esc(', '.join(fields['required_fields']))}; scope resolution: {esc(needs['scope_resolution'])}." + details("Complete accepted fields", needs) + "</li>")
        chunks.append("<li><b>Jev selected from the available operations.</b> " + (esc('; '.join(f"{op['choice']} (probability {op['probabilities'].get(op['choice'])}, confidence {op['confidence']})" for op in operations)) if operations else "No Jev operation selection ran; interpretation left an unsupported population.") + details("Selected arguments and actual provider receipt", {"bound": bound, "selector": record["selector"]}) + "</li>")
        chunks.append(f"<li><b>Read source evidence.</b> {len(record['evidence'])} evidence items; {len(record['source_executions'])} recorded source retrieval spans." + details("Source execution and citations", record["source_executions"]) + "</li>")
        for evidence in record["evidence"]:
            chunks.append(f"<p><b>{esc(evidence['source']['title'])}</b><br><small>{esc(evidence['source']['locator'])}</small></p><pre>{esc(evidence['excerpt'])}</pre>")
        chunks.append("<li><b>Assess the original obligations.</b> " + details("Structured answer requirements and missing facts", record["assessments"]) + "</li>")
        if record["findings"]:
            chunks.append("<li><b>Host summarized cited evidence.</b><ul>" + ''.join(f"<li>{esc(item['claim'])}</li>" for item in record["findings"]) + "</ul></li>")
        chunks.append("<li><b>Return with limitations.</b><ul>" + ''.join(f"<li>{esc(item)}</li>" for item in record["limitations"]) + f"</ul><a href={record['receipt']}>Final public receipt</a></li></ol></section>")
    chunks.append("<h2>Remaining gaps</h2><ul>" + ''.join(f"<li>{esc(item)}</li>" for item in summary["known_gaps"]) + "</ul><p>This baseline is immutable evidence of the original attempt. Any code repair and retest is reported separately.</p></html>")
    (BASE / "baseline.html").write_text(''.join(chunks), encoding="utf-8")
    print("Stored baseline-summary.json and baseline.html")


if __name__ == "__main__":
    main()
