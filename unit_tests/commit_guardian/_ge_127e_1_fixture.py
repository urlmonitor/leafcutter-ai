"""
MODULE: unit_tests/commit_guardian/_ge_127e_1_fixture.py
SHARED FIXTURE for GE-127e-1's test files (private sibling module, per the
    unit_tests/commit_guardian/ package-import pattern already used by
    test_ge_127a_1.py: importers must
    ``sys.path.insert(0, str(Path(__file__).resolve().parent))`` before
    ``import _ge_127e_1_fixture``).

WHY A SHARED MODULE, NOT ONE FILE. GE-127e-1's test_spec names seven
    descriptors. A single file holding all of them plus their fixture
    content and extraction helpers would itself risk crossing this repo's
    own 400-counted-line .py gate -- the exact trap two sibling ACs in this
    epic already hit today, whose fix both times was "split into focused
    files plus a shared fixture module, never exempt the file." This module
    is that shared piece: git/subprocess plumbing, deterministic
    per-file-content fixture builders, and the output-extraction helpers
    every descriptor needs, so each test_ge_127e_1_*.py file stays small and
    focused on one or two assertions.

THE PRINTED-BLOCK CONTRACT THIS MODULE'S EXTRACTORS ASSUME, AND WHY IT IS
    SPECIFIED HERE RATHER THAN DISCOVERED. GE-127e-1 is greenfield: no
    per-file description exists in check_file_size.py today (its refusal is
    the fixed, per-AC-documented two-sentence block), so there is no
    existing print format to reverse-engineer the way test_ge_127a_1.py
    reverse-engineered the EXISTING "Lines: N (Limit: M)" line. Per the
    test-writer's role of writing the RED contract python-coder must turn
    GREEN, this module fixes the minimal shape the new content must take,
    appended to the SAME existing refusal block
    (ONE OUTCOME, NOT A SECOND SURFACE -- GE-127e-1's own it_requirements):

        Parts:
          - <name>: <portion> lines
          - <name>: <portion> lines
          ...
        Division:
          Side A: <name>[, <name> ...] (<length> lines)
          Side B: <name>[, <name> ...] (<length> lines)

    or, for a file accounted for by one part:

        Parts:
          - <name>: <portion> lines
        No division found: <name> accounts for the whole file.

    No test in this AC's suite asserts on a NAME or a PORTION value it
    authored -- every name and every number the assertions use is read back
    out of the real process output via the extractors below, then checked
    against either the fixture's own raw bytes or another number the same
    output printed (see each test_ge_127e_1_*.py file's own docstring).
    Only the STRUCTURE of the two blocks above is fixed by this module, the
    same way a test author fixes an expected function signature for code
    that does not exist yet.

    The pre-existing "Lines: N (Limit: M)" line this module's
    ``extract_quoted_length_and_limit`` reads is NOT part of this contract:
    it is today's real, already-shipped ``_print_too_large_file`` output,
    unchanged by this AC, and is the anchor GE-127e-1's own reconciliation
    clause is stated against.

DECISION HISTORY
- 2026-09-14 [GE-127e-1/test-writer]: Initial authoring.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_FILE_SIZE = _COMMIT_GUARDIAN_DIR / "check_file_size.py"
_RUN_HOOK = _COMMIT_GUARDIAN_DIR / "run_hook.py"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"
_CONFIG_PATH = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"
_REAL_OVERSIZED_FILE = _REPO_ROOT / "scripts" / "build_phases.py"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 60
_BUILD_TIMEOUT_SECONDS = 180

sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
from _file_size_ratchet import count_content_lines  # noqa: E402

import json  # noqa: E402

_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_PY_LIMIT = _CONFIG["file_size"]["line_limits"][".py"]

# ---------------------------------------------------------------------------
# Extraction helpers -- read names/numbers OUT of real process output.
# ---------------------------------------------------------------------------

_QUOTED_LENGTH_RE = re.compile(r"Lines:\s*(\d+)\s*\(Limit:\s*(\d+)\)")
_PART_LINE_RE = re.compile(r"^\s*-\s*(?P<name>\S+):\s*(?P<portion>\d+)\s*lines?\s*$", re.IGNORECASE | re.MULTILINE)
_SIDE_LINE_RE = re.compile(
    r"^\s*Side\s+\w+:\s*(?P<names>.+?)\s*\(\s*(?P<length>\d+)\s*lines?\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_NO_DIVISION_RE = re.compile(r"no division", re.IGNORECASE)


def extract_quoted_length_and_limit(output: str) -> tuple[int, int]:
    """Read the (measured_length, limit) pair from the EXISTING refusal line.

    This is today's real ``_print_too_large_file`` output
    ("Lines: N (Limit: M)"), unchanged by this AC.
    """
    match = _QUOTED_LENGTH_RE.search(output)
    if not match:
        raise AssertionError(f"could not find 'Lines: N (Limit: M)' in output: {output!r}")
    return int(match.group(1)), int(match.group(2))


def extract_named_portions(output: str) -> list[tuple[str, int]]:
    """Read every ``- <name>: <portion> lines`` entry out of *output*."""
    return [(m.group("name"), int(m.group("portion"))) for m in _PART_LINE_RE.finditer(output)]


def extract_sides(output: str) -> list[tuple[list[str], int]]:
    """Read every ``Side X: <names> (<length> lines)`` entry out of *output*."""
    sides: list[tuple[list[str], int]] = []
    for m in _SIDE_LINE_RE.finditer(output):
        names = [n.strip() for n in m.group("names").split(",")]
        sides.append((names, int(m.group("length"))))
    return sides


def has_no_division_marker(output: str) -> bool:
    """True if *output* states that no division was found."""
    return bool(_NO_DIVISION_RE.search(output))


# ---------------------------------------------------------------------------
# Fixture content builders -- deterministic, docstring/comment-free .py text
# made ENTIRELY of top-level function definitions ("named parts"), so its
# ``count_content_lines`` length is exactly the sum of the parts' sizes.
# ---------------------------------------------------------------------------


def make_part_source(name: str, n_lines: int) -> str:
    """Build one top-level function definition spanning exactly *n_lines* lines.

    Args:
        name: The function's name -- this IS the "named part" an author
            reading the file would see.
        n_lines: Exact total line count of the returned text (the ``def``
            line plus ``n_lines - 1`` body assignment lines).

    Returns:
        Source text with no docstring, no comment, no trailing newline.
    """
    if n_lines < 1:
        raise ValueError("a part must span at least one line")
    lines = [f"def {name}():"]
    for i in range(n_lines - 1):
        lines.append(f"    {name}_{i:04d} = {i}")
    return "\n".join(lines)


def make_multi_part_fixture(parts: list[tuple[str, int]]) -> str:
    """Concatenate several named parts with no separating blank line.

    Args:
        parts: ``(name, n_lines)`` pairs, in file order.

    Returns:
        Full file content ending in one trailing newline. Its
        ``count_content_lines`` length is exactly ``sum(n for _, n in parts)``
        -- verified by callers via the sanity assertion in each test.
    """
    body = "\n".join(make_part_source(name, n) for name, n in parts)
    content = body + "\n"
    expected = sum(n for _, n in parts)
    actual = count_content_lines(content)
    if actual != expected:
        raise AssertionError(f"fixture sanity: expected {expected} counted lines, got {actual}")
    return content


# ---------------------------------------------------------------------------
# git / subprocess plumbing (mirrors test_ge_127a_1.py / test_ge_127b_1.py)
# ---------------------------------------------------------------------------


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic committer identity."""
    git(["init", "-q"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "GE-127e-1 test fixture"], root)


def commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit."""
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", message], root)


def stage_all(root: Path) -> None:
    """Stage everything without committing."""
    git(["add", "-A"], root)


def run_check(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke check_file_size.py directly (bypassing the hook wrapper)."""
    return subprocess.run(
        [_PYTHON, str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def run_check_via_hook(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke check_file_size.py through the registered run_hook.py wrapper.

    This is the real production entry point named by GE-127e-1's own
    test_spec ``surface_invoked`` field (the deployed-layout form of this
    same wrapper-plus-target pair) -- see test_ge_127e_1_reachability_and_deployed.py.
    """
    return subprocess.run(
        [_PYTHON, str(_RUN_HOOK), str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def build_into(target: Path) -> subprocess.CompletedProcess:
    """Run the real build.py into *target*."""
    return subprocess.run(
        [_PYTHON, str(_BUILD_PY), "--target-dir", str(target)],
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
    )


def fresh_repo_dir(prefix: str) -> Path:
    """Create a fresh temp directory (caller owns cleanup)."""
    return Path(tempfile.mkdtemp(prefix=prefix))
