"""
MODULE: conftest
GOAL: Repo-root pytest configuration file.
BUSINESS CONTEXT: Provides session-level pytest configuration for the
    leafcutter-ai test suite.  The AC linkage enforcement hook (which converts
    failing tests covering not-done ACs to informational xfail outcomes) is
    registered as a named plugin via pytest.ini addopts so it loads for every
    pytest invocation — including subprocess runs with ``--config-file``
    pointing at out-of-tree test directories.
ARCHITECTURE: The enforcement plugin lives at
    ``scripts/ac_store/pytest_ac_enforcement.py`` and is loaded via
    ``addopts = -p scripts.ac_store.pytest_ac_enforcement`` in pytest.ini.
    This conftest file is kept for any additional session-level fixtures or
    hooks that apply only to in-tree test runs.
"""

from __future__ import annotations
