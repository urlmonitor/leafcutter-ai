"""
MODULE: unit_tests/commit_guardian/_ge_120h_3_fixture.py
SHARED FIXTURE for GE-120h-3's two arm test files (test_ge_120h_3.py -- arm 3,
    the nothing-to-inspect clause -- and test_ge_120h_3_refusals.py -- arm 4,
    the anti-theatre refusal clause). Private sibling module, per the
    unit_tests/commit_guardian/ package-import pattern already used by
    test_ge_127e_1_reachability_and_deployed.py's ``_ge_127e_1_fixture``:
    importers must ``sys.path.insert(0, str(Path(__file__).resolve().parent))``
    before ``import _ge_120h_3_fixture``.

WHY A SHARED MODULE, NOT INLINE IN EACH TEST FILE. This repo's
    ``check_file_size.py`` counts lines per file with a 400-line cap for
    ``.py``; splitting the git/subprocess plumbing into one shared module
    (mirroring ``_ge_127e_1_fixture.py``'s own stated rationale) keeps both
    test files focused on their own arm's assertions.

PRODUCTION ENTRY POINT, PER FILE. Four of the five checks this AC registers
    (check_folder_density.py, check_sql_complexity.py, check_debug_scripts.py,
    check_test_fixture_bloat.py) are pre-commit entries that delegate through
    ``run_hook.py`` -- ``run_via_hook()`` below drives them exactly that way,
    against a REAL git repository (``git init`` + real ``git add``), never by
    importing and calling the check's own function. The fifth,
    check_ac_done_on_merge.py, is registered on the ``post-merge`` stage and
    is invoked directly per GE-120h-3's own constraint ("check-ac-done-on-merge
    READS git diff HEAD~1 HEAD ... run_hook.py scopes itself to pre-commit") --
    ``run_direct()`` is reserved for that one script.

DECISION HISTORY
- 2026-09-30 [GE-120h-3/test-writer]: Initial authoring, covering only the
    two arms still open after PR #808 registered all five hooks (arms 1, 2, 5
    landed there). Verified empirically before writing any test: run_hook.py
    delegating to the TEMPLATE (source-tree) script, in a scratch git repo
    with no build.py deploy, reproduces every behaviour these tests assert
    on -- see the sign-off comment on TICKET-20260930-GE-120h-3.md for the
    probe transcripts this fixture's helpers were derived from.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"

RUN_HOOK = GUARDIAN_DIR / "run_hook.py"
FOLDER_DENSITY = GUARDIAN_DIR / "check_folder_density.py"
SQL_COMPLEXITY = GUARDIAN_DIR / "check_sql_complexity.py"
DEBUG_SCRIPTS = GUARDIAN_DIR / "check_debug_scripts.py"
TEST_FIXTURE_BLOAT = GUARDIAN_DIR / "check_test_fixture_bloat.py"
AC_DONE_ON_MERGE = GUARDIAN_DIR / "hooks" / "check_ac_done_on_merge.py"
MANIFEST_PATH = GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 60

# ---------------------------------------------------------------------------
# git / subprocess plumbing (mirrors _ge_127e_1_fixture.py's own helpers)
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
    git(["config", "user.name", "GE-120h-3 test fixture"], root)


def commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit (COMMIT_AGENT_MODE bypasses the
    delegated-commit guard for this SCRATCH repo, which is not this project's
    own worktree and carries no such hook installed anyway)."""
    import os

    git(["add", "-A"], root)
    env = {**os.environ, "COMMIT_AGENT_MODE": "1"}
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", message],
        check=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def stage_all(root: Path) -> None:
    """Stage everything without committing."""
    git(["add", "-A"], root)


def fresh_repo_dir(prefix: str) -> Path:
    """Create a fresh temp directory (caller owns cleanup)."""
    return Path(tempfile.mkdtemp(prefix=prefix))


def run_via_hook(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke *script* through the registered ``run_hook.py`` wrapper.

    This is the real production entry point every pre-commit hooks_manifest
    entry among the five delegates through (see run_hook.py's own module
    docstring: "All pre-commit entries delegate through this script").
    """
    return subprocess.run(
        [_PYTHON, str(RUN_HOOK), str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def run_direct(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke *script* directly -- the real path for check_ac_done_on_merge.py,
    which is on the post-merge stage and is NOT dispatched through run_hook.py
    (GE-120h-3's own constraint: run_hook.py scopes itself to pre-commit)."""
    return subprocess.run(
        [_PYTHON, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Manifest helpers -- read the SAME source-of-truth commit_guardian.json this
# AC's own implementation notes point at.
# ---------------------------------------------------------------------------


def load_manifest_hooks() -> list[dict]:
    """Return the raw hooks_manifest.hooks list from the template manifest."""
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return raw.get("hooks_manifest", {}).get("hooks", [])


def get_hook_entry(hook_id: str) -> dict | None:
    """Return the hooks_manifest entry with id == *hook_id*, or None."""
    for hook in load_manifest_hooks():
        if hook.get("id") == hook_id:
            return hook
    return None


# ---------------------------------------------------------------------------
# Fixture content builders -- deterministic inputs each check exists to
# refuse (or, for the nothing-to-inspect tests, deliberately does NOT name).
# ---------------------------------------------------------------------------


def make_overcomplex_sql(n_branches: int = 40) -> str:
    """Build a .sql function body whose keyword-derived complexity score
    exceeds sql_complexity.max_score (75, per commit_guardian.json)."""
    lines = ["CREATE OR REPLACE FUNCTION complex_fn() RETURNS INT AS $$", "BEGIN"]
    for i in range(n_branches):
        lines.append(
            f"  IF x = {i} THEN y := y + 1; ELSIF x = {i}+1 THEN y := y - 1; END IF;"
        )
    lines.append("  RETURN y;")
    lines.append("END;")
    lines.append("$$ LANGUAGE plpgsql;")
    return "\n".join(lines) + "\n"


def make_untagged_debug_script() -> str:
    """Build a debug script missing every required tag (DEBUG SCRIPT /
    CATEGORY / DESCRIPTION) and every context tag."""
    return '"""\nNo tags here at all.\n"""\nprint("hi")\n'


def make_bloated_test_file() -> str:
    """Build a test_*.py file with an inline dict over max_inline_dict_keys
    (5, per commit_guardian.json) -- the ADR-028 fixture-bloat shape."""
    return (
        "def test_bloated():\n"
        "    data = {\n"
        '        "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6,\n'
        "    }\n"
        "    assert data\n"
    )
