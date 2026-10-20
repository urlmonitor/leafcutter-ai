"""
MODULE: unit_tests/build_guards/test_bp_1500h_1_i.py
GOAL: Failing tests for AC BP-1500h-1-i -- a file-location setting naming a
    MISSING file or a FOLDER is reported as BROKEN (a warning naming the
    setting and the path / "is a folder"), never as "not configured"; the
    work reading it is skipped, the build continues and passes (decision 8),
    and the build never falls back to the shipped default path.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500h-1-i.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bp1500h_support import (  # noqa: E402
    CHANGELOG_KEY,
    SCRIPTS_DIR,
    directory_read_lines,
    lines_with,
    not_configured_lines,
    real_build,
    run_driver,
    settings_for,
    shipped_default,
)

_MISSING = "docs/missing-categories.md"
_FOLDER = "docs/categories-folder"


def _warning_lines(output: str, *needles: str) -> list[str]:
    return [ln for ln in lines_with(output, *needles) if "[WARNING]" in ln]


@pytest.mark.shared_layout_mutator
def test_missing_file_setting_warns_broken_skips_and_build_passes():
    # covers: BP-1500h-1-i
    # angle: criterion
    """Missing path: build exits 0, exactly one WARNING names the setting and
    the path as not found, nothing says 'not configured', nothing is written
    at that path or at the default path (no fallback to absent behaviour)."""
    run = real_build(settings_for(CHANGELOG_KEY, _MISSING))
    default_rel = shipped_default(CHANGELOG_KEY)

    assert run.returncode == 0, run.output[-2000:]
    warns = _warning_lines(run.output, CHANGELOG_KEY, _MISSING)
    assert len(warns) == 1, f"expected exactly one broken-setting warning: {warns}"
    assert "not found" in warns[0].lower() or "missing" in warns[0].lower(), warns[0]
    assert not_configured_lines(run.output, CHANGELOG_KEY) == []
    assert not (run.target / _MISSING).exists(), "scaffold written at broken path"
    assert not (run.target / default_rel).exists(), "fell back to default path"


@pytest.mark.shared_layout_mutator
def test_folder_setting_warns_is_a_folder_and_is_not_read():
    # covers: BP-1500h-1-i
    # angle: failure
    """Setting names an existing folder: build exits 0, one WARNING says the
    path is a folder, not a file, and the output has no directory read error."""
    run = real_build(
        settings_for(CHANGELOG_KEY, _FOLDER), plant={f"{_FOLDER}/": ""}
    )

    assert run.returncode == 0, run.output[-2000:]
    warns = _warning_lines(run.output, CHANGELOG_KEY, _FOLDER)
    assert len(warns) == 1, f"expected exactly one broken-setting warning: {warns}"
    assert "folder" in warns[0].lower() and "not a file" in warns[0].lower(), warns[0]
    assert directory_read_lines(run.output, run.target) == []
    assert not_configured_lines(run.output, CHANGELOG_KEY) == []


@pytest.mark.shared_layout_mutator
def test_broken_setting_build_differs_from_absent_setting_build():
    # covers: BP-1500h-1-i
    # angle: discrimination
    """The key-absent build installs the scaffold at the default location and
    prints no broken warning; the broken-setting build does neither -- so a
    typo is not silently treated as unset."""
    broken = real_build(settings_for(CHANGELOG_KEY, _MISSING))
    absent = real_build(settings_for(CHANGELOG_KEY, None))
    default_rel = shipped_default(CHANGELOG_KEY)

    assert (absent.target / default_rel).is_file()  # control
    assert _warning_lines(absent.output, CHANGELOG_KEY) == []  # control
    assert not (broken.target / default_rel).exists()
    assert len(_warning_lines(broken.output, CHANGELOG_KEY, _MISSING)) == 1


def test_integrity_check_does_not_accept_a_folder_for_a_file_setting(tmp_path):
    # covers: BP-1500h-1-i
    # angle: seam
    """build_referential_integrity must not accept a folder for a file-location
    key (its .exists() test passes a folder today). Control: a real file is
    accepted, a missing path is flagged, so the folder case is judged apart."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from build_referential_integrity import check_referential_integrity

    (tmp_path / "a-folder").mkdir()
    (tmp_path / "real.md").write_text("x\n", encoding="utf-8")

    def flagged(value: str) -> bool:
        found = check_referential_integrity(tmp_path, {CHANGELOG_KEY: value})
        return any(f["config_key"] == CHANGELOG_KEY for f in found)

    assert flagged("real.md") is False  # control: usable file accepted
    assert flagged("nope.md") is True  # control: missing flagged
    assert flagged("a-folder") is True  # folder is not a file


def test_broken_setting_is_skipped_by_every_reader_without_fallback():
    # covers: BP-1500h-1-i
    # angle: reachability
    """Run the three readers on a missing-file setting: no scaffold at the
    broken path or the default path, no staleness read of either, and the
    steps complete (the build continues)."""
    run = run_driver(settings_for(CHANGELOG_KEY, _MISSING))
    default_rel = shipped_default(CHANGELOG_KEY)

    assert run.returncode == 0, run.output[-2000:]
    assert not (run.target / _MISSING).exists()
    assert not (run.target / default_rel).exists()
    assert default_rel not in run.result["mapping_keys"]
    assert len(_warning_lines(run.output, CHANGELOG_KEY, _MISSING)) == 1
