"""
MODULE: scripts/ac_store/project_python.py
GOAL: Resolve the interpreter a gate must judge an adopter project's tests
    with, and read a collection-time ImportError of the project's own package
    out of a pytest run (TQ-500f-3-v).
BUSINESS CONTEXT: The build routes launch their gates as bare ``python
    fast_lane.py ...``. In an adopter whose dependencies live in a project venv
    (DIAGraph: a uv-managed ``.venv`` in each worktree) that interpreter has
    pytest but not the project package, so a gate that ran its tests as
    ``sys.executable -m pytest`` failed every conftest import, read every new
    test as ERROR and reported ``no_red_outcome_among_new_tests`` while the
    same tests were genuinely red under the project venv (17 red, 1 green by
    design). The gate must judge with the project's interpreter, and when even
    that interpreter cannot import the project, it must say so by name.
ARCHITECTURE: Resolution order, first match wins, all keyed off the project
    root (the nearest ancestor of the tests that holds ``.git``):
        1. ``testing_context.python_command`` in the project's
           ``skills_config.json`` (``.claude/`` then ``.leafcutter/``),
           shlex-split; a relative executable resolves against the root.
        2. The root's ``.venv`` interpreter.
        3. ``uv run --project <root> python`` when the root is uv-managed
           (``uv.lock``, or ``[tool.uv`` in ``pyproject.toml``) and ``uv`` is
           on PATH.
        4. The interpreter running the gate (``sys.executable``) -- the
           behaviour before this module existed.
    No leading underscore: imported from scripts/build_orchestration/ as well
    as from this directory (BP-900h-4), and registered in AC_STORE_DEPLOY_MAP.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from pytest_outcome_reader import PytestOutcomes

_LOG = logging.getLogger(__name__)

_CONFIG_DIRS = (".claude", ".leafcutter")
_VENV_INTERPRETERS = (Path(".venv", "bin", "python"), Path(".venv", "Scripts", "python.exe"))
_PROBE_TIMEOUT_SECONDS = 300
# The full dotted name: only an exact top-level project package counts, so a
# not-yet-written submodule ("pkg.new_module") is never mistaken for it.
_MISSING_MODULE_RE = re.compile(r"No module named '([\w.]+)'")


class ProjectPython(NamedTuple):
    """The command prefix that runs the project's Python, and where it came from.

    Attributes:
        argv: Command prefix; append ``-m pytest ...`` or ``-c ...``.
        source: ``configured`` | ``venv`` | ``uv`` | ``current``.
    """

    argv: tuple[str, ...]
    source: str

    @property
    def display(self) -> str:
        """The interpreter as a verdict names it: a path, or the joined command."""
        return self.argv[0] if len(self.argv) == 1 else shlex.join(self.argv)


def find_project_root(start: Path) -> Path | None:
    """Return the nearest directory at or above *start* that holds ``.git``."""
    current = start if start.is_dir() else start.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _configured_command(root: Path) -> tuple[str, ...] | None:
    """``testing_context.python_command`` from the project's skills_config.json."""
    for platform_dir in _CONFIG_DIRS:
        config = root / platform_dir / "skills_config.json"
        if not config.is_file():
            continue
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _LOG.warning("project_python: ignoring unreadable %s: %s", config, exc)
            continue
        testing = data.get("testing_context") if isinstance(data, dict) else None
        value = testing.get("python_command") if isinstance(testing, dict) else None
        if isinstance(value, str) and value.strip():
            argv = shlex.split(value)
            executable = Path(argv[0])
            if not executable.is_absolute() and len(executable.parts) > 1:
                argv[0] = str(root / executable)
            return tuple(argv)
    return None


def _uv_managed(root: Path) -> bool:
    """True when *root* is a uv project (a ``uv.lock``, or ``[tool.uv`` in pyproject)."""
    if (root / "uv.lock").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        return "[tool.uv" in pyproject.read_text(encoding="utf-8")
    except OSError as exc:
        _LOG.warning("project_python: cannot read %s: %s", pyproject, exc)
        return False


def resolve_project_python(start: Path | str | None) -> ProjectPython:
    """Resolve the interpreter to judge the tests at or under *start* with.

    Args:
        start: A test file or directory inside the project, or ``None``.

    Returns:
        The first of configured / venv / uv / current that applies (see the
        module ARCHITECTURE note).
    """
    root = find_project_root(Path(start).resolve()) if start is not None else None
    if root is not None:
        configured = _configured_command(root)
        if configured:
            return ProjectPython(configured, "configured")
        for rel in _VENV_INTERPRETERS:
            if (root / rel).is_file():
                return ProjectPython((str(root / rel),), "venv")
        if _uv_managed(root):
            uv = shutil.which("uv")
            if uv:
                return ProjectPython((uv, "run", "--project", str(root), "python"), "uv")
            _LOG.warning("project_python: %s is uv-managed but uv is not on PATH", root)
    return ProjectPython((sys.executable,), "current")


def resolve_for_files(test_files) -> ProjectPython:
    """Resolve the project interpreter from the first of *test_files*."""
    files = [Path(f) for f in test_files]
    return resolve_project_python(files[0] if files else None)


def pytest_unusable(judge: ProjectPython) -> bool:
    """True when *judge* cannot import pytest (TQ-500f-3-ii, extended to *judge*).

    The running interpreter is asked in-process, as before; any other
    interpreter is asked with one ``-c "import pytest"`` subprocess.
    """
    if judge.source == "current":
        return importlib.util.find_spec("pytest") is None
    try:
        proc = subprocess.run(
            [*judge.argv, "-c", "import pytest"],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _LOG.warning("project_python: cannot probe %s for pytest: %s", judge.display, exc)
        return True
    return proc.returncode != 0


def with_import_failures(outcomes: dict, proc: subprocess.CompletedProcess) -> PytestOutcomes:
    """Return *outcomes* carrying the modules the run could not import.

    Used on a run that did not finish (exit 2 interrupted collection, exit 4
    conftest import failure), where no per-test line names the cause.
    """
    marked = PytestOutcomes(outcomes)
    marked.subfailed = dict(getattr(outcomes, "subfailed", {}))
    text = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    marked.missing_modules = sorted(set(_MISSING_MODULE_RE.findall(text)))
    return marked


def project_packages(root: Path) -> set[str]:
    """Top-level package names the project defines in *root* or *root*/src."""
    names: set[str] = set()
    for base, is_src in ((root, False), (root / "src", True)):
        if not base.is_dir():
            continue
        try:
            children = list(base.iterdir())
        except OSError as exc:
            _LOG.warning("project_python: cannot list %s: %s", base, exc)
            continue
        for child in children:
            if child.is_dir() and (child / "__init__.py").is_file():
                names.add(child.name)
            elif is_src and child.suffix == ".py":
                names.add(child.stem)
            elif is_src and child.is_dir() and child.name.isidentifier():
                names.add(child.name)
    return names


def project_import_refusal(test_root: Path, results: dict, judge: ProjectPython) -> str | None:
    """Name an un-importable project package behind a run, or return ``None``.

    Args:
        test_root: Where the gate looked for tests (locates the project root).
        results: The run's outcomes, as returned by the pytest readers.
        judge: The interpreter that ran the tests.

    Returns:
        The refusal text naming *judge* and the package, when the run could not
        import one of the project's own top-level packages; else ``None``.
    """
    root = find_project_root(Path(test_root).resolve())
    missing = getattr(results, "missing_modules", [])
    hits = sorted(set(missing) & project_packages(root)) if root is not None and missing else []
    if not hits:
        return None
    return (
        f"pytest could not collect the new tests: the interpreter {judge.display} "
        f"({judge.source}) cannot import the project package '{hits[0]}' "
        f"(No module named '{hits[0]}'). The tests were not judged, so this says "
        "nothing about whether they are red. Set testing_context.python_command in "
        "the project's skills_config.json, or create the project's .venv, then re-run."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-22 [python-coder/TQ-500f-3-v]: Created. The red-baseline gate ran
#   the adopter's tests with whatever interpreter launched it, and an
#   un-importable project package surfaced as "no red outcome". Resolution order
#   (configured, .venv, uv, current) per the AC; the refusal is keyed on a
#   top-level package that exists on disk, so an absent submodule a new test
#   names is never misread as an environment fault.
# ====================================================================
