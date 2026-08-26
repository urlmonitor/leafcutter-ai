"""
MODULE: unit_tests/ac_store/test_validate_ac_schema_no_op.py
GOAL: KI-ACS-001 — validate_ac_schema.py must never report a success-shaped
    result from a run that validated nothing.

BUSINESS CONTEXT: The script takes file paths and did no globbing of its own.
    Handed a directory — the intuitive way to validate a component — it matched
    zero files, printed "No YAML files to validate." and exited 0. A validator
    that cannot distinguish "clean" from "I was given nothing" is worse than no
    validator, because it is consulted for reassurance. CLAUDE.md's own
    AC-store hygiene section prescribed the bare-directory form from 2026-08-10
    until 2026-08-18, so the documented defence against store rot was itself a
    no-op for eight days.

    Two behaviours are asserted here:
      1. a directory argument is walked recursively and its AC YAML validated;
      2. a run that resolves zero files exits NON-ZERO.

    The recursive part matters on its own: AC YAML sits at more than one depth,
    so a fixed-depth glob like ``*/*.yaml`` silently skips whole directories —
    the same defect in a smaller costume.

DOC_LINKS:
  - docs/known-issues/ac-store.md
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the validator as a subprocess — the way every caller reaches it."""
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )


_VALID_AC = """\
id: {ac_id}
title: "A placeholder criterion used only to exercise the validator"
component: ac-store
components:
  - ac_store
level: L2
status: active
req_status: draft
work_status: todo
readiness: draft
priority: medium
roadmap_phase: phase_1
criteria: |
  Given a fixture record,
  When the validator reads it,
  Then it is accepted.
depends_on: []
doc_links: []
assigned_agent: python-coder
estimated_complexity: S
origin_agent: BrainCandy
created: 2026-08-19
amended_by: []
superseded_by: null
covered_by: []
implemented_by: []
change_target: docs
test_required: false
test_rationale: "Fixture record; not real work."
notes: "Fixture."
"""


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """An AC store with records at TWO different depths."""
    root = tmp_path / "acs"
    shallow = root / "ac-store"
    nested = shallow / "ACS-900-feature-folder"
    nested.mkdir(parents=True)
    (shallow / "ACS-901.yaml").write_text(
        _VALID_AC.format(ac_id="ACS-901"), encoding="utf-8"
    )
    (nested / "ACS-902.yaml").write_text(
        _VALID_AC.format(ac_id="ACS-902"), encoding="utf-8"
    )
    return root


def test_directory_argument_is_walked_recursively(store: Path) -> None:
    """A directory resolves to every AC YAML beneath it, at any depth.

    RED before the fix: the script does no globbing, so a directory matches zero
    files and it prints "No YAML files to validate." while exiting 0.
    """
    result = _run(str(store))

    assert result.returncode == 0, (
        f"expected a clean directory to validate cleanly, got "
        f"{result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "No YAML files to validate" not in result.stdout, (
        "the directory was treated as zero files — the no-op this test exists "
        f"to prevent. stdout: {result.stdout}"
    )
    # Both depths must be reached: the shallow record AND the nested one.
    assert "2" in result.stdout, (
        "expected both records (one shallow, one nested) to be counted; a "
        f"fixed-depth glob would find only one. stdout: {result.stdout}"
    )


def test_directory_walk_surfaces_a_real_violation(store: Path, tmp_path: Path) -> None:
    """A directory containing an invalid record fails, rather than passing blind."""
    bad = store / "ac-store" / "ACS-903.yaml"
    bad.write_text(
        _VALID_AC.format(ac_id="ACS-903").replace(
            "readiness: draft", "readiness: not-a-readiness-value"
        ),
        encoding="utf-8",
    )

    result = _run(str(store))

    assert result.returncode == 1, (
        "a directory holding an invalid record must fail; passing here is the "
        f"false green. stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ACS-903" in result.stderr, (
        f"the failure must name the offending record. stderr: {result.stderr}"
    )


def test_zero_resolved_files_exits_non_zero(tmp_path: Path) -> None:
    """An argument list that resolves to no AC YAML is an error, not a pass.

    This is the heart of KI-ACS-001: silence must not read as success.
    """
    empty = tmp_path / "empty"
    empty.mkdir()

    result = _run(str(empty))

    assert result.returncode != 0, (
        "a run that validated nothing exited 0 — a success-shaped result from a "
        f"run that checked nothing. stdout: {result.stdout}"
    )


def test_non_yaml_only_argument_exits_non_zero(tmp_path: Path) -> None:
    """Passing only non-YAML files validates nothing, so it must not report OK."""
    stray = tmp_path / "notes.md"
    stray.write_text("not an AC\n", encoding="utf-8")

    result = _run(str(stray))

    assert result.returncode != 0, (
        "non-YAML arguments were skipped silently and the run reported success "
        f"having checked nothing. stdout: {result.stdout}"
    )


def test_index_yaml_is_excluded_from_a_directory_walk(store: Path) -> None:
    """index.yaml is a registry, not an AC — walking must not try to validate it.

    Without this exclusion, fixing the walk would make every directory run fail
    on a file that was never an acceptance criterion.
    """
    (store / "ac-store" / "index.yaml").write_text(
        "components:\n  - id: ac-store\n    prefix: ACS\n", encoding="utf-8"
    )

    result = _run(str(store))

    assert result.returncode == 0, (
        "index.yaml is a registry and must be skipped by the directory walk; "
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_explicit_file_paths_still_work(store: Path) -> None:
    """Regression guard: the existing file-path contract is unchanged.

    Every current caller (check_fixture_schema.py, the documented find -exec
    form) passes explicit files. This must keep behaving exactly as before.
    """
    one = store / "ac-store" / "ACS-901.yaml"
    two = store / "ac-store" / "ACS-900-feature-folder" / "ACS-902.yaml"

    result = _run(str(one), str(two))

    assert result.returncode == 0, (
        f"explicit file paths regressed. stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "OK" in result.stdout


def test_missing_path_is_still_reported(tmp_path: Path) -> None:
    """A named path that does not exist remains an error, not a silent skip."""
    result = _run(str(tmp_path / "nope.yaml"))

    assert result.returncode != 0
    assert "not found" in result.stderr.lower()
