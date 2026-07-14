"""
MODULE: pytest_ac_enforcement
GOAL: Pytest plugin that converts failing tests covering not-done ACs to
    informational (xfail) outcomes, preventing them from blocking the run.
BUSINESS CONTEXT: A test that covers an AC whose work_status is not "done"
    must never fail the CI run — the feature is in progress and the test is
    expected to fail until the AC is complete.  The test is still visible in
    the output so the team can track its progress.
ARCHITECTURE: Registered as a pytest plugin via pytest.ini addopts
    ``-p scripts.ac_store.pytest_ac_enforcement``.  This ensures the plugin
    loads for ANY pytest invocation that uses the project pytest.ini,
    regardless of where the test files live — including subprocess invocations
    with ``--config-file=<repo_root>/pytest.ini`` pointing at temp directories.

    The plugin calls :mod:`scripts.ac_store.test_enforcement` for the pure
    classification logic.  The AC store root is read from the environment
    variable ``LEAFCUTTER_AC_STORE_ROOT`` (set by tests that inject a synthetic
    store); if absent, falls back to ``docs/acceptance-criteria/`` relative to
    this file's directory.

    Outcome conversion:
      - A failing ``call``-phase test whose ``# covers: <AC-ID>`` tag points at
        an AC with work_status != "done" has its report ``outcome`` set to
        ``"xfailed"`` with a ``wasxfail`` attribute so pytest shows XFAIL.
      - All other tests are unaffected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Session-level state (module globals — one per pytest process)
# ---------------------------------------------------------------------------

_ac_cache: dict[str, str] | None = None
_cache_built: bool = False


def _get_enforcement():
    """Import and return the test_enforcement module.

    Returns:
        The scripts.ac_store.test_enforcement module.

    Raises:
        ImportError: When the module cannot be found on sys.path.
    """
    from scripts.ac_store import test_enforcement  # noqa: PLC0415
    return test_enforcement


def _resolve_ac_store_root() -> Path:
    """Resolve the AC store root directory.

    Checks ``LEAFCUTTER_AC_STORE_ROOT`` environment variable first, then
    falls back to ``docs/acceptance-criteria/`` relative to this module.

    Returns:
        Absolute path to the AC store root.
    """
    env_root = os.environ.get("LEAFCUTTER_AC_STORE_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent.parent / "docs" / "acceptance-criteria"


def _get_ac_cache() -> dict[str, str]:
    """Return the session-scoped AC work_status cache, built on first call.

    Returns:
        Dict mapping AC id → work_status string.
    """
    global _ac_cache, _cache_built  # noqa: PLW0603
    if not _cache_built:
        try:
            enforcement = _get_enforcement()
            ac_root = _resolve_ac_store_root()
            _ac_cache = enforcement.build_ac_work_status_cache(ac_root)
        except ImportError as exc:
            print(
                f"WARNING: pytest_ac_enforcement: cannot import test_enforcement: {exc}",
                file=sys.stderr,
            )
            _ac_cache = {}
        _cache_built = True
    return _ac_cache or {}


# ---------------------------------------------------------------------------
# pytest hook
# ---------------------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo,
) -> Generator[None, pytest.TestReport, None]:
    """Convert failing tests covering not-done ACs to xfail outcomes.

    For each test that fails during the ``call`` phase:
      1. Extracts the ``# covers: <AC-ID>`` tag from the test function source.
      2. Looks up the AC's work_status in the session cache.
      3. If classified as ``"informational"`` (work_status != ``"done"``),
         rewrites the report ``outcome`` to ``"xfailed"`` so pytest does not
         count the test as a run failure.

    Args:
        item: The pytest test item being reported on.
        call: The call-phase info object (phase: setup / call / teardown).

    Yields:
        None (hookwrapper protocol — delegates to inner hooks, then post-processes).
    """
    outcome = yield
    report: pytest.TestReport = outcome.get_result()

    # Only intercept actual test-call failures (not setup/teardown).
    if report.when != "call" or report.outcome != "failed":
        return

    # Only XFAIL-convert assertion failures (the "feature not done yet" semantic).
    # Implementation errors — TypeError, ImportError, AttributeError, etc. — must
    # remain RED so that a broken import or wrong function signature is never
    # silently masked as XFAIL. call.excinfo carries the exception type when the
    # test body raises; when it is None the hook proceeds with the XFAIL check as
    # a safe default.
    if call.excinfo is not None and not issubclass(call.excinfo.type, AssertionError):
        return

    try:
        enforcement = _get_enforcement()
    except ImportError as exc:
        print(
            f"WARNING: pytest_ac_enforcement: cannot import test_enforcement: {exc}",
            file=sys.stderr,
        )
        return

    ac_id = enforcement.extract_covers_tag(item)
    if ac_id is None:
        return

    cache = _get_ac_cache()
    classification = enforcement.classify_by_work_status(ac_id, cache)
    if classification != "informational":
        return

    # Downgrade to xfail so pytest does not count this as a run failure.
    report.outcome = "xfailed"
    report.wasxfail = (
        f"AC {ac_id} work_status is not done — test is informational"
    )
