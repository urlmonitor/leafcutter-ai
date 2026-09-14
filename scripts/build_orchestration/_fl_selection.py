"""
MODULE: scripts/build_orchestration/_fl_selection.py
GOAL: The dormant select_batch AC selection function and the dependency-order
    topological sort helper it (and resolve_connected_build_set) share.
BUSINESS CONTEXT: select_batch reuses scan_ac_store filter/sort helpers so
    readiness semantics track the scanner exactly. It has no production
    caller today (see its own docstring) but is deliberately retained —
    dormant, not dead. _topo_order_build_set is the deterministic
    prerequisites-first ordering used by resolve_connected_build_set
    (fast_lane.py) to order a resolved connected build set. Extracted
    verbatim from fast_lane.py (NO behaviour change) as part of the
    2026-09-14 file-size split — see fast_lane.py's own DECISION HISTORY
    for the full record.
ARCHITECTURE: resolve_connected_build_set (fast_lane.py) imports
    _topo_order_build_set from this module and calls it as a plain function
    reference — unlike traverse_ac_tree / _load_ac / _run_pytest_and_parse,
    no test patches "fast_lane._topo_order_build_set", so relocating its
    definition here does not disturb any mock.patch target.
"""

from __future__ import annotations

from pathlib import Path

from _fl_common import (
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
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_batch(*, ac_root: Path, limit: int) -> list[str]:
    """Select up to *limit* ready leaf ACs and return their ids in stable order.

    The selection and sort order exactly mirrors scan_ac_store: priority
    ascending (critical < high < medium < low), then estimated_complexity
    ascending (S < M < L < XL), then id ascending.  The same store state always
    yields the identical ordered list — the function is deterministic and does
    NOT modify the store.

    Ready leaf requirements (same as scan_ac_store):
        * level: L2 or L3
        * status: active
        * readiness: approved
        * work_status: todo
        * all depends_on have work_status: done (or the list is empty)

    Args:
        ac_root: Root directory of the AC YAML store.
        limit: Maximum number of AC ids to return (cohesion cap M).

    Returns:
        Ordered list of at most *limit* ready AC ids.  Returns ``[]`` when no
        ready ACs exist or *ac_root* does not exist.

    NO PRODUCTION CALLER TODAY — READ THIS BEFORE DELETING OR BUILDING ON IT.
    Nothing in the shipping lane invokes this function or its ``select_batch``
    CLI subcommand.  Its only former caller was ``fast-lane-build.js``, an
    orphaned second runner deleted under BO-2400c-1-v.  The live lane
    (``fast-lane-ship.js``) calls ``select_connected`` instead, which is a
    DIFFERENT operation: it resolves one AC's connected build set, whereas this
    picks up to N ready ACs from the whole store.  ``select_connected`` is not a
    superset and does not replace this.  The lane stopped calling it because
    BO-2400f moved the lane from batch-mode to single-AC-mode, not because
    anything superseded it.

    It is therefore DORMANT, not dead, and deliberately retained:

    * Its behaviour is covered by tests that EXECUTE it, including
      ``TestSelectBatchCli`` in unit_tests/build_orchestration/test_fast_lane_cli.py,
      which runs the CLI as a real subprocess.
    * ACD-2000b-4 once named this function as "the requirement-grain selection
      this rule constrains".  AS OF 2026-09-01 IT EXPLICITLY DOES NOT: an IT-PO
      surface decision re-pointed that rule at the claim path
      (``filter_already_claimed``), which the live lane really does invoke, and
      away from this function, which it does not.  The determinism guarantee
      below is retained as a general property of the rule wherever it lands,
      not as a reason to implement it here.

    Two consequences, and both have bitten this repository before:

    * Do NOT delete it as dead code.  This is now the ONLY thing standing
      against that, since the ACD-2000b-4 claim above has been withdrawn — so
      read it as the whole of the case rather than half of it.  The function
      has no caller, but it has a tested capability (see above) and no
      replacement: ``select_connected`` resolves one AC's connected set and
      does not select N ready ACs from the store.  Deleting it retires that
      capability with nobody deciding to — the exact shape KI-BO-006 was
      written about.
    * Do NOT build ACD-2000b-4's overlap rule onto it.  THAT CHOICE IS NOW MADE
      (2026-09-01) and it went the other way: the rule's host is the claim path
      the live lane invokes on every run — ``fast-lane-ship.js`` calls
      ``fast_lane.py claim``, whose handler reaches ``filter_already_claimed``,
      which already walks the store and already decides admit-or-refuse, on
      ``work_status`` alone.  A footprint comparison is missing there.
      Implemented here instead, the rule would never fire, because nothing
      calls this.
    """
    if not ac_root.exists():
        return []

    yaml_paths = _walk_ac_yamls(ac_root)
    all_records: list[dict] = []
    for path in yaml_paths:
        record = _load_ac(path)
        if record is not None:
            all_records.append(record)

    id_index = _build_id_index(all_records)
    _drain_cycles(id_index, all_records)

    filtered: list[dict] = []
    for ac in all_records:
        if not _is_leaf(ac):
            continue
        if not _matches_work_status(ac, "todo"):
            continue
        if not _is_active(ac):
            continue
        if not _is_approved(ac):
            continue
        filtered.append(ac)

    ready: list[dict] = []
    for ac in filtered:
        status, _ = _classify_ac(ac, id_index)
        if status == "ready":
            ready.append(ac)

    ready = _sort_ready(ready)
    return [ac.get("id", "") for ac in ready[:limit]]


def _topo_order_build_set(
    build_set: set[str],
    id_index: dict[str, dict],
) -> list[str]:
    """Return *build_set* ids in dependency order (prerequisites first).

    Depth-first post-order over the ``depends_on`` edges restricted to
    *build_set*. Nodes and in-set dependencies are visited in ascending id order
    so the same store state always yields the identical list (deterministic).
    A grey-node guard breaks any residual dependency cycle without recursing
    forever.

    Args:
        build_set: The set of AC ids to order.
        id_index: Full id-to-record mapping (for ``depends_on`` lookup).

    Returns:
        Ordered list of the ids in *build_set*, prerequisites before dependents.
    """
    order: list[str] = []
    black: set[str] = set()
    grey: set[str] = set()

    def _visit(node: str) -> None:
        if node in black or node in grey:
            return
        grey.add(node)
        rec = id_index.get(node) or {}
        in_set_deps = sorted(
            dep for dep in (rec.get("depends_on") or []) if dep in build_set
        )
        for dep in in_set_deps:
            _visit(dep)
        grey.discard(node)
        black.add(node)
        order.append(node)

    for node in sorted(build_set):
        _visit(node)
    return order


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
