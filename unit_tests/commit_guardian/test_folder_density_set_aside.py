"""
MODULE: unit_tests/commit_guardian/test_folder_density_set_aside.py
COVERS: GE-133a-1 -- only the location the configuration declares is set aside.

Every test drives a REAL ``git commit`` whose pre-commit hook runs the DEPLOYED
check_folder_density.py (see _ge_133a_harness.py). The verdict is the commit's
exit status and printed output.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_133a_harness import (  # noqa: E402
    FAMILY,
    STORE,
    Scratch,
    make_files,
    too_dense,
)

UNREAD_RE = re.compile(r"could not be read|cannot be read|could not read|unreadable|not be found", re.IGNORECASE)
UNINTERPRETED_RE = re.compile(r"could not (?:be )?interpret|cannot (?:be )?interpret|uninterpretable|malformed", re.IGNORECASE)


def _stage_store_growth(s: Scratch) -> None:
    make_files(s.repo, FAMILY, 4, start=100)


def _seed_family(s: Scratch) -> None:
    make_files(s.repo, FAMILY, 15)


@pytest.mark.shared_layout_reader
def test_store_crossing_and_new_family_commit_without_declaration_edit(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-133a-1
    # angle: discrimination
    """A store family crossing 15->19 and a brand-new 20-file family commit, and the
    declaration file is byte-identical afterwards (a location, not a list)."""
    s = Scratch(shared_reference_layout, tmp_path)
    _seed_family(s)
    s.baseline()
    before = s.config.read_bytes()
    _stage_store_growth(s)
    make_files(s.repo, f"{STORE}/guardrail-engine/GE-999-new-family", 20)
    rc, out = s.commit()
    assert rc == 0, f"store crossing was refused: {out!r}"
    assert s.config.read_bytes() == before, "the check rewrote its configuration"


@pytest.mark.shared_layout_reader
def test_lookalike_folders_outside_store_are_still_judged(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-133a-1
    # angle: discrimination
    """Source, test and prefix-lookalike folders go 15->16 and are refused; the store
    folder (15->19) is not named."""
    s = Scratch(shared_reference_layout, tmp_path)
    _seed_family(s)
    lookalikes = ["templates/acceptance-criteria", "unit_tests/acceptance-criteria", "docs/acceptance-criteria-archive"]
    for folder in lookalikes:
        make_files(s.repo, folder, 15)
    s.baseline()
    _stage_store_growth(s)
    for folder in lookalikes:
        make_files(s.repo, folder, 1, tag="new", start=900)
    rc, out = s.commit()
    assert rc != 0, f"lookalike folders were not refused: {out!r}"
    named = too_dense(out)
    assert named == {f: 16 for f in lookalikes}, f"named {named!r}; output {out!r}"
    assert FAMILY not in named


@pytest.mark.shared_layout_reader
def test_absent_or_malformed_declaration_judges_and_says_so(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-133a-1
    # angle: failure
    """Absent key, then an entry naming no location: refused, store named at 19, not
    reported as set aside, and the output says what could not be read/interpreted."""
    marker = "ENTRY-WITHOUT-PATH-MARKER"
    cases = {
        "absent": ("absent", [UNREAD_RE, re.compile(r"set_aside_locations"), re.compile(r"commit_guardian\.json")]),
        "malformed": ([{"ground": marker}], [UNINTERPRETED_RE, re.compile(marker)]),
    }
    for name, (declaration, expectations) in cases.items():
        case_dir = tmp_path / name
        case_dir.mkdir()
        s = Scratch(shared_reference_layout, case_dir, declaration)
        _seed_family(s)
        s.baseline()
        _stage_store_growth(s)
        rc, out = s.commit()
        assert rc != 0, f"{name}: commit completed: {out!r}"
        assert too_dense(out).get(FAMILY) == 19, f"{name}: store folder not named at 19: {out!r}"
        for line in out.splitlines():
            assert not (FAMILY in line and re.search(r"set[ -]aside", line, re.IGNORECASE)), f"{name}: {line!r}"
        for pattern in expectations:
            assert pattern.search(out), f"{name}: missing {pattern.pattern!r} in {out!r}"


@pytest.mark.shared_layout_reader
def test_empty_declaration_judges_without_claiming_unreadable(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-133a-1
    # angle: discrimination
    """Negative control: an empty declaration sets nothing aside, and is not called unreadable."""
    s = Scratch(shared_reference_layout, tmp_path, [])
    _seed_family(s)
    s.baseline()
    _stage_store_growth(s)
    rc, out = s.commit()
    assert rc != 0, f"empty declaration did not judge the store folder: {out!r}"
    assert too_dense(out).get(FAMILY) == 19, out
    assert not UNREAD_RE.search(out), f"empty declaration reported as unreadable: {out!r}"
    assert not UNINTERPRETED_RE.search(out), f"empty declaration reported as uninterpretable: {out!r}"


@pytest.mark.shared_layout_reader
def test_set_aside_follows_the_declared_location_not_a_built_in_path(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-133a-1
    # angle: discrimination
    """Declaration names only records/criteria/: the store folder is judged and named,
    the records/criteria folder (15->19) is not."""
    other = "records/criteria/family-a"
    s = Scratch(shared_reference_layout, tmp_path, [{"path": "records/criteria/", "ground": "declared elsewhere"}])
    _seed_family(s)
    make_files(s.repo, other, 15)
    s.baseline()
    _stage_store_growth(s)
    make_files(s.repo, other, 4, start=100)
    rc, out = s.commit()
    assert rc != 0, f"store folder was not judged: {out!r}"
    assert set(too_dense(out)) == {FAMILY}, f"named {too_dense(out)!r}; output {out!r}"
