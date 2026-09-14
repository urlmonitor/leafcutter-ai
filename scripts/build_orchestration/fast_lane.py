"""
MODULE: scripts/build_orchestration/fast_lane.py
GOAL: Batch selection, test-gate, and AC lifecycle functions for the fast-lane
    build pipeline.
BUSINESS CONTEXT: BO-2400a/f series — the fast-lane build loop selects a cohesive
    batch of ready leaf ACs, verifies that their tests are red before the coder
    runs, verifies that all tests are green and fully covered before commit
    staging, and manages the AC work_status lifecycle: claim (todo->in_progress),
    release (in_progress->todo on failure), and mark-done (in_progress->done on
    success). Three deterministic, idempotent gate functions and five lifecycle
    functions with no LLM calls in the critical path.
ARCHITECTURE: select_batch reuses scan_ac_store filter/sort helpers so readiness
    semantics track the scanner exactly.  verify_red_baseline derives a
    newly-added / pre-existing partition of the batch's covers-tagged tests
    from git (test-function granularity against the worktree's merge-base with
    origin/main, or an explicit ``base_ref``) and passes when at least one
    newly-added test is classified red (BO-2400a-3 amended 2026-08-17; see
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/
    BO-2400a-3*.yaml) — it reuses done_proof's covers-tag scanner,
    ``_TEST_DEF_RE``, and pytest-output parser so the batch-membership and
    outcome-classification semantics never drift from the done-proof gate.
    verify_green_and_coverage reuses done_proof helpers and verify_done_eligible
    to keep coverage semantics in sync with the done-proof gate.  claim_build_set,
    release_claim, filter_already_claimed, mark_done_built_acs, and
    check_no_stale_todo perform status-only YAML mutations (work_status field only)
    via _update_ac_work_status; all file I/O is wrapped per the Error Handling
    Policy (Rule 1).  _update_ac_work_status commits its edit via
    _atomic_write_text (BO-2400e-3), a write-to-temp-in-the-same-directory then
    os.replace so a reader always sees either the whole old or whole new content
    and an interrupted/failed write never truncates the on-disk record; the CLI's
    "claim" subcommand (BO-2400e-3-i) reads claim_build_set's own success/error
    fields and exits non-zero with the error announced on stderr rather than
    silently reporting success when a write could never be made.  A CLI entry
    point (main()) wraps each function for
    subprocess-based pipeline invocation.  compute_changelog_requirement (KI-BO-001)
    imports scripts/release/check_changelog_presence.py as a module and reads its
    EXEMPT_PREFIXES attribute at call time so the fast lane's "does this run owe a
    changelog entry" decision can never drift from the CI gate's own rule;
    build_changelog_payload assembles the scripts/changelog/emit_entry.py payload
    from run state, always with breaking=False (never inferred from AC metadata).
    Both are exposed via the changelog_requirement / changelog_payload CLI
    subcommands for the fast-lane-ship.js Changelog phase.  compute_producibility_verdict
    (BO-2400f-12) is a pure, read-only function that decides, for each id in a
    resolved connected build set, whether this run's roster can produce it —
    positive-declaration-only (BO-2400f-12-ii): unproducible only on an
    explicit ``test_required: false`` or an ``assigned_agent`` naming an agent
    outside ``_ROSTER_BUILD_AGENTS``; an unannotated record defaults to
    producible and readiness/priority/req_status/status are never read.  It
    performs no writes, so it never mutates the store (BO-2400f-12-i).
    Exposed via the check_producibility CLI subcommand, which fast-lane-ship.js
    dispatches between the Resolve and claim-connected steps so an
    unproducible resolved set refuses before any claim or build-agent
    dispatch.

    2026-09-14 FILE-SIZE SPLIT (NO behaviour change): this module measured
    1388 content lines (the check-file-size hook's own counter) against the
    repository's 400-line limit. Implementation moved to sibling modules
    under this same directory — _fl_common.py (path wiring + shared
    imported names), _fl_lifecycle.py (claim_build_set, release_claim,
    filter_already_claimed, mark_done_built_acs, check_no_stale_todo,
    _update_ac_work_status and friends), _fl_changelog.py
    (compute_changelog_requirement, build_changelog_payload),
    _fl_producibility.py (compute_producibility_verdict), _fl_selection.py
    (select_batch, _topo_order_build_set), _fl_red_baseline_support.py
    (verify_red_baseline's private helpers), _fl_coverage.py
    (verify_green_and_coverage), and _fl_cli.py (_build_cli_parser) — all
    re-exported here so every name previously importable from fast_lane
    remains importable from fast_lane. scripts/build_orchestration/ is
    deployed WHOLE by build_build_orchestration_scripts() in
    scripts/build_phases.py (a glob of every *.py file, not a hardcoded
    list), so these siblings deploy automatically with no build_phases.py
    edit required.

    resolve_connected_build_set and verify_red_baseline themselves remain
    physically defined in THIS module rather than moving to a sibling: the
    test suite calls mock.patch("fast_lane._load_ac", ...),
    mock.patch("fast_lane.traverse_ac_tree", ...), and
    mock.patch("fast_lane._run_pytest_and_parse", ...) to observe/stub
    exactly those two functions' internal behaviour. A mock.patch on a
    module attribute only affects a bare-name (global) lookup performed by
    code whose ``__globals__`` IS that module's own namespace — i.e. code
    physically defined (via ``def``) in that module. Re-exporting either
    function into fast_lane's namespace via `from _fl_x import fn` would
    NOT do: the function's `__globals__` would still be `_fl_x`'s dict, so
    the patch would silently have no effect and the mocked test double
    would never be consulted — a defect invisible to the test itself (it
    would still "pass" against the real implementation, not the intended
    stub). Every OTHER name each of these two functions calls as a bare
    global (_build_id_index, _drain_cycles, _is_leaf, _walk_ac_yamls,
    derive_parent_id, _topo_order_build_set, _scan_test_root_for_covers_tags,
    _resolve_git_baseline_context, _partition_newly_added,
    _classify_newly_added, _report_preexisting, _red_baseline_verdict,
    _RedBaselineGitError) is NOT patched via "fast_lane.<name>" anywhere in
    the suite, so those are imported normally from the sibling modules that
    now define them — an ordinary import re-binds the name in fast_lane's
    namespace to the same function object, which is all a plain (unpatched)
    call needs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _fl_cli import _build_cli_parser
from _fl_changelog import build_changelog_payload, compute_changelog_requirement
from _fl_common import (
    _LOG,
    _build_id_index,
    _drain_cycles,
    _is_leaf,
    _load_ac,
    _run_pytest_and_parse,
    _scan_test_root_for_covers_tags,
    _walk_ac_yamls,
    derive_parent_id,
    traverse_ac_tree,
    verify_done_eligible,
)
from _fl_coverage import verify_green_and_coverage
from _fl_lifecycle import (
    _update_ac_work_status,  # noqa: F401 — re-exported for `from fast_lane import _update_ac_work_status`
    check_no_stale_todo,
    claim_build_set,
    filter_already_claimed,
    mark_done_built_acs,
    release_claim,
)
from _fl_producibility import compute_producibility_verdict
from _fl_red_baseline_support import (
    _RedBaselineGitError,
    _classify_newly_added,
    _partition_newly_added,
    _red_baseline_verdict,
    _report_preexisting,
    _resolve_git_baseline_context,
)
from _fl_selection import _topo_order_build_set, select_batch

# ---------------------------------------------------------------------------
# Public API — resolve_connected_build_set and verify_red_baseline remain
# physically defined here (see the module ARCHITECTURE note above) because
# the test suite's mock.patch("fast_lane.<name>", ...) calls rely on their
# internal bare-name global lookups resolving through this module's own
# namespace.
# ---------------------------------------------------------------------------


def resolve_connected_build_set(
    ac_id: str,
    *,
    ac_root: Path,
    exclude_structural_parent: bool = False,
) -> list[str]:
    """Resolve the connected build set for *ac_id* in dependency order.

    The connected build set is::

        subtree(ac_id)  UNION  transitive_unmet_depends_on_closure(ac_id)

    where ``subtree(ac_id)`` is every L2/L3 descendant of *ac_id* reachable via
    ``covered_by`` (plus *ac_id* itself when it is a leaf), and the closure is
    every L2/L3 AC that is a direct or transitive ``depends_on`` prerequisite of
    a member of the set and is not yet ``work_status: done``.

    Selection rules (differs from :func:`select_batch`):
        * Only L2/L3 leaves with ``work_status != 'done'`` are returned.
        * Readiness is NOT a filter — a not-done ``draft``/``reviewed`` leaf is
          included (pointing at the AC is the operator's go-ahead).
        * The result is in dependency order: a prerequisite leaf always appears
          before any leaf that (transitively) depends on it.
        * Dependency cycles are broken deterministically (no infinite loop).
        * Already-done prerequisites are not pulled in (the dep is met).

    Args:
        ac_id: The target AC id to resolve the connected set for.
        ac_root: Root directory of the AC YAML store.
        exclude_structural_parent: When ``True``, any ``depends_on`` entry that
            equals ``derive_parent_id(node)`` (i.e. the structural parent of the
            node being expanded) is skipped and NOT added to the build set during
            the transitive closure walk.  Genuine (non-structural-parent)
            dependencies are still walked normally.  The subtree union step
            (``traverse_ac_tree``) is unaffected — the AC's own children always
            enter the set via the subtree, independent of this flag.  Defaults to
            ``False``, which preserves the existing behaviour where every
            ``depends_on`` entry is walked.

    Returns:
        Ordered list of not-done leaf AC ids (deps first). ``[]`` when the whole
        connected set is already done.

    Raises:
        ValueError: When *ac_id* does not exist in the store (message names the
            missing id — never a silent empty list).
    """
    yaml_paths = _walk_ac_yamls(ac_root) if ac_root.exists() else []
    all_records: list[dict] = []
    for path in yaml_paths:
        record = _load_ac(path)
        if record is not None:
            all_records.append(record)

    id_index = _build_id_index(all_records)
    # BO-2400c-6 correctness trap: _drain_cycles() below mutates id_index IN
    # PLACE, deleting cycle nodes, so it can produce a deterministic order for
    # the depends_on closure walk further down. Snapshot an UNDRAINED shallow
    # copy first — the tree walk (traverse_ac_tree) must see every record as
    # it stands on disk, including cycle members, or any subtree hanging off
    # a cycle-adjacent node silently vanishes from the build set with no
    # error (BO-2400c-6-i). The depends_on closure walk below intentionally
    # keeps using the drained `id_index` — that is the pre-existing,
    # unchanged behaviour this AC does not touch.
    undrained_id_index = dict(id_index)
    _drain_cycles(id_index, all_records)

    if ac_id not in id_index:
        msg = (
            f"resolve_connected_build_set: AC id {ac_id!r} not found in the store "
            f"at {ac_root} — check the id for typos (no build set resolved)."
        )
        raise ValueError(msg)

    # 1. Subtree leaves (not-done L2/L3 descendants via covered_by).
    build_set: set[str] = set(
        traverse_ac_tree(ac_id, ac_root, id_index=undrained_id_index, exclude_done=True)
    )

    # 2. Transitive unmet depends_on closure. A done prerequisite is already met
    #    and is not pulled in; a not-done composite dep expands to its leaves.
    worklist: list[str] = list(build_set)
    while worklist:
        node = worklist.pop()
        rec = id_index.get(node)
        if rec is None:
            continue
        for dep in rec.get("depends_on") or []:
            if exclude_structural_parent and dep == derive_parent_id(node):
                continue  # skip structural parent dep — not expanded into build set
            dep_rec = id_index.get(dep)
            if dep_rec is None or dep_rec.get("work_status", "") == "done":
                continue  # unknown or already-met prerequisite
            if _is_leaf(dep_rec):
                if dep not in build_set:
                    build_set.add(dep)
                    worklist.append(dep)
            else:
                for leaf in traverse_ac_tree(
                    dep, ac_root, id_index=undrained_id_index, exclude_done=True
                ):
                    if leaf not in build_set:
                        build_set.add(leaf)
                        worklist.append(leaf)

    return _topo_order_build_set(build_set, id_index)


def verify_red_baseline(
    *, ac_ids: list[str], test_root: Path, base_ref: str | None = None
) -> dict:
    """Check that at least one newly-added test covering *ac_ids* is red.

    Scans *test_root* for ``# covers: <id>`` tags matching any id in *ac_ids*,
    partitions the linked tests into newly-added and pre-existing using git
    at test-function granularity (BO-2400a-3-ii, -iii; the worktree's
    merge-base with ``origin/main``, or *base_ref* when supplied), runs them
    via pytest, and passes when at least one newly-added test is classified
    red (BO-2400a-3-v, amended 2026-08-17 from "every newly-added test must
    fail").  Pre-existing tests are reported but never affect the verdict
    (BO-2400a-3-iv).  When the git partition cannot be resolved, the gate
    fails closed rather than falling back to a permissive default
    (BO-2400a-3-vii).  Idempotent (BO-2400a-3-viii): resolving the partition
    performs read-only git queries only, never a fetch or ref update.

    Args:
        ac_ids: Batch of AC ids whose covering tests establish the baseline.
        test_root: Root directory to scan for ``*.py`` test files; must be
            inside a git worktree.
        base_ref: Optional explicit git ref to diff newly-added tests
            against.  Defaults to ``None``, which derives
            ``git merge-base HEAD origin/main`` from *test_root*.

    Returns:
        Dict with keys:

        ``gate_passed`` (bool)
            True iff at least one newly-added covering test is red.

        ``reason`` (str | None)
            ``None`` when ``gate_passed`` is True; otherwise exactly one of
            ``"no_new_covering_tests"``, ``"all_new_tests_green_at_baseline"``,
            ``"no_red_outcome_among_new_tests"``, or
            ``"baseline_partition_unavailable"`` (BO-2400a-3-i, -vii).

        ``red``, ``green_at_baseline``, ``inconclusive`` (list[dict])
            Newly-added tests classified per BO-2400a-3-vi, each entry
            ``{"nodeid": str, "ac_id": str, "outcome": str}``.

        ``preexisting`` (list[dict])
            Pre-existing tests in the same entry shape — reported but
            excluded from the verdict (BO-2400a-3-iv).
    """
    batch_set = set(ac_ids)
    all_tags = _scan_test_root_for_covers_tags(test_root)
    linked_tags = [t for t in all_tags if t["ac_id"] in batch_set]

    try:
        repo_root, resolved_base_ref = _resolve_git_baseline_context(test_root, base_ref)
        newly_added_tags, preexisting_tags = _partition_newly_added(
            linked_tags, repo_root, resolved_base_ref
        )
    except _RedBaselineGitError as exc:
        _LOG.warning("verify_red_baseline: baseline partition unavailable: %s", exc)
        return _red_baseline_verdict(
            gate_passed=False, reason="baseline_partition_unavailable"
        )

    test_files = list({t["file"] for t in newly_added_tags + preexisting_tags})
    pytest_results = _run_pytest_and_parse(test_files)

    red, green_at_baseline, inconclusive = _classify_newly_added(
        newly_added_tags, pytest_results
    )
    preexisting = _report_preexisting(preexisting_tags, pytest_results)

    if not newly_added_tags:
        return _red_baseline_verdict(
            gate_passed=False,
            reason="no_new_covering_tests",
            preexisting=preexisting,
        )

    if red:
        return _red_baseline_verdict(
            gate_passed=True,
            reason=None,
            red=red,
            green_at_baseline=green_at_baseline,
            inconclusive=inconclusive,
            preexisting=preexisting,
        )

    reason = (
        "all_new_tests_green_at_baseline"
        if not inconclusive
        else "no_red_outcome_among_new_tests"
    )
    return _red_baseline_verdict(
        gate_passed=False,
        reason=reason,
        green_at_baseline=green_at_baseline,
        inconclusive=inconclusive,
        preexisting=preexisting,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the fast-lane pipeline gates.

    Dispatches to select_batch, select_connected, verify_red_baseline,
    verify_green_and_coverage, claim, release, or mark_done based on the
    subcommand, prints the result as JSON to stdout, and returns an exit
    code matching the gate outcome.

    Exit codes:

    * ``select_batch``: always 0 (an empty list is a valid result).
    * ``select_connected``: always 0; 1 when the AC id is not found.
    * ``verify_red_baseline``: 0 when gate_passed is True (at least one
      newly-added covering test is red); 1 otherwise — including the
      baseline_partition_unavailable fail-closed case.
    * ``verify_green_and_coverage``: 0 when both green and coverage_ok are
      True; 1 when either condition fails.
    * ``claim``: 0 when ACs are claimed successfully; 1 when target_refused
      (whole set already in_progress) or an I/O error occurs.
    * ``release``: always 0 (idempotent; releasing a todo AC is a no-op).
    * ``mark_done``: 0 when all ACs are done (all_done=True); 1 when any
      AC in the set is still not done (stale-todo guard).

    Args:
        argv: Argument list.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        Integer exit code per the gate outcome described above.
    """
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "select_batch":
        result = select_batch(ac_root=Path(args.ac_root), limit=args.limit)
        print(json.dumps(result))
        return 0

    if args.subcommand == "select_connected":
        try:
            result = resolve_connected_build_set(
                args.ac,
                ac_root=Path(args.ac_root),
                exclude_structural_parent=args.exclude_structural_parent,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result))
        return 0

    if args.subcommand == "verify_red_baseline":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        red_verdict = verify_red_baseline(
            ac_ids=ac_ids,
            test_root=Path(args.test_root),
            base_ref=args.base_ref,
        )
        print(json.dumps(red_verdict))
        return 0 if red_verdict["gate_passed"] else 1

    if args.subcommand == "verify_green_and_coverage":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        green_verdict = verify_green_and_coverage(
            ac_ids=ac_ids,
            test_root=Path(args.test_root),
            ac_root=Path(args.ac_root),
        )
        print(json.dumps(green_verdict))
        return 0 if (green_verdict["green"] and green_verdict["coverage_ok"]) else 1

    if args.subcommand == "check_producibility":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        verdict = compute_producibility_verdict(ac_ids, ac_root=Path(args.ac_root))
        print(json.dumps(verdict))
        return 0 if verdict["producible"] else 1

    if args.subcommand == "claim":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        filter_result = filter_already_claimed(ac_ids, ac_root=ac_root)
        to_build = filter_result["to_build"]
        excluded_claimed = filter_result["excluded_claimed"]
        target_refused = filter_result["target_refused"]
        if target_refused:
            refused_payload = {
                "claimed": [],
                "excluded_claimed": excluded_claimed,
                "target_refused": True,
            }
            print(json.dumps(refused_payload))
            return 1
        claim_result = claim_build_set(to_build, ac_root=ac_root)
        claim_payload = {
            "claimed": claim_result["claimed"],
            "excluded_claimed": excluded_claimed,
            "target_refused": False,
            "success": claim_result["success"],
            "error": claim_result["error"],
        }
        print(json.dumps(claim_payload))
        if not claim_result["success"]:
            # BO-2400e-3-i: a write that could never be made must never be
            # reported as a success. claim_result["error"] already names
            # both the failing AC id and the underlying OS reason (see
            # claim_build_set), so it is printed here rather than
            # discarded -- "log at WARNING and return 0" (this repo's
            # forbidden anti-pattern, CLAUDE.md Error Handling Policy Rule
            # 3) would tell the caller it is safe to dispatch test-writer/
            # coder against ACs that were never actually claimed.
            print(claim_result["error"], file=sys.stderr)
            return 1
        return 0

    if args.subcommand == "release":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        release_result = release_claim(ac_ids, [], ac_root=ac_root)
        print(json.dumps({"released": release_result["released"]}))
        return 0

    if args.subcommand == "mark_done":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        test_root = Path(args.test_root)
        covered_ac_ids: list[str] = []
        for ac_id in ac_ids:
            verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
            if verdict["eligible"]:
                covered_ac_ids.append(ac_id)
        mark_result = mark_done_built_acs(ac_ids, covered_ac_ids, ac_root=ac_root)
        stale_result = check_no_stale_todo(ac_ids, ac_root=ac_root)
        mark_done_payload = {
            "marked_done": mark_result["marked_done"],
            "all_done": stale_result["all_done"],
            "stale": stale_result["stale"],
        }
        print(json.dumps(mark_done_payload))
        return 0 if stale_result["all_done"] else 1

    if args.subcommand == "changelog_requirement":
        changed_paths = [p.strip() for p in args.files.split(",") if p.strip()]
        requirement = compute_changelog_requirement(changed_paths)
        print(json.dumps(requirement))
        return 0

    if args.subcommand == "changelog_payload":
        built_ac_ids = [i.strip() for i in args.built_ac_ids.split(",") if i.strip()]
        files_modified = [p.strip() for p in args.files_modified.split(",") if p.strip()]
        payload = build_changelog_payload(
            target_ac=args.target_ac,
            built_ac_ids=built_ac_ids,
            files_modified=files_modified,
            branch=args.branch,
            ac_root=Path(args.ac_root),
        )
        print(json.dumps(payload))
        return 0

    return 1  # unreachable with argparse required=True, but satisfies mypy


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[fast-lane] unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Split this module
#   (measured 1388 content lines against the 400-line check-file-size
#   limit) into sibling modules under scripts/build_orchestration/ — see
#   the module ARCHITECTURE note above for the full file-by-file map and
#   the reason resolve_connected_build_set / verify_red_baseline / main()
#   stayed here. Every function's docstring, body, and DECISION HISTORY
#   entries moved verbatim to the sibling module that now owns it — see
#   each sibling's own DECISION HISTORY for the pre-split record of that
#   function's changes. NO BEHAVIOUR CHANGE: every name previously
#   importable from fast_lane remains importable from fast_lane via
#   re-export, and every mock.patch("fast_lane.<name>", ...) target used by
#   the test suite (_load_ac, traverse_ac_tree, _run_pytest_and_parse)
#   still resolves through this module's own namespace exactly as before.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
