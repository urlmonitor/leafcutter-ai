"""
MODULE: readme_marker_recorder.py
GOAL: PostToolUse hook that records a sha256 marker when the Read tool reads a
      README.md file, so readme_read_guard.py can verify README awareness.
BUSINESS CONTEXT: Companion to readme_read_guard.py (EPIC-AgentKnowledgeSystem ticket 01).
      Records that a README was read this session by storing its sha256 hash in
      .claude/.cache/readme_markers/<session_id>.json.
ARCHITECTURE: Reads tool_result and tool_input from stdin JSON. Only fires when
      the file path ends with README.md (case-insensitive). Writes/merges
      {abs_path: sha256} into the session marker file. Fail-open: any exception -> exit 0.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

SESSION_ENV_VAR = "CLAUDE_SESSION_ID"
FULL_READ_LINE_THRESHOLD = 800
COVERAGE_THRESHOLD = 0.90


def _get_session_id() -> str:
    sid = os.environ.get(SESSION_ENV_VAR, "").strip()
    if sid:
        return sid
    ppid = os.getppid()
    return f"fallback-{ppid}"


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


def _save_markers(marker_file: Path, markers: dict) -> None:
    marker_file.parent.mkdir(parents=True, exist_ok=True)
    with open(marker_file, "w", encoding="utf-8") as fh:
        json.dump(markers, fh, indent=2)


def _sha256_file(path: Path) -> str:
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ""


def _count_lines(path: Path) -> int:
    try:
        return path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    except Exception:
        return 0


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}

        tool_input = payload.get("tool_input", {})
        file_path_str = tool_input.get("file_path", "")

        if not file_path_str:
            sys.exit(0)

        # Only process README.md files (case-insensitive)
        if not Path(file_path_str).name.upper() == "README.MD":
            sys.exit(0)

        readme = Path(file_path_str).resolve()
        if not readme.exists():
            sys.exit(0)

        # Coverage check for large files (>800 lines)
        line_count = _count_lines(readme)
        if line_count > FULL_READ_LINE_THRESHOLD:
            # For large files, check if the read covered enough of the file.
            # We use a heuristic: if 'limit' is provided, check coverage ratio.
            limit = tool_input.get("limit")
            offset = tool_input.get("offset", 0)
            if limit is not None:
                coverage = limit / max(line_count, 1)
                if coverage < COVERAGE_THRESHOLD and offset == 0:
                    # Partial read of a large file -- do not record as fully read
                    sys.exit(0)
            # If no limit specified, treat as full read (exit 0 -> record marker)

        # Compute sha256
        sha = _sha256_file(readme)
        if not sha:
            sys.exit(0)

        # Find repo root for marker file location
        repo_root = _find_repo_root(readme)
        if repo_root is None:
            sys.exit(0)

        session_id = _get_session_id()
        marker_file = _marker_path(repo_root, session_id)

        markers = _load_markers(marker_file)
        markers[str(readme)] = sha
        _save_markers(marker_file, markers)

        # Success -- no output needed (PostToolUse hooks should be quiet)
        sys.exit(0)

    except Exception:
        sys.exit(0)  # Fail-open


if __name__ == "__main__":
    main()

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-14 03:10 [EPIC-AgentKnowledgeSystem ticket 01]: Initial implementation.
  PostToolUse Read hook that records sha256 markers when README.md files are read.
  Companion to readme_read_guard.py. Coverage check for large files (>800 lines):
  partial reads (limit < 90% of line count) do not count as a full read.

- 2026-05-15 14:00 [TICKET-20260515-Fix_ReadmeGuard_SessionId_Mismatch]: No logic changes
  to this file. The session_id mismatch bug (different PPIDs in PostToolUse vs
  PreToolUse processes causing marker files to be written under a different name than
  the guard reads) is fixed in readme_read_guard.py via a fallback scan of all
  fallback-*.json files written within the last 24 hours (Option B). This recorder
  continues to write markers under the current process's fallback session ID;
  readme_read_guard.py now knows to scan across all recent fallback files.
====================================================================
"""
