"""
MODULE: pytest_git_identity_guard
GOAL: Snapshot the host repository's shared commit identity (user.name and
    user.email) before the first test, compare it at session end, and fail the
    run, naming the test, key, before value and after value, when it changed.
BUSINESS CONTEXT: A test that sandboxes itself with a linked worktree and writes
    an identity with an unqualified ``git config`` lands that write in the one
    configuration shared by the host and every worktree of it (KI-TQ-012, TQ-100a-2).
    The pollution outlives the process, so the session itself must object.
ARCHITECTURE: Registered through pytest.ini ``addopts`` with ``-p``. Reads the
    host repository via ``git config --local --get`` (never a value a test hands
    it). ABSENT is its own state, distinct from an empty string; only exit code 1
    means absent, any other non-zero code makes the snapshot unavailable and the
    guard switches itself off with a one-line notice (never a false finding). To
    attribute a change to a test cheaply, the shared config file's stat signature
    is checked after each test and git is re-read only when it moved. A signal that
    kills the process outright cannot be caught, so that case is not covered.
    Under pytest-xdist every worker snapshots and attributes on its own, reports
    its findings through ``workeroutput``, and the controller merges them (deduped
    on key/before/after) and compares the last-known state with the final one.
    Limitation: a worker that observes a change another worker's test made blames
    the test it was running; the controller keeps the first report per change.
    Package-internal; no template copy.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

IDENTITY_KEYS = ("user.name", "user.email")
_STATE_KEY = "_tq100a2i_identity_guard"
_UNATTRIBUTED = "<no single test: changed outside any test>"
_OUTPUT_KEY = "tq100a2i_findings"


class _Absent:
    """Sentinel for a key that is not set; distinct from the empty string."""

    def __repr__(self) -> str:
        return "<absent>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Absent)

    def __hash__(self) -> int:
        return hash("_Absent")


ABSENT = _Absent()


class SnapshotUnavailable(Exception):
    """Git answered with something other than set (0) or absent (1)."""

    def __init__(self, key: str, code: int) -> None:
        super().__init__(f"git config --get {key} exited {code}")


def read_identity(repo_root) -> dict:
    """Read each identity key from the host repository's shared config as git resolves it."""
    identity: dict = {}
    for key in IDENTITY_KEYS:
        try:
            result = subprocess.run(
                ["git", "config", "--local", "--get", key],
                cwd=str(repo_root), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise SnapshotUnavailable(key, -1) from exc
        if result.returncode == 1:
            identity[key] = ABSENT
        elif result.returncode == 0:
            identity[key] = result.stdout.rstrip("\n")
        else:
            raise SnapshotUnavailable(key, result.returncode)
    return identity


def _diff(before: dict, after: dict, fixture: str) -> list[tuple]:
    """Changed keys as (fixture, key, old, new) tuples; [] if equal."""
    changes = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key, ABSENT), after.get(key, ABSENT)
        if old != new:
            changes.append((fixture, key, old, new))
    return changes


def _render(change: tuple) -> str:
    fixture, key, old, new = change
    return (
        f"git identity changed in the host repository's shared config: "
        f"fixture={fixture} key={key} before={old!r} after={new!r}"
    )


def compare_identity(before: dict, after: dict, fixture: str) -> list[str]:
    """One message per changed key naming fixture, key, before and after; [] if equal."""
    return [_render(change) for change in _diff(before, after, fixture)]


def _shared_config_path(repo_root: Path):
    """Path of the shared config file, or None when git cannot resolve it."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=str(repo_root),
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None  # git missing or hung: the guard stays off, silently
    if result.returncode != 0:
        return None
    return Path(repo_root) / result.stdout.strip() / "config"


def _stat(path) -> tuple | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _is_worker(config) -> bool:
    return hasattr(config, "workerinput")


def _disable(config, reason) -> None:
    """Switch the guard off for this process with a one-line notice."""
    setattr(config, _STATE_KEY, None)
    print(f"git-identity-guard: snapshot unavailable, guard disabled ({reason})",
          file=sys.stderr)


def _read_or_disable(config, state):
    """Current identity, or None after disabling the guard when git cannot answer."""
    try:
        return read_identity(state["root"])
    except (OSError, subprocess.SubprocessError, SnapshotUnavailable) as exc:
        _disable(config, exc)
        return None


def pytest_configure(config) -> None:
    """Take the snapshot (controller and workers); skip outside a git repo."""
    root = Path(str(config.rootpath))
    try:
        path = _shared_config_path(root)
        if path is None:
            return
        before = read_identity(root)
    except SnapshotUnavailable as exc:
        _disable(config, exc)
        return
    except (OSError, subprocess.SubprocessError):
        return
    state = {"root": root, "before": before, "last": before, "path": path,
             "stat": _stat(path), "findings": []}
    setattr(config, _STATE_KEY, state)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item) -> None:
    """After each test, re-read git only when the shared config file moved."""
    state = getattr(item.config, _STATE_KEY, None)
    if state is None:
        return
    signature = _stat(state["path"])
    if signature == state["stat"]:
        return
    state["stat"] = signature
    now = _read_or_disable(item.config, state)
    if now is None:
        return
    state["findings"].extend(_diff(state["last"], now, item.nodeid))
    state["last"] = now


def _to_wire(change: tuple) -> tuple:
    return tuple(None if isinstance(v, _Absent) else v for v in change)


def _from_wire(change) -> tuple:
    fixture, key, old, new = change
    return (fixture, key, ABSENT if old is None else old, ABSENT if new is None else new)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error) -> None:
    """xdist controller: merge a worker's attributed findings (deduped per change)."""
    state = getattr(node.config, _STATE_KEY, None)
    output = getattr(node, "workeroutput", None) or {}
    if state is None:
        return
    seen = {c[1:] for c in state["findings"]}
    for raw in output.get(_OUTPUT_KEY, []):
        change = _from_wire(raw)
        if change[1:] in seen:
            continue
        seen.add(change[1:])
        state["findings"].append(change)
        state["last"] = dict(state["last"], **{change[1]: change[3]})


def _record_line(before: dict) -> str:
    """The session-end record: which identity keys were compared and matched."""
    present = [k for k in IDENTITY_KEYS if before.get(k, ABSENT) != ABSENT]
    absent = [k for k in IDENTITY_KEYS if k not in present]
    if not present:
        return ("git-identity-guard: no identity keys were present at start or end "
                f"({' and '.join(absent)} absent); comparison not exercised")
    line = f"git-identity-guard: compared {' and '.join(present)}; values matched (unchanged)"
    if absent:
        line += f"; {' and '.join(absent)} absent at start and end, not exercised"
    return line


def _write(reporter, text: str, red: bool = False) -> None:
    if reporter is not None:
        reporter.write_line("\n" + text, red=red)
    else:
        print("\n" + text)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus) -> None:
    """Compare the final state with the snapshot; fail the run on any difference."""
    config = session.config
    state = getattr(config, _STATE_KEY, None)
    if state is None:
        return
    if _is_worker(config):
        wire = [_to_wire(c) for c in state["findings"]]
        getattr(config, "workeroutput", {})[_OUTPUT_KEY] = wire
        return
    after = _read_or_disable(config, state)
    if after is None:
        return
    findings = [_render(c) for c in state["findings"]]
    findings += compare_identity(state["last"], after, _UNATTRIBUTED)
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if not findings:
        _write(reporter, _record_line(state["before"]))
        return
    for line in findings:
        _write(reporter, f"GIT-IDENTITY-GUARD FAILURE: {line}", red=True)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED

# DECISION HISTORY
# ================================================================================
# - 2026-11-05 14:00 [python-coder]: Created session-scoped host git identity guard; per-test attribution via config stat signature to avoid a git subprocess per test. (#TQ-100a/TQ-100a-2-i)
# - 2026-11-05 15:00 [python-coder]: Review fixes: distinct matched/no-keys record line, xdist worker attribution via workeroutput, only exit 1 means absent, guarded reads disable the guard, final-vs-last comparison always runs. (#TQ-100a/TQ-100a-2-i)
