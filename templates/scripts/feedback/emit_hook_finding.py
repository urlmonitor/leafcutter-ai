"""
MODULE: leafcutter/scripts/feedback/emit_hook_finding.py
GOAL: Lightweight helper for pre-commit hooks to emit one finding to feedback.jsonl
      by calling submit_feedback.main() in-process (fast, no subprocess shell-out).
BUSINESS CONTEXT: Each commit_guardian hook that surfaces a violation calls
      emit_finding() with one line. The call is failure-isolated: if submit_feedback
      raises or returns non-zero, emit_finding() logs a stderr warning and returns
      False — the calling hook's exit code and stdout output are never affected.
ARCHITECTURE: Imports submit_feedback from the local package tree (relative to this
      file's location). Falls back to subprocess.run if the import fails (different
      Python env). The feedback.jsonl path defaults to the project default via
      submit_feedback._JSONL_DEFAULT. Category defaults to process-finding; callers
      may override with tooling-issue or quality-concern where semantically appropriate.
DOC_LINKS:
  - docs/how-to/feedback-collection.md

Usage (in a hook):
    from scripts.feedback.emit_hook_finding import emit_finding

    # On violation found:
    emit_finding(
        hook_name="check_orphan_workers",
        outcome="block",          # "warn" | "block"
        note="Found 2 idle orphan workers from other worktrees",
        tags=["orphan-workers"],
    )
    # Hook continues normally regardless of emit_finding's return value.

    # On clean pass: do NOT call emit_finding (no entry for clean passes).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import resolve
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _THIS_DIR.parent.parent  # leafcutter/scripts/../..

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _import_submit_feedback():
    """Import submit_feedback module, returning it or None on failure.

    Returns:
        Module object or None.
    """
    try:
        import importlib.util

        _sf_path = _THIS_DIR / "submit_feedback.py"
        spec = importlib.util.spec_from_file_location("submit_feedback", _sf_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod  # noqa: TRY300
    except Exception as exc:  # noqa: BLE001 — import fallback is intentional
        print(f"[emit_hook_finding] submit_feedback import failed (will use subprocess fallback): {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_finding(
    hook_name: str,
    outcome: str,
    note: str,
    category: str = "process-finding",
    tags: list[str] | None = None,
    branch: str | None = None,
    staged_files_count: int | None = None,
    jsonl_path: str | None = None,
    config_path: str | None = None,
) -> bool:
    """Emit one hook finding to feedback.jsonl.

    Calls submit_feedback.main() in-process. On any failure, logs a warning to
    stderr and returns False. Never raises — the calling hook always continues.

    Args:
        hook_name: Name of the calling hook (e.g. ``check_orphan_workers``).
        outcome: ``"warn"`` or ``"block"``.
        note: Short one-sentence description of the finding (verbatim).
        category: Feedback category id. Default: ``"process-finding"``.
        tags: List of kebab-case tag strings. Default: empty list.
        branch: Git branch name at commit time (optional).
        staged_files_count: Number of staged files (optional integer).
        jsonl_path: Override path to feedback.jsonl (optional).
        config_path: Override path to feedback_categories.yaml (optional).

    Returns:
        bool: True when the feedback entry was written successfully, False otherwise.
    """
    try:
        return _call_submit_feedback(
            hook_name=hook_name,
            outcome=outcome,
            note=note,
            category=category,
            tags=tags or [],
            branch=branch,
            staged_files_count=staged_files_count,
            jsonl_path=jsonl_path,
            config_path=config_path,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("could not emit finding for %s: %s", hook_name, exc)
        return False


def _call_submit_feedback(
    hook_name: str,
    outcome: str,
    note: str,
    category: str,
    tags: list[str],
    branch: str | None,
    staged_files_count: int | None,
    jsonl_path: str | None,
    config_path: str | None,
) -> bool:
    """Build argv and call submit_feedback.main() in-process.

    Args:
        hook_name: Name of the calling hook.
        outcome: ``"warn"`` or ``"block"``.
        note: Short finding description.
        category: Category id.
        tags: List of tag strings.
        branch: Git branch name (optional).
        staged_files_count: Staged file count (optional).
        jsonl_path: Override JSONL path (optional).
        config_path: Override categories.yaml path (optional).

    Returns:
        bool: True on exit code 0, False otherwise.
    """
    sf_mod = _import_submit_feedback()
    if sf_mod is None:
        return _call_submit_feedback_subprocess(
            hook_name, outcome, note, category, tags,
            branch, staged_files_count, jsonl_path, config_path,
        )

    argv = _build_argv(
        hook_name, outcome, note, category, tags,
        branch, staged_files_count, jsonl_path, config_path,
    )
    try:
        exit_code = sf_mod.main(argv)
    except SystemExit as exc:
        return exc.code == 0
    else:
        return exit_code == 0


def _build_argv(
    hook_name: str,
    outcome: str,
    note: str,
    category: str,
    tags: list[str],
    branch: str | None,
    staged_files_count: int | None,
    jsonl_path: str | None,
    config_path: str | None,
) -> list[str]:
    """Build the argv list for submit_feedback.main().

    Args:
        hook_name: Calling hook name.
        outcome: warn or block.
        note: Finding description.
        category: Category id.
        tags: List of tag strings.
        branch: Git branch (optional).
        staged_files_count: Staged file count (optional).
        jsonl_path: JSONL path override (optional).
        config_path: Config path override (optional).

    Returns:
        list[str]: Argument list for submit_feedback.main().
    """
    argv = [
        "--phase", hook_name,
        "--category", category,
        "--note", note,
        "--source", "hook",
        "--hook-name", hook_name,
        "--outcome", outcome,
    ]
    if tags:
        argv += ["--tags", ",".join(tags)]
    if branch is not None:
        argv += ["--branch", branch]
    if staged_files_count is not None:
        argv += ["--staged-files-count", str(staged_files_count)]
    if jsonl_path is not None:
        argv += ["--jsonl", jsonl_path]
    if config_path is not None:
        argv += ["--config", config_path]
    return argv


def _call_submit_feedback_subprocess(
    hook_name: str,
    outcome: str,
    note: str,
    category: str,
    tags: list[str],
    branch: str | None,
    staged_files_count: int | None,
    jsonl_path: str | None,
    config_path: str | None,
) -> bool:
    """Fallback: call submit_feedback.py via subprocess when import fails.

    Args:
        hook_name: Calling hook name.
        outcome: warn or block.
        note: Finding description.
        category: Category id.
        tags: List of tag strings.
        branch: Git branch (optional).
        staged_files_count: Staged file count (optional).
        jsonl_path: JSONL path override (optional).
        config_path: Config path override (optional).

    Returns:
        bool: True when subprocess exits 0.
    """
    import subprocess

    sf_path = str(_THIS_DIR / "submit_feedback.py")
    argv = [sys.executable, sf_path] + _build_argv(
        hook_name, outcome, note, category, tags,
        branch, staged_files_count, jsonl_path, config_path,
    )
    try:
        result = subprocess.run(argv, capture_output=True)
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"emit_hook_finding: subprocess fallback failed: {exc}", file=sys.stderr)
        return False
    return result.returncode == 0


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-15 15:35 [EPIC-FeedbackCollection/ticket-09]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Lightweight in-process helper for commit_guardian hooks to emit JSONL feedback.
#   Failure-isolated: any exception returns False and logs to stderr; the calling
#   hook's exit code is never affected. Falls back to subprocess.run when import
#   fails. Category defaults to process-finding; hooks may override with
#   tooling-issue or quality-concern where appropriate. Only call on violation
#   found — not on clean passes (no entry for clean results).
# ====================================================================
