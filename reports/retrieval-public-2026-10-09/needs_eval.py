"""Bounded replay of unchanged needs gold plus independently authored holdouts.

Uses the existing real kernel packet/ledger evaluator. This controller neither
generates model responses nor sends expected values to the blind host.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from report_support.layout import receipt_path, require_unarchived_controller

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_retrieval_needs_llm import prepare, submit, verify_baseline

DIRECTORY = Path(__file__).resolve().parent
OUTPUT = DIRECTORY / "needs-evaluation"


def read(path):
    return json.loads(receipt_path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset():
    original, comparison = verify_baseline()
    holdouts = read(DIRECTORY / "holdouts.json")
    return {**original, "cases": [*original["cases"], *holdouts["cases"]]}, comparison


def fingerprints():
    return {name: digest(DIRECTORY / name) for name in ("plan.json", "holdouts.json", "needs_eval.py")}


async def main():
    require_unarchived_controller()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "submit"))
    parser.add_argument("--actor-id", default="host:blind-public-needs")
    arguments = parser.parse_args()
    data, comparison = dataset()
    freeze_path = OUTPUT / "independent-plan-freeze.json"
    if arguments.action == "prepare":
        await prepare(OUTPUT, data)
        freeze_path.write_text(json.dumps(fingerprints(), indent=2) + "\n", encoding="utf-8")
        print("Host-only manifest:", read(OUTPUT / "host-location.json")["manifest"])
        return
    if read(freeze_path) != fingerprints():
        raise ValueError("The independently frozen plan or holdouts changed")
    await submit(OUTPUT, data, comparison, arguments.actor_id)
    records = [read(OUTPUT / f"{case['id']}.result.json") for case in data["cases"]]
    groups = {name: [row for row in records if row["case_id"].startswith(prefix)]
              for name, prefix in (("unchanged_baseline", "N"), ("independent_holdouts", "H"))}
    summary = {name: {"cases": len(rows), "semantic_passes": sum(row["shared_semantics"]["passed"] for row in rows),
                     "accepted_host_operations": sum(row["envelope"]["usage_summary"]["host_operations"] for row in rows),
                     "failures": [{"case": row["case_id"], "checks": [check["name"] for check in row["shared_semantics"]["checks"] if not check["passed"]]}
                                  for row in rows if not row["shared_semantics"]["passed"]]}
               for name, rows in groups.items()}
    summary.update(mode="fresh blind host agent through actual packet/ledger; no graph retrieval", model_id=None,
                   actual_model_request_count=None, jev_calls=0, tokens=None, expected_labels_sent_to_host=False)
    (OUTPUT / "combined-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
