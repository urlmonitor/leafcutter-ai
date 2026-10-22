"""
MODULE: unit_tests/build_orchestration/_bo_4300a_2_probe.py
GOAL: Run a snippet against the DEPLOYED worktree_identity.py in a genuinely fresh interpreter
    (BO-4300a-2 proofs); the snippet sees the module as ``wi_module`` and prints one JSON value.
NOT a test file (leading underscore).
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path


def deployed_identity_probe(snippet: str) -> Any:
    """Return the JSON value *snippet* prints after importing the deployed ``worktree_identity``."""
    scripts_dir = str(deployed_maker_path().parent)
    prelude = f"import sys\nsys.path.insert(0, {scripts_dir!r})\nimport worktree_identity as wi_module\n"
    proc = subprocess.run([sys.executable, "-I", "-c", prelude + snippet], capture_output=True, text=True,
                          timeout=60, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        raise AssertionError(f"probe failed (exit {proc.returncode}): {proc.stderr[-800:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])
