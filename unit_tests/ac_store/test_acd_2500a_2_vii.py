"""
MODULE: test_acd_2500a_2_vii
GOAL: Red-first specification of ACD-2500a-2-vii: which protected fields a stage may
    change comes from one per-stage owner map in the "protected fields" family. The
    planner's hand-back pass (`--stage itpo-handback`) may change assigned_agent, a file
    finding's decision and its own enrichment fields (it_requirements, declared_files,
    delivers_to, expects_from); it may never change criteria, test_intent, test_spec, a
    file finding's other fields or a test_design_* mark. A stage the map does not list is
    `not evaluated` for the family (ticket 03).
BUSINESS CONTEXT: The IT PO's hand-back pass legitimately reassigns work and declares
    files the test designer's findings revealed; the same reassignment during test design
    is a protected-field edit (ACD-2500a-2-vi).
ARCHITECTURE: A tmp git repo (_protected_fields_fixtures): HEAD is the post-design batch
    (R1 carries test_intent and a code-aware design; R2 carries one undecided file finding
    "describes, does not implement"), the working tree holds the hand-back's edits, the
    check runs with `--before-ref HEAD`. Contract read here: the owner map is the module
    attribute OWNER_MAP of scripts/ac_store/_rc_protected_fields.py, {stage: fields the
    stage may change}; a file-finding finding names its sub-field (e.g. a field
    containing both "file_findings" and "verdict").
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _protected_fields_fixtures import (  # noqa: E402
    DECISION,
    L1,
    NEW_CRITERIA,
    NOT_EVALUATED,
    OLD_CRITERIA,
    R0,
    R1,
    R2,
    REFERENCE_FILE,
    UNMAPPED_FILE,
    committed_store,
    decisions,
    design_of,
    edit,
    family_module,
    field_of,
    protected,
    run_stage,
)
from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS,
    SCRIPTS_DIR,
    cli_argv,
    hierarchy,
    intent_entry,
    run_cli_subprocess,
)

_HANDBACK = "itpo-handback"
_CLAUSE = "one row is written"
_DESCRIBES = "describes, does not implement"
_ALLOWED_ON_R2 = ("assigned_agent", "decision", "declared_files", "it_requirements", "delivers_to", "expects_from")


def _handback_records() -> list[dict]:
    """The post-design batch: R1 (test_intent + design) and R2 (one undecided finding).

    R1 and R2 deliver to each other's agent (python-coder) and expect from each other, so
    the contract family is satisfied before the hand-back.
    """
    r1 = {
        "criteria": OLD_CRITERIA,
        "test_intent": [intent_entry(_CLAUSE)],
        "delivers_to": {"agent": "python-coder", "contract": "Writes one row per run."},
        "expects_from": {"ac_id": R2, "contract": "The row id it wrote."},
        **design_of(R1, _CLAUSE),
    }
    r2 = {
        "it_requirements": ["Writes one row per run."],
        "declared_files": [{"path": UNMAPPED_FILE, "state": "to_be_created"}],
        "delivers_to": {"agent": "python-coder", "contract": "The row id it wrote."},
        "expects_from": {"ac_id": R1, "contract": "One row per run."},
        "file_findings": [{
            "file": UNMAPPED_FILE, "verdict": _DESCRIBES,
            "reason": "It only documents the writer.", "line_range": "1-5",
            "found_in": None, "decision": None,
        }],
        "file_findings_opened_files": [REFERENCE_FILE],
    }
    return hierarchy(R0, 2, child={1: r1, 2: r2})


def _handback_store(root: Path):
    return committed_store(root, _handback_records())


def _allowed_r2_edits(record: dict, *, declared: dict | None = None) -> None:
    """The hand-back's allowed edits on R2 (the criteria's example)."""
    record["assigned_agent"] = "sql-coder"
    record["file_findings"][0]["decision"] = {
        "choice": "reassign", "reason": "The writer is SQL work.", "by": "it-po",
    }
    record["declared_files"].append(declared or {"path": "scripts/example_writer.py", "state": "existing"})
    record["it_requirements"].append("Writes through the shared writer")
    record["delivers_to"]["contract"] = "The row id the shared writer returned."
    record["expects_from"]["contract"] = "One row per run, through the shared writer."


def _verdict_to_consistent(record: dict) -> None:
    record["file_findings"][0]["verdict"] = "consistent"


def _finding_names(finding: dict, *tokens: str) -> bool:
    return all(token in field_of(finding) for token in tokens)


def test_handback_allowed_changes_raise_no_finding(tmp_path):
    # covers: ACD-2500a-2-vii
    # angle: discrimination
    """At itpo-handback, R2's assigned_agent, its finding's decision, a new declared file,
    a new it_requirements entry and the changed contract texts raise no 'protected fields'
    finding. Control in the same run: R1's criteria change is reported."""
    store = _handback_store(tmp_path)
    edit(store, R2, _allowed_r2_edits)
    edit(store, R1, lambda r: r.update(criteria=NEW_CRITERIA))

    _, report = run_stage(store, _HANDBACK)

    on_r2 = [f for f in protected(report, R2) if f["disposition"] == DECISION]
    assert on_r2 == [], on_r2
    assert decisions(report) == {(R1, "criteria")}


def test_handback_reports_criteria_and_finding_verdict(tmp_path):
    # covers: ACD-2500a-2-vii
    # angle: criterion
    """Same scenario plus R2's finding verdict changed to 'consistent': exactly two
    'protected fields' findings, (R1, criteria) and (R2, the file-finding verdict), each
    'needs a decision' and each naming stage itpo-handback."""
    store = _handback_store(tmp_path)
    edit(store, R2, lambda r: (_allowed_r2_edits(r), _verdict_to_consistent(r)))
    edit(store, R1, lambda r: r.update(criteria=NEW_CRITERIA))

    _, report = run_stage(store, _HANDBACK)

    found = [f for f in protected(report) if f["disposition"] == DECISION]
    assert len(found) == 2, protected(report)
    by_record = {f["record_id"]: f for f in found}
    assert set(by_record) == {R1, R2}
    assert field_of(by_record[R1]) == "criteria"
    assert _finding_names(by_record[R2], "file_findings", "verdict"), by_record[R2]
    assert all(f["detail"]["stage"] == _HANDBACK for f in found)


_LONE_CHANGES = {
    "test_intent": (R1, ("test_intent",), lambda r: r["test_intent"][0].update(needs_test=False)),
    "test_spec": (R1, ("test_spec",), lambda r: r["test_spec"][0].update(description="Reworded.")),
    "finding-reason": (R2, ("file_findings", "reason"), lambda r: r["file_findings"][0].update(reason="Reworded.")),
    "authorship-date": (R1, ("test_design_authorship",), lambda r: r["test_design_authorship"].update(date="2026-10-21")),
}


@pytest.mark.parametrize("change", sorted(_LONE_CHANGES))
def test_handback_test_intent_only_run_raises_exactly_one_finding(tmp_path, change):
    # covers: ACD-2500a-2-vii
    # angle: discrimination
    """A separate hand-back run whose only change is R1's test_intent (one clause's
    needs_test flipped) gives exactly one 'protected fields' finding naming test_intent and
    stage itpo-handback; so does each other lone change to the designer's output."""
    record_id, tokens, mutate = _LONE_CHANGES[change]
    store = _handback_store(tmp_path)
    edit(store, record_id, mutate)

    _, report = run_stage(store, _HANDBACK)

    found = [f for f in protected(report) if f["disposition"] == DECISION]
    assert len(found) == 1, protected(report)
    assert found[0]["record_id"] == record_id
    assert _finding_names(found[0], *tokens), found[0]
    assert found[0]["detail"]["stage"] == _HANDBACK


def test_same_assignment_change_reported_at_test_design_stage(tmp_path):
    # covers: ACD-2500a-2-vii
    # angle: boundary
    """The identical on-disk change (R2 reassigned) and before-state checked with --stage
    test-design reports assigned_agent; with --stage itpo-handback it does not."""
    store = _handback_store(tmp_path)
    edit(store, R2, lambda r: r.update(assigned_agent="sql-coder"))

    _, at_design = run_stage(store, "test-design")
    _, at_handback = run_stage(store, _HANDBACK)

    assert decisions(at_design) == {(R2, "assigned_agent")}
    assert decisions(at_handback) == set()
    assert not any("unrecognised --stage" in f["message"] for f in at_handback["findings"])


def _criteria_only_store(root: Path):
    """A hand-back whose one disallowed change is R1's criteria (R1 has no test_intent,
    so the test-intent family stays silent and only the owner map decides the verdict)."""
    records = _handback_records()
    r1 = next(r for r in records if r["id"] == R1)
    del r1["test_intent"]
    store = committed_store(root, records)
    edit(store, R1, lambda r: r.update(criteria=NEW_CRITERIA))
    return store


def _widened(allowed, extra: str):
    """`allowed` plus `extra`, in the container type the owner map uses."""
    merged = [*allowed, extra]
    if isinstance(allowed, (set, frozenset)):
        return type(allowed)(merged)
    return type(allowed)(merged) if isinstance(allowed, (tuple, list)) else merged


def test_owner_map_is_the_single_source(tmp_path, monkeypatch):
    # covers: ACD-2500a-2-vii
    # angle: discrimination
    """In process: the criteria-only hand-back fails with that one finding; with OWNER_MAP
    monkeypatched to also allow criteria for itpo-handback the next run on the same store
    passes with no other edit; restoring the map restores the finding. The allowed field
    names are not copied into requirement_rule_check.py."""
    module = family_module()
    store = _criteria_only_store(tmp_path)

    exit_code, report = run_stage(store, _HANDBACK)
    assert exit_code == 1 and decisions(report) == {(R1, "criteria")}, report["findings"]

    monkeypatch.setitem(module.OWNER_MAP, _HANDBACK, _widened(module.OWNER_MAP[_HANDBACK], "criteria"))
    widened_exit, widened = run_stage(store, _HANDBACK)
    assert widened_exit == 0 and widened["verdict"] == "passed", widened["findings"]

    monkeypatch.undo()
    restored_exit, restored = run_stage(store, _HANDBACK)
    assert restored_exit == 1 and decisions(restored) == {(R1, "criteria")}

    tree = ast.parse((SCRIPTS_DIR / "requirement_rule_check.py").read_text(encoding="utf-8"))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (literals & {"assigned_agent", "declared_files", "it_requirements", "delivers_to", "expects_from"})


@pytest.mark.parametrize("stage", ["po", "ba", "itpo"])
def test_stages_outside_owner_map_listed_not_evaluated(tmp_path, stage):
    # covers: ACD-2500a-2-vii
    # angle: boundary
    """At --stage po / ba / itpo the same criteria change gives every record one 'not
    evaluated' from 'protected fields' and no blocking finding from it."""
    store = _criteria_only_store(tmp_path)

    _, report = run_stage(store, stage)

    found = protected(report)
    assert sorted(f["record_id"] for f in found) == sorted([R0, L1, R1, R2])
    assert {f["disposition"] for f in found} == {NOT_EVALUATED}
    assert not any(f["disposition"] in BLOCKERS for f in found)


def test_itpo_handback_stage_reachable_from_cli(tmp_path):
    # covers: ACD-2500a-2-vii
    # angle: reachability
    """`requirement_rule_check.py --stage itpo-handback --before-ref HEAD` as a subprocess
    accepts the stage and exits 0 when only the six allowed fields changed. Control: an
    unknown stage still fails with the unrecognised-stage finding."""
    store = _handback_store(tmp_path)
    to_be_created = {"path": "data/example_writer.dat", "state": "to_be_created"}
    edit(store, R2, lambda r: _allowed_r2_edits(r, declared=to_be_created))
    edit(store, R1, lambda r: r["delivers_to"].update(agent="sql-coder"))

    run = run_cli_subprocess(cli_argv(store, "--before-ref", "HEAD", stage=_HANDBACK), cwd=store.repo_root)

    assert not any("unrecognised --stage" in f["message"] for f in run.report["findings"]), run.report
    assert run.exit_code == 0 and run.report["verdict"] == "passed", run.report["findings"]
    assert [f for f in protected(run.report) if f["disposition"] == DECISION] == []
    for field in _ALLOWED_ON_R2:
        assert not any(field in field_of(f) for f in protected(run.report, R2) if f["disposition"] == DECISION)

    unknown = run_cli_subprocess(cli_argv(store, "--before-ref", "HEAD", stage="itpo-handbag"), cwd=store.repo_root)
    assert unknown.exit_code == 1
    assert any("unrecognised --stage" in f["message"] for f in unknown.report["findings"])
