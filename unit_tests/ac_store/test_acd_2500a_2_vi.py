"""
MODULE: test_acd_2500a_2_vi
GOAL: Red-first specification of ACD-2500a-2-vi: a field the test-design stage does not
    own, changed on a record that already existed, is reported by the rule family
    "protected fields" as `needs a decision` and fails the stage; the family repairs
    nothing, lists a new record `not evaluated: new record`, and never mistakes the rule
    check's own back-link repair for a stage edit (ticket 02).
BUSINESS CONTEXT: ADR-072 names "the rule check, run with --before-ref HEAD" as the
    deterministic backstop for the fields templates/agents/test-designer.md tells the
    test designer never to touch. This family is that backstop.
ARCHITECTURE: A tmp git repo (_protected_fields_fixtures): HEAD is the stage's
    before-state, the working tree holds the stage's edits, the check runs with
    `--before-ref HEAD --stage test-design`. The before-state is coherent, so in the
    stage-owned-only control the whole check passes today and the family is the only
    thing that can fail it. Contract read here: findings carry detail
    {field, stage, before, after}; the fixed list is the module constant
    PROTECTED_FIELDS of scripts/ac_store/_rc_protected_fields.py; the before-state
    exposes each record's committed fields as BeforeState.committed_record(record).
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _protected_fields_fixtures import (  # noqa: E402
    DECISION,
    FAMILY_PROTECTED,
    L1,
    NEW_CRITERIA,
    NOT_EVALUATED,
    R0,
    R1,
    R2,
    R3,
    apply_stage_owned_edits,
    apply_vi_scenario,
    committed_store,
    decisions,
    edit,
    family_module,
    field_of,
    file_findings_fill,
    four_field_spec,
    protected,
    run_stage,
    stage_start_records,
)
from _rule_check_fixtures import (  # noqa: E402
    FAMILY_BACKLINKS,
    REPO_ROOT,
    SCRIPTS_DIR,
    BLOCKERS,
    cli_argv,
    finding_text,
    findings_for,
    run_cli_subprocess,
    snapshot_tree,
    write_snapshot,
)

_STAGE = "test-design"
_THREE = {(R1, "criteria"), (R2, "assigned_agent"), (R2, "expects_from")}
_CLAUSE_FIELDS = {
    "criteria", "test_intent", "assigned_agent", "implements_pattern", "pattern_bindings",
    "declared_files", "covered_by", "delivers_to", "expects_from", "test_required",
}
_STAGE_OWNED = (
    "test_spec", "test_design_authorship", "test_design_opened_files", "file_findings",
    "file_findings_opened_files", "reference_file_path", "hold_reason",
)
_TEMPLATE = REPO_ROOT / "templates" / "agents" / "test-designer.md"


def _scenario(tmp_path):
    store = committed_store(tmp_path, stage_start_records())
    apply_vi_scenario(store)
    return store


def test_protected_field_changes_reported_as_three_decisions(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: criterion
    """Exactly three 'protected fields' findings, each 'needs a decision', for
    (R1, criteria), (R2, assigned_agent), (R2, expects_from); each names the record's
    file, its id, the field and the stage test-design."""
    store = _scenario(tmp_path)

    _, report = run_stage(store, _STAGE)

    found = [f for f in protected(report) if f["disposition"] == DECISION]
    assert len(found) == 3, protected(report)
    assert decisions(report) == _THREE
    for finding in found:
        assert finding["file"] == store.rel(finding["record_id"])
        text = finding_text(finding)
        assert field_of(finding) in text and _STAGE in text, finding


def test_assigned_agent_finding_states_before_and_after(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: criterion
    """The assigned_agent finding's detail carries before 'python-coder' (the committed
    record) and after 'llm-expert' (the working tree); swapped sources fail."""
    store = _scenario(tmp_path)

    _, report = run_stage(store, _STAGE)

    found = [f for f in protected(report, R2) if field_of(f) == "assigned_agent"]
    assert len(found) == 1, protected(report)
    detail = found[0]["detail"]
    assert detail["before"] == "python-coder"
    assert detail["after"] == "llm-expert"
    assert detail["stage"] == _STAGE


def test_before_state_carries_committed_field_values(tmp_path, monkeypatch):
    # covers: ACD-2500a-2-vi
    # angle: discrimination
    """BeforeState(ref=HEAD), after one prefetch, gives R2's committed assigned_agent,
    expects_from and it_requirements from the ONE `git cat-file --batch` call while the
    working tree holds llm-expert; the (existed, readiness) lookup is unchanged."""
    store = _scenario(tmp_path)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import _rc_records  # noqa: PLC0415

    calls: list[list[str]] = []
    real_run = _rc_records.subprocess.run

    def counting_run(argv, *args, **kwargs):
        calls.append(list(argv))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(_rc_records.subprocess, "run", counting_run)
    records, _, _ = _rc_records.load_folder(store.folder, store.repo_root)
    by_id = {r["id"]: r for r in records}
    state = _rc_records.BeforeState(ref="HEAD")

    state.prefetch(records, store.repo_root)

    assert sum("cat-file" in argv for argv in calls) == 1, calls
    assert len(calls) == 2, calls  # rev-parse --verify + the one batch read, nothing per record
    assert by_id[R2]["assigned_agent"] == "llm-expert"  # the working tree
    committed = getattr(state, "committed_record", None)
    assert callable(committed), "BeforeState must expose committed_record(record): the committed fields"
    before = committed(by_id[R2])
    assert before["assigned_agent"] == "python-coder"
    assert before["expects_from"] == {"ac_id": R1, "contract": "One row per run, read back by id."}
    assert before["it_requirements"] == four_field_spec()
    assert committed(by_id[R3]) is None
    assert state.lookup(by_id[R2]) == (True, "draft")
    assert state.lookup(by_id[R3]) == (False, None)


def test_stage_owned_fields_raise_no_finding(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: boundary
    """No 'protected fields' finding names a field the test-design stage owns. Control in
    the same store: the criteria change IS reported, so an empty family cannot pass."""
    store = _scenario(tmp_path)

    _, report = run_stage(store, _STAGE)

    for finding in protected(report):
        assert not any(name in field_of(finding) for name in _STAGE_OWNED), finding
    assert (R1, "criteria") in decisions(report)


def test_family_changes_no_record(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: criterion
    """The family reports R1's and R2's fields and leaves both files byte-identical, so
    every reported field keeps the value the stage left."""
    store = _scenario(tmp_path)
    before = snapshot_tree(store.folder)

    _, report = run_stage(store, _STAGE)

    assert decisions(report) == _THREE
    after = snapshot_tree(store.folder)
    for rid in (R1, R2):
        assert after[f"{rid}.yaml"] == before[f"{rid}.yaml"], rid
    assert store.read(R1)["criteria"] == NEW_CRITERIA
    assert store.read(R2)["assigned_agent"] == "llm-expert"


def test_protected_field_finding_fails_stage_verdict(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: criterion
    """The run's verdict is failed, main() returns 1, and every blocker is the family's.
    Control: the same store whose only stage edits are stage-owned passes with exit 0."""
    store = _scenario(tmp_path / "changed")

    exit_code, report = run_stage(store, _STAGE)

    assert report["verdict"] == "failed" and exit_code == 1
    blockers = {f["rule_family"] for f in report["findings"] if f["disposition"] in BLOCKERS}
    assert blockers == {FAMILY_PROTECTED}, report["findings"]

    control = committed_store(tmp_path / "control", stage_start_records())
    apply_stage_owned_edits(control)
    control_exit, control_report = run_stage(control, _STAGE)
    assert control_report["verdict"] == "passed" and control_exit == 0, control_report["findings"]


def test_new_record_listed_not_evaluated_new_record(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: boundary
    """R3 (absent from HEAD) gets exactly one 'not evaluated' finding reading 'not
    evaluated: new record', is not reported as changed, and is counted under
    not_evaluated."""
    store = _scenario(tmp_path)

    _, report = run_stage(store, _STAGE)

    found = protected(report, R3)
    assert len(found) == 1, found
    assert found[0]["disposition"] == NOT_EVALUATED
    assert "not evaluated: new record" in found[0]["message"]
    assert report["family_counts"][FAMILY_PROTECTED]["not_evaluated"] == 1


def test_readiness_only_snapshot_lists_records_not_evaluated(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: boundary
    """With a readiness-only --before-snapshot instead of --before-ref, the family lists
    every record 'not evaluated' and raises no decision (never a pass); the readiness
    family still restores R1's agent-raised approval from the snapshot."""
    store = _scenario(tmp_path)
    edit(store, R1, lambda r: r.update(readiness="approved"))
    snapshot = write_snapshot(store, {R1: "draft"})

    _, report = run_stage(store, _STAGE, "--before-snapshot", str(snapshot))

    found = protected(report)
    assert {f["record_id"] for f in found} == {R0, L1, R1, R2, R3}
    assert {f["disposition"] for f in found} == {NOT_EVALUATED}
    assert len(found) == 5
    assert store.read(R1)["readiness"] == "draft"


def _template_fields() -> set[str]:
    """The fields test-designer.md's 'Never touch these fields' sentence names, plus test_required."""
    text = " ".join(_TEMPLATE.read_text(encoding="utf-8").split())
    match = re.search(r"Never touch these fields, which stay byte-identical before and after your run: (.*?)\.", text)
    assert match, "test-designer.md lost its 'Never touch these fields' sentence"
    names = set()
    for item in match.group(1).split(","):
        item = re.sub(r"^and ", "", item.strip())
        names.add("it_requirements" if "it_requirements" in item else item)
    either = re.search(r"Do not touch (\w+) either", text)
    assert either, "test-designer.md lost its 'Do not touch test_required either' sentence"
    return names | {either.group(1)}


def _diff(left: set[str], right: set[str], left_name: str, right_name: str) -> str:
    return (f"only in {left_name}: {sorted(left - right)}; "
            f"only in {right_name}: {sorted(right - left)}")


def test_protected_field_list_matches_test_designer_template(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: discrimination
    """Parity: PROTECTED_FIELDS equals the clause's list and the template's never-touch
    list (plus test_required), naming any one-sided field; requirement_rule_check.py holds
    no second copy. Behaviour: filling reference_file_path is not reported, changing
    another it_requirements key is."""
    module = family_module()
    held = set(module.PROTECTED_FIELDS) - {"it_requirements"}
    template = _template_fields() - {"it_requirements"}
    assert held == _CLAUSE_FIELDS, _diff(held, _CLAUSE_FIELDS, "PROTECTED_FIELDS", "the clause")
    assert held == template, _diff(held, template, "PROTECTED_FIELDS", "test-designer.md")
    tree = ast.parse((SCRIPTS_DIR / "requirement_rule_check.py").read_text(encoding="utf-8"))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (literals & _CLAUSE_FIELDS), f"second copy in requirement_rule_check.py: {literals & _CLAUSE_FIELDS}"

    filled = committed_store(tmp_path / "filled", stage_start_records())
    edit(filled, R2, file_findings_fill)
    _, filled_report = run_stage(filled, _STAGE)
    assert [f for f in protected(filled_report, R2) if f["disposition"] == DECISION] == []

    other = committed_store(tmp_path / "other", stage_start_records())
    edit(other, R2, lambda r: (file_findings_fill(r), r["it_requirements"].update(n_location_rule="2")))
    _, other_report = run_stage(other, _STAGE)
    found = [f for f in protected(other_report, R2) if f["disposition"] == DECISION]
    assert len(found) == 1, found
    assert "n_location_rule" in finding_text(found[0]) and "it_requirements" in field_of(found[0])
    assert "reference_file_path" not in field_of(found[0])


def test_backlink_repair_in_same_run_not_reported_as_stage_change(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: seam
    """The committed L1 lacks R2; the back-link family appends it ('fixed') and pass 2's
    new covered_by entry is not a 'protected fields' finding. Control: a covered_by entry
    the stage itself added to R1 is reported."""
    records = stage_start_records()
    next(r for r in records if r["id"] == L1)["covered_by"] = [R1, R3]
    store = committed_store(tmp_path, records)
    apply_stage_owned_edits(store)
    edit(store, R1, lambda r: r.update(covered_by=["ACD-9990a-1-i"]))

    _, report = run_stage(store, _STAGE)

    fixed = findings_for(report, record_id=L1, rule_family=FAMILY_BACKLINKS)
    assert [f["disposition"] for f in fixed] == ["fixed"]
    assert R2 in store.read(L1)["covered_by"]
    assert [f for f in protected(report, L1) if f["disposition"] == DECISION] == []
    assert decisions(report) == {(R1, "covered_by")}


def test_protected_fields_reachable_from_cli(tmp_path):
    # covers: ACD-2500a-2-vi
    # angle: reachability
    """`python scripts/ac_store/requirement_rule_check.py --stage test-design --location
    <tmp folder> --before-ref HEAD` exits 1 and its one JSON report holds the criteria
    finding under 'protected fields'."""
    store = _scenario(tmp_path)

    run = run_cli_subprocess(cli_argv(store, "--before-ref", "HEAD", stage=_STAGE), cwd=store.repo_root)

    assert run.exit_code == 1, run.stderr
    assert (R1, "criteria") in decisions(run.report)


def test_protected_fields_module_in_rule_check_deploy_map():
    # covers: ACD-2500a-2-vi
    # angle: seam
    """RULE_CHECK_DEPLOY_MAP lists the family module and requirement_rule_check.FAMILIES
    registers it, so the installed check /plan-feature runs carries the family. Reads
    the tuple only; never spawns build.py."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]];"
         "from build_phases_ac_store_rc import RULE_CHECK_DEPLOY_MAP as M;"
         "import requirement_rule_check as R;"
         "print(('scripts/ac_store/_rc_protected_fields.py', '_rc_protected_fields.py') in M);"
         "print(any(getattr(f, 'NAME', None) == 'protected fields' for f in R.FAMILIES))",
         str(REPO_ROOT / "scripts"), str(SCRIPTS_DIR)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    in_map, registered = proc.stdout.split()
    assert in_map == "True", "_rc_protected_fields.py is missing from RULE_CHECK_DEPLOY_MAP"
    assert registered == "True", "no family named 'protected fields' in requirement_rule_check.FAMILIES"


class _Rec(dict):
    """A record stand-in: a mapping with the .file the family reads."""

    file = "docs/acceptance-criteria/x/R.yaml"


def _changes(committed: dict, current: dict, allowed: tuple = ()):
    from types import SimpleNamespace  # noqa: PLC0415

    return family_module().changes(SimpleNamespace(applied_repairs={}), _Rec(current), committed, allowed)


def test_absent_none_and_empty_are_the_same_value():
    # covers: ACD-2500a-2-vi
    # angle: boundary
    """A field absent or None at stage start and [] / {} / '' now is not a change; a real
    change (None to a non-empty list) still is, so the comparison cannot pass by ignoring all."""
    for empty in ([], {}, ""):
        assert _changes({}, {"delivers_to": empty}) == [], empty
        assert _changes({"covered_by": None}, {"covered_by": empty}) == [], empty
        assert _changes({"covered_by": []}, {}) == [], empty
    assert [c[0] for c in _changes({"covered_by": None}, {"covered_by": ["ACD-1"]})] == ["covered_by"]


def test_two_findings_for_one_file_stay_distinct():
    # covers: ACD-2500a-2-vi
    # angle: discrimination
    """Two file findings on the same file, both with a changed verdict, give two differently
    named sub-fields, so the report's one-finding-per-key dedupe cannot collapse them."""
    before = [{"file": "a.py", "verdict": "x"}, {"file": "a.py", "verdict": "y"}]
    after = [{"file": "a.py", "verdict": "x2"}, {"file": "a.py", "verdict": "y2"}]
    names = [c[0] for c in _changes({"file_findings": before}, {"file_findings": after})]
    assert len(names) == 2 and len(set(names)) == 2, names
    assert all("a.py" in n for n in names), names
