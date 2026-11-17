"""
MODULE: test_inf_500d_3_iv
GOAL: RED tests for AC INF-500d-3-iv -- an agent that cannot find its own recovery file records that
    the id was not captured, never the newest id it can find in the shared temporary directory.
AC: INF-500d-3-iv (source_ac); depends on INF-500d-3 (the closed reason set) and INF-500d-3-ii
    (per-run error files).

CONTRACT THIS FILE FIXES (llm-expert edits the signoff skill and live-surface-tester against it):

    1. live-surface-tester's own fenced capture block (the one that runs submit_feedback.py and sets
       ``FB_ID``) is run as written with bash. When the own error file holds no recovery line, or names a
       recovery file that is missing or empty, ``FB_ID`` ends as a reasoned marker
       ``(submit-failed:<reason>:<category>)``, <reason> a member of the delivered vocabulary:
       ``written-uncited`` (with the block's own category) whenever a ``sidecar:`` line was announced.
       The block's last exit status is 0.
    2. Neither instruction names a step that lists, globs, sorts or finds recovery files in the shared
       temporary directory, takes "the newest" or "the first" one, or relies on ``head -1`` first-match-wins.
    3. signoff Call 2 reads only the run's own per-run error file.

The prompt text comes from the DEPLOYED copies in the shared reference layout (no build.py here).
"""
# @ac-tag: INF-500d-3-iv

from __future__ import annotations

import os
import re

import pytest

from unit_tests.feedback import _inf_500d_3_helpers as h3
from unit_tests.feedback._inf_500d_3_ii_check import RUN_A, fill, redirects, searches
from unit_tests.feedback._inf_500d_3_ii_run import error_file, run_shell, search_command
from unit_tests.feedback._inf_500d_3_marker import (
    DECOY_NEWEST_ID,
    lift_capture_block,
    plant_decoys,
    reason_ids,
    run_block,
    set_stub,
    vocabulary,
)
from unit_tests.feedback._inf_500d_4_vi_helpers import _all_deployed_surfaces

pytestmark = pytest.mark.shared_layout_reader

SIGNOFF = "skills/signoff/SKILL.md"
LIVE = "agents/live-surface-tester.md"
ERROR_LINE = "ERROR: destination could not be written"
NAMED = "feedback_id_555.txt"

_MUTANTS = {
    "a fallback that takes the newest feedback_id file in the temporary directory":
        'FB_ID=$(cat "$(ls -t "$TMPDIR"/feedback_id_*.txt | head -1)")',
    "a fallback that globs feedback_id_*.txt and takes the first match":
        'for f in "$TMPDIR"/feedback_id_*.txt; do FB_ID=$(cat "$f"); break; done',
    "a head -1 over a search that can see another agent's file":
        "FB_ID=$(grep -h -o 'sidecar:[^ ]*' \"$TMPDIR\"/feedback_err_*.txt | sed 's/sidecar://' | head -1)\n"
        'FB_ID=$(cat "$FB_ID")',
    "a recipe that falls through to a directory search when the named file is empty":
        f'FB_ID=$(cat "$TMPDIR/{NAMED}")\n[ -z "$FB_ID" ] && FB_ID=$(cat "$(ls -t "$TMPDIR"/feedback_id_*.txt | head -1)")',
}
_SHARED_DIR_STEPS = {
    "ls over recovery files": re.compile(r"\bls\s[^\n]*feedback_id"),
    "find over the temporary directory": re.compile(r"(?m)^\s*(?:\$\s+)?find\s[^\n]*(?:/tmp|TMPDIR|feedback_id)"),
    "glob of recovery files by name": re.compile(r"(?:/tmp|\$\{?TMPDIR\}?)/feedback_id_[^\s'\"]*[*?\[]"),
    "newest or first recovery file": re.compile(
        r"(?i)\b(newest|latest|most recent|first)\b[^\n.]{0,50}\b(recovery file|feedback_id|sidecar)"
        r"|\b(recovery file|feedback_id|sidecar)[^\n.]{0,40}\b(newest|latest|most recent)\b"),
    "modification time": re.compile(r"(?i)\b(mtime|modification time|modified time)\b"),
    "first match wins": re.compile(r"\|\s*head\s+-(?:n\s*)?1\b"),
}


def _surfaces(layout) -> dict[str, str]:
    return _all_deployed_surfaces(layout)


def _the_block(layout) -> str:
    blocks = lift_capture_block(_surfaces(layout)[LIVE])
    assert len(blocks) == 1, f"live-surface-tester must carry exactly one executable capture block, found {len(blocks)}"
    return blocks[0]


def _own_category(block: str) -> str:
    match = re.search(r"--category\s+(\S+)", fill(block, RUN_A))
    assert match, "the capture block names no --category"
    return match.group(1)


def _marker_problems(fb: str, layout) -> list[str]:
    """Why ``fb`` is not a failure marker whose reason is in INF-500d-3's closed set (and holds no id)."""
    problems = []
    match = re.fullmatch(vocabulary(layout)["patterns"]["reasoned_marker"], fb)
    if not match:
        problems.append(f"FB_ID {fb!r} is not a reasoned marker (submit-failed:<reason>:<category>)")
    elif match.group(1) not in reason_ids(layout):
        problems.append(f"reason {match.group(1)!r} is not in the vocabulary {reason_ids(layout)}")
    if "fb_" in fb:
        problems.append(f"FB_ID {fb!r} holds an id")
    return problems


def _mutant_value(script: str, layout) -> str:
    return run_shell(script + "\nprintf '%s' \"$FB_ID\"\n", layout).stdout


def _assert_mutants_flagged(layout, *, only: tuple[str, ...] = ()) -> None:
    """Positive controls: every wrong version leaves an id in FB_ID, which the same predicate flags."""
    for label, script in _MUTANTS.items():
        if only and label not in only:
            continue
        value = _mutant_value(script, layout)
        assert "fb_" in value, f"control row broken: the wrong recipe {label!r} recorded {value!r}, not a decoy id"
        assert _marker_problems(value, layout), f"the judge is blind to: {label}"


def _run_named(layout, block: str, *, recovery: str | None):
    """Run the block against an entry point that exits non-zero and announces the recovery file NAMED."""
    path = layout.tmpdir / NAMED
    path.unlink(missing_ok=True)
    if recovery is not None:
        path.write_text(recovery, encoding="utf-8")
    set_stub(layout, [ERROR_LINE, f"sidecar:{path}"], 1)
    return run_block(block, layout)


# ---------------------------------------------------------------------------
# the own error file holds no recovery line
# ---------------------------------------------------------------------------

def test_capture_block_records_a_closed_set_failure_marker_when_the_own_error_file_has_no_recovery_line(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: criterion
    """FB_ID is a reasoned marker from the vocabulary, with decoys planted, and the block ends with status 0."""
    block = _the_block(shared_reference_layout)
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    for label, lines, rc in (("failure line", [ERROR_LINE, f"submit-failed:destination-unwritable:{_own_category(block)}"], 1),
                             ("nothing on stderr", [], 2)):
        set_stub(layout, lines, rc)
        status, fb = run_block(block, layout)
        assert status == 0, f"{label}: the capture block ended with status {status} (it must fail open)"
        assert not _marker_problems(fb, layout), f"{label}: {_marker_problems(fb, layout)}"


def test_capture_block_never_records_a_decoy_id_from_the_shared_temporary_directory(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: discrimination
    """The newest decoy holds fb_2026-08-25_9057159a; FB_ID holds no id at all and is still the marker."""
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    _assert_mutants_flagged(layout, only=tuple(list(_MUTANTS)[:3]))
    block = _the_block(shared_reference_layout)
    for lines in ([ERROR_LINE], []):
        set_stub(layout, lines, 1)
        _status, fb = run_block(block, layout)
        assert DECOY_NEWEST_ID not in fb, f"the decoy id was recorded: {fb!r}"
        assert "fb_" not in fb, f"an id that is not this run's was recorded: {fb!r}"
        assert not _marker_problems(fb, layout), _marker_problems(fb, layout)


def test_signoff_recovery_step_returns_nothing_foreign_when_the_own_error_file_has_no_recovery_line(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: discrimination
    """Signoff Call 2, run as written against the run's own error file (no sidecar line), finds nothing."""
    text = _surfaces(shared_reference_layout)[SIGNOFF]
    (red, *_), (find, *_) = redirects(SIGNOFF, text), searches(SIGNOFF, text)
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    own = error_file(red, RUN_A, layout)
    own.write_text(f"{ERROR_LINE}\n", encoding="utf-8")
    shared = run_shell("grep -o 'sidecar:[^ ]*' \"$TMPDIR\"/feedback_err_*.txt", layout)
    assert shared.stdout.strip(), "control: a search over the shared directory must see the decoy"
    found = run_shell(search_command(find, RUN_A, layout), layout)
    assert found.stdout == "", f"Call 2 returned a line although the own error file holds none: {found.stdout!r}"


# ---------------------------------------------------------------------------
# no step lists, sorts or searches the shared temporary directory
# ---------------------------------------------------------------------------

def _shared_dir_offences(text: str) -> list[str]:
    return [f"{label}: {m.group(0).strip()[:90]!r}" for label, rule in _SHARED_DIR_STEPS.items()
            for m in rule.finditer(text)]


def test_signoff_and_live_surface_tester_contain_no_step_that_lists_sorts_or_searches_the_shared_temp_directory(
        shared_reference_layout):
    # covers: INF-500d-3-iv
    # angle: discrimination
    """Synthetic positive controls fire; the deployed signoff skill and live-surface-tester carry no such step."""
    controls = ("ls -t /tmp/feedback_id_*.txt",
                "If your own recovery file is missing, take the newest recovery file in the temporary directory.",
                "find /tmp -name 'feedback_id_*.txt'",
                "grep -o 'sidecar:[^ ]*' /tmp/feedback_err_x.txt | head -1")
    for planted in controls:
        assert _shared_dir_offences(planted), f"the scan is blind to: {planted!r}"
    own_search = "grep -o 'sidecar:[^ ]*feedback_id_[0-9]*.txt' /tmp/feedback_err_<ticket_basename>_<agent_name>.txt"
    assert not _shared_dir_offences(own_search), "the scan flags the search of the run's own error file"

    surfaces = _surfaces(shared_reference_layout)
    offences = [f"{rel}: {o}" for rel in (SIGNOFF, LIVE) for o in _shared_dir_offences(surfaces[rel])]
    assert not offences, "\n  ".join(["a step lists, sorts, searches or takes the first/newest recovery file:", *offences])


# ---------------------------------------------------------------------------
# the named recovery file is missing or empty
# ---------------------------------------------------------------------------

def test_capture_block_records_written_but_not_captured_when_the_named_recovery_file_is_missing(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: criterion
    """The error file names a recovery file that does not exist; decoys present; FB_ID is the written-uncited marker."""
    block = _the_block(shared_reference_layout)
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    status, fb = _run_named(layout, block, recovery=None)
    assert fb == f"(submit-failed:written-uncited:{_own_category(block)})", f"recorded {fb!r}"
    assert status == 0


def test_capture_block_records_written_but_not_captured_when_the_named_recovery_file_is_empty(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: criterion
    """Same run with the named recovery file present but empty; FB_ID is the marker and no other id."""
    block = _the_block(shared_reference_layout)
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    status, fb = _run_named(layout, block, recovery="")
    assert fb == f"(submit-failed:written-uncited:{_own_category(block)})", f"recorded {fb!r}"
    assert "fb_" not in fb
    assert status == 0


def test_missing_or_empty_named_recovery_file_never_yields_another_id(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: discrimination
    """Missing, then empty, with decoys: FB_ID holds no fb_ id; the wrong recipes are flagged by the same judge."""
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    path = layout.tmpdir / NAMED
    path.write_text("", encoding="utf-8")
    os.utime(path, (1_600_000_000, 1_600_000_000))  # the oldest file, so `ls -t` still picks a decoy
    _assert_mutants_flagged(layout)
    block = _the_block(shared_reference_layout)
    for label, recovery in (("missing", None), ("empty", "")):
        _status, fb = _run_named(layout, block, recovery=recovery)
        assert "fb_" not in fb, f"{label} recovery file: another id was recorded: {fb!r}"
        assert not _marker_problems(fb, layout), f"{label} recovery file: {_marker_problems(fb, layout)}"


@pytest.mark.parametrize("category", ["blocker", "tooling-issue"])
def test_capture_block_fallback_markers_carry_the_category_the_block_submits_under(
        shared_reference_layout, tmp_path, category):
    # covers: INF-500d-3-iv
    # angle: discrimination
    """The same file submits under complete, blocker and tooling-issue; the fallback markers must follow, not say 'complete'."""
    block = _the_block(shared_reference_layout)
    assert "--category complete" in block or "<category>" in block, "the block names no category to swap"
    swapped = block.replace("<category>", category).replace("--category complete", f"--category {category}")
    layout = h3.make_layout(tmp_path)
    plant_decoys(layout)
    missing = layout.tmpdir / NAMED
    sink = f"[submit_feedback] sink: {layout.tmpdir}/feedback.jsonl"
    scenarios = (("named file missing", [ERROR_LINE, f"sidecar:{missing}"], 1, "written-uncited"),
                 ("sink line only", [sink], 1, "written-uncited"),
                 ("nothing on stderr", [], 2, "facility-unavailable"))
    problems = []
    for label, lines, rc, reason in scenarios:
        missing.unlink(missing_ok=True)
        set_stub(layout, lines, rc)
        status, fb = run_block(swapped, layout)
        expected = f"(submit-failed:{reason}:{category})"
        if fb != expected:
            problems.append(f"{label}: recorded {fb!r}, expected {expected!r}")
        if status != 0:
            problems.append(f"{label}: the block ended with status {status}")
    assert not problems, "\n  ".join(problems)


# ---------------------------------------------------------------------------
# reachability: the happy path stays intact
# ---------------------------------------------------------------------------

def test_live_surface_tester_capture_block_is_reachable_as_a_bash_command(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iv
    # angle: reachability
    """The deployed block, run with bash against the real submit_feedback.py and a declared sink, yields its own id."""
    block = _the_block(shared_reference_layout)
    layout = h3.make_layout(tmp_path)
    status, fb = run_block(block, layout)
    assert status == 0
    assert h3.ID_RE.fullmatch(fb), f"FB_ID is not an id: {fb!r}"
    assert [r["feedback_id"] for r in h3.records(layout)] == [fb], "FB_ID is not the id of the record the run wrote"
