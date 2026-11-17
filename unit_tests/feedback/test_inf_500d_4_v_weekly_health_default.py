"""
MODULE: test_inf_500d_4_v_weekly_health_default
GOAL: RED tests for review-fix defect M-1 -- ``weekly_health.py`` defaults to a worktree-relative telemetry
    stream, so in a worktree it quietly reports zero.
AC: INF-500d-4-v (readers default to the declared stream, state which file they read, and refuse -- never
    report a quiet zero -- when no usable declaration exists); ADR-069.

THE DEFECT: ``scripts/agent-health/weekly_health.py`` main() falls back to
    ``<repo>/debugging/logs/agent_telemetry.jsonl`` when ``--telemetry`` is not given. In a worktree that is a
    per-drive location that holds nothing, so the lane section reads "sink absent" / zero events while the
    drive's real stream sits in the declared root. Its sibling ``generate_health_report.py`` already resolves
    through ``feedback_reader.resolve`` and prints ``[generate_health_report] read N records from <path>``.

THE CONTRACT (the weekly report follows its sibling):
    * with a usable declaration and no ``--telemetry``, it reads ``operational_telemetry_stream`` and states
      ``read N records from <path>`` on stderr; the lane figures come from that stream, never from a decoy
      under the repository;
    * with no usable declaration (absent, or no ``operational_log_root``) and no ``--telemetry`` it refuses:
      non-zero, no report on stdout, stderr naming the declaration -- it does not report zero;
    * an explicit ``--telemetry`` is still honoured.

REAL-ARTIFACT NOTE: the DEPLOYED ``weekly_health.py`` runs as a subprocess against a real temporary git
    repository (``--repo``), a declaration written by the real build helper, and telemetry written by the real
    producer (``emit_event.py``). No build.py is spawned and nothing mocks a read.
"""
# @ac-tag: INF-500d-4-v

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_EVENTS = 3
_STAMP = "2026-08-18T12:00:00"


def _git_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(var, None)
    env.update({
        "HOME": str(home), "GIT_AUTHOR_DATE": _STAMP, "GIT_COMMITTER_DATE": _STAMP,
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    return env


def _git_repo(path: Path) -> Path:
    """A real one-commit repository, as weekly_health needs history to read."""
    path.mkdir()
    env = _git_env(path)
    (path / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "seed")):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True, env=env)
    return path


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _install(base: Path, *, declared: bool) -> tuple[Path, Path, Path | None]:
    """A worktree-shaped install; returns ``(project, out_root, log_root)`` (``log_root`` None when undeclared)."""
    project = base / "wt"
    project.mkdir()
    out_root = h.deploy_install(project)
    log_root = None
    if declared:
        log_root = base / "enduring" / "logs"
        log_root.mkdir(parents=True)
        h.declare(out_root, log_root)
    return project, out_root, log_root


def _emit(out_root: Path, cwd: Path, tmpdir: Path, count: int, *, log: Path | None = None) -> None:
    """File ``count`` lane-start events through the REAL producer (declared stream, or an explicit ``--log``)."""
    for _ in range(count):
        extra = ["--log", str(log)] if log is not None else []
        proc = h.run_py(h.emit_script(out_root), [*h.emit_args(agent="fast-lane", event="run_started"), *extra], cwd, tmpdir)
        assert proc.returncode == 0, proc.stderr


def _weekly(out_root: Path, repo: Path, cwd: Path, tmpdir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    script = out_root / "scripts" / "agent-health" / "weekly_health.py"
    args = ["--repo", str(repo), "--no-gh", "--weeks", "1", "--today", "2026-08-19", "--format", "json", *extra]
    return h.run_py(script, args, cwd, tmpdir)


def test_weekly_health_without_a_path_reads_the_declared_stream_and_states_it(tmp_path):
    # covers: INF-500d-4-v
    # angle: criterion
    """No --telemetry: the report reads the declared stream (N events from the real producer), prints
    'read N records from <path>', and ignores a decoy stream under the repository."""
    project, out_root, log_root = _install(tmp_path, declared=True)
    repo = _git_repo(tmp_path / "repo")
    tmpdir = _tmpdir(tmp_path)
    _emit(out_root, project, tmpdir, _EVENTS)
    stream = log_root / "agent_telemetry.jsonl"
    assert len(h.read_records(stream)) == _EVENTS, "fixture: the producer must have written the declared stream"
    decoy = repo / "debugging" / "logs" / "agent_telemetry.jsonl"
    decoy.parent.mkdir(parents=True)
    _emit(out_root, project, tmpdir, 1, log=decoy)  # one event where the old default looked

    proc = _weekly(out_root, repo, project, tmpdir)

    assert proc.returncode == 0, f"weekly_health failed: {proc.stderr!r}"
    stated = re.findall(r"read (\d+) records? from (\S+)", proc.stderr)
    assert stated, f"the report must state which file it read ('read N records from <path>'): {proc.stderr!r}"
    assert {(count, Path(path).resolve()) for count, path in stated} == {(str(_EVENTS), stream.resolve())}, (
        f"it must state the declared stream and its record count, got {stated}")
    lane = json.loads(proc.stdout)["lane"]
    assert lane["starts"] == _EVENTS, (
        f"the lane figures must come from the declared stream ({_EVENTS} starts), not the repo decoy (1): {lane}")
    assert lane["event_total"] == _EVENTS


@pytest.mark.parametrize("shape", ["no_declaration", "no_operational_log_root"])
def test_weekly_health_refuses_without_a_usable_declaration_instead_of_reporting_zero(tmp_path, shape):
    # covers: INF-500d-4-v
    # angle: failure
    """No usable declaration and no --telemetry: non-zero, nothing on stdout, stderr names the declaration. The old
    default 'worked' here by reading a stream under the repository; an explicit --telemetry still works."""
    project, out_root, log_root = _install(tmp_path, declared=(shape != "no_declaration"))
    if shape == "no_operational_log_root":
        h.rewrite_declaration(out_root, operational_log_root=None)
    repo = _git_repo(tmp_path / "repo")
    tmpdir = _tmpdir(tmp_path)
    decoy = repo / "debugging" / "logs" / "agent_telemetry.jsonl"
    decoy.parent.mkdir(parents=True)
    _emit(out_root, project, tmpdir, 1, log=decoy)

    proc = _weekly(out_root, repo, project, tmpdir)

    assert proc.returncode != 0, (
        f"with no usable declaration the report must refuse, not read the repository's own stream: "
        f"stdout={proc.stdout[:200]!r} stderr={proc.stderr!r}")
    assert proc.stdout.strip() == "", f"a refusal prints no report (a quiet zero): {proc.stdout[:200]!r}"
    assert str(h.declaration_path(out_root)) in proc.stderr, f"stderr must name the expected declaration: {proc.stderr!r}"

    explicit = tmp_path / "explicit" / "agent_telemetry.jsonl"
    _emit(out_root, project, tmpdir, 2, log=explicit)
    ok = _weekly(out_root, repo, project, tmpdir, "--telemetry", str(explicit))
    assert ok.returncode == 0, f"an explicit --telemetry must still be honoured: {ok.stderr!r}"
    assert json.loads(ok.stdout)["lane"]["starts"] == 2
