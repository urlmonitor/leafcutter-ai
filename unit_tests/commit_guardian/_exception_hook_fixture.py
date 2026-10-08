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

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

#: A `sitecustomize` module that makes `ruff` unimportable for any
#: interpreter started with its directory on PYTHONPATH, by refusing to
#: find it at the meta-path level.
#:
#: WHY NOT `PYTHONNOUSERSITE=1`, which this suite used until 2026-10-07:
#: that only disables the USER site directory. It removes ruff on a machine
#: where ruff was pip-installed with `--user` (as on the authoring machine),
#: and removes NOTHING in CI, where `pip install -r requirements-dev.txt`
#: puts ruff in the environment's own site-packages. The three
#: "ruff is genuinely absent" tests therefore passed locally and failed on
#: CI shard 3/8 with exit 0 -- the hook correctly found ruff and allowed the
#: clean file through. Blocking the import is independent of where ruff is
#: installed, so it behaves the same in both places.
#:
#: The raised message matters: `runpy` reports a module it cannot find as
#: "No module named ruff", which is exactly the marker
#: `check_exception_handling_hook._RUFF_MODULE_MISSING_MARKER` looks for to
#: decide the module form is unavailable and fall through to the bare
#: executable. Raising a differently-worded ImportError here would NOT
#: reproduce a genuinely-absent ruff -- the hook would read the failure as
#: "ruff ran and reported something".
_RUFF_IMPORT_BLOCKER = '''\
import sys


class _BlockRuff:
    """Meta-path finder that refuses to resolve the `ruff` package."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ruff" or fullname.startswith("ruff."):
            raise ModuleNotFoundError("No module named ruff", name=fullname)
        return None


sys.meta_path.insert(0, _BlockRuff())
'''


@contextlib.contextmanager
def ruff_made_unavailable():
    """Yield an env mapping in which ruff is neither importable nor on PATH.

    Both of the hook's lookup routes must be closed for this to represent a
    genuinely absent ruff:

    - the bare `ruff` executable, closed by pointing PATH at an empty dir;
    - the `ruff` MODULE, closed by the `sitecustomize` blocker above, since
      `subprocess.run([sys.executable, ...])` execs the interpreter by
      absolute path and never consults PATH at all.

    Yields:
        dict[str, str]: environment overrides to pass to `_run_hook`.
    """
    with tempfile.TemporaryDirectory() as stub_dir:
        (Path(stub_dir) / "sitecustomize.py").write_text(
            _RUFF_IMPORT_BLOCKER, encoding="utf-8"
        )
        with tempfile.TemporaryDirectory() as empty_dir:
            yield {"PATH": empty_dir, "PYTHONPATH": stub_dir}


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
