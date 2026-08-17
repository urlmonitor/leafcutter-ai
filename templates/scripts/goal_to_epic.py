"""
MODULE: goal_to_epic (standalone-deploy delegator)
GOAL: Make ``goal_to_epic.py`` reachable at the top level of a consumer
    project's deployed scripts tree — ``<output_root>/scripts/goal_to_epic.py``
    — and via a repo-root shim at ``<target>/scripts/goal_to_epic.py``, per
    AC BP-900a-2, WITHOUT duplicating the full ~2700-line implementation.
BUSINESS CONTEXT: The full ``goal_to_epic.py`` implementation is already
    deployed by ``build_ac_store`` (scripts/build_phases.py) to
    ``<output_root>/scripts/ac_store/goal_to_epic.py``, sourced from the
    package's ``scripts/goal_to_epic.py`` — this is the path every existing
    caller (templates/agents/build-ac.md, templates/skills/build-ac/SKILL.md)
    already invokes via ``{{config.output_root}}/scripts/ac_store/goal_to_epic.py``.
    AC BP-900a-2 additionally requires a top-level
    ``<output_root>/scripts/goal_to_epic.py`` deploy target and a
    ``<target>/scripts/goal_to_epic.py`` shim, matching the deploy pattern
    already used for ``setup_ticket_worktree.py``
    (``build_template_standalone_scripts``). Re-implementing or copying the
    full implementation into this second location would violate the
    project's 400-line file-size limit (``check_file_size`` pre-commit hook)
    and create a second copy of the same logic that could silently drift
    from the ``scripts/ac_store/goal_to_epic.py`` original. This file is a
    thin delegator instead: it forwards ``argv`` unchanged to the real
    ``main()`` deployed alongside it.
ARCHITECTURE: Pure stdlib (sys, pathlib) — no I/O beyond the module import.
    At build time, both this file (via
    ``build_template_standalone_scripts``, sourced from
    ``templates/scripts/goal_to_epic.py``) and the real implementation (via
    ``build_ac_store``, sourced from ``scripts/goal_to_epic.py``) are
    deployed as siblings under ``<output_root>/scripts/`` — this file at the
    top level, the real implementation under
    ``<output_root>/scripts/ac_store/goal_to_epic.py``. This module inserts
    the sibling ``ac_store/`` directory onto ``sys.path`` at import time and
    imports ``main`` from the deployed ``goal_to_epic`` module there, then
    forwards ``sys.argv`` unchanged when run as a script. Because
    ``build_ac_store`` (an ``artifact_phases`` entry) always runs before
    ``build_template_standalone_scripts`` (an ``internal_phases`` entry) in
    ``_run_phases`` (scripts/build.py), the sibling module is guaranteed to
    already be on disk by the time this file is deployed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_AC_STORE_DIR = Path(__file__).resolve().parent / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

from goal_to_epic import main  # noqa: E402 — sys.path must be set up first


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-17 [python-coder/EPIC-DeploymentCompleteness/BP-900a-2]: Added
#   this thin-delegator template source for the top-level
#   <output_root>/scripts/goal_to_epic.py deploy target and its
#   <target>/scripts/goal_to_epic.py shim. Deliberately NOT a verbatim copy
#   of scripts/goal_to_epic.py (2726 raw lines / 1690 after docstring
#   stripping) — a full copy would breach the 400-line file-size limit
#   enforced by check_file_size and would duplicate logic that already lives
#   at <output_root>/scripts/ac_store/goal_to_epic.py (deployed by
#   build_ac_store). This delegator imports that sibling module's main() and
#   forwards argv, so both deploy locations always run identical logic.
#   (#BP-900a-2)
# ====================================================================
