"""
MODULE: unit_tests/ac_store/test_acd_300c_4.py
COVERS: ACD-300c-4
GOAL: Red-first specification of the approval step's id-list mode with a priority option
    (scripts/ac_store/approve_acs.py --ids A,B --priority P --json): it approves exactly the ids it is
    given and does not hold, writes readiness, priority and ONE appended amended_by entry per record as
    a field-targeted write, never writes a held id, and ships beside the other ac_store scripts so the
    /plan-feature workflow can run its deployed copy.
BUSINESS CONTEXT: Today the final gate's approval is a status-checker agent told to edit YAML; it skips
    the step's hold check, its append-only amended_by entry and its write-then-read-back check.
ARCHITECTURE: The real CLI as a subprocess (cwd = a tmp consumer-style repo; _acd_300c_4_fixtures).
    The workflow half of ACD-300c-4 lives in
    unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4.py.
RED STATE: approve_acs.py has no --ids / --priority (argparse exits 2), and RULE_CHECK_DEPLOY_MAP has
    no approve_acs entry.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300c_4_fixtures import (  # noqa: E402
    BATCH,
    HELD,
    PRIOR_PRIORITY,
    RELEASED,
    UNDECIDED,
    amended_by_of,
    approval_entries,
    approval_entry_lines,
    batch_store,
    report_of,
    run_ids,
    store_bytes,
    today,
)

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
PLAN_FEATURE_JS = REPO / "templates" / "workflows-js" / "plan-feature.js"


def test_id_list_mode_approves_released_ids_with_priority(tmp_path):
    # covers: ACD-300c-4
    # angle: reachability
    """`approve_acs.py --ids ACD-9990a-1,ACD-9990a-2,ACD-9990a-4 --priority high --json` exits 0 and the
    three records read readiness approved and priority high (they were reviewed and low)."""
    store = batch_store(tmp_path)

    run = run_ids(store, RELEASED, priority="high")
    report = report_of(run)

    assert sorted(report["approved"]) == RELEASED, report
    for rid in RELEASED:
        record = store.read(rid)
        assert (record["readiness"], record["priority"]) == ("approved", "high"), (rid, record["readiness"], record["priority"])


def test_id_list_mode_never_writes_a_held_id(tmp_path):
    # covers: ACD-300c-4
    # angle: discrimination
    """Given all four ids, ACD-9990a-3 (an undecided file finding) is reported held with reason "file
    finding undecided" and its file bytes are unchanged: readiness reviewed, priority as before.

    Wrong versions caught: the id-list mode trusts the caller and skips the hold check (the held id is
    approved); the held id is given the new priority while its readiness stays reviewed (bytes change).
    Control: the three released ids are approved in the same run, so the step really wrote.
    """
    store = batch_store(tmp_path)
    before = store_bytes(store, [HELD])

    report = report_of(run_ids(store, BATCH, priority="high"))

    assert report["held"] == [{"id": HELD, "file": store.rel(HELD), "reason": UNDECIDED}], report
    assert HELD not in report["approved"], report
    assert store.path(HELD).read_bytes() == before[HELD], "the held record's file changed"
    held = store.read(HELD)
    assert (held["readiness"], held["priority"]) == ("reviewed", PRIOR_PRIORITY), held
    assert [store.read(rid)["readiness"] for rid in RELEASED] == ["approved"] * 3


def test_approval_appends_one_entry_and_keeps_prior_entries_byte_identical(tmp_path):
    # covers: ACD-300c-4
    # angle: discrimination
    """Each approved record, whose amended_by already holds a multi-line entry (verbatim from a real
    store record), gains exactly one entry at the END of the list recording the approval and today's
    date; every byte of the prior entry is unchanged.

    Wrong versions caught: the block is re-rendered through yaml.dump (the folded note reflows); the new
    entry is inserted at the start of the list; a second approval entry is appended when the priority is
    written in a separate pass (exactly one new entry, exactly one approval entry).
    """
    store = batch_store(tmp_path)
    before = store_bytes(store, RELEASED)
    prior = {rid: amended_by_of(store, rid) for rid in RELEASED}

    report_of(run_ids(store, RELEASED, priority="high"))

    for rid in RELEASED:
        entry_lines = approval_entry_lines(before[rid], store.path(rid).read_bytes(), priority="high")
        appended = yaml.safe_load(textwrap.dedent("".join(entry_lines)))
        assert isinstance(appended, list) and len(appended) == 1, (rid, entry_lines)
        assert appended[0].get("action") == "approved" and str(appended[0].get("date")) == today(), appended
        after = amended_by_of(store, rid)
        assert after[:-1] == prior[rid] and len(after) == len(prior[rid]) + 1, (rid, after)
        assert len(approval_entries(after)) == 1, after


def test_approval_changes_no_other_field_bytes(tmp_path):
    # covers: ACD-300c-4
    # angle: real_artifact
    """The real CLI on the tmp store (all four ids); all 4 files read back from disk against their
    before-bytes: outside readiness, priority and the appended amended_by entry every byte is identical,
    and the held record is identical in full.

    Wrong versions caught: readiness replaced at the first "readiness: reviewed" text anywhere in the
    file (each record carries that text in its `notes` value, BEFORE the readiness key); priority written
    by re-dumping the whole record (keys reorder, the folded note reflows).
    """
    store = batch_store(tmp_path)
    before = store_bytes(store, BATCH)

    run = run_ids(store, BATCH, priority="high")
    assert run.exit_code == 0, run.stderr[-600:]

    after = store_bytes(store, BATCH)
    for rid in RELEASED:
        approval_entry_lines(before[rid], after[rid], priority="high")
    assert after[HELD] == before[HELD]


def _rc_map() -> list[tuple[str, str]]:
    sys.path.insert(0, str(SCRIPTS))
    import build_phases_ac_store_rc as rc_map  # noqa: PLC0415

    return list(rc_map.RULE_CHECK_DEPLOY_MAP)


def test_approval_step_is_deployed_where_the_workflow_runs_it():
    # covers: ACD-300c-4
    # angle: deployed
    """In process, no build.py: RULE_CHECK_DEPLOY_MAP holds ('scripts/ac_store/approve_acs.py',
    'approve_acs.py'); every scripts/ac_store module in approve_acs.py's import closure (_approval_holds
    and what it imports) is an entry of the ac_store deploy map; and plan-feature.js runs the step from the
    deployed .leafcutter/scripts/ac_store/ copy, never from the source path.

    Wrong versions caught: approve_acs.py deployed while the workflow still invokes
    scripts/ac_store/approve_acs.py from the source path; approve_acs added to the map while a module it
    imports is left out (the deployed copy fails on import). A run from the deployed layout needs POSIX
    flock (shared_reference_layout) and runs only on CI; the existing deploy-map parity checks
    (test_acd_2500a_1_deploy_declaration.py) are left to stay green.
    """
    assert ("scripts/ac_store/approve_acs.py", "approve_acs.py") in _rc_map()

    import build_phases_ac_store as phase  # noqa: PLC0415
    import build_referential_integrity as bri  # noqa: PLC0415

    deployed = {src for src, _dest in phase.AC_STORE_DEPLOY_MAP}
    closure = bri.compute_intra_package_closure(REPO / "scripts" / "ac_store" / "approve_acs.py", REPO)
    modules = {m for m in closure if m.startswith("scripts/ac_store/") and m.endswith(".py")}
    assert "scripts/ac_store/_approval_holds.py" in modules, sorted(modules)  # control: closure is non-trivial
    assert modules <= deployed, sorted(modules - deployed)

    source = PLAN_FEATURE_JS.read_text(encoding="utf-8")
    assert "approve_acs.py" in source, "plan-feature.js never runs the approval step"
    source_path_runs = [
        line.strip() for line in source.splitlines()
        if "scripts/ac_store/approve_acs.py" in line and ".leafcutter/scripts/ac_store/approve_acs.py" not in line
    ]
    assert source_path_runs == [], source_path_runs


# --------------------------------------------------------------------------
# review fixes: H-1 (any readiness), M-1 (missing priority line), L-2, L-3
# --------------------------------------------------------------------------
from _acd_2500b_approval_fixtures import run_approve  # noqa: E402
from _acd_300c_4_fixtures import (  # noqa: E402
    PENDING,
    records_store,
    reviewed_intent,
    reviewed_no_tests,
    strip_lines,
)

DRAFT, NOLINE, DRAFT_HELD = "ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-3"


def _mixed_store(tmp_path):
    """A draft leaf, a leaf with no readiness line, and a draft leaf held for a missing test design."""
    store = records_store(tmp_path, [
        reviewed_no_tests(DRAFT, readiness="draft", priority=PRIOR_PRIORITY),
        reviewed_no_tests(NOLINE, priority=PRIOR_PRIORITY),
        reviewed_intent(DRAFT_HELD, readiness="draft", priority=PRIOR_PRIORITY),
    ])
    strip_lines(store, NOLINE, "readiness")
    return store


def test_ids_mode_approves_draft_and_unset_readiness_records(tmp_path):
    # covers: ACD-300c-4
    # angle: failure
    """A non-held record at readiness draft, and one with no readiness line, is approved like a reviewed
    one (the old final-gate flow approved every non-held id): exit 0, readiness approved, priority high,
    one approval entry each. The batch's PO/BA records are typically still draft."""
    store = _mixed_store(tmp_path)

    report = report_of(run_ids(store, [DRAFT, NOLINE], priority="high"))

    assert sorted(report["approved"]) == [DRAFT, NOLINE], report
    for rid in (DRAFT, NOLINE):
        record = store.read(rid)
        assert (record["readiness"], record["priority"]) == ("approved", "high"), (rid, record)
        assert len(approval_entries(amended_by_of(store, rid))) == 1


def test_ids_mode_holds_a_draft_record_before_anything_else(tmp_path):
    # covers: ACD-300c-4
    # angle: discrimination
    """A draft record with test intent and no design is reported held ("test design pending") and its file
    is byte-identical; the readiness check never lets a held draft through or turns it into an exit 2."""
    store = _mixed_store(tmp_path)
    before = store_bytes(store, [DRAFT_HELD])

    run = run_ids(store, [DRAFT, DRAFT_HELD], priority="high")
    report = report_of(run)

    assert [h["id"] for h in report["held"]] == [DRAFT_HELD] and report["held"][0]["reason"] == PENDING, report
    assert store.path(DRAFT_HELD).read_bytes() == before[DRAFT_HELD]
    assert report["approved"] == [DRAFT], report


def test_missing_priority_line_is_inserted_not_fatal(tmp_path):
    # covers: ACD-300c-4
    # angle: failure
    """A record with no top-level priority line is approved with the line inserted (priority high), and the
    other records of the batch are still approved: one such record does not abort the run."""
    store = batch_store(tmp_path)
    strip_lines(store, RELEASED[0], "priority")

    run = run_ids(store, RELEASED, priority="high")

    report = report_of(run)
    assert sorted(report["approved"]) == RELEASED, report
    assert {store.read(rid)["priority"] for rid in RELEASED} == {"high"}
    assert [store.read(rid)["readiness"] for rid in RELEASED] == ["approved"] * 3


def test_ids_mode_refuses_glob_characters_and_a_filename_with_another_id(tmp_path):
    # covers: ACD-300c-4
    # angle: discrimination
    """`--ids 'ACD-9990a-*'` is refused (exit non-zero, nothing written); a file named ACD-9990a-9.yaml whose
    `id:` is another id is not taken for ACD-9990a-9 (not found, exit 1, nothing written)."""
    store = batch_store(tmp_path)
    before = store_bytes(store, BATCH)
    assert run_ids(store, ["ACD-9990a-*"], priority="high").exit_code != 0
    imposter = store.path("ACD-9990a-1").with_name("ACD-9990a-9.yaml")
    imposter.write_bytes(store.path("ACD-9990a-1").read_bytes())

    run = run_ids(store, ["ACD-9990a-9"], priority="high")

    assert run.exit_code == 1, (run.exit_code, run.stderr[-400:])
    assert store_bytes(store, BATCH) == before
    assert store.read("ACD-9990a-1")["readiness"] == "reviewed"


def test_priority_with_goal_mode_is_refused(tmp_path):
    # covers: ACD-300c-4
    # angle: discrimination
    """`--goal X --priority high` exits non-zero with a message naming --priority; it is not ignored."""
    store = batch_store(tmp_path)

    run = run_approve(store, "--goal", "ACD-9990a", "--priority", "high")

    assert run.exit_code != 0 and "--priority" in run.stderr, (run.exit_code, run.stderr[-400:])
