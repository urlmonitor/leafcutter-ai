"""
MODULE: test_acd_2500a_3_ii
GOAL: Red-first specification of ACD-2500a-3-ii: a documentation link whose
    relationship is 'modifies' naming a file missing from the record's declared
    list is a 'needs a decision' finding, and the record is never rewritten.
BUSINESS CONTEXT: The declared list is the only answer to "which files does the work
    change" (ACD-1600c-4); a 'modifies' link outside it is either a stale link or a
    missing declaration and only the author can say which. The check surfaces the
    disagreement and never lets either side win silently.
ARCHITECTURE: Driven through the rule-check CLI (`main(argv)`; a real subprocess
    for the reachability test) over real yaml.safe_dump records in a tmp
    consumer-style repo. The seam test substitutes the answer of
    declared_files.get_declared_files in process and then runs `main(argv)`.

INTERPRETATIONS (architect note section 3, D2): family name string
    "declared files versus modifies links"; `family_counts[family]` carries
    `evaluated` / `not_evaluated`; a record without declared files is a `not
    evaluated` entry inside `findings` that never fails the verdict. Path
    normalisation (ACD-1600c-4-iii) is not exercised here: only exact repo-root
    relative POSIX paths are used.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS,
    DISPOSITION_DECISION,
    DISPOSITION_NOT_EVALUATED,
    REPO_ROOT,
    SCRIPTS_DIR,
    check_store,
    cli_argv,
    finding_text,
    findings_for,
    make_store,
    run_cli_subprocess,
    snapshot_tree,
    valid_record,
)

FAMILY_MODIFIES = "declared files versus modifies links"

_P, _S, _T = "ACD-9985", "ACD-9986", "ACD-9987"
_NO_FILES = "not evaluated: no declared files"


def _link(path: str, relationship: str) -> dict:
    return {"path": path, "relationship": relationship, "status": "exists"}


def _p_record(**overrides) -> dict:
    """P: declares scripts/x.py (existing) then unit_tests/ac_store/test_x.py (to be
    created); links: x.py modifies, y.py modifies, ac-schema.md describes."""
    fields = {
        "level": "L0",
        "declared_files": [
            {"path": "scripts/x.py", "state": "existing"},
            {"path": "unit_tests/ac_store/test_x.py", "state": "to_be_created"},
        ],
        "doc_links": [
            _link("scripts/x.py", "modifies"),
            _link("scripts/y.py", "modifies"),
            _link("docs/reference/ac-schema.md", "describes"),
        ],
    }
    fields.update(overrides)
    return valid_record(_P, **fields)


def _s_record() -> dict:
    """S: no declared files; links scripts/build.py as modified."""
    return valid_record(_S, level="L0", drop=("declared_files",), doc_links=[_link("scripts/build.py", "modifies")])


def _store(tmp_path, records):
    store = make_store(tmp_path, records)
    target = store.repo_root / "scripts" / "x.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# fixture\n", encoding="utf-8")
    return store


def _family(report, record_id=None):
    return findings_for(report, record_id=record_id, rule_family=FAMILY_MODIFIES)


def _blocking(findings):
    return [f for f in findings if f["disposition"] in BLOCKERS]


def test_modifies_link_outside_declared_list_one_needs_decision_finding(tmp_path):
    # covers: ACD-2500a-3-ii
    # angle: criterion
    """P gets exactly one finding of this family, disposition 'needs a decision',
    naming P and scripts/y.py and saying a documentation link says the work modifies
    a file P's declared list does not contain."""
    store = _store(tmp_path, [_p_record(), _s_record()])

    exit_code, report = check_store(store)

    p_findings = _family(report, _P)
    assert len(p_findings) == 1, p_findings
    finding = p_findings[0]
    assert finding["disposition"] == DISPOSITION_DECISION
    assert finding["file"] == store.rel(_P)
    assert finding["record_id"] == _P
    assert _P in finding["message"] and "scripts/y.py" in finding["message"]
    assert "scripts/y.py" in finding_text(finding)  # detail carries the path
    lowered = finding["message"].lower()
    assert "documentation link" in lowered and "modif" in lowered and "declared" in lowered
    assert report["verdict"] == "failed" and exit_code == 1


def test_declared_modifies_link_and_describes_link_not_named(tmp_path):
    # covers: ACD-2500a-3-ii
    # angle: boundary
    """scripts/x.py (declared AND linked as modified) and docs/reference/ac-schema.md
    (linked as describing) are named in no finding of this family. Boundary: a
    record T whose undeclared paths are linked only as 'related' or as a plain
    string link (no relationship) gets no finding either -- only the exact
    relationship 'modifies' counts."""
    t_record = valid_record(
        _T, level="L0",
        declared_files=[{"path": "scripts/ac_store/_fixture_t.py", "state": "to_be_created"}],
        doc_links=[_link("scripts/z.py", "related"), "scripts/w.py", _link("scripts/v.py", "modifies-nothing")],
    )
    store = _store(tmp_path, [_p_record(), t_record])

    _, report = check_store(store)

    p_findings = _family(report, _P)
    assert len(_blocking(p_findings)) == 1  # control: the y.py finding exists
    for finding in _family(report):
        text = finding_text(finding)
        assert "scripts/x.py" not in text, finding
        assert "docs/reference/ac-schema.md" not in text, finding
    assert _blocking(_family(report, _T)) == [], _family(report, _T)


def test_declared_list_and_links_unchanged_after_run(tmp_path):
    # covers: ACD-2500a-3-ii
    # angle: criterion
    """After the run P's record file is byte-identical (the whole folder is): the
    declared list is still scripts/x.py then unit_tests/ac_store/test_x.py in that
    order, scripts/y.py is not added and no link is removed."""
    store = _store(tmp_path, [_p_record(), _s_record()])
    before = snapshot_tree(store.folder)

    _, report = check_store(store)

    assert len(_blocking(_family(report, _P))) == 1  # the check did run its rule
    assert snapshot_tree(store.folder) == before
    record = store.read(_P)
    assert [entry["path"] for entry in record["declared_files"]] == [
        "scripts/x.py", "unit_tests/ac_store/test_x.py",
    ]
    assert [link["path"] for link in record["doc_links"]] == [
        "scripts/x.py", "scripts/y.py", "docs/reference/ac-schema.md",
    ]
    assert not [f for f in report["findings"] if f["disposition"] == "fixed"]


def test_no_declared_files_record_not_evaluated_for_family(tmp_path):
    # covers: ACD-2500a-3-ii
    # angle: boundary
    """S (no declared files; links scripts/build.py as modified) gets no blocking
    finding of this family, is listed 'not evaluated: no declared files' for it and
    is not counted as passed (family_counts: P evaluated, S not evaluated)."""
    store = _store(tmp_path, [_p_record(), _s_record()])

    _, report = check_store(store)

    s_findings = _family(report, _S)
    assert len(s_findings) == 1, s_findings
    assert s_findings[0]["disposition"] == DISPOSITION_NOT_EVALUATED
    assert _NO_FILES in finding_text(s_findings[0])
    assert report["family_counts"][FAMILY_MODIFIES] == {"evaluated": 1, "not_evaluated": 1}

    only_s = make_store(tmp_path / "only_s", [_s_record()])
    exit_code, only_report = check_store(only_s)
    assert only_report["family_counts"][FAMILY_MODIFIES] == {"evaluated": 0, "not_evaluated": 1}
    assert _blocking(only_report["findings"]) == []  # unevaluated is not a failure ...
    assert only_report["verdict"] == "passed" and exit_code == 0  # ... and not a pass count


def test_family_finding_fails_stage_verdict(tmp_path):
    # covers: ACD-2500a-3-ii
    # angle: failure
    """A folder whose only finding is P's scripts/y.py finding yields verdict
    'failed' and a non-zero exit; the same folder without the y.py link passes
    (control: the finding is what flips the verdict)."""
    store = _store(tmp_path / "bad", [_p_record()])

    exit_code, report = check_store(store)

    assert len(report["findings"]) == 1, report["findings"]
    assert report["findings"][0]["rule_family"] == FAMILY_MODIFIES
    assert report["verdict"] == "failed"
    assert exit_code != 0

    good = _store(tmp_path / "good", [_p_record(doc_links=[_link("scripts/x.py", "modifies")])])
    good_exit, good_report = check_store(good)
    assert good_report["findings"] == [], good_report["findings"]
    assert good_report["verdict"] == "passed" and good_exit == 0


def test_declared_files_read_through_seam(tmp_path, monkeypatch):
    # covers: ACD-2500a-3-ii
    # angle: seam
    """With the seam's answer for P substituted (declared_files.get_declared_files
    patched, the record on disk unchanged) the family's findings follow the
    substituted answer: declaring scripts/y.py removes the finding, the 'no declared
    files' state turns P into a not-evaluated entry. The seam is called for P."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    sys.path.insert(0, str(REPO_ROOT))
    modules = []
    for name in ("declared_files", "scripts.ac_store.declared_files"):
        try:
            modules.append(importlib.import_module(name))
        except ImportError:
            continue
    assert modules, "declared_files seam module must be importable"
    real = modules[0].get_declared_files
    no_files = modules[0].NO_DECLARED_FILES
    calls: list[str] = []
    answers: dict[str, object] = {}

    def fake(record):
        record_id = record.get("id")
        if record_id == _P:
            calls.append(record_id)
            if "answer" in answers:
                return answers["answer"]
        return real(record)

    store = _store(tmp_path, [_p_record()])
    on_disk = snapshot_tree(store.folder)
    for module in modules:
        monkeypatch.setattr(module, "get_declared_files", fake)

    _, unsubstituted = check_store(store)  # the seam is consulted; its answer matches disk
    assert calls, "the family must read P's declared files through get_declared_files"
    assert len(_blocking(_family(unsubstituted, _P))) == 1

    answers["answer"] = [
        {"path": "scripts/x.py", "state": "existing"},
        {"path": "scripts/y.py", "state": "existing"},
    ]
    _, with_y = check_store(store)
    assert _blocking(_family(with_y, _P)) == [], _family(with_y, _P)  # follows the seam

    answers["answer"] = [{"path": "scripts/x.py", "state": "existing"}]
    _, without_y = check_store(store)
    assert len(_blocking(_family(without_y, _P))) == 1  # and back again

    answers["answer"] = no_files
    _, none_declared = check_store(store)
    p_findings = _family(none_declared, _P)
    assert _blocking(p_findings) == [] and len(p_findings) == 1, p_findings
    assert p_findings[0]["disposition"] == DISPOSITION_NOT_EVALUATED
    assert snapshot_tree(store.folder) == on_disk  # the record on disk never moved


def test_acd_2500a_3_ii_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-3-ii
    # angle: reachability
    """The real script in a subprocess reports P's scripts/y.py finding, lists S as
    not evaluated for the family, and exit code 1 is the failed verdict."""
    store = _store(tmp_path, [_p_record(), _s_record()])

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 1, (run.stdout[:600], run.stderr[:600])
    assert run.report["verdict"] == "failed"
    p_findings = _blocking(_family(run.report, _P))
    assert len(p_findings) == 1 and "scripts/y.py" in finding_text(p_findings[0])
    assert _NO_FILES in finding_text(_family(run.report, _S)[0])
