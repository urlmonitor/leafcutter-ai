"""Score only context enrichment over labelled, controlled repository cases.

The public production step reads real on-disk documents. Expected facts are independent
fixture labels. A report identifies failures per case, and the CLI exits nonzero whenever
one fails. There are no scripted model answers and no downstream classifier or research.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from kernel.config import KernelConfig, SourceConfig, load_kernel_config
from kernel.contracts import TaskInput, content_hash
from kernel.context_enrichment import gather_context

EVAL_SET = Path(__file__).resolve().parents[1] / "fixtures" / "eval" / "context_enrichment.json"
SOURCE_ID = "eval.docs"


def load_cases(path: Path = EVAL_SET) -> list[dict[str, Any]]:
    """Load the independent labels, miniature repositories and caller context."""
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def config_for(case: dict[str, Any], **limits: Any) -> KernelConfig:
    """Use production defaults and a single explicit fixture repository source."""
    config = load_kernel_config()
    source = SourceConfig(id=SOURCE_ID, kind="repo_text", roots=["."],
                          categories=["task_context"],
                          deny_globs=case.get("source_deny_globs", []))
    enrichment = config.context_enrichment.model_copy(update={
        "source_ids": [SOURCE_ID], "max_files": 24, "max_sources": 1,
        "max_evidence": 6, "max_chars": 4000, "max_excerpt_chars": 1000,
        "max_context_chars": 2000, **limits})
    return config.model_copy(update={"sources": [source], "context_enrichment": enrichment})


def task_for(case: dict[str, Any], root: Path) -> TaskInput:
    """Build the production boundary input, preserving the original goal and caller claims."""
    return TaskInput.model_validate({
        "goal": case["goal"], "caller": {"id": "enrichment-eval", "kind": "host"},
        "scope": {"workspace_id": "enrichment-eval", "repository_root": str(root),
                  "read_roots": case.get("read_roots", []),
                  "source_ids": case.get("source_ids", [])},
        "context": case.get("context", {}), "permissions": case.get("permissions", ["read_repo"])})


def write_repo(case: dict[str, Any], root: Path) -> None:
    """Materialise ordinary source documents, not a generated production artifact."""
    root.mkdir(parents=True, exist_ok=True)
    for name, contents in case["files"].items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")


def score(case: dict[str, Any], result: Any, task: TaskInput,
          config: KernelConfig) -> dict[str, Any]:
    """Check each emitted fact against its on-disk source and each independent case label."""
    expected, failures = case["expected"], []
    payload = result.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False)
    evidence = payload["evidence"]
    paths = [item["locator"].split("#", 1)[0] for item in evidence]
    excerpts = "\n".join(item["excerpt"] for item in evidence)
    for path in expected.get("sources", []):
        if path not in paths:
            failures.append(f"missing_source:{path}")
    for fact in expected.get("facts", []):
        if fact not in excerpts:
            failures.append(f"missing_fact:{fact}")
    for path in expected.get("forbidden_sources", []):
        if path in paths:
            failures.append(f"forbidden_source:{path}")
    for sentinel in expected.get("forbidden_text", []):
        if sentinel in serialized:
            failures.append(f"forbidden_text:{sentinel}")
    for item, path in zip(evidence, paths, strict=True):
        if path not in case["files"]:
            failures.append(f"unknown_provenance:{path}")
        elif item["excerpt"] not in case["files"][path]:
            failures.append(f"ungrounded_excerpt:{path}")
        if item["content_hash"] != content_hash(item["excerpt"]):
            failures.append(f"invalid_content_hash:{path}")
        if item["source_id"] != SOURCE_ID:
            failures.append(f"unexpected_source_id:{path}")
    if expected.get("empty_evidence") and evidence:
        failures.append("expected_no_evidence")
    if "status" in expected and result.status not in expected["status"]:
        failures.append(f"unexpected_status:{result.status}")
    if result.files_scanned < expected.get("min_files", 0):
        failures.append("insufficient_files_examined")
    if result.files_scanned and SOURCE_ID not in result.sources_consulted:
        failures.append("examined_source_not_recorded")
    if result.files_scanned > expected.get("max_files", config.context_enrichment.max_files):
        failures.append("excess_files_examined")
    if expected.get("limitations") and not result.limitations:
        failures.append("missing_limitation")
    if result.original_goal != task.goal:
        failures.append("original_goal_changed")
    if result.caller_context.model_dump() != task.context.model_dump():
        failures.append("caller_context_rewritten")
    if result.registered_capabilities:
        failures.append("invented_registered_capabilities")
    if len(evidence) > config.context_enrichment.max_evidence:
        failures.append("evidence_count_exceeded")
    if sum(len(item["excerpt"]) for item in evidence) > config.context_enrichment.max_chars:
        failures.append("evidence_text_budget_exceeded")
    if any(len(item["excerpt"]) > config.context_enrichment.max_excerpt_chars for item in evidence):
        failures.append("excerpt_budget_exceeded")
    return {"id": case["id"], "category": case["category"], "status": result.status,
            "evidence_count": len(evidence), "files_scanned": result.files_scanned,
            "sources": paths, "failures": failures, "passed": not failures}


def run_case(case: dict[str, Any], root: Path) -> dict[str, Any]:
    """Run the real enrichment step once in an isolated repository."""
    write_repo(case, root)
    task, config = task_for(case, root), config_for(case)
    before = task.model_dump(mode="json")
    result = gather_context(task, config)
    row = score(case, result, task, config)
    if task.model_dump(mode="json") != before:
        row["failures"].append("input_task_mutated")
        row["passed"] = False
    after_files = {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
                   for path in root.rglob("*") if path.is_file()}
    if after_files != case["files"]:
        row["failures"].append("repository_modified")
        row["passed"] = False
    return row


def run_eval(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run only enrichment; return every case's result and aggregate pass/fail counts."""
    selected = load_cases() if cases is None else cases
    if not selected:
        raise ValueError("the enrichment evaluation must contain at least one case")
    with tempfile.TemporaryDirectory(prefix="kernel-context-eval-") as temporary:
        scratch = Path(temporary)
        rows = [run_case(case, scratch / case["id"]) for case in selected]
    return {"step": "context_enrichment", "rows": rows, "total": len(rows),
            "passed": sum(row["passed"] for row in rows), "jev_calls": 0}


def main(argv: list[str] | None = None) -> int:
    """Print the JSON report and return nonzero for any failed context case."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    arguments = parser.parse_args(argv)
    report = run_eval()
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
