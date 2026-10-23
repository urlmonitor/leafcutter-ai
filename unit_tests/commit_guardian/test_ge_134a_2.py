"""
MODULE: unit_tests/commit_guardian/test_ge_134a_2.py
COVERS: GE-134a-2 -- growing a file's decision-history block never counts as
    growth, for the growth ratchet and the limit-crossing check alike

GOAL: The four test_spec descriptors of GE-134a-2, against real fixture git
    repositories built by _ge_127d_2_fixture.build_fixture_tree (a copy of
    the production modules -- no build.py, no POSIX flock). The committed
    state is landed with commit_bypassing_hook before any hook exists.

RED TODAY: both the previous (HEAD blob) and current lengths count the
    history block, and count_added_measured_lines counts appended entry
    lines as added measured lines, so a history-only append to an oversized
    file is refused as growth and a history-only append to a 399-line file
    is judged against a length above 400.

DECISION HISTORY
- 2026-10-21 [test-writer/GE-134a-2]: Initial authoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as d2  # noqa: E402
import _ge_134a_fixture as fx  # noqa: E402

_JS_PATH = "workflows/body.js"
_PY_PATH = "src/near_limit.py"


def _js_body(extra_entries: int = 0, extra_code: bool = False) -> str:
    """A JavaScript body measuring 1,400 lines plus a trailing '//' block of
    a heading and 5 entries (+ *extra_entries* appended entries)."""
    code = ["const extra = 1;"] if extra_code else []
    body = fx.body_lines(1400, "//", "const value_{i} = {i};")
    block = ["// DECISION HISTORY", *fx.history_entries("//", 5 + extra_entries)]
    return "\n".join([*code, *body, *block]) + "\n"


def _py_body(extra_entries: int = 0) -> str:
    """A Python file measuring 399 lines plus a trailing '#' block of a
    heading and 1 entry (+ *extra_entries* appended entries)."""
    body = fx.body_lines(399, "#")
    block = ["# DECISION HISTORY", *fx.history_entries("#", 1 + extra_entries)]
    return "\n".join([*body, *block]) + "\n"


def _committed_js_repo(root: Path) -> None:
    d2.build_fixture_tree(root, line_limit=1000, checked_extensions=[".js"])
    fx.commit_setup(root, _JS_PATH, _js_body())


def test_ge_134a_2_history_only_append_to_an_oversized_js_body_commits(tmp_path):
    # covers: GE-134a-2
    # angle: reachability
    """Limit 1,000, committed body measuring 1,400: appending 3 entry lines
    and running the fixture copy of check_file_size.py exits 0, listing the
    file at 1,400 lines."""
    _committed_js_repo(tmp_path)
    result = fx.stage_and_check(tmp_path, _JS_PATH, _js_body(extra_entries=3))
    output = d2.combined_output(result)
    assert result.returncode == 0, output
    assert f"{_JS_PATH} (modified, 1400 lines - OK)" in output


def test_ge_134a_2_history_only_append_measures_1400_before_and_after(tmp_path, monkeypatch):
    # covers: GE-134a-2
    # angle: discrimination
    """get_previous_length on the committed blob and measure_current_length
    on the staged file both give 1,400, and resolve_added_measured_lines
    gives 0 for the 3 appended entry lines."""
    _committed_js_repo(tmp_path)
    d2.write_and_stage(tmp_path, _JS_PATH, _js_body(extra_entries=3))
    ratchet = fx.load_ratchet()
    monkeypatch.chdir(tmp_path)

    assert ratchet.get_previous_length(_JS_PATH) == 1400
    assert ratchet.measure_current_length(_JS_PATH) == 1400
    assert ratchet.resolve_added_measured_lines(_JS_PATH, ["HEAD"]) == 0


def test_ge_134a_2_history_plus_one_code_line_is_refused_stating_1400_and_1401(tmp_path):
    # covers: GE-134a-2
    # angle: criterion
    """The same 3-entry append plus 1 code line: the check exits 1 and the
    grew refusal states Previous length: 1400 and New length: 1401."""
    _committed_js_repo(tmp_path)
    result = fx.stage_and_check(tmp_path, _JS_PATH, _js_body(extra_entries=3, extra_code=True))
    output = d2.combined_output(result)
    assert result.returncode == 1, output
    assert "FILE GREW" in output, output
    assert d2.parse_grown_previous_and_new_length(output) == (1400, 1401), output


def test_ge_134a_2_history_append_to_a_399_line_python_file_does_not_cross_400(tmp_path):
    # covers: GE-134a-2
    # angle: discrimination
    """Limit 400, committed file measuring 399: appending 20 entry lines
    exits 0 with no too-large (or grew) refusal, listing the file at 399."""
    d2.build_fixture_tree(tmp_path, line_limit=400, checked_extensions=[".py"])
    fx.commit_setup(tmp_path, _PY_PATH, _py_body())
    result = fx.stage_and_check(tmp_path, _PY_PATH, _py_body(extra_entries=20))
    output = d2.combined_output(result)
    assert result.returncode == 0, output
    assert "FILE TOO LARGE" not in output
    assert "FILE GREW" not in output
    assert f"{_PY_PATH} (modified, 399 lines - OK)" in output
