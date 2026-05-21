"""
MODULE: readme_read_guard.py
GOAL: PreToolUse hook that blocks Edit/Write tool calls when the nearest-ancestor
      README.md has not been read this session (sha256 marker not present in cache).
BUSINESS CONTEXT: Enforcement hook for EPIC-AgentKnowledgeSystem. Ensures agents
      read folder READMEs before editing in gated directories. Part of the
      load-bearing README system introduced in ticket 01.
ARCHITECTURE: Reads tool_input from stdin JSON, walks parent dirs to find nearest
      README.md, checks sha256 marker in .claude/.cache/readme_markers/<session_id>.json.
      If the per-session file does not contain the required hash, falls back to
      scanning all fallback-*.json files written within the last 24 hours (Option B
      fix for PPID-mismatch when CLAUDE_SESSION_ID is absent). Exits 0 to allow,
      exits 2 to block. Fail-open: any exception -> exit 0.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# -- Configuration ------------------------------------------------------------

SKIP_LIST = {
    ".venv", "__pycache__", ".pytest_cache", "node_modules",
    ".git", "tickets", "docs",
}

GATED_PREFIXES = (
    ".claude/agents/",
    ".claude/skills/",
    ".claude/hooks/",
    "alembic/versions/",
)

TRIVIAL_EDIT_OLD_LEN = 200
TRIVIAL_EDIT_DELTA = 100
BYPASS_ENV_VAR = "CLAUDE_NO_README_CHECK"
SESSION_ENV_VAR = "CLAUDE_SESSION_ID"
FALLBACK_SCAN_MAX_AGE_SECONDS = 86400  # 24 hours


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from start to find the git repo root directory.

    Args:
        start: The directory to begin searching from.

    Returns:
        The Path to the repo root (.git directory found), or None if not found.
    """
    current = start
    for _ in range(20):
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _in_skip_list(file_path: Path) -> bool:
    """Return True if any path component is in SKIP_LIST."""
    for part in file_path.parts:
        if part in SKIP_LIST:
            return True
    return False


def _is_gated(file_path: Path, repo_root: Path) -> bool:
    """Return True if the file is under a gated prefix (relative to repo root).

    Args:
        file_path: Absolute path of the file being edited.
        repo_root: Absolute path to the git repo root.

    Returns:
        True if the file falls under any GATED_PREFIXES entry.
    """
    try:
        rel = file_path.relative_to(repo_root)
        rel_str = str(rel).replace("\\", "/")
        return any(rel_str.startswith(p) for p in GATED_PREFIXES)
    except ValueError:
        return False


def _find_nearest_readme(file_path: Path, repo_root: Path) -> Path | None:
    """Walk parent dirs from file_path up to repo_root to find nearest README.md.

    Args:
        file_path: Absolute path of the file being edited.
        repo_root: Absolute path to the git repo root (search stops here).

    Returns:
        Path to the nearest README.md, or None if none found up to repo_root.
    """
    current = file_path.parent
    while True:
        candidate = current / "README.md"
        if candidate.exists():
            return candidate
        if current == repo_root:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _get_session_id() -> str:
    """Return the session ID from env var or a fallback based on parent PID."""
    sid = os.environ.get(SESSION_ENV_VAR, "")
    if sid:
        return sid
    ppid = os.getppid()
    return f"fallback-{ppid}"


def _marker_path(repo_root: Path, session_id: str) -> Path:
    return repo_root / ".claude" / ".cache" / "readme_markers" / f"{session_id}.json"


def _load_markers(marker_file: Path) -> dict:
    """Load the session marker JSON file, returning an empty dict on any error.

    Args:
        marker_file: Path to the session marker JSON file.

    Returns:
        Dict mapping absolute README paths to their sha256 hashes.
    """
    if not marker_file.exists():
        return {}
    try:
        with open(marker_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _readme_sha256(readme_path: Path) -> str:
    try:
        content = readme_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ""


def _scan_fallback_markers(cache_dir: Path, readme_abs: str, expected_sha: str) -> bool:
    """Scan all fallback-*.json marker files for a matching README hash.

    This is Option B: when the per-session marker file does not contain the required
    README hash (due to PPID mismatch between PostToolUse and PreToolUse processes),
    scan all fallback-*.json files in the cache directory. If any file was written
    within the last 24 hours and contains the expected {readme_abs: sha256} entry,
    allow the edit.

    Args:
        cache_dir: Path to .claude/.cache/readme_markers/ directory.
        readme_abs: Absolute path string of the README being checked.
        expected_sha: SHA-256 hash of the README file content.

    Returns:
        True if a recent fallback marker file contains the matching hash; False otherwise.
    """
    if not cache_dir.is_dir():
        return False
    now = time.time()
    for candidate in cache_dir.glob("fallback-*.json"):
        try:
            age = now - candidate.stat().st_mtime
            if age > FALLBACK_SCAN_MAX_AGE_SECONDS:
                continue
            with open(candidate, "r", encoding="utf-8") as fh:
                markers = json.load(fh)
            if markers.get(readme_abs) == expected_sha:
                return True
        except Exception:
            continue
    return False


def main() -> None:
    try:
        # -- Bypass env var ---------------------------------------------------
        if os.environ.get(BYPASS_ENV_VAR, "").strip():
            sys.exit(0)

        # -- Read stdin payload -----------------------------------------------
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        tool_input = payload.get("tool_input", payload)

        # Get the file path being edited/written
        file_path_str = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or ""
        )
        if not file_path_str:
            sys.exit(0)  # Can't determine path -> fail-open

        file_path = Path(file_path_str).resolve()

        # -- Skip-list check --------------------------------------------------
        if _in_skip_list(file_path):
            sys.exit(0)

        # -- Repo root detection ----------------------------------------------
        repo_root = _find_repo_root(file_path)
        if repo_root is None:
            sys.exit(0)  # Not in a git repo -> fail-open

        # -- Gated check ------------------------------------------------------
        # Only enforce for gated paths; skip everything else
        if not _is_gated(file_path, repo_root):
            sys.exit(0)

        # -- Trivial-edit skip ------------------------------------------------
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        if (
            len(old_string) < TRIVIAL_EDIT_OLD_LEN
            and abs(len(new_string) - len(old_string)) < TRIVIAL_EDIT_DELTA
        ):
            sys.exit(0)

        # -- Find nearest README ----------------------------------------------
        readme = _find_nearest_readme(file_path, repo_root)
        if readme is None:
            sys.exit(0)  # No README found -> fail-open (can't enforce)

        # -- Check primary session marker -------------------------------------
        session_id = _get_session_id()
        marker_file = _marker_path(repo_root, session_id)
        markers = _load_markers(marker_file)

        readme_abs = str(readme.resolve())
        expected_sha = _readme_sha256(readme)

        if markers.get(readme_abs) == expected_sha:
            sys.exit(0)  # README was read this session

        # -- Fallback scan (Option B: tolerate PPID mismatch) -----------------
        # When CLAUDE_SESSION_ID is absent, PostToolUse and PreToolUse hooks run
        # in different processes with different PPIDs, so the per-session marker
        # file may not match. Scan all recent fallback-*.json files for the hash.
        # Only applies when the session_id starts with "fallback-" (no real session ID).
        if session_id.startswith("fallback-"):
            cache_dir = repo_root / ".claude" / ".cache" / "readme_markers"
            if _scan_fallback_markers(cache_dir, readme_abs, expected_sha):
                sys.exit(0)  # Found in a recent fallback marker

        # -- Block ------------------------------------------------------------
        rel_readme = readme.relative_to(repo_root)
        rel_file = file_path.relative_to(repo_root)
        msg = (
            f"readme_read_guard: BLOCKED\n\n"
            f"You are about to edit '{rel_file}' but have not read the nearest-ancestor README:\n"
            f"  {rel_readme}\n\n"
            f"Read it now with:\n"
            f"  Read(file_path='{readme_abs}')\n\n"
            f"Also consider reading parent-folder READMEs for cross-cutting conventions.\n"
            f"Bypass (bulk migrations only): set CLAUDE_NO_README_CHECK=1 in env."
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    except Exception:
        # Fail-open: any unexpected error must not block legitimate edits
        sys.exit(0)


if __name__ == "__main__":
    main()

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-14 03:10 [EPIC-AgentKnowledgeSystem ticket 01]: Initial implementation.
  Three hooks introduced for README enforcement and per-agent memory.
  readme_read_guard.py enforces nearest-ancestor README reads before edits
  in gated directories. Fail-open design ensures no legitimate edit is ever
  blocked by a hook crash.

- 2026-05-15 14:00 [TICKET-20260515-Fix_ReadmeGuard_SessionId_Mismatch]: Option B fallback
  scan. When CLAUDE_SESSION_ID is absent, PostToolUse and PreToolUse hooks run in
  different processes with different PPIDs, causing the per-session marker file to
  never match. Fix: after the primary session-file lookup fails and the session_id
  starts with "fallback-", scan all fallback-*.json files in the cache directory.
  If any was written within the last 24 hours and contains the expected README sha256,
  allow the edit. readme_marker_recorder.py requires no logic change. The fallback
  scan is wrapped in the existing fail-open guard.
====================================================================
"""
