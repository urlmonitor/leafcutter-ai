"""
MODULE: scripts/build_orchestration/_fl_common.py
GOAL: Shared path wiring and re-exported dependency names for the fast-lane
    module family (fast_lane.py and its _fl_* sibling modules).
BUSINESS CONTEXT: BO-2400a/f series — fast_lane.py grew to 1388 content lines
    (the check-file-size hook's own counter) against the repository's 400-line
    limit, so it was split into this leaf module plus a set of sibling
    modules under scripts/build_orchestration/, each importing shared names
    from here rather than repeating the sys.path wiring and done_proof /
    scan_ac_store / ac_parent_id imports in every file. See fast_lane.py's
    own DECISION HISTORY for the full record of the split and which
    functions moved where.
ARCHITECTURE: Every _fl_* sibling module (and fast_lane.py itself) imports
    from this module FIRST, so its sys.path.insert side effect runs before
    any sibling module's own done_proof / scan_ac_store / ac_parent_id /
    check_changelog_presence import — exactly preserving the import order
    the single-file fast_lane.py guaranteed by construction (top-to-bottom
    execution of one module). _LOG is pinned to the literal logger name
    "fast_lane" (rather than logging.getLogger(__name__)) so every sibling
    module logs through the IDENTICAL logger channel the pre-split single
    file used, regardless of which sibling module a given log call now
    lives in.

    scripts/build_orchestration/ is deployed WHOLE by
    build_build_orchestration_scripts() in scripts/build_phases.py (a glob
    of every *.py file in this directory, not a hardcoded list), so this
    module and its siblings deploy automatically to every consumer install
    with no build_phases.py edit required. Contrast with
    scripts/commit_guardian/, which uses a hardcoded deploy_map.

# DECISION HISTORY
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted from
#   fast_lane.py as part of a pure structural split (NO behaviour change):
#   fast_lane.py measured 1388 content lines against the 400-line
#   check-file-size limit. The split created this leaf module
#   (_fl_common.py: path wiring + shared imported names), _fl_lifecycle.py
#   (AC work_status lifecycle helpers), _fl_changelog.py (changelog
#   requirement/payload helpers), _fl_producibility.py (the producibility
#   guard), _fl_selection.py (select_batch / _topo_order_build_set),
#   _fl_red_baseline_support.py (verify_red_baseline's private helpers),
#   _fl_coverage.py (verify_green_and_coverage), and _fl_cli.py
#   (_build_cli_parser). fast_lane.py itself retains only
#   resolve_connected_build_set, verify_red_baseline, and main(): both
#   retained functions are the target of mock.patch("fast_lane.<name>", ...)
#   calls in the test suite (patching _load_ac, traverse_ac_tree, and
#   _run_pytest_and_parse respectively) that rely on those functions'
#   bare-name global lookups resolving through fast_lane's OWN module
#   dict — moving either function's definition to a different module would
#   silently break those patches (the mocked name would never be consulted)
#   without failing loudly. Every name previously importable from
#   fast_lane remains importable from fast_lane via re-export.
#   (#TICKETLESS reason=fast-lane-file-size-split)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path wiring — make ac_store helpers importable without package install
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"
_RELEASE_DIR = _SCRIPTS_DIR / "release"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))
if str(_RELEASE_DIR) not in sys.path:
    sys.path.insert(0, str(_RELEASE_DIR))

from done_proof import (  # noqa: E402
    _TEST_DEF_RE,
    _find_nodeid_for_test,
    _run_pytest_and_parse,
    _scan_test_root_for_covers_tags,
    verify_done_eligible,
)
from scan_ac_store import (  # noqa: E402
    _build_id_index,
    _classify_ac,
    _drain_cycles,
    _is_active,
    _is_approved,
    _is_leaf,
    _load_ac,
    _matches_work_status,
    _sort_ready,
    _walk_ac_yamls,
    traverse_ac_tree,
)
from ac_parent_id import derive_parent_id  # noqa: E402

_LOG = logging.getLogger("fast_lane")

# Every name below is imported here solely to be re-exported to the _fl_*
# sibling modules and to fast_lane.py itself (see the module docstring) —
# none of them is referenced within this file's own code, so each is named
# in __all__ to tell ruff's F401 check that the import is intentional
# rather than dead.
__all__ = [
    "_LOG",
    "_TEST_DEF_RE",
    "_build_id_index",
    "_classify_ac",
    "_drain_cycles",
    "_find_nodeid_for_test",
    "_is_active",
    "_is_approved",
    "_is_leaf",
    "_load_ac",
    "_matches_work_status",
    "_run_pytest_and_parse",
    "_scan_test_root_for_covers_tags",
    "_sort_ready",
    "_walk_ac_yamls",
    "derive_parent_id",
    "traverse_ac_tree",
    "verify_done_eligible",
]
