"""
epic_ac_phases.py — The --ac-mode phases that can terminate the process.

MODULE: epic_ac_phases
GOAL: Hold the four phases unique to --ac (subtree) mode — collect the leaves,
      apply the readiness gate, order them, then generate and assemble — each
      of which maps its own failure onto a CLI exit code.
BUSINESS CONTEXT: These are the steps build_epic_from_ids() deliberately does
      NOT perform: it takes its id list as authoritative and lets its
      exceptions propagate to the caller, whereas run() is the interactive
      route /build-ac drives and must fail with a readable message and the
      right exit code. Separating them keeps that asymmetry explicit instead of
      buried in branches. Extracted from goal_to_epic.py so every file can meet
      the 400-line check_file_size limit.
ARCHITECTURE: Each function is a run() phase lifted out whole, including its
      ``sys.exit`` calls — these are process-terminating by design, which is why
      they are not shared with epic_phases (whose helpers are side-effect
      symmetrical across both entrypoints). Imports epic_assembly,
      epic_dependencies, epic_errors, epic_readiness, epic_readiness_gate and
      epic_tickets. Deployed flat beside goal_to_epic.py (see
      AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-1 / -1-i: traversal returns only leaf ACs; L1-scoped traversal
                        excludes sibling branches.
    ACD-1200a-3-i:      zero-leaf condition exits non-zero with no files written.
    ACD-1200b-1-i:      all-approved fast path bypasses the gate entirely.
    ACD-1200c-1-i:      cycle detection exits non-zero before any write.
    ACD-1200c-2:        tickets are generated in topological order, so the
                        numeric prefixes record build order.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from epic_assembly import assemble_epic_folder
from epic_dependencies import resolve_leaf_dependencies, topological_sort
from epic_errors import CyclicDependencyError, ZeroLeafError
from epic_readiness import classify_readiness, print_fast_path_message
from epic_readiness_gate import _gate_select_approved_ids
from epic_tickets import generate_tickets_for_leaves

# This module always lives in ``ac_store/`` under both layouts (see
# epic_tickets.py for the full explanation), so its siblings — including
# scan_ac_store.py — are unconditionally alongside it.
_sibling_dir = Path(__file__).resolve().parent


def _collect_leaf_ids(ac_id: str, ac_store_root: Path) -> list[str]:
    """Walk the AC subtree beneath *ac_id* and return its leaf AC ids.

    traverse_ac_tree is imported inside the function rather than at module
    scope, deliberately: the name is then looked up at call time, so a test
    that patches it still sees its patch, and the sys.path-push-then-import
    shape is the one build_referential_integrity's closure guard resolves.

    Args:
        ac_id: The goal or L1 AC id to start traversal from.
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        list[str]: The leaf AC ids beneath *ac_id*, in traversal order.

    Raises:
        SystemExit: Code 1 when the subtree contains no leaves (ACD-1200a-3-i).
    """
    if str(_sibling_dir) not in sys.path:
        sys.path.insert(0, str(_sibling_dir))

    from scan_ac_store import traverse_ac_tree  # noqa: PLC0415

    leaf_ids = traverse_ac_tree(ac_id, ac_store_root)

    if not leaf_ids:
        print(
            f"No leaf-level ACs found beneath {ac_id}. "
            "Decompose the L1s into L2/L3 ACs first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return leaf_ids


def _apply_readiness_gate(
    leaf_ids: list[str],
    ac_store_root: Path,
    yes: bool,
    approved_only: bool,
) -> list[str]:
    """Filter *leaf_ids* down to the set the readiness gate approves.

    Classifies the leaves BEFORE any ticket is generated. When every leaf is
    already approved the gate is bypassed entirely and only a confirmation is
    printed (ACD-1200b-1-i).

    Args:
        leaf_ids: The leaf AC ids collected from the subtree.
        ac_store_root: Root directory of the AC YAML store.
        yes: True when the ``--yes`` CLI flag was passed.
        approved_only: True when the ``--approved-only`` CLI flag was passed.

    Returns:
        list[str]: The leaf AC ids to build the epic from.

    Raises:
        SystemExit: Code 0 when the user cancelled or nothing remains approved;
            code 1 via :func:`_gate_select_approved_ids` on a no-TTY run with
            neither flag.
    """
    readiness = classify_readiness(leaf_ids, ac_store_root)

    if not readiness["unapproved"]:
        # All-approved fast-path: no prompt, print confirmation, proceed.
        print_fast_path_message(len(leaf_ids))
        return leaf_ids

    # Some ACs need approval — route to _gate_select_approved_ids for the
    # TTY-aware decision.
    approved_ids = _gate_select_approved_ids(
        readiness, ac_store_root, yes=yes, approved_only=approved_only
    )
    if approved_ids is None:
        # User cancelled (interactive only) — exit cleanly with no writes.
        print("Epic generation cancelled. No files written.")
        sys.exit(0)
    if not approved_ids:
        print("No approved ACs remain after gate decision. Nothing to generate.")
        sys.exit(0)
    return approved_ids


def _order_leaves_or_exit(
    leaf_ids: list[str],
    ac_store_root: Path,
) -> tuple[dict[str, list[str]], list[str]]:
    """Resolve inter-leaf dependencies and compute build order, exiting on a cycle.

    Runs BEFORE any ticket file is written, so a cycle costs nothing
    (ACD-1200c-1-i). build_epic_from_ids() deliberately does NOT use this
    helper — it lets CyclicDependencyError propagate to its caller.

    Args:
        leaf_ids: The leaf AC ids to order.
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        tuple[dict[str, list[str]], list[str]]: The dependency graph and the
        topologically ordered ids.

    Raises:
        SystemExit: Code 1 when the dependency graph contains a cycle.
    """
    dep_graph = resolve_leaf_dependencies(leaf_ids, ac_store_root)
    try:
        topo_order = topological_sort(dep_graph)
    except CyclicDependencyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    return dep_graph, topo_order


def _generate_and_assemble_or_exit(
    topo_order: list[str],
    ac_store_root: Path,
    inbox_dir: Path,
    epic_name: str,
) -> tuple[list[str], Path]:
    """Generate one ticket per ordered leaf and assemble them into the epic folder.

    Tickets are written to the inbox root first; those loose copies are removed
    later by the single-location-write phase (ACD-1200a-9), leaving only the
    epic-folder copies. Generation follows topological order so the numeric
    prefixes assembly assigns record the build sequence (ACD-1200c-2).

    Args:
        topo_order: AC ids in topological build order.
        ac_store_root: Root directory of the AC YAML store.
        inbox_dir: Absolute path to the tickets inbox root.
        epic_name: PascalCase EPIC name without the ``EPIC-`` prefix.

    Returns:
        tuple[list[str], Path]: The loose ticket paths and the epic folder.

    Raises:
        SystemExit: Code 1 when ticket generation or assembly fails.
    """
    try:
        ticket_paths = generate_tickets_for_leaves(topo_order, ac_store_root, inbox_dir)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: ticket generation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        epic_folder = assemble_epic_folder(ticket_paths, epic_name, inbox_dir)
    except (ZeroLeafError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    return ticket_paths, epic_folder


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 12:00 [goal-to-epic-decompose]: Created during the decomposition of
  scripts/goal_to_epic.py. All four functions are consecutive blocks lifted out
  of run() (273 lines, cyclomatic 18) unchanged — same printed strings, same
  sys.exit codes, same exception types caught in the same order. They are kept
  apart from epic_phases because these terminate the process and are therefore
  --ac-mode only: build_epic_from_ids() lets the equivalent failures propagate
  to its caller instead.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
