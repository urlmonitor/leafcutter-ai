"""
MODULE: unit_tests/ac_store/test_acd_2500b_3.py
COVERS: ACD-2500b-3
GOAL: Red-first spec for "requirements whose test design the planner wrote before this change keep it
    and stay buildable": on a FIXTURE store (never the 1,357 / 941 counts of the AC, which are a
    dated measurement), every legacy design is kept byte-for-byte, none is reclassified, reset or
    flagged "test design pending", the implementation-ready set is the one the pre-change rule gives,
    legacy designs are told apart by the missing authorship mark, and one record can be redesigned.
BUSINESS CONTEXT: ADR-071. Legacy = a non-empty test_spec WITHOUT the code-aware authorship mark;
    `_test_intent.is_legacy_design` (ticket 22, commit dcd3ad20c) is the one predicate and ticket 25
    consumes it. No migration writes anything. The change that ships beside this one (tickets 23 and 24)
    adds the approval hold, the "test design pending" gate reason and the `--json` approval report;
    legacy records must pass through all of them untouched.
ARCHITECTURE: The fixture store (built once per test by `_scenario`, real serializer) mixes four legacy
    records (one reviewed, one schema_version 2, one with no file targets: not ready before and not ready
    after, an explicit control), one code-aware record, and the new states: an intent record without a
    design at "reviewed" and one set to "approved" by hand. The "before" expectations are an
    INDEPENDENT statement of the pre-change rule (approved, has file targets, has a test contract), not a
    call of the code under test. What is red today: the legacy half alone already holds (ticket 22 is
    built), so each test also runs the legacy records through the NEW surface (the `--json` approval
    report, the gate hold on the intent record) and asserts the legacy records are untouched while the
    intent records are held: that half is red until tickets 23 and 24 ship.
    Note interpretation (conflict 13): the code-aware step is ACD-2500c-1, built later, so the
    single-record redesign uses a STUB writer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import (  # noqa: E402
    PENDING,
    REPO_ROOT,
    STEP,
    build,
    design_for,
    goal,
    json_of,
    legacy_leaf,
    read_bytes,
    reviewed_intent,
    run_approve,
    run_report,
    run_scan,
    valid_record,
)
from _rule_check_fixtures import run_cli_subprocess, write_snapshot  # noqa: E402

LEGACY = ("ZZL-1a-1", "ZZL-1a-2", "ZZL-1a-3", "ZZL-1a-4")
CODE_AWARE = "ZZL-1a-5"
INTENT_REVIEWED = "ZZL-1a-6"
INTENT_APPROVED = "ZZL-1a-7"
LEGACY_READY_BEFORE = {"ZZL-1a-1", "ZZL-1a-2"}  # approved, files declared, a test contract: the pre-change rule


def _scenario(tmp_path):
    """The fixture store: legacy x4, one code-aware, one reviewed intent, one hand-approved intent."""
    code_aware = valid_record(
        CODE_AWARE,
        readiness="approved",
        test_spec=design_for(["it is a valid requirement"]),
        test_design_authorship={"step": STEP, "date": "2026-10-14"},
        test_design_opened_files=["scripts/ac_store/_test_intent.py"],
    )
    records = [
        goal("ZZL-1", [LEGACY[2], INTENT_REVIEWED]),
        legacy_leaf(LEGACY[0]),
        legacy_leaf(LEGACY[1], schema_version=2),
        legacy_leaf(LEGACY[2], readiness="reviewed"),
        legacy_leaf(LEGACY[3], schema_version=2, drop=("declared_files",)),
        code_aware,
        reviewed_intent(INTENT_REVIEWED),
        reviewed_intent(INTENT_APPROVED, readiness="approved"),
    ]
    return build(tmp_path, records)


def _legacy_parts(store, record_id: str) -> dict:
    """The parsed record minus the two fields an approval legitimately changes."""
    data = store.read(record_id)
    return {k: v for k, v in data.items() if k not in ("readiness", "amended_by")}


def _real_legacy_records(limit: int = 3) -> list[Path]:
    """Up to `limit` real, approved, legacy-designed records of the shipped store, in sorted order."""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "ac_store"))
    from _test_intent import is_legacy_design  # noqa: PLC0415

    found: list[Path] = []
    for path in sorted((REPO_ROOT / "docs" / "acceptance-criteria").rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "\ntest_spec:" not in text or "readiness: approved" not in text or "test_design_authorship" in text:
            continue
        data = yaml.safe_load(text)
        if isinstance(data, dict) and is_legacy_design(data) and not data.get("test_intent"):
            found.append(path)
        if len(found) == limit:
            break
    return found


def test_legacy_design_unchanged_after_change(tmp_path):
    # covers: ACD-2500b-3
    # angle: real_artifact
    """Every legacy test_spec is byte-identical after the change's approval step has run over it.

    Fixture bytes: (1) up to three REAL legacy records copied verbatim from the shipped store (no
    hand-typed literal), approved one by one through the real approval CLI with `--json`; (2) the
    serializer-written fixture store, approved as a batch. Each approved legacy record is not held and
    its file is byte-identical; the one legacy record at "reviewed" changes ONLY readiness and
    amended_by (its test_spec byte-for-byte equal); the intent record in the same batch IS held
    (positive control that the new hold is live).
    """
    real = _real_legacy_records()
    assert real, "the shipped store must hold at least one approved legacy-designed record"
    real_store = build(tmp_path / "real", [])
    for path in real:
        real_store.folder.joinpath(path.name).write_bytes(path.read_bytes())
        before = path.read_bytes()
        report = json_of(run_approve(real_store, "--ac", path.stem, "--json"))
        assert report["held"] == [], (path.name, report)
        assert real_store.folder.joinpath(path.name).read_bytes() == before, f"{path.name} was rewritten"

    store = _scenario(tmp_path / "fixture")
    snapshot = {rid: read_bytes(store, rid) for rid in (*LEGACY, CODE_AWARE)}
    designs = {rid: store.read(rid)["test_spec"] for rid in LEGACY}
    reviewed_before = _legacy_parts(store, LEGACY[2])

    report = json_of(run_approve(store, "--goal", "ZZL-1", "--json"))

    assert [h["id"] for h in report["held"]] == [INTENT_REVIEWED], report
    for rid in (LEGACY[0], LEGACY[1], LEGACY[3], CODE_AWARE):
        assert read_bytes(store, rid) == snapshot[rid], f"{rid} (not in the promotion set) was rewritten"
    assert {rid: store.read(rid)["test_spec"] for rid in LEGACY} == designs
    assert _legacy_parts(store, LEGACY[2]) == reviewed_before


def test_legacy_not_reclassified_reset_or_flagged(tmp_path):
    # covers: ACD-2500b-3
    # angle: criterion
    """No legacy record gains test_intent, drops to "reviewed", or is flagged "test design pending".

    After the approval run: the three approved legacy records are still "approved", the reviewed one
    was promoted (it is the only readiness change among the legacy records), none carries test_intent or
    a hold_reason, none is in the held report, and the gate and approval predicates agree. Positive
    control in the same run: the intent record IS held "test design pending" and the code-aware record is
    untouched, so "not flagged" is not just "nothing flags anything".
    """
    from _impl_readiness_gate import implementation_readiness_reasons  # noqa: PLC0415
    from _test_intent import design_pending  # noqa: PLC0415

    store = _scenario(tmp_path)
    report = json_of(run_approve(store, "--goal", "ZZL-1", "--json"))

    held = {h["id"]: h["reason"] for h in report["held"]}
    assert held == {INTENT_REVIEWED: PENDING}, held
    for rid in LEGACY:
        record = store.read(rid)
        assert "test_intent" not in record and "hold_reason" not in record, rid
        assert record["readiness"] == "approved", rid
        assert design_pending(record) is False, rid
        assert PENDING not in implementation_readiness_reasons(record), rid
    assert store.read(INTENT_REVIEWED)["readiness"] == "reviewed"
    assert implementation_readiness_reasons(store.read(INTENT_APPROVED)) == [PENDING]


def test_legacy_ready_set_unchanged(tmp_path):
    # covers: ACD-2500b-3
    # angle: boundary
    """The implementation-ready set of the legacy records is the one the pre-change rule gives.

    Expected, stated independently of the code under test: a legacy record is ready iff it is approved,
    has file targets and has a test contract. Before the approval run: {1a-1, 1a-2}; after it the
    promoted reviewed record joins ({1a-1, 1a-2, 1a-3}); 1a-4 (no file targets) stays out in BOTH gate modes
    with exactly ["missing file targets"]. The code-aware record is ready; the hand-approved intent record
    is in neither mode (the new, always-held reason). Exact set equality, advisory and enforced.
    """
    store = _scenario(tmp_path)

    def ready_and_flagged(*flags):
        out = json.loads(run_scan(store, *flags).stdout or "{}")
        return (
            {item["ac_id"] for item in out["ready"]},
            {item["ac_id"]: item["reasons"] for item in out["not_implementation_ready"]},
        )

    ready, _ = ready_and_flagged()
    assert ready & set(LEGACY) == LEGACY_READY_BEFORE, ready
    json_of(run_approve(store, "--goal", "ZZL-1", "--json"))
    legacy_after = LEGACY_READY_BEFORE | {LEGACY[2]}

    for flags in ((), ("--enforce-impl-readiness",)):
        ready, flagged = ready_and_flagged(*flags)
        assert ready & set(LEGACY) == legacy_after, (flags, ready)
        assert CODE_AWARE in ready and INTENT_APPROVED not in ready, (flags, ready)
        assert flagged[LEGACY[3]] == ["missing file targets"] and flagged[INTENT_APPROVED] == [PENDING], flagged
        assert not (set(flagged) & legacy_after), flagged


def test_legacy_distinguished_by_missing_authorship_mark(tmp_path):
    # covers: ACD-2500b-3
    # angle: seam
    """The by-author report lists the legacy designs apart from the code-aware one, and the approval
    step (which consumes the same store) holds only the records without a design.

    Exact: legacy == the four legacy ids, by_step == {step: [code-aware id]}; records with no design
    (the two intent records) are in neither list. The approval report over the same store never names
    a legacy record, so "legacy" is a provenance label and not a hold.
    """
    store = _scenario(tmp_path)
    report = json_of(run_report(store))
    assert report["legacy"] == sorted(LEGACY), report
    assert report["by_step"] == {STEP: [CODE_AWARE]}, report
    assert not ({INTENT_REVIEWED, INTENT_APPROVED} & set(report["legacy"]))

    approval = json_of(run_approve(store, "--goal", "ZZL-1", "--json"))
    assert not ({h["id"] for h in approval["held"]} & set(LEGACY)), approval
    assert json_of(run_report(store))["legacy"] == sorted(LEGACY), "approval must not change provenance"


def _stub_redesign(store, record_id: str) -> None:
    """The stub for the code-aware step (ACD-2500c-1 is built later): one record, new design + mark."""
    record = store.read(record_id)
    record["test_spec"] = design_for(["it is a valid requirement"])
    record["test_design_authorship"] = {"step": STEP, "date": "2026-10-14"}
    record["test_design_opened_files"] = ["scripts/ac_store/_test_intent.py"]
    store.write(record)


def test_single_record_redesign_adds_mark(tmp_path):
    # covers: ACD-2500b-3
    # angle: seam
    """Sending ONE legacy record through the (stubbed) code-aware step yields the new design and the mark.

    The stub rewrites exactly one fixture record; the REAL rule check (`--stage test-design`, subprocess)
    raises no schema or intent-coverage blocker for it; `is_legacy_design` flips True -> False; the by-author report
    moves the record from "legacy" to the step; every other legacy record stays byte-identical; and the
    approval step over the store still holds only the intent record (the redesigned one is not held).
    """
    from _test_intent import is_legacy_design  # noqa: PLC0415

    store = _scenario(tmp_path)
    target = LEGACY[0]
    others = {rid: read_bytes(store, rid) for rid in LEGACY[1:]}
    assert is_legacy_design(store.read(target)) is True

    _stub_redesign(store, target)

    after = store.read(target)
    assert is_legacy_design(after) is False
    assert after["test_design_authorship"]["step"] == STEP and after["test_spec"][0]["proves_clause"]
    snapshot = write_snapshot(store)
    check = run_cli_subprocess(
        ["--for-ids", target, "--repo-root", str(store.repo_root), "--stage", "test-design",
         "--before-snapshot", str(snapshot)],
        cwd=store.repo_root,
    )
    # The fixture ids imply parents that do not exist (a back-link family concern, not this test's
    # subject), so the design is judged by the families that read a test design: schema and intent.
    judged = ("record schema", "test intent coverage")
    blockers = [f for f in check.report.get("findings", []) if f.get("record_id") == target
                and f.get("rule_family") in judged and f.get("disposition") in ("needs a decision", "failed")]
    assert blockers == [], blockers
    assert check.report["family_counts"]["record schema"]["evaluated"] >= 1, "the schema family must have looked"

    report = json_of(run_report(store))
    assert target not in report["legacy"] and report["by_step"][STEP] == sorted([target, CODE_AWARE])
    assert {rid: read_bytes(store, rid) for rid in LEGACY[1:]} == others
    approval = json_of(run_approve(store, "--goal", "ZZL-1", "--json"))
    assert [h["id"] for h in approval["held"]] == [INTENT_REVIEWED], approval


def test_acd_2500b_3_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500b-3
    # angle: reachability
    """The change's real entry points (subprocess) leave every legacy design untouched and consume the label.

    Entry points: `python scripts/ac_store/approve_acs.py --goal ZZL-1 --json` and
    `python scripts/ac_store/design_authors_report.py --json`. The behaviour occurred (the intent record is
    held "test design pending"; the reviewed legacy record is approved) and is consumed in control flow on
    disk: the legacy test_spec values are equal before and after, and a second approval run reports the
    same single hold and changes no byte.
    """
    store = _scenario(tmp_path)
    designs = {rid: store.read(rid)["test_spec"] for rid in LEGACY}

    first = json_of(run_approve(store, "--goal", "ZZL-1", "--json"))
    assert first["held"] == [{"id": INTENT_REVIEWED, "file": store.rel(INTENT_REVIEWED), "reason": PENDING}]
    assert LEGACY[2] in first["approved"] and store.read(LEGACY[2])["readiness"] == "approved"
    after_first = {p.name: p.read_bytes() for p in store.folder.glob("*.yaml")}

    second = json_of(run_approve(store, "--goal", "ZZL-1", "--json"))
    assert [h["id"] for h in second["held"]] == [INTENT_REVIEWED]
    assert {p.name: p.read_bytes() for p in store.folder.glob("*.yaml")} == after_first
    assert {rid: store.read(rid)["test_spec"] for rid in LEGACY} == designs
    assert json_of(run_report(store))["legacy"] == sorted(LEGACY)
