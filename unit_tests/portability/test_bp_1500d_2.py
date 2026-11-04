"""
MODULE: test_bp_1500d_2
AC: BP-1500d-2 -- "The record still reads after the project is moved, copied or
    opened somewhere else"

Expected RED at authoring time: today's record carries keys anchored to the
producing package's position (parent-step prefixed template keys), and the
deployed reader does not report a location-keyed record as unreadable naming
the record and the project. All tests use the shared BP-1500d-1 harness (a real
build.py subprocess into an out-of-package project); no second harness.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ._bp1500d1_harness import HarnessBuild, build_out_of_package_harness
from ._bp1500d2_support import (
    MANIFEST_NAME,
    assert_package_absent_from_ancestors,
    copy_project,
    load_record,
    location_keyed,
    new_scratch,
    non_portable_keys,
    read_with_deployed_reader,
)


@pytest.fixture(scope="module")
def built() -> HarnessBuild:
    hb = build_out_of_package_harness()
    assert hb.proc.returncode == 0, hb.proc.stderr[-500:]
    yield hb
    hb.cleanup()


@pytest.fixture()
def scratch():
    s = new_scratch()
    yield s
    shutil.rmtree(s, ignore_errors=True)


def _relocate(project: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(project), str(dest))
    return dest


def test_bp_1500d_2_record_reads_at_the_new_location_after_the_project_is_moved_without_the_package(
    built: HarnessBuild, scratch: Path
) -> None:
    # covers: BP-1500d-2
    # angle: criterion
    original = copy_project(built, scratch / "orig" / "proj")
    before = load_record(original)
    moved = _relocate(original, scratch / "x" / "y" / "z" / "moved_project")
    assert len(moved.parts) != len(original.parts) and moved.parent != original.parent
    assert not original.exists()
    assert_package_absent_from_ancestors(moved, built.package_dir.name)

    after = load_record(moved)  # reads without a rebuild
    assert after == before, "record changed on the move"
    assert non_portable_keys(after) == [], (
        "record entries are keyed to the location they were written in: "
        f"{non_portable_keys(after)[:3]}"
    )
    read = read_with_deployed_reader(moved)
    assert read.returncode == 0 and read.verified == len(after["output_mappings"]), read.output[-800:]


def test_bp_1500d_2_every_entry_still_resolves_to_the_artifact_it_describes_in_the_relocated_tree(
    built: HarnessBuild, scratch: Path
) -> None:
    # covers: BP-1500d-2
    # angle: real_artifact
    original = copy_project(built, scratch / "orig" / "proj")
    pre_count = len(load_record(original)["output_mappings"])
    moved = _relocate(original, scratch / "deeper" / "still" / "proj2")
    assert not original.exists()  # an absolute path to the old place cannot resolve

    # cold process: parse the bytes the real build serialized
    proc = subprocess.run(
        [sys.executable, "-I", "-c",
         "import json,sys;print(json.dumps(sorted(json.load(open(sys.argv[1]))['output_mappings'])))",
         str(moved / MANIFEST_NAME)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    keys = json.loads(proc.stdout)
    assert pre_count > 0 and len(keys) == pre_count
    unresolved = [k for k in keys if not (moved / k).is_file()]
    assert unresolved == [], unresolved[:3]
    assert non_portable_keys(load_record(moved)) == []


def test_bp_1500d_2_the_record_is_read_through_the_real_reader_entry_point_in_a_process_that_cannot_see_the_package(
    built: HarnessBuild, scratch: Path
) -> None:
    # covers: BP-1500d-2
    # angle: reachability
    moved = _relocate(copy_project(built, scratch / "o" / "p"), scratch / "a" / "b" / "c" / "proj")
    assert_package_absent_from_ancestors(moved, built.package_dir.name)
    clean = read_with_deployed_reader(moved)
    assert clean.returncode == 0 and clean.verified > 0, clean.output[-800:]

    # the result is consumed: tamper one deployed artifact -> verdict changes
    victim = sorted(load_record(moved)["output_mappings"])[0]
    target = moved / victim
    target.write_bytes(target.read_bytes() + b"\n# tampered after relocation\n")
    tampered = read_with_deployed_reader(moved)
    assert tampered.returncode != 0 and tampered.counts.get("drifted", 0) >= 1, tampered.output[-800:]

    # and the record read there is in a form that holds wherever it is read
    assert non_portable_keys(load_record(moved)) == []


def test_bp_1500d_2_a_location_keyed_record_is_reported_unreadable_at_the_new_location_and_still_reads_at_the_original(
    built: HarnessBuild, scratch: Path
) -> None:
    # covers: BP-1500d-2
    # angle: failure
    good_a = copy_project(built, scratch / "g" / "orig")
    bad_a = copy_project(built, scratch / "b" / "orig")
    location_keyed(bad_a)
    n = len(load_record(good_a)["output_mappings"])
    assert n > 0

    run1 = read_with_deployed_reader(good_a)
    run3 = read_with_deployed_reader(bad_a)
    assert run1.returncode == 0 and run1.verified == n
    # run 3: the load-bearing control -- non-portable record still reads at origin
    assert run3.verified == n and run3.counts.get("missing", 1) == 0 and run3.counts.get("drifted", 1) == 0, run3.output[-600:]

    good_b = _relocate(good_a, scratch / "g2" / "deeper" / "new")
    bad_b = _relocate(bad_a, scratch / "b2" / "deeper" / "new")
    run2 = read_with_deployed_reader(good_b)
    run4 = read_with_deployed_reader(bad_b)
    assert run2.returncode == 0 and run2.verified == n, run2.output[-600:]

    # run 4: reported unreadable, naming record and project; not accepted, not empty
    assert run4.returncode != 0
    assert run4.verified == 0
    assert "unreadable" in run4.output.lower(), run4.output[-800:]
    assert MANIFEST_NAME in run4.output, "report must name the record"
    assert str(bad_b.parent.name) in run4.output, "report must name the project"
    assert run4.counts.get("missing", 0) + run4.counts.get("unreadable", 0) > 0, "must not read as an empty record"


@pytest.mark.parametrize("package_dir_name", ["leafcutter-ai", "wt-bp900-deploy"])
def test_bp_1500d_2_readability_holds_in_the_producing_workspace_under_a_differently_named_package_directory(
    package_dir_name: str,
) -> None:
    # covers: BP-1500d-2
    # angle: deployed
    hb = build_out_of_package_harness(package_dir_name=package_dir_name)
    try:
        assert hb.proc.returncode == 0, hb.proc.stderr[-500:]
        rec = load_record(hb.target_root)
        n = len(rec["output_mappings"])
        read = read_with_deployed_reader(hb.target_root)
        assert n > 0 and read.returncode == 0 and read.verified == n, read.output[-600:]
        # entry keys must not carry the package directory's own name
        carrying = [
            k for k in list(rec) + list(rec["output_mappings"])
            if package_dir_name in k.replace("\\", "/").split("/")
        ]
        assert carrying == [], carrying[:3]
        assert non_portable_keys(rec) == []
    finally:
        hb.cleanup()
