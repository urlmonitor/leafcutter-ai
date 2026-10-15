"""
MODULE: test_acd_2500a_3
GOAL: Red-first specification of ACD-2500a-3: the requirement rule check judges
    specialist-versus-surface compatibility from the ONE surface-to-specialist map
    (config/surface_craft_map.yaml), never from a second file-type table.
BUSINESS CONTEXT: A frontend file assigned to python-coder wastes a dispatch. The
    check names the one mismatched path, the specialist the map gives for it and the
    assigned agent; matched files stay unnamed; a record without declared files is
    listed "not evaluated: no declared files" and is never counted as passed.
ARCHITECTURE: Every test is driven through the rule-check CLI (`main(argv)` in
    process, or the real script in a subprocess for the reachability test) over real
    yaml.safe_dump records in a tmp consumer-style repo (_rule_check_fixtures.py).
    The map is overridden through `--surface-map` with a TMP copy edited by the test;
    the shipped config/surface_craft_map.yaml is never modified.

INTERPRETATIONS (architect note sections 3, D2, D9): the family name string is
    "specialist versus surface" (the table's family name); `family_counts[family]`
    holds `evaluated` (records the family judged) and `not_evaluated` (records
    listed "not evaluated"); `not evaluated` entries live inside `findings` and
    never fail the verdict; one finding per mismatched path; an unmapped path is
    `not evaluated: unresolved surface`; an unreadable map is verdict failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS,
    DISPOSITION_DECISION,
    DISPOSITION_NOT_EVALUATED,
    REPO_ROOT,
    check_store,
    cli_argv,
    finding_text,
    findings_for,
    make_store,
    run_cli_subprocess,
    valid_record,
)

FAMILY_SURFACE = "specialist versus surface"
SHIPPED_MAP = REPO_ROOT / "config" / "surface_craft_map.yaml"

_P, _Q, _S = "ACD-9980", "ACD-9981", "ACD-9982"
_MISMATCH = "web/app/page.tsx"
_NO_FILES = "not evaluated: no declared files"


def _touch(store, *paths: str) -> None:
    """Create the 'existing' declared files in the tmp repo (no existence noise)."""
    for rel in paths:
        target = store.repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# fixture\n", encoding="utf-8")


def _entry(path: str, state: str) -> dict:
    return {"path": path, "state": state}


def _records() -> list[dict]:
    """P (python-coder; scripts/x.py + web/app/page.tsx), Q (llm-expert; one
    agent template), S (python-coder; no declared files)."""
    return [
        valid_record(
            _P, level="L0", assigned_agent="python-coder",
            declared_files=[_entry("scripts/x.py", "existing"), _entry(_MISMATCH, "to_be_created")],
        ),
        valid_record(
            _Q, level="L0", assigned_agent="llm-expert",
            declared_files=[_entry("templates/agents/foo.md", "existing")],
        ),
        valid_record(_S, level="L0", assigned_agent="python-coder", drop=("declared_files",)),
    ]


def _store(tmp_path, records=None):
    store = make_store(tmp_path, _records() if records is None else records)
    _touch(store, "scripts/x.py", "templates/agents/foo.md")
    return store


def _surface(report, record_id=None):
    return findings_for(report, record_id=record_id, rule_family=FAMILY_SURFACE)


def _blocking(findings):
    return [f for f in findings if f["disposition"] in BLOCKERS]


def _tmp_map(store, mutate=None, entries=None) -> Path:
    """A tmp copy of the shipped map (optionally edited), outside the record folder."""
    data = yaml.safe_load(SHIPPED_MAP.read_text(encoding="utf-8"))
    if entries is not None:
        data["entries"] = entries
    if mutate is not None:
        mutate(data["entries"])
    target = store.repo_root / "tmp_surface_craft_map.yaml"
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return target


def test_mismatched_file_named_with_resolved_specialist_and_agent(tmp_path):
    # covers: ACD-2500a-3
    # angle: criterion
    """P gets exactly one 'needs a decision' finding naming web/app/page.tsx, the
    specialist the map gives for it (frontend-coder) and python-coder."""
    store = _store(tmp_path)

    exit_code, report = check_store(store)

    p_findings = _surface(report, _P)
    assert len(p_findings) == 1, p_findings
    finding = p_findings[0]
    assert finding["disposition"] == DISPOSITION_DECISION
    assert finding["file"] == store.rel(_P)
    text = finding_text(finding)
    assert _MISMATCH in text
    assert "frontend-coder" in text  # the map's specialist for *.tsx
    assert "python-coder" in text  # the assigned agent
    assert "sql-coder" not in text and "llm-expert" not in text  # not another craft
    assert report["verdict"] == "failed" and exit_code == 1


def test_matched_file_not_named_in_finding(tmp_path):
    # covers: ACD-2500a-3
    # angle: criterion
    """scripts/x.py (map: python-coder, matches the assignment) is not named in P's
    finding; the finding for the mismatched file does exist (control)."""
    store = _store(tmp_path)

    _, report = check_store(store)

    p_findings = _surface(report, _P)
    assert [f for f in p_findings if _MISMATCH in finding_text(f)], p_findings  # control
    for finding in p_findings:
        assert "scripts/x.py" not in finding_text(finding), finding


def test_llm_expert_template_only_no_finding(tmp_path):
    # covers: ACD-2500a-3
    # angle: criterion
    """Q (llm-expert, templates/agents/foo.md only) produces no finding at all, while
    P in the same run produces one (so 'no finding' is not a dead check)."""
    store = _store(tmp_path)

    _, report = check_store(store)

    assert len(_blocking(_surface(report, _P))) == 1  # control row
    assert findings_for(report, record_id=_Q) == [], findings_for(report, record_id=_Q)


def test_no_declared_files_listed_not_evaluated(tmp_path):
    # covers: ACD-2500a-3
    # angle: boundary
    """S (no declared files) is listed 'not evaluated: no declared files' for the
    family, never counted as passed (family_counts), and never fails a verdict: a
    folder holding only S passes with 0 evaluated and 1 not evaluated."""
    store = _store(tmp_path)

    _, report = check_store(store)

    s_findings = _surface(report, _S)
    assert len(s_findings) == 1, s_findings
    assert s_findings[0]["disposition"] == DISPOSITION_NOT_EVALUATED
    assert _NO_FILES in finding_text(s_findings[0])
    counts = report["family_counts"][FAMILY_SURFACE]
    assert counts == {"evaluated": 2, "not_evaluated": 1}, counts  # P and Q judged; S not

    only_s = make_store(tmp_path / "only_s", [_records()[2]])
    exit_code, only_report = check_store(only_s)
    assert only_report["family_counts"][FAMILY_SURFACE] == {"evaluated": 0, "not_evaluated": 1}
    assert _blocking(only_report["findings"]) == []
    assert only_report["verdict"] == "passed" and exit_code == 0


def test_verdict_source_is_surface_craft_map(tmp_path):
    # covers: ACD-2500a-3
    # angle: seam
    """The verdicts come from the map: a TMP copy whose *.tsx entry names sql-coder
    changes P's finding to name sql-coder; a tiny map that only knows *.py makes
    scripts/x.py the mismatch (a built-in file-type table would ignore both edits)."""
    store = _store(tmp_path)
    shipped_before = SHIPPED_MAP.read_bytes()

    def tsx_to_sql(entries):
        for entry in entries:
            if entry["glob"] == "**/*.tsx":
                entry["craft"] = "sql-coder"

    changed = _tmp_map(store, mutate=tsx_to_sql)
    _, report = check_store(store, "--surface-map", str(changed))
    p_findings = _blocking(_surface(report, _P))
    assert len(p_findings) == 1, p_findings
    text = finding_text(p_findings[0])
    assert _MISMATCH in text and "sql-coder" in text and "frontend-coder" not in text

    only_py = _tmp_map(store, entries=[{"glob": "**/*.py", "craft": "sql-coder"}])
    _, py_report = check_store(store, "--surface-map", str(only_py))
    py_findings = _blocking(_surface(py_report, _P))
    assert len(py_findings) == 1, py_findings
    py_text = finding_text(py_findings[0])
    assert "scripts/x.py" in py_text and "sql-coder" in py_text and _MISMATCH not in py_text
    assert SHIPPED_MAP.read_bytes() == shipped_before  # the shipped map is never edited


def test_unresolved_surface_not_evaluated_never_mismatch(tmp_path):
    # covers: ACD-2500a-3
    # angle: boundary
    """A declared path the map has no entry for is 'not evaluated: unresolved
    surface' -- never a mismatch and never a pass (counted as not evaluated)."""
    record = valid_record(
        _P, level="L0", assigned_agent="python-coder",
        declared_files=[_entry("docs/notes.md", "to_be_created")],
    )
    store = make_store(tmp_path, [record])

    exit_code, report = check_store(store)

    findings = _surface(report, _P)
    assert len(findings) == 1, findings
    assert findings[0]["disposition"] == DISPOSITION_NOT_EVALUATED
    assert "not evaluated: unresolved surface" in finding_text(findings[0])
    assert "docs/notes.md" in finding_text(findings[0])
    assert report["family_counts"][FAMILY_SURFACE]["not_evaluated"] == 1
    assert report["verdict"] == "passed" and exit_code == 0


def test_one_finding_per_mismatched_path(tmp_path):
    # covers: ACD-2500a-3
    # angle: boundary
    """Two mismatched paths give two findings, each naming only its own path
    (one finding per path, architect note D9)."""
    record = valid_record(
        _P, level="L0", assigned_agent="python-coder",
        declared_files=[_entry("web/app/page.tsx", "to_be_created"), _entry("queries/r.sql", "to_be_created")],
    )
    store = make_store(tmp_path, [record])

    _, report = check_store(store)

    findings = _blocking(_surface(report, _P))
    assert len(findings) == 2, findings
    by_path = {
        ("web/app/page.tsx" if "web/app/page.tsx" in finding_text(f) else "queries/r.sql"): f
        for f in findings
    }
    assert set(by_path) == {"web/app/page.tsx", "queries/r.sql"}
    assert "queries/r.sql" not in finding_text(by_path["web/app/page.tsx"])
    assert "web/app/page.tsx" not in finding_text(by_path["queries/r.sql"])
    assert "frontend-coder" in finding_text(by_path["web/app/page.tsx"])
    assert "sql-coder" in finding_text(by_path["queries/r.sql"])


def test_unreadable_surface_map_fails_verdict(tmp_path):
    # covers: ACD-2500a-3
    # angle: failure
    """A map that cannot be read is verdict failed with a 'failed' finding -- never
    a silent pass (the check fails closed on its rule sources)."""
    store = _store(tmp_path)

    exit_code, report = check_store(store, "--surface-map", str(store.repo_root / "no_such_map.yaml"))

    assert report["verdict"] == "failed" and exit_code == 1
    assert [f for f in report["findings"] if f["disposition"] == "failed"], report["findings"]


def test_acd_2500a_3_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-3
    # angle: reachability
    """The real script (python scripts/ac_store/requirement_rule_check.py) in a
    subprocess reports P's mismatch, lists S as not evaluated, and its exit code (1)
    is consumed as the failed verdict."""
    store = _store(tmp_path)

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 1, (run.stdout[:600], run.stderr[:600])
    assert run.report["verdict"] == "failed"
    p_findings = _blocking(_surface(run.report, _P))
    assert len(p_findings) == 1 and _MISMATCH in finding_text(p_findings[0])
    assert _NO_FILES in finding_text(_surface(run.report, _S)[0])
