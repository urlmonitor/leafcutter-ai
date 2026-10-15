"""
MODULE: unit_tests/ac_store/test_acd_2500c_2_hold_report.py
COVERS: ACD-2500c-2
GOAL: Red-first specification of scripts/ac_store/approval_hold_report.py, the deterministic oracle
    the /plan-feature approval gate asks which requirements may be offered for approval.
BUSINESS CONTEXT: ACD-2500c-2 (G4 architect note, sections 2.5 and 5). The workflow cannot read
    records, so before the gate and again right before the approval write it runs
    `python approval_hold_report.py --ids A,B --store-root DIR [--repo-root DIR]` and reads
    {"approved": [ids with no hold], "held": [{id, file, reason}]} from stdout. An unknown or
    unreadable id exits 1 with no report, which the workflow reads as "everything held".
ARCHITECTURE: The CLI runs as a real subprocess (its production entry point) against tmp stores
    built with the real serializer (_acd_2500b_approval_fixtures). Hold reasons come from
    `approval_hold_reason`, the one predicate approve_acs.py already uses; here "approved" means
    "no hold, offerable" and nothing is promoted or written. The deployed copy is checked from the
    shared reference layout (no build spawned): the workflow runs `.leafcutter/scripts/ac_store/`.
RED STATE: scripts/ac_store/approval_hold_report.py does not exist; the CLI exits 2 (no such file).
WRONG VERSIONS the tests catch: held ids listed under approved; an absolute or backslash `file`; a
    partial report printed next to an error exit; an unreadable record read as "no hold"; the
    script writing to the store (a promotion); the module missing from the deploy declaration.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import (  # noqa: E402
    PENDING, SCRIPTS, TWO, build, design_for, legacy_leaf, reviewed_intent, reviewed_no_tests,
)
from _rule_check_fixtures import REPO_ROOT, unreadable_record_text  # noqa: E402

CLI = SCRIPTS / "approval_hold_report.py"
HELD, DESIGNED, NO_TESTS, LEGACY = "ZZH-1", "ZZH-2", "ZZH-3", "ZZH-4"
ALL = [HELD, DESIGNED, NO_TESTS, LEGACY]
_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _store(tmp_path):
    """R1 intent without a design (held); R2 designed; R3 needs no tests; R4 a legacy design."""
    return build(tmp_path, [
        reviewed_intent(HELD),
        reviewed_intent(DESIGNED, spec=design_for(TWO)),
        reviewed_no_tests(NO_TESTS),
        legacy_leaf(LEGACY, readiness="reviewed"),
    ])


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _run(store, ids, *extra, repo_root: bool = True, cwd: Path | None = None, script: Path = CLI):
    argv = [sys.executable, str(script), "--ids", ",".join(ids),
            "--store-root", str(store.repo_root / "docs" / "acceptance-criteria"), *extra]
    if repo_root:
        argv += ["--repo-root", str(store.repo_root)]
    proc = subprocess.run(argv, cwd=str(cwd or store.repo_root), capture_output=True, text=True,
                          encoding="utf-8", timeout=90, env=_ENV)
    return proc


def _report(proc) -> dict:
    """stdout as exactly one JSON document (the failure message carries stderr)."""
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout must be one JSON document ({exc}); exit={proc.returncode}; "
                             f"stdout={proc.stdout[:300]!r}; stderr={proc.stderr[:300]!r}") from exc


def test_hold_report_splits_approvable_from_held(tmp_path):
    # covers: ACD-2500c-2
    # angle: reachability
    """AC-3: run as `python approval_hold_report.py --ids ... --store-root ... --repo-root ...`, the CLI exits 0
    and prints exactly {"approved": [...], "held": [...]}: R2, R3 and R4 (control rows: a covered design, a
    no-tests record, a legacy design) are approved; R1 (intent, no design) is held with `test design pending`
    and its repo-relative POSIX file. Exact counts: 3 approved, 1 held."""
    store = _store(tmp_path)

    proc = _run(store, ALL)

    assert proc.returncode == 0, proc.stderr
    report = _report(proc)
    assert set(report) == {"approved", "held"}, report
    assert sorted(report["approved"]) == [DESIGNED, NO_TESTS, LEGACY], report
    assert report["held"] == [{"id": HELD, "file": store.rel(HELD), "reason": PENDING}], report


@pytest.mark.parametrize(("ids", "approved", "held"), [([HELD], [], [HELD]), ([DESIGNED], [DESIGNED], [])],
                         ids=["every_id_held", "no_id_held"])
def test_hold_report_boundaries_keep_both_lists(ids, approved, held, tmp_path):
    # covers: ACD-2500c-2
    # angle: boundary
    """Boundary: when every asked id is held, `approved` is an empty list (present, not omitted), so the gate
    offers nothing; when none is held, `held` is an empty list. One id each way."""
    store = _store(tmp_path)

    proc = _run(store, ids)

    assert proc.returncode == 0, proc.stderr
    report = _report(proc)
    assert report["approved"] == approved, report
    assert [h["id"] for h in report["held"]] == held, report


def test_repo_root_is_inferred_from_the_store_when_the_flag_is_omitted(tmp_path):
    # covers: ACD-2500c-2
    # angle: boundary
    """`--repo-root` is optional: without it the root is the nearest ancestor of the store holding
    docs/acceptance-criteria (the rule check's inference), not the cwd, so `file` is the same repo-relative
    path even when the process runs from an unrelated directory."""
    store = _store(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    proc = _run(store, [HELD], repo_root=False, cwd=elsewhere)

    assert proc.returncode == 0, proc.stderr
    report = _report(proc)
    assert [h["file"] for h in report["held"]] == [store.rel(HELD)], report


@pytest.mark.parametrize("bad", ["unknown_id", "unreadable_record"])
def test_unknown_or_unreadable_id_exits_one_with_no_report(bad, tmp_path):
    # covers: ACD-2500c-2
    # angle: failure
    """Fail-closed: one unknown id, or one record whose YAML cannot be read, among otherwise good ids exits 1
    with NOTHING on stdout (no partial report: the workflow reads that as "everything held"). Control: the
    same call without the bad id exits 0 with a report, so the error is caused by the bad id alone."""
    store = _store(tmp_path)
    if bad == "unreadable_record":
        store.write_text("ZZH-9.yaml", unreadable_record_text("ZZH-9"))
    asked = [*ALL, "ZZH-9"]

    proc = _run(store, asked)
    control = _run(store, ALL)

    assert control.returncode == 0 and control.stdout.strip(), control.stderr
    assert proc.returncode == 1, (proc.returncode, proc.stdout[:300], proc.stderr[:300])
    assert proc.stdout.strip() == "", f"a report was printed next to the error: {proc.stdout[:300]}"
    assert proc.stderr.strip(), "the error must be explained on stderr"


def test_hold_report_is_read_only_and_deterministic(tmp_path):
    # covers: ACD-2500c-2
    # angle: discrimination
    """Two runs on the same store print byte-identical stdout, and the store and tree are byte-identical
    afterwards: the oracle never promotes or edits a record (wrong version: reusing approve_acs's write path
    and approving the approvable ones as a side effect, which would also change the second run's answer)."""
    store = _store(tmp_path)
    before = _tree(store.repo_root)

    first, second = _run(store, ALL), _run(store, ALL)

    assert first.returncode == 0 and second.returncode == 0, first.stderr
    assert first.stdout == second.stdout and first.stdout.strip(), "two runs must print the same bytes"
    assert _tree(store.repo_root) == before, "approval_hold_report.py must never write"
    for rid in (DESIGNED, NO_TESTS, LEGACY):
        assert store.read(rid)["readiness"] == "reviewed", f"{rid} was promoted"


def test_hold_report_is_declared_in_the_rule_check_deploy_map():
    # covers: ACD-2500c-2
    # angle: deployed
    """The workflow runs `.leafcutter/scripts/ac_store/approval_hold_report.py`, so the script is declared
    exactly once in RULE_CHECK_DEPLOY_MAP (which AC_STORE_DEPLOY_MAP splices in), its source exists, and every
    scripts/ac_store module it imports is itself deployed (the closure the real build guard computes)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_phases_ac_store as phase
    import build_phases_ac_store_rc as rc_map
    import build_referential_integrity as bri

    entry = "scripts/ac_store/approval_hold_report.py"
    declared = [src for src, _dest in rc_map.RULE_CHECK_DEPLOY_MAP]
    assert "scripts/ac_store/requirement_rule_check.py" in declared  # control: the map was read correctly
    assert declared.count(entry) == 1, f"{entry} must be declared exactly once in RULE_CHECK_DEPLOY_MAP"
    assert (REPO_ROOT / entry).is_file(), f"declared source missing: {entry}"
    deployed = {src for src, _dest in phase.AC_STORE_DEPLOY_MAP}
    closure = bri.compute_intra_package_closure(REPO_ROOT / entry, REPO_ROOT)
    modules = {m for m in closure if m.startswith("scripts/ac_store/") and m.endswith(".py")}
    assert "scripts/ac_store/_approval_holds.py" in modules, "the oracle must reuse the approval predicate"
    assert modules <= deployed, sorted(modules - deployed)


@pytest.mark.shared_layout_reader
def test_deployed_hold_report_matches_the_canonical_script(shared_reference_layout, tmp_path):
    # covers: ACD-2500c-2
    # angle: deployed
    """From the deployed layout: .leafcutter/scripts/ac_store/approval_hold_report.py exists and, on the same
    store, prints exactly the bytes the canonical script prints (the deployed copy imports only deployed
    modules and has not drifted)."""
    layout = Path(shared_reference_layout)
    deployed = layout / ".leafcutter" / "scripts" / "ac_store" / "approval_hold_report.py"
    assert deployed.is_file(), f"not deployed: {deployed}"
    store = _store(tmp_path)

    canonical = _run(store, ALL)
    from_deployed = _run(store, ALL, cwd=layout, script=deployed)

    assert canonical.returncode == 0, canonical.stderr
    assert from_deployed.returncode == 0, from_deployed.stderr
    assert from_deployed.stdout == canonical.stdout, "deployed copy drifted from the canonical script"
