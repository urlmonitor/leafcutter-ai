"""
MODULE: scripts/build_orchestration/_wvr_pytest.py
GOAL: One pytest run over a set of in-scope tests, read the way the rest of the
    repository reads a run: TQ-500g-4's shared parser for the outcomes and
    TQ-500f-3-i's kind rule for what kind of failure each one was.
BUSINESS CONTEXT: TQ-500g-1-i / -ii. The wrong-version runner must not carry a
    reading rule of its own. A test failed only when the shared parser says so
    (a failed sub-case is a failure), and a failure counts as having reached
    the code only when the kind rule (done_proof_kind_support, fed by
    ``_kind_plugin``) calls it an assertion. Both come from the SAME single
    pytest run.
ARCHITECTURE: Imports the parser from ``pytest_outcome_reader`` (through
    done_proof), the timeout budget from done_proof
    (``_resolve_pytest_timeout_seconds``, env override
    ``LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS``) and the kind helpers from
    ``done_proof_kind_support``. It only launches the process itself, because the
    shared launcher takes whole files and hides a timeout from a crash, and the
    runner needs node-id selection and that distinction. A timeout, a crash
    (return code other than 0 or 1, or an OSError) and an unreadable run come
    back as a status other than ``ran``; the caller reports those ``not_run``.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import _fl_common  # noqa: F401  (puts scripts/ac_store on sys.path)
import done_proof_kind_support as kind_support
from done_proof import _PYTEST_RUN_INCOMPLETE_SENTINEL, _resolve_pytest_timeout_seconds
from pytest_outcome_reader import parse_pytest_outcomes

_LOG = logging.getLogger("wrong_version_runner")
_PYTEST_FLAGS = ("-v", "--tb=no", "--no-header", "-p", "no:cacheprovider", "--continue-on-collection-errors")


@dataclass(frozen=True)
class NodeSpec:
    """One test to select by node id."""

    file: Path
    chain: tuple[str, ...]

    @property
    def arg(self) -> str:
        """The pytest command-line selector."""
        return "::".join([str(self.file), *self.chain])

    @property
    def identity(self) -> str:
        """Absolute POSIX file path plus the ``::`` chain (the kind rule's identity)."""
        return "::".join([Path(self.file).resolve().as_posix(), *self.chain])


@dataclass
class PytestRun:
    """The reading of one pytest run.

    Attributes:
        status: ``ran``, ``timeout``, ``crash`` or ``unreadable``.
        detail: A one-line explanation when *status* is not ``ran``.
        outcome: ``{identity: PASSED|FAILED|...}`` for each test that reported.
        kind: ``{identity: absence|assertion}`` for each failed test whose kind is known.
        collection_failed: Module identities that failed to collect (absence).
    """

    status: str
    detail: str = ""
    outcome: dict[str, str] = field(default_factory=dict)
    kind: dict[str, str] = field(default_factory=dict)
    collection_failed: set[str] = field(default_factory=set)


def _merge_outcomes(per_nodeid: dict[str, str]) -> dict[str, str]:
    """Fold parametrised nodeids into one outcome per identity (worst wins)."""
    merged: dict[str, list[str]] = {}
    for nodeid, outcome in per_nodeid.items():
        merged.setdefault(kind_support._normalize_outcome_identity(nodeid), []).append(outcome)
    folded: dict[str, str] = {}
    for identity, outcomes in merged.items():
        if all(o == "PASSED" for o in outcomes):
            folded[identity] = "PASSED"
        elif any(o in ("FAILED", "ERROR") for o in outcomes):
            folded[identity] = "FAILED"
        else:
            folded[identity] = sorted(set(outcomes))[0]
    return folded


def _read_kinds(kind_path: str, outcomes: dict[str, str]) -> tuple[dict[str, str], set[str]]:
    """Read the kind plugin's output into per-identity kinds and collection failures."""
    try:
        with open(kind_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}, set()
    _per_test, per_module = kind_support._index_kind_plugin_output(raw)
    by_nodeid = kind_support._load_kind_map(kind_path, outcomes)
    kinds: dict[str, str] = {}
    for nodeid, kind in by_nodeid.items():
        identity = kind_support._normalize_outcome_identity(nodeid)
        if kinds.get(identity) != "assertion":
            kinds[identity] = kind
    return kinds, set(per_module)


def _child_env(kind_path: str) -> dict[str, str]:
    """Environment of the pytest child: strict AC mode, the kind plugin, no bytecode."""
    plugin_dir = str(Path(kind_support.__file__).resolve().parent)
    existing = os.environ.get("PYTHONPATH", "")
    return {
        **os.environ,
        "AC_ENFORCE_STRICT": "1",
        kind_support._KIND_OUTPUT_ENV_VAR: kind_path,
        "PYTHONPATH": plugin_dir + os.pathsep + existing if existing else plugin_dir,
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run_selected(nodes: list[NodeSpec]) -> PytestRun:
    """Run pytest once over *nodes* (selected by node id) and read it.

    Args:
        nodes: The in-scope tests to run; nothing else is selected.

    Returns:
        The :class:`PytestRun`. Never raises for a timeout, a crash or an OSError.
    """
    if not nodes:
        return PytestRun("ran")
    fd, kind_path = tempfile.mkstemp(suffix=".json", prefix="leafcutter_wvr_kind_")
    os.close(fd)
    try:
        return _run_and_read(nodes, kind_path)
    finally:
        try:
            os.unlink(kind_path)
        except OSError:
            pass


def _run_and_read(nodes: list[NodeSpec], kind_path: str) -> PytestRun:
    """Launch pytest, classify how it ended, and read a finished run."""
    files = sorted({n.file for n in nodes})
    budget = _resolve_pytest_timeout_seconds(files)
    cmd = [sys.executable, "-m", "pytest", *_PYTEST_FLAGS, "-p", kind_support._KIND_PLUGIN_MODULE_NAME]
    cmd.extend(n.arg for n in nodes)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=budget, env=_child_env(kind_path))
    except subprocess.TimeoutExpired:
        return PytestRun("timeout", f"pytest exceeded its {budget:.1f}s timeout budget")
    except OSError as exc:
        return PytestRun("crash", f"pytest could not be started: {exc}")
    if proc.returncode not in (0, 1):
        # A module that fails to collect leaves pytest with "no collectors" (4) or
        # an interrupted collection (2); the kind plugin names that module.
        _kinds, collected = _read_kinds(kind_path, {})
        if proc.returncode in (2, 4) and collected:
            return PytestRun("ran", "", {}, {}, collected)
        return PytestRun("crash", f"pytest crashed: returncode {proc.returncode}")
    outcomes = parse_pytest_outcomes(proc.stdout, proc.returncode)
    kinds_path_outcomes = dict(outcomes)
    if _PYTEST_RUN_INCOMPLETE_SENTINEL in outcomes:
        _kinds, collected = _read_kinds(kind_path, {})
        if not collected:
            return PytestRun("unreadable", str(outcomes[_PYTEST_RUN_INCOMPLETE_SENTINEL]))
        kinds_path_outcomes = dict(parse_pytest_outcomes(proc.stdout, None))
    kinds, collected = _read_kinds(kind_path, kinds_path_outcomes)
    return PytestRun("ran", "", _merge_outcomes(kinds_path_outcomes), kinds, collected)
