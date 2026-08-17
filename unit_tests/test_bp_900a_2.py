"""
MODULE: test_bp_900a_2
GOAL: Behavioral regression coverage for AC BP-900a-2 — build.py must deploy
    the two standalone scripts ``goal_to_epic.py`` and
    ``build_ac_mode_detection.py`` to the consumer project's
    ``<output_root>/scripts/`` directory (byte-identical to their sources in
    ``templates/scripts/``) AND install a shim at ``<target>/scripts/<name>``
    that resolves to the deployed copy, with a RELATIVE (not absolute)
    symlink target.
TICKET: tickets/00_inbox/epics/EPIC-DeploymentCompleteness/03_TICKET-20260611-BP-900a-2.md
AC: BP-900a-2

ARCHITECTURE: Real-artifact behavioral tests (per the Real-Artifact
    Behavioral Test Mandate, BP-1100f-2) plus one idempotency check. All run
    the REAL ``build.main(["--target-dir", ...])`` entry point into a fresh
    ``tmp_path`` and then read the deployed files / shims back off disk —
    neither mocks the copy call, the shim-creation call, nor inspects
    ``call_args``. A dispatch-topology-only test (grepping source for a
    shim_map/deploy-list literal) would pass on entries that are defined but
    never wired into the phase runner or ``install_shims()``, so it is
    deliberately NOT used here as the sole coverage.

SOURCE-OF-TRUTH NOTE: Unlike the sibling AC BP-900a-1 (whose Gherkin prose
    named a ``templates/scripts/ac_store/`` source that did not match the
    already-implemented convention), the existing
    ``build_template_standalone_scripts()`` phase in scripts/build_phases.py
    already sources exclusively from ``templates/scripts/`` (shallow glob,
    no subdirectories) and deploys into ``<output_root>/scripts/`` — this
    matches BP-900a-2's Gherkin prose verbatim, so no divergence is needed
    here. At authoring time neither ``templates/scripts/goal_to_epic.py`` nor
    ``templates/scripts/build_ac_mode_detection.py`` exists yet (only the
    top-level ``scripts/goal_to_epic.py`` and ``scripts/build_ac_mode_detection.py``
    exist), so python-coder must add the two template sources (most likely by
    copying the existing top-level scripts/ versions verbatim) as part of
    closing this AC — see it_requirements.n_location_rule ("2 — the
    standalone-script deploy list and the shim-install list").

RELATIVE-SHIM NOTE: The AC's it_requirements.notes calls out BP-016/BP-017
    (commits 47fb660ff, 9bf606c28) — prior regressions where build-shim
    symlinks pointed at absolute developer-machine paths, breaking every
    consumer install. test_ac2_shims_resolve_to_the_deployed_copy asserts the
    new shims' symlink targets are RELATIVE strings (os.readlink() output is
    not an absolute path), not merely that resolve() lands on the right file
    (which absolute and relative symlinks would equally satisfy).
"""
# @ac-tag: BP-900a-2

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup

# The 2 standalone scripts BP-900a-2 requires to be deployed + shimmed.
_EXPECTED_FILES = [
    "goal_to_epic.py",
    "build_ac_mode_detection.py",
]

_TEMPLATE_SOURCE_DIR = _REPO_ROOT / "templates" / "scripts"


def _find_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* — the dir holding scripts/.

    Mirrors the helper in unit_tests/test_bp_900a_1.py: keyed on ``scripts/``
    because that is the prefix consumer templates address, regardless of the
    configured output-root directory name (``.leafcutter`` by default).
    """
    candidates = sorted(
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} (a directory "
        f"containing a 'scripts/' subdirectory); found {[p.name for p in candidates]}."
    )
    return candidates[0]


def _run_build_into(target_dir: Path) -> tuple[Path, Path]:
    """Run the REAL build.py --target-dir against *target_dir*.

    Returns (target_dir, output_root) so callers can check both the
    consolidated output tree AND the shim locations at target_dir root.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. The deployment "
        "assertions below cannot run against a failed build."
    )
    output_root = _find_output_root(target_dir)
    return target_dir, output_root


# ---------------------------------------------------------------------------
# Real-artifact behavioral tests
# ---------------------------------------------------------------------------


def test_standalone_scripts_are_deployed_to_output_root(tmp_path: Path) -> None:
    """AC BP-900a-2: after a real build, goal_to_epic.py and
    build_ac_mode_detection.py exist under the deployed output root's
    scripts/ directory, byte-identical to their sources in templates/scripts/.

    This is a real-artifact round-trip: it runs the actual build.py entry
    point into a fresh tmp_path, then reads the deployed directory listing
    and file bytes back off disk. It does not mock shutil.copy2, does not
    inspect call_args on build_template_standalone_scripts, and does not
    merely check that a deploy-list literal is present in source.
    """
    # covers: BP-900a-2
    _target_dir, output_root = _run_build_into(tmp_path / "consumer")
    deployed_scripts_dir = output_root / "scripts"

    missing = [
        name for name in _EXPECTED_FILES if not (deployed_scripts_dir / name).is_file()
    ]
    assert not missing, (
        f"{len(missing)} of the 2 required standalone scripts were NOT deployed to "
        f"{deployed_scripts_dir}: {sorted(missing)!r}. AC BP-900a-2 requires both "
        "goal_to_epic.py and build_ac_mode_detection.py to exist under "
        "<output_root>/scripts/ — add templates/scripts/goal_to_epic.py and "
        "templates/scripts/build_ac_mode_detection.py as source templates so "
        "build_template_standalone_scripts() (scripts/build_phases.py) deploys them."
    )

    mismatches: list[str] = []
    for name in _EXPECTED_FILES:
        src = _TEMPLATE_SOURCE_DIR / name
        dst = deployed_scripts_dir / name

        if not src.is_file():
            mismatches.append(f"{name}: template source missing at {src}")
            continue
        if not dst.is_file():
            # Already reported above; skip to avoid duplicate noise.
            continue
        if dst.read_bytes() != src.read_bytes():
            mismatches.append(f"{name}: deployed content differs from template source")

    assert not mismatches, (
        "Deployed standalone scripts are not byte-identical to their "
        "templates/scripts/ sources (or the source is missing):\n  "
        + "\n  ".join(mismatches)
        + "\nAC BP-900a-2 requires verbatim copies (no transformation or "
        "interpolation) from templates/scripts/ to <output_root>/scripts/."
    )


def test_standalone_script_shims_resolve_to_the_deployed_copy(tmp_path: Path) -> None:
    """AC BP-900a-2: shims at <target>/scripts/goal_to_epic.py and
    <target>/scripts/build_ac_mode_detection.py resolve to the deployed
    copies under <output_root>/scripts/, and the created symlinks use a
    RELATIVE target (not an absolute developer-machine path — see BP-016 /
    BP-017 regression note in it_requirements.notes on the source AC).

    Real-artifact round-trip: runs the actual build.py entry point, then
    reads the shim path's on-disk symlink target and resolved content back
    off disk. Does not mock install_shims() or inspect its call_args/return
    value — a shim_map entry that is defined but never wired into
    install_shims()'s actual symlink-creation loop would still fail this
    assertion because no file/symlink would exist at the canonical path.
    """
    # covers: BP-900a-2
    target_dir, output_root = _run_build_into(tmp_path / "consumer")
    deployed_scripts_dir = output_root / "scripts"

    missing_shims: list[str] = []
    absolute_targets: list[str] = []
    content_mismatches: list[str] = []

    for name in _EXPECTED_FILES:
        shim_path = target_dir / "scripts" / name
        deployed_path = deployed_scripts_dir / name

        if not (shim_path.is_file() or shim_path.is_symlink()):
            missing_shims.append(
                f"{name}: no shim found at {shim_path} "
                f"(expected a symlink or copy resolving to {deployed_path})"
            )
            continue

        # The shim must resolve to content identical to the deployed copy.
        if not deployed_path.is_file():
            content_mismatches.append(
                f"{name}: deployed copy missing at {deployed_path}; cannot verify shim"
            )
        elif shim_path.read_bytes() != deployed_path.read_bytes():
            content_mismatches.append(
                f"{name}: shim content at {shim_path} does not match deployed copy "
                f"at {deployed_path}"
            )

        # The symlink target itself (not the resolved path) must be relative.
        if shim_path.is_symlink():
            raw_target = os.readlink(shim_path)
            if Path(raw_target).is_absolute():
                absolute_targets.append(
                    f"{name}: symlink target is ABSOLUTE ({raw_target!r}) — must be "
                    "relative per BP-016/BP-017 (absolute developer-machine paths "
                    "break every consumer install)"
                )

    assert not missing_shims, (
        "Expected shims not found:\n  " + "\n  ".join(missing_shims)
        + "\nAC BP-900a-2 requires a shim at <target>/scripts/<name> for both "
        "goal_to_epic.py and build_ac_mode_detection.py — add entries to the "
        "shim-install list (install_shims()'s file_shims, scripts/build_helpers.py)."
    )
    assert not content_mismatches, (
        "Shim content does not match the deployed copy:\n  "
        + "\n  ".join(content_mismatches)
    )
    assert not absolute_targets, (
        "Shim symlink targets must be relative, not absolute:\n  "
        + "\n  ".join(absolute_targets)
    )


def test_standalone_scripts_deploy_and_shims_are_idempotent(tmp_path: Path) -> None:
    """AC BP-900a-2 (it_requirements): re-running build.py with the same
    inputs produces the same output — a second build must not remove or
    change either deployed file or either shim.

    Runs the real build twice into the same target directory and re-reads
    the deployed files / shim targets from disk after the second run.
    """
    # covers: BP-900a-2
    target_dir = tmp_path / "consumer"
    _target_dir, output_root = _run_build_into(target_dir)
    deployed_scripts_dir = output_root / "scripts"

    first_pass_deployed = {
        name: (deployed_scripts_dir / name).read_bytes()
        for name in _EXPECTED_FILES
        if (deployed_scripts_dir / name).is_file()
    }
    first_pass_shim_targets = {
        name: os.readlink(target_dir / "scripts" / name)
        for name in _EXPECTED_FILES
        if (target_dir / "scripts" / name).is_symlink()
    }

    # Guard against a tautological pass: if nothing was deployed/shimmed on
    # the first build, the loops below would silently iterate zero times and
    # this test would report green while the feature is entirely absent.
    # test_standalone_scripts_are_deployed_to_output_root and
    # test_standalone_script_shims_resolve_to_the_deployed_copy are the
    # authoritative RED signal for "nothing deployed yet", but this test must
    # not itself claim success in that state.
    assert set(first_pass_deployed) == set(_EXPECTED_FILES), (
        f"Cannot verify idempotency: not all files were deployed on the first "
        f"build. Deployed: {sorted(first_pass_deployed)!r}, "
        f"expected: {sorted(_EXPECTED_FILES)!r}."
    )
    assert set(first_pass_shim_targets) == set(_EXPECTED_FILES), (
        f"Cannot verify idempotency: not all shims were created on the first "
        f"build. Shimmed: {sorted(first_pass_shim_targets)!r}, "
        f"expected: {sorted(_EXPECTED_FILES)!r}."
    )

    # Second run, same target — must be idempotent.
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"Second build.py run exited {exit_code!r}; expected 0."

    for name, first_bytes in first_pass_deployed.items():
        deployed_path = deployed_scripts_dir / name
        assert deployed_path.is_file(), (
            f"After a second build run, deployed file disappeared: {deployed_path}"
        )
        assert deployed_path.read_bytes() == first_bytes, (
            f"Re-running build.py changed the content of deployed file: {name}. "
            "The build must be idempotent."
        )

    for name, first_target in first_pass_shim_targets.items():
        shim_path = target_dir / "scripts" / name
        assert shim_path.is_symlink(), (
            f"After a second build run, shim disappeared or was replaced by a "
            f"non-symlink: {shim_path}"
        )
        assert os.readlink(shim_path) == first_target, (
            f"Re-running build.py changed the symlink target of shim: {name}. "
            "The build must be idempotent."
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-17 [test-writer/EPIC-DeploymentCompleteness/BP-900a-2]: Initial
#   failing test stubs written before python-coder implementation. At
#   authoring time:
#     - templates/scripts/goal_to_epic.py and
#       templates/scripts/build_ac_mode_detection.py do NOT exist (only the
#       top-level scripts/goal_to_epic.py and scripts/build_ac_mode_detection.py
#       exist). build_template_standalone_scripts() (scripts/build_phases.py)
#       already globs templates/scripts/*.py into <output_root>/scripts/, so
#       once the two template sources are added, this phase should deploy
#       them automatically without further code changes.
#     - install_shims()'s file_shims list (scripts/build_helpers.py) has no
#       entries for scripts/goal_to_epic.py or
#       scripts/build_ac_mode_detection.py, so no shim is created at
#       <target>/scripts/<name> today.
#   Expected RED states:
#     test_standalone_scripts_are_deployed_to_output_root fails with an
#       AssertionError listing both files as missing/not deployed.
#     test_standalone_script_shims_resolve_to_the_deployed_copy fails with an
#       AssertionError listing both shims as missing.
#     test_standalone_scripts_deploy_and_shims_are_idempotent fails with an
#       AssertionError from its own explicit non-tautology guard (asserts
#       both files/both shims were actually deployed on the first build)
#       before it ever reaches the second build — it does NOT silently pass
#       on an empty-dict first pass.
# ====================================================================
