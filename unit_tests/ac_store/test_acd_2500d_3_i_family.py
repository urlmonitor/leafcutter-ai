"""
MODULE: unit_tests/ac_store/test_acd_2500d_3_i_family.py
COVERS: ACD-2500d-3-i
GOAL: Red-first specification of the rule family "file findings consistency" (ticket 39, G4 note
    section 4). The family judges a record's `file_findings` against the record's declared files and
    the tree: a declared file with no finding, a finding for a file that is neither declared nor the
    reference file, a verdict that contradicts the tree, a verdict missing its companion field, and
    a verdict on a file that was not opened. It does NOT report an undecided finding: that waits for
    the planner's next pass and is an approval hold, so failing the stage on it would loop the
    designer for nothing.
BUSINESS CONTEXT: ADR-071 / the G4 note. Findings are `needs a decision`; nothing is repaired; only
    records whose `file_findings` is a list are evaluated (an absent field means the step has not run).
ARCHITECTURE: Each row is one record in its own tmp repo (real serializer, real source file under
    the repo root, see _acd_2500d_3_i_fixtures) checked in process by `requirement_rule_check`; one
    test drives the real CLI as a subprocess. Rows are judged on this family's findings only.

RED STATE: the family does not exist, so every row that expects a finding finds none (assertion red)
    and `_rc_report.FAMILY_FILE_FINDINGS` is not defined (AttributeError: an absence red).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500d_3_i_fixtures import (  # noqa: E402
    EXISTING, FAMILY, FINDINGS, MISSING, OPENED, OTHER, code_repo, decision, family_findings, finding, leaf,
    make_store,
)
from _acs_100i_fixtures import complete_impl_spec  # noqa: E402
from _rule_check_fixtures import cli_argv, run_cli_subprocess, snapshot_tree  # noqa: E402

NEW_FILE = "scripts/ac_store/_to_be_made.py"
DESCRIBES = "describes, does not implement"
ABSENT = "absent, not to-be-created"
ELSEWHERE = "behaviour found elsewhere"
_DECLARED = [{"path": EXISTING, "state": "existing"}, {"path": NEW_FILE, "state": "to_be_created"}]


def _rec(record_id: str, findings: list[dict], opened: list[str] | None = None, declared=None, **extra) -> dict:
    return leaf(record_id, findings, opened, declared_files=declared or _DECLARED, **extra)


def _count(tmp_path: Path, label: str, record: dict) -> list[dict]:
    """This family's findings for one row, each in its own tmp repo."""
    _code, found = family_findings(tmp_path / label.replace(" ", "_"), record)
    return found


def test_declared_file_without_a_finding_is_reported(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: criterion
    """A declared file that exists but has no finding is reported once, naming the file and the record.

    The to_be_created file that is absent from the tree is exempt (exactly ONE finding, not two). Rows run
    in separate tmp repos; the control row (a consistent finding for the file) has no finding.
    """
    tmp = tmp_path
    silent = _count(tmp, "none", _rec("ZZG-1a-1", []))
    covered = _count(tmp, "covered", _rec("ZZG-1a-2", [finding(EXISTING)]))
    assert covered == []
    assert len(silent) == 1, silent
    assert silent[0]["record_id"] == "ZZG-1a-1" and EXISTING in silent[0]["message"], silent[0]
    assert silent[0]["disposition"] == "needs a decision"


def test_finding_for_an_undeclared_file_is_reported_unless_it_is_the_reference_file(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: boundary
    """A finding whose file is not declared is reported (the step never adds files), except the reference file.

    Row 1: a finding for OTHER with nothing naming OTHER: one finding naming it. Control row: the same
    finding when it_requirements.reference_file_path is OTHER: none. The declared file keeps its own
    finding in both rows so only the undeclared one is judged.
    """
    base = [finding(EXISTING), finding(OTHER, "consistent")]
    tmp = tmp_path
    stray = _count(tmp, "stray", _rec("ZZG-2a-1", base, [EXISTING, OTHER]))
    spec = {**complete_impl_spec(), "reference_file_path": OTHER}
    named = _count(tmp, "named", _rec("ZZG-2a-2", base, [EXISTING, OTHER], package_surface=True, it_requirements=spec))
    assert named == []
    assert len(stray) == 1 and OTHER in stray[0]["message"], stray


def test_verdict_must_agree_with_the_tree(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: failure
    """An absent file must carry "absent, not to-be-created"; that verdict on an existing file is wrong.

    Declared MISSING is `existing` in the record but is not on disk. Rows (label: expected findings):
    consistent on the absent file: 1; the absent verdict on the absent file (control): 0; the absent
    verdict on the file that exists: 1. Each finding names the file.
    """
    declared = [*_DECLARED, {"path": MISSING, "state": "existing"}]
    rows = {
        "consistent but absent": ([finding(EXISTING), finding(MISSING, "consistent")], 1, MISSING),
        "absent and absent": ([finding(EXISTING), finding(MISSING, ABSENT)], 0, ""),
        "absent but present": ([finding(EXISTING, ABSENT), finding(MISSING, ABSENT)], 1, EXISTING),
    }
    wrong = {}
    for label, (findings, want, name) in rows.items():
        got = _count(tmp_path, label, _rec("ZZG-3a-1", findings, declared=declared))
        if len(got) != want or any(name not in g["message"] for g in got):
            wrong[label] = [g["message"] for g in got]
    assert wrong == {}, wrong


def test_verdict_companion_fields_are_required(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: boundary
    """`describes, does not implement` needs line_range; `behaviour found elsewhere` needs found_in.

    Other verdicts must have found_in null. Exact count per row, each message naming the field.
    Control rows carry the companion field and give none.
    """
    rows = {
        "describes without range": (finding(EXISTING, DESCRIBES), "line_range"),
        "elsewhere without found_in": (finding(EXISTING, ELSEWHERE), "found_in"),
        "consistent with found_in": (finding(EXISTING, "consistent", found_in=OTHER), "found_in"),
    }
    controls = [
        finding(EXISTING, DESCRIBES, line_range="3-9"),
        finding(EXISTING, ELSEWHERE, found_in=OTHER),
    ]
    wrong = {}
    for label, (item, field) in rows.items():
        got = _count(tmp_path, label, _rec("ZZG-4a-1", [item]))
        if len(got) != 1 or field not in got[0]["message"]:
            wrong[label] = [g["message"] for g in got]
    for index, item in enumerate(controls):
        got = _count(tmp_path, f"control{index}", _rec(f"ZZG-4a-{index + 2}", [item]))
        if got:
            wrong[f"control {index}"] = [g["message"] for g in got]
    assert wrong == {}, wrong


def test_verdict_on_a_file_that_was_not_opened_is_reported(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: failure
    """A verdict on an existing file that is not in file_findings_opened_files is reported (d-1: none unopened).

    Control row: the same finding with the file in the opened list gives none. Exactly one finding
    otherwise, naming the file.
    """
    unopened = _count(tmp_path, "unopened", _rec("ZZG-5a-1", [finding(EXISTING)], opened=[]))
    opened = _count(tmp_path, "opened", _rec("ZZG-5a-2", [finding(EXISTING)], opened=[EXISTING]))
    assert opened == []
    assert len(unopened) == 1 and EXISTING in unopened[0]["message"], unopened


def test_an_undecided_finding_is_not_a_rule_check_failure(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: discrimination
    """An undecided finding is an approval hold, not a family finding: the stage must not fail on it.

    Wrong version caught: the family reports `decision is None` (the designer would loop for nothing).
    Control row in the same call (so the test cannot pass because the family is absent): a finding for
    an undeclared file IS reported. Undecided rows: a non-consistent verdict with no decision, and a
    decided one, give no finding.
    """
    undecided = finding(EXISTING, DESCRIBES, line_range="1-4")
    decided = finding(EXISTING, DESCRIBES, line_range="1-4", decided=decision())
    tmp = tmp_path
    proof = _count(tmp, "proof", _rec("ZZG-6a-1", [finding(EXISTING), finding(OTHER, "consistent")], [EXISTING, OTHER]))
    waiting = _count(tmp, "undecided", _rec("ZZG-6a-2", [undecided]))
    done = _count(tmp, "decided", _rec("ZZG-6a-3", [decided]))
    assert len(proof) == 1, "the family is not evaluating records with file_findings"
    assert waiting == [] and done == []


def test_records_without_file_findings_are_not_evaluated(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: boundary
    """Only a record whose `file_findings` is a list is evaluated: absent field (step not run) gives none.

    One store, two records: A has no field at all, B has a list naming an undeclared file. Exactly one
    finding in total, and it is B's, so the control proves the family ran over the same store.
    """
    plain = leaf("ZZG-7a-1", [], declared_files=_DECLARED)
    del plain[FINDINGS], plain[OPENED]
    broken = _rec("ZZG-7a-2", [finding(EXISTING), finding(OTHER, "consistent")], [EXISTING, OTHER])
    store = make_store(tmp_path, [plain, broken])
    code_repo(store)
    from _rule_check_fixtures import check_store  # noqa: PLC0415

    _code, report = check_store(store, stage="itpo")
    mine = [f for f in report["findings"] if f["rule_family"] == FAMILY]
    assert [f["record_id"] for f in mine] == ["ZZG-7a-2"], mine


def test_family_is_registered_and_the_cli_fails_on_it(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: reachability
    """The real rule-check CLI (subprocess) reports this family, fails the verdict, and repairs nothing.

    Entry point: `python scripts/ac_store/requirement_rule_check.py --location .. --stage test-design`.
    The report names the family in family_counts (evaluated 1) with one `needs a decision` finding naming
    the stray file; the exit code is non-zero; every byte of the store is unchanged after the run; and
    `_rc_report.FAMILY_FILE_FINDINGS` is the same string the report uses.
    """
    import _rc_report  # noqa: PLC0415

    store = make_store(tmp_path, [_rec("ZZG-8a-1", [finding(EXISTING), finding(OTHER, "consistent")], [EXISTING, OTHER])])
    code_repo(store)
    before = snapshot_tree(store.folder)

    run = run_cli_subprocess(cli_argv(store, stage="test-design"), cwd=store.repo_root)

    assert _rc_report.FAMILY_FILE_FINDINGS == FAMILY
    assert run.exit_code != 0, run.stdout[:400]
    assert run.report["family_counts"][FAMILY]["evaluated"] == 1, run.report["family_counts"]
    mine = [f for f in run.report["findings"] if f["rule_family"] == FAMILY]
    assert len(mine) == 1 and OTHER in mine[0]["message"] and mine[0]["disposition"] == "needs a decision", mine
    assert snapshot_tree(store.folder) == before, "the rule check must not repair or rewrite records"
