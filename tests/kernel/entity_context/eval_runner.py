"""Independent labelled recognition evaluation; no downstream answer can mask a miss."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from kernel.contracts import CallerContext
from tests.conftest import load_fixture
from tests.kernel.entity_context.support import (
    FAMILIES, api, build, compact_size, config_for, long_goal, payload, task_for, write_repo,
)


def load_cases() -> list[dict]:
    """Load labels authored independently of the index and matcher."""
    return load_fixture("entity_evaluation/corpus")["cases"]


def case_goal(case: dict) -> str:
    """Expand only documented deterministic corpus inputs, never expected labels."""
    if case.get("goal_factory") == "long":
        return long_goal()
    if case.get("goal_factory") == "repeat":
        return " ".join(["Zephyr"] * 100)
    return case["goal"]


def score(case: dict, result, task, config) -> dict:
    """Compare actual identities, spans, coverage and work with independent labels."""
    expected = {tuple(pair) for pair in case["expected"]}
    observed = {(card.family, card.identity) for card in result.entities if card.resolution == "resolved"}
    failures = []
    if observed != expected:
        failures.append("identity_mismatch")
    if result.original_goal != task.goal:
        failures.append("original_goal_changed")
    unresolved = {(entry.reference, entry.state) for entry in result.unresolved}
    for pair in case.get("unresolved", []):
        if tuple(pair) not in unresolved:
            failures.append("unresolved_mismatch:" + pair[0])
    alternatives = {item for entry in result.unresolved for item in entry.candidates}
    if "candidates" in case and alternatives != set(case["candidates"]):
        failures.append("ambiguity_mismatch")
    for card in result.entities:
        for mention in card.matches:
            source = task.goal if mention.channel == "goal" else getattr(task.context, mention.channel)[mention.record_index]
            if source[mention.start:mention.end] != mention.surface:
                failures.append("mention_span_mismatch:" + card.identity)
        if not card.matches:
            failures.append("missing_mentions:" + card.identity)
        provenance = card.provenance
        if not all((provenance.source_id, provenance.locator, provenance.snapshot,
                    provenance.source_hash, provenance.projection_hash)):
            failures.append("provenance_missing:" + card.identity)
        if len(card.meaning) > config.entity_context.max_meaning_chars:
            failures.append("meaning_budget")
    if case.get("occurrences") is not None and sum(len(c.matches) for c in result.entities) != case["occurrences"]:
        failures.append("occurrences_mismatch")
    actual = result.model_dump(mode="json")
    actual.pop("original_goal", None)  # caller supplied reference is not a cache disclosure
    for sentinel in case.get("forbidden", []):
        if sentinel in json.dumps(actual, ensure_ascii=False):
            failures.append("forbidden:" + sentinel)
    for key in ("status",):
        if key in case and getattr(result, key) != case[key]:
            failures.append(key + "_mismatch")
    if "index_status" in case and result.coverage.index_status != case["index_status"]:
        failures.append("index_status_mismatch")
    if "expected_lookups" in case and result.budgets.lookups != case["expected_lookups"]:
        failures.append("lookup_count_mismatch")
    if result.coverage.counts.omitted < case.get("omitted_min", 0):
        failures.append("omitted_count_mismatch")
    if result.budgets.lookups > config.entity_context.max_lookups:
        failures.append("lookup_budget")
    if len(result.entities) > config.entity_context.max_entities:
        failures.append("entity_budget")
    if compact_size(payload(result)) > config.entity_context.max_serialized_chars:
        failures.append("serialized_budget")
    if result.budgets.jev_calls != 0:
        failures.append("recognition_model_call")
    by_family = {}
    for family in FAMILIES:
        want = {identity for kind, identity in expected if kind == family}
        got = {identity for kind, identity in observed if kind == family}
        by_family[family] = {"expected": len(want), "observed": len(got), "correct": len(want & got)}
    return {"id": case["id"], "expected": sorted(expected), "observed": sorted(observed),
            "failures": sorted(set(failures)), "passed": not failures,
            "lookups": result.budgets.lookups, "coverage": result.coverage.model_dump(mode="json"),
            "by_family": by_family}


def run_case(case: dict, root: Path, *, recognizer=None) -> dict:
    """Feed real owner records into the real builder, then the real recognition path."""
    write_repo(root)
    config = config_for(**case.get("limits", {}))
    build(root, config)
    if case.get("deny_globs"):
        sources = [source.model_copy(update={"deny_globs": case["deny_globs"]}) for source in config.sources]
        config = config.model_copy(update={"sources": sources})
    if case.get("mutation") == "dirty":
        path = root / "docs/glossary.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nDirty edit.\n", encoding="utf-8")
    task = task_for(root, case_goal(case), context=CallerContext.model_validate(case.get("context", {})),
                    permissions=case.get("permissions", ["read_repo"]))
    run = recognizer or api("kernel.entity_context", "recognize_entities")
    return score(case, run(task, config), task, config)


def run_eval(cases: list[dict] | None = None, *, recognizer=None) -> dict:
    """Report macro input coverage and exact precision/recall counts for every family."""
    selected = load_cases() if cases is None else cases
    if not selected:
        raise ValueError("entity recognition evaluation requires at least one case")
    with tempfile.TemporaryDirectory(prefix="entity-eval-") as temporary:
        rows = [run_case(case, Path(temporary) / case["id"], recognizer=recognizer) for case in selected]
    family_report = {}
    for family in sorted(FAMILIES):
        wanted = sum(row["by_family"][family]["expected"] for row in rows)
        got = sum(row["by_family"][family]["observed"] for row in rows)
        correct = sum(row["by_family"][family]["correct"] for row in rows)
        family_report[family] = {"expected": wanted, "observed": got, "correct": correct,
                                 "precision": correct / got if got else None,
                                 "recall": correct / wanted if wanted else None,
                                 "covered_cases": sum(row["by_family"][family]["expected"] > 0 for row in rows)}
    return {"schema_version": "1.0", "evaluation": "independent_entity_recognition", "rows": rows,
            "by_family": family_report, "total": len(rows), "passed": sum(row["passed"] for row in rows),
            "historical_evidence": load_fixture("entity_evaluation/corpus")["historical_evidence"]}


def main(argv=None) -> int:
    """Write a reviewable report and return failure for any missed recognition label."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_eval()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["total"] and report["total"] == report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
