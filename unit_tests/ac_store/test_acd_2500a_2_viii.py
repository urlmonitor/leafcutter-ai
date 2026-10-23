"""
MODULE: test_acd_2500a_2_viii
GOAL: Red-first specification of ACD-2500a-2-viii: a rule-check run given no before-state
    (neither --before-ref nor --before-snapshot) writes no file, lists the
    before-state families `not evaluated: no before-state`, reports the back-link it would
    have appended as `needs a decision` naming the id, and states at the top of the report
    that no before-state was given and nothing was repaired (ticket 05).
BUSINESS CONTEXT: KI-ACS-20261015 -- a hand run without a before-state rewrote readiness
    approved -> draft in 46 done records, because every record looked newly created. The
    fix is total: no before-state, no write of any family.
ARCHITECTURE: The folder is a tmp git repo (committed) holding ACD-9990 (L0), ACD-9990a
    (L1) and ACD-9990a-1 (L2) at readiness approved / work_status done, plus ACD-9990a-4
    (draft) which the L1's covered_by lacks. The hand-run argv is built here, NOT with
    cli_argv (which always adds a --before-snapshot). The stage is test-design: an
    authoring stage listed in the protected-fields owner map, so "no before-state" is the
    only reason that family has not to judge. Report contract read here: the additive
    top-level key before_state = {given: bool, repairs_applied: bool}.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_BACKLINKS,
    FAMILY_READINESS,
    SCRIPTS_DIR,
    commit_all,
    finding_text,
    findings_for,
    hierarchy,
    init_git_repo,
    make_store,
    run_cli,
    run_cli_subprocess,
    snapshot_tree,
    valid_record,
)

FAMILY_PROTECTED = "protected fields"
_STAGE = "test-design"
_L0, _L1, _CHILD, _NEW = "ACD-9990", "ACD-9990a", "ACD-9990a-1", "ACD-9990a-4"
_APPROVED = (_L0, _L1, _CHILD)
_ALL = (*_APPROVED, _NEW)
_NO_BEFORE_STATE = "not evaluated: no before-state"


def _store(tmp_path: Path):
    """3 approved/done records plus ACD-9990a-4 missing from its parent's covered_by, committed."""
    records = hierarchy(_L0, 1)
    for record in records:
        record.update(readiness="approved", work_status="done")
    records.append(valid_record(_NEW, level="L2", depends_on=[_L1]))
    store = make_store(tmp_path, records)
    init_git_repo(store.repo_root)
    commit_all(store.repo_root, "stage start")
    return store


def _hand_argv(store) -> list[str]:
    """The hand-run argv: no --before-ref, no --before-snapshot."""
    return ["--location", store.location, "--repo-root", str(store.repo_root), "--stage", _STAGE]


def _hand_run(store) -> tuple[int, dict]:
    return run_cli(_hand_argv(store), cwd=store.repo_root)


def test_run_without_before_state_writes_no_file(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: criterion
    """The folder is byte-identical after the hand run; the 3 records still read approved
    and ACD-9990a's covered_by is unchanged."""
    store = _store(tmp_path)
    before = snapshot_tree(store.folder)
    covered_before = store.read(_L1)["covered_by"]

    _hand_run(store)

    assert snapshot_tree(store.folder) == before
    assert [store.read(rid)["readiness"] for rid in _APPROVED] == ["approved"] * 3
    assert store.read(_L1)["covered_by"] == covered_before == [_CHILD]


def test_before_state_families_list_not_evaluated(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: criterion
    """Every record gets exactly one 'not evaluated' finding reading 'not evaluated: no
    before-state' from the readiness family and one from the 'protected fields' family."""
    store = _store(tmp_path)

    _, report = _hand_run(store)

    for family in (FAMILY_READINESS, FAMILY_PROTECTED):
        found = [f for f in findings_for(report, rule_family=family) if f["record_id"] is not None]
        assert sorted(f["record_id"] for f in found) == sorted(_ALL), (family, found)
        for finding in found:
            assert finding["disposition"] == "not evaluated", finding
            assert _NO_BEFORE_STATE in finding["message"], finding


def test_missing_backlink_reported_as_decision_with_id(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: criterion
    """The back-link finding lands on ACD-9990a as 'needs a decision' (not 'fixed') and
    names ACD-9990a-4, the id that would have been appended."""
    store = _store(tmp_path)

    _, report = _hand_run(store)

    found = findings_for(report, rule_family=FAMILY_BACKLINKS)
    assert len(found) == 1, found
    assert found[0]["record_id"] == _L1 and found[0]["file"] == store.rel(_L1)
    assert found[0]["disposition"] == "needs a decision"
    assert _NEW in finding_text(found[0])


def test_report_states_no_before_state_before_findings(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: discrimination
    """stdout's top-level before_state is exactly {given: false, repairs_applied: false}
    and, in the raw stdout, comes before family_counts and findings; stdout stays one
    JSON document. Control: the --before-ref HEAD run reports before_state.given true."""
    store = _store(tmp_path)

    run = run_cli_subprocess(_hand_argv(store), cwd=store.repo_root)

    assert run.report.get("before_state") == {"given": False, "repairs_applied": False}, run.report.keys()
    position = {key: run.stdout.find(f'\n  "{key}":') for key in ("before_state", "family_counts", "findings")}
    assert -1 not in position.values(), position
    assert position["before_state"] < position["family_counts"] < position["findings"]

    control = run_cli_subprocess([*_hand_argv(store), "--before-ref", "HEAD"], cwd=store.repo_root)
    assert control.report["before_state"]["given"] is True


def test_before_ref_run_repairs_backlink_and_keeps_approved(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: real_artifact
    """The same committed folder run with --before-ref HEAD: the parent file read back from
    disk lists ACD-9990a-4 in covered_by, the finding is 'fixed', and the 3 records still
    read approved."""
    store = _store(tmp_path)

    _, report = run_cli([*_hand_argv(store), "--before-ref", "HEAD"], cwd=store.repo_root)

    on_disk = store.path(_L1).read_text(encoding="utf-8")
    assert _NEW in store.read(_L1)["covered_by"] and _NEW in on_disk
    assert [f["disposition"] for f in findings_for(report, rule_family=FAMILY_BACKLINKS)] == ["fixed"]
    assert [store.read(rid)["readiness"] for rid in _APPROVED] == ["approved"] * 3


def test_hand_run_without_before_state_reachable_from_cli(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: reachability
    """`python scripts/ac_store/requirement_rule_check.py` with the hand-run argv: stdout
    is one JSON document, the folder is byte-identical afterwards, and the authoring
    stage still ends verdict failed (exit 1)."""
    store = _store(tmp_path)
    before = snapshot_tree(store.folder)

    run = run_cli_subprocess(_hand_argv(store), cwd=store.repo_root)

    assert snapshot_tree(store.folder) == before
    assert run.exit_code == 1 and run.report["verdict"] == "failed"


def test_no_before_state_fix_is_total_not_partial(tmp_path, monkeypatch):
    # covers: ACD-2500a-2-viii
    # angle: discrimination
    """With no before-state, no repair of any family reaches the guarded writer: zero
    apply_edit calls, the back-link still reported as a decision, nothing demoted.
    Control: the --before-ref HEAD run hands exactly one repair (the back-link) to it."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import _rc_edit  # noqa: PLC0415
    import requirement_rule_check  # noqa: PLC0415

    calls: list[tuple[str, str]] = []
    real_apply = _rc_edit.apply_edit

    def recording_apply(path, field, how):
        calls.append((Path(path).name, field))
        return real_apply(path, field, how)

    monkeypatch.setattr(requirement_rule_check, "apply_edit", recording_apply)
    monkeypatch.setattr(_rc_edit, "apply_edit", recording_apply)
    store = _store(tmp_path / "hand")

    _, report = _hand_run(store)

    assert calls == []
    assert [f["disposition"] for f in findings_for(report, rule_family=FAMILY_BACKLINKS)] == ["needs a decision"]
    assert [store.read(rid)["readiness"] for rid in _APPROVED] == ["approved"] * 3

    control = _store(tmp_path / "control")
    run_cli([*_hand_argv(control), "--before-ref", "HEAD"], cwd=control.repo_root)
    assert calls == [(f"{_L1}.yaml", "covered_by")]


def test_unresolvable_before_ref_is_treated_as_no_before_state(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: discrimination
    """--before-ref no-such-ref: nothing is written (approved stays approved), before_state.given
    is false, and the readiness family lists the records not evaluated; the setup failure stays."""
    store = _store(tmp_path)
    before = snapshot_tree(store.folder)
    code, report = run_cli([*_hand_argv(store), "--before-ref", "no-such-ref"], cwd=store.repo_root)
    assert snapshot_tree(store.folder) == before
    assert report["before_state"] == {"given": False, "repairs_applied": False}
    assert code == 1
    assert any(f["disposition"] == "failed" and "no-such-ref" in f["message"] for f in report["findings"])
    texts = [f["message"] for f in findings_for(report, record_id=_L1, rule_family=FAMILY_READINESS)]
    assert any("not evaluated" in t for t in texts), texts


def test_unreadable_before_snapshot_is_treated_as_no_before_state(tmp_path):
    # covers: ACD-2500a-2-viii
    # angle: discrimination
    """A --before-snapshot that is not readable JSON writes nothing and reports given false."""
    store = _store(tmp_path)
    bad = tmp_path / "bad_snapshot.json"
    bad.write_text("{not json", encoding="utf-8")
    before = snapshot_tree(store.folder)
    _, report = run_cli([*_hand_argv(store), "--before-snapshot", str(bad)], cwd=store.repo_root)
    assert snapshot_tree(store.folder) == before
    assert report["before_state"] == {"given": False, "repairs_applied": False}
