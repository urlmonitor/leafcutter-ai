"""
MODULE: unit_tests/ac_store/_protected_fields_fixtures.py
GOAL: Shared scenario builders for the "protected fields" rule family tests
    (test_acd_2500a_2_vi.py, test_acd_2500a_2_vii.py): a tmp git repo whose HEAD commit
    is the stage's before-state and whose working tree holds the stage's edits.
BUSINESS CONTEXT: ACD-2500a-2-vi / -vii. A stage may change only the fields it owns; the
    rule check, run with --before-ref HEAD, compares every protected field of every record
    against its committed value. Both tickets drive the check the same way, so the
    before/after plumbing lives here once.
ARCHITECTURE: Builds on _rule_check_fixtures (make_store, hierarchy, init_git_repo,
    commit_all, run_cli). Records go through the real serializer (Store.write ->
    yaml.safe_dump). The before-state is otherwise coherent: the L1 already lists every
    child, including the one the stage creates, so the back-link family has nothing to
    repair unless a test removes a link on purpose. The family module is reached through
    `family_module()`, which turns its absence into an assertion (not an import error).

PUBLIC API:
    R0, L1, R1, R2, R3, NEW_CRITERIA, FAMILY_PROTECTED
    stage_start_records(**per_child) -> list[dict]      the committed before-state
    committed_store(tmp_path, records) -> Store          make_store + git init + commit
    edit(store, record_id, mutate)                       read, mutate(dict), write back
    run_stage(store, stage, *extra) -> (exit, report)    --before-ref HEAD, in process
    protected(report, record_id=None) -> list[dict]      the family's findings
    decisions(report) -> {(record_id, field)}            its 'needs a decision' findings
    family_module()                                      import _rc_protected_fields
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    SCRIPTS_DIR,
    Store,
    cli_argv,
    commit_all,
    findings_for,
    hierarchy,
    init_git_repo,
    make_store,
    run_cli,
)

FAMILY_PROTECTED = "protected fields"
DECISION = "needs a decision"
NOT_EVALUATED = "not evaluated"

R0 = "ACD-9990"
L1 = "ACD-9990a"
R1 = "ACD-9990a-1"
R2 = "ACD-9990a-2"
R3 = "ACD-9990a-3"

OLD_CRITERIA = "Given a fixture record,\nWhen the rule check runs,\nThen one row is written.\n"
NEW_CRITERIA = "Given a fixture record,\nWhen the rule check runs,\nThen two rows are written.\n"
REFERENCE_FILE = "config/ac_store_schema.json"  # copied into every tmp store by make_store
TARGET_DIR = "unit_tests/ac_store/"
# A path the surface map has no entry for: the specialist-versus-surface family lists it
# `not evaluated` whoever R2 is assigned to, so a reassignment adds no other blocker.
UNMAPPED_FILE = "data/_fixture_acd_9990a_2.dat"
FAMILY_MODULE_FILE = SCRIPTS_DIR / "_rc_protected_fields.py"


def four_field_spec() -> dict:
    """Object-form it_requirements with every package-surface field except the reference file."""
    return {
        "config_schema_fragment": {"type": "object"},
        "n_location_rule": "1",
        "required_skills": ["python-coder"],
        "post_write_commands": ["python scripts/build.py"],
    }


def stage_start_records(**per_child: dict) -> list[dict]:
    """The committed before-state: L0, L1 (listing R1..R3), R1 (producer) and R2 (consumer).

    R1 delivers to python-coder and R2 (python-coder) expects from R1, so the contract
    family is satisfied. R2 carries object-form it_requirements still waiting for its
    reference file (hold_reason "reference file pending") and declares UNMAPPED_FILE.
    `per_child` maps "r1"/"r2"
    to extra overrides.
    """
    r1 = {
        "criteria": OLD_CRITERIA,
        "delivers_to": {"agent": "python-coder", "contract": "Writes one row per run."},
        **per_child.get("r1", {}),
    }
    r2 = {
        "expects_from": {"ac_id": R1, "contract": "One row per run, read back by id."},
        "it_requirements": four_field_spec(),
        "declared_files": [{"path": UNMAPPED_FILE, "state": "to_be_created"}],
        "hold_reason": "reference file pending",
        **per_child.get("r2", {}),
    }
    records = hierarchy(R0, 2, child={1: r1, 2: r2})
    for record in records:
        if record["id"] == L1:
            record["covered_by"] = [R1, R2, R3]
    return records


def committed_store(tmp_path: Path, records: list[dict]) -> Store:
    """A tmp git repo whose HEAD commit holds `records` (the stage's before-state)."""
    store = make_store(tmp_path, records)
    (store.repo_root / TARGET_DIR).mkdir(parents=True, exist_ok=True)
    (store.repo_root / TARGET_DIR / "__init__.py").write_text("", encoding="utf-8")
    init_git_repo(store.repo_root)
    commit_all(store.repo_root, "stage start")
    return store


def edit(store: Store, record_id: str, mutate: Callable[[dict], Any]) -> None:
    """Read `record_id`, apply `mutate` to the dict, write it back (uncommitted)."""
    record = store.read(record_id)
    mutate(record)
    store.write(record)


def design_of(record_id: str, clause: str = "it is a valid requirement") -> dict:
    """The fields the test-design stage owns, filled for `record_id` (a coherent design
    whose entries prove `clause`)."""
    code_file = f"scripts/ac_store/_fixture_{record_id.lower().replace('-', '_')}.py"
    entries = [
        {
            "name": f"test_{angle}_{record_id.lower().replace('-', '_')}",
            "target_dir": TARGET_DIR,
            "framework": "pytest",
            "type": "unit",
            "angle": angle,
            "description": f"The {angle} proof of {record_id}.",
            "proves_clause": clause,
            "code_file": code_file,
            "to_be_created": True,
        }
        for angle in ("criterion", "reachability")
    ]
    return {
        "test_spec": entries,
        "test_design_authorship": {"step": "test-designer", "date": "2026-10-20"},
        "test_design_opened_files": [REFERENCE_FILE],
    }


def file_findings_fill(record: dict) -> None:
    """The test-design stage's group-2 edits on R2: findings, reference file, marker cleared."""
    record["file_findings"] = [
        {
            "file": REFERENCE_FILE,
            "verdict": "consistent",
            "reason": "It holds the schema the record names as its reference file.",
            "line_range": None,
            "found_in": None,
            "decision": None,
        }
    ]
    record["file_findings_opened_files"] = [REFERENCE_FILE]
    record["it_requirements"]["reference_file_path"] = REFERENCE_FILE
    record.pop("hold_reason", None)


def apply_stage_owned_edits(store: Store) -> None:
    """Only what the test-design stage owns: R1's design, R2's file findings, R3 created."""
    edit(store, R1, lambda r: r.update(design_of(R1)))
    edit(store, R2, file_findings_fill)
    store.write(new_record())


def new_record() -> dict:
    """R3, created during the stage (absent from the HEAD commit).

    R3 (python-coder) also expects from R1, so R1's delivery keeps a consumer when a
    scenario reassigns R2 and the contract family stays silent.
    """
    from _rule_check_fixtures import valid_record  # noqa: PLC0415

    return valid_record(
        R3, level="L2", depends_on=[L1],
        expects_from={"ac_id": R1, "contract": "One row per run, counted."},
    )


def run_stage(store: Store, stage: str, *extra: str) -> tuple[int, dict]:
    """Run the check in process with --before-ref HEAD (unless `extra` names a before-state)."""
    before = () if ("--before-ref" in extra or "--before-snapshot" in extra) else ("--before-ref", "HEAD")
    return run_cli(cli_argv(store, *before, *extra, stage=stage), cwd=store.repo_root)


def protected(report: dict, record_id: str | None = None) -> list[dict]:
    """The 'protected fields' findings of `report` (optionally for one record)."""
    family = FAMILY_PROTECTED
    return findings_for(report, record_id=record_id, rule_family=family)


def field_of(finding: dict) -> str:
    """The field a 'protected fields' finding names (detail.field)."""
    detail = finding.get("detail")
    return str(detail.get("field")) if isinstance(detail, dict) else ""


def decisions(report: dict) -> set[tuple[str, str]]:
    """{(record_id, field)} of every 'needs a decision' finding of the family."""
    return {
        (f["record_id"], field_of(f))
        for f in protected(report)
        if f["disposition"] == DECISION
    }


def family_module():
    """Import scripts/ac_store/_rc_protected_fields.py; its absence is an assertion red."""
    assert FAMILY_MODULE_FILE.is_file(), (
        f"{FAMILY_MODULE_FILE.relative_to(SCRIPTS_DIR.parents[1])} does not exist: the "
        "'protected fields' rule family module has not been written yet"
    )
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return importlib.import_module("_rc_protected_fields")


def reassign_r2(record: dict) -> None:
    """R2's out-of-stage edits in the ACD-2500a-2-vi example: assignment and contract text."""
    record["assigned_agent"] = "llm-expert"
    record["expects_from"] = {"ac_id": R1, "contract": "Two rows per run, read back by id."}


def apply_vi_scenario(store: Store) -> None:
    """The full ACD-2500a-2-vi stage: the stage-owned edits plus three protected changes."""
    apply_stage_owned_edits(store)
    edit(store, R1, lambda r: r.update(criteria=NEW_CRITERIA))
    edit(store, R2, reassign_r2)
