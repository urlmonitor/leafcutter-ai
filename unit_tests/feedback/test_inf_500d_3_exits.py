"""
MODULE: test_inf_500d_3_exits
GOAL: AC INF-500d-3 tests for the failure exits of ``submit_feedback.py`` (writer, malformed, facility and
    destination paths), the set of emitted reasons, INF-500d-4-i's refusal-line count, and the parser errors.
    The contract is documented in ``test_inf_500d_3.py``; the shared helpers live in ``_inf_500d_3_support``.
"""
# @ac-tag: INF-500d-3

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Callable

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback import test_inf_500d_4_i as t4i
from unit_tests.feedback import test_inf_500d_4_i_feedback_sink_rule as sink_rule
from unit_tests.feedback._inf_500d_3_support import (
    _DEV_FULL,
    DESTINATION,
    FACILITY,
    MALFORMED,
    TICKET,
    Scn,
    _argv,
    _assert_reason,
    _bad_declaration,
    _exec,
    _human_lines,
    _kw,
    _layout,
    _load_vocab,
    _prep_sink_outside_root,
    _prep_stale_root,
    _reason_lines,
    _reasons,
    _run,
)


# ---------------------------------------------------------------------------
# 3-7: the failure exits
# ---------------------------------------------------------------------------

def test_writer_refusal_emits_one_writer_not_allowed_line_and_nothing_else_on_stdout(tmp_path):
    # covers: INF-500d-3
    # angle: discrimination
    """python-coder may not write subagent-quality: exactly one writer-not-allowed line, ERROR line kept."""
    lay = _layout(tmp_path)
    before = h.snapshot(tmp_path)

    proc = _run(lay, _argv(category="subagent-quality"))

    _assert_reason(proc, "writer-not-allowed", "subagent-quality")
    assert [line for line in _human_lines(proc) if "ERROR" in line], f"the human-readable ERROR stays: {proc.stderr!r}"
    assert not lay.sink.exists() and h.snapshot(tmp_path) == before, "a refused writer must write nothing"
    # Control: an allowed writer for the same category succeeds, so the refusal above is the writer rule's doing.
    allowed = _run(lay, _argv(category="subagent-quality", phase="ticket-supervisor"))
    assert allowed.returncode == 0 and not _reason_lines(allowed), allowed.stderr


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_every_malformed_submission_path_emits_malformed_submission_and_writes_nothing(tmp_path, case):
    # covers: INF-500d-3
    # angle: discrimination
    """Each malformed submission: one malformed-submission line, human text kept, nothing created."""
    lay = _layout(tmp_path)
    scn = MALFORMED[case]

    proc, before = _exec(lay, scn)

    _assert_reason(proc, "malformed-submission", scn.category, case)
    assert [line for line in _human_lines(proc) if re.search(r"error|usage", line, re.IGNORECASE)], (
        f"{case}: the human-readable ERROR or usage text stays beside the reason line: {proc.stderr!r}")
    assert not lay.sink.exists(), f"{case}: nothing may be written for a malformed submission"
    assert h.snapshot(tmp_path) == before, f"{case}: created {sorted(h.snapshot(tmp_path) - before)}"


@pytest.mark.parametrize("case", sorted(FACILITY))
def test_missing_pyyaml_and_an_unusable_categories_file_each_emit_facility_unavailable_without_a_traceback(
    tmp_path, case,
):
    # covers: INF-500d-3
    # angle: discrimination
    """PyYAML missing, or a categories file absent / unparseable / empty: facility-unavailable, no traceback."""
    lay = _layout(tmp_path)

    proc, before = _exec(lay, FACILITY[case])

    _assert_reason(proc, "facility-unavailable", "complete", case)
    assert not lay.sink.exists(), f"{case}: no built-in category list may stand in and write a report"
    assert h.snapshot(tmp_path) == before, f"{case}: nothing may be created"
    if case == "categories_file_absent":
        assert "Checked path:" in proc.stderr and "To fix:" in proc.stderr, (
            f"the INF-100c-4 Checked path / To fix lines stay for the absent file: {proc.stderr!r}")


@pytest.mark.parametrize("case", sorted(DESTINATION))
def test_every_destination_failure_path_emits_destination_unwritable(tmp_path, case):
    # covers: INF-500d-3
    # angle: discrimination
    """Each way the destination cannot be written: one destination-unwritable line, no traceback, nothing early."""
    if case == "jsonl_is_dev_full_append_fails" and not os.path.exists(_DEV_FULL):
        pytest.skip("/dev/full is absent on this platform")
    lay = _layout(tmp_path)

    proc, before = _exec(lay, DESTINATION[case])

    _assert_reason(proc, "destination-unwritable", "complete", case)
    assert h.snapshot(tmp_path) == before, f"{case}: a refused destination must create nothing: {sorted(h.snapshot(tmp_path) - before)}"


# ---------------------------------------------------------------------------
# 13-14: the set as a whole
# ---------------------------------------------------------------------------

def test_every_emitted_reason_is_a_vocabulary_member_and_every_script_detected_reason_is_emitted(tmp_path):
    # covers: INF-500d-3
    # angle: discrimination
    """Across every exit path: emitted reasons are members, script-detected ones are all emitted, no traceback."""
    vocab = _load_vocab(_layout(tmp_path / "probe").out_root)
    members = {r["id"]: r for r in _reasons(vocab)}
    matrix: dict[str, tuple[Scn, str | None]] = {"writer": (Scn(argv=_kw(category="subagent-quality")), None)}
    for name in ("unrecognised_category", "tag_starts_with_a_digit", "parser_missing_phase", "agent_source_without_ticket"):
        matrix[name] = (MALFORMED[name], None)
    for name in FACILITY:
        matrix[name] = (FACILITY[name], "facility-unavailable")
    for name in ("declaration_absent", "stale_enduring_root", "jsonl_names_a_directory", "jsonl_parent_is_a_regular_file"):
        matrix[name] = (DESTINATION[name], None)

    emitted: dict[str, set[str]] = {}
    for name, (scn, _expect) in matrix.items():
        lay = _layout(tmp_path / name)
        proc, _before = _exec(lay, scn)
        assert "Traceback" not in proc.stderr, f"{name}: ended in a traceback: {proc.stderr!r}"
        lines = _reason_lines(proc)
        assert len(lines) == 1, f"{name}: every exit path must emit exactly one reason line: {proc.stderr!r}"
        emitted.setdefault(lines[0].split(":")[1], set()).add(name)

    assert set(emitted) <= set(members), f"reasons outside the vocabulary: {sorted(set(emitted) - set(members))}"
    script_detected = {rid for rid, r in members.items() if r["detected_by"] == "script"}
    assert script_detected <= set(emitted), f"script-detected reasons no path emits: {sorted(script_detected - set(emitted))}"
    assert "written-uncited" not in emitted, "written-uncited is decided by the caller, never by the script on a failed run"
    assert "facility-unavailable" in emitted, "the PyYAML and categories-file paths are script-decided facility failures"


# ---------------------------------------------------------------------------
# 15-16: INF-500d-4-i's refusal-line count
# ---------------------------------------------------------------------------

def _synthetic(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["synthetic"], returncode=1, stdout="", stderr=stderr)


def test_refusal_line_helper_excludes_exactly_one_submit_failed_line_and_stderr_lines_keeps_its_meaning():
    # covers: INF-500d-3
    # angle: discrimination
    """refusal_lines drops at most one line that begins with submit-failed:; stderr_lines still returns everything."""
    cases = [
        ("human\nsubmit-failed:destination-unwritable:complete\n", 1),
        ("human one\nhuman two\nsubmit-failed:destination-unwritable:complete\n", 2),
        ("human\nsubmit-failed:a:b\nsubmit-failed:c:d\n", 2),
        ("submit-failed:destination-unwritable:complete\n", 0),
        ("  submit-failed:destination-unwritable:complete\n", 1),
        ("ERROR: see submit-failed:x:y for details\n", 1),
        ("human\n\n   \nsubmit-failed:a:b\n", 1),
        ("human one\nhuman two\n", 2),
        ("human\n", 1),
    ]
    for stderr, expected in cases:
        assert len(h.refusal_lines(_synthetic(stderr))) == expected, f"{stderr!r}: expected {expected}"
        assert h.stderr_lines(_synthetic(stderr)) == [line for line in stderr.splitlines() if line.strip()], (
            f"stderr_lines must keep returning every non-blank line: {stderr!r}")


def _append_to_failures(monkeypatch, extra: str) -> None:
    real = h.submit

    def wrapped(*args, **kwargs):
        proc = real(*args, **kwargs)
        if proc.returncode == 0:
            return proc
        return subprocess.CompletedProcess(proc.args, proc.returncode, proc.stdout, proc.stderr + extra)

    monkeypatch.setattr(h, "submit", wrapped)


def _four_i_cases(base: Path) -> list[Callable[[], None]]:
    paths = [base / name for name in ("absent", "bad", "stale", "sink")]
    for path in paths:
        path.mkdir(parents=True)
    return [
        lambda: t4i.test_absent_declaration_refuses_and_writes_no_file_anywhere(paths[0]),
        lambda: t4i.test_unreadable_keyless_or_relative_declaration_each_refuses(paths[1], "malformed_json"),
        lambda: t4i.test_stale_declaration_refuses_without_creating_the_enduring_root(paths[2]),
        lambda: sink_rule.test_submit_feedback_refuses_a_sink_that_is_not_directly_under_the_root(paths[3]),
    ]


def test_declared_sink_refusals_leave_one_human_line_plus_the_reason_line_and_the_4_i_assertions_stay_strict(
    tmp_path, monkeypatch,
):
    # covers: INF-500d-3
    # angle: criterion
    """Real refusals leave 2 raw stderr lines and 1 refusal line; the 4-i assertion sites accept exactly that."""
    declaration_re = {"absent": r"absent|not found|does not exist|no such file|no declaration",
                      "bad": r"unreadable|unparse?able|cannot be (?:read|parsed)|malformed|invalid json|could not parse",
                      "stale": r"no longer exists|does not exist", "sink": r"operational_log_root"}
    for name, condition in declaration_re.items():
        lay = _layout(tmp_path / f"real_{name}")
        if name == "absent":
            h.declaration_path(lay.out_root).unlink()
        elif name == "bad":
            _bad_declaration("malformed_json", lay.out_root)
        elif name == "stale":
            _prep_stale_root(lay)
        else:
            _prep_sink_outside_root(lay)
        before = h.snapshot(lay.base)

        proc = _run(lay, _argv())

        assert proc.returncode != 0 and proc.stdout == "", proc
        assert len(h.stderr_lines(proc)) == 2, f"{name}: one human refusal line plus the reason line: {proc.stderr!r}"
        human = h.refusal_lines(proc)
        assert len(human) == 1, f"{name}: exactly one human-readable refusal line: {human!r}"
        assert str(h.declaration_path(lay.out_root)) in human[0], f"{name}: the line names the declaration: {human[0]!r}"
        assert re.search(condition, h.without_paths(human[0], tmp_path), re.IGNORECASE), f"{name}: {human[0]!r}"
        assert h.snapshot(lay.base) == before and not lay.sink.exists(), f"{name}: nothing may be created"

    # The two INF-500d-4-i assertion sites, driven with the reason line appended, still pass ...
    # (the real script prints the reason line itself, so no synthetic line is added here)
    for run_case in _four_i_cases(tmp_path / "with_reason"):
        run_case()
    # ... and still fail when the extra line is anything else (a second line is not excused).
    _append_to_failures(monkeypatch, "unexpected extra line\n")
    for run_case in (_four_i_cases(tmp_path / "with_noise")[0], _four_i_cases(tmp_path / "with_noise2")[3]):
        with pytest.raises(AssertionError):
            run_case()


# ---------------------------------------------------------------------------
# 17: reachability
# ---------------------------------------------------------------------------

def test_submit_feedback_run_as_a_subprocess_emits_the_reason_line_on_a_real_failure(tmp_path):
    # covers: INF-500d-3
    # angle: reachability
    """Real argv, python -B, own sink: a refused writer and an undeclared sink each print the line; success none."""
    lay = _layout(tmp_path)

    refused = _run(lay, _argv(category="subagent-quality"))
    _assert_reason(refused, "writer-not-allowed", "subagent-quality", "refused writer")

    h.declaration_path(lay.out_root).unlink()
    undeclared = _run(lay, _argv())
    _assert_reason(undeclared, "destination-unwritable", "complete", "no sink declaration")

    h.declare(lay.out_root, lay.root)
    accepted = _run(lay, _argv())
    assert accepted.returncode == 0 and re.match(h.FEEDBACK_ID_RE, accepted.stdout.strip()), accepted.stderr
    assert not _reason_lines(accepted), f"a successful run carries no reason line: {accepted.stderr!r}"


@pytest.mark.parametrize(("value", "expected"), [("complete", "complete"), ("a:b", "-")])
def test_parser_error_with_the_equals_form_of_category_takes_the_category_from_raw_argv(tmp_path, value, expected):
    # covers: INF-500d-3
    # angle: discrimination
    """--category=<v> and no --phase: the parser fails; the category part comes from the raw argv, '-' if unrepresentable."""
    lay = _layout(tmp_path)
    argv = ["--ticket", TICKET, f"--category={value}", "--note", "probe"]

    proc = _run(lay, argv)

    _assert_reason(proc, "malformed-submission", expected, f"--category={value}")
    # Control: the two-token spelling of the same value reaches the same category part, so the equals branch is not a default.
    spaced = _run(lay, ["--ticket", TICKET, "--category", value, "--note", "probe"])
    _assert_reason(spaced, "malformed-submission", expected, f"--category {value}")
