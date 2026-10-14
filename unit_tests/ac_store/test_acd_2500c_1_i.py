"""
MODULE: unit_tests/ac_store/test_acd_2500c_1_i.py
COVERS: ACD-2500c-1-i
GOAL: Red-first specification of ticket 30: the requirement rule check's new family
    "test design grounding" rejects a code-aware test-design entry that names a file neither in
    the tree nor declared to-be-created, reports a design whose opened-files list is empty as
    not grounded, leaves legacy designs alone, and reports a to-be-created entry on a record in
    the "no declared files" state as `not evaluated: no declared files` (never passed, never
    rejected). Also the small extension of G4 architect note section 4 (conflict 15): no-clause,
    dangling-clause, missing-dir and missing-convention.
BUSINESS CONTEXT: ADR-071 / ticket 29 note, section 4. A design that names a file nobody opened
    is how a test-writer ends up asserting against code that does not exist; the family judges
    only designs carrying the authorship mark (legacy exemption through is_legacy_design's
    negation) and reads declared files only through declared_files.get_declared_files.
ARCHITECTURE: The family is run through the REAL CLI (requirement_rule_check.main in process, the
    script as a subprocess for the reachability test) over records written with yaml.safe_dump and
    a tmp tree holding the files the entries name (unit_tests/ac_store/_rule_check_fixtures.py).
    Finding shape: rule_family "test design grounding"; disposition `needs a decision`;
    detail {"kind": "absent"|"not-grounded"|"no-clause"|"dangling-clause"|"missing-dir"|
    "missing-convention", "entry": <test_spec entry name>, "path": <path>} (entry and path are
    absent for not-grounded); the not evaluated finding carries the label
    "not evaluated: no declared files". Interpretation: `entry` is the entry's `name`.
RED STATE: the family does not exist, so no finding appears under it (an ASSERTION red); the
    registration test is an ABSENCE red (the constant / module is missing).
NEGATIVE-ROW CONTROLS: every "no finding" claim sits in a store with a record that must yield
    exactly one finding, so a missing family cannot pass it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ac_store"))

from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS, check_store, cli_argv, findings_for, intent_criteria, intent_record, make_store,
    run_cli_subprocess, valid_record,
)

FAMILY = "test design grounding"
STAGE = "test-design"
CLAUSES = ["the design is accepted", "the author is reported", "the gap is named"]
EXISTING = "scripts/ac_store/existing_unit.py"
NEW = "scripts/ac_store/new_unit.py"
ABSENT = "scripts/does_not_exist.py"
CONVENTION = "unit_tests/ac_store/test_convention.py"
OPENED = [EXISTING, CONVENTION]
NOT_EVALUATED = "not evaluated: no declared files"


def entry(name, clause, code_file=EXISTING, to_be_created=False, **extra):
    """One code-aware test_spec entry (the ACD-2500c-3 shape)."""
    item = {
        "name": name, "target_dir": "unit_tests/ac_store/", "framework": "pytest", "type": "unit",
        "angle": "criterion", "description": f"Asserts: {clause}.", "proves_clause": clause,
        "code_file": code_file, "to_be_created": to_be_created, "convention_test_file": CONVENTION,
    }
    item.update(extra)
    return item


def good_entries():
    """E1 (existing file) and E2 (to-be-created file, declared by `design`'s default)."""
    return [entry("test_e1", CLAUSES[0]), entry("test_e2", CLAUSES[1], NEW, True)]


def design(record_id, entries=None, *, clauses=CLAUSES[:2], declared=..., opened=..., marked=True, **overrides):
    """A code-aware record: intent over `clauses`, `entries` as test_spec, mark and opened list.

    `declared=...` declares NEW as to_be_created; `declared=None` leaves declared_files out (the
    "no declared files" state); `opened=...` is OPENED, `opened=None` drops the key.
    """
    fields = {"test_spec": good_entries() if entries is None else entries}
    fields["declared_files"] = [{"path": NEW, "state": "to_be_created"}] if declared is ... else declared
    if marked:
        fields["test_design_authorship"] = {"step": "test-designer", "date": "2026-10-14"}
        if opened is not None:
            fields["test_design_opened_files"] = list(OPENED) if opened is ... else opened
    if fields["declared_files"] is None:
        del fields["declared_files"]
        overrides["drop"] = ("declared_files",)
    return intent_record(record_id, list(clauses), **fields, **overrides)


def build(tmp_path, *records):
    """The tmp repo: the records plus the files the entries name (EXISTING, the convention test)."""
    store = make_store(tmp_path, list(records))
    for rel in (EXISTING, CONVENTION):
        target = store.repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("X = 1\n", encoding="utf-8")
    return store


def run(store):
    """Run the check at the test-design stage; the fixture itself must be clean of foreign blockers."""
    code, report = check_store(store, stage=STAGE)
    foreign = [f for f in report["findings"] if f["rule_family"] != FAMILY and f["disposition"] in BLOCKERS]
    assert not foreign, f"the fixture records must be valid for every other family: {foreign}"
    return code, report


def family(report, record_id):
    return findings_for(report, record_id, FAMILY)


def one_finding(report, record_id, kind):
    """The record's single family finding, asserted to be a `needs a decision` of `kind` naming the record."""
    found = family(report, record_id)
    assert len(found) == 1, f"{record_id}: expected exactly one {FAMILY!r} finding, got {found}"
    assert found[0]["disposition"] == "needs a decision"
    assert found[0]["detail"]["kind"] == kind, found[0]
    assert record_id in found[0]["message"]
    return found[0]


def test_entry_naming_undeclared_missing_file_rejected(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """E3 (scripts/does_not_exist.py, neither present nor declared) yields ONE finding naming the record, the
    entry and the path; E1 and E2 yield none. An entry merely FLAGGED to_be_created, with the path not among
    the declared files, is rejected too (python-coder: judge against the declared files, never the flag)."""
    e3 = entry("test_e3", CLAUSES[2], ABSENT)
    flagged = entry("test_flagged", CLAUSES[1], "scripts/ac_store/flagged_only.py", True)
    store = build(
        tmp_path,
        design("ZZG-101", [*good_entries(), e3], clauses=CLAUSES),
        design("ZZG-102", [entry("test_e1", CLAUSES[0]), flagged]),
        design("ZZG-100"),
    )

    code, report = run(store)

    absent = one_finding(report, "ZZG-101", "absent")
    assert absent["detail"]["path"] == ABSENT and absent["detail"]["entry"] == "test_e3"
    assert ABSENT in absent["message"] and "test_e3" in absent["message"]
    flagged_finding = one_finding(report, "ZZG-102", "absent")
    assert flagged_finding["detail"]["path"] == "scripts/ac_store/flagged_only.py"
    assert family(report, "ZZG-100") == []  # control: E1 and E2 alone are fine
    assert code != 0 and report["verdict"] == "failed"


def test_existing_and_declared_to_be_created_entries_pass(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: criterion
    """E1 (existing code file, existing test directory) and E2 (to-be-created file the record declares) produce
    no finding and no `not evaluated`; the negative row in the SAME store proves the family is alive, and a
    store with only the good record passes."""
    store = build(tmp_path, design("ZZG-100"), design("ZZG-101", [entry("test_e3", CLAUSES[0], ABSENT)], clauses=CLAUSES[:1]))

    _, report = run(store)

    assert family(report, "ZZG-100") == []
    assert [f["detail"]["path"] for f in family(report, "ZZG-101")] == [ABSENT]
    only_good = build(tmp_path / "alone", design("ZZG-100"))
    code, alone = run(only_good)
    assert code == 0 and alone["verdict"] == "passed" and FAMILY in alone["family_counts"]


def test_empty_opened_files_reported_not_grounded(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: boundary
    """A design whose test_design_opened_files is empty, or missing, is reported not grounded, naming the
    record; the same design with an opened list is not (control)."""
    store = build(tmp_path, design("ZZG-101", opened=[]), design("ZZG-102", opened=None), design("ZZG-103"))

    _, report = run(store)

    one_finding(report, "ZZG-101", "not-grounded")
    one_finding(report, "ZZG-102", "not-grounded")
    assert family(report, "ZZG-103") == []


def test_legacy_design_not_evaluated_for_grounding(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: criterion
    """Wrong version caught: judging every test_spec whatever the authorship mark. A legacy design (test_spec, no authorship mark, no opened list, an entry naming an absent file) is not
    evaluated by this family at all: no finding of any kind. A marked design with no test_spec is skipped too.
    The marked, ungrounded control in the same store yields exactly one finding."""
    legacy = design("ZZG-101", [entry("test_old", CLAUSES[0], ABSENT)], clauses=CLAUSES[:1], marked=False)
    no_spec = design("ZZG-102", opened=[])
    del no_spec["test_spec"]
    store = build(tmp_path, legacy, no_spec, design("ZZG-103", opened=[]))

    _, report = run(store)

    assert family(report, "ZZG-101") == [], "legacy designs are exempt"
    assert family(report, "ZZG-102") == [], "no test_spec: nothing to ground"
    one_finding(report, "ZZG-103", "not-grounded")


def test_to_be_created_entry_without_declared_files_not_evaluated(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: boundary
    """On a 'no declared files' record a to-be-created entry is reported `not evaluated: no declared files`:
    one non-blocking finding, never a `needs a decision`, never silently passed; the existing-file entry is
    still judged on existence (ZZG-102 names an absent, not-to-be-created file: a real rejection)."""
    unconfirmable = design("ZZG-101", declared=None)
    absent_entry = design("ZZG-102", [entry("test_e1", CLAUSES[0]), entry("test_e3", CLAUSES[1], ABSENT)], declared=None)
    store = build(tmp_path, unconfirmable, absent_entry)

    _, report = run(store)

    found = family(report, "ZZG-101")
    assert len(found) == 1, found
    assert found[0]["disposition"] == "not evaluated" and NOT_EVALUATED in found[0]["message"]
    assert [f["detail"]["path"] for f in family(report, "ZZG-102") if f["disposition"] == "needs a decision"] == [ABSENT]
    assert report["family_counts"][FAMILY]["not_evaluated"] >= 1


def test_entry_without_proves_clause_reported_no_clause(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """A marked entry without proves_clause is reported `no-clause`; the clause-bearing record is not."""
    bare = entry("test_e1", CLAUSES[0])
    del bare["proves_clause"]
    store = build(tmp_path, design("ZZG-101", [bare, entry("test_e2", CLAUSES[1], NEW, True)]), design("ZZG-100"))

    _, report = run(store)

    assert one_finding(report, "ZZG-101", "no-clause")["detail"]["entry"] == "test_e1"
    assert family(report, "ZZG-100") == []


def test_entry_clause_matching_no_intent_clause_reported_dangling(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """An entry whose proves_clause matches no test_intent clause is `dangling-clause`; a clause matching
    under normalisation (trailing '.') is not; a record with no test_intent is not checked."""
    dangling = [entry("test_e1", "a clause nobody wrote"), entry("test_e2", CLAUSES[1], NEW, True)]
    punctuated = [entry("test_e1", CLAUSES[0] + "."), entry("test_e2", CLAUSES[1], NEW, True)]
    no_intent = valid_record(
        "ZZG-103", criteria=intent_criteria(CLAUSES[:2]), test_spec=dangling, declared_files=[{"path": NEW, "state": "to_be_created"}],
        test_design_authorship={"step": "test-designer", "date": "2026-10-14"}, test_design_opened_files=list(OPENED),
    )
    store = build(tmp_path, design("ZZG-101", dangling), design("ZZG-102", punctuated), no_intent)

    _, report = run(store)

    assert one_finding(report, "ZZG-101", "dangling-clause")["detail"]["entry"] == "test_e1"
    assert family(report, "ZZG-102") == []
    assert family(report, "ZZG-103") == []


def test_entry_target_dir_missing_reported(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """An entry whose target_dir is not in the tree is `missing-dir`, naming the directory; the entry with
    an existing directory is not."""
    bad = [entry("test_e1", CLAUSES[0], target_dir="unit_tests/no_such_dir/"), entry("test_e2", CLAUSES[1], NEW, True)]
    store = build(tmp_path, design("ZZG-101", bad), design("ZZG-100"))

    _, report = run(store)

    finding = one_finding(report, "ZZG-101", "missing-dir")
    assert finding["detail"]["path"].rstrip("/") == "unit_tests/no_such_dir"
    assert family(report, "ZZG-100") == []


def test_cited_convention_file_missing_reported(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """A cited convention_test_file that is not in the tree is `missing-convention`; an entry citing none is
    not reported (the key is optional)."""
    ghost = "unit_tests/ac_store/test_ghost.py"
    bad = [entry("test_e1", CLAUSES[0], convention_test_file=ghost), entry("test_e2", CLAUSES[1], NEW, True)]
    uncited = [entry("test_e1", CLAUSES[0]), entry("test_e2", CLAUSES[1], NEW, True)]
    del uncited[0]["convention_test_file"]
    store = build(tmp_path, design("ZZG-101", bad), design("ZZG-100", uncited))

    _, report = run(store)

    assert one_finding(report, "ZZG-101", "missing-convention")["detail"]["path"] == ghost
    assert family(report, "ZZG-100") == []


def test_grounding_family_is_registered_and_declared_for_deploy():
    # covers: ACD-2500c-1-i
    # angle: criterion
    """The family follows the G2 recipe: the name constant lives in _rc_report, the module _rc_design_grounding
    exposes it as NAME, requirement_rule_check.FAMILIES lists it after _rc_test_intent, and the module is one
    entry of RULE_CHECK_DEPLOY_MAP (never a line in build_phases_ac_store.py)."""
    import _rc_report
    import build_phases_ac_store_rc as deploy
    import requirement_rule_check

    assert _rc_report.FAMILY_TEST_DESIGN_GROUNDING == FAMILY
    names = [getattr(module, "NAME", None) for module in requirement_rule_check.FAMILIES]
    assert FAMILY in names and names.index(FAMILY) > names.index(_rc_report.FAMILY_TEST_INTENT)
    declared = [src for src, _dest in deploy.RULE_CHECK_DEPLOY_MAP]
    assert declared.count("scripts/ac_store/_rc_design_grounding.py") == 1


def test_acd_2500c_1_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: reachability
    """Entry point (resolved: CLI script, step 1): `python scripts/ac_store/requirement_rule_check.py` in a real
    subprocess at the test-design stage. The workflow consumes the exit code and the verdict: the ungrounded
    store exits non-zero with the family's finding; the grounded one exits 0 with the family evaluated."""
    bad = build(tmp_path / "bad", design("ZZG-101", [*good_entries(), entry("test_e3", CLAUSES[2], ABSENT)], clauses=CLAUSES))
    good = build(tmp_path / "good", design("ZZG-100"))

    failed = run_cli_subprocess(cli_argv(bad, stage=STAGE), cwd=bad.repo_root)
    passed = run_cli_subprocess(cli_argv(good, stage=STAGE), cwd=good.repo_root)

    assert failed.exit_code != 0 and failed.report["verdict"] == "failed"
    assert [f["detail"]["path"] for f in findings_for(failed.report, "ZZG-101", FAMILY)] == [ABSENT]
    assert passed.exit_code == 0 and passed.report["verdict"] == "passed"
    assert FAMILY in passed.report["family_counts"]
