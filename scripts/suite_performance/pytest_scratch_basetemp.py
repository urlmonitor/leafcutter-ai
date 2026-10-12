"""
MODULE: pytest_scratch_basetemp
GOAL: Keep a pytest run's scratch in the one designated scratch location,
    refuse a scratch base inside a durable folder or the project tree, and print
    where a failed test's scratch was retained (BO-4400f-2). It does NOT
    redirect the process-wide temp dir (TMPDIR / tempfile.tempdir): a path
    that contained the scratch root would be read as product-owned content by
    code that matches path components, and would move other plugins' state.
BUSINESS CONTEXT: test-logs/wire-700a5-tmp reached 3.4 GB because a run's
    --basetemp pointed at a durable log folder. Retention "failed" (pytest.ini)
    plus this plugin means passing tests leave nothing and failing tests leave
    their scratch somewhere discoverable and outside the project.
ARCHITECTURE: Registered through pytest.ini ``addopts`` with ``-p`` (this repo
    has no root conftest.py). Uses ``new_item()`` from templates/scripts/scratch.py
    for the per-run unique folder; never hands the shared scratch root to pytest
    as basetemp because pytest empties a given basetemp. Package-internal; no
    template copy.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRATCH_SOURCE = _REPO_ROOT / "templates" / "scripts" / "scratch.py"
_ITEM_KEY = "_bo4400f2_scratch_item"
_CALLER_OWNED_KEY = "_bo4400f2_caller_owned_basetemp"


def _load_scratch():
    """Load the scratch module by file path (templates/ is not a package)."""
    spec = importlib.util.spec_from_file_location("_leafcutter_scratch", _SCRATCH_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def refusal_for(basetemp: str, project: Path, durable: list[str]) -> str | None:
    """Return a refusal message for a forbidden scratch base, else None."""
    target = Path(os.path.abspath(basetemp)).resolve()
    project = project.resolve()
    for declared in durable:
        folder = (project / declared).resolve()
        if _inside(target, folder):
            return (
                f"--basetemp {basetemp} is inside the durable location "
                f"'{declared}' ({folder}); a durable location may not hold scratch"
            )
    if _inside(target, project):
        return (
            f"--basetemp {basetemp} is inside the project tree {project}; "
            "scratch may not be written inside the project"
        )
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config) -> None:
    """Refuse a forbidden basetemp; otherwise default it into the scratch item."""
    scratch = _load_scratch()
    given = config.option.basetemp
    if given:
        message = refusal_for(str(given), Path(str(config.rootpath)), scratch.durable_paths())
        if message:
            raise pytest.UsageError(message)
        setattr(config, _CALLER_OWNED_KEY, True)
        return
    if hasattr(config, "workerinput"):
        return
    item = scratch.new_item(f"pytest-{os.getpid()}-{uuid.uuid4().hex[:8]}", "pytest")
    config.option.basetemp = str(Path(item) / "basetemp")
    setattr(config, _ITEM_KEY, item)


def pytest_sessionstart(session) -> None:
    """Keep every test's folder when the caller supplied (and so owns) --basetemp.

    The shipped ``tmp_path_retention_policy = failed`` is for the plugin-chosen
    folder inside the scratch item, which is removed when the run is green. A
    caller that names its own --basetemp (a parent test inspecting a child
    session's trees, or a person debugging) has taken ownership of that folder
    and cleans it up itself; deleting passed tests' trees out from under it
    would make the supplied folder useless.
    """
    if not getattr(session.config, _CALLER_OWNED_KEY, False):
        return
    factory = getattr(session.config, "_tmp_path_factory", None)
    if factory is not None and hasattr(factory, "_retention_policy"):
        factory._retention_policy = "all"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add the retained scratch location to a failed test's report."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    tmp_path = getattr(item, "funcargs", {}).get("tmp_path")
    where = tmp_path if tmp_path is not None else getattr(item.config, _ITEM_KEY, None)
    if where:
        report.sections.append(("Retained scratch", f"scratch retained at: {where}"))


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus) -> None:
    """Remove this run's scratch item when nothing failed.

    ``trylast`` keeps the removal after every other plugin's sessionfinish has
    finished reading anything under the item (e.g. the basetemp folders).
    """
    item = getattr(session.config, _ITEM_KEY, None)
    if item and session.testsfailed == 0:
        shutil.rmtree(item, ignore_errors=True)
