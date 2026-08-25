"""
MODULE: test_bp_900a_1
GOAL: Behavioral regression coverage for AC BP-900a-1 — build.py must deploy
    all 13 ac_store scripts to the consumer project's
    ``<output_root>/scripts/ac_store/`` directory, byte-identical to source.
TICKET: tickets/00_inbox/epics/EPIC-DeploymentCompleteness/01_TICKET-20260611-BP-900a-1.md
AC: BP-900a-1

ARCHITECTURE: Two real-artifact behavioral tests (per the Real-Artifact
    Behavioral Test Mandate, BP-1100f-2). Both run the REAL ``build.py
    --target-dir`` into a fresh ``tmp_path`` and then read the deployed files
    back off disk — neither mocks the copy call nor inspects ``call_args``.
    A dispatch-topology-only test (e.g. asserting a deploy_map entry exists in
    source via string grep) would pass on a deploy_map that is defined but
    never wired into the phase runner, so it is deliberately NOT used here as
    the sole coverage.

SOURCE-OF-TRUTH NOTE: The AC's Gherkin criteria describes the source location
    as "templates/scripts/ac_store/". At the time this ticket was authored,
    that directory exists but is EMPTY, while the actual 13 source scripts
    live at ``scripts/ac_store/`` (package root), and the existing
    ``build_ac_store()`` phase in scripts/build_phases.py already sources its
    (currently incomplete) deploy_map from that same ``scripts/ac_store/``
    location — see its docstring and DECISION HISTORY entry for
    EPIC-AcPipelineDeployGaps. This test therefore asserts byte-identity
    against ``<repo_root>/scripts/ac_store/<name>``, matching the established,
    already-implemented convention, rather than the (currently non-existent)
    ``templates/scripts/ac_store/`` source implied by the AC's prose. If a
    human clarifies that scripts should instead be authored under
    ``templates/scripts/ac_store/`` as canonical source, this test's source
    path must be updated to match (Source-of-Truth Discipline Rule 5 — prefer
    expanding/adjusting the test over silently shrinking the AC's intent).
"""
# @ac-tag: BP-900a-1

from __future__ import annotations

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

# The 13 files the AC requires to exist under <output_root>/scripts/ac_store/.
_EXPECTED_FILES = [
    "ac_prioritizer.py",
    "generate_ticket_from_ac.py",
    "scan_ac_store.py",
    "mark_ac_done.py",
    "validate_ac_schema.py",
    "ac_triage.py",
    "create_ac_workflow.py",
    "cross_reference_audit.py",
    "backfill_readiness.py",
    "ac_parent_id.py",
    "scan_ac_orphans.py",
    "fix_ac_orphans.py",
    "__init__.py",
]


def _find_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* — the dir holding scripts/.

    Mirrors the helper in unit_tests/test_bp_900g_4.py: keyed on ``scripts/``
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


def _run_build_into(target_dir: Path) -> Path:
    """Run the REAL build.py --target-dir against *target_dir* and return the
    deployed <output_root>/scripts/ac_store/ directory.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. The deployment "
        "assertions below cannot run against a failed build."
    )
    output_root = _find_output_root(target_dir)
    return output_root / "scripts" / "ac_store"


# ---------------------------------------------------------------------------
# Real-artifact behavioral tests
# ---------------------------------------------------------------------------


def test_ac1_all_13_ac_store_files_are_deployed(tmp_path: Path) -> None:
    """AC BP-900a-1: all 13 named ac_store scripts exist under
    <target>/.leafcutter/scripts/ac_store/ after a successful build.

    This is a real-artifact round-trip: it runs the actual build.py entry
    point into a fresh tmp_path, then reads the deployed directory listing
    back off disk. It does not mock shutil.copy2, does not inspect call_args
    on build_ac_store, and does not merely check that a deploy_map literal is
    present in source — a deploy_map with the right filenames that is never
    executed (or whose output the phase runner discards) would still fail
    this assertion.
    """
    # covers: BP-900a-1
    deployed_dir = _run_build_into(tmp_path / "consumer")

    missing = [name for name in _EXPECTED_FILES if not (deployed_dir / name).is_file()]

    assert not missing, (
        f"{len(missing)} of the 13 required ac_store scripts were NOT deployed to "
        f"{deployed_dir}: {sorted(missing)!r}. AC BP-900a-1 requires all 13 files "
        "(ac_prioritizer.py, generate_ticket_from_ac.py, scan_ac_store.py, "
        "mark_ac_done.py, validate_ac_schema.py, ac_triage.py, "
        "create_ac_workflow.py, cross_reference_audit.py, backfill_readiness.py, "
        "ac_parent_id.py, scan_ac_orphans.py, fix_ac_orphans.py, __init__.py) to "
        "exist under <output_root>/scripts/ac_store/ — add the missing entries to "
        "build_ac_store()'s deploy_map in scripts/build_phases.py."
    )


def test_ac1_deployed_files_are_byte_identical_to_source(tmp_path: Path) -> None:
    """AC BP-900a-1: each deployed ac_store script is byte-identical to its
    source counterpart — no template compilation or interpolation.

    Reads both the source file and the file the real build actually wrote to
    disk, and compares raw bytes. This is the real-effect round-trip: the
    write is never mocked, and the comparison happens against what is
    actually sitting on disk after the build ran, not against an in-memory
    expectation of what should have been copied.
    """
    # covers: BP-900a-1
    deployed_dir = _run_build_into(tmp_path / "consumer")
    source_dir = _REPO_ROOT / "scripts" / "ac_store"

    mismatches: list[str] = []
    for name in _EXPECTED_FILES:
        src = source_dir / name
        dst = deployed_dir / name

        if not src.is_file():
            # Should not happen in this repo today — all 13 sources exist —
            # but surfacing it explicitly is more useful than an opaque
            # FileNotFoundError from .read_bytes() below.
            mismatches.append(f"{name}: source file missing at {src}")
            continue

        if not dst.is_file():
            mismatches.append(f"{name}: not deployed to {dst}")
            continue

        if dst.read_bytes() != src.read_bytes():
            mismatches.append(f"{name}: deployed content differs from source")

    assert not mismatches, (
        "Deployed ac_store scripts are not byte-identical to their sources:\n  "
        + "\n  ".join(mismatches)
        + "\nAC BP-900a-1 requires verbatim copies (no transformation or "
        "interpolation) from scripts/ac_store/ to <output_root>/scripts/ac_store/."
    )


def test_ac1_deployed_ac_store_is_idempotent_on_rebuild(tmp_path: Path) -> None:
    """AC BP-900a-1 (it_requirements): re-running build.py with the same
    inputs produces the same output — a second build must not remove or
    change any of the 13 deployed files.

    Runs the real build twice into the same target directory and re-reads
    the deployed files from disk after the second run.
    """
    # covers: BP-900a-1
    target_dir = tmp_path / "consumer"
    deployed_dir = _run_build_into(target_dir)
    first_pass = {name: (deployed_dir / name).read_bytes() for name in _EXPECTED_FILES}

    # Second run, same target — must be idempotent.
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"Second build.py run exited {exit_code!r}; expected 0."

    second_pass_missing = [
        name for name in _EXPECTED_FILES if not (deployed_dir / name).is_file()
    ]
    assert not second_pass_missing, (
        f"After a second build run, these previously-deployed ac_store files are "
        f"missing: {sorted(second_pass_missing)!r}."
    )

    changed = [
        name
        for name in _EXPECTED_FILES
        if (deployed_dir / name).read_bytes() != first_pass[name]
    ]
    assert not changed, (
        f"Re-running build.py changed the content of these deployed ac_store "
        f"files: {sorted(changed)!r}. The build must be idempotent."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-17 [test-writer/EPIC-DeploymentCompleteness/BP-900a-1]: Initial
#   failing test stubs written before python-coder implementation. At
#   authoring time, build_ac_store()'s deploy_map (scripts/build_phases.py)
#   deploys only 10 files (6 of which overlap with the 13 required by this
#   AC: ac_prioritizer.py, generate_ticket_from_ac.py, scan_ac_store.py,
#   mark_ac_done.py, scan_ac_orphans.py, ac_parent_id.py) and is missing
#   validate_ac_schema.py, ac_triage.py, create_ac_workflow.py,
#   cross_reference_audit.py, backfill_readiness.py, fix_ac_orphans.py, and
#   __init__.py. All source files for the missing 7 already exist at
#   scripts/ac_store/, so this is a deploy_map completeness gap, not a
#   missing-source gap. Expected red state: test_ac1_all_13_ac_store_files_are_deployed
#   fails with an AssertionError listing the 7 missing filenames.
# ====================================================================
