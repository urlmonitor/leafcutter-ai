"""
MODULE: test_bp_900g_8_i
GOAL: Prove the three edge shapes AC BP-900g-8-i names for the derived,
    transitive intra-package dependency closure BP-900g-8 introduced: a chain
    correct at its first hop and broken at its second, an out-of-package
    (stdlib / third-party / host-project) reference that must never be
    mistaken for a deploy gap, and -- the one shape BP-900g-8's own notes
    call "the acceptance test for 'derived'" -- a module added to the package
    AFTER the fact, with no manifest, list, or allowlist edited, which only a
    closure genuinely computed from the code (never an enumeration, however
    complete) can catch.
BUSINESS CONTEXT: BP-900g-8-i depends on BP-900g-8 and adds no new closure
    and no new harness -- it drives three surface shapes through the closure
    function and the deployed-tree harness BP-900g-8 delivers
    (compute_intra_package_closure /
    compute_intra_package_closure_with_deploy_root_relative in
    build_referential_integrity.py, and build.py's
    _check_intra_package_closure_guard preflight). Before this file, BP-900g-8
    itself was covered by 18 passing tests but none of them added a module
    inside a test run and left every manifest untouched -- so the specific
    claim "derived, not enumerated" was true by code inspection
    (compute_intra_package_closure re-parses the tree with ast on every call)
    but had never been demonstrated. BP-900g-8's 2026-09-01 amendment records
    this explicitly: "the missing decisive test (the newly-added-module case
    named in BP-900g-8-i) is reported as a recommendation for human judgement,
    not acted on." This file acts on it.
ARCHITECTURE: Four tests, matching BP-900g-8-i's test_spec table.
    (1) boundary -- a chain A -> B -> C where B is declared/deployed but C is
    not: the build must fail naming C, not just A, proving the closure does
    not stop at the first hop.
    (2) boundary -- an out-of-package false-positive control: a deployed
    script that reads a stdlib module, a third-party distribution, and a
    host-project-style path (the ``debugging/scripts/...`` form BP-900g-4
    mis-normalised and BP-900g-5 had to narrow a prefix to exclude) must
    produce zero findings and a zero-exit build.
    (3) reachability + must_block -- THE decisive test. A module is written
    into the package tree inside the test and an already-deployed script is
    made to resolve it; no manifest, list, or allowlist is edited. The build
    must either deploy the new module or fail naming it -- a zero-exit build
    that silently omits it is the one outcome that proves the closure is
    still reading a list, and is a failure of this test.
    (4) deployed -- re-inspects the produced TARGET DIRECTORIES from the same
    three shapes (never build_phases.py's text) to confirm the guard's
    preflight-before-any-write property: an aborted build leaves nothing
    partially deployed, and the out-of-package script's harmless references
    (stdlib, third-party, host-project path) never manifest as sibling files
    in the deployed tree.

    All four reuse BP-900g-8's proven pattern: a ``shutil.copytree`` scratch
    copy of the whole package (never this worktree's own tracked
    scripts/build_phases.py -- a ``finally``-block restore does not survive
    the test process being killed) driven by the real
    `python <scratch>/scripts/build.py --target-dir <tmp>` subprocess.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup -- make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_referential_integrity as _bri  # noqa: E402 -- after sys.path setup

# Reused, proven scratch-package builder -- the same helper BP-900g-8's own
# unit_tests/test_bp_900g_8.py and unit_tests/test_bp_900g_9.py already use,
# rather than a fourth private copy of the same fixture.
_SYNTHETIC_PACKAGE_HELPER_PATH = (
    _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
)
_SCRATCH_BUILD_SUBPROCESS_TIMEOUT_SECONDS = 300

_DEPLOY_MAP_ANCHOR = "AC_STORE_DEPLOY_MAP: tuple[tuple[str, str], ...] = (\n"


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from test_bp_100k_2.py.

    Never imported as a bare ``test_bp_100k_2`` module name, so this does not
    collide with pytest's own collection of that file.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp900g8i_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


def _run_build_in_scratch_pkg(pkg_root: Path, target: Path) -> subprocess.CompletedProcess[str]:
    """Run ``<pkg_root>/scripts/build.py`` as a subprocess against *target*.

    Never touches this worktree's own tracked ``scripts/build_phases.py`` --
    all mutation happens on the ``shutil.copytree`` scratch copy so a killed
    test process leaves nothing tracked mutated on disk.
    """
    return subprocess.run(
        [sys.executable, str(pkg_root / "scripts" / "build.py"), "--target-dir", str(target)],
        capture_output=True,
        text=True,
        timeout=_SCRATCH_BUILD_SUBPROCESS_TIMEOUT_SECONDS,
        cwd=str(pkg_root),
    )


def _find_output_root(target_dir: Path) -> Path | None:
    """Return the deployed output root inside *target_dir*, or None if absent.

    Unlike BP-900g-8's sibling helper of the same name, returns None instead
    of asserting -- a preflight-aborted build in this file's test 1 and test 3
    (undeployed-outcome branch) legitimately leaves no output root at all, and
    that absence is itself part of what test 4 asserts on.
    """
    candidates = [
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    ] if target_dir.is_dir() else []
    if len(candidates) == 0:
        return None
    assert len(candidates) == 1, (
        f"Expected at most one deployed output root under {target_dir}; found "
        f"{[p.name for p in candidates]}."
    )
    return candidates[0]


def _inject_deploy_map_entry(build_phases_text: str, source_rel: str, dest_name: str) -> str:
    """Return *build_phases_text* with one extra AC_STORE_DEPLOY_MAP entry declared.

    Mirrors the injection-not-deletion anchor pattern established in
    unit_tests/test_bp_900g_9.py's three-entry test -- appending after the
    tuple's opening line rather than hand-authoring a full replacement.
    """
    assert _DEPLOY_MAP_ANCHOR in build_phases_text, (
        "AC_STORE_DEPLOY_MAP's opening-line anchor was not found -- the "
        "declaration's literal form changed and this fixture can no longer "
        "inject an entry into it (AC BP-900g-8-i)."
    )
    injected_line = f'    ("{source_rel}", "{dest_name}"),\n'
    return build_phases_text.replace(_DEPLOY_MAP_ANCHOR, _DEPLOY_MAP_ANCHOR + injected_line, 1)


# ---------------------------------------------------------------------------
# Test 1 -- angle: boundary. Second hop: A -> B (declared) -> C (undeclared).
# ---------------------------------------------------------------------------


def test_bp_900g_8_i_second_hop_missing_dependency_fails_the_build_naming_the_inner_module(
    tmp_path: Path,
) -> None:
    """A closure that stops at the first hop passes this test's setup and fails the assertion.

    scan_ac_store.py (already deployed) is made to import a new sibling B,
    which in turn imports a second new sibling C. B is added to the deploy
    declaration; C deliberately is not. The build must fail naming C -- the
    module actually missing -- not merely B or scan_ac_store.py, or an author
    fixing the wrong hop is the observable consequence.
    """
    # covers: BP-900g-8-i
    build_synthetic_full_package = _load_build_synthetic_full_package()
    pkg_root = build_synthetic_full_package(tmp_path / "workspace")

    ac_store_dir = pkg_root / "scripts" / "ac_store"
    (ac_store_dir / "_bp900g8i_dep_c.py").write_text(
        "BP900G8I_MARKER_C = 'second-hop-leaf'\n", encoding="utf-8"
    )
    (ac_store_dir / "_bp900g8i_dep_b.py").write_text(
        "import _bp900g8i_dep_c  # BP-900g-8-i: second-hop fixture\n", encoding="utf-8"
    )
    scan_ac_store = ac_store_dir / "scan_ac_store.py"
    scan_ac_store.write_text(
        "import _bp900g8i_dep_b  # BP-900g-8-i: first-hop fixture\n"
        + scan_ac_store.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    scratch_build_phases = pkg_root / "scripts" / "build_phases.py"
    original_text = scratch_build_phases.read_text(encoding="utf-8")
    scratch_build_phases.write_text(
        _inject_deploy_map_entry(
            original_text, "scripts/ac_store/_bp900g8i_dep_b.py", "_bp900g8i_dep_b.py"
        ),
        encoding="utf-8",
    )
    # C is deliberately NEVER declared -- that is the second, broken hop.

    target_dir = tmp_path / "second_hop_target"
    result = _run_build_in_scratch_pkg(pkg_root, target_dir)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "build.py exited 0 with a second-hop dependency (_bp900g8i_dep_c.py, "
        f"resolved only via _bp900g8i_dep_b.py) undeclared.\n{combined}\n"
        "(AC BP-900g-8-i)."
    )
    assert "_bp900g8i_dep_c.py" in combined, (
        "The build failure did not name the INNER, second-hop module "
        f"'_bp900g8i_dep_c.py' -- a closure that stops at depth 1 would name "
        f"only '_bp900g8i_dep_b.py' instead, which is the exact failure this "
        f"test exists to catch.\nOutput:\n{combined}\n(AC BP-900g-8-i)."
    )


# ---------------------------------------------------------------------------
# Test 2 -- angle: boundary. Out-of-package false-positive control.
# ---------------------------------------------------------------------------


def test_bp_900g_8_i_out_of_package_modules_produce_no_finding(tmp_path: Path) -> None:
    """A deployed script referencing stdlib, third-party, and a host-project path must be clean.

    Adds all three out-of-package reference shapes to an already-deployed
    script and asserts a zero-exit build. A closure that demands the build
    ship the standard library, an installed distribution, or a path the
    consumer's own repository owns acquires an allowlist within a week --
    which is the hand-maintained list this whole feature exists to remove.
    """
    # covers: BP-900g-8-i
    build_synthetic_full_package = _load_build_synthetic_full_package()
    pkg_root = build_synthetic_full_package(tmp_path / "workspace")

    scan_ac_store = pkg_root / "scripts" / "ac_store" / "scan_ac_store.py"
    probe = (
        "\n\n"
        "# BP-900g-8-i out-of-package probe: stdlib, third-party, host-project path.\n"
        "import base64  # stdlib -- must never be treated as an intra-package dependency\n"
        "import yaml  # third-party (already a real dependency of this file) -- ditto\n"
        "\n\n"
        "def _bp900g8i_host_project_path_probe() -> str:\n"
        "    # A host-project path of the exact form BP-900g-4 mis-normalised and\n"
        "    # BP-900g-5 narrowed a prefix to exclude -- belongs to the CONSUMER's\n"
        "    # own repository, never to this package.\n"
        "    return open('debugging/scripts/check/prod_status_check.py').read()\n"
    )
    scan_ac_store.write_text(
        scan_ac_store.read_text(encoding="utf-8") + probe, encoding="utf-8"
    )

    # Unit-level half: the closure computed directly from the mutated script
    # must not contain the stdlib module, the third-party module, or the
    # host-project path -- non-existence under root is the sole
    # internal/external discriminator (no allowlist), so all three are
    # expected to be silently absent from Set A itself.
    closure = _bri.compute_intra_package_closure(scan_ac_store, pkg_root)
    for external_name in ("base64", "base64.py", "yaml", "yaml.py",
                           "debugging/scripts/check/prod_status_check.py"):
        assert external_name not in closure, (
            f"compute_intra_package_closure() included {external_name!r} in the "
            f"closure of a script that merely references it as stdlib, "
            f"third-party, or a host-project path. Closure: {sorted(closure)!r} "
            "(AC BP-900g-8-i)."
        )

    # Integration half: the same three references must not abort a real build.
    target_dir = tmp_path / "clean_target"
    result = _run_build_in_scratch_pkg(pkg_root, target_dir)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        "build.py --target-dir exited "
        f"{result.returncode!r} over a script whose only new references are "
        "stdlib, third-party, and a host-project path -- none of which this "
        f"package owns or ships.\nOutput:\n{combined}\n(AC BP-900g-8-i)."
    )
    assert "base64" not in combined and "prod_status_check" not in combined, (
        "The clean build's own output unexpectedly named one of the "
        f"out-of-package probes as a finding.\nOutput:\n{combined}\n"
        "(AC BP-900g-8-i)."
    )


# ---------------------------------------------------------------------------
# Test 3 -- angle: reachability, must_block. THE decisive "derived, not
# enumerated" test.
# ---------------------------------------------------------------------------


def test_bp_900g_8_i_newly_added_module_is_covered_with_no_manifest_edit(
    tmp_path: Path,
) -> None:
    """A module added to the package AFTER the fact, with zero manifest edits, must not slip past.

    This is the one test BP-900g-8's own notes name as unfakeable: every other
    clause of the closure guard can be satisfied by a sufficiently complete,
    hand-authored enumeration written today. This one cannot, because the
    module is written into the tree from inside the test itself and no list,
    map, or allowlist is edited before the build runs. A zero-exit build that
    silently ships without the new module is the one outcome that proves the
    closure is still reading a list -- and is a failure of this test, not a
    pass.
    """
    # covers: BP-900g-8-i
    build_synthetic_full_package = _load_build_synthetic_full_package()
    pkg_root = build_synthetic_full_package(tmp_path / "workspace")

    new_module_name = "_bp900g8i_newly_added_module.py"
    new_module = pkg_root / "scripts" / "ac_store" / new_module_name
    new_module.write_text(
        "BP900G8I_NEWLY_ADDED_MARKER = 'derived-not-enumerated'\n", encoding="utf-8"
    )

    scan_ac_store = pkg_root / "scripts" / "ac_store" / "scan_ac_store.py"
    scan_ac_store.write_text(
        f"import {new_module_name[:-3]}  # BP-900g-8-i: newly-added-module fixture\n"
        + scan_ac_store.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    # THE point of this test: no manifest, list, or allowlist is touched below.
    # scripts/build_phases.py is left byte-for-byte as the scratch copy built it.

    target_dir = tmp_path / "newly_added_target"
    result = _run_build_in_scratch_pkg(pkg_root, target_dir)
    combined = result.stdout + result.stderr

    output_root = _find_output_root(target_dir)
    deployed_new_module = (
        (output_root / "scripts" / "ac_store" / new_module_name)
        if output_root is not None
        else None
    )
    module_actually_deployed = deployed_new_module is not None and deployed_new_module.is_file()

    if result.returncode == 0:
        assert module_actually_deployed, (
            "build.py exited 0 after a brand-new module "
            f"({new_module_name}) was added to the package tree and resolved "
            "by an already-deployed script, with NO manifest, list, or "
            "allowlist edited -- and the new module is ABSENT from the "
            "produced tree. This is the one outcome the AC forbids: a run in "
            "which the new module is silently ignored means the closure is "
            "still reading a hand-maintained list, not deriving from the "
            f"code.\nOutput:\n{combined}\n(AC BP-900g-8-i)."
        )
    else:
        assert new_module_name in combined, (
            "build.py aborted, but its failure output did not name the "
            f"newly-added module '{new_module_name}' -- the closure noticed "
            "SOMETHING was wrong without being able to say what, which is not "
            f"the derived-and-actionable failure the AC requires.\n"
            f"Output:\n{combined}\n(AC BP-900g-8-i)."
        )


# ---------------------------------------------------------------------------
# Test 4 -- angle: deployed. Re-inspect the PRODUCED TARGET DIRECTORIES from
# all three shapes above -- never build_phases.py's text.
# ---------------------------------------------------------------------------


def test_bp_900g_8_i_all_three_shapes_asserted_against_the_produced_target_tree(
    tmp_path: Path,
) -> None:
    """Re-run all three shapes and inspect the produced target directories directly.

    Tests 1-3 already assert on subprocess stdout/stderr, which is itself
    output produced by running against a real target -- but this entry pins
    the assertion surface the AC's last clause disqualifies any alternative
    to: reading build_phases.py's text and agreeing with it. Every assertion
    here is a filesystem check against a directory `build.py` actually wrote
    (or, for an aborted build, provably did NOT write to), never a check of
    the deploy declaration's source.
    """
    # covers: BP-900g-8-i
    build_synthetic_full_package = _load_build_synthetic_full_package()

    # Shape 1 re-run: second-hop-missing must leave the target UNWRITTEN --
    # the preflight guard runs before _run_phases(), so an aborted build must
    # produce no output root at all, not a partially-populated one.
    pkg_root_1 = build_synthetic_full_package(tmp_path / "workspace_hop")
    ac_store_dir_1 = pkg_root_1 / "scripts" / "ac_store"
    (ac_store_dir_1 / "_bp900g8i_dep_c.py").write_text("C = 1\n", encoding="utf-8")
    (ac_store_dir_1 / "_bp900g8i_dep_b.py").write_text(
        "import _bp900g8i_dep_c\n", encoding="utf-8"
    )
    scan_1 = ac_store_dir_1 / "scan_ac_store.py"
    scan_1.write_text(
        "import _bp900g8i_dep_b\n" + scan_1.read_text(encoding="utf-8"), encoding="utf-8"
    )
    build_phases_1 = pkg_root_1 / "scripts" / "build_phases.py"
    build_phases_1.write_text(
        _inject_deploy_map_entry(
            build_phases_1.read_text(encoding="utf-8"),
            "scripts/ac_store/_bp900g8i_dep_b.py",
            "_bp900g8i_dep_b.py",
        ),
        encoding="utf-8",
    )
    hop_target = tmp_path / "hop_target"
    result_1 = _run_build_in_scratch_pkg(pkg_root_1, hop_target)
    assert result_1.returncode != 0, "Shape 1 (second hop) unexpectedly built clean."
    assert _find_output_root(hop_target) is None, (
        "The second-hop-missing build aborted (non-zero exit) but still left an "
        f"output root under {hop_target}. The preflight guard must abort BEFORE "
        "any output is written, or an aborted build could still ship a partial, "
        "silently-incomplete deploy (AC BP-900g-8-i)."
    )

    # Shape 2 re-run: out-of-package references must never manifest as
    # sibling files in the DEPLOYED tree.
    pkg_root_2 = build_synthetic_full_package(tmp_path / "workspace_ext")
    scan_2 = pkg_root_2 / "scripts" / "ac_store" / "scan_ac_store.py"
    scan_2.write_text(
        scan_2.read_text(encoding="utf-8")
        + "\nimport base64\n"
        + "\ndef _probe() -> str:\n"
        + "    return open('debugging/scripts/check/prod_status_check.py').read()\n",
        encoding="utf-8",
    )
    ext_target = tmp_path / "ext_target"
    result_2 = _run_build_in_scratch_pkg(pkg_root_2, ext_target)
    assert result_2.returncode == 0, "Shape 2 (out-of-package) unexpectedly failed to build."
    ext_output_root = _find_output_root(ext_target)
    assert ext_output_root is not None, "Shape 2's clean build produced no output root."
    deployed_ac_store_dir = ext_output_root / "scripts" / "ac_store"
    deployed_names = {p.name for p in deployed_ac_store_dir.iterdir()} if deployed_ac_store_dir.is_dir() else set()
    for forbidden in ("base64.py", "prod_status_check.py", "debugging"):
        assert forbidden not in deployed_names, (
            f"The deployed scripts/ac_store/ tree unexpectedly contains "
            f"{forbidden!r}: {sorted(deployed_names)!r}. An out-of-package "
            "reference must never manifest as a deployed sibling file "
            "(AC BP-900g-8-i)."
        )

    # Shape 3 re-run: the decisive case, re-checked purely against the
    # produced tree (no log-text assertion here at all).
    pkg_root_3 = build_synthetic_full_package(tmp_path / "workspace_new")
    new_name = "_bp900g8i_newly_added_module.py"
    (pkg_root_3 / "scripts" / "ac_store" / new_name).write_text("D = 1\n", encoding="utf-8")
    scan_3 = pkg_root_3 / "scripts" / "ac_store" / "scan_ac_store.py"
    scan_3.write_text(
        f"import {new_name[:-3]}\n" + scan_3.read_text(encoding="utf-8"), encoding="utf-8"
    )
    new_target = tmp_path / "new_target"
    result_3 = _run_build_in_scratch_pkg(pkg_root_3, new_target)
    new_output_root = _find_output_root(new_target)
    if result_3.returncode == 0:
        assert new_output_root is not None, (
            "Shape 3's build exited 0 but produced no output root at all -- "
            "cannot verify the new module was deployed (AC BP-900g-8-i)."
        )
        deployed_new = new_output_root / "scripts" / "ac_store" / new_name
        assert deployed_new.is_file(), (
            f"Shape 3's build exited 0 and {new_name} is ABSENT from the "
            f"produced tree at {deployed_new} -- the exact silently-dropped "
            "outcome this AC forbids (AC BP-900g-8-i)."
        )
    else:
        assert new_output_root is None, (
            "Shape 3's build aborted (non-zero exit) but still left a "
            f"populated output root under {new_target} -- an aborted build "
            "must not leave a partial deploy (AC BP-900g-8-i)."
        )
