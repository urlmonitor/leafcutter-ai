"""
MODULE: unit_tests/commit_guardian/test_folder_density_set_aside_report.py
COVERS: GE-133a-2 -- a set-aside folder is reported with its stated ground and
    counted apart from the judged ones; a run that judged nothing is not "clean".

Every test drives a REAL ``git commit`` whose pre-commit hook runs the DEPLOYED
check_folder_density.py (see _ge_133a_harness.py) and reads the real output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_133a_harness import (  # noqa: E402
    STORE,
    STORE_GROUND,
    Scratch,
    figure,
    leaks_into_judged_lists,
    make_files,
)

STORE_A = f"{STORE}/comp-a/fam-a"
STORE_B = f"{STORE}/comp-a/fam-b"
STORE_C = f"{STORE}/comp-b/fam-c"
OUTSIDE = ["scripts/tools", "unit_tests/tools", "docs/guides"]


def _seed(s: Scratch) -> None:
    make_files(s.repo, STORE_A, 18)
    make_files(s.repo, STORE_B, 29)
    make_files(s.repo, STORE_C, 5)
    for folder in OUTSIDE:
        make_files(s.repo, folder, 10)


def _stage_one_in(s: Scratch, folders: list[str]) -> None:
    for folder in folders:
        make_files(s.repo, folder, 1, tag="new", start=900)


@pytest.mark.shared_layout_reader
def test_set_aside_folders_reported_with_ground_and_counted_apart(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-133a-2
    # angle: criterion
    """3 judged, 2 set aside; both store folders named with the declared ground; neither
    is reported as within limits nor as already over."""
    s = Scratch(shared_reference_layout, tmp_path)
    _seed(s)
    s.baseline()
    _stage_one_in(s, [STORE_A, STORE_B, *OUTSIDE])
    rc, out = s.commit()
    assert rc == 0, f"commit was refused: {out!r}"
    assert 3 in figure(out, "judged"), f"judged figure missing: {out!r}"
    assert 2 in figure(out, r"set[ -]aside"), f"set-aside figure missing: {out!r}"
    for folder in (STORE_A, STORE_B):
        assert folder in out, f"{folder} not named: {out!r}"
        assert leaks_into_judged_lists(out, folder) == [], f"{folder} leaked: {out!r}"
    assert STORE_GROUND in out, f"stated ground not reported: {out!r}"


@pytest.mark.shared_layout_reader
def test_set_aside_count_moves_with_its_population(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-133a-2
    # angle: discrimination
    """Adding a third store folder moves the set-aside figure to 3 while judged stays 3."""
    s = Scratch(shared_reference_layout, tmp_path)
    _seed(s)
    s.baseline()
    _stage_one_in(s, [STORE_A, STORE_B, STORE_C, *OUTSIDE])
    rc, out = s.commit()
    assert rc == 0, f"commit was refused: {out!r}"
    assert 3 in figure(out, "judged"), f"judged figure missing: {out!r}"
    assert 3 in figure(out, r"set[ -]aside"), f"set-aside figure did not move to 3: {out!r}"
    assert 2 not in figure(out, r"set[ -]aside"), f"stale set-aside figure 2 still stated: {out!r}"
    assert STORE_C in out, f"third store folder not named: {out!r}"


@pytest.mark.shared_layout_reader
def test_store_only_commit_reports_zero_judged_and_no_clean_line(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-133a-2
    # angle: discrimination
    """Only store folders staged: exit 0, 0 judged, each named as set aside, and no
    'all within limits' pass line from a run that judged nothing."""
    s = Scratch(shared_reference_layout, tmp_path)
    _seed(s)
    s.baseline()
    _stage_one_in(s, [STORE_A, STORE_B])
    rc, out = s.commit()
    assert rc == 0, f"commit was refused: {out!r}"
    assert 0 in figure(out, "judged"), f"zero-judged figure missing: {out!r}"
    for folder in (STORE_A, STORE_B):
        assert folder in out, f"{folder} not named: {out!r}"
    assert "all within limits" not in out.lower(), f"success-shaped line from a run that judged nothing: {out!r}"
