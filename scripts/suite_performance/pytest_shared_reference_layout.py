"""
MODULE: pytest_shared_reference_layout
GOAL: Pytest plugin exposing the ``shared_reference_layout`` fixture -- a
    single, real deployed copy of this package produced once for the whole
    run (lazily, on first demand) and shared, cross-process-safely, across
    every worker and every read-only consumer test.
BUSINESS CONTEXT: TQ-600a-1. See CLAUDE.md's "Tests must not spawn their
    own build.py" rule -- this fixture is the shared layout that rule
    requires a read-only consumer to reuse instead of running its own
    ``python scripts/build.py --target-dir <tmp>``.
ARCHITECTURE: Registered as a pytest plugin via pytest.ini's addopts
    ``-p scripts.suite_performance.pytest_shared_reference_layout``,
    mirroring the existing whole-suite-loaded precedent
    ``-p scripts.ac_store.pytest_ac_enforcement``. This is the LOAD-BEARING
    registration: this repo has no root conftest.py and no
    unit_tests/conftest.py, so a per-directory conftest.py is invisible
    outside its own directory -- registering here instead of there is what
    makes the fixture reachable from every test file, not just one
    directory's worth.

    All production/locking/caching logic lives in
    ``_shared_layout_producer.py`` and ``_shared_layout_coordination.py``
    (split out to respect the project's file-size limit); this module is a
    thin registration surface plus the fixture itself.
    ``get_or_produce_shared_layout`` and ``SharedReferenceLayoutError`` are
    re-exported here so a caller that imports this plugin module directly
    (as the low-level tests in
    unit_tests/suite_performance/test_tq_600a_1.py do) can reach them
    without also importing the private helper modules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import (
    SharedReferenceLayoutError,
    get_or_produce_shared_layout,
)

__all__ = [
    "SharedReferenceLayoutError",
    "get_or_produce_shared_layout",
    "shared_reference_layout",
]


@pytest.fixture(scope="session")
def shared_reference_layout() -> Path:
    """Return the path to this run's single shared reference layout.

    Produced lazily, on first request, and shared across every test and
    every pytest-xdist worker in the run -- see
    ``_shared_layout_producer.get_or_produce_shared_layout`` for the
    cross-process production, locking, and caching contract.

    ONLY for tests that read a deployed layout without altering it. A test
    that mutates the package before building (e.g. withholding a
    dependency to assert a build failure) must build its own copy instead
    -- see CLAUDE.md's "Tests must not spawn their own build.py" section,
    the read-vs-mutate boundary. Routing individual tests onto this
    fixture versus their own copy is TQ-600a-2/TQ-600a-5's per-test
    selector, not this ticket's -- this fixture only needs to exist and be
    safe to route onto; it does not itself refuse a declared mutator.

    Returns:
        The absolute path to the deployed, complete package root.
    """
    return get_or_produce_shared_layout()


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 19:14 [python-coder]: Created the shared_reference_layout
#   pytest fixture/plugin for TQ-600a-1 and registered it in pytest.ini's
#   addopts (mirroring the existing
#   `-p scripts.ac_store.pytest_ac_enforcement` precedent) so it is reachable
#   from a plain, un-augmented pytest invocation over any test in the suite
#   -- registering it only in a per-directory conftest.py would have been
#   invisible outside that one directory, since this repo has no root
#   conftest.py and no unit_tests/conftest.py. (#TQ-600a-1)
