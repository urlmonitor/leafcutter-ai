"""
MODULE: unit_tests/commit_guardian/_ge_127a_1_i_fixtures.py
COVERS: GE-127a-1-i (shared fixture module — carries no tests of its own)

GOAL: Shared constants, subprocess/git helpers, and the shared
    ``UnmeasurableFixtureTestCase`` scaffolding used by every split test
    module for GE-127a-1-i's "current-content unmeasurable" record:

        - test_ge_127a_1_i_named_situations.py
        - test_ge_127a_1_i_verdict_floor.py
        - test_ge_127a_1_i_entry_points.py

WHY THIS FILE EXISTS: test_ge_127a_1_i.py exceeded the ``check-file-size``
    gate's 400-line limit (467 lines by the gate's own docstring/comment
    -stripped counting rule) and was split along a behavioural seam per
    BrainCandy's explicit decision (test files stay in the gate's scope).
    Splitting the file without a shared module would have required
    copy-pasting these fixtures into three places, letting them drift; this
    module exists so there is exactly one copy.

None of this module's names begin with ``test_``, so it carries no test
cases of its own and is not itself picked up by unittest discovery.

DECISION HISTORY
- 2026-09-07 [GE-127a-1-i/test-writer]: Extracted verbatim from
    test_ge_127a_1_i.py during the mandatory file-size split (see that
    file's original module docstring, preserved in full in each of the
    three split files, for the record of how these fixtures were designed).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_FILE_SIZE = _COMMIT_GUARDIAN_DIR / "check_file_size.py"
_RUN_HOOK = _COMMIT_GUARDIAN_DIR / "run_hook.py"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"
_CONFIG_PATH = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 180

_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_PY_LIMIT = _CONFIG["file_size"]["line_limits"][".py"]

_INDETERMINATE_EXIT = 2
_FINDING_EXIT = 1
_CLEAN_EXIT = 0

_INDETERMINATE_RE = re.compile(r"INDETERMINATE:\s*reason=(.+)", re.IGNORECASE)
_UNDECODABLE_BYTES = b"\xff\xfe\x00\x01not valid utf-8\n" * 5


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors test_ge_127b_1_i.py's conventions in this dir)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def _init_repo(root: Path) -> None:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test-writer@example.com"], root)
    _git(["config", "user.name", "GE-127a-1-i test fixture"], root)


def _commit_all(root: Path, message: str) -> None:
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def _stage_all(root: Path) -> None:
    _git(["add", "-A"], root)


def _content(n_lines: int, tag: str = "v") -> str:
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


def _run_check(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _run_check_via_hook(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_RUN_HOOK), str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _extract_indeterminate_reason(output: str) -> str | None:
    match = _INDETERMINATE_RE.search(output)
    if match is None:
        return None
    return match.group(1).strip()


def _passed_block(output: str) -> str:
    """Return only the PASSED-block portion of *output*, for absence checks."""
    if "PASSED" not in output:
        return ""
    return output.split("PASSED", 1)[1]


class UnmeasurableFixtureTestCase(unittest.TestCase):
    """Shared tempdir + git-repo scaffolding, with a real baseline covered file."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_repo(self.root)
        # A real, ordinary covered file at HEAD so the RATCHET's own
        # previous-length resolution (a different concern -- GE-127b-1/-i)
        # never itself reports EMPTY HISTORY or INDETERMINATE for a reason
        # unrelated to THIS record's current-content measurability.
        (self.root / "existing.py").write_text(_content(20), encoding="utf-8")
        _commit_all(self.root, "establish baseline covered file")
