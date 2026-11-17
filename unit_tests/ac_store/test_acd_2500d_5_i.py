"""
MODULE: unit_tests/ac_store/test_acd_2500d_5_i.py
COVERS: ACD-2500d-5-i
GOAL: Red-first specification of ticket 28: scripts/ac_store/design_prepass.py, the deterministic
    pre-pass whose report gives the code-aware agent the mechanical file facts of a batch: per
    declared file exists / to_be_created / neither, per named test directory its existence, per
    reference file its existence, same file type and same area. Byte-identical across runs; no
    report (non-zero exit, empty stdout) on any error.
BUSINESS CONTEXT: ADR-071 / G4 architect note (ticket 29, section 3). The agent must not guess
    file facts; the workflow reads the pre-pass from disk and does not dispatch the agent when
    there is no report (that fifth AC test lives in ticket 31, conflict 3).
ARCHITECTURE: Every test runs the REAL CLI as a subprocess over a tmp consumer-style repo
    (unit_tests/ac_store/_acd_2500d_5_i_fixtures.py); records come from yaml.safe_dump. Definitions
    pinned by the note: the tree wins (exists > to_be_created > neither); same_type = same
    lower-cased suffix as the deliverable, same_area = same parent directory; test_dirs = distinct
    test_spec target_dirs plus <test-root>/<parent dir name of each declared file>; reference
    candidates (up to 10 sorted siblings) only for a record carrying hold_reason
    'reference file pending'.
RED STATE: design_prepass.py does not exist, so every run exits non-zero with no report (an
    ASSERTION red on the exit code, never an import error: the script is only ever executed).
NEGATIVE-ROW CONTROLS: each "absent / different" claim sits beside a control in the same report.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500d_5_i_fixtures import (  # noqa: E402
    DOC_REFERENCE, MISSING, NEW_FILE, R1, R2, R3, SIBLING, batch_store, declared_states, dirs_of,
    record_of, reference_requirements, run_prepass, tree_bytes, write_tree,
)
from _rule_check_fixtures import intent_record, make_store, valid_record  # noqa: E402

BATCH = [R1, R2, R3]


def _ok(store, ids=BATCH, *extra):
    run = run_prepass(store, ids, *extra)
    assert run.exit_code == 0, f"pre-pass failed: exit {run.exit_code}, stderr {run.stderr[:400]!r}"
    assert run.report is not None, "pre-pass exited 0 but printed no report"
    return run.report


def test_declared_file_states_reported(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: criterion
    """R1's scripts/a.py is 'exists', R2's new file 'to_be_created', R3's scripts/missing.py 'neither'
    (python-coder: design_prepass.py reads declared files only through declared_files.get_declared_files)."""
    report = _ok(batch_store(tmp_path))

    assert declared_states(record_of(report, R1)) == {"scripts/a.py": "exists"}
    assert declared_states(record_of(report, R2)) == {NEW_FILE: "to_be_created"}
    assert declared_states(record_of(report, R3)) == {MISSING: "neither"}
    assert report["batch"] == BATCH


def test_test_directory_existence_reported(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: criterion
    """R1 names unit_tests/ac_store/ (present) and unit_tests/missing_dir/ (absent): each reported with its
    own existence, so an implementation reporting one answer for all directories fails."""
    dirs = dirs_of(record_of(_ok(batch_store(tmp_path)), R1))

    assert dirs["unit_tests/ac_store"] is True
    assert dirs["unit_tests/missing_dir"] is False


def test_reference_file_type_and_area_reported(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: criterion
    """R2's reference file is the same type and area as its deliverable; the entry is exactly
    {path, exists, same_type, same_area} in the contract shape."""
    report = _ok(batch_store(tmp_path))

    assert record_of(report, R2)["reference_files"] == [
        {"path": SIBLING, "exists": True, "same_type": True, "same_area": True}
    ]
    assert record_of(report, R1)["reference_files"] == []  # control: no reference named, none invented


def test_r3_missing_file_neither_and_reference_different_type(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: criterion
    """For R3 the report says scripts/missing.py is 'neither' and the .md reference is a different
    file type (and a different area), while the reference itself exists."""
    report = _ok(batch_store(tmp_path))
    r3 = record_of(report, R3)

    assert declared_states(r3)[MISSING] == "neither"
    assert r3["reference_files"] == [
        {"path": DOC_REFERENCE, "exists": True, "same_type": False, "same_area": False}
    ]
    assert record_of(report, R2)["reference_files"][0]["same_type"] is True  # control, same report


def test_two_runs_byte_identical(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """Two runs on the same batch and tree give identical stdout BYTES: LF only, keys sorted, records
    sorted by id whatever the order of --ids, declared files sorted by path whatever the declared order."""
    reversed_files = valid_record(
        "ZZP-4", declared_files=[{"path": "scripts/z.py", "state": "existing"}, {"path": "scripts/a.py", "state": "existing"}]
    )
    store = batch_store(tmp_path, [reversed_files])
    first = run_prepass(store, [*BATCH, "ZZP-4"])
    second = run_prepass(store, [*BATCH, "ZZP-4"])
    shuffled = run_prepass(store, ["ZZP-4", R3, R1, R2])

    assert first.exit_code == 0 and first.stdout, first.stderr
    assert first.stdout == second.stdout
    assert first.stdout == shuffled.stdout, "the report must not depend on the order of --ids"
    assert b"\r" not in first.stdout and first.stdout.endswith(b"\n")
    pairs = json.loads(first.stdout, object_pairs_hook=lambda items: items)
    assert [key for key, _ in pairs] == sorted(key for key, _ in pairs), "top-level keys must be sorted"
    report = json.loads(first.stdout)
    assert report["batch"] == sorted(report["batch"]) == [R1, R2, R3, "ZZP-4"]
    assert [item["path"] for item in record_of(report, "ZZP-4")["declared_files"]] == ["scripts/a.py", "scripts/z.py"]


def test_no_declared_files_record_emits_empty_list(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """A record in the 'no declared files' state appears with declared_files: [] (consumers read that as
    'not evaluated: no declared files'); a record WITH declared files never does (control, same report)."""
    nothing = intent_record("ZZP-5", ["it works"], drop=("declared_files",))
    report = _ok(batch_store(tmp_path, [nothing]), [*BATCH, "ZZP-5"])

    assert record_of(report, "ZZP-5")["declared_files"] == []
    assert all(record_of(report, rid)["declared_files"] for rid in BATCH)


def test_tree_wins_and_paths_outside_the_repo_are_neither(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """A declared 'to_be_created' file already on disk is 'exists' (the tree wins); a path with '..' or an
    absolute path is 'neither' even when a real file sits there (nothing resolves outside the repo)."""
    outside = tmp_path / "outside.py"
    outside.write_text("X = 1\n", encoding="utf-8")
    odd = valid_record(
        "ZZP-6",
        declared_files=[
            {"path": "scripts/a.py", "state": "to_be_created"},
            {"path": "../outside.py", "state": "existing"},
            {"path": outside.as_posix(), "state": "existing"},
        ],
    )
    states = declared_states(record_of(_ok(batch_store(tmp_path / "repo", [odd]), ["ZZP-6"]), "ZZP-6"))

    assert states["scripts/a.py"] == "exists"
    assert states["../outside.py"] == "neither"
    assert states[outside.as_posix()] == "neither"


def test_nonexistent_reference_file_reports_exists_false(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """A reference file that is not on disk is reported exists false, while same_type and same_area are
    still judged from the paths (same suffix, same directory as the deliverable)."""
    ghost = valid_record(
        "ZZP-7",
        declared_files=[{"path": NEW_FILE, "state": "to_be_created"}],
        it_requirements=reference_requirements("scripts/ac_store/ghost.py"),
    )
    report = _ok(batch_store(tmp_path, [ghost]), ["ZZP-7", R2])

    assert record_of(report, "ZZP-7")["reference_files"] == [
        {"path": "scripts/ac_store/ghost.py", "exists": False, "same_type": True, "same_area": True}
    ]
    assert record_of(report, R2)["reference_files"][0]["exists"] is True  # control


def test_test_dirs_include_the_mirrored_directory_and_honour_test_root(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """Besides the test_spec target_dirs, each declared file names <test-root>/<its parent directory's
    name> (scripts/ac_store/x.py -> unit_tests/ac_store/); --test-root moves the mirror, never the target_dirs."""
    store = batch_store(tmp_path)

    default = dirs_of(record_of(_ok(store), R1))
    moved = dirs_of(record_of(_ok(store, BATCH, "--test-root", "tests/"), R1))

    assert default == {"unit_tests/ac_store": True, "unit_tests/missing_dir": False, "unit_tests/scripts": False}
    assert moved == {"unit_tests/ac_store": True, "unit_tests/missing_dir": False, "tests/scripts": False}
    assert dirs_of(record_of(_ok(store), R2)) == {"unit_tests/ac_store": True}


def test_reference_candidates_only_for_a_pending_record(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """A record marked hold_reason 'reference file pending' (no reference named) gets up to 10 sorted
    candidates: files in the deliverable's directory with its suffix, excluding itself; the identical
    record without the marker gets none."""
    tree = {f"scripts/pend/mod_{n:02d}.py": "X = 1\n" for n in range(12)}
    write_tree(tmp_path, {**tree, "scripts/pend/readme.md": "x\n"})
    files = [{"path": "scripts/pend/new_unit.py", "state": "to_be_created"}]
    pending = valid_record("ZZP-8", declared_files=files, hold_reason="reference file pending")
    plain = valid_record("ZZP-9", declared_files=files)
    store = make_store(tmp_path, [pending, plain])

    report = _ok(store, ["ZZP-8", "ZZP-9"])
    candidates = record_of(report, "ZZP-8")["reference_files"]

    assert [item["path"] for item in candidates] == [f"scripts/pend/mod_{n:02d}.py" for n in range(10)]
    assert all(item["same_type"] and item["same_area"] for item in candidates)
    assert record_of(report, "ZZP-9")["reference_files"] == []


def test_ids_outside_the_scope_are_skipped_silently(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """An L1 composite and an L2 leaf with no intent, declared files or package surface are in neither
    batch nor records, and do not fail the run (allAcsWritten lists composites too)."""
    composite = valid_record("ZZP-10", level="L1", drop=("declared_files",))
    empty_leaf = valid_record("ZZP-11", drop=("declared_files",))
    report = _ok(batch_store(tmp_path, [composite, empty_leaf]), [*BATCH, "ZZP-10", "ZZP-11"])

    assert report["batch"] == BATCH
    assert [item["id"] for item in report["records"]] == BATCH


def test_prepass_failures_print_no_report(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: failure
    """An unknown id, an unreadable record and an unknown flag each give a non-zero exit, an EMPTY stdout
    (never a partial report) and a stderr message; the same batch without the fault exits 0 (control)."""
    store = batch_store(tmp_path)
    control = run_prepass(store, BATCH)
    store.write_text("ZZP-12.yaml", "id: ZZP-12\nlevel: L2\ncriteria: [unclosed\n")

    unknown = run_prepass(store, [*BATCH, "ZZP-404"])
    unreadable = run_prepass(store, [*BATCH, "ZZP-12"])
    bad_flag = run_prepass(store, BATCH, "--no-such-flag")

    assert control.exit_code == 0 and control.report is not None
    for name, run in (("unknown id", unknown), ("unreadable record", unreadable), ("bad flag", bad_flag)):
        assert run.exit_code != 0, f"{name}: must exit non-zero"
        assert run.stdout == b"", f"{name}: must print no report, got {run.stdout[:200]!r}"
        assert run.stderr.strip(), f"{name}: must explain itself on stderr"


def test_prepass_never_writes(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: failure
    """The pre-pass is read-only: the repo tree and the store are byte-identical after a run, for both a
    successful batch and a failing one (and the successful run really produced a report)."""
    store = batch_store(tmp_path)
    before = tree_bytes(store.repo_root)

    ok = run_prepass(store, BATCH)
    failed = run_prepass(store, [*BATCH, "ZZP-404"])

    assert ok.exit_code == 0 and ok.report is not None and failed.exit_code != 0
    assert tree_bytes(store.repo_root) == before


def test_fifty_records_within_two_seconds(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: boundary
    """A batch of 50 records completes within 2 seconds (best of two whole-process runs)."""
    records = [
        valid_record(f"ZZQ-{n}", declared_files=[{"path": f"scripts/f{n}.py", "state": "to_be_created"}])
        for n in range(50)
    ]
    store = make_store(tmp_path, records)
    ids = [record["id"] for record in records]
    durations = []
    for _ in range(2):
        started = time.perf_counter()
        run = run_prepass(store, ids)
        durations.append(time.perf_counter() - started)
        assert run.exit_code == 0 and run.report is not None, run.stderr
        assert len(run.report["records"]) == 50

    assert min(durations) < 2.0, durations


def test_acd_2500d_5_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-5-i
    # angle: reachability
    """Entry point (resolved: CLI script, step 1): `python scripts/ac_store/design_prepass.py --ids ...` in a
    real subprocess. The report is what the workflow consumes (exit 0 + one JSON document); the failing
    run is what it must treat as batch failure (non-zero + no stdout). The tree is the only input: after
    removing the test directory the same run reports it absent."""
    store = batch_store(tmp_path)

    good = run_prepass(store, BATCH, cwd=tmp_path.parent)
    bad = run_prepass(store, ["ZZP-404"], cwd=tmp_path.parent)

    assert good.exit_code == 0, good.stderr
    assert json.loads(good.stdout)["records"][0]["id"] == R1
    assert declared_states(record_of(good.report, R3)) == {MISSING: "neither"}
    assert bad.exit_code != 0 and bad.stdout == b""
    shutil.rmtree(store.repo_root / "unit_tests")
    after = run_prepass(store, [R1])
    assert after.exit_code == 0 and dirs_of(record_of(after.report, R1))["unit_tests/ac_store"] is False
