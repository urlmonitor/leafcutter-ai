"""
MODULE: worktree
GOAL: Package for worktree lifecycle utilities (process sweep, log cleanup).
BUSINESS CONTEXT: Exposes sweep_processes as a public API so close-worktree
    workflow and worktree-agent can import or invoke it without duplicating
    platform-specific logic.
ARCHITECTURE: Single-file package; __init__.py re-exports the public API
    surface from sweep_processes so callers can do
    ``from portable_dev_workflow.scripts.worktree import sweep, SweepResult``.
"""

from .sweep_processes import SweepResult, sweep, sweep_log_files

__all__ = ["SweepResult", "sweep", "sweep_log_files"]
