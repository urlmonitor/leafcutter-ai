"""
MODULE: project_context_discovery
GOAL: Runtime discovery helpers for PROJECT_CONTEXT.md companion files.
BUSINESS CONTEXT: Portable agents in leafcutter/templates/agents/
    are project-agnostic. Project-specific knowledge is supplied via a
    PROJECT_CONTEXT.md companion file that each agent reads at startup.
    This module provides helpers used by build.py to discover and report on
    those companion files — for metadata/reporting purposes only. The build
    pipeline does NOT inline PROJECT_CONTEXT.md content into compiled agent
    bodies (ADR-025 decision 3: runtime-only discovery).
ARCHITECTURE: Pure-read module. No side effects beyond stderr log lines.
    Imported by build.py; may also be used standalone or in tests.
    See leafcutter/docs/conventions/PROJECT_CONTEXT-injection.md
    and ADR-025 for the full convention specification.
"""

from __future__ import annotations

import sys
from pathlib import Path


def find_project_contexts(project_root: Path | None = None) -> list[tuple[str, Path]]:
    """Return (agent_name, path) pairs for every PROJECT_CONTEXT.md found.

    Walks ``.agents/agents/`` relative to *project_root* (or the current
    working directory when *project_root* is ``None``) and collects every
    subdirectory that contains a file named exactly ``PROJECT_CONTEXT.md``
    (uppercase, canonical per ADR-025 decision 2).  Lowercase variants are
    silently ignored — they violate the naming convention and must not be
    treated as valid context files.

    The build pipeline does NOT inline ``PROJECT_CONTEXT.md`` content into
    the compiled ``.claude/agents/<name>.md`` body (ADR-025 decision 3 —
    runtime-only discovery).  This helper is a pure read operation used
    only to populate the ``project_context_present: bool`` field in the
    per-agent compile-metadata report.

    Args:
        project_root: Absolute path to the project root.  Defaults to
            ``Path.cwd()`` when ``None``.

    Returns:
        Sorted list of ``(agent_name, path)`` tuples — one entry per agent
        whose ``.agents/agents/<agent_name>/PROJECT_CONTEXT.md`` exists.
        Agent names are the subdirectory names under ``.agents/agents/``.
    """
    root = project_root if project_root is not None else Path.cwd()
    agents_dir = root / ".agents" / "agents"
    if not agents_dir.is_dir():
        return []
    results: list[tuple[str, Path]] = []
    for subdir in sorted(agents_dir.iterdir()):
        if not subdir.is_dir():
            continue
        ctx = subdir / "PROJECT_CONTEXT.md"
        if ctx.exists():
            results.append((subdir.name, ctx))
    return results


def get_project_context_metadata(
    agent_name: str,
    project_root: Path | None = None,
) -> dict[str, bool]:
    """Return compile-metadata dict for a single agent's PROJECT_CONTEXT presence.

    Checks whether ``.agents/agents/<agent_name>/PROJECT_CONTEXT.md`` exists.
    When absent, emits a one-line debug message to stderr per ADR-025 decision 4
    (missing-context fallback: silent skip + one-line debug log).

    The compiled agent body is NOT altered by this function — the
    ``project_context_present`` flag is for reporting purposes only.

    Args:
        agent_name: The agent identifier (kebab-case, e.g. ``"sql-coder"``).
        project_root: Absolute path to the project root.  Defaults to
            ``Path.cwd()`` when ``None``.

    Returns:
        ``{"project_context_present": True}`` when the file exists,
        ``{"project_context_present": False}`` otherwise.
    """
    root = project_root if project_root is not None else Path.cwd()
    ctx_path = root / ".agents" / "agents" / agent_name / "PROJECT_CONTEXT.md"
    if ctx_path.exists():
        return {"project_context_present": True}
    print(
        f"PROJECT_CONTEXT.md not found for {agent_name}; running template-only",
        file=sys.stderr,
    )
    return {"project_context_present": False}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-15 10:15 [python-coder/EPIC-PortableSQLAgents/ticket-01]: (#EPIC-LeafcutterMVP/01)
#   Created this module to implement PROJECT_CONTEXT runtime discovery
#   per ADR-025 decisions 2-4. Functions were originally written inline
#   in build.py but extracted here to keep build.py under 400 lines.
#   find_project_contexts() walks .agents/agents/ and returns (name, path)
#   tuples for all agents with a PROJECT_CONTEXT.md present.
#   get_project_context_metadata() returns a {"project_context_present": bool}
#   dict for a single agent and emits the ADR-025 decision-4 debug log when
#   the file is absent. Both functions are pure read operations — no side
#   effects on compiled agent bodies (runtime-only discovery per ADR-025).
# ====================================================================
