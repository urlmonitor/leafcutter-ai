"""
epic_phases.py — Post-assembly phases shared by both epic-building entrypoints.

MODULE: epic_phases
GOAL: Hold the steps that run() (--ac mode) and build_epic_from_ids() (--ids
      mode) perform identically once the epic folder exists: mapping AC ids to
      their prefixed epic filenames, translating each ticket's depends_on,
      repointing implemented_by back-references at repo-relative paths, and
      writing Master_Plan.md without letting an OSError kill an
      already-assembled epic.
BUSINESS CONTEXT: These phases were duplicated between the two entrypoints,
      and the duplication had already caused a real defect: BO-2600a-5 added
      the depends_on translation to build_epic_from_ids() and did not
      back-port it to run(), so the DEFAULT route that /build-ac drives emitted
      epics whose tickets depended on files that did not exist until TKT-017
      fixed it. TKT-016 was the implemented_by half of the same back-port gap.
      Holding one copy here is what stops that class of drift recurring.
ARCHITECTURE: Every function is a pure phase over already-computed inputs — no
      traversal, no readiness gate, no CLI concerns. The two genuine behavioural
      differences between the callers are explicit parameters rather than
      forked copies: *warn_unrelativisable* (run() warns about a back-reference
      it cannot relativise; build_epic_from_ids() stays silent) and the return
      value of :func:`_write_master_plan_safely` (run() prints the path,
      build_epic_from_ids() logs it at INFO). Imports epic_assembly,
      epic_master_plan, epic_runtime and epic_tickets. Deployed flat beside
      goal_to_epic.py (see AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-7: Master_Plan.md is written at the epic folder root, and an
                 OSError there is non-fatal — the folder is already assembled.
    ACD-1200a-9: implemented_by back-references name the epic-folder path.
    TKT-016:     both the lookup key AND the recorded value are relativised, so
                 no absolute developer-home path is written into the store.
    TKT-017 /
    BO-2600a-5:  depends_on entries are translated to the co-located
                 epic-folder filenames assembly actually produced.
"""

from __future__ import annotations

from pathlib import Path

from epic_assembly import _replace_implemented_by_entry
from epic_master_plan import generate_master_plan
from epic_runtime import get_logger
from epic_tickets import _translate_ticket_depends_on

# ---------------------------------------------------------------------------
# depends_on translation (TKT-017 / BO-2600a-5)
# ---------------------------------------------------------------------------


def _epic_filename_map(
    topo_order: list[str],
    ticket_paths: list[str],
) -> dict[str, str]:
    """Map each AC id to the prefixed filename assembly gave its ticket.

    Prefix assignment mirrors :func:`assemble_epic_folder` exactly:
    ``topo_order[i]`` becomes ``f"{i+1:02d}_<basename>"``. *topo_order* and
    *ticket_paths* are positionally paired — :func:`generate_tickets_for_leaves`
    emits one path per input id, in order — so ``strict=True`` turns any future
    drift between the two into a loud failure rather than a silently truncated
    map.

    Args:
        topo_order: AC ids in topological build order.
        ticket_paths: Loose ticket paths, in the same order as *topo_order*.

    Returns:
        dict[str, str]: AC id → prefixed epic-folder filename
        (e.g. ``"01_TICKET-BO-5C1.md"``).
    """
    return {
        ac_id: f"{i:02d}_{Path(ticket_path).name}"
        for i, (ac_id, ticket_path) in enumerate(
            zip(topo_order, ticket_paths, strict=True), start=1
        )
    }


def _wire_epic_depends_on(
    epic_folder: Path,
    topo_order: list[str],
    dep_graph: dict[str, list[str]],
    ac_to_epic_filename: dict[str, str],
) -> None:
    """Rewrite every epic ticket's depends_on to name its sibling ticket files.

    Assembly renames every ticket with an ``NN_`` prefix recording build order.
    Sibling references must be rewritten to the names assembly actually
    produced, or check-doc-frontmatter refuses the commit and the epic cannot
    land at all.

    The raw dependency list comes from *dep_graph* (built from the AC store
    before generation), never from the ticket's own frontmatter:
    generate_ticket_from_ac.py hardcodes ``depends_on: []`` on every standalone
    ticket it writes (ACD-400b-7), so there is nothing to read back.

    Args:
        epic_folder: Absolute path to the assembled EPIC folder.
        topo_order: AC ids in topological build order.
        dep_graph: Leaf-to-leaf dependency map from resolve_leaf_dependencies.
        ac_to_epic_filename: Output of :func:`_epic_filename_map`.
    """
    for leaf_ac_id in topo_order:
        ticket_file = epic_folder / ac_to_epic_filename[leaf_ac_id]
        _translate_ticket_depends_on(
            ticket_file, dep_graph.get(leaf_ac_id, []), ac_to_epic_filename
        )


# ---------------------------------------------------------------------------
# implemented_by back-references (ACD-1200a-9 / TKT-016)
# ---------------------------------------------------------------------------


def _relativise_backref_pair(
    loose_path: str,
    epic_path: str,
    worktree_root: Path | None,
    warn_unrelativisable: bool,
) -> tuple[str, str]:
    """Convert a (loose, epic) absolute path pair to repo-relative form.

    Both halves must be relativised, not just the lookup key. generate_ticket_from_ac.py
    stamps ``implemented_by`` using a path relative to the worktree root, while
    ``_call_generate_ticket_from_ac`` returns the absolute path from the
    ``Written: <abs_path>`` stdout line — so relativising only *loose_path*
    makes the lookup match and then writes an ABSOLUTE epic path into the
    store, a back-reference that resolves solely on the machine that produced
    it and that carries a developer's home directory into a shared record
    (TKT-016).

    Args:
        loose_path: Absolute path of the loose inbox ticket (the lookup key).
        epic_path: Absolute path of the epic-folder ticket (the recorded value).
        worktree_root: The worktree root to relativise against, or None when it
            could not be derived.
        warn_unrelativisable: When True, emit a WARNING for a path that cannot
            be made relative and for an absent *worktree_root*. run() warns;
            build_epic_from_ids() does not.

    Returns:
        tuple[str, str]: The (lookup key, recorded value) pair, each relative
        to *worktree_root* where possible and otherwise unchanged.
    """
    if worktree_root is None:
        if warn_unrelativisable:
            # TKT-016 second clause: an underivable worktree root previously
            # produced absolute paths indistinguishable from correct output.
            # Say so rather than recording one silently.
            get_logger().warning(
                "worktree root could not be derived from the inbox directory — "
                "recording an ABSOLUTE implemented_by back-reference for %s. It "
                "will not resolve on another machine; re-run with an inbox "
                "directory of the form <worktree>/tickets/00_inbox.",
                epic_path,
            )
        return loose_path, epic_path

    old_path = loose_path
    new_path = epic_path
    try:
        old_path = str(Path(loose_path).relative_to(worktree_root))
    except ValueError:
        # loose_path is not under worktree_root — fall back to the original
        # value (covers edge cases like absolute paths outside the tree).
        pass
    try:
        new_path = str(Path(epic_path).relative_to(worktree_root))
    except ValueError:
        if warn_unrelativisable:
            get_logger().warning(
                "epic ticket %s is not under the worktree root %s — recording "
                "an absolute implemented_by back-reference, which will not "
                "resolve on any other machine",
                epic_path,
                worktree_root,
            )
    return old_path, new_path


def _apply_epic_backrefs(
    ac_store_root: Path,
    loose_to_epic_map: dict[str, str],
    worktree_root: Path | None,
    warn_unrelativisable: bool,
) -> None:
    """Repoint every source AC's implemented_by from the loose path to the epic path.

    Args:
        ac_store_root: Root directory of the AC YAML store.
        loose_to_epic_map: Output of :func:`_build_loose_to_epic_map`.
        worktree_root: Worktree root used to relativise both paths, or None.
        warn_unrelativisable: Forwarded to :func:`_relativise_backref_pair`.
    """
    for loose_path, epic_path in loose_to_epic_map.items():
        old_path, new_path = _relativise_backref_pair(
            loose_path, epic_path, worktree_root, warn_unrelativisable
        )
        _replace_implemented_by_entry(ac_store_root, old_path, new_path)


# ---------------------------------------------------------------------------
# Master_Plan.md (ACD-1200a-7)
# ---------------------------------------------------------------------------


def _write_master_plan_safely(
    epic_folder: Path,
    topo_order: list[str],
    dep_graph: dict[str, list[str]],
    goal_ac_id: str,
    goal_summary: str,
    epic_name: str,
) -> Path | None:
    """Write Master_Plan.md, treating an OSError as non-fatal.

    The epic folder is fully assembled by the time this runs, so a failure to
    write the plan must not fail the build — it is logged at WARNING and the
    caller continues. Reporting the success case is left to the caller, which
    is the one behavioural difference between the two entrypoints: run() prints
    the path to stdout, build_epic_from_ids() logs it at INFO.

    Args:
        epic_folder: Absolute path to the assembled EPIC folder.
        topo_order: AC ids in topological build order.
        dep_graph: Leaf-to-leaf dependency map.
        goal_ac_id: The AC id recorded as the plan's source_ac.
        goal_summary: The plan's ``## Goal`` paragraph.
        epic_name: PascalCase EPIC name without the ``EPIC-`` prefix.

    Returns:
        Path | None: The written Master_Plan.md path, or None when the write
        failed.
    """
    try:
        return generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id=goal_ac_id,
            goal_summary=goal_summary,
            epic_name=epic_name,
        )
    except OSError as exc:
        get_logger().warning(
            "Master_Plan.md generation failed (non-fatal): %s", exc
        )
        return None


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 12:00 [goal-to-epic-decompose]: Created during the decomposition of
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  Every function here is a block lifted out of run() and/or
  build_epic_from_ids(), which each ran ~150-275 lines and carried near-identical
  copies of these four phases.

  Where the two copies differed, the difference is now a parameter rather than
  a fork, and each was checked line by line before merging:
  - back-reference relativisation: run() emitted two WARNINGs (unrelativisable
    epic path; underivable worktree root) that build_epic_from_ids() replaced
    with a bare `pass`. Merged as *warn_unrelativisable*; with it False the
    except body is empty, exactly as before.
  - Master_Plan reporting: run() printed "Master_Plan.md written: <path>" to
    stdout, build_epic_from_ids() logged it at INFO. The shared helper returns
    the path (or None) and each caller reports as it did before, so neither
    output changed.
  - filename map: run() used `zip(..., strict=True)`, build_epic_from_ids()
    built the map in two steps via an intermediate ac_to_source_basename dict
    with a non-strict zip. Unified on the strict form. The lists are the same
    length by construction — generate_tickets_for_leaves appends exactly one
    path per input id — so this is not reachable behaviour, only a louder
    failure mode if that ever stops being true.

  The duplication being removed here is not hypothetical: BO-2600a-5 added the
  depends_on translation to build_epic_from_ids() only, and the default --ac
  route shipped epics with dangling depends_on until TKT-017 back-ported it;
  TKT-016 was the implemented_by half of the same gap. One copy is the fix for
  that class of drift.

  Pre-split history lives in goal_to_epic.py's DECISION HISTORY block (the
  2026-06-22 EPIC-GoalToEpicBugfixes/01, 2026-08-12 BO-2600a-5 and 2026-08-13
  tgh-build entries).
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
