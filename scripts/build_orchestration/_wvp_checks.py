"""
MODULE: scripts/build_orchestration/_wvp_checks.py
GOAL: The five checks a replacement must pass on the code as it NOW stands, before it is run as a
    wrong version: scope and paths, old text exactly once, changes something, still loads, reaches a
    line a test naming it runs.
BUSINESS CONTEXT: TQ-500g-1-xiii (ADR-079). A pinned replacement was prepared against earlier code.
    Every run re-checks it against the code as written now, so a pin that no longer applies, no longer
    loads, changes nothing or sits on a line its tests no longer run is neither used nor dropped: it
    goes back to the preparer. A fresh or declared replacement is held to the same checks. Wording of
    each failed check is fixed here and nowhere else.
ARCHITECTURE: The ONLY implementation of the checks; the plan (``_wvp_plan``), the write step
    (``_wvw_write``) and the declared path call it, none carries a copy. Order, first failure wins:
    (e) paths and scope, (a) old text once, (c) changes bytes (``static_check``, no I/O beyond reading
    the named files), a failure recorded by an earlier run for the same file bytes, then (b) the
    altered file executes as a module in a child interpreter, applied and put back through the runner's
    journalled ``RunGate`` (never git stash, always byte for byte), then (d) one traced pytest run of
    the tests naming the candidates (``_wvr_trace``, ``_wvr_effect``). Logging goes to stderr only.
"""

from __future__ import annotations

import itertools
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import _fl_common  # noqa: F401  (puts scripts/ac_store on sys.path)
import _wvr_gate as gate_mod
from _wvp_store import CHANGES_NOTHING, DID_NOT_LOAD, NO_LINE, PinError
from _wvr_effect import NOT_REACHED, NOT_TRACEABLE, REACHED, changed_lines, reached
from _wvr_pytest import NodeSpec, run_selected
from _wvr_scope import ScopedTest, wrong_version_key
from _wvr_trace import Traced, run_traced
from _wvw_prepare import Altered, alter
from done_proof import _resolve_pytest_timeout_seconds

_LOG = logging.getLogger("wrong_version_writer")
NOT_IN_SCOPE = "not in scope"
TARGET_CHANGED = "target changed"
COULD_NOT_CHECK = "the check that a test runs a changed line could not be made"
_LOAD_EXIT = 17
_TIMES = re.compile(r"^old text found (\d+) times in ")
_RUN_IDS = itertools.count()
_CHILD = (
    "import importlib.util, os, sys\n"
    "root = sys.argv[1]\n"
    "for path in sys.argv[2:]:\n"
    "    sys.path[:0] = [os.path.dirname(path), root]\n"
    "    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)\n"
    "    module = importlib.util.module_from_spec(spec)\n"
    "    try:\n"
    "        spec.loader.exec_module(module)\n"
    "    except (ImportError, NameError, AttributeError, SyntaxError):\n"
    f"        sys.exit({_LOAD_EXIT})\n"
    "    except BaseException:\n"
    "        pass\n"
)


class CheckError(PinError):
    """A check could not be made safely (the code could not be put back); ``str(exc)`` is the step's error."""


@dataclass
class Item:
    """One candidate: a name, its ordered replacements and the name's CURRENT in-scope files.

    ``known_failure`` is the check an earlier run recorded as failed for the very file bytes now on
    disk (``None`` when there is none): it is the result instead of running (b) and (d) again.
    """

    name: str
    replacements: list[dict]
    files: list[str]
    known_failure: str | None = None


@dataclass
class Verdict:
    """The outcome of the checks for one :class:`Item`.

    ``reason`` is the failed check's fixed wording (``None`` when every check passed); ``detail`` is the
    writer's own wording of the refusal; ``note`` says why a check passed without being made.
    """

    reason: str | None = None
    detail: str = ""
    note: str = ""
    altered: list[Altered] = field(default_factory=list)


def _short(detail: str) -> str:
    """The fixed wording of a path or old-text refusal of ``_wvw_prepare`` (others pass through as written)."""
    if " is not in scope for " in detail:
        return NOT_IN_SCOPE
    found = _TIMES.match(detail)
    if found:
        return f"old text found {found.group(1)} times"
    return TARGET_CHANGED if detail.startswith("old text not found in ") else detail


def _current(root: Path, rel: str) -> bytes:
    """The bytes of *rel* as now written (empty when it cannot be read)."""
    try:
        return (root / rel).read_bytes()
    except OSError:
        return b""


def static_check(item: Item, root: Path, test_root_rel: str | None) -> Verdict:
    """Checks (e), (a) and (c) of *item* against the code as now written; first failure wins."""
    altered, detail = alter(item.name, item.replacements, root, item.files, test_root_rel)
    if detail:
        return Verdict(_short(detail), detail)
    if all(a.data == _current(root, a.rel) for a in altered):
        return Verdict(CHANGES_NOTHING, CHANGES_NOTHING)
    return Verdict(altered=altered)


def _run_child(files: list[str], root: Path) -> int | None:
    """Execute *files* as modules in a child interpreter; its exit code, or ``None`` when it was cut short."""
    budget = _resolve_pytest_timeout_seconds([Path(f) for f in files])
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, "-c", _CHILD, str(root), *files], cwd=root, env=env,
                              capture_output=True, timeout=budget, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _LOG.warning("the load check could not finish (%s); the run decides whether it loads", exc)
        return None
    return proc.returncode


def _executes_badly(altered: list[Altered], root: Path, git_directory: Path) -> bool:
    """Apply *altered* through the journalled gate, execute each .py file, ALWAYS put the files back.

    Raises:
        CheckError: When the check could not be made or the files could not be put back.
    """
    run_dir = git_directory / "leafcutter" / "wrong-version-runs" / f"load-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{next(_RUN_IDS)}"
    gate = gate_mod.RunGate(root, run_dir)
    code, problem = None, ""
    try:
        gate.apply("load check", {a.rel: a.data for a in altered})
        code = _run_child([str(root / a.rel) for a in altered], root)
    except (gate_mod.GateError, OSError) as exc:
        problem = f"the load check could not be made: {exc}"
    finally:
        back = gate.restore()
    if not back.ok:
        raise CheckError("; ".join(back.failures))
    if problem:
        raise CheckError(problem)
    return code == _LOAD_EXIT


def load_check(altered: list[Altered], root: Path, git_directory: Path) -> str | None:
    """Check (b): ``DID_NOT_LOAD`` when an altered .py file does not compile or does not execute as a module.

    A file of any other language has no pre-run load check; the run judges it.
    """
    python = [a for a in altered if a.rel.endswith(".py")]
    for a in python:
        try:
            compile(a.data, a.rel, "exec")
        except (SyntaxError, ValueError):
            return DID_NOT_LOAD
    return DID_NOT_LOAD if python and _executes_badly(python, root, git_directory) else None


def _holders(name: str, tests: list[ScopedTest], root: Path) -> list[NodeSpec]:
    """The tests whose own entry names *name*, as nodes run from the repository root."""
    key = wrong_version_key(name)
    return [replace(t.node, file=Path(t.node.file).resolve(), cwd=root) for t in tests
            if t.node is not None and ((t.names and key in t.versions) or key in t.extras)]


def _reach_word(traced: Traced, identity: str, changes: dict[str, set[int]]) -> str:
    """Whether one holder ran a changed line; a holder that started a child process cannot be judged."""
    word = reached(traced.executed(identity), changes, traced.untraceable)
    return NOT_TRACEABLE if word == NOT_REACHED and traced.started_a_child(identity) else word


def _effect_check(live: list[tuple[Item, Verdict]], root: Path, tests: list[ScopedTest]) -> None:
    """Check (d) for *live* with ONE traced run of the holder tests; sets ``reason`` or ``note`` on each verdict."""
    changes = {i.name: {a.rel: changed_lines(_current(root, a.rel), a.data) for a in v.altered} for i, v in live}
    holders = {i.name: _holders(i.name, tests, root) for i, _v in live}
    nodes = list({n.identity: n for found in holders.values() for n in found}.values())
    if not nodes:
        return
    run, traced = run_traced(nodes, sorted({rel for ch in changes.values() for rel in ch}), root, None, run_selected)
    if run.status != "ran":
        _LOG.warning("the traced run was cut short (%s: %s); the effect check is not made", run.status, run.detail)
    _judge_reach(live, holders, changes, traced if run.status == "ran" else None)


def _judge_reach(live: list[tuple[Item, Verdict]], holders: dict[str, list[NodeSpec]],
                 changes: dict[str, dict[str, set[int]]], traced: Traced | None) -> None:
    """Set check (d)'s ``reason`` or ``note`` on each verdict; *traced* is ``None`` when the run was cut short."""
    for item, verdict in live:
        words = [] if traced is None else [_reach_word(traced, n.identity, changes[item.name]) for n in holders[item.name]]
        if traced is None or (NOT_TRACEABLE in words and REACHED not in words):
            verdict.note = COULD_NOT_CHECK
        elif words and REACHED not in words:
            verdict.reason = verdict.detail = NO_LINE


def check_candidates(items: list[Item], root: Path, git_directory: Path, tests: list[ScopedTest],
                     test_root_rel: str | None) -> list[Verdict]:
    """Run the five checks on every candidate; one :class:`Verdict` per item, in order.

    Args:
        items: The candidates (pinned, freshly prepared or declared replacements).
        root: The worktree root; the files are as written.
        git_directory: The absolute git directory (the load check's journal lives under it).
        tests: The in-scope tests of the work (their own entries decide who holds a name).
        test_root_rel: The test root relative to *root*, or ``None``.

    Returns:
        The verdicts. (b) costs one child interpreter per candidate with Python files; (d) at most one
        traced pytest run, and none when no candidate reaches it.

    Raises:
        CheckError: When a load check could not be made or its files could not be put back.
    """
    verdicts = [static_check(i, root, test_root_rel) for i in items]
    live: list[tuple[Item, Verdict]] = []
    for item, verdict in zip(items, verdicts, strict=True):
        if verdict.reason:
            continue
        if item.known_failure:
            verdict.reason = verdict.detail = item.known_failure
            continue
        verdict.reason = load_check(verdict.altered, root, git_directory)
        verdict.detail = verdict.reason or ""
        if not verdict.reason:
            live.append((item, verdict))
    if live:
        _effect_check(live, root, tests)
    return verdicts


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 22:00 [python-coder]: Created: the five pin checks in one module; the load check executes
#   the altered file under the runner's journalled gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/05) (ADR-079)
# - 2026-10-29 [coordinator]: Check (d) treats a holder that started a child process as not traceable (note,
#   never a re-preparation), like the runner since fde974ed6; extracted _reach_word. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/05)
