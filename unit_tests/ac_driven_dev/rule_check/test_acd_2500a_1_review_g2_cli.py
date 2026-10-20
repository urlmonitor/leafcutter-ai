"""
MODULE: test_acd_2500a_1_review_g2_cli
GOAL: Red-first specification of the G2 review findings (H-1, H-2, L-2, L-3) against the
    requirement rule check CLI (scripts/ac_store/requirement_rule_check.py): the
    `--changed-since REV` mode, the `records_to_commit` report key, `--for-ids` strictness,
    unmapped documentation triggers, and CRLF-safe repairs.
BUSINESS CONTEXT: The check used to trust the author agent's `acs_written` list. It must find
    the stage's records itself (modified/added/untracked files against a git rev) and report
    every record file the run left changed -- repaired parents included -- so the stage
    commit cannot leave a repaired parent behind (H-1), and a typo'd or cross-folder id list
    cannot read as all clear (H-2).
ARCHITECTURE: Real `git init` repos under tmp_path (never mocked git); records come from the
    shared serializer-backed fixtures (unit_tests/ac_store/_rule_check_fixtures.py). The
    H-1 reachability test runs the script as a real subprocess. Sub-package placement mirrors
    test_acd_2500a_1.py (unit_tests/ac_store is over the folder-density cap); repo root is
    `Path(__file__).resolve().parents[3]`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "unit_tests" / "ac_store"))

from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS,
    DISPOSITION_FAILED,
    DISPOSITION_FIXED,
    DISPOSITION_NOT_EVALUATED,
    FAMILY_DOC_TRIGGERS,
    changed_since_argv,
    check_store,
    commit_all,
    finding_text,
    findings_for,
    hierarchy,
    init_git_repo,
    make_store,
    roots,
    run_cli,
    run_cli_subprocess,
    valid_record,
)


def _ids_argv(store, ids: list[str], snapshot_ids: list[str]) -> list[str]:
    """`--for-ids` argv with a before-snapshot that knows every id (draft readiness)."""
    snapshot = store.repo_root / "_ids_snapshot.json"
    snapshot.write_text(json.dumps({i: "draft" for i in snapshot_ids}), encoding="utf-8")
    return [
        "--for-ids", ",".join(ids), "--repo-root", str(store.repo_root),
        "--stage", "ba", "--before-snapshot", str(snapshot),
    ]


# ---------------------------------------------------------------------------
# H-2: --for-ids must not ignore ids it cannot honour
# ---------------------------------------------------------------------------
def test_h2_for_ids_with_one_missing_id_is_failed_and_names_it(tmp_path):
    # covers: ACD-2500a-1
    # angle: failure
    """One real id plus one id absent from the store: verdict failed, and a `failed`
    finding names the missing id (today the missing id is silently dropped and the run
    passes on the remaining records)."""
    store = make_store(tmp_path, hierarchy("ACD-9990", 2))
    ids = ["ACD-9990a-1", "ACD-9990a-9"]

    exit_code, report = run_cli(
        _ids_argv(store, ids, ["ACD-9990", "ACD-9990a", "ACD-9990a-1", "ACD-9990a-2"]),
        cwd=store.repo_root,
    )

    assert report["verdict"] == "failed", report
    assert exit_code == 1
    named = [
        f for f in report["findings"]
        if f["disposition"] == DISPOSITION_FAILED and "ACD-9990a-9" in finding_text(f)
    ]
    assert len(named) >= 1, f"no failed finding names the missing id: {report['findings']}"


def test_h2_for_ids_spanning_two_component_folders_is_failed(tmp_path):
    # covers: ACD-2500a-1
    # angle: failure
    """Ids that live in two component folders cannot all be checked in one folder: the run
    is failed with a finding naming the ids outside the checked folder (today the second
    folder's record is silently left unchecked)."""
    store = make_store(tmp_path, hierarchy("ACD-9990", 1))
    other = make_store(
        tmp_path, [valid_record("INF-9990", level="L0")], component_dir="infra", feature="other"
    )
    assert other.folder != store.folder
    ids = ["ACD-9990a-1", "INF-9990"]

    exit_code, report = run_cli(
        _ids_argv(store, ids, ["ACD-9990", "ACD-9990a", "ACD-9990a-1", "INF-9990"]),
        cwd=store.repo_root,
    )

    assert report["verdict"] == "failed", report
    assert exit_code == 1
    named = [
        f for f in report["findings"]
        if f["disposition"] == DISPOSITION_FAILED and "INF-9990" in finding_text(f)
    ]
    assert len(named) >= 1, f"no failed finding names the out-of-folder id: {report['findings']}"


# ---------------------------------------------------------------------------
# --changed-since: the check finds the stage's records itself
# ---------------------------------------------------------------------------
def _committed_roots_repo(tmp_path):
    """A real git repo whose HEAD holds 4 root records; ACD-993 is committed INVALID
    (no `criteria`) so a run that wrongly looks at unchanged records goes red."""
    records = roots(4)
    records[3] = valid_record("ACD-993", level="L0", drop=("criteria",))
    store = make_store(tmp_path, records)
    init_git_repo(tmp_path)
    commit_all(tmp_path, "baseline store")
    return store


def test_changed_since_checks_exactly_the_modified_and_added_records(tmp_path):
    # covers: ACD-2500a-1
    # angle: criterion
    """Commit a store, modify one record and add one: the run checks exactly those two
    (records_checked == 2) and reports nothing about the unchanged committed records,
    including the invalid ACD-993."""
    store = _committed_roots_repo(tmp_path)
    modified = store.read("ACD-990")
    modified["title"] = "Fixture requirement ACD-990 (reworded)"
    store.write(modified)
    store.write(valid_record("ACD-994", level="L0"))

    exit_code, report = run_cli(changed_since_argv(store), cwd=store.repo_root)

    assert report["records_checked"] == 2, report
    assert report["verdict"] == "passed", report["findings"]
    assert exit_code == 0
    assert not findings_for(report, "ACD-993"), "an unchanged committed record was checked"
    assert not findings_for(report, "ACD-991") and not findings_for(report, "ACD-992")


def test_changed_since_with_nothing_changed_is_failed_with_zero_records(tmp_path):
    # covers: ACD-2500a-1
    # covers: ACD-2500a-1-i
    # angle: boundary
    """No record differs from the rev: verdict failed, records_checked 0, and a finding says
    no records changed since the given rev (the zero-record rule, never an all-clear)."""
    store = _committed_roots_repo(tmp_path)

    exit_code, report = run_cli(changed_since_argv(store, "HEAD"), cwd=store.repo_root)

    assert report["verdict"] == "failed", report
    assert report["records_checked"] == 0
    assert exit_code == 1
    messages = [f["message"].lower() for f in report["findings"] if f["disposition"] in BLOCKERS]
    assert any("no" in m and "changed since" in m and "head" in m for m in messages), messages


# ---------------------------------------------------------------------------
# H-1: records_to_commit includes repaired parents, also on the resume run
# ---------------------------------------------------------------------------
def _child_added_without_backlink(tmp_path):
    """HEAD holds L0 + L1 (covering a-1) + a-1; the worktree adds a-2, which the parent
    (committed, unchanged) does not yet list in covered_by."""
    store = make_store(tmp_path, hierarchy("ACD-9990", 1))
    init_git_repo(tmp_path)
    commit_all(tmp_path, "baseline store")
    child = hierarchy("ACD-9990", 2)[3]
    assert child["id"] == "ACD-9990a-2"
    store.write(child)
    return store


def test_h1_records_to_commit_contains_the_repaired_parent_and_survives_resume(tmp_path):
    # covers: ACD-2500a-1
    # angle: reachability
    """Real git + real subprocess: the added child's parent lacks the back-link. After a
    `--changed-since HEAD` run records_to_commit holds BOTH the child and the repaired
    parent. A second identical run (the resume run) reports no `fixed` finding -- the
    repair already happened -- yet records_to_commit STILL holds the parent: it is
    derived from git state, not from this run's own fixes."""
    store = _child_added_without_backlink(tmp_path)
    child_path, parent_path = store.rel("ACD-9990a-2"), store.rel("ACD-9990a")
    argv = changed_since_argv(store)

    first = run_cli_subprocess(argv, cwd=store.repo_root)

    assert first.report["verdict"] == "passed", (first.report, first.stderr)
    assert "ACD-9990a-2" in store.read("ACD-9990a")["covered_by"], "the parent was not repaired"
    assert first.report["records_to_commit"] == sorted([child_path, parent_path]), first.report

    second = run_cli_subprocess(argv, cwd=store.repo_root)

    assert second.report["verdict"] == "passed", (second.report, second.stderr)
    assert [f for f in second.report["findings"] if f["disposition"] == DISPOSITION_FIXED] == []
    assert parent_path in second.report["records_to_commit"], second.report
    assert child_path in second.report["records_to_commit"], second.report


# ---------------------------------------------------------------------------
# L-2: an unmapped documentation trigger is never silent
# ---------------------------------------------------------------------------
def test_l2_unmapped_documentation_trigger_is_reported_not_silent(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: failure
    """A documentation trigger with no specialist mapping (injected through a tmp copy of
    the schema whose enum allows it) yields a `failed` or `not evaluated` finding from the
    documentation-trigger family for that L1 -- today `TRIGGER_SPECIALISTS.get` returns
    None and the trigger is skipped without a word."""
    store = make_store(
        tmp_path, hierarchy("ACD-9990", 2, l1={"documentation_triggers": ["runbook"]})
    )
    schema = json.loads(store.schema.read_text(encoding="utf-8"))
    enum = schema["properties"]["documentation_triggers"]["oneOf"][0]["items"]["enum"]
    enum.append("runbook")
    store.schema.write_text(json.dumps(schema), encoding="utf-8")

    _, report = check_store(store, "--schema", str(store.schema))

    hits = [
        f for f in findings_for(report, "ACD-9990a", FAMILY_DOC_TRIGGERS)
        if f["disposition"] in (DISPOSITION_FAILED, DISPOSITION_NOT_EVALUATED)
    ]
    assert len(hits) >= 1, f"unmapped trigger produced no finding: {report['findings']}"
    assert any("runbook" in finding_text(f) for f in hits), hits


# ---------------------------------------------------------------------------
# L-3: a repair must preserve CRLF byte-for-byte
# ---------------------------------------------------------------------------
def _crlf_parent_bytes(parent: dict, *, last_key: str) -> bytes:
    """Serialize `parent` with the real serializer, `last_key` moved to the end, converted
    to CRLF with NO trailing newline."""
    ordered = {k: v for k, v in parent.items() if k != last_key}
    ordered[last_key] = parent[last_key]
    text = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True)
    return text.rstrip("\n").replace("\n", "\r\n").encode("utf-8")


@pytest.mark.parametrize("covered_by", [[], ["ACD-9990a-1"]], ids=["flow-empty", "block-one"])
def test_l3_repair_on_crlf_parent_without_trailing_newline_keeps_line_endings(tmp_path, covered_by):
    # covers: ACD-2500a-2-i
    # angle: real_artifact
    """The parent is a CRLF file whose last line is `covered_by` and has no trailing
    newline. After the back-link repair the raw bytes hold no lone CR and no LF-only line."""
    records = hierarchy("ACD-9990", 2)
    parent = next(r for r in records if r["id"] == "ACD-9990a")
    parent["covered_by"] = list(covered_by)
    store = make_store(tmp_path, records)
    store.path("ACD-9990a").write_bytes(_crlf_parent_bytes(parent, last_key="covered_by"))

    check_store(store)

    raw = store.path("ACD-9990a").read_bytes()
    assert set(store.read("ACD-9990a")["covered_by"]) >= {"ACD-9990a-1", "ACD-9990a-2"}, (
        "the back-link repair did not happen, so the byte check below would be vacuous"
    )
    assert raw.count(b"\n") >= 10
    stripped = raw.replace(b"\r\n", b"")
    assert stripped.count(b"\r") == 0, f"lone CR byte(s) in the repaired file: {raw[-80:]!r}"
    assert stripped.count(b"\n") == 0, f"LF-only line ending(s) in the repaired file: {raw[-80:]!r}"
