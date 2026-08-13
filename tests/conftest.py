"""
Shared pytest configuration and helpers for the leafcutter-ai test suite.

Fixture convention (ADR-028):
  tests/
    conftest.py             ← load_fixture() helper (this file)
    fixtures/
      _shared/              ← fixtures used by two or more test modules
      <module>/             ← module = test file stem minus the test_ prefix
                               e.g. tests/test_build_clean.py → fixtures/build_clean/

Usage:
    from conftest import load_fixture

    data = load_fixture("build_pipeline/valid_config")
    # → tests/fixtures/build_pipeline/valid_config.json

    shared = load_fixture("_shared/common_schema")
    # → tests/fixtures/_shared/common_schema.json
"""

import json
from pathlib import Path
from typing import Any


def load_fixture(name: str) -> Any:
    """Load a JSON fixture by slash-separated path relative to tests/fixtures/.

    Parameters
    ----------
    name:
        Slash-separated path identifying the fixture, e.g.
        ``"build_pipeline/valid_config"`` or ``"_shared/common_schema"``.
        The ``.json`` extension is appended automatically.

    Returns
    -------
    Any
        The parsed JSON content (dict, list, str, int, etc.).

    Raises
    ------
    FileNotFoundError
        If the resolved fixture path does not exist on disk. The error message
        includes the full path so callers can diagnose missing files quickly.
    """
    path = Path(__file__).parent / "fixtures" / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
