"""
MODULE: scripts/build_orchestration/_wvr_trace.py
GOAL: Run the baseline pytest run with the line-trace plugin beside the other plugins, and read what
    each test ran of the files the wrong versions alter.
BUSINESS CONTEXT: TQ-500g-1-xiv. The runner must tell a test the wrong version could not reach from a
    weak test. Which lines a test ran comes only from the run on the code as written, per test; a file
    whose run-or-not-run cannot be traced (not Python, outside the repository, or an unreadable trace)
    keeps the run-decided verdict, and an unreadable trace is logged at WARNING. So does a test that ran
    no traced changed line but started a child process: the child's lines are out of the trace's sight.
ARCHITECTURE: ``run_traced(nodes, files, root, extras)`` makes ONE ``_wvr_pytest.run_selected`` call that
    carries the trace plugin together with *extras* (the database plugin), so they share one run. It
    returns the :class:`_wvr_pytest.PytestRun` and a :class:`Traced`. The plugin's output is a temporary
    file this module creates and always deletes. Test identities are the kind rule's (parametrised cases
    folded: the lines of every case are united).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import _wvr_trace_plugin as plugin
import done_proof_kind_support as kind_support
from _wvr_effect import NOT_REACHED, NOT_TRACEABLE, reached
from _wvr_pytest import NodeSpec, PytestRun, run_selected
from _wvr_verdict import NOT_EXECUTED, UNTRACED_NOTE, row

_LOG = logging.getLogger("wrong_version_runner")


@dataclass
class Traced:
    """What the baseline run traced.

    Attributes:
        lines: ``{test identity: {repo-relative path: lines the test ran}}``.
        at_import: ``{repo-relative path: lines run outside any test}``; they count for every test.
        untraceable: The altered files whose run-or-not-run could not be traced.
        spawned: Test identities that started a child process (``""``: one was started outside any test,
            which makes every test's run-or-not-run untraceable).
    """

    lines: dict[str, dict[str, set[int]]] = field(default_factory=dict)
    at_import: dict[str, set[int]] = field(default_factory=dict)
    untraceable: set[str] = field(default_factory=set)
    spawned: set[str] = field(default_factory=set)

    def started_a_child(self, identity: str) -> bool:
        """True when *identity* (or code outside any test) started a child process the trace cannot see."""
        return identity in self.spawned or "" in self.spawned

    def executed(self, identity: str) -> dict[str, set[int]]:
        """The lines *identity* ran plus those run at import time, per repo-relative path."""
        merged = {rel: set(found) for rel, found in self.at_import.items()}
        for rel, found in self.lines.get(identity, {}).items():
            merged.setdefault(rel, set()).update(found)
        return merged


def is_traceable(rel: str, root: Path) -> bool:
    """A file is traceable only when it ends in ``.py`` and lies inside the repository."""
    inside = os.path.realpath(root / rel).startswith(os.path.realpath(root) + os.sep)
    return rel.endswith(".py") and inside and (root / rel).is_file()


def _relative(path: str, root: Path) -> str:
    """Return *path* relative to *root* in POSIX form."""
    return os.path.relpath(path, os.path.realpath(root)).replace("\\", "/")


def _read(out_path: str, root: Path) -> Traced | None:
    """Read the plugin's output file; ``None`` when it is missing or unreadable."""
    try:
        with open(out_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError) as exc:
        _LOG.warning("wrong-version trace output unreadable (%s); run-or-not-run is not traced", exc)
        return None
    traced = Traced()
    spawned = raw.pop(plugin.SPAWNED_KEY, {})
    traced.spawned = {k if k == "" else kind_support._normalize_outcome_identity(k) for k in spawned}
    for key, per_file in raw.items():
        rooted = {_relative(path, root): set(found) for path, found in per_file.items()}
        if key == "":
            traced.at_import = rooted
            continue
        bucket = traced.lines.setdefault(kind_support._normalize_outcome_identity(key), {})
        for rel, found in rooted.items():
            bucket.setdefault(rel, set()).update(found)
    return traced


def run_traced(nodes: list[NodeSpec], files: list[str], root: Path,
               extras: list[tuple[str, dict[str, str]]] | None = None, runner: Callable = run_selected
               ) -> tuple[PytestRun, Traced]:
    """Run *nodes* once with the trace plugin (and *extras*) loaded, and read what each test ran.

    Args:
        nodes: The in-scope tests.
        files: Repo-relative paths of every file a wrong version alters.
        root: The repository root.
        extras: Other ``(plugin module, environment)`` plugins that share this one run.
        runner: The function that makes the pytest run (the caller's own ``run_selected`` binding).

    Returns:
        ``(the run, the trace)``. Files that are not traceable, and every file when the trace output
        is unreadable, are in ``Traced.untraceable``.
    """
    traceable = [rel for rel in files if is_traceable(rel, root)]
    untraceable = set(files) - set(traceable)
    if not traceable:
        return (runner(nodes, extras) if extras else runner(nodes)), Traced(untraceable=untraceable)
    fd, out_path = tempfile.mkstemp(suffix=".json", prefix="leafcutter_wvr_trace_")
    os.close(fd)
    env = {plugin.PATHS_ENV: json.dumps([str(Path(os.path.realpath(root)) / rel) for rel in traceable]),
           plugin.OUTPUT_ENV: out_path}
    try:
        run = runner(nodes, [*(extras or []), (plugin.__name__, env)])
        traced = _read(out_path, root) if run.status == "ran" else None
    finally:
        with contextlib.suppress(OSError):
            os.unlink(out_path)
    if traced is None:
        return run, Traced(untraceable=set(files))
    traced.untraceable = untraceable
    return run, traced


def apply_reach(rows: list[dict], holders: dict[str, str], changes: dict[str, set[int]], traced: Traced) -> list[dict]:
    """Rewrite the rows of one wrong version by whether each test ran a changed line.

    A test that ran none of the changed lines of traceable files gets ``not_executed`` with the fixed
    detail, whatever its outcome under the alteration. A test the check cannot judge keeps its row and
    its detail gains the could-not-be-traced note. Rows of other tests (the group row) are untouched.

    Args:
        rows: The rows of one run of one wrong version.
        holders: ``{row label: test identity}`` of the tests whose own entry names the wrong version.
        changes: ``{repo-relative path: as-written lines the wrong version changes}``.
        traced: What the baseline run traced.

    Returns:
        The rows, rewritten where the check applies.
    """
    out: list[dict] = []
    for r in rows:
        identity = holders.get(r["test"])
        word = NOT_TRACEABLE if identity is None else reached(traced.executed(identity), changes, traced.untraceable)
        child = identity is not None and word == NOT_REACHED and traced.started_a_child(identity)
        if word == NOT_REACHED and not child:
            out.append(row(r["test"], r["wrong_version"], "not_executed", NOT_EXECUTED))
        elif child:
            out.append({**r, "detail": f"{r['detail']}; {UNTRACED_NOTE} a child process the test started"})
        elif word == NOT_TRACEABLE and identity is not None:
            files = ", ".join(sorted(traced.untraceable & set(changes)))
            out.append({**r, "detail": f"{r['detail']}; {UNTRACED_NOTE} {files}"})
        else:
            out.append(r)
    return out


# ================================================================================
# DECISION HISTORY
# ================================================================================
# - 2026-10-25 20:30 [python-coder]: Created: one baseline run carries the trace plugin beside the other
#   plugins; untraceable files and an unreadable trace fail safe to the run-decided verdict. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/04)
# - 2026-10-29 [coordinator]: A test that ran no traced changed line but started a child process keeps its
#   run-decided verdict (with the could-not-be-traced note) instead of reading not_executed. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/04)
