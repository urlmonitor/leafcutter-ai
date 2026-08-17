"""
MODULE: build_ac_mode_detection
GOAL: Detect the /build-ac routing mode (leaf, goal, or L1-no-children) for a
    given AC id so the build-ac agent can branch to the correct pipeline path.
BUSINESS CONTEXT: Implements the three-way routing branch described in
    ticket 05 of EPIC-GoalToEpic:

      1. Leaf AC   (level L2/L3, covered_by empty/None) -> single-ticket path
      2. Goal AC   (level L0 or L1, covered_by non-empty) -> epic-generation mode
      3. L1-no-children (level L0/L1, covered_by empty/None) -> error + decompose suggestion

    This module is a pure detection utility: it reads the level and
    covered_by fields and returns a routing dict. It does NOT invoke any
    pipeline steps — those are the caller's responsibility.
ARCHITECTURE: Pure stdlib, no I/O. Deployed to
    ``<output_root>/scripts/build_ac_mode_detection.py`` by
    ``build_template_standalone_scripts`` (scripts/build_phases.py, sourced
    from this file), and shimmed at ``<target>/scripts/build_ac_mode_detection.py``
    by ``install_shims`` (scripts/build_helpers.py) per AC BP-900a-2. This is
    a header-normalized, otherwise verbatim copy of the package's
    ``scripts/build_ac_mode_detection.py``, which is ALSO deployed separately
    to ``<output_root>/scripts/ac_store/build_ac_mode_detection.py`` by
    ``build_ac_store`` — the two deploy targets intentionally coexist so both
    the documented ``{{config.output_root}}/scripts/ac_store/`` invocation
    path (templates/agents/build-ac.md) and the top-level
    ``<target>/scripts/build_ac_mode_detection.py`` shim path (BP-900a-2)
    resolve to a working copy.

Used by:
  - templates/agents/build-ac.md (Step 2 mode-detection branch)
  - unit_tests/agents/test_build_ac_mode_detection.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Public constants — routing mode identifiers
# ---------------------------------------------------------------------------

AC_MODE_LEAF = "leaf"
AC_MODE_GOAL = "goal"
AC_MODE_L1_NO_CHILDREN = "l1_no_children"

# Leaf path has no user-facing mode message (backward-compatible silent routing)
LEAF_MESSAGE_NONE = None

# Message templates — exact strings required by ACD-1200e-2 and ACD-1200e-2-i
GOAL_MESSAGE_TEMPLATE = (
    "{id} is a goal — generating epic from all leaf ACs beneath it."
)
L1_NO_CHILDREN_MESSAGE_TEMPLATE = (
    "{id} is an L1 with no leaf ACs beneath it. "
    "Decompose into L2/L3 first, or use /ba to generate behavioral specifications."
)

# Levels that are treated as composite (goal-level) ACs when they have children
_COMPOSITE_LEVELS = {"L0", "L1"}

# Levels that are always treated as leaf ACs regardless of covered_by
# (L2, L3, and anything deeper is a leaf by definition)
_LEAF_LEVELS = {"L2", "L3"}


def detect_ac_mode(ac_id: str, level: str, covered_by: list | None) -> dict:
    """
    Detect the routing mode for a /build-ac invocation.

    Parameters
    ----------
    ac_id : str
        The AC identifier (e.g. "ACD-050", "ACS-101a-1").
    level : str
        The AC level string from the YAML store ("L0", "L1", "L2", "L3", …).
    covered_by : list | None
        The covered_by list from the AC YAML. Empty list or None means no children.

    Returns
    -------
    dict with the following keys:
        mode : str
            One of AC_MODE_LEAF, AC_MODE_GOAL, AC_MODE_L1_NO_CHILDREN.
        message : str | None
            User-facing message to print before entering the mode.
            None for the leaf path (no mode switch message shown).
        invoke_goal_to_epic : bool
            True only for AC_MODE_GOAL — tells the caller to invoke goal_to_epic.py.
        use_single_ticket_path : bool
            True only for AC_MODE_LEAF — tells the caller to use the existing
            single-ticket flow (generate_ticket_from_ac.py).

    Detection rules (in evaluation order)
    --------------------------------------
    1. If level is in _LEAF_LEVELS (L2, L3, …): ALWAYS leaf, regardless of covered_by.
    2. If level is in _COMPOSITE_LEVELS (L0, L1):
       a. covered_by non-empty → goal (epic-generation mode).
       b. covered_by empty or None → L1-no-children (error path).
    3. Any other level: treat as leaf (backward-compatible default).
    """
    has_children = bool(covered_by)

    # Rule 1: leaf levels are always leaves
    if level in _LEAF_LEVELS:
        return {
            "mode": AC_MODE_LEAF,
            "message": LEAF_MESSAGE_NONE,
            "invoke_goal_to_epic": False,
            "use_single_ticket_path": True,
        }

    # Rule 2: composite levels branch on whether children exist
    if level in _COMPOSITE_LEVELS:
        if has_children:
            # Goal with children → epic-generation mode
            return {
                "mode": AC_MODE_GOAL,
                "message": GOAL_MESSAGE_TEMPLATE.format(id=ac_id),
                "invoke_goal_to_epic": True,
                "use_single_ticket_path": False,
            }
        else:
            # L0 or L1 with no children → error path
            return {
                "mode": AC_MODE_L1_NO_CHILDREN,
                "message": L1_NO_CHILDREN_MESSAGE_TEMPLATE.format(id=ac_id),
                "invoke_goal_to_epic": False,
                "use_single_ticket_path": False,
            }

    # Rule 3: unknown / future level — fall back to leaf (backward compatible)
    return {
        "mode": AC_MODE_LEAF,
        "message": LEAF_MESSAGE_NONE,
        "invoke_goal_to_epic": False,
        "use_single_ticket_path": True,
    }


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-17 [python-coder/EPIC-DeploymentCompleteness/BP-900a-2]: Added
#   this file as the tracked template source for the top-level
#   <output_root>/scripts/build_ac_mode_detection.py deploy target and its
#   <target>/scripts/build_ac_mode_detection.py shim. Header-normalized copy
#   of scripts/build_ac_mode_detection.py (detect_ac_mode logic unchanged) —
#   small enough (118 lines) to duplicate safely without breaching the
#   400-line file-size limit, unlike the sibling goal_to_epic.py which uses a
#   thin-delegator pattern instead. (#BP-900a-2)
# ====================================================================
