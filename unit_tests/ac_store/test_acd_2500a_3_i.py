"""
MODULE: test_acd_2500a_3_i
GOAL: Red-first specification of ACD-2500a-3-i: a Node workflow body
    (templates/workflows-js/*.js) assigned to python-coder passes the
    specialist-versus-surface family; a .sql file assigned to python-coder does not.
BUSINESS CONTEXT: The path-aware map (ACD-1700b-1) makes Node orchestration
    python-coder's craft while SQL belongs to sql-coder. The verdict must follow the
    map: editing the workflow-bodies entry flips W's verdict with no other edit.
ARCHITECTURE: Driven through the rule-check CLI (`main(argv)`; a real subprocess
    for the reachability test) over real yaml.safe_dump records in a tmp
    consumer-style repo. The map change is made on a TMP copy passed via
    `--surface-map`; the shipped config/surface_craft_map.yaml is never modified
    (asserted byte-for-byte).

INTERPRETATION: family name string "specialist versus surface" (architect note
    section 3 table), as in test_acd_2500a_3.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS,
    DISPOSITION_DECISION,
    REPO_ROOT,
    # The protected-fields family's 'not evaluated' entries (ACD-2500a-2-vi / -vii)
    # are not this file's subject; every other finding is kept.
    check_store_other_families as check_store,
    cli_argv,
    finding_text,
    findings_for,
    make_store,
    run_cli_subprocess_other_families as run_cli_subprocess,
    valid_record,
)

FAMILY_SURFACE = "specialist versus surface"
SHIPPED_MAP = REPO_ROOT / "config" / "surface_craft_map.yaml"

_W, _Y = "ACD-9983", "ACD-9984"
_WORKFLOW = "templates/workflows-js/plan-feature.js"
_SQL = "queries/report.sql"


def _records() -> list[dict]:
    """W (python-coder; a workflow body) and Y (python-coder; a .sql file)."""
    return [
        valid_record(
            _W, level="L0", assigned_agent="python-coder",
            declared_files=[{"path": _WORKFLOW, "state": "existing"}],
        ),
        valid_record(
            _Y, level="L0", assigned_agent="python-coder",
            declared_files=[{"path": _SQL, "state": "to_be_created"}],
        ),
    ]


def _store(tmp_path):
    store = make_store(tmp_path, _records())
    target = store.repo_root / _WORKFLOW
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// fixture\n", encoding="utf-8")
    return store


def _surface(report, record_id):
    return findings_for(report, record_id=record_id, rule_family=FAMILY_SURFACE)


def _workflow_entries_to(store, craft: str) -> Path:
    """A tmp copy of the shipped map whose workflow-body entries name `craft`."""
    data = yaml.safe_load(SHIPPED_MAP.read_text(encoding="utf-8"))
    changed = 0
    for entry in data["entries"]:
        if entry["glob"].startswith("templates/workflows-js/"):
            entry["craft"] = craft
            changed += 1
    assert changed >= 1, "the shipped map must carry a workflow-body entry"
    target = store.repo_root / "tmp_surface_craft_map.yaml"
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return target


def test_workflow_js_assigned_python_coder_passes(tmp_path):
    # covers: ACD-2500a-3-i
    # angle: criterion
    """W (python-coder, templates/workflows-js/plan-feature.js) produces no finding;
    Y in the same run does (control: the check is alive)."""
    store = _store(tmp_path)

    _, report = check_store(store)

    assert [f for f in report["findings"] if f["disposition"] in BLOCKERS and f["record_id"] == _Y]
    assert findings_for(report, record_id=_W) == [], findings_for(report, record_id=_W)


def test_sql_assigned_python_coder_flagged(tmp_path):
    # covers: ACD-2500a-3-i
    # angle: criterion
    """Y (python-coder, queries/report.sql) gets exactly one 'needs a decision'
    finding naming the path, the resolved specialist sql-coder and python-coder."""
    store = _store(tmp_path)

    exit_code, report = check_store(store)

    y_findings = _surface(report, _Y)
    assert len(y_findings) == 1, y_findings
    assert y_findings[0]["disposition"] == DISPOSITION_DECISION
    text = finding_text(y_findings[0])
    assert _SQL in text and "sql-coder" in text and "python-coder" in text
    assert "frontend-coder" not in text and "llm-expert" not in text
    assert _WORKFLOW not in text  # W's path never leaks into Y's finding
    assert report["verdict"] == "failed" and exit_code == 1


def test_map_entry_change_flips_workflow_verdict(tmp_path):
    # covers: ACD-2500a-3-i
    # angle: seam
    """Pointing the workflow-bodies entries at another specialist (llm-expert) in a
    TMP map copy changes W's verdict on the next run with no other edit: W goes from
    no finding to one finding naming llm-expert, its path and python-coder. The
    unchanged tmp copy is the control (W still passes)."""
    store = _store(tmp_path)
    shipped_before = SHIPPED_MAP.read_bytes()

    _, baseline = check_store(store)
    assert findings_for(baseline, record_id=_W) == []  # shipped map: W passes

    _, flipped = check_store(store, "--surface-map", str(_workflow_entries_to(store, "llm-expert")))

    w_findings = _surface(flipped, _W)
    assert len(w_findings) == 1, w_findings
    assert w_findings[0]["disposition"] == DISPOSITION_DECISION
    text = finding_text(w_findings[0])
    assert _WORKFLOW in text and "llm-expert" in text and "python-coder" in text
    assert SHIPPED_MAP.read_bytes() == shipped_before  # the shipped map is never edited

    _, restored = check_store(store, "--surface-map", str(_workflow_entries_to(store, "python-coder")))
    assert findings_for(restored, record_id=_W) == []  # and it flips back, again no other edit


def test_acd_2500a_3_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-3-i
    # angle: reachability
    """The real script in a subprocess: Y is flagged naming sql-coder, W is not, and
    exit code 1 is the failed verdict."""
    store = _store(tmp_path)

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 1, (run.stdout[:600], run.stderr[:600])
    assert run.report["verdict"] == "failed"
    y_findings = _surface(run.report, _Y)
    assert len(y_findings) == 1 and "sql-coder" in finding_text(y_findings[0])
    assert findings_for(run.report, record_id=_W) == []
