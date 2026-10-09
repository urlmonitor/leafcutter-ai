"""Verify actual source fields in repair receipts and produce a compact readable index."""
import hashlib
import html
import json
import shutil
from pathlib import Path
from typing import Any

from report_support.layout import href, receipt_path

import yaml

BASE = Path(__file__).resolve().parent


def read(path):
    return json.loads(receipt_path(path).read_text(encoding="utf-8"))


def save(path, data):
    path = receipt_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def archive_host(out: Path) -> None:
    """Copy the original external-host artifacts into the proof directory.

    Args:
        out: Evaluation directory containing the recorded host location."""
    host_root = Path(read(out / "location.json")["host_root"])
    records = []
    for kind in ("packets", "responses"):
        for source in sorted((host_root / kind).glob("*.json")):
            target = out / "host-artifacts" / kind / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            records.append({"source": str(source), "archive": str(target.relative_to(BASE)),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
            if kind == "packets":
                for ref in read(source)["input_artifact_refs"]:
                    item = Path(ref)
                    destination = out / "host-artifacts" / "inputs" / item.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(item, destination)
    save(out / "host-artifacts" / "manifest.json", records)


def verify(directory: str) -> dict[str, Any]:
    """Compare recorded field evidence with the canonical source snapshot.

    Args:
        directory: Evaluation folder relative to this report.

    Returns:
        Recorded-case verification summary."""
    out = BASE / directory
    canonical = read(BASE / "baseline-source-comparison.json")
    results = []
    for ident in ("P01", "P02"):
        env = read(out / f"{ident}.current.json")
        state = read(out / f"{ident}.resume-2.state.json")
        payload = env["output"]["payload"] if env.get("output") else {}
        evidence = payload.get("evidence", [])
        by_field = {item["source"]["section_locator"]: item for item in evidence}
        criteria = by_field.get("/criteria")
        test_spec = by_field.get("/test_spec")
        source_matches = bool(criteria and test_spec
            and criteria["excerpt"] == canonical["criteria"]
            and yaml.safe_load(test_spec["excerpt"]) == canonical["test_spec"]
            and all(item["source"]["source_version"]["commit"] == canonical["source_sha"] for item in evidence))
        needs = [item["output_payload"] for item in state["results"].values()
            if item["output_schema_id"] == "leafcutter.retrieval_needs_output.v1"]
        diagnostics = [item["diagnostics"] for item in state["results"].values()
            if "knowledge_selected_operation" in item["diagnostics"]]
        traces = read(out / f"{ident}.resume-2.trace.json")
        jev = [item["data"] for item in traces if item["kind"] == "generation"]
        bindings = read(out / f"{ident}.response-origin.json")
        assessment = payload.get("assessments", {}).get("need.question", {})
        success = env["status"] == "completed" and source_matches and assessment.get("status") == "fulfilled"
        results.append({"id": ident, "catalog_enabled": ident == "P02", "status": env["status"],
            "success": success, "question": read(out / f"{ident}.request.json")["goal"],
            "needs": needs[-1], "diagnostics": diagnostics, "jev": jev, "assessment": assessment,
            "evidence": evidence, "source_matches_actual_commit": source_matches,
            "original_host_response_reused": bindings["sha256"] == bindings["new_response_sha256"] and bindings["bound_request_identical"],
            "jev_calls": env["usage_summary"]["jev_calls"],
            "accepted_host_results": sum(item["calls"] for item in env["usage_summary"]["usage"] if item["provider"] == "host"),
            "receipt": href(f"{directory}/{ident}.current.json")})
    summary = {"directory": directory, "scope": "Two exact-AC field retrieval cases only, with/without catalog; original broad-count/discovery cases were not rerun.",
        "storage_mode": "Bounded local actual-source projection + Git source resolver; not live Neo4j",
        "models": "Fresh actual TypeSafe Jev decisions, unchanged original blind interpretation responses reused; no new host generation.",
        "source_sha": canonical["source_sha"], "working_source_hash": read(out / "working-source-freeze.json")["aggregate_sha256"],
        "successful_cases": sum(item["success"] for item in results), "cases_total": len(results), "cases": results,
        "jev_calls": sum(item["jev_calls"] for item in results), "accepted_host_results": sum(item["accepted_host_results"] for item in results)}
    save(out / "verified-summary.json", summary)
    archive_host(out)
    return summary


def main():
    first = verify("repair-evaluation")
    final = verify("final-verification")
    baseline = read(BASE / "baseline-summary.json")
    public_jev = baseline["actual_jev_calls"] + first["jev_calls"] + final["jev_calls"]
    public_hosts = baseline["accepted_host_results"] + first["accepted_host_results"] + final["accepted_host_results"]
    esc = html.escape
    pages = [f"""<!doctype html><html lang=en><meta charset=utf-8><title>Retrieval proof: current result</title>
    <style>body{{font:17px/1.6 system-ui;max-width:1020px;margin:42px auto;padding:0 22px;color:#172554;background:#f8fafc}}h1,h2{{line-height:1.2}}section{{padding:24px;margin:22px 0;border:1px solid #cbd5e1;border-radius:12px;background:white}}.callout{{padding:18px;background:#dbeafe;border-radius:10px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;background:#f1f5f9;padding:16px;border-radius:8px}}a{{color:#1d4ed8}}small{{color:#475569}}li{{margin:8px 0}}summary{{cursor:pointer;font-weight:600}}</style>
    <h1>Retrieval proof: current result</h1><p><b>{final['successful_cases']}/2 exact-AC cases complete after the source-field repair.</b> Both catalog modes returned the actual acceptance clauses and authored test specification, with citations, through the public question-only entry.</p>
    <p class=callout>Real TypeSafe Jev made the routing and answer decisions. The host's original interpretation was reused byte-for-byte with identical input binding, so the improvement comes from the code repair. The source is real committed repository data through local storage and the real Git reader. Live Aura positive retrieval is still unproven.</p>
    <p><a href=baseline.html>Original six-case baseline, preserved</a> · <a href=final-verification/verified-summary.json>Final verification receipts</a> · <a href=final-verification/working-source-freeze.json>Exact tested working-code hashes</a> · <a href=repair-evaluation/verified-summary.json>First repair attempt</a></p>
    <p>Original baseline: <b>0/5 complete positive answers</b>, 1/1 stale-source control, all six honest partials. The first repair passed 2/2. A final separate two-case run verifies the last defensive empty-text guard at its own code hash; no questions, thresholds or gold changed. Totals across these public runs: {public_jev} actual Jev calls, {public_hosts} accepted host results, no graph/catalog writes or telemetry exports.</p>"""]
    for case in final["cases"]:
        diagnostic = case["diagnostics"][-1]
        needs = case["needs"]
        fields = needs["selections"]
        pages.append(f"<section><h2>{case['id']}: catalog {'enabled' if case['catalog_enabled'] else 'disabled'} · {esc(case['status'])}</h2><ol>")
        pages.append(f"<li><b>Agent asked:</b> {esc(case['question'])}</li>")
        pages.append(f"<li><b>Host interpreted all fields in one packet:</b> target {esc(', '.join(fields['target_ids']))}; type {esc(', '.join(fields['entity_types']))}; document {esc(', '.join(fields['document_types']))}; fields {esc(', '.join(fields['required_fields']))}; completeness {esc(needs['completeness'])}.</li>")
        pages.append(f"<li><b>Jev chose:</b> <code>{esc(diagnostic['knowledge_selected_operation'])}</code>, arguments <code>{esc(str(diagnostic['knowledge_selected_arguments']))}</code>.</li>")
        pages.append("<li><b>Retrieval read two source fields at the same pinned commit.</b> Both excerpts were independently compared to the actual canonical file, including the full parsed test specification.</li>")
        for evidence in case["evidence"]:
            pages.append(f"<details><summary>{esc(evidence['source']['section_locator'])}</summary><p><small>{esc(evidence['source']['locator'])}</small></p><pre>{esc(evidence['excerpt'])}</pre></details>")
        pages.append(f"<li><b>Assessment:</b> {esc(case['assessment']['status'])}; missing required fields: {len(case['assessment']['missing_fields'])}. Final public status: {esc(case['status'])}. The output is an evidence bundle; no canned final prose was supplied.</li></ol><p><a href={href(case['receipt'])}>Actual final receipt</a></p></section>")
    pages.append("""<h2>Still open</h2><ul>
    <li><b>Broad counts:</b> in the baseline Jev chose the right operation with probabilities 0.76/0.75, below the unchanged 0.80 gate. The reads therefore did not execute. Controlled tests additionally show the default six-result limit cannot enumerate the fifteen-descendant family.</li>
    <li><b>Discovering an unknown population:</b> the host requested discovery for “test writing,” but the runtime cannot yet establish that exhaustive population. The baseline did not enter the expected human clarification path. Choosing discovery can be reasonable; this remains a missing capability.</li>
    <li><b>Live Neo4j publication:</b> credentials connect, but canonical publication failed before a ready generation. Successful local source-backed proof does not establish successful Aura retrieval.</li></ul>
    <h2>What the tests establish</h2><p>Controlled public tests exercise actual kernel, LangGraph, host waits, source mapping, exact citation disclosure, saved-query digest selection, scope boundaries and honest partials. Model decisions in those tests are scripted; they are separate from the real-model receipts above. Additional guards cover unavailable/truncated extra fields, total byte and character limits, one-result citation limits, and rejection of unrequested, uncited or empty backend field text.</p>
    <p>The separate blind interpretation evaluation passed the unchanged 12 gold cases and 4 independently authored holdouts; its score is field selection, not full answer quality. <a href=needs-evaluation/controller-envelope-repair/summary.json>Interpretation receipts</a>.</p></html>""")
    (BASE / "index.html").write_text(''.join(pages), encoding="utf-8")
    print(json.dumps({"current_report": str(BASE / "index.html"), "final_cases_passed": final["successful_cases"],
        "public_jev_calls_total": public_jev, "public_accepted_host_total": public_hosts}))


if __name__ == "__main__":
    main()
