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
      at the repo root. On lock present: appends a JSONL audit record to
      <operational_log_root>/inline_work_guard.jsonl (the root recorded in this
      workspace's build-time declaration, config/knowledge_sink.json -- never
      beneath the repo root, which is deleted with the drive) then exits 2
      (block) or 0 (warn), depending on INLINE_WORK_GUARD_MODE env var (default:
      block). With no usable declaration it warns on stderr, names the
      declaration and writes nothing; the exit code is unchanged. On lock absent:
      exits 0 immediately (fail-open). Any exception: exits 0 (fail-open),
      matching the fail-open pattern of sibling hooks.
"""

import json
import os
import sys
import time
from pathlib import Path

# -- Configuration ------------------------------------------------------------

LOCK_FILENAME = ".build-feature.lock"
AUDIT_LOG_FILENAME = "inline_work_guard.jsonl"  # beneath the declared operational_log_root
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


def _declaration_path() -> Path:
    """Return the build-time declaration of THIS hook's own deployed workspace.

    The hook deploys to ``<output_root>/hooks/`` and is reached through the
    ``.claude/hooks`` symlink, so its resolved location is one directory below
    ``<output_root>``, whose ``config/`` holds ``knowledge_sink.json``. The Gemini
    copy (``<output_root>/gemini/hooks/``, reached through ``.gemini``) is one
    directory deeper, so a ``gemini`` directory is stepped out of.
    """
    install = Path(__file__).resolve().parents[1]
    if install.name == "gemini":
        install = install.parent
    return install / "config" / "knowledge_sink.json"


def _resolve_audit_path() -> tuple[Path | None, str]:
    """Return ``(<operational_log_root>/inline_work_guard.jsonl, "")`` or ``(None, why not)``.

    Standard library only. The audit log lives in the declared operational log
    root (AC INF-500d-4-iv), never beneath the repo root the guard is judging:
    that is a per-drive workspace which is deleted when the drive ends.
    """
    try:
        data = json.loads(_declaration_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "absent: no such file"
    except (OSError, ValueError) as exc:
        return None, f"unreadable or unparseable: {exc}"
    root = data.get("operational_log_root") if isinstance(data, dict) else None
    if not isinstance(root, str) or not root:
        return None, "missing: no 'operational_log_root' entry"
    if not Path(root).is_absolute():
        return None, f"not absolute: 'operational_log_root' is {root!r}"
    return Path(root) / AUDIT_LOG_FILENAME, ""


def _append_audit_record(
    audit_path: Path,
    repo_root: Path,
    tool_name: str,
    file_path: str,
    session_id: str,
    mode: str,
) -> None:
    """Append a JSONL audit record to *audit_path* as one atomic append.

    Args:
        audit_path: The audit file under the declared operational log root.
        repo_root: Absolute path to the git repo root.
        tool_name: Name of the tool being called (e.g. "Edit" or "Write").
        file_path: Path of the file the tool was targeting.
        session_id: Current session identifier.
        mode: Current guard mode ("block" or "warn").
    """
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool_name": tool_name,
        "file_path": file_path,
        "session_id": session_id,
        "mode": mode,
        "lock_file": str(repo_root / LOCK_FILENAME),
    }
    line = (json.dumps(record) + "\n").encode("utf-8")
    try:
        audit_path.parent.mkdir(exist_ok=True)  # the final log directory only
        fd = os.open(audit_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError as exc:
        # Audit failure must not affect the guard outcome -- but say so.
        print(f"inline_work_guard: WARNING: could not append audit record to {audit_path}: {exc}", file=sys.stderr)


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

        audit_path, problem = _resolve_audit_path()
        if audit_path is None:
            # No usable declaration: warn, name it, write nothing workspace-relative.
            audit_note = f"NOT written -- no usable build-time declaration {_declaration_path()} ({problem})"
            print(f"inline_work_guard: WARNING: {audit_note}", file=sys.stderr)
        else:
            audit_note = f"appended to: {audit_path}"
            _append_audit_record(
                audit_path=audit_path,
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
                f"Audit record {audit_note}"
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
                f"Audit record {audit_note}"
            )
            print(msg, file=sys.stderr)
            sys.exit(2)

    except Exception:  # noqa: BLE001 -- hook fail-open: an unexpected error must never block an edit
        sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-12 [python-coder/INF-500d-4-iv]: The audit log moved from
  <repo_root>/debugging/logs/inline_work_guard.jsonl (inside the per-drive
  workspace, destroyed with it) to <operational_log_root>/inline_work_guard.jsonl,
  read from this hook's own workspace declaration (parents[1]/config/
  knowledge_sink.json, standard library only). A missing/unusable declaration
  warns on stderr naming it and writes nothing; the block/warn exit code is
  untouched. The append is one os.write on an O_APPEND descriptor and creates
  only the final log directory. The audit-failure `except Exception: pass` is
  now a narrow OSError handler that warns.
- 2026-05-27 [TICKET-20260527-BuildFeatureInlineWorkGuard]: Initial implementation.
  PreToolUse hook that blocks Edit/Write tool calls while .build-feature.lock
  exists. Uses the lock file protocol: /build-feature writes the lock at start,
  supervisors delete it when they start. Fail-open design ensures no legitimate
  phase-agent edit is ever blocked by a hook crash. Supports warn-vs-block toggle
  via INLINE_WORK_GUARD_MODE env var (default: block). JSONL audit log written
  to debugging/logs/inline_work_guard.jsonl for post-hoc observability.
====================================================================
"""
