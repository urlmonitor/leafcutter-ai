"""
MODULE: unit_tests/build_guards/test_bp_1500h_1.py
GOAL: Failing tests for AC BP-1500h-1 -- a file-location setting left empty is
    "not configured" for EVERY build step that reads it, said once; an ABSENT
    key is the shipped default (user decision 11).
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500h-1.yaml

The pair of scratch projects (empty vs absent) differ in exactly one setting.
Empty-value builds are REAL ``build.py`` runs into scratch targets (cached per
scenario in ``_bp1500h_support``); the per-key set runs the three
setting-reading steps in a fresh process with the real config loader.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bp1500h_support import (  # noqa: E402
    CHANGELOG_KEY,
    PRECOMMIT_KEY,
    README_KEY,
    REACHABILITY_KEY,
    directory_read_lines,
    not_configured_lines,
    real_build,
    run_driver,
    settings_for,
    shipped_default,
)

# Files the staleness step registers (it reads them to compare content).
_STALENESS_READ = {CHANGELOG_KEY, PRECOMMIT_KEY}
# The pre-existing literal fallback for a key the shipped defaults omit.
_LITERAL_FALLBACK = {REACHABILITY_KEY: "config/reachability_exemptions.yaml"}


def _default_rel(key: str) -> str | None:
    return shipped_default(key) or _LITERAL_FALLBACK.get(key)


@pytest.mark.shared_layout_mutator
def test_empty_setting_turns_the_feature_off():
    # covers: BP-1500h-1
    # angle: criterion
    """Empty changelog_categories_path: build passes, no scaffold is written
    anywhere for it (not at the shipped default), no step reads or checks a
    file for it. Control: the key-absent build DOES install the default."""
    default_rel = shipped_default(CHANGELOG_KEY)
    assert default_rel, "shipped default for changelog_categories_path missing"
    empty = real_build(settings_for(CHANGELOG_KEY, ""))
    absent = real_build(settings_for(CHANGELOG_KEY, None))

    assert empty.returncode == 0, empty.output[-2000:]
    assert not (empty.target / default_rel).exists(), "scaffold at default path"
    stray = [p for p in empty.target.rglob("changelog_categories.md")
             if ".leafcutter" not in p.parts]
    assert stray == [], f"scaffold installed for an empty setting: {stray}"
    assert directory_read_lines(empty.output, empty.target) == [], (
        "a step tried to read the project folder as a file"
    )
    # control: absent is NOT off -- the scaffold lands at the default path
    assert absent.returncode == 0, absent.output[-2000:]
    assert (absent.target / default_rel).is_file()


@pytest.mark.shared_layout_mutator
def test_absent_setting_uses_the_shipped_default_path():
    # covers: BP-1500h-1
    # angle: discrimination
    """Absent key: scaffold installed at the shipped default, the staleness
    step reads it, no 'not configured' line -- AND the empty-value build of the
    same project differs from it (says 'not configured', reads nothing).
    Catches 'absent is treated as off too' and 'empty is treated as absent'."""
    default_rel = shipped_default(CHANGELOG_KEY)
    assert default_rel
    absent = real_build(settings_for(CHANGELOG_KEY, None))
    empty = real_build(settings_for(CHANGELOG_KEY, ""))
    steps = run_driver(settings_for(CHANGELOG_KEY, None))

    assert (absent.target / default_rel).is_file()
    assert not_configured_lines(absent.output, CHANGELOG_KEY) == []
    assert default_rel in steps.result["mapping_keys"], (
        "staleness step did not read the default-path scaffold"
    )
    # the pair must differ: empty announces itself, absent does not
    assert len(not_configured_lines(empty.output, CHANGELOG_KEY)) == 1
    assert not (empty.target / default_rel).exists()


@pytest.mark.shared_layout_mutator
def test_empty_setting_output_has_no_directory_read_and_one_not_configured_line():
    # covers: BP-1500h-1
    # covers: BP-1500h
    # angle: deployed
    """Empty-value build output: no 'Is a directory', no 'could not read
    <project folder>', exactly one 'not configured' line naming the setting."""
    empty = real_build(settings_for(CHANGELOG_KEY, ""))
    absent = real_build(settings_for(CHANGELOG_KEY, None))

    assert empty.returncode == 0, empty.output[-2000:]
    assert directory_read_lines(empty.output, empty.target) == []
    lines = not_configured_lines(empty.output, CHANGELOG_KEY)
    assert len(lines) == 1, f"expected exactly one 'not configured' line: {lines}"
    assert CHANGELOG_KEY in lines[0]
    # control: the absent build says neither thing
    assert directory_read_lines(absent.output, absent.target) == []
    assert not_configured_lines(absent.output, CHANGELOG_KEY) == []


@pytest.mark.parametrize(
    "key", [CHANGELOG_KEY, PRECOMMIT_KEY, REACHABILITY_KEY, README_KEY]
)
def test_every_file_location_setting_behaves_the_same_when_empty(key):
    # covers: BP-1500h-1
    # angle: boundary
    """Each file-location key set to '' writes and reads nothing for that key
    and prints one 'not configured' line naming it; the same key absent uses
    its shipped default (scaffold installed there, staleness step reads it).
    A fix scoped to the one key in the 2026-10-12 log fails the other keys."""
    default_rel = _default_rel(key)
    assert default_rel, f"no default location known for {key}"
    empty = run_driver(settings_for(key, ""))

    assert empty.returncode == 0, empty.output[-2000:]
    assert directory_read_lines(empty.output, empty.target) == [], key
    assert not (empty.target / default_rel).exists(), f"{key}: scaffold written"
    assert default_rel not in empty.result["mapping_keys"], f"{key}: file read"
    lines = not_configured_lines(empty.output, key)
    assert len(lines) == 1, f"{key}: expected one 'not configured' line: {lines}"
    assert not [f for f in empty.result["integrity"] if f["config_key"] == key], (
        f"{key}: integrity check flagged an empty setting"
    )

    if shipped_default(key) is None:
        return  # no shipped default for this key: absent-case not definable
    absent = run_driver(settings_for(key, None))
    assert (absent.target / default_rel).is_file(), f"{key}: absent -> no scaffold"
    if key in _STALENESS_READ:
        assert default_rel in absent.result["mapping_keys"], f"{key}: not read"
    assert not_configured_lines(absent.output, key) == [], f"{key}: absent announced"
