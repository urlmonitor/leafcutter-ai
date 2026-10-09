"""
MODULE: pytest_scratch_basetemp
GOAL: Keep a pytest run's scratch in the one designated scratch location,
    refuse a scratch base inside a durable folder or the project tree, and print
    where a failed test's scratch was retained (BO-4400f-2).
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
import tempfile
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRATCH_SOURCE = _REPO_ROOT / "templates" / "scripts" / "scratch.py"
_ITEM_KEY = "_bo4400f2_scratch_item"


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
        return
    if hasattr(config, "workerinput"):
        return
    item = scratch.new_item(f"pytest-{os.getpid()}-{uuid.uuid4().hex[:8]}", "pytest")
    scratch_tmp = Path(item) / "tmp"
    scratch_tmp.mkdir()
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = str(scratch_tmp)
    tempfile.tempdir = str(scratch_tmp)
    config.option.basetemp = str(Path(item) / "basetemp")
    setattr(config, _ITEM_KEY, item)


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

    ``trylast`` is load-bearing: the shared reference layout lives under the
    TMPDIR this plugin points into the item, and shared_layout_integrity
    evaluates that layout in its own sessionfinish. Removing the item first
    makes the integrity check see missing files and fail an otherwise green run.
    """
    item = getattr(session.config, _ITEM_KEY, None)
    if item and session.testsfailed == 0:
        shutil.rmtree(item, ignore_errors=True)
