"""
MODULE: test_inf_500d_4_iv_gemini_copies
GOAL: RED tests for review-fix defect H-4 -- the Gemini copies of the drive-written-log tools resolve the
    install's declaration from the wrong directory.
AC: INF-500d-4-iv (writers default to the declared root: emit_event, inline_work_guard),
    INF-500d-4-v (readers read the declared sink and state it: trend_report); ADR-069.

THE DEFECT: the build copies three of these tools under ``.leafcutter/gemini/`` verbatim:
    ``gemini/skills/agent-telemetry/scripts/emit_event.py``,
    ``gemini/skills/feedback-analysis/scripts/trend_report.py`` and
    ``gemini/hooks/inline_work_guard.py``. Each computes the install root from its own resolved
    location with a fixed ``parents[N]`` that is right one directory higher (the ``.claude`` / ``skills``
    / ``hooks`` layout) and lands in ``.leafcutter/gemini/`` -- a directory with no ``config/`` and no
    ``scripts/``. So on Gemini:
      * ``trend_report`` dies with ``ModuleNotFoundError: feedback_reader`` (a REGRESSION: main's copy ran);
      * ``emit_event`` always finds no declaration and drops every event;
      * ``inline_work_guard`` never finds a declaration and writes no audit record.

THE CONTRACT: run from the way Gemini reaches them (``.gemini/...``, a symlink to ``.leafcutter/gemini``),
    each Gemini copy behaves exactly as its ``.claude`` twin does against the same declaration:
    trend_report reads and states the declared sink; emit_event appends to the declared stream;
    inline_work_guard audits under the declared root. Each test runs the Claude route FIRST against the same
    install (the control), so the counts below prove the Gemini copy added its own record to the SAME file.

REAL-ARTIFACT NOTE: the files under test are the REAL deployed Gemini copies from the shared reference
    layout (marker ``shared_layout_reader``), copied verbatim with symlinks kept -- the established way for
    a reader to run the deployed files (see ``test_inf_500d_4_iv.py``) -- and re-declared with the real
    build helper so the declared location is an absolute path that exists. Records come from the real
    producer. No build.py is spawned.
"""
# @ac-tag: INF-500d-4-iv
# @ac-tag: INF-500d-4-v

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_LOCK = ".build-feature.lock"

pytestmark = pytest.mark.shared_layout_reader


def _gemini_install(layout: Path, base: Path) -> tuple[Path, Path, Path]:
    """A verbatim copy of the real deployed install, declared with the real helper.

    Returns ``(project, out_root, log_root)``; ``.gemini`` is the same relative symlink the build lays down.
    """
    project = base / "proj"
    project.mkdir()
    real = Path(layout)
    shutil.copytree(real / ".leafcutter", project / ".leafcutter", symlinks=True)
    shutil.copytree(real / ".claude", project / ".claude", symlinks=True)
    os.symlink(".leafcutter/gemini", project / ".gemini")
    (project / ".git").write_text("gitdir: /nonexistent/worktree-gitdir\n", encoding="utf-8")
    out_root = project / ".leafcutter"
    log_root = base / "enduring" / "logs"
    log_root.mkdir(parents=True)
    h.declare(out_root, log_root)
    assert (project / ".gemini" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py").is_file(), (
        "fixture: the real layout must carry the Gemini emit_event.py")
    return project, out_root, log_root


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def test_gemini_trend_report_runs_and_reads_the_declared_sink(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-v
    # angle: deployed
    """Gemini's trend_report starts (no ModuleNotFoundError: feedback_reader), reads the declared feedback sink
    and says so on stderr, exactly as the Claude copy does against the same install."""
    project, out_root, log_root = _gemini_install(shared_reference_layout, tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = log_root / "feedback.jsonl"
    h.seed_reports(out_root, project, tmpdir, sink, 3, tag="declared", category="subagent-quality", phase="ticket-supervisor")

    claude = h.run_py(project / ".claude" / "skills" / "feedback-analysis" / "scripts" / "trend_report.py",
                      ["--format", "json"], project, tmpdir)
    assert claude.returncode == 0, f"control failed (the Claude copy must read the declared sink): {claude.stderr!r}"

    gemini = h.run_py(project / ".gemini" / "skills" / "feedback-analysis" / "scripts" / "trend_report.py",
                      ["--format", "json"], project, tmpdir)

    assert "ModuleNotFoundError" not in gemini.stderr, (
        f"the Gemini copy resolved the install root one directory too low:\n{gemini.stderr}")
    assert gemini.returncode == 0, f"Gemini trend_report failed: {gemini.stderr!r}"
    assert re.search(rf"read 3 records? from {re.escape(str(sink))}", gemini.stderr), (
        f"it must state the declared sink it read: {gemini.stderr!r}")
    assert json.loads(gemini.stdout)["summary"]["total_entries"] == 3
    assert json.loads(gemini.stdout) == json.loads(claude.stdout), "the two copies must report the same corpus"


def test_gemini_emit_event_writes_to_the_declared_stream(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-iv
    # angle: deployed
    """Gemini's emit_event appends to the declared telemetry stream (it drops every event today), landing in the
    same file the Claude copy writes; nothing is created under the project."""
    project, out_root, log_root = _gemini_install(shared_reference_layout, tmp_path)
    tmpdir = _tmpdir(tmp_path)
    stream = log_root / "agent_telemetry.jsonl"
    before = h.snapshot(project)

    claude = h.run_py(project / ".claude" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py",
                      h.emit_args(agent="claude-route"), project, tmpdir)
    assert claude.returncode == 0 and stream.is_file(), f"control failed: {claude.stderr!r}"

    gemini = h.run_py(project / ".gemini" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py",
                      h.emit_args(agent="gemini-route"), project, tmpdir)

    assert gemini.returncode == 0, gemini.stderr
    assert "no usable build-time declaration" not in gemini.stderr, (
        f"the Gemini copy looked for the declaration one directory too low: {gemini.stderr!r}")
    agents = [r["agent_name"] for r in h.read_records(stream)]
    assert agents == ["claude-route", "gemini-route"], f"the Gemini event must join the declared stream: {agents}"
    assert h.snapshot(project) == before, "something was written under the project"


def test_gemini_inline_work_guard_audits_under_the_declared_root(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-iv
    # angle: deployed
    """With the lock present, the Gemini guard still blocks (exit 2) and now appends its audit record under the
    declared operational_log_root, beside the Claude copy's record; no warning that the declaration is missing."""
    project, out_root, log_root = _gemini_install(shared_reference_layout, tmp_path)
    tmpdir = _tmpdir(tmp_path)
    (project / _LOCK).write_text("locked\n", encoding="utf-8")
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(project / "work" / "x.py")}})
    audit = log_root / "inline_work_guard.jsonl"

    claude = h.run_py(project / ".claude" / "hooks" / "inline_work_guard.py", [], project, tmpdir, stdin=payload)
    assert claude.returncode == 2 and audit.is_file(), f"control failed: rc={claude.returncode} {claude.stderr!r}"

    gemini = h.run_py(project / ".gemini" / "hooks" / "inline_work_guard.py", [], project, tmpdir, stdin=payload)

    assert gemini.returncode == 2, f"the Gemini guard must keep its own verdict: rc={gemini.returncode} {gemini.stderr!r}"
    assert "no usable build-time declaration" not in gemini.stderr, (
        f"the Gemini copy looked for the declaration one directory too low: {gemini.stderr!r}")
    assert [r["tool_name"] for r in h.read_records(audit)] == ["Write", "Write"], (
        "the Gemini guard's audit record must land in the declared root beside the Claude copy's")
    assert list(project.rglob("inline_work_guard.jsonl")) == [], "an audit file exists beneath the workspace"
