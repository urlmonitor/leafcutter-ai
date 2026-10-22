"""
MODULE: unit_tests/commit_guardian/test_ge_134a_1_i.py
COVERS: GE-134a-1-i -- where a decision-history block starts and ends

GOAL: The six test_spec descriptors of GE-134a-1-i. The record's own fixture
    (_ge_134a_fixture.h_1_i_example) is: a comment mentioning DECISION
    HISTORY, the code line LABEL = "DECISION HISTORY", a 6-line block
    (heading, '=' rule line, 4 entries), then x = 1. It must measure 3.

RED TODAY: count_content_lines counts every comment line, so the 6 block
    lines are counted (the fixture measures 9). The whole-text-heading
    descriptor is a guard that holds today; it carries a control row (the
    exact heading followed by the same lines measures 0) that is red today.

DECISION HISTORY
- 2026-10-21 [test-writer/GE-134a-1-i]: Initial authoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as d2  # noqa: E402
import _ge_134a_fixture as fx  # noqa: E402

_RULE = "# " + "=" * 68


@pytest.fixture()
def ratchet():
    return fx.load_ratchet()


def _measure(ratchet, tmp_path: Path, name: str, lines: list[str]) -> int:
    return fx.measure_text(ratchet, tmp_path, name, "\n".join(lines) + "\n")


def test_ge_134a_1_i_a_mention_comment_and_a_label_line_are_counted(ratchet, tmp_path):
    # covers: GE-134a-1-i
    # angle: discrimination
    """The record's fixture measures 3, and each of the mention comment and
    the LABEL line is one of the counted lines: removing either drops the
    length by exactly one."""
    full = fx.h_1_i_example()
    assert fx.measure_text(ratchet, tmp_path, "full.py", full) == 3

    lines = full.splitlines()
    without_mention = [ln for ln in lines if ln != "# see DECISION HISTORY below for why"]
    without_label = [ln for ln in lines if not ln.startswith("LABEL = ")]
    assert len(without_mention) == len(lines) - 1
    assert len(without_label) == len(lines) - 1
    assert _measure(ratchet, tmp_path, "no_mention.py", without_mention) == 2
    assert _measure(ratchet, tmp_path, "no_label.py", without_label) == 2


def test_ge_134a_1_i_the_six_block_lines_are_not_counted(ratchet, tmp_path):
    # covers: GE-134a-1-i
    # angle: criterion
    """None of the six block lines is counted: the total is 3, not 9."""
    full = fx.h_1_i_example()
    assert len(full.splitlines()) == 9
    assert fx.pre_change_count(full) == 9
    assert fx.measure_text(ratchet, tmp_path, "full.py", full) == 3


def test_ge_134a_1_i_code_after_the_block_is_counted(ratchet, tmp_path):
    # covers: GE-134a-1-i
    # angle: discrimination
    """x = 1 directly after the last entry is counted; with a blank line and
    more code after it, every line after the block is counted."""
    assert fx.measure_text(ratchet, tmp_path, "direct.py", fx.h_1_i_example()) == 3

    longer = fx.h_1_i_example(trailing=["", "y = 2", "z = 3"])
    assert fx.measure_text(ratchet, tmp_path, "longer.py", longer) == 6


def test_ge_134a_1_i_only_a_whole_text_heading_starts_a_block(ratchet, tmp_path):
    # covers: GE-134a-1-i
    # angle: discrimination
    """'# DECISION HISTORY notes are below' plus three comment lines: all four
    are counted. Control row: the exact heading plus the same three lines is
    a block and measures 0."""
    followers = ["# first comment", "# - looks like an entry", "#   and a continuation"]
    near_miss = ["# DECISION HISTORY notes are below", *followers]
    assert _measure(ratchet, tmp_path, "near_miss.py", near_miss) == 4

    exact = ["# DECISION HISTORY", *followers]
    assert _measure(ratchet, tmp_path, "exact.py", exact) == 0


def test_ge_134a_1_i_a_rule_line_belongs_to_the_block_only_when_directly_above(ratchet, tmp_path):
    # covers: GE-134a-1-i
    # angle: discrimination
    """A '=' rule line directly above the heading is not counted; one
    separated from the heading by a blank line or a code line is counted."""
    block = ["# DECISION HISTORY", "# - entry one", "# - entry two"]
    assert _measure(ratchet, tmp_path, "direct.py", [_RULE, *block, "x = 1"]) == 1
    assert _measure(ratchet, tmp_path, "blank.py", [_RULE, "", *block, "x = 1"]) == 3
    assert _measure(ratchet, tmp_path, "code.py", [_RULE, "y = 0", *block, "x = 1"]) == 3


def test_ge_134a_1_i_a_file_that_is_only_a_history_block_measures_zero_and_is_not_refused(ratchet, tmp_path):
    # covers: GE-134a-1-i
    # angle: reachability
    """measure_current_length gives 0 for a file that is one history block,
    and the fixture copy of check_file_size.py, run as a subprocess on that
    staged file, exits 0 (not 1, not the INDETERMINATE exit 2) listing it at
    0 lines."""
    only_block = "\n".join(["# DECISION HISTORY", _RULE, *fx.history_entries("#", 4)]) + "\n"
    assert fx.measure_text(ratchet, tmp_path, "only_block.py", only_block) == 0

    root = tmp_path / "repo"
    root.mkdir()
    d2.build_fixture_tree(root, line_limit=5, checked_extensions=[".py"])
    result = fx.stage_and_check(root, "src/only_block.py", only_block)
    output = d2.combined_output(result)
    assert result.returncode == 0, output
    assert "INDETERMINATE" not in output
    assert "src/only_block.py (new, 0 lines - OK)" in output
