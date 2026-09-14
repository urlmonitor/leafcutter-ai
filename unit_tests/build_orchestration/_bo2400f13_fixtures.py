"""
MODULE: unit_tests/build_orchestration/_bo2400f13_fixtures.py
GOAL: Shared REAL-git-repo fixture helpers for the BO-2400f-13 family of
      tests (BO-2400f-13, -i, -ii, -iii, -iv) — the occupied-build-workspace
      refusal criteria.

NOT a test file itself (leading underscore — mirrors the convention already
established by unit_tests/_workflow_engine_harness.py). Nothing in here is
collected by pytest.

=== Why a shared module ===

Every BO-2400f-13-* test that wants REAL-SUBPROCESS evidence (the mandatory
angle for this whole family — see each AC's test_rationale) needs the same
scaffolding: a real "origin" repo, a real clone standing in for the fast
lane's main repo, and a real invocation of
``setup_ticket_worktree.py create-fastlane-worktree <slug>`` as a subprocess.
Duplicating that scaffolding five times invites the five copies to drift.

=== The _git_toplevel() anchoring trap (read before editing) ===

``setup_ticket_worktree.py``'s ``_git_toplevel(anchor=None)`` resolves the
repository root from ``Path(__file__).resolve().parent`` — the SCRIPT'S OWN
directory — not the process cwd and not an argument. Invoking the real
deployed script in place (at its real path inside this worktree) would
therefore resolve to *this worktree's own repo*, not an isolated fixture,
and could create real worktrees/branches inside the actual development tree.

The fix used throughout this module: COPY the script under test into
``<repo_root>/scripts/setup_ticket_worktree.py`` inside the fixture's own
throwaway repo. ``_git_toplevel()`` then resolves ``anchor`` to that
``scripts/`` directory, and ``git -C <anchor> rev-parse --show-toplevel``
correctly returns the fixture's ``repo_root`` — never the real development
tree. ``_resolve_installed_layout(repo_root)`` then sees a non-git parent
(the fixture's own tmp_path) and selects the dev-layout pair
``(repo_root, repo_root.parent)``, so worktrees land at
``tmp_path/worktrees/<slug>`` exactly as this module's helpers expect.

Verified live (2026-09-07, manual probe) that this technique round-trips
correctly for: fresh-open, branch-reconnect, bare-directory occupant,
branch-checked-out-elsewhere, and existing-empty-directory scenarios — see
each function's docstring for the exact reproduction.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"
DEPLOYED_SCRIPT = _REPO_ROOT / "scripts" / "setup_ticket_worktree.py"

_GIT_USER_EMAIL = "test-writer@example.com"
_GIT_USER_NAME = "Test Writer"


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command anchored at *cwd* and return the CompletedProcess."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def init_origin_repo(path: Path) -> str:
    """Create a real bare-enough 'origin' repo at *path* with one commit.

    Carries a minimal ``.pre-commit-config.yaml`` so that, after cloning,
    ``_establish_pre_commit_config``'s copy-fallback step succeeds and the
    AC-5 bootstrap fail-fast probe in ``_bootstrap()`` never fires — none of
    that machinery is what this AC family is testing, and a fixture that
    trips it produces failures unrelated to occupancy detection.

    Returns the initial commit SHA.
    """
    path.mkdir(parents=True, exist_ok=True)
    run_git(["init", "-q", "-b", "main"], path)
    run_git(["config", "user.email", _GIT_USER_EMAIL], path)
    run_git(["config", "user.name", _GIT_USER_NAME], path)
    (path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (path / "README.md").write_text("initial content\n", encoding="utf-8")
    run_git(["add", "-A"], path)
    run_git(["commit", "-q", "-m", "initial commit"], path)
    return run_git(["rev-parse", "HEAD"], path).stdout.strip()


def advance_origin(path: Path, filename: str, content: str, message: str) -> str:
    """Add one commit to an already-initialised origin repo. Returns the new SHA."""
    (path / filename).write_text(content, encoding="utf-8")
    run_git(["add", "-A"], path)
    run_git(["commit", "-q", "-m", message], path)
    return run_git(["rev-parse", "HEAD"], path).stdout.strip()


def clone_repo_root(origin: Path, tmp_path: Path, dirname: str = "repo_root") -> Path:
    """Clone *origin* into ``tmp_path/<dirname>`` and configure a git identity.

    ``tmp_path`` itself must NOT be a git repository — this is what makes
    ``_resolve_installed_layout()`` select the dev-layout pair
    ``(repo_root, tmp_path)``, putting worktrees at ``tmp_path/worktrees/``.
    """
    repo_root = tmp_path / dirname
    run_git(["clone", "-q", str(origin), str(repo_root)], tmp_path)
    run_git(["config", "user.email", _GIT_USER_EMAIL], repo_root)
    run_git(["config", "user.name", _GIT_USER_NAME], repo_root)
    return repo_root


def stage_script(repo_root: Path, source: Path = DEPLOYED_SCRIPT) -> Path:
    """Copy *source* (the script under test) into ``repo_root/scripts/``.

    This is the anchoring trick documented in the module docstring: it makes
    ``_git_toplevel(anchor=None)`` resolve to *repo_root*, not the real
    development tree, when the copied script is later invoked directly.

    Returns the path to the copied script.
    """
    dest_dir = repo_root / "scripts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "setup_ticket_worktree.py"
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def run_create_fastlane_worktree(
    script_path: Path, slug: str, timeout: int = 60
) -> subprocess.CompletedProcess:
    """Invoke ``<script_path> create-fastlane-worktree <slug>`` as a real subprocess.

    Returns the CompletedProcess (never raises on non-zero exit — callers
    assert on ``.returncode`` themselves, since a refusal or a today's-defect
    exit is exactly what several tests want to inspect).
    """
    return subprocess.run(
        [sys.executable, str(script_path), "create-fastlane-worktree", slug],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_json_stdout(proc: subprocess.CompletedProcess) -> dict[str, Any] | None:
    """Best-effort parse of *proc*'s stdout for the script's single JSON payload line.

    ``git worktree add`` itself writes progress prose ("Preparing worktree...",
    "HEAD is now at ...", "branch '...' set up to track ...") to STDOUT, not
    stderr — confirmed by direct execution. The script's own
    ``print(json.dumps(payload))`` is therefore not necessarily the ONLY line
    on stdout. This scans stdout's lines from the LAST one backwards and
    returns the first line that parses as a JSON object, matching how a real
    caller (jq, or fast-lane-ship.js's own agent prompt) would extract it.

    Returns None (never raises) when no line parses as JSON — the correct
    outcome for asserting "today, there is no discriminated payload at all",
    which is exactly the RED state several tests pin down.
    """
    text = proc.stdout or ""
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue
    return None


def make_occupied_bare_directory(worktrees_dir: Path, slug: str) -> Path:
    """Create a plain, non-empty, UNREGISTERED directory at worktrees_dir/<slug>.

    This is the exact shape that produced KI-BO-015 in production: an
    ordinary directory nobody registered as any git worktree at all.
    """
    target = worktrees_dir / slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "leftover.txt").write_text("unregistered leftover content\n", encoding="utf-8")
    return target


def make_registered_worktree_on_other_branch(
    repo_root: Path, worktrees_dir: Path, slug: str, branch: str = "feature/unrelated-work"
) -> Path:
    """Register a real git worktree at worktrees_dir/<slug> on an unrelated branch."""
    target = worktrees_dir / slug
    run_git(["worktree", "add", "-b", branch, str(target), "main"], repo_root)
    return target


def relocate_worktree(repo_root: Path, old_path: Path, new_path: Path) -> None:
    """Move a registered worktree from *old_path* to *new_path* via `git worktree move`.

    Leaves *old_path* free while the worktree's branch stays checked out at
    *new_path* — the "branch checked out elsewhere, location itself free"
    occupancy condition BO-2400f-13's second scenario names explicitly.
    """
    run_git(["worktree", "move", str(old_path), str(new_path)], repo_root)


def make_fresh_fastlane_worktree(script_path: Path, slug: str, timeout: int = 60) -> Path:
    """Run the real CLI once to produce a genuine prior fast-lane worktree.

    Returns the resulting worktree path. Raises AssertionError if the CLI
    call itself failed — callers use this only to set up a precondition, not
    to test the CLI call itself.
    """
    proc = run_create_fastlane_worktree(script_path, slug, timeout=timeout)
    payload = parse_json_stdout(proc)
    if proc.returncode != 0 or not payload or not payload.get("worktree_path"):
        raise AssertionError(
            "Fixture precondition failed: could not create a prior fast-lane "
            f"worktree for slug={slug!r}. exit={proc.returncode} "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    return Path(payload["worktree_path"])
