"""
MODULE: test_bp_1500d_1_i
AC: BP-1500d-1-i -- "The record describes the producing end truthfully --
    where the package stood, and which of its files the deployment came
    from -- or says plainly that it cannot"

All six tests are marked ``_MANUAL`` (same performance rationale as the
parent module, ``test_bp_1500d_1.py``): the module-scoped fixture performs
TWO real ``git archive`` + real ``build.py`` subprocess builds
(same-directory layout A, sibling out-of-package layout B), each of which
takes several seconds -- far past the 5-second per-test budget. Both builds
are shared across all six test functions in this module via one
module-scoped fixture, so the cost is paid once, not twelve times.

RED-BASELINE CAVEAT (per this AC's own it_requirements #9, and mirrored from
``test_bp_1500d_1.py``'s own header): the harness this module builds on
(``_bp1500d1i_harness.py``, and the sibling layout it reuses from
``_bp1500d1_harness.py``) materialises its package copy via ``git archive
HEAD`` -- committed content only. Every test in this module is RED against
an uncommitted production fix in this same worktree, no matter how correct
that fix is, until the fix is committed. This is a property of the fixture,
not evidence the fix is broken; see this AC's own it_requirements #9 for the
full reasoning and the alternatives considered and rejected.

DECISION HISTORY
====================================================================
- 2026-09-07 [test-writer/BP-1500d-1-i]: Initial six-entry test_spec
  authored against ``317517346`` (the already-committed fix). Per this
  AC's it_requirements #9 and the TDD-order note in the worktree CLAUDE.md,
  these tests are GREEN ON ARRIVAL against that commit -- the fixture's
  git-archive-HEAD design makes a true pre-implementation red baseline
  structurally unreachable here, since the fix had to land before the
  harness could see it at all. This is documented as a TDD-order finding,
  not treated as a pass-on-arrival; see the sign-off comment's
  ``red_baseline`` block for the mutation-based substitute proof run against
  each test in this module (one one-line mutation of
  ``scripts/build_helpers.py`` or ``check_build_drift.py`` per test,
  confirmed red under the mutation and green again once reverted).
====================================================================
"""

from __future__ import annotations

import json

import pytest

from ._bp1500d1_harness import REAL_PACKAGE_ROOT, probe_child_sys_path
from ._bp1500d1i_harness import (
    MANIFEST_METADATA_KEYS,
    PairedSession,
    build_paired_session,
    extract_result_line,
    parse_result_field,
    run_build_drift_reader,
    template_account_keys,
)


@pytest.fixture(scope="module")
def paired_session() -> PairedSession:
    """Both layouts (same-directory + sibling), built ONCE, shared by every
    test in this module -- this AC's it_requirements #6 makes the paired
    two-layout run inside one session the contract, not a convenience."""
    session = build_paired_session()
    yield session
    session.cleanup()


def test_bp_1500d_1_i_one_session_builds_both_layouts_and_the_same_directory_record_states_both_halves_truthfully_MANUAL(
    paired_session: PairedSession,
) -> None:
    # covers: BP-1500d-1-i
    # angle: criterion
    """MANUAL: shares the module-fixture pair of real builds (~20s
    amortised). THE CONTROL. Layout A (same-directory) must state BOTH
    halves truthfully: the position resolves to the package from the
    record's own directory, and the account of the package's own files is
    non-empty with every name resolving to a real file when combined with
    the stated position. Reached through the SAME code path as layout B
    (a real ``build.py`` subprocess), not a fixture shortcut."""
    same_dir = paired_session.same_directory
    assert same_dir.proc.returncode == 0, (
        f"real build.py exited {same_dir.proc.returncode} for the "
        f"same-directory layout:\nstdout:\n{same_dir.proc.stdout}\n"
        f"stderr:\n{same_dir.proc.stderr}"
    )
    assert same_dir.manifest_exists, f"no record at {same_dir.manifest_path}"

    manifest = same_dir.load_manifest()

    # Half 1 -- the stated position. Same-directory means package_root ==
    # target_root, so the offset must be the empty string (the writer's own
    # documented meaning for "the package root and the manifest directory
    # are the same directory") -- never None (unavailable) and never a
    # non-empty offset (that would be a different, wrong layout).
    package_root_raw = manifest.get("package_root")
    assert package_root_raw == "", (
        f"layout A is genuinely the same directory, but the record's stated "
        f"position is {package_root_raw!r}, not the empty-string same-"
        "directory answer."
    )
    resolved_base = (same_dir.project_root / package_root_raw).resolve()
    assert resolved_base == same_dir.project_root.resolve(), (
        f"the stated position {package_root_raw!r} does not resolve to the "
        f"package from the record's own directory {same_dir.project_root}"
    )

    # Half 2 -- the account of the package's own files.
    account_keys = template_account_keys(manifest)
    assert account_keys, (
        "layout A's record accounts for ZERO of the package's own template "
        "files -- a same-directory install must never produce this."
    )
    missing = [key for key in account_keys if not (same_dir.project_root / key).is_file()]
    assert not missing, (
        f"{len(missing)} of {len(account_keys)} account entries do not "
        f"resolve to a real file under {same_dir.project_root}: {missing[:5]}"
    )

    # Both halves were produced through the SAME entry point as layout B --
    # a real ``build.py <target-dir>`` subprocess, never an in-process call.
    argv_str = " ".join(same_dir.proc.args)
    assert "build.py" in argv_str
    assert "--target-dir" in same_dir.proc.args


def test_bp_1500d_1_i_the_sibling_layout_record_reduces_neither_half_to_nothing_MANUAL(
    paired_session: PairedSession,
) -> None:
    # covers: BP-1500d-1-i
    # angle: criterion
    """MANUAL: shares the module-fixture pair of real builds (~20s
    amortised). The second half of the same paired session. Neither half of
    layout B's record may be silently reduced to nothing: the position
    either holds for the receiving project as it now sits, or is an
    explicit unavailable (``None``); the account is either populated with
    names that resolve, or is explicitly unavailable (paired with the same
    ``None``). The specific forbidden pair -- an empty-string position
    together with an empty account -- is asserted absent by name, since that
    exact pair is a definite false claim (same-directory) plus a false
    claim of a package that shipped nothing."""
    sibling = paired_session.sibling
    assert sibling.proc.returncode == 0, (
        f"real build.py exited {sibling.proc.returncode} for the sibling "
        f"layout:\nstdout:\n{sibling.proc.stdout}\nstderr:\n{sibling.proc.stderr}"
    )
    assert sibling.manifest_exists, f"no record at {sibling.manifest_path}"

    manifest = sibling.load_manifest()
    package_root_raw = manifest.get("package_root")
    account_keys = template_account_keys(manifest)

    # THE FORBIDDEN PAIR, asserted by name -- not merely "fields non-empty".
    forbidden_pair = package_root_raw == "" and not account_keys
    assert not forbidden_pair, (
        "layout B recorded the same-directory position ('') together with "
        "an empty account -- a definite false claim of 'the package is "
        "right here' plus a false claim of 'this package shipped nothing', "
        "for a build that is neither."
    )

    if package_root_raw is None:
        # Explicit unavailable is a legitimate answer for the position --
        # but only paired with an equally explicit unavailable account,
        # never a truthful-looking empty collection recorded on its own.
        assert not account_keys, (
            "position is explicitly unavailable (None) but the account is "
            f"non-empty ({len(account_keys)} keys) -- the two halves must "
            "be unavailable together, per this AC's agreement requirement."
        )
        return

    # The position is stated. Layout B genuinely is NOT the same directory,
    # so the stated position must not be the same-directory answer, and the
    # account must be genuinely populated with names that resolve.
    assert package_root_raw != "", (
        "layout B is a genuine out-of-package sibling install, but its "
        "record states the same-directory position ('') -- a false claim."
    )
    assert account_keys, (
        "layout B's record accounts for ZERO of the package's own template "
        "files while stating a real position -- the account was silently "
        "reduced to nothing without recording why."
    )
    missing = [
        key for key in account_keys
        if not (sibling.target_root / key).is_file()
    ]
    assert not missing, (
        f"{len(missing)} of {len(account_keys)} account entries do not "
        f"resolve to a real file under {sibling.target_root} when combined "
        f"with the stated position: {missing[:5]}"
    )


def test_bp_1500d_1_i_the_stated_position_and_the_named_package_files_agree_so_the_reader_derivation_completes_and_resolves_MANUAL(
    paired_session: PairedSession,
) -> None:
    # covers: BP-1500d-1-i
    # angle: seam
    """MANUAL: shares the module-fixture pair of real builds (~20s
    amortised). THE AGREEMENT ENTRY -- the one this AC cannot be closed
    without. Performs the SAME two-step derivation
    ``check_build_drift.py``'s ``main()`` performs against layout B's
    record (comparison base from the stated position + the record's own
    directory, then the family prefix expressed back against that same
    directory), and asserts three things together: the derivation
    completes without raising; the derived key space actually matches the
    recorded names (the silent failure mode, since a dot-dot relative
    position does NOT raise); and the REAL reader, run as a subprocess
    against the real record, reports a verified count greater than zero."""
    sibling = paired_session.sibling
    manifest = sibling.load_manifest()
    package_root_raw = manifest.get("package_root")
    repo_root = sibling.target_root

    if package_root_raw is None:
        # Explicit unavailable: the reader must report unavailable too, not
        # clean and not drifted -- this is the boundary this AC's it_
        # requirements #4 assigns to check_build_drift.py's own contract,
        # asserted here as the "both halves unavailable together" case.
        proc = run_build_drift_reader(sibling.target_root)
        assert proc.returncode != 0, (
            "position is explicitly unavailable, but the real reader "
            f"reported a clean exit:\n{proc.stderr}"
        )
        assert "package_root" in proc.stderr and "null" in proc.stderr, (
            f"reader did not name the unavailable position as the reason "
            f"for its non-clean exit:\n{proc.stderr}"
        )
        return

    package_offset = package_root_raw or ""

    # FIRST -- the derivation completes. Mirrors check_build_drift.py's own
    # ``templates_base = (repo_root / package_offset) if package_offset
    # else repo_root`` followed by ``templates_dir.relative_to(repo_root)``
    # exactly. An absolute recorded position is the one case that raises.
    templates_base = (repo_root / package_offset) if package_offset else repo_root
    templates_dir = templates_base / "templates" / "agents"
    try:
        agents_prefix = templates_dir.relative_to(repo_root).as_posix()
    except ValueError as exc:
        pytest.fail(
            f"reader's own family_prefix derivation raised for an honest "
            f"sibling position {package_root_raw!r}: {exc}"
        )

    # SECOND -- the derived key space actually matches the recorded names.
    # This is the failure the crash-shaped reading of this defect misses: a
    # dot-dot relative position keeps the derivation lexically successful
    # but can still yield a key space the recorded names do not share.
    prefix_with_slash = agents_prefix.rstrip("/") + "/"
    string_valued_keys = [k for k, v in manifest.items() if isinstance(v, str)]
    matching_keys = [k for k in string_valued_keys if k.startswith(prefix_with_slash)]
    assert matching_keys, (
        f"derived family_prefix {agents_prefix!r} matches ZERO of the "
        f"{len(string_valued_keys)} recorded template-account keys -- an "
        "honest position paired with names in a different key space, the "
        "exact silent intermediate state this AC's agreement clause forbids."
    )

    # THIRD -- run the REAL reader (subprocess, the deployed hook) and
    # assert it actually accounts for the recorded names.
    proc = run_build_drift_reader(sibling.target_root)
    result_line = extract_result_line(proc.stderr)
    verified = parse_result_field(result_line, "verified")
    assert verified > 0, (
        f"real reader verified={verified} against layout B; the agreement "
        f"clause requires the derived key space to actually account for "
        f"the recorded names.\n{result_line}\nfull stderr:\n{proc.stderr}"
    )
    assert proc.returncode == 0, (
        f"expected a clean exit from the real reader against an intact, "
        f"agreeing record; got {proc.returncode}:\n{proc.stderr}"
    )


def test_bp_1500d_1_i_an_automated_caller_cannot_receive_the_unavailable_producing_end_as_the_same_answer_as_a_legitimate_same_directory_install_MANUAL(
    paired_session: PairedSession,
) -> None:
    # covers: BP-1500d-1-i
    # angle: real_artifact
    """MANUAL: shares the module-fixture pair of real builds (~20s
    amortised). DISTINGUISHABILITY. Parses the REAL bytes both builds
    serialized -- a cold on-disk read, never a hand-authored fixture -- and
    asserts the two records' producing-end descriptions are not equal to
    one another at the DATA level, reachable by a caller that never saw
    either build's console (every warning on this path is emitted at build
    time and gone by the time a pre-commit hook reads the record)."""
    same_dir_manifest = json.loads(
        paired_session.same_directory.manifest_path.read_text(encoding="utf-8")
    )
    sibling_manifest = json.loads(
        paired_session.sibling.manifest_path.read_text(encoding="utf-8")
    )

    same_dir_position = same_dir_manifest.get("package_root")
    sibling_position = sibling_manifest.get("package_root")

    assert same_dir_position == "", (
        f"layout A (genuinely same-directory) recorded position "
        f"{same_dir_position!r}, not the same-directory answer."
    )
    assert sibling_position != same_dir_position, (
        "layout A (genuinely same-directory) and layout B (genuinely "
        f"out-of-package) both recorded position {same_dir_position!r} -- "
        "an automated caller that reads only the data field cannot tell a "
        "legitimate same-directory install from layout B's answer."
    )

    same_dir_keys = template_account_keys(same_dir_manifest)
    sibling_keys = template_account_keys(sibling_manifest)
    assert same_dir_keys, "layout A's account must be non-empty to be a meaningful control"
    assert sibling_keys, "layout B's account must be non-empty for this comparison to mean anything"
    assert same_dir_keys != sibling_keys, (
        "layout A's and layout B's template-account key sets are IDENTICAL "
        "-- an implementation that emits the same producing-end description "
        "in both layouts would pass every other entry in this AC while "
        "failing the one property distinguishability actually requires."
    )


def test_bp_1500d_1_i_the_producing_end_description_is_written_by_the_real_build_command_line_from_outside_the_package_tree_MANUAL(
    paired_session: PairedSession,
) -> None:
    # covers: BP-1500d-1-i
    # angle: reachability
    """MANUAL: shares the module-fixture pair of real builds (~20s
    amortised). PRODUCTION ENTRY POINT. ``write_build_manifest`` and
    ``_relative_package_offset`` already accept both roots as parameters, so
    a direct-import test proves the writer CAN describe the producing end
    without proving a build DOES. Both layouts were invoked as the real
    ``python <pkg>/scripts/build.py --target-dir <dir>`` command line
    (subprocess, not an import); for the genuinely out-of-package sibling
    layout, an independent probe child process using the exact same
    (cwd, env) launch conditions confirms no path under the real producing
    package checkout is reachable via ``sys.path`` -- verified as a property
    of a real child, not assumed from how the env was constructed. Only
    then is the producing-end description asserted present in the record
    each child actually wrote."""
    same_dir = paired_session.same_directory
    sibling = paired_session.sibling

    for label, proc in (("same-directory", same_dir.proc), ("sibling", sibling.proc)):
        argv_str = " ".join(proc.args)
        assert "build.py" in argv_str, f"{label} layout: {argv_str}"
        assert "--target-dir" in proc.args, f"{label} layout: {proc.args}"

    real_package_str = str(REAL_PACKAGE_ROOT)
    sibling_argv_str = " ".join(sibling.proc.args)
    assert real_package_str not in sibling_argv_str, (
        "sibling build subprocess argv referenced the real producing "
        f"package checkout ({real_package_str}) rather than only its "
        "harness copy."
    )

    child_sys_path = probe_child_sys_path(
        cwd=sibling.target_root,
        env={k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"},
    )
    offending = [p for p in child_sys_path if real_package_str in p]
    assert not offending, (
        f"a child process launched with the sibling layout's own cwd/env "
        f"could still reach the real producing package checkout via "
        f"sys.path: {offending}"
    )

    same_dir_manifest = same_dir.load_manifest()
    sibling_manifest = sibling.load_manifest()
    assert "package_root" in same_dir_manifest, (
        "same-directory layout's record has no 'package_root' key at all "
        "-- the producing-end description never reached the record the "
        "real command line wrote."
    )
    assert "package_root" in sibling_manifest, (
        "sibling layout's record has no 'package_root' key at all -- the "
        "producing-end description never reached the record the real "
        "command line wrote."
    )


def test_bp_1500d_1_i_a_stated_producing_end_that_does_not_hold_is_reported_as_such_and_both_good_records_still_answer_correctly_afterwards_MANUAL(
    paired_session: PairedSession,
) -> None:
    # covers: BP-1500d-1-i
    # angle: failure
    """MANUAL: shares the module-fixture pair of real builds (~20s
    amortised); the five inspection runs themselves are fast file
    edits/reads. THE NEGATIVE CONTROL. Five runs over the SAME paired
    session: (1) both good records read clean via the real reader and give
    different position answers. (2) Layout B's position is set to a name
    with no real package copy, leaving the recorded template-account keys
    untouched (still prefixed with the REAL offset) -- the reader must
    report a non-clean, attributable failure (not the manifest-absent
    warn-and-exit-0 path, and not a silently-followed clean pass).
    (3) Restore; both good again, still different. (4) The position is left
    stated correctly but the account is emptied to nothing but metadata --
    the reader must report this as gaps (an account that could not be
    given), never as a clean comparison. (5) Restore; both good and still
    different. Runs 3 and 5 attribute each red to its own breakage rather
    than to an already-broken fixture."""
    same_dir = paired_session.same_directory
    sibling = paired_session.sibling

    original_sibling_bytes = sibling.manifest_path.read_bytes()
    original_sibling_manifest = json.loads(original_sibling_bytes)

    def _assert_both_good_and_different() -> None:
        same_dir_proc = run_build_drift_reader(same_dir.project_root)
        sibling_proc = run_build_drift_reader(sibling.target_root)
        assert same_dir_proc.returncode == 0, (
            f"layout A unexpectedly non-clean:\n{same_dir_proc.stderr}"
        )
        assert sibling_proc.returncode == 0, (
            f"layout B unexpectedly non-clean:\n{sibling_proc.stderr}"
        )
        same_dir_verified = parse_result_field(
            extract_result_line(same_dir_proc.stderr), "verified"
        )
        sibling_verified = parse_result_field(
            extract_result_line(sibling_proc.stderr), "verified"
        )
        assert same_dir_verified > 0
        assert sibling_verified > 0
        same_dir_position = same_dir.load_manifest().get("package_root")
        sibling_position = sibling.load_manifest().get("package_root")
        assert same_dir_position != sibling_position, (
            "both good records report the SAME producing-end position "
            f"({same_dir_position!r}) -- runs 1/3/5 require them to differ."
        )

    # Run 1 -- both good, clean, and different.
    _assert_both_good_and_different()

    # Run 2 -- layout B's stated position does not hold for the project it
    # sits in (a real, resolvable-looking offset that names no actual
    # package copy), while the recorded template-account keys are left
    # untouched under the REAL offset -- a genuine position/account
    # mismatch, not a crash.
    broken_position = dict(original_sibling_manifest)
    broken_position["package_root"] = "../a-package-that-was-never-built-here"
    sibling.manifest_path.write_text(json.dumps(broken_position), encoding="utf-8")
    try:
        broken_proc = run_build_drift_reader(sibling.target_root)
        assert broken_proc.returncode != 0, (
            f"run 2 (position does not hold) unexpectedly reported clean:\n"
            f"{broken_proc.stderr}"
        )
        result_line = extract_result_line(broken_proc.stderr)
        assert parse_result_field(result_line, "verified") == 0, (
            f"run 2 should report a description that does not hold -- "
            f"zero templates resolved via the broken position -- got: "
            f"{result_line}"
        )
        # Not the "absence of anything to describe" verdict either: that
        # path prints a WARNING about a missing manifest and exits 0, which
        # this must not match.
        assert "manifest not found" not in broken_proc.stderr, (
            f"run 2 was read as an absence of anything to describe, not as "
            f"a description that does not hold:\n{broken_proc.stderr}"
        )
    finally:
        # Run 3 -- restore, clean again (attribution: run 2's red was the
        # broken position, not an already-broken fixture).
        sibling.manifest_path.write_bytes(original_sibling_bytes)
    _assert_both_good_and_different()

    # Run 4 -- the position is left stated correctly, but the account of
    # the package's own files is replaced with nothing (only metadata keys
    # remain).
    emptied_account = {
        key: value
        for key, value in original_sibling_manifest.items()
        if key in MANIFEST_METADATA_KEYS
    }
    sibling.manifest_path.write_text(json.dumps(emptied_account), encoding="utf-8")
    try:
        emptied_proc = run_build_drift_reader(sibling.target_root)
        assert emptied_proc.returncode != 0, (
            f"run 4 (emptied account) unexpectedly reported clean:\n"
            f"{emptied_proc.stderr}"
        )
        result_line = extract_result_line(emptied_proc.stderr)
        gaps = parse_result_field(result_line, "gaps")
        drifted = parse_result_field(result_line, "drifted")
        assert gaps > 0, (
            f"run 4 must be reported as gaps (an account that could not be "
            f"given), never as a clean comparison: {result_line}"
        )
        assert drifted == 0, (
            f"run 4 emptied the account -- it must not be misreported as "
            f"in-place drift of templates that were never removed from "
            f"disk: {result_line}"
        )
    finally:
        # Run 5 -- restore, clean again.
        sibling.manifest_path.write_bytes(original_sibling_bytes)
    _assert_both_good_and_different()
