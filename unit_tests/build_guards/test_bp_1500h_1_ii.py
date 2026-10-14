"""
MODULE: unit_tests/build_guards/test_bp_1500h_1_ii.py
GOAL: Failing tests for AC BP-1500h-1-ii -- an empty setting is announced
    exactly once per build at INFORMATIONAL severity (no [WARNING] prefix),
    however many steps read it; two empty settings give exactly two lines,
    one naming each.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500h-1-ii.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bp1500h_support import (  # noqa: E402
    CHANGELOG_KEY,
    PRECOMMIT_KEY,
    not_configured_lines,
    real_build,
    run_driver,
    settings_for,
)


@pytest.mark.shared_layout_mutator
def test_empty_setting_read_by_two_steps_is_announced_once_at_info():
    # covers: BP-1500h-1-ii
    # angle: criterion
    """changelog_categories_path '' is read by the scaffold-staleness and
    scaffold-install steps; the real build prints exactly one 'not configured'
    line for it and that line carries no warning prefix. Control: an ABSENT key
    prints none. Catches 'each reader prints its own line' and 'printed as a
    warning'."""
    empty = real_build(settings_for(CHANGELOG_KEY, ""))
    absent = real_build(settings_for(CHANGELOG_KEY, None))

    lines = not_configured_lines(empty.output, CHANGELOG_KEY)
    assert len(lines) == 1, f"expected exactly one 'not configured' line: {lines}"
    assert "[WARNING]" not in lines[0] and "warning" not in lines[0].lower()
    assert not_configured_lines(absent.output, CHANGELOG_KEY) == []


def test_two_empty_settings_give_two_statements():
    # covers: BP-1500h-1-ii
    # angle: boundary
    """changelog_categories_path and precommit_autofix_config_path both '':
    exactly two 'not configured' lines, one naming each. Control: one empty
    key gives one line (so the count tracks keys, not a fixed total)."""
    both = run_driver(
        {**settings_for(CHANGELOG_KEY, ""), **settings_for(PRECOMMIT_KEY, "")}
    )
    one = run_driver(settings_for(CHANGELOG_KEY, ""))

    changelog = not_configured_lines(both.output, CHANGELOG_KEY)
    precommit = not_configured_lines(both.output, PRECOMMIT_KEY)
    assert len(changelog) == 1 and len(precommit) == 1, (changelog, precommit)
    assert CHANGELOG_KEY in changelog[0] and PRECOMMIT_KEY in precommit[0]
    assert len(not_configured_lines(one.output, CHANGELOG_KEY)) == 1
    assert not_configured_lines(one.output, PRECOMMIT_KEY) == []
