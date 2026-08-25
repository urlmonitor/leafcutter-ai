"""
MODULE: test_bp_900g_8
GOAL: Regression + specification tests for the derived, transitive intra-package
    dependency closure that BP-900g-8 introduces. Before this fix, a deployed
    script's own sibling-module dependencies were checked (if at all) via a
    hand-maintained deploy_map list, so a sibling added to the source tree could
    silently fail to ship -- exactly what happened to
    scripts/ac_store/generate_ticket_from_ac.py, which resolves
    scripts/ac_store/_component_migration_map.py via
    importlib.util.spec_from_file_location at import time, while build_ac_store's
    deploy_map (scripts/build_phases.py) never deployed the sibling. That gap is
    invisible in every SOURCE-tree check (the source tree has every module by
    construction) and does not even crash the deployed process for this specific
    script -- _load_migration_map's except clause swallows the missing sibling
    into a "Cannot load MIGRATION_MAP" WARNING and silently degrades. Only a
    DEPLOYED-tree, code-derived closure check can catch it.
BUSINESS CONTEXT: AC BP-900g-8. Three sets are in play (see the ticket's
    config_schema_fragment): Set A (resolved_closure) is the transitive set of
    intra-package modules a deployed script actually resolves, DERIVED from the
    code; Set B (deploy_declaration) is the existing hand-authored deploy_map;
    Set C (guard_manifest) is the guard's model of what has been deployed. The
    binding-direction rule requires B to CONTAIN closure(A) at build time, and
    forbids satisfying this AC merely by adding the one known-missing file to B
    (necessary, not sufficient) -- the closure computation and the build-time
    containment check are the actual deliverable.
ARCHITECTURE: Four tests, matching the ticket's Test Requirements table exactly.
    (1) A pure unit-level test of the closure computation + containment-check
    functions this ticket introduces in build_referential_integrity.py, using a
    SYNTHETIC withheld-declaration set so the assertion is independent of
    whatever the real (post-fix) deploy_map ends up looking like.
    (2) A must_block/reachability test: withholds the sibling from the deploy_map
    ON DISK, runs `python scripts/build.py --target-dir <tmp>` as a real
    subprocess and asserts it fails naming the script/dependency/phase, then
    restores the source and re-runs the SAME command for the positive control.
    (3) A deployed-tree test: runs the real build into a temp target, then
    resolves the closure of EVERY deployed .py script against that DEPLOYED
    tree (not the source tree), asserting every resolved dependency is present.
    (4) A real-artifact test: runs the DEPLOYED generate_ticket_from_ac.py in a
    genuinely fresh subprocess (no inherited PYTHONPATH, cwd outside the source
    tree) and asserts it does not merely avoid crashing (which it already does,
    via graceful degradation) but that its sibling module actually LOADS --
    the "Cannot load MIGRATION_MAP" WARNING is the observable proof of the gap.

None of `compute_intra_package_closure` / `find_uncovered_closure_dependencies`
exist yet in build_referential_integrity.py as of this writing -- tests 1 and 3
are expected to fail with AttributeError until python-coder implements them.
Tests 2 and 4 exercise the real, currently-unguarded build.py / deployed script
and are expected to fail on assertions (not import errors).
"""

from __future__ import annotations

import os
import re
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

import build as _build  # noqa: E402 -- after sys.path setup
import build_referential_integrity as _bri  # noqa: E402 -- after sys.path setup


def _find_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* -- the dir holding scripts/.

    Mirrors the helper in test_bp_900g_4.py: the build deploys scripts to
    exactly one output root (e.g. ``.leafcutter/``) under the target directory.
    """
    candidates = sorted(
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} (a directory "
        f"containing a 'scripts/' subdirectory); found {[p.name for p in candidates]}."
    )
    return candidates[0]


# ---------------------------------------------------------------------------
# Test 1 -- angle: criterion. Pure unit test of the closure computation and the
# containment/coverage check, using a SYNTHETIC withheld declaration.
# ---------------------------------------------------------------------------


def test_bp_900g_8_derived_closure_includes_the_sibling_the_deploy_map_omits():
    """AC-1 (resolving a same-package module) + AC-2 (dependency coverage check)
    + AC-3 (derived from the code, never a hand-maintained list).

    Computes the closure for the REAL scripts/ac_store/generate_ticket_from_ac.py
    from the code (static analysis of its importlib.util.spec_from_file_location
    sibling load), and asserts _component_migration_map.py is in it. Then checks
    coverage against a SYNTHETIC declared set that withholds the sibling (the
    live state at HEAD 339b0981c cited by this AC's Gherkin), independent of
    whatever the real build_ac_store deploy_map contains after this ticket's fix
    -- because adding the one file to the deploy_map is necessary but the AC
    explicitly forbids treating it as sufficient.
    """
    # covers: BP-900g-8
    script = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"

    closure = _bri.compute_intra_package_closure(script, _REPO_ROOT)

    assert "scripts/ac_store/_component_migration_map.py" in closure, (
        "compute_intra_package_closure() did not include "
        "'scripts/ac_store/_component_migration_map.py' in the closure of "
        f"generate_ticket_from_ac.py. Closure: {sorted(closure)!r}. "
        "generate_ticket_from_ac.py resolves this sibling via "
        "importlib.util.spec_from_file_location at import time (module-level "
        "assignment _COMPONENT_MIGRATION_MAP = _load_migration_map()); a closure "
        "computed from the code, not a list, must see this (AC BP-900g-8)."
    )

    # Withhold the sibling from a synthetic declared set -- this is the exact
    # gap the AC's Gherkin narrates, regardless of what the real deploy_map
    # contains once this ticket's fix lands.
    declared_without_sibling = closure - {
        "scripts/ac_store/_component_migration_map.py"
    }

    uncovered = _bri.find_uncovered_closure_dependencies(
        "scripts/ac_store/generate_ticket_from_ac.py",
        _REPO_ROOT,
        declared_without_sibling,
    )

    assert "scripts/ac_store/_component_migration_map.py" in uncovered, (
        "find_uncovered_closure_dependencies() did not report "
        "'scripts/ac_store/_component_migration_map.py' as uncovered when the "
        f"declared set withheld it. Uncovered: {sorted(uncovered)!r}. The "
        "containment check (Set B must contain closure(Set A)) must flag a "
        "withheld dependency, not silently accept it (AC BP-900g-8)."
    )

    # Non-vacuity guard: a declared set that DOES include the sibling must NOT
    # be reported as uncovered -- otherwise this check would fail every build,
    # which is exactly the "wearing the word derived" failure mode the AC warns
    # against for an over-eager check.
    declared_with_sibling = set(closure)
    still_uncovered = _bri.find_uncovered_closure_dependencies(
        "scripts/ac_store/generate_ticket_from_ac.py",
        _REPO_ROOT,
        declared_with_sibling,
    )
    assert "scripts/ac_store/_component_migration_map.py" not in still_uncovered, (
        "find_uncovered_closure_dependencies() reported "
        "'scripts/ac_store/_component_migration_map.py' as uncovered even when "
        f"the declared set explicitly included it. Uncovered: "
        f"{sorted(still_uncovered)!r} (AC BP-900g-8)."
    )


# ---------------------------------------------------------------------------
# Test 2 -- angle: reachability. must_block + paired positive control, both
# through the SAME production entry point (python scripts/build.py).
# ---------------------------------------------------------------------------


def test_bp_900g_8_build_subprocess_blocks_when_a_resolved_dependency_is_withheld_from_the_deploy(  # noqa: E501
    tmp_path: Path,
) -> None:
    """AC-2 (build exits non-zero naming script/dependency/phase) + AC-5
    (real subprocess demonstration with a negative control).

    Temporarily removes any build_ac_store deploy_map line that ships
    _component_migration_map.py (a no-op today, since HEAD 339b0981c never
    declared it -- the pre-fix state already IS the withheld state), runs the
    REAL `python scripts/build.py --target-dir <tmp>` as a subprocess, and
    asserts non-zero exit naming the deployed script, the missing dependency,
    and the build_ac_store phase. The source file is always restored in a
    ``finally`` block. The SAME command is then run again, unmodified, and must
    exit zero -- a positive-path build alone cannot distinguish a working guard
    from an absent one.
    """
    # covers: BP-900g-8
    build_phases_path = _REPO_ROOT / "scripts" / "build_phases.py"
    build_py_path = _REPO_ROOT / "scripts" / "build.py"
    original_text = build_phases_path.read_text(encoding="utf-8")

    # Matches a single-line deploy_map tuple entry referencing the sibling, e.g.
    #   (ac_store_src / "_component_migration_map.py", "_component_migration_map.py"),
    # -- the style every other deploy_map entry in build_ac_store() already uses.
    # Pre-fix, this matches nothing (the entry does not exist yet), which
    # correctly represents the withheld state the AC's Gherkin narrates.
    withhold_re = re.compile(
        r"^[ \t]*\([^\n]*_component_migration_map\.py[^\n]*\),?[ \t]*$",
        re.MULTILINE,
    )
    withheld_text = withhold_re.sub("", original_text)

    try:
        build_phases_path.write_text(withheld_text, encoding="utf-8")

        withheld_target = tmp_path / "withheld_target"
        withheld_target.mkdir()
        result = subprocess.run(
            [sys.executable, str(build_py_path), "--target-dir", str(withheld_target)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(_REPO_ROOT),
        )
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "build.py --target-dir exited 0 while a resolved intra-package "
            "dependency (_component_migration_map.py, resolved by "
            "generate_ticket_from_ac.py) was withheld from the build_ac_store "
            f"deploy declaration.\nstdout:\n{result.stdout}\nstderr:\n"
            f"{result.stderr}\n(AC BP-900g-8)."
        )
        assert "generate_ticket_from_ac.py" in combined, (
            "build.py's failure output did not name the deployed script "
            f"'generate_ticket_from_ac.py'. Output:\n{combined} (AC BP-900g-8)."
        )
        assert "_component_migration_map.py" in combined, (
            "build.py's failure output did not name the missing dependency "
            f"'_component_migration_map.py'. Output:\n{combined} (AC BP-900g-8)."
        )
        assert "build_ac_store" in combined, (
            "build.py's failure output did not name the deploy phase "
            "'build_ac_store' that would have to carry the missing dependency. "
            f"Output:\n{combined} (AC BP-900g-8)."
        )
    finally:
        build_phases_path.write_text(original_text, encoding="utf-8")

    # Positive control: the SAME command against the UNMODIFIED tree must exit 0.
    clean_target = tmp_path / "clean_target"
    clean_target.mkdir()
    result2 = subprocess.run(
        [sys.executable, str(build_py_path), "--target-dir", str(clean_target)],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(_REPO_ROOT),
    )
    assert result2.returncode == 0, (
        "build.py --target-dir exited "
        f"{result2.returncode!r} against the UNMODIFIED source tree; expected 0. "
        f"stdout:\n{result2.stdout}\nstderr:\n{result2.stderr}\n(AC BP-900g-8). "
        "A positive-path build alone cannot prove the guard works, but a "
        "negative-path failure alone cannot prove the guard is not simply always "
        "failing -- both halves through the same command are required."
    )


# ---------------------------------------------------------------------------
# Test 3 -- angle: deployed. Resolve against the DEPLOYED tree, not source.
# ---------------------------------------------------------------------------


def test_bp_900g_8_deployed_tree_contains_the_full_closure_of_every_deployed_script(
    tmp_path: Path,
) -> None:
    """AC-2 (dependency deployed) + AC-4 (transitive) + AC-5 (deployed, not source).

    Runs the real build.py into a temp target, then for EVERY deployed .py
    script under ``<output_root>/scripts/``, computes its closure via
    ``compute_intra_package_closure`` rooted at the DEPLOYED tree, and asserts
    every resolved dependency exists in that same deployed tree. Checking
    against the source tree cannot fail here by construction (BP-811
    copy-tier vs. reachability-tier distinction) -- only a deployed-tree check
    can.
    """
    # covers: BP-900g-8
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. The "
        "deployed-tree closure assertion below cannot run against a failed build."
    )

    output_root = _find_output_root(target_dir)
    scripts_dir = output_root / "scripts"
    assert scripts_dir.is_dir(), f"No deployed scripts/ directory found under {output_root}."

    deployed_scripts = sorted(p for p in scripts_dir.rglob("*.py") if p.is_file())
    assert deployed_scripts, "No deployed .py scripts found -- nothing to check (AC BP-900g-8)."

    # Non-vacuity guard: the live gap this AC cites must actually be represented
    # in the scanned set, or this test could pass while checking nothing real.
    generate_ticket = scripts_dir / "ac_store" / "generate_ticket_from_ac.py"
    assert generate_ticket in deployed_scripts, (
        "generate_ticket_from_ac.py was not found under the deployed scripts "
        f"directory {scripts_dir}. Deployed: "
        f"{[p.relative_to(output_root).as_posix() for p in deployed_scripts]!r} "
        "(AC BP-900g-8)."
    )

    missing: list[str] = []
    for script in deployed_scripts:
        closure = _bri.compute_intra_package_closure(script, output_root)
        for dep in closure:
            if not (output_root / dep).is_file():
                missing.append(f"{script.relative_to(output_root).as_posix()} -> {dep}")

    assert not missing, (
        f"{len(missing)} deployed script(s) resolve an intra-package dependency "
        "that is NOT present in the DEPLOYED tree:\n  "
        + "\n  ".join(sorted(missing))
        + "\nThis is checked against the DEPLOYED tree, not the source tree -- "
        "the source tree contains every module by construction and is "
        "structurally blind to a missing deploy phase (AC BP-900g-8)."
    )


# ---------------------------------------------------------------------------
# Test 4 -- angle: real_artifact. Fresh cold-import subprocess of the DEPLOYED
# copy, with the source tree off sys.path.
# ---------------------------------------------------------------------------


def test_bp_900g_8_deployed_generate_ticket_cold_imports_in_a_fresh_subprocess(
    tmp_path: Path,
) -> None:
    """AC-5: the demonstration must exercise the DEPLOYED copy in a fresh subprocess.

    Runs the real build into a temp target, then executes the DEPLOYED
    generate_ticket_from_ac.py with ``--help`` in a genuinely fresh ``python``
    subprocess: a minimal environment (no inherited PYTHONPATH) and a cwd
    outside the package source tree, so nothing but the deployed tree itself
    can satisfy its imports. importlib.reload is deliberately NOT used here --
    it re-executes inside an already-populated namespace and masks cold-import
    failures (the GenReviewFixes H-2 lesson cited by this AC).

    Exit-0 alone is NOT sufficient evidence: ``_load_migration_map``'s except
    clause already swallows a missing sibling into a "Cannot load
    MIGRATION_MAP" WARNING rather than crashing the process, so an exit-0-only
    assertion would pass even at HEAD 339b0981c with the sibling absent. The
    WARNING-absence assertion below is the one that actually goes red for the
    live gap this AC cites.
    """
    # covers: BP-900g-8
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"build.py --target-dir exited {exit_code!r}; expected 0."

    output_root = _find_output_root(target_dir)
    deployed_script = output_root / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
    assert deployed_script.is_file(), f"{deployed_script} was not deployed."

    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    fresh_cwd = tmp_path / "fresh_cwd"
    fresh_cwd.mkdir()

    result = subprocess.run(
        [sys.executable, str(deployed_script), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(fresh_cwd),
        env=clean_env,
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 0, (
        "The deployed generate_ticket_from_ac.py did not reach its entry point "
        f"in a fresh subprocess.\nexit={result.returncode}\n{combined}\n"
        "(AC BP-900g-8)."
    )
    assert "ModuleNotFoundError" not in combined, (
        "The deployed generate_ticket_from_ac.py raised ModuleNotFoundError in a "
        f"fresh subprocess:\n{combined}\n(AC BP-900g-8)."
    )
    assert "Cannot load MIGRATION_MAP" not in combined, (
        "The deployed generate_ticket_from_ac.py logged 'Cannot load "
        "MIGRATION_MAP from ...' -- proof that its sibling "
        "_component_migration_map.py did not load from the DEPLOYED tree in a "
        f"fresh subprocess. Output:\n{combined}\n(AC BP-900g-8)."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-25 [test-writer/BP-900g-8]: Initial red-baseline test authoring.
#   Introduces the expected contract for two new functions in
#   build_referential_integrity.py -- compute_intra_package_closure() and
#   find_uncovered_closure_dependencies() -- neither of which exists yet
#   (tests 1 and 3 fail with AttributeError). Tests 2 and 4 exercise the real,
#   currently-unguarded scripts/build.py and the currently-silently-degrading
#   scripts/ac_store/generate_ticket_from_ac.py and fail on assertions, not
#   import errors. Test 2 mutates scripts/build_phases.py on disk within a
#   try/finally to simulate withholding the one dependency this AC's Gherkin
#   names as the live gap (at HEAD 339b0981c the deploy_map entry does not
#   exist at all, so the withheld state is the pre-fix baseline itself); the
#   removal regex targets a single-line tuple entry matching the style every
#   other build_ac_store deploy_map entry already uses. Test 4's assertion
#   about "Cannot load MIGRATION_MAP" was added after confirming empirically
#   (probe run against a real build) that generate_ticket_from_ac.py does NOT
#   crash today even with the sibling absent -- its importlib.util-based
#   sibling loader swallows the failure into a WARNING and degrades silently,
#   so an exit-0-only assertion would have passed immediately and been
#   under-specified. (#BP-900g-8)
# ====================================================================
