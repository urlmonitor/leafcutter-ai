"""
MODULE: build_shim_env
GOAL: Read the shim strategy a build run is DECLARED to use (the
    ``LEAFCUTTER_SHIM_STRATEGY`` environment variable overrides the config)
    and resolve the method it can actually use.
BUSINESS CONTEXT: The workspace maker (``worktree.py``) tells its install
    build to copy, never link, so no link creation happens anywhere on the
    ensure path (BO-4300b-4). Split out of ``build_helpers.py`` because that
    file is already over its file-size limit and may not grow.
ARCHITECTURE: Standalone, no shared state; imported by ``build_helpers.py``
    (``install_shims``). Part of the build tool itself, run from the source
    tree -- never deployed into a consumer install, so no deploy-manifest
    entry is needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from build_shim_probe import resolve_effective_shim_strategy


def declared_shim_strategy(config: dict[str, Any]) -> str:
    """Return the declared shim strategy; ``LEAFCUTTER_SHIM_STRATEGY`` (set by the workspace maker) wins.

    BO-4300b-4: a workspace build is told to copy, never link, so no link
    creation happens anywhere on the ensure path.
    """
    return os.environ.get("LEAFCUTTER_SHIM_STRATEGY") or config.get("shim_strategy", "auto")


def effective_shim_strategy(config: dict[str, Any], target_root: Path) -> str:
    """Return the shim method this run can actually use for *config* under *target_root*.

    The declared strategy (``declared_shim_strategy``) is recomputed through
    ``build_shim_probe.resolve_effective_shim_strategy`` (ADR-041 section 1),
    exactly as ``install_shims`` did before this module existed.
    """
    return resolve_effective_shim_strategy(declared_shim_strategy(config), target_root)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 12:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   Created: moved out of build_helpers.py (over its file-size limit) so the
#   workspace maker's LEAFCUTTER_SHIM_STRATEGY override (BO-4300b-4) adds no
#   lines there. (ADR-018)
# ====================================================================
