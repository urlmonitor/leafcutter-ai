"""
epic_pipeline.py — The two epic-building entrypoints.

MODULE: epic_pipeline
GOAL: Orchestrate a whole epic build, in the two shapes the CLI offers:
      run() walks the AC subtree beneath a goal AC (--ac mode), and
      build_epic_from_ids() takes an explicit leaf id list as authoritative
      (--ids mode).
BUSINESS CONTEXT: Implements ACD-1200a end to end. The --ids entrypoint exists
      because the --ac path re-walks the covered_by subtree and drops any leaf
      that lives outside the first AC's tree but was included by
      fast_lane.resolve_connected_build_set() — the exact defect BO-2600a-5
      closes. Extracted from goal_to_epic.py so that file can meet the 400-line
      check_file_size limit.
ARCHITECTURE: Both functions read as a linear sequence of named phases. The
      phases they share live in epic_phases; the --ac-mode-only phases that can
      terminate the process live in epic_ac_phases. What remains here is the
      sequencing plus the three things genuinely unique to run(): the dry-run
      branch, target_epic stamping, and printing to stdout. Deployed flat
      beside goal_to_epic.py (see AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-3-iii: dry-run and real-run derive the epic name from one shared
                     code path (n_location_rule: 1).
    ACD-1200d-1:     included leaf ACs are stamped with target_epic AFTER
                     assembly, so a failed assembly leaves no dangling
                     back-reference.
    BO-2600a-5:      the --ids id set is authoritative; no subtree
                     re-derivation, cross-tree ids preserved.
"""

from __future__ import annotations

from pathlib import Path

from epic_ac_phases import (
    _apply_readiness_gate,
    _collect_leaf_ids,
    _generate_and_assemble_or_exit,
    _order_leaves_or_exit,
)
from epic_ac_store import _get_ac_title, stamp_target_epic
from epic_assembly import _build_loose_to_epic_map, _remove_loose_inbox_tickets, assemble_epic_folder
from epic_dependencies import resolve_leaf_dependencies, topological_sort
from epic_naming import _derive_epic_name
from epic_phases import (
    _apply_epic_backrefs,
    _epic_filename_map,
    _wire_epic_depends_on,
    _write_master_plan_safely,
)
from epic_runtime import _derive_worktree_from_inbox, get_logger
from epic_tickets import generate_tickets_for_leaves

# ---------------------------------------------------------------------------
# Orchestration entry point (--ac mode)
# ---------------------------------------------------------------------------


def run(
    ac_id: str,
    ac_store_root: Path,
    inbox_dir: Path,
    dry_run: bool = False,
    worktree_root: Path | None = None,
    yes: bool = False,
    approved_only: bool = False,
) -> Path:
    """Full orchestration: traverse → generate tickets → assemble EPIC folder.

    1. Calls :func:`~scripts.ac_store.scan_ac_store.traverse_ac_tree` on
       *ac_id* to collect leaf AC ids.
    2. Raises :class:`ZeroLeafError` (via :func:`assemble_epic_folder`) when
       no leaves are found — exits non-zero at the CLI layer.
    3. Calls :func:`generate_tickets_for_leaves` once per leaf.
    4. Calls :func:`assemble_epic_folder` to build the numbered EPIC folder.

    Args:
        ac_id: The goal or L1 AC id to start traversal from.
        ac_store_root: Root directory of the AC YAML store.
        inbox_dir: Absolute path to the tickets inbox root.
        dry_run: When True, print the plan and return without writing files.
        worktree_root: Absolute path to the git worktree root, used to
            relativise the absolute loose ticket paths before rewriting
            ``implemented_by``. Required because generate_ticket_from_ac.py
            stamps that field with a worktree-relative path while
            ``_call_generate_ticket_from_ac`` returns the absolute one — so
            without it the comparison inside
            :func:`_replace_implemented_by_entry` always evaluates False and
            the update silently does nothing (ACD-1200a-9 / TKT-016).
        yes: When True, proceed past the readiness gate as if the user chose
            "yes" at the interactive prompt (proceed with only the
            already-approved leaf ACs). No effect when all ACs are already
            approved. Required when stdin has no controlling TTY and some ACs
            are unapproved. (ACD-1200b-4)
        approved_only: When True, filter to only already-approved leaf ACs and
            skip unapproved ones without any interactive prompt. Clears the
            readiness gate in non-interactive (no-TTY) runs. (ACD-1200b-4)

    Returns:
        Absolute path to the created EPIC folder (or a placeholder in dry-run).

    Raises:
        SystemExit: With code 1 on zero-leaf condition, no-TTY missing-flag
            condition, or other errors.
    """
    leaf_ids = _collect_leaf_ids(ac_id, ac_store_root)

    # Derived BEFORE the dry-run branch so both paths use one shared code path
    # for the name (ACD-1200a-3-iii, n_location_rule: 1).
    ac_title = _get_ac_title(ac_id, ac_store_root)
    epic_name = _derive_epic_name(ac_title)

    if dry_run:
        print(f"Dry-run: would create EPIC-{epic_name} with {len(leaf_ids)} ticket(s):")
        for leaf_id in leaf_ids:
            print(f"  {leaf_id}")
        # Return a placeholder path — no files written
        return (inbox_dir / "epics" / f"EPIC-{epic_name}").resolve()

    # --- Readiness gate (ACD-1200b / ACD-1200b-4) ---
    leaf_ids = _apply_readiness_gate(leaf_ids, ac_store_root, yes, approved_only)

    # --- Dependency wiring + topological sort (ACD-1200c) ---
    dep_graph, topo_order = _order_leaves_or_exit(leaf_ids, ac_store_root)

    # --- Ticket generation + assembly (ACD-1200a-2 / ACD-1200a-3) ---
    ticket_paths, epic_folder = _generate_and_assemble_or_exit(
        topo_order, ac_store_root, inbox_dir, epic_name
    )

    print(f"EPIC folder created: {epic_folder}")

    # --- depends_on translation (TKT-017) ---
    _wire_epic_depends_on(
        epic_folder, topo_order, dep_graph, _epic_filename_map(topo_order, ticket_paths)
    )

    # --- target_epic stamping (ACD-1200d-1) ---
    # Use the actual assembled folder name so the stamp matches what
    # /build-feature will resolve. After assembly, so a failed assembly never
    # leaves dangling back-refs.
    stamp_target_epic(topo_order, epic_folder.name, ac_store_root)

    # --- Single-location write + correct implemented_by (ACD-1200a-9) ---
    _apply_epic_backrefs(
        ac_store_root,
        _build_loose_to_epic_map(ticket_paths, epic_folder),
        worktree_root,
        warn_unrelativisable=True,
    )
    _remove_loose_inbox_tickets(ticket_paths, inbox_dir)

    # --- Master_Plan.md generation (ACD-1200a-7) ---
    goal_summary = (
        f"This epic implements AC {ac_id}: {ac_title}. "
        f"It consists of {len(topo_order)} ticket(s) generated from the leaf ACs "
        f"beneath {ac_id}, assembled in topological build order with all "
        f"inter-ticket dependencies derived from the AC depends_on graph."
    )
    master_plan_path = _write_master_plan_safely(
        epic_folder, topo_order, dep_graph, ac_id, goal_summary, epic_name
    )
    if master_plan_path is not None:
        print(f"Master_Plan.md written: {master_plan_path}")

    return epic_folder


# ---------------------------------------------------------------------------
# ID-list entrypoint (BO-2600a-5)
# ---------------------------------------------------------------------------


def build_epic_from_ids(
    ids: list[str],
    *,
    store_root: Path,
    inbox_dir: Path,
) -> Path:
    """Assemble a dependency-ordered EPIC folder from EXACTLY the provided leaf AC ids.

    The id list is the authoritative scope. No single-root subtree walk is done to
    re-derive or expand it (BO-2600a-5 AC-3). This preserves cross-tree
    prerequisites that fast_lane.resolve_connected_build_set() included but that
    a subtree walk would drop — the exact defect this entrypoint closes.

    Two hygiene fixes over run(): (a) repo-relative implemented_by
    back-references, never absolute worktree paths; (b) AC-id to co-located
    ticket-filename depends_on translation at generation time so
    ticket_frontmatter_guard passes without a downstream hook auto-fix.

    Args:
        ids: Explicit ordered list of leaf AC ids to include in the epic. Taken as
             authoritative — no subtree re-derivation is performed. Cross-tree ids
             in the list are preserved.
        store_root: Root directory of the AC YAML store.
        inbox_dir: Absolute path to the tickets inbox root (e.g. ``tickets/00_inbox``).
             Should follow the ``<worktree>/tickets/00_inbox`` convention so the
             worktree root can be derived by path math for repo-relative path
             computation (BO-2600a-5 hygiene fix a).

    Returns:
        Absolute path to the created EPIC folder.

    Raises:
        CyclicDependencyError: When the dependency graph among the provided ids
            contains a cycle. Fires before any files are written.
        ZeroLeafError: When *ids* is empty (propagated from assemble_epic_folder).
        subprocess.CalledProcessError: When ticket generation fails for an id.
        OSError: When file I/O fails during epic folder assembly or implemented_by
            updates.
    """
    # Step 1 — Dependency graph (restricted to the given id set).
    # resolve_leaf_dependencies already drops edges where the target is NOT in
    # *ids*, so no additional restriction is needed.
    dep_graph = resolve_leaf_dependencies(ids, store_root)

    # Step 2 — Topological sort: dependees (no unresolved deps) come first.
    # CyclicDependencyError raised here fires before any file writes, and is
    # deliberately NOT caught — unlike run(), this entrypoint reports failure to
    # its caller rather than to a CLI exit code.
    topo_order = topological_sort(dep_graph)

    # Step 3 — Derive epic name from the first id's AC title (store lookup).
    epic_name = _derive_epic_name(_get_ac_title(ids[0], store_root)) if ids else "FromIdsList"

    # Step 4 — Generate one ticket per id in topological order.
    ticket_paths = generate_tickets_for_leaves(topo_order, store_root, inbox_dir)

    # Step 5 — Assemble the epic folder (copies loose tickets with numeric prefixes).
    epic_folder = assemble_epic_folder(ticket_paths, epic_name, inbox_dir)

    # Step 6 — Translate each ticket's depends_on to co-located epic filenames
    # (BO-2600a-5 AC-4), sourcing the raw AC ids from dep_graph rather than from
    # the ticket's own frontmatter, which ACD-400b-7 hardcodes to [].
    _wire_epic_depends_on(
        epic_folder, topo_order, dep_graph, _epic_filename_map(topo_order, ticket_paths)
    )

    # Step 7 — Repoint implemented_by at the epic-folder ticket paths, relative
    # to the worktree root so the values start with "tickets/" (never "/…").
    _apply_epic_backrefs(
        store_root,
        _build_loose_to_epic_map(ticket_paths, epic_folder),
        _derive_worktree_from_inbox(inbox_dir),
        warn_unrelativisable=False,
    )

    # Step 8 — Remove loose inbox-root ticket copies (single-location write policy).
    _remove_loose_inbox_tickets(ticket_paths, inbox_dir)

    # Step 9 — Generate Master_Plan.md (non-fatal on OSError; epic folder is done).
    goal_summary = (
        f"This epic assembles {len(topo_order)} ticket(s) from an explicit "
        f"connected-set id list: {', '.join(ids)}. Generated by build_epic_from_ids "
        f"— the id set is taken as authoritative (no subtree re-derivation). "
        f"Cross-tree ids in the list are preserved exactly as supplied."
    )
    master_plan_path = _write_master_plan_safely(
        epic_folder, topo_order, dep_graph, ids[0] if ids else "unknown",
        goal_summary, epic_name,
    )
    if master_plan_path is not None:
        get_logger().info("Master_Plan.md written: %s", master_plan_path)

    return epic_folder


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-12 [BO-2600a-5]: Explicit id-list entrypoint and two hygiene fixes.
  Implements BO-2600a-5: adds build_epic_from_ids(ids, *, store_root, inbox_dir)
  and a matching --ids CLI mode so fast_lane.resolve_connected_build_set() can
  pass its full connected-set result (including cross-tree prerequisites) directly
  to epic assembly without re-walking a single AC's subtree via traverse_ac_tree().
  Root defect closed: the existing --ac path re-walks the covered_by subtree and
  drops any leaf that lives outside the first AC's tree but was included by the
  connected-set resolution. The new path takes the id list as authoritative.
  Internals reused: resolve_leaf_dependencies (restricted to the given id set via
  the existing out-of-set edge filter), topological_sort, generate_tickets_for_leaves,
  assemble_epic_folder, generate_master_plan. --ac mode is preserved unchanged
  (backward compatible). Two hygiene fixes applied in the same pass:
  (a) _translate_ticket_depends_on() translates AC ids in ticket depends_on fields
  to co-located epic-folder filenames at generation time (so ticket_frontmatter_guard
  passes without a downstream hook auto-fix); (b) implemented_by back-references
  written into source AC YAMLs are repo-relative (start with "tickets/", never
  absolute worktree paths). CLI: _build_parser() now uses a mutually exclusive
  group (required=True) containing --ac and --ids; main() routes on args.ids.
  Covered by 6 unit tests in unit_tests/build_orchestration/test_bo_2600a_5.py;
  how-to documentation added in docs/how-to/goal-to-epic.md §5.
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py. run() was 273 lines at cyclomatic 18 (over the
  threshold of 15) and build_epic_from_ids() 150 lines at 10; between them they
  carried four near-identical copies of the post-assembly phases. Both are now
  linear sequences of named phases (epic_ac_phases for the --ac-only,
  process-terminating ones; epic_phases for the shared ones) at cyclomatic 4
  and 2. Every printed string, sys.exit code and signature is unchanged — the
  signatures load-bearing because
  unit_tests/build_orchestration/test_bo_2600a_5.py asserts on
  inspect.signature(run), and build_epic_from_ids' keyword-only store_root /
  inbox_dir is fast_lane's documented call surface.

  One hazard became structural rather than documented. The pre-split run()
  carried a 10-line comment warning that its depends_on translation loop must
  not be written `for ac_id in topo_order`, because a statement-level loop
  variable leaks past the loop and would overwrite run()'s own `ac_id`
  parameter — leaving the Master_Plan block below it attributing the whole epic
  to whichever leaf sorted last. That loop now lives in
  epic_phases._wire_epic_depends_on, a different function, so the shadowing is
  impossible rather than merely avoided by naming discipline.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
