"""
MODULE: pytest_manual_deselect
GOAL: Auto-mark every collected test whose function name ends in ``_MANUAL``
    with the ``manual`` marker, so the default ``-m "not manual"`` in
    pytest.ini's ``addopts`` genuinely deselects it and ``-m manual`` opts in.
BUSINESS CONTEXT: TQ-600a-13. The docs said the default run excludes
    ``_MANUAL`` tests, but nothing excluded them, so they ran (and paid their
    cost) on every run. The suffix is the rule: no enumeration and no
    per-test decorator, so a newly added ``_MANUAL`` test is excluded without
    anyone remembering to register it.
ARCHITECTURE: A pytest plugin registered in pytest.ini's ``addopts`` via
    ``-p scripts.suite_performance.pytest_manual_deselect``, mirroring the
    existing suite_performance plugins. ``pytest_collection_modifyitems`` runs
    ``tryfirst`` so the marker exists before pytest's own mark plugin applies
    the ``-m`` expression. The ``manual`` marker itself is registered as a
    direct ``markers =`` ini key (not in addopts). Not a commit-guardian hook
    or CI gate import, so it needs no build deploy-manifest entry.
"""

import pytest

MANUAL_SUFFIX = "_MANUAL"
MANUAL_MARKER = "manual"


def is_manual_node_id(nodeid: str) -> bool:
    """Return True when the node id, up to any ``[`` parametrize bracket, ends in ``_MANUAL``."""
    return nodeid.split("[", 1)[0].endswith(MANUAL_SUFFIX)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Add the ``manual`` marker to every collected item whose name ends in ``_MANUAL``."""
    for item in items:
        if is_manual_node_id(item.nodeid):
            item.add_marker(getattr(pytest.mark, MANUAL_MARKER))
