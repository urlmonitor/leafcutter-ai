"""
MODULE: test_inf_500d_4_iv_inline_work_guard_fresh_install
GOAL: Pin how the deployed inline_work_guard hook writes its audit record on a fresh install, and that it
    refuses (rather than recreates) a vanished enduring project.
AC: INF-500d-4-iv (writers default to the declared root; with no usable declaration the writer warns, names
    it and writes nothing); ADR-069 section 4.

The hook used to create its audit directory with ``mkdir(exist_ok=True)`` and no parents. On a fresh install
the project exists but ``<project>/debugging`` does not, so the first audit write warned and was lost. The
other writers (``feedback_sink``, ``emit_event``) create up to the log directory, and only while the enduring
root is live; the hook must do the same.

REAL-ARTIFACT NOTE: the install is the deployed layout from ``_inf_500d_4_helpers.deploy_install`` and the
    declaration is written by the REAL build helper (``h.declare``). The hook runs in a subprocess through the
    ``.claude/hooks`` symlink, with a real ``.build-feature.lock`` and a real stdin payload; the audit record
    is read back from disk.
"""
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_AUDIT_NAME = "inline_work_guard.jsonl"


def _hook(out_root: Path) -> Path:
    """The hook the way the harness reaches it: through the ``.claude/hooks`` symlink."""
    return out_root.parent / ".claude" / "hooks" / "inline_work_guard.py"


def _install(base: Path, log_root: Path | None) -> tuple[Path, Path]:
    """A locked, deployed project under ``base``; returns ``(project, out_root)``."""
    (base / "tmpdir").mkdir(exist_ok=True)  # the run's TMPDIR: created before any snapshot is taken
    project = base / "project"
    project.mkdir()
    out_root = h.deploy_install(project)
    h.declare(out_root, log_root)
    (project / ".build-feature.lock").write_text("locked\n", encoding="utf-8")
    return project, out_root


def _fire(out_root: Path, project: Path, base: Path, mode: str | None):
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(project / "src" / "x.py")}})
    env = {"INLINE_WORK_GUARD_MODE": mode} if mode else None
    return h.run_py(_hook(out_root), [], project, tmpdir, stdin=payload, env_extra=env)


@pytest.mark.parametrize("layout", ["inherited_root_fresh_project", "own_root_fresh_project"])
def test_fresh_install_audit_record_lands_under_the_declared_log_root(tmp_path, layout):
    # covers: INF-500d-4-iv
    # angle: reachability
    """The project exists, ``<project>/debugging`` does not: the first audit write creates the log directory
    under the DECLARED operational_log_root, appends the record, and warns about nothing. (Today the
    ``mkdir`` has no parents, so the write fails and the record is lost.)"""
    if layout == "inherited_root_fresh_project":
        enduring = tmp_path / "enduring"
        enduring.mkdir()  # a live project with no debugging/ yet -- what a fresh install looks like
        log_root = enduring / "debugging" / "logs"
    else:
        log_root = None  # a plain build: <project>/debugging/logs, declared by the real helper
    project, out_root = _install(tmp_path, log_root)
    declared = Path(h.read_declaration(out_root)["operational_log_root"])
    assert not declared.exists(), "fixture: the declared log directory must not exist before the first write"
    assert declared.parent.parent.is_dir(), "fixture: the enduring project must exist"

    proc = _fire(out_root, project, tmp_path, mode=None)

    assert proc.returncode == 2, f"block mode must still block (exit 2); got {proc.returncode}: {proc.stderr}"
    audit = declared / _AUDIT_NAME
    assert audit.is_file(), (
        f"the audit record must land under the declared operational_log_root {declared}; "
        f"stderr was:\n{proc.stderr}")
    records = h.read_records(audit)
    assert len(records) == 1, records
    assert records[0]["tool_name"] == "Write" and records[0]["mode"] == "block", records[0]
    assert records[0]["file_path"] == str(project / "src" / "x.py"), records[0]
    assert "WARNING" not in proc.stderr, f"a fresh install must not warn about the audit write:\n{proc.stderr}"
    assert "could not append" not in proc.stderr and "NOT written" not in proc.stderr, proc.stderr
    assert not (project / "debugging").exists() or log_root is None, (
        "with an inherited root nothing may be written into the workspace itself")


@pytest.mark.parametrize(("mode", "exit_code"), [(None, 2), ("block", 2), ("warn", 0)])
@pytest.mark.parametrize("shape", ["conventional_project_gone", "flat_root_gone"])
def test_vanished_project_warns_naming_the_declaration_creates_nothing_and_keeps_exit_codes(
        tmp_path, shape, mode, exit_code):
    # covers: INF-500d-4-iv
    # angle: failure
    """The declared enduring project no longer exists: the hook warns on stderr naming the declaration file,
    creates NO directory (``mkdir(parents=True)`` alone would conjure the vanished project), and exits 2 in
    block mode / 0 in warn mode exactly as before."""
    gone = tmp_path / "gone_project"  # never created
    log_root = gone / "debugging" / "logs" if shape == "conventional_project_gone" else gone / "logs"
    project, out_root = _install(tmp_path, log_root)
    declaration = h.declaration_path(out_root)
    assert not gone.exists(), "fixture: the declared enduring project must be gone"
    before = h.snapshot(tmp_path)

    proc = _fire(out_root, project, tmp_path, mode=mode)

    assert proc.returncode == exit_code, f"exit code must be unchanged ({exit_code}); got {proc.returncode}: {proc.stderr}"
    warned = [line for line in h.stderr_lines(proc) if line.startswith("inline_work_guard: WARNING:")]
    assert warned, f"the hook must warn that the audit record was not written:\n{proc.stderr}"
    assert any(str(declaration) in line for line in warned), (
        f"the warning must name the declaration {declaration}:\n{proc.stderr}")
    assert not gone.exists(), "a vanished enduring project must not be recreated"
    assert h.snapshot(tmp_path) == before, "the refused write must create no file or directory anywhere"
    # control: the guard's own message still carries the outcome (block vs warn) through the refusal
    assert ("BLOCKED" in proc.stderr) == (exit_code == 2), proc.stderr
