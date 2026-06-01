"""
MODULE: inline_work_guard.py
GOAL: PreToolUse hook that blocks Edit/Write tool calls while .build-feature.lock
      exists, preventing /build-feature from doing inline implementation work
      before dispatching a supervisor agent.
BUSINESS CONTEXT: Enforcement hook for TICKET-20260527-BuildFeatureInlineWorkGuard.
      Claude sometimes ignores the requirement to dispatch a supervisor and instead
      performs implementation work inline when /build-feature is invoked. This hook
      enforces the constraint mechanically: /build-feature writes .build-feature.lock
      at start; epic-supervisor and build-single-ticket delete it when they start.
      Any Edit/Write while the lock exists means a supervisor was not dispatched.
ARCHITECTURE: Reads tool_input from stdin JSON, walks parent dirs to find the
      per-worktree repo root (where .git lives), checks for .build-feature.lock
      at the repo root. On lock present: appends a JSONL audit record then exits 2
      (block) or 0 (warn), depending on INLINE_WORK_GUARD_MODE env var (default:
      block). On lock absent: exits 0 immediately (fail-open). Any exception: exits
      0 (fail-open), matching the fail-open pattern of sibling hooks.
"""

import json
import os
import sys
import time
from pathlib import Path

# -- Configuration ------------------------------------------------------------

LOCK_FILENAME = ".build-feature.lock"
AUDIT_LOG_FILENAME = "debugging/logs/inline_work_guard.jsonl"
MODE_ENV_VAR = "INLINE_WORK_GUARD_MODE"
DEFAULT_MODE = "block"
SESSION_ENV_VAR = "CLAUDE_SESSION_ID"


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


def _get_session_id() -> str:
    """Return the session ID from env var or a fallback based on parent PID.

    Returns:
        Session ID string from CLAUDE_SESSION_ID env var, or fallback-<ppid>.
    """
    sid = os.environ.get(SESSION_ENV_VAR, "").strip()
    if sid:
        return sid
    ppid = os.getppid()
    return f"fallback-{ppid}"


def _append_audit_record(
    repo_root: Path,
    tool_name: str,
    file_path: str,
    session_id: str,
    mode: str,
) -> None:
    """Append a JSONL audit record to the audit log file.

    Args:
        repo_root: Absolute path to the git repo root.
        tool_name: Name of the tool being called (e.g. "Edit" or "Write").
        file_path: Path of the file the tool was targeting.
        session_id: Current session identifier.
        mode: Current guard mode ("block" or "warn").
    """
    audit_path = repo_root / AUDIT_LOG_FILENAME
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool_name": tool_name,
            "file_path": file_path,
            "session_id": session_id,
            "mode": mode,
            "lock_file": str(repo_root / LOCK_FILENAME),
        }
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        # Audit failure must not affect the guard outcome
        pass


def main() -> None:
    """Main entry point for the inline_work_guard PreToolUse hook."""
    try:
        # -- Read stdin payload -----------------------------------------------
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        tool_input = payload.get("tool_input", payload)

        # Extract the tool name (passed by the harness in the outer envelope)
        tool_name = payload.get("tool_name", "Edit")

        # Get the file path being edited/written
        file_path_str = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or ""
        )

        # -- Determine repo root ----------------------------------------------
        # Start from the file being edited if possible; fall back to $PWD
        if file_path_str:
            start_dir = Path(file_path_str).resolve().parent
        else:
            start_dir = Path(os.environ.get("PWD", ".")).resolve()

        repo_root = _find_repo_root(start_dir)
        if repo_root is None:
            # Try from $PWD directly
            repo_root = _find_repo_root(Path(os.environ.get("PWD", ".")).resolve())
        if repo_root is None:
            sys.exit(0)  # Not in a git repo -> fail-open

        # -- Check for lock file ----------------------------------------------
        lock_path = repo_root / LOCK_FILENAME
        if not lock_path.exists():
            sys.exit(0)  # No lock -> allow through (fail-open)

        # -- Lock present: guard fires ----------------------------------------
        mode = os.environ.get(MODE_ENV_VAR, DEFAULT_MODE).strip().lower()
        session_id = _get_session_id()

        _append_audit_record(
            repo_root=repo_root,
            tool_name=tool_name,
            file_path=file_path_str,
            session_id=session_id,
            mode=mode,
        )

        if mode == "warn":
            # Warn mode: log and allow through
            msg = (
                f"inline_work_guard: WARNING (warn mode)\n\n"
                f"A {tool_name} call on '{file_path_str}' was attempted while\n"
                f"  {lock_path}\n"
                f"exists. In block mode this call would be blocked.\n\n"
                f"/build-feature must dispatch a supervisor first:\n"
                f"  - For epics: dispatch epic-supervisor via the Agent tool.\n"
                f"  - For standalone tickets: invoke the build-single-ticket sub-skill.\n\n"
                f"The supervisor will delete the lock file, allowing phase agents to run.\n"
                f"Audit record appended to: {repo_root / AUDIT_LOG_FILENAME}"
            )
            print(msg, file=sys.stderr)
            sys.exit(0)
        else:
            # Block mode (default): block the tool call
            msg = (
                f"inline_work_guard: BLOCKED\n\n"
                f"A {tool_name} call on '{file_path_str}' was blocked because\n"
                f"  {lock_path}\n"
                f"exists. This means /build-feature has NOT yet dispatched a supervisor.\n\n"
                f"You MUST dispatch a supervisor before making any file edits:\n"
                f"  - For epics: dispatch epic-supervisor via the Agent tool.\n"
                f"  - For standalone tickets: invoke the build-single-ticket sub-skill.\n\n"
                f"The supervisor will delete the lock file, unblocking phase agents.\n"
                f"Audit record appended to: {repo_root / AUDIT_LOG_FILENAME}"
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
- 2026-05-27 [TICKET-20260527-BuildFeatureInlineWorkGuard]: Initial implementation.
  PreToolUse hook that blocks Edit/Write tool calls while .build-feature.lock
  exists. Uses the lock file protocol: /build-feature writes the lock at start,
  supervisors delete it when they start. Fail-open design ensures no legitimate
  phase-agent edit is ever blocked by a hook crash. Supports warn-vs-block toggle
  via INLINE_WORK_GUARD_MODE env var (default: block). JSONL audit log written
  to debugging/logs/inline_work_guard.jsonl for post-hoc observability.
====================================================================
"""
