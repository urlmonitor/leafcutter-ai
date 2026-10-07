"""
MODULE: _exception_hook_fixture.py
GOAL: Shared subprocess plumbing for the tests of
    templates/hooks/check_exception_handling_hook.py, so the hook's
    invocation contract is defined once rather than per test module.
BUSINESS CONTEXT: Extracted from test_exception_hook.py when GE-108e's
    arms pushed that file past its 400-line limit and check-file-size
    refused the commit. The split is by concern -- GE-108e's module-vs-
    executable lookup arms moved to test_ge_108e.py -- and these three
    helpers are needed by both halves. Duplicating them would let the two
    copies drift on a contract (how the hook is launched, what payload
    shape it reads) that must stay identical for the two files to be
    testing the same thing.
ARCHITECTURE: Plain helper module, imported by sibling test modules via
    the established `sys.path.insert(parent)` convention this suite
    already uses (see _ge_127f_4_fixture.py). No test cases live here.

These helpers are UNCHANGED from the versions that lived in
test_exception_hook.py; this is a move, not a rewrite.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _hook_path() -> Path:
    """Resolve the hook script path relative to this fixture file.

    This module lives at unit_tests/commit_guardian/, and the hook lives
    at templates/hooks/check_exception_handling_hook.py. Walk up two
    levels to reach the repo root, then descend into templates.

    Returns:
        Absolute path to the hook script.
    """
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "templates" / "hooks" / "check_exception_handling_hook.py"


def _run_hook(payload: dict, *, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook script as a subprocess, sending *payload* on stdin.

    Args:
        payload: Dict to serialise as JSON on stdin.
        env: Optional environment overrides (merged onto os.environ).

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        [sys.executable, str(_hook_path())],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged_env,
    )


def _make_payload(file_path: str) -> dict:
    """Build a minimal PostToolUse payload for the hook.

    The hook reads ``tool_response.path`` (or ``tool_input.file_path``)
    to find the edited file. Claude Code's hook contract passes the path
    in the tool_response or tool_input depending on the tool.

    Args:
        file_path: Absolute path string of the file that was just written.

    Returns:
        A dict matching the shape the hook expects on stdin.
    """
    return {
        "tool": "Write",
        "tool_input": {"file_path": file_path, "content": "..."},
        "tool_response": {"path": file_path},
    }


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-07 [GE-108e]: Extracted verbatim from test_exception_hook.py.
  That file reached 453 measured lines against a 400 limit once
  GE-108e's three module-lookup arms were added, and check-file-size
  refused the commit. Splitting the new arms into test_ge_108e.py left
  both files needing the same three helpers; a shared module keeps the
  hook's launch contract and payload shape single-sourced, which matters
  more here than usual because the two files deliberately differ only in
  the ENVIRONMENT they hand the child (PATH / PYTHONNOUSERSITE).
====================================================================
"""
