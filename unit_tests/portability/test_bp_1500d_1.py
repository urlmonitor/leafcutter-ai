"""
MODULE: test_bp_1500d_1
AC: BP-1500d-1 -- "The record of what was installed is written into the
    project that received it, and accounts for that project"

These tests are EXPECTED RED AT AUTHORING TIME per the AC's own test_spec
descriptions (entries 2 and 4 name the specific measured symptom: an
out-of-package build can emit ``output_mappings: {}`` while exiting 0, and
today's writer targets can be mis-anchored so the record never lands inside
the receiving project's own tree). They exercise the REAL ``build.py``
command line as a subprocess against a REAL out-of-package harness (see
``_bp1500d1_harness.py`` -- this AC constructs that harness because
BP-900h-1, the AC that specifies it, is an unstarted spec with zero
implementation anywhere in the workspace).

All six tests are marked ``_MANUAL`` (module docstring performance note):
the harness performs a real ``git archive`` of the whole producing package
plus a real ``build.py`` subprocess run, which took ~18s in local
measurement -- far past the 5-second per-test budget. A single module-scoped
build is shared across all six test functions to avoid paying that cost six
times over.

DECISION HISTORY
====================================================================
- 2026-09-01 [test-writer/BP-1500d-1]: Initial red stubs, per test_spec.
====================================================================
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._bp1500d1_harness import (
    REAL_PACKAGE_ROOT,
    HarnessBuild,
    build_out_of_package_harness,
    hash_file,
    is_under_package_parent,
    probe_child_sys_path,
)


@pytest.fixture(scope="module")
def harness() -> HarnessBuild:
    """One real out-of-package build, shared by every test in this module."""
    hb = build_out_of_package_harness()
    yield hb
    hb.cleanup()


def _inspect(target_root: Path) -> tuple[bool, str]:
    """THE INSPECTION this AC's criterion demands be demonstrated to
    discriminate (test_spec entry 6). Scoped deliberately to THIS AC's own
    Then-clause -- record present IN the receiving project's own tree, and
    non-empty -- not to the separate readers (check_build_drift.py /
    check_output_drift.py) whose broader multi-root search is BP-1500d-4's
    subject, per this AC's own notes."""
    manifest_path = target_root / ".build_manifest.json"
    if not manifest_path.is_file():
        return False, f"no record found in {target_root}"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"record at {manifest_path} unreadable: {exc}"
    mappings = data.get("output_mappings", {})
    if not mappings:
        return False, f"record at {manifest_path} accounts for nothing (0 entries)"
    return True, f"record at {manifest_path} accounts for {len(mappings)} entries"


def test_bp_1500d_1_out_of_package_harness_target_is_not_under_the_package_parent_MANUAL(
    harness: HarnessBuild,
) -> None:
    # covers: BP-1500d-1
    # angle: deployed
    """MANUAL: real git-archive + real build.py subprocess in module fixture
    (~18s). THE FIXTURE PRECONDITION. Asserts the harness layout itself:
    target not reachable via the real package's own parent, a package copy
    present at <scratch>/leafcutter-ai/, target held nothing else before the
    build ran, and the placement-rule discriminator actually discriminates
    (paired control: a deliberately sibling-placed path IS flagged)."""
    assert not is_under_package_parent(harness.target_root), (
        f"harness target {harness.target_root} is reachable via the real "
        f"package's own parent {REAL_PACKAGE_ROOT.parent} -- this is the "
        "false-green placement the AC's it_requirements #2 warns against."
    )
    assert harness.package_dir.is_dir(), (
        f"expected a package copy at {harness.package_dir}"
    )
    assert (harness.package_dir / "scripts" / "build.py").is_file()
    assert harness.pre_build_target_files == ["skills_config.json"], (
        "target held more than a minimal skills_config.json before the "
        f"build ran: {harness.pre_build_target_files}"
    )

    # Paired control: the SAME discriminator must flag a sibling-placed path
    # (still reachable via the real package's own parent) as NOT satisfying
    # the placement rule -- proving the check discriminates rather than
    # merely holding for the one path we happened to build.
    sibling = REAL_PACKAGE_ROOT.parent / "a-deliberately-sibling-placed-target"
    assert is_under_package_parent(sibling), (
        f"expected {sibling} (a sibling of the real package root) to be "
        "flagged as reachable via the package's own parent -- if this "
        "assertion fails the discriminator cannot tell the two cases apart."
    )


def test_bp_1500d_1_real_build_writes_the_record_into_the_out_of_package_receiving_project_MANUAL(
    harness: HarnessBuild,
) -> None:
    # covers: BP-1500d-1
    # angle: criterion
    """MANUAL: shares the module-fixture build (~18s amortised).
    Positive half: a record exists at the receiving project's own root.
    Negative half (this AC's test_rationale entry 2): the producing
    package's OWN record is byte-unchanged by a build aimed elsewhere --
    a test that only asserts presence in the target passes on an
    implementation that writes to both."""
    assert harness.proc.returncode == 0, (
        f"real build.py exited {harness.proc.returncode}:\n"
        f"stdout:\n{harness.proc.stdout}\nstderr:\n{harness.proc.stderr}"
    )
    assert harness.manifest_exists, (
        f"expected a record at {harness.manifest_path} after a real build "
        f"into the out-of-package receiving project.\n"
        f"stdout:\n{harness.proc.stdout}\nstderr:\n{harness.proc.stderr}"
    )

    after = hash_file(harness.real_package_manifest_path)
    assert after == harness.real_package_manifest_hash_before, (
        f"the producing package's own record at "
        f"{harness.real_package_manifest_path} changed "
        f"({harness.real_package_manifest_hash_before!r} -> {after!r}) as a "
        "side effect of a build aimed at a different, out-of-package project."
    )


def test_bp_1500d_1_the_record_is_produced_through_the_real_build_command_line_not_an_imported_helper_MANUAL(
    harness: HarnessBuild,
) -> None:
    # covers: BP-1500d-1
    # angle: reachability
    """MANUAL: shares the module-fixture build (~18s amortised).
    PRODUCTION ENTRY POINT. write_build_manifest() already accepts a
    target_root parameter, so a direct-import test that hands it the
    scratch path passes today regardless of whether build.py itself routes
    the target there. This asserts the REAL command line was used (argv
    naming build.py + --target-dir), that the launch conditions kept the
    real producing package checkout off the child's reachable surface
    (verified via an independent probe child process using the exact same
    cwd/env, not merely assumed from how we built the env), and that the
    record the entry point actually produced is consumed (non-empty,
    resolvable) rather than merely present."""
    argv_str = " ".join(harness.proc.args)
    assert "build.py" in argv_str
    assert "--target-dir" in harness.proc.args
    assert str(harness.target_root) in harness.proc.args

    real_package_str = str(REAL_PACKAGE_ROOT)
    assert real_package_str not in argv_str, (
        "build subprocess argv referenced the real producing package "
        f"checkout ({real_package_str}) rather than only its harness copy."
    )

    child_sys_path = probe_child_sys_path(
        cwd=harness.target_root,
        env={k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"},
    )
    offending = [p for p in child_sys_path if real_package_str in p]
    assert not offending, (
        f"a child process launched with the same cwd/env as the real build "
        f"could still reach the producing package checkout via sys.path: "
        f"{offending}"
    )

    assert harness.manifest_exists
    manifest = harness.load_manifest()
    assert manifest.get("output_mappings"), (
        "the record the real entry point produced must actually be "
        "consumed as non-empty, not merely present on disk."
    )


def test_bp_1500d_1_record_entries_name_artifacts_actually_present_in_the_receiving_project_MANUAL(
    harness: HarnessBuild,
) -> None:
    # covers: BP-1500d-1
    # angle: real_artifact
    """MANUAL: shares the module-fixture build (~18s amortised). Parses the
    REAL bytes the real build wrote (cold read off disk, never a
    hand-authored fixture) and asserts two non-vacuity properties: the
    entry set is non-empty, and every entry resolves to a real file under
    the receiving project. Then asserts the converse on a representative
    sample of the actually-deployed tree (every deployed agent .md file),
    so a record naming one artifact out of hundreds cannot pass."""
    assert harness.manifest_exists, f"no record at {harness.manifest_path}"
    manifest = harness.load_manifest()
    mappings = manifest.get("output_mappings", {})

    assert mappings, (
        "output_mappings is empty for an out-of-package build -- this is "
        "the exact measured symptom (154 mappings in-parent vs {} for a "
        "temp-root target) this AC's it_requirements #4 names."
    )

    missing = [
        rel for rel in mappings
        if not (harness.target_root / rel).is_file()
    ]
    assert not missing, (
        f"{len(missing)} of {len(mappings)} record entries do not resolve "
        f"to a real file under {harness.target_root}: {missing[:5]}"
    )

    # Converse: a representative, independently-enumerated sample of the
    # deployed tree must actually be NAMED in the record.
    agents_dir = harness.target_root / ".claude" / "agents"
    deployed_agent_files = sorted(
        str(p.relative_to(harness.target_root)) for p in agents_dir.glob("*.md")
    )
    assert deployed_agent_files, (
        f"expected at least one deployed agent file under {agents_dir} to "
        "sample against"
    )
    unnamed = [rel for rel in deployed_agent_files if rel not in mappings]
    assert not unnamed, (
        f"{len(unnamed)} of {len(deployed_agent_files)} actually-deployed "
        f"agent files are not named anywhere in the record: {unnamed[:5]}"
    )


def test_bp_1500d_1_a_copy_of_the_project_taken_without_the_producing_package_still_carries_the_record_MANUAL(
    harness: HarnessBuild, tmp_path: Path,
) -> None:
    # covers: BP-1500d-1
    # angle: criterion
    """MANUAL: shares the module-fixture build (~18s amortised); the copy
    step itself is fast. The (b)-travels-with-it half. The package copy is
    a SIBLING of the receiving project (never nested inside it -- see the
    harness module's DECISION HISTORY), so copying the receiving project
    alone to a second location already leaves the package copy behind
    entirely by construction; this test asserts that explicitly rather than
    relying on the directory layout to make it true by accident. Asserts
    the record is present in the copy and byte-identical to the original.
    Whether the copy's entries still RESOLVE at the new location is
    BP-1500d-2's subject and is deliberately not asserted here."""
    import shutil

    assert harness.manifest_exists, f"no record at {harness.manifest_path}"
    assert not (harness.target_root / harness.package_dir.name).exists(), (
        "fixture invariant violated: the package copy must not be nested "
        "inside the receiving project for this test to mean anything"
    )

    copy_dest = tmp_path / "receiving_project_copy_without_package"
    shutil.copytree(harness.target_root, copy_dest)

    assert not (copy_dest / harness.package_dir.name).exists(), (
        "the copy must leave the producing package copy behind entirely"
    )

    copied_manifest = copy_dest / ".build_manifest.json"
    assert copied_manifest.is_file(), (
        f"a copy of the receiving project taken WITHOUT the producing "
        f"package no longer carries the record at {copied_manifest} -- a "
        "consumer who never has the producing package to hand would have "
        "no record at all."
    )
    assert hash_file(copied_manifest) == hash_file(harness.manifest_path), (
        "the copied record is not byte-identical to the original"
    )


def test_bp_1500d_1_inspection_goes_red_on_a_record_filed_with_the_package_and_on_a_record_that_accounts_for_nothing_then_green_again_MANUAL(
    harness: HarnessBuild,
) -> None:
    # covers: BP-1500d-1
    # angle: failure
    """MANUAL: shares the module-fixture build (~18s amortised); the five
    inspection runs themselves are fast file moves/writes.
    THE NEGATIVE CONTROL THE CRITERION DEMANDS. Five runs of the SAME
    inspection against the SAME harness: (1) good install, clean;
    (2) record moved into the package copy -- red; (3) restored, clean
    again; (4) record replaced with one that accounts for nothing -- red;
    (5) restored, clean again. Runs 3 and 5 are what make each red
    attributable to its own breakage rather than to an already-broken
    fixture.

    EXPECTED RED AT AUTHORING TIME, AND NOT ONLY AT run 2/4: this AC's own
    "VERIFIED EVIDENCE" measured that a genuinely out-of-package build emits
    ``output_mappings: {}`` today (this harness's DECISION HISTORY
    reproduces that live), so run 1 itself -- the "good install" baseline --
    is expected to already be red, for the SAME accounts-for-nothing reason
    run 4 constructs deliberately. That is not a broken test: it is this
    AC's Then-clause not yet being met by production code."""
    assert harness.manifest_exists, f"no record at {harness.manifest_path}"
    original_bytes = harness.manifest_path.read_bytes()

    # Run 1 -- good install, clean (EXPECTED RED at authoring time -- see
    # docstring above).
    ok, msg = _inspect(harness.target_root)
    assert ok, f"run 1 (good install) unexpectedly red: {msg}"

    # Run 2 -- record filed with the producing package copy instead of the
    # receiving project. Must go red.
    misfiled_path = harness.package_dir / ".build_manifest.json"
    harness.manifest_path.rename(misfiled_path)
    try:
        ok, msg = _inspect(harness.target_root)
        assert not ok, (
            "run 2 (record misfiled with the package) unexpectedly stayed "
            f"clean: {msg}"
        )
    finally:
        # Run 3 -- restore, clean again (attribution: run 2's red was the
        # misfiling, not an already-broken fixture).
        misfiled_path.rename(harness.manifest_path)
    ok, msg = _inspect(harness.target_root)
    assert ok, f"run 3 (restored) unexpectedly red: {msg}"

    # Run 4 -- record present but accounts for nothing. Must go red.
    empty_record = {"output_mappings": {}}
    harness.manifest_path.write_text(json.dumps(empty_record), encoding="utf-8")
    try:
        ok, msg = _inspect(harness.target_root)
        assert not ok, (
            f"run 4 (empty record) unexpectedly stayed clean: {msg}"
        )
    finally:
        # Run 5 -- restore, clean again.
        harness.manifest_path.write_bytes(original_bytes)
    ok, msg = _inspect(harness.target_root)
    assert ok, f"run 5 (restored) unexpectedly red: {msg}"
