"""
MODULE: scripts/build_orchestration/_fl_cli.py
GOAL: Argument-parser construction for the fast-lane CLI.
BUSINESS CONTEXT: A CLI entry point wraps each fast-lane gate/lifecycle
    function for subprocess-based pipeline invocation (fast-lane-ship.js).
    Extracted verbatim from fast_lane.py (NO behaviour change) as part of
    the 2026-09-14 file-size split — see fast_lane.py's own DECISION
    HISTORY for the full record.
ARCHITECTURE: This module holds ONLY parser construction — no dispatch
    logic and no dependency on fast_lane.py itself, so it can be imported
    by fast_lane.py in one direction with no import cycle.
    ``main()`` (the dispatcher that calls ``_build_cli_parser()`` and then
    routes to the individual gate functions) remains defined in
    fast_lane.py rather than here: it calls ``resolve_connected_build_set``
    and ``verify_red_baseline``, both of which must themselves stay
    physically defined in fast_lane.py (see that module's ARCHITECTURE
    note), and moving ``main()`` here while those two stay there would
    require this module to import back from fast_lane.py — an import
    cycle this split avoids entirely by keeping the dispatcher next to the
    functions it dispatches to.
"""

from __future__ import annotations

import argparse


def _build_cli_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the fast_lane CLI.

    Returns:
        Configured ArgumentParser with select_batch, select_connected,
        verify_red_baseline, verify_green_and_coverage, claim, release,
        and mark_done subcommands.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Fast-lane build pipeline gates (BO-2400a). "
            "Select a ready AC batch, verify the red baseline before coding, "
            "or verify green coverage before staging."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # --- select_batch ---
    sb = subparsers.add_parser(
        "select_batch",
        help="Select up to --limit ready leaf ACs and print their ids as a JSON list.",
    )
    sb.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")
    sb.add_argument("--limit", required=True, type=int, metavar="N", help="Cohesion cap.")

    # --- select_connected ---
    sc = subparsers.add_parser(
        "select_connected",
        help=(
            "Resolve the connected build set for one AC (subtree + unmet deps, "
            "dependency-ordered, readiness-agnostic) and print the ids as a JSON list."
        ),
    )
    sc.add_argument("--ac", required=True, metavar="ID", help="Target AC id to resolve.")
    sc.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")
    sc.add_argument(
        "--exclude-structural-parent",
        action="store_true",
        default=False,
        help=(
            "When set, skip any depends_on entry that equals the structural parent "
            "of the node being expanded (i.e. derive_parent_id(node)). "
            "Genuine (non-structural-parent) dependencies are still walked. "
            "Defaults to False — omitting the flag preserves existing behaviour."
        ),
    )

    # --- verify_red_baseline ---
    vrb = subparsers.add_parser(
        "verify_red_baseline",
        help=(
            "Verify that at least one newly-added (git-derived) test covering "
            "ac-ids is currently red."
        ),
    )
    vrb.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids whose newly-added covering tests establish the baseline.",
    )
    vrb.add_argument("--test-root", required=True, metavar="DIR", help="Root of test tree.")
    vrb.add_argument(
        "--base-ref",
        required=False,
        default=None,
        metavar="REF",
        help=(
            "Git ref to diff newly-added tests against. Defaults to "
            "'git merge-base HEAD origin/main' resolved from --test-root."
        ),
    )

    # --- verify_green_and_coverage ---
    vgc = subparsers.add_parser(
        "verify_green_and_coverage",
        help="Verify all batch tests pass and every AC id has a covering test.",
    )
    vgc.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to verify.",
    )
    vgc.add_argument("--test-root", required=True, metavar="DIR", help="Root of test tree.")
    vgc.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")

    # --- check_producibility ---
    cp2 = subparsers.add_parser(
        "check_producibility",
        help=(
            "Compute the producibility verdict for a resolved connected "
            "build set (BO-2400f-12): whether this run's roster can produce "
            "every member. Prints JSON {producible, unproducible}. Exits 0 "
            "when producible, 1 otherwise (fail-closed)."
        ),
    )
    cp2.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to check.",
    )
    cp2.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")

    # --- claim ---
    claim_p = subparsers.add_parser(
        "claim",
        help=(
            "Claim the connected build set: partition ac-ids by work_status, "
            "flip todo ACs to in_progress, refuse if the whole set is already "
            "in_progress. Prints JSON {claimed, excluded_claimed, target_refused}."
        ),
    )
    claim_p.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to claim.",
    )
    claim_p.add_argument(
        "--ac-root",
        required=True,
        metavar="DIR",
        help="Root of AC YAML store.",
    )

    # --- release ---
    release_p = subparsers.add_parser(
        "release",
        help=(
            "Release claimed ACs back to work_status: todo. "
            "Idempotent — a todo AC is a no-op. "
            "Prints JSON {released}."
        ),
    )
    release_p.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to release.",
    )
    release_p.add_argument(
        "--ac-root",
        required=True,
        metavar="DIR",
        help="Root of AC YAML store.",
    )

    # --- mark_done ---
    md_p = subparsers.add_parser(
        "mark_done",
        help=(
            "Coverage-gated mark-done: flip each in_progress AC to done only "
            "when it has a passing covers-tagged test, then run the stale-todo "
            "guard. Prints JSON {marked_done, all_done, stale}. "
            "Exits 0 when all_done, 1 otherwise."
        ),
    )
    md_p.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to mark done.",
    )
    md_p.add_argument(
        "--ac-root",
        required=True,
        metavar="DIR",
        help="Root of AC YAML store.",
    )
    md_p.add_argument(
        "--test-root",
        required=True,
        metavar="DIR",
        help="Root of test tree to scan for covers-tagged tests.",
    )

    # --- changelog_requirement ---
    cr_p = subparsers.add_parser(
        "changelog_requirement",
        help=(
            "Decide whether the run's delivered change owes a changelog entry, "
            "reusing check_changelog_presence's own exempt-path rule. Prints "
            "JSON {required, releasable_paths}."
        ),
    )
    cr_p.add_argument(
        "--files",
        required=True,
        metavar="PATHS",
        help="Comma-separated repo-relative file paths the run's change touches.",
    )

    # --- changelog_payload ---
    cp_p = subparsers.add_parser(
        "changelog_payload",
        help=(
            "Assemble the scripts/changelog/emit_entry.py payload for one "
            "fast-lane run. Prints the JSON payload on stdout."
        ),
    )
    cp_p.add_argument("--target-ac", required=True, metavar="ID", help="Operator-named target AC id.")
    cp_p.add_argument(
        "--built-ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids the run built (dependency order).",
    )
    cp_p.add_argument(
        "--files-modified",
        required=False,
        default="",
        metavar="PATHS",
        help="Comma-separated files the coder reported modifying.",
    )
    cp_p.add_argument("--branch", required=True, metavar="BRANCH", help="Worktree branch.")
    cp_p.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")

    return parser


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
