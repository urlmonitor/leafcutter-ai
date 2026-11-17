"""Repair only the controller actor identifier; preserve all blind response bytes.

The original rejection receipts remain immutable. These are the same sixteen
kernel waits and model outputs, not sixteen new model attempts.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from report_support.layout import receipt_path, require_unarchived_controller

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from integrations.retrieval_needs_llm import make_experiment_service
from scripts.evaluate_retrieval_needs_llm import freeze, overlay_grade, shared_grade, verify_baseline

DIRECTORY = Path(__file__).resolve().parent
BASE = DIRECTORY / "needs-evaluation"
OUTPUT = BASE / "controller-envelope-repair"


def read(path):
    return json.loads(receipt_path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = receipt_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def main():
    require_unarchived_controller()
    if (OUTPUT / "summary.json").exists():
        raise ValueError("Corrected receipts already exist; refuse repeat")
    freeze(BASE)
    baseline, comparison = verify_baseline()
    cases = [*baseline["cases"], *read(DIRECTORY / "holdouts.json")["cases"]]
    host_root = Path(read(BASE / "host-location.json")["root"])
    records = []
    for case in cases:
        identifier = case["id"]
        response_path = receipt_path(BASE / f"responses/{identifier}.json")
        response_hash = hashlib.sha256(response_path.read_bytes()).hexdigest()
        original = read(BASE / f"{identifier}.submission.json")
        assert original["response"] == read(response_path)
        submission = {**original, "actor": {"id": "host:blind_retrieval_host", "kind": "host"}}
        save(OUTPUT / f"{identifier}.submission.json", submission)
        service = make_experiment_service(ROOT, host_root / "kernel-runs")
        try:
            result = await service.resume_run(original["run_id"], submission)
            output = result.output.payload if result.output else None
            record = {"case_id": identifier, "original_rejected_receipt": f"../{identifier}.result.json",
                "response_sha256": response_hash, "response_unchanged": hashlib.sha256(response_path.read_bytes()).hexdigest() == response_hash,
                "envelope": result.model_dump(mode="json"), "result": output,
                "shared_semantics": shared_grade(case, output) if output else {"passed": False, "checks": []},
                "overlay": overlay_grade(identifier, output, comparison) if output else {"applicable": False, "passed": False}}
            save(OUTPUT / f"{identifier}.result.json", record)
            records.append(record)
            print(identifier, result.status.value, "semantic_pass", record["shared_semantics"]["passed"], flush=True)
        finally:
            await service._env.aclose()
    summary = {"correction": "Controller actor id contained a slash. Reused identical blind responses and original waits with a valid actor id.",
        "underlying_model_requests": None, "tokens": None, "model_id": None, "new_model_generations_for_correction": 0,
        "jev_calls": sum(record["envelope"]["usage_summary"]["jev_calls"] for record in records),
        "accepted_host_interpretations": sum(record["envelope"]["status"] == "completed" and record["result"] is not None for record in records),
        "all_model_response_bytes_unchanged": all(record["response_unchanged"] for record in records), "results": records}
    for name, prefix in (("unchanged_baseline", "N"), ("independent_holdouts", "H")):
        rows = [record for record in records if record["case_id"].startswith(prefix)]
        summary[name] = {"cases": len(rows), "semantic_passes": sum(record["shared_semantics"]["passed"] for record in rows),
            "failures": [{"case": record["case_id"], "checks": [check["name"] for check in record["shared_semantics"]["checks"] if not check["passed"]]}
                         for record in rows if not record["shared_semantics"]["passed"]]}
    save(OUTPUT / "summary.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
