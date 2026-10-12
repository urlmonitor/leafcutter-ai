"""
MODULE: test_inf_500d_4_iv (feedback side)
GOAL: RED tests for AC INF-500d-4-iv -- every log a drive writes lands in the
    one enduring location, not in the workspace that is about to be deleted.
    (The plan-feature.js product-truth telemetry half is in
    unit_tests/workflows/test_inf_500d_4_iv.py.)
AC: INF-500d-4-iv (source_ac); depends on INF-500d-4-iii (declaration, ADR-069).

CONTRACT THIS FILE FIXES (python-coder implements against exactly this):

    1. With no ``--jsonl``, the deployed ``submit_feedback.py`` appends to
       ``feedback_sink`` from ITS OWN workspace's deployed
       ``<output_root>/config/knowledge_sink.json`` (found relative to the
       script's resolved location), from any current directory. The
       ``_find_project_root`` walk for ``.claude/`` is no longer the sink.
    2. With no ``--log``, ``emit_event.py`` appends to
       ``operational_telemetry_stream`` from the same declaration -- including
       when it is run through the ``.claude/skills`` symlink (the way the skill
       documents it) from the project root, a nested directory, or elsewhere.
       The old ancestor search for ``<dir>/config/knowledge_sink.json`` never
       matches ``<project>/.leafcutter/config/`` and returned the bare relative
       path (verified 2026-10-09).
    3. The ``inline_work_guard`` hook, run from ``.claude/hooks``, appends its
       audit record to ``<operational_log_root>/inline_work_guard.jsonl``.
    4. Without a usable declaration ``emit_event.py`` exits 0 with a stderr
       warning naming the declaration and drops the event; the hook still never
       gains a new way to block and likewise warns; neither writes relative to
       the workspace.
    5. Concurrent appends from several workspaces into one sink lose or
       interleave no record.

REAL-ARTIFACT NOTE: subprocess runs of the REAL scripts in temp deployed
    layouts, declarations written by the real build helper, the guard run via
    the real ``templates/settings.json`` command, and the deployed emit_event
    proved against the real shared reference layout. No build.py is spawned.
"""
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_REPO_ROOT = h.REPO_ROOT
_LOCK = ".build-feature.lock"


def _worktree(base: Path, name: str, *, log_root: Path | None) -> tuple[Path, Path, Path]:
    """A worktree-shaped project; ``log_root=None`` leaves it with NO declaration."""
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    if log_root is not None:
        h.declare(out_root, log_root)
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, cwd


def _enduring(base: Path) -> Path:
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    return root


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _emit_script(out_root: Path) -> Path:
    """emit_event.py as the skill documents it: through the .claude/skills symlink."""
    return out_root.parent / ".claude" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"


def _hook_script(out_root: Path) -> Path:
    return out_root.parent / ".claude" / "hooks" / "inline_work_guard.py"


def _emit_args(agent: str = "ticket-supervisor") -> list[str]:
    return ["--event", "agent_start", "--agent", agent, "--ticket", "/x/01_t.md", "--phase", "python-coder"]


def _hook_payload(project: Path) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(project / "work" / "x.py")}})


def test_report_filed_in_a_worktree_survives_the_worktree_removal(tmp_path):
    # covers: INF-500d-4-iv
    # angle: real_artifact
    """File in a worktree, delete the worktree, then read the id back from the declared sink."""
    root = _enduring(tmp_path)
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    tmpdir = _tmpdir(tmp_path)

    proc = h.submit(out_root, cwd, tmpdir)
    assert proc.returncode == 0, proc.stderr
    filed_id = proc.stdout.strip()
    assert filed_id, "no id was returned"

    shutil.rmtree(project)  # the workspace is removed; only now is the durable location read
    sink = root / "feedback.jsonl"
    assert sink.is_file(), f"the report went somewhere the workspace removal destroyed; {root} holds {sorted(p.name for p in root.iterdir())}"
    assert [r["feedback_id"] for r in h.read_records(sink)] == [filed_id]


def test_two_worktrees_append_to_one_sink_without_displacing_each_other(tmp_path):
    # covers: INF-500d-4-iv
    # angle: boundary
    """Two worktrees declaring one root append N reports each, concurrently: 2N parseable lines, every id present."""
    per_worktree = 5
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    layouts = [_worktree(tmp_path, f"wt{n}", log_root=root) for n in (1, 2)]
    procs = [
        h.popen_py(h.submit_script(out_root), h.submit_args(note=f"wt{n} report {i}"), cwd, tmpdir)
        for n, (_project, out_root, cwd) in enumerate(layouts, start=1)
        for i in range(per_worktree)
    ]
    printed: list[str] = []
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=h.RUN_TIMEOUT)
        assert proc.returncode == 0, stderr
        printed.append(stdout.strip())

    sink = root / "feedback.jsonl"
    assert sink.is_file(), "no shared sink exists: each worktree wrote to its own"
    records = h.read_records(sink)
    assert len(records) == 2 * per_worktree, f"expected {2 * per_worktree} records, found {len(records)}"
    assert sorted(r["feedback_id"] for r in records) == sorted(printed)
    assert len(set(printed)) == 2 * per_worktree


def test_every_drive_written_log_resolves_under_the_one_declared_root(tmp_path):
    # covers: INF-500d-4-iv
    # angle: criterion
    """From the worktree root: report, telemetry event and guard audit all land under R; nothing under the worktree."""
    root = _enduring(tmp_path)
    project, out_root, _cwd = _worktree(tmp_path, "wt", log_root=root)
    tmpdir = _tmpdir(tmp_path)
    (project / _LOCK).write_text("locked\n", encoding="utf-8")
    before = h.snapshot(project)

    report = h.submit(out_root, project, tmpdir)
    event = h.run_py(_emit_script(out_root), _emit_args(), project, tmpdir)
    guard = h.run_py(_hook_script(out_root), [], project, tmpdir, stdin=_hook_payload(project))

    assert report.returncode == 0, report.stderr
    assert event.returncode == 0, event.stderr
    assert guard.returncode == 2, f"the guard must still block while the lock exists: rc={guard.returncode} {guard.stderr!r}"
    assert (root / "feedback.jsonl").is_file(), "feedback.jsonl is not under the declared root"
    assert [r["feedback_id"] for r in h.read_records(root / "feedback.jsonl")] == [report.stdout.strip()]
    telemetry = (root / "agent_telemetry.jsonl")
    assert telemetry.is_file(), "agent_telemetry.jsonl is not under the declared root"
    assert [r["event_type"] for r in h.read_records(telemetry)] == ["agent_start"]
    audit = root / "inline_work_guard.jsonl"
    assert audit.is_file(), "inline_work_guard.jsonl is not under the declared root"
    assert [r["tool_name"] for r in h.read_records(audit)] == ["Write"]
    assert h.snapshot(project) == before, "something was written under the disposable worktree"
    assert list(project.rglob("*.jsonl")) == [], "a log file exists beneath the worktree"


@pytest.mark.shared_layout_reader
def test_emit_event_finds_the_declaration_in_the_real_deployed_layout(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-iv
    # angle: deployed
    """The real deployed emit_event.py lands at the declared stream from the project root, a nested dir and elsewhere."""
    layout = Path(shared_reference_layout)
    real_out = layout / ".leafcutter"
    real_declaration = real_out / "config" / "knowledge_sink.json"
    assert real_declaration.is_file(), f"the real build deployed no declaration at {real_declaration}"
    assert "operational_telemetry_stream" in json.loads(real_declaration.read_text(encoding="utf-8"))
    assert (real_out / "skills" / "agent-telemetry" / "scripts" / "emit_event.py").is_file(), "emit_event.py is not in the real deployed layout"

    # The shared layout is built in a staging directory and then moved, so the absolute paths its build
    # recorded name a directory that no longer exists. Run a verbatim copy of the real deployed files
    # (symlinks kept, as the build lays them out) and re-declare it with the real build helper, so the
    # declared stream is an absolute path that is real, and the only thing under test is where the
    # deployed script LOOKS for the declaration.
    project = tmp_path / "proj"
    project.mkdir()
    shutil.copytree(real_out, project / ".leafcutter", symlinks=True)
    shutil.copytree(layout / ".claude", project / ".claude", symlinks=True)
    out_root = project / ".leafcutter"
    h.declare(out_root)
    declared = Path(h.read_declaration(out_root)["operational_telemetry_stream"])
    assert declared == project / "debugging" / "logs" / "agent_telemetry.jsonl"
    script = _emit_script(out_root)
    assert script.is_file(), "the .claude/skills route to emit_event.py is broken in the real layout"

    nested = project / "deep" / "er"
    nested.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    for label, cwd in (("project root", project), ("nested subdirectory", nested), ("unrelated directory", elsewhere)):
        agent = f"probe-{uuid.uuid4().hex[:10]}"
        proc = h.run_py(script, ["--event", "probe", "--agent", agent], cwd, tmp_path)
        assert proc.returncode == 0, f"{label}: {proc.stderr!r}"
        assert declared.is_file(), f"{label}: nothing was written to the declared stream {declared}"
        hits = [line for line in declared.read_text(encoding="utf-8").splitlines() if agent in line]
        assert len(hits) == 1, f"{label}: the event must land at the declared stream exactly once, found {len(hits)}"
        if cwd != project:
            assert not (cwd / "debugging").exists(), f"{label}: a workspace-relative log was created at {cwd / 'debugging'}"


@pytest.mark.parametrize("variant", ["absent", "malformed_json"])
def test_emit_event_without_a_declaration_warns_and_writes_nothing(tmp_path, variant):
    # covers: INF-500d-4-iv
    # angle: failure
    """No usable declaration: exit 0, a stderr warning naming the declaration, and no log created anywhere."""
    project, out_root, _cwd = _worktree(tmp_path, "wt", log_root=None)
    tmpdir = _tmpdir(tmp_path)
    if variant == "malformed_json":
        h.declaration_path(out_root).parent.mkdir(parents=True, exist_ok=True)
        h.declaration_path(out_root).write_text("{ not json", encoding="utf-8")
    before = h.snapshot(tmp_path)

    proc = h.run_py(_emit_script(out_root), _emit_args(), project, tmpdir)

    assert proc.returncode == 0, "telemetry stays non-fatal (BP-400a-1-i)"
    assert str(h.declaration_path(out_root)) in proc.stderr, f"the warning must name the missing declaration: {proc.stderr!r}"
    assert h.snapshot(tmp_path) == before, "the event must be dropped, not written workspace-relative"
    assert list(tmp_path.rglob("agent_telemetry.jsonl")) == []

    # Control: an explicit --log is still honoured, so the silence above is the missing declaration's doing.
    explicit = tmp_path / "explicit" / "agent_telemetry.jsonl"
    ok = h.run_py(_emit_script(out_root), [*_emit_args(), "--log", str(explicit)], project, tmpdir)
    assert ok.returncode == 0
    assert len(h.read_records(explicit)) == 1


@pytest.mark.parametrize("mode", ["block", "warn"])
def test_inline_work_guard_without_a_declaration_warns_instead_of_writing_workspace_relative(tmp_path, mode):
    # covers: INF-500d-4-iv
    # angle: failure
    """The guard keeps its own exit code, names the missing declaration on stderr, and writes no audit file anywhere."""
    project, out_root, _cwd = _worktree(tmp_path, "wt", log_root=None)
    tmpdir = _tmpdir(tmp_path)
    (project / _LOCK).write_text("locked\n", encoding="utf-8")
    before = h.snapshot(tmp_path)

    proc = h.run_py(_hook_script(out_root), [], project, tmpdir, stdin=_hook_payload(project),
                    env_extra={"INLINE_WORK_GUARD_MODE": mode})

    assert proc.returncode == (2 if mode == "block" else 0), f"the guard's own verdict changed: {proc.returncode} {proc.stderr!r}"
    assert "knowledge_sink.json" in proc.stderr, f"the missing declaration must be named: {proc.stderr!r}"
    assert h.snapshot(tmp_path) == before, "the audit record was written workspace-relative"
    assert list(tmp_path.rglob("inline_work_guard.jsonl")) == []


def test_inf_500d_4_iv_reachable_from_entry_point(tmp_path):
    # covers: INF-500d-4-iv
    # angle: reachability
    """Run the guard through the real templates/settings.json command: it blocks, and its audit lands under R."""
    settings = json.loads((_REPO_ROOT / "templates" / "settings.json").read_text(encoding="utf-8"))
    commands: list[str] = []

    def collect(node: object) -> None:
        if isinstance(node, dict):
            command = node.get("command")
            if isinstance(command, str) and "inline_work_guard.py" in command:
                commands.append(command)
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(settings)
    assert len(commands) == 1, f"expected exactly one inline_work_guard hook command in settings.json: {commands!r}"

    root = _enduring(tmp_path)
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    tmpdir = _tmpdir(tmp_path)
    (project / _LOCK).write_text("locked\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.symlink(h.sys.executable, bin_dir / "python")
    before = h.snapshot(project)

    proc = subprocess.run(
        commands[0], shell=True, input=_hook_payload(project), capture_output=True, text=True,
        cwd=str(cwd), timeout=h.RUN_TIMEOUT, check=False,
        env=h.make_env(tmpdir, path=f"{bin_dir}:/usr/bin:/bin"),
    )

    assert proc.returncode == 2, f"the hook, run the way the harness runs it, must block: rc={proc.returncode} {proc.stderr!r}"
    audit = root / "inline_work_guard.jsonl"
    assert audit.is_file(), "the production hook command did not write its audit record under the declared root"
    records = h.read_records(audit)
    assert len(records) == 1 and records[0]["file_path"] == str(project / "work" / "x.py")
    assert h.snapshot(project) == before, "the hook wrote under the disposable worktree"
    assert re.search(r"BLOCKED", proc.stderr), "the guard's own verdict is no longer surfaced"
