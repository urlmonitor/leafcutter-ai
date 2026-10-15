"""
MODULE: test_acd_2500a_1_ii
GOAL: Red-first specification of ACD-2500a-1-ii: an unreadable record or a rule
    family that errors is a failure, never a skipped pass
    (scripts/ac_store/requirement_rule_check.py).
BUSINESS CONTEXT: Fail-closed on every inconclusive path. One bad record or one
    exploding rule must not stop the other records and families from being checked,
    and must not let the run pass.
ARCHITECTURE: Records are real yaml.safe_dump output; the single malformed file is
    the deliberate exception (`unreadable_record_text()`, syntax error at line 7).
    The family-exception test injects a fault family through the entry module's
    `FAMILIES` registry (architect note, section 1: "FAMILIES ordered registry";
    a family exposes NAME and evaluate_record(ctx, record)) and still runs the
    check through `main(argv)`.
INTERPRETATION: `FAMILIES` is read as a sequence of module-like objects exposing
    `NAME` and `evaluate_record`; the fault family is placed FIRST so the real
    families that follow it must still run for the same record.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    SCRIPTS_DIR,
    check_store,
    cli_argv,
    findings_for,
    make_store,
    roots,
    run_cli_subprocess,
    unreadable_record_text,
)

_BAD_ID = "ACD-992"


def _three_record_store(tmp_path, *, second: dict | None = None):
    """Two readable roots (ACD-990, ACD-991) plus ACD-992 with a YAML syntax error at line 7."""
    readable = roots(2)
    if second:
        readable[1].update(second)
    store = make_store(tmp_path, readable)
    store.write_text(f"{_BAD_ID}.yaml", unreadable_record_text(_BAD_ID))
    return store


def test_yaml_error_record_finding_names_file_and_line(tmp_path):
    # covers: ACD-2500a-1-ii
    # angle: failure
    """A record with a YAML syntax error at line 7 yields a 'failed' finding naming the
    file, saying it could not be read and giving line 7; verdict failed; 3 files counted."""
    store = _three_record_store(tmp_path)

    exit_code, report = check_store(store)

    assert report["verdict"] == "failed"
    assert exit_code == 1
    assert report["records_checked"] == 3
    assert len(report["findings"]) == 1, report["findings"]
    finding = report["findings"][0]
    assert finding["file"] == store.rel(_BAD_ID)
    assert finding["record_id"] is None
    assert finding["disposition"] == "failed"
    assert finding["rule_family"] == "record readable"
    assert "could not be read" in finding["message"]
    assert finding["line"] == 7


def test_other_records_still_checked_when_one_unreadable(tmp_path):
    # covers: ACD-2500a-1-ii
    """The 2 readable records are still checked in the same run: a violation in one of
    them is reported next to the unreadable-file finding; the clean one has none."""
    store = _three_record_store(tmp_path, second={"components": []})

    _, report = check_store(store)

    clean_id, violating_id = "ACD-990", "ACD-991"
    assert report["records_checked"] == 3
    assert len(findings_for(report, record_id=violating_id)) == 1, report["findings"]
    assert findings_for(report, record_id=clean_id) == []
    unreadable = [f for f in report["findings"] if f["record_id"] is None]
    assert len(unreadable) == 1 and unreadable[0]["file"] == store.rel(_BAD_ID)
    assert len(report["findings"]) == 2
    assert report["verdict"] == "failed"


def test_rule_family_exception_is_failure_not_skip(tmp_path, monkeypatch):
    # covers: ACD-2500a-1-ii
    # angle: failure
    """A rule family that raises on a readable record yields a failed finding for that
    record and family and verdict failed; the other records are still handed to the
    family, and the real families after it still report on the same record."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import requirement_rule_check as entry  # entry module: its main() is what runs

    seen: list[str] = []
    explode_on = "ACD-991"

    def evaluate_record(_ctx, record):
        seen.append(record["id"])
        if record["id"] == explode_on:
            raise RuntimeError("boom from the fault family")  # noqa: TRY003
        return []

    fault = SimpleNamespace(NAME="fault-injection fixture family", evaluate_record=evaluate_record)
    monkeypatch.setattr(entry, "FAMILIES", [fault, *entry.FAMILIES])

    store = make_store(tmp_path, roots(3))
    store.write({**store.read(explode_on), "components": []})  # a real violation, same record

    exit_code, report = check_store(store)

    assert report["verdict"] == "failed"
    assert exit_code == 1
    assert {"ACD-990", "ACD-991", "ACD-992"} <= set(seen), seen
    failures = findings_for(report, record_id=explode_on, rule_family=fault.NAME)
    assert len(failures) == 1, report["findings"]
    assert failures[0]["disposition"] == "failed"
    assert failures[0]["file"] == store.rel(explode_on)
    assert "boom from the fault family" in failures[0]["message"]
    assert len(findings_for(report, record_id=explode_on)) == 2, report["findings"]
    assert findings_for(report, record_id="ACD-990") == []
    assert findings_for(report, record_id="ACD-992") == []


def test_acd_2500a_1_ii_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-1-ii
    # angle: reachability
    """Real CLI subprocess: a folder with an unreadable record exits 1 and the stdout
    report carries the line-7 finding the workflow reads."""
    store = _three_record_store(tmp_path)

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 1, run.stderr
    assert run.report["verdict"] == "failed"
    assert run.report["records_checked"] == 3
    assert [f["line"] for f in run.report["findings"]] == [7]
