"""
MODULE: test_inf_500d_4_i_feedback_sink_rule
GOAL: RED tests for review-fix defect M-2 -- the feedback sink must obey the SAME usable-stream rule as
    the telemetry stream: a declared ``feedback_sink`` is usable only when the declaration also records
    an absolute ``operational_log_root`` and the sink sits DIRECTLY under it.
AC: INF-500d-4-i (the report sink refuses rather than quietly using a disposable location),
    INF-500d-4-iv (writers default to the declared root), INF-500d-4-v (readers read the declared sink
    and refuse with no usable declaration); ADR-069 section 4 ("one usable-stream rule").

THE DEFECT: ``sink_resolution.read_usable_stream`` is applied to the telemetry and knowledge streams
    but not to ``feedback_sink``. ``feedback_sink._failure`` and ``feedback_reader.resolve`` only ask
    for an absolute ``feedback_sink`` (plus, for the writer, an absolute root). A hand-written
    declaration that puts ``feedback_sink`` somewhere other than directly under
    ``operational_log_root`` therefore writes -- and is read -- at a location the root does not own,
    which is exactly the disposable-location problem the rule exists to prevent.

THE CONTRACT: for a hand-written declaration whose ``feedback_sink`` is NOT directly under
    ``operational_log_root`` --
      * ``submit_feedback.py`` refuses (non-zero, empty stdout, ONE stderr line naming the declaration
        and ``operational_log_root``) and creates nothing;
      * ``sink_resolution.py --print-location feedback`` refuses (exit 1, empty stdout, stderr naming
        ``operational_log_root``);
      * every reader (aggregate, list_tags, trend_report, resolve_feedback, link_feedback) refuses
        without reading or touching the sink it was misdirected to.
    A declaration the build helper writes (sink directly under the root) keeps working everywhere.

REAL-ARTIFACT NOTE: the declaration is the real build helper's output, round-tripped through
    ``h.rewrite_declaration`` to hand-write the one mismatching key. Records at the misdirected sink come
    from the REAL producer (``submit_feedback.py --jsonl``). Every command is the deployed script in a
    subprocess; nothing mocks a read or a write and no build.py is spawned.
"""
# @ac-tag: INF-500d-4-i
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import re
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_SEEDED = 3


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _install(base: Path, *, mismatch: bool) -> tuple[Path, Path, Path, Path]:
    """A declared install; with ``mismatch`` its ``feedback_sink`` is hand-moved OUT from under the root.

    Returns ``(project, out_root, sink, root)`` where ``sink`` is the file the declaration names and holds
    ``_SEEDED`` real reports.
    """
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    project = base / "wt"
    project.mkdir()
    out_root = h.deploy_install(project)
    h.declare(out_root, root)
    if mismatch:
        elsewhere = base / "elsewhere"
        elsewhere.mkdir()
        sink = elsewhere / "feedback.jsonl"
        h.rewrite_declaration(out_root, feedback_sink=str(sink))
    else:
        sink = root / "feedback.jsonl"
    h.seed_reports(out_root, project, _tmpdir(base), sink, _SEEDED, tag="seed",
                   category="subagent-quality", phase="ticket-supervisor")
    return project, out_root, sink, root


def _readers(out_root: Path, feedback_id: str) -> dict[str, tuple[Path, list[str]]]:
    feedback = out_root / "scripts" / "feedback"
    return {
        "aggregate": (feedback / "aggregate.py", ["--format", "json"]),
        "list_tags": (feedback / "list_tags.py", []),
        "trend_report": (out_root / "skills" / "feedback-analysis" / "scripts" / "trend_report.py", ["--format", "json"]),
        "resolve_feedback": (feedback / "resolve_feedback.py", ["--feedback-id", feedback_id]),
        "link_feedback": (feedback / "link_feedback.py", ["--feedback-id", feedback_id, "--ticket", "t.md"]),
    }


def test_submit_feedback_refuses_a_sink_that_is_not_directly_under_the_root(tmp_path):
    # covers: INF-500d-4-i
    # angle: failure
    """submit_feedback with a declared feedback_sink outside operational_log_root: non-zero, empty stdout, ONE
    stderr line naming the declaration and operational_log_root, and nothing written anywhere."""
    project, out_root, sink, root = _install(tmp_path, mismatch=True)
    cwd = project / "work"
    cwd.mkdir()
    tmpdir = _tmpdir(tmp_path)
    digest = h.sha256(sink)
    before = h.snapshot(tmp_path)

    proc = h.submit(out_root, cwd, tmpdir)

    assert proc.returncode != 0, f"a sink outside the root must be refused: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert proc.stdout == "", f"nothing may be printed on stdout (a caller would capture it as the id): {proc.stdout!r}"
    lines = h.stderr_lines(proc)
    assert len(lines) == 1, f"exactly one stderr line expected, got {lines!r}"
    assert str(h.declaration_path(out_root)) in lines[0], f"the line must name the declaration: {lines[0]!r}"
    assert "operational_log_root" in lines[0], f"the line must name the rule it broke: {lines[0]!r}"
    assert h.sha256(sink) == digest, "the report was appended to a sink the root does not own"
    assert h.snapshot(tmp_path) == before, "a refusal must create nothing"
    assert not (root / "feedback.jsonl").exists()


def test_print_location_feedback_refuses_a_sink_that_is_not_directly_under_the_root(tmp_path):
    # covers: INF-500d-4-i
    # covers: INF-500d-4-iv
    # angle: failure
    """`sink_resolution.py --print-location feedback` answers nothing (exit 1, empty stdout) for the mismatching
    declaration, naming operational_log_root; the root and a well-formed declaration still print."""
    project, out_root, _sink, root = _install(tmp_path, mismatch=True)
    tmpdir = _tmpdir(tmp_path)
    script = out_root / "scripts" / "knowledge" / "sink_resolution.py"

    refused = h.run_py(script, ["--print-location", "feedback"], project, tmpdir)

    assert refused.returncode == 1, f"expected exit 1, got {refused.returncode}: stdout={refused.stdout!r}"
    assert refused.stdout == "", f"nothing may be printed on stdout: {refused.stdout!r}"
    assert "operational_log_root" in refused.stderr, f"stderr must name the rule: {refused.stderr!r}"
    assert str(h.declaration_path(out_root)) in refused.stderr

    # Controls: the root itself still answers for this declaration, and a well-formed declaration answers `feedback`.
    root_answer = h.run_py(script, ["--print-location", "root"], project, tmpdir)
    assert root_answer.returncode == 0 and root_answer.stdout.strip() == str(root), root_answer.stderr
    good_base = tmp_path / "good"
    good_base.mkdir()
    good_project, good_out, good_sink, _good_root = _install(good_base, mismatch=False)
    good = h.run_py(good_out / "scripts" / "knowledge" / "sink_resolution.py", ["--print-location", "feedback"],
                    good_project, _tmpdir(good_base))
    assert good.returncode == 0 and good.stdout.strip() == str(good_sink), good.stderr


@pytest.mark.parametrize("reader", ["aggregate", "list_tags", "trend_report", "resolve_feedback", "link_feedback"])
def test_every_feedback_reader_refuses_a_sink_that_is_not_directly_under_the_root(tmp_path, reader):
    # covers: INF-500d-4-v
    # angle: failure
    """Each reader pointed (by declaration alone) at a sink outside the root exits non-zero, states no
    'read N records', names the declaration and operational_log_root, and leaves the misdirected sink byte for
    byte untouched. The same reader reads a well-formed declaration (the control), so the refusal is the
    mismatch's doing."""
    bad_base = tmp_path / "bad"
    bad_base.mkdir()
    project, out_root, sink, _root = _install(bad_base, mismatch=True)
    tmpdir = _tmpdir(bad_base)
    feedback_id = h.read_records(sink)[0]["feedback_id"]
    script, args = _readers(out_root, feedback_id)[reader]
    digest = h.sha256(sink)
    before = h.snapshot(bad_base)

    proc = h.run_py(script, args, project, tmpdir)

    assert proc.returncode != 0, f"{reader}: must refuse a sink outside the root: stdout={proc.stdout[:200]!r} stderr={proc.stderr!r}"
    assert not re.search(r"read \d+ records?", proc.stderr), f"{reader}: it read the misdirected sink: {proc.stderr!r}"
    assert str(h.declaration_path(out_root)) in proc.stderr, f"{reader}: stderr must name the declaration: {proc.stderr!r}"
    assert "operational_log_root" in proc.stderr, f"{reader}: stderr must name the rule it broke: {proc.stderr!r}"
    assert proc.stdout.strip() == "", f"{reader}: a refusal prints no report: {proc.stdout[:200]!r}"
    assert h.sha256(sink) == digest, f"{reader}: touched the misdirected sink"
    assert h.snapshot(bad_base) == before, f"{reader}: a refusal must create nothing"

    good_base = tmp_path / "good"
    good_base.mkdir()
    good_project, good_out, good_sink, _good_root = _install(good_base, mismatch=False)
    good_id = h.read_records(good_sink)[0]["feedback_id"]
    good_script, good_args = _readers(good_out, good_id)[reader]
    ok = h.run_py(good_script, good_args, good_project, _tmpdir(good_base))
    assert ok.returncode == 0, f"{reader}: control failed on a well-formed declaration: {ok.stderr!r}"
    assert re.search(rf"read {_SEEDED} records? from {re.escape(str(good_sink))}", ok.stderr), (
        f"{reader}: control must state the declared sink: {ok.stderr!r}")
