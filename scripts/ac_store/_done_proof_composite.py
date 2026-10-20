"""
MODULE: _done_proof_composite
GOAL: Derive composite AC proof from every covered child using its language runner.
BUSINESS CONTEXT: Composite ACs inherit their children's proof. Routing TypeScript
    child files to pytest incorrectly refuses otherwise valid frontend work.
ARCHITECTURE: Resolve and check all leaf descendants, then reuse done_proof's
    Python and TypeScript phases. Local imports preserve the public module's
    runner seams without creating a module-load cycle. Leaf reachability policy
    remains in done_proof and is not applied to composite proofs.
    BO-202: also owns the ONE composite classifier (covered_by AC-id children
    vs test paths, store-wide covers-tag scan, recursive unproven-child
    resolution) shared by check_done_proof.py and mark_ac_done.py, so the
    commit-time hook and the work_status writer can never disagree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

import ac_retirement  # ACS-900d-4: the ONE retired-record predicate (looked up at call time)
from test_enforcement import COVERS_TAG_RE

# Directory names excluded from all test-file scanning (both .py and .ts/.tsx).
# Prevents traversal into node_modules and other non-test subtrees.
_EXCLUDED_SCAN_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".next",
        "dist",
        "coverage",
        ".git",
        "__pycache__",
        ".venv",
    }
)


def _collect_all_covered_ids(test_root: Path) -> set[str]:
    """Scan *test_root* recursively and return all AC ids referenced in covers tags.

    Reads every ``*.py``, ``*.ts``, and ``*.tsx`` file under *test_root``, extracting
    the id from every ``# covers: <id>`` (Python) or ``// covers: <id>``
    (TypeScript/JavaScript) comment line.  Uses the shared :data:`COVERS_TAG_RE`
    seam (BO-2500e-1) so both syntax forms are recognised.

    Directories named ``node_modules``, ``.next``, ``dist``, ``coverage``,
    ``.git``, ``__pycache__``, and ``.venv`` are excluded from traversal.

    This is a STATIC presence-only scan — no tests are run.  Unreadable files
    are logged to stderr and skipped.

    Args:
        test_root: Root directory to search recursively for test files.

    Returns:
        Set of AC id strings found in ``covers:`` comments.  Empty set when
        *test_root* does not exist or contains no readable test files.
    """
    covered: set[str] = set()
    try:
        py_files = sorted(test_root.rglob("*.py"))
        ts_files = sorted(test_root.rglob("*.ts"))
        tsx_files = sorted(test_root.rglob("*.tsx"))
    except OSError as exc:
        print(
            f"WARNING: check_done_proof: cannot scan {test_root}: {exc}",
            file=sys.stderr,
        )
        return covered

    all_test_files = (
        [f for f in py_files if not any(p in _EXCLUDED_SCAN_DIRS for p in f.parts)]
        + [f for f in ts_files if not any(p in _EXCLUDED_SCAN_DIRS for p in f.parts)]
        + [f for f in tsx_files if not any(p in _EXCLUDED_SCAN_DIRS for p in f.parts)]
    )

    for test_file in all_test_files:
        try:
            text = test_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"WARNING: check_done_proof: cannot read {test_file}: {exc}",
                file=sys.stderr,
            )
            continue
        for match in COVERS_TAG_RE.finditer(text):
            covered.add(match.group(1))
    return covered


def _composite_child_ids(covered_by: object) -> list[str]:
    """Return the AC-id children of a ``covered_by`` value, excluding test paths.

    BO-2500b-1-iii: the single place deciding which ``covered_by`` entries
    count as composite children — shared by :func:`check_staged_done_proofs`
    and :func:`_unproven_composite_children` so the two never disagree. This
    store also uses ``covered_by`` on a LEAF to record its own proving
    test-file path(s) (e.g. this very AC's own record) — an entry is that,
    not an AC-id child, when it contains a path separator or ends in a
    recognised test-file extension (mirroring, in spirit, the
    store-resolvability convention ``done_proof.py::_has_resolvable_child``
    already uses for the same distinction).

    Args:
        covered_by: The raw ``covered_by`` value from a parsed AC YAML
            mapping (expected to be a list, but may be any YAML-parsed type).

    Returns:
        Entries that are NOT test-file paths. Empty when *covered_by* is not
        a list, is empty, or holds only test paths — all three mean "this AC
        is a leaf, not a composite".
    """
    return [e for e in map(str, covered_by if isinstance(covered_by, list) else []) if not re.search(r"[/\\]|\.(py|ts|tsx)$", e)]


def collect_store_ids(ac_root: Path | None) -> frozenset[str]:
    """Return the id of every AC record under *ac_root* (the filename stem).

    The store convention is that a record's filename stem equals its ``id``
    (:func:`_resolve_child_ac` relies on the same convention), so this is one
    directory walk with no YAML parsing. Callers compute it ONCE per hook or CI
    run and hand it to ``ac_retirement.is_retired``.

    Args:
        ac_root: The ``acceptance-criteria`` directory, or ``None``.

    Returns:
        The ids found. Empty when *ac_root* is ``None`` or cannot be walked, so
        a retirement check against it answers "not retired" (fails closed).
    """
    if ac_root is None:
        return frozenset()
    try:
        return frozenset(path.stem for path in ac_root.rglob("*.yaml"))
    except OSError as exc:
        print(f"WARNING: check_done_proof: cannot scan {ac_root}: {exc}", file=sys.stderr)
        return frozenset()


def _entry_retired(ac_id: str, info: dict, ac_status_map: dict[str, dict]) -> bool:
    """Return whether the status-map entry *info* for *ac_id* is retired (ACS-900d-4)."""
    return ac_retirement.is_retired({"id": ac_id, **info}, ac_status_map)


def _has_resolvable_child(covered_by: list[str], ac_status_map: dict[str, dict]) -> bool:
    """Return whether at least one entry of *covered_by* resolves to a real AC.

    BO-2500a-6 remediation M-2: legacy ACs hold TEST FILE PATHS in
    ``covered_by``; none resolve to a record in *ac_status_map*, so such an AC
    is a LEAF, not a composite with phantom "uncovered children". The
    classification is data-driven: it checks store resolvability only.

    Args:
        covered_by: The AC's own ``covered_by`` list.
        ac_status_map: ``{ac_id: entry}`` from ``_build_ac_status_map``.

    Returns:
        ``True`` iff at least one entry is a key in *ac_status_map*.
    """
    return any(entry in ac_status_map for entry in covered_by)


def _has_live_child(covered_by: list[str], ac_status_map: dict[str, dict]) -> bool:
    """Return whether *covered_by* names at least one resolvable, NON-retired child."""
    return any(
        entry in ac_status_map and not _entry_retired(entry, ac_status_map[entry], ac_status_map)
        for entry in covered_by
    )


def _resolve_all_child_ids(
    covered_by: list[str],
    ac_status_map: dict[str, dict],
    _seen: set[str] | None = None,
) -> list[str]:
    """Flatten a composite's ``covered_by`` tree into its leaf descendant ids.

    A child that is itself a composite (it has a LIVE resolvable child --
    BO-2500a-6-ii) is expanded recursively; a child holding only test-file
    paths, or whose children are all retired, is a LEAF needing its own
    covers-tagged test (ACS-900d-4-iv). A RETIRED child (``ac_retirement``)
    stays in ``covered_by`` as an audit trail but owes no proof and supplies
    none: it contributes nothing. Cycles are broken via *_seen*. An entry that
    does not resolve in *ac_status_map* is skipped entirely.

    Args:
        covered_by: The composite's own list of direct child AC ids.
        ac_status_map: ``{ac_id: entry}`` from ``_build_ac_status_map``; its keys
            are the whole-store id set the retirement predicate needs.
        _seen: Internal recursion guard; callers should omit this argument.

    Returns:
        Leaf AC ids reachable from *covered_by*, in traversal order.
    """
    seen = _seen if _seen is not None else set()
    leaf_ids: list[str] = []
    for child_id in covered_by:
        if child_id in seen:
            continue
        seen.add(child_id)
        child_info = ac_status_map.get(child_id)
        if child_info is None or _entry_retired(child_id, child_info, ac_status_map):
            continue  # unresolvable entry, or a retired child that owes and gives no proof
        child_covered_by = child_info.get("covered_by", [])
        if _has_live_child(child_covered_by, ac_status_map):
            leaf_ids.extend(_resolve_all_child_ids(child_covered_by, ac_status_map, seen))
        else:
            leaf_ids.append(child_id)
    return leaf_ids


def _retired_verdict(
    ac_id: str, ac_status_map: dict[str, dict], dangling_tags: list[dict]
) -> dict | None:
    """Return the "eligible" verdict for a retired *ac_id*, else ``None`` (ACS-900d-4).

    A retired record is never asked for a covering test or for finished
    children, and its own ``work_status`` is not re-evaluated. This is a
    read-side decision: nothing is written to the record.

    Args:
        ac_id: The AC being judged.
        ac_status_map: ``{ac_id: entry}`` from ``_build_ac_status_map``.
        dangling_tags: Dangling-tag diagnostics, passed through unchanged.

    Returns:
        A verdict dict shaped like ``verify_done_eligible``'s, or ``None`` when
        *ac_id* is not retired.
    """
    info = ac_status_map.get(ac_id)
    if info is None or not _entry_retired(ac_id, info, ac_status_map):
        return None
    return {
        "eligible": True,
        "reason": "",
        "passing_tests": [],
        "failing_tests": [],
        "dangling_tags": dangling_tags,
    }


def _find_ac_root(yaml_path: Path) -> Path | None:
    """Return the ancestor ``acceptance-criteria`` directory of *yaml_path*.

    Used to resolve an L0/L1 composite's ``covered_by`` children by id
    (BO-2500b-1-ii) — the store lays composites and their children out as
    siblings (or descendants) under a shared ``docs/acceptance-criteria/``
    tree, so walking up from the staged file to that directory name gives a
    root to search for the child records.

    Args:
        yaml_path: Absolute or relative path to a staged AC YAML file.

    Returns:
        The ``acceptance-criteria`` ancestor directory, or ``None`` when no
        such ancestor exists (e.g. a path outside the AC store) — callers
        treat ``None`` as "children cannot be resolved" and fail closed
        (report unproven), never as "skip the composite".
    """
    for parent in yaml_path.resolve().parents:
        if parent.name == "acceptance-criteria":
            return parent
    return None


def _load_ac_yaml_or_none(path: Path) -> dict | None:
    """Read and parse an AC YAML file, returning ``None`` on any failure.

    Read/parse failures and non-mapping documents are logged to stderr at
    WARNING and treated as unresolved rather than fatal, matching the
    fail-open static-scan behaviour of the rest of this module.

    Args:
        path: Path to the AC YAML file to read.

    Returns:
        The parsed mapping, or ``None`` when the file cannot be read/parsed
        or does not contain a YAML mapping.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        print(
            f"WARNING: check_done_proof: cannot read {path}: {exc}",
            file=sys.stderr,
        )
        return None
    return data if isinstance(data, dict) else None


def _resolve_child_ac(ac_root: Path, child_id: str) -> dict | None:
    """Locate and load a child AC's YAML record by id under *ac_root*.

    Args:
        ac_root: Root ``acceptance-criteria`` directory to search recursively.
        child_id: The child AC's ``id`` field value; the store convention is
            that the filename stem equals the id (``<id>.yaml``).

    Returns:
        The child's parsed YAML mapping, or ``None`` when no matching file is
        found or it cannot be read/parsed.
    """
    try:
        matches = sorted(ac_root.rglob(f"{child_id}.yaml"))
    except OSError as exc:
        print(
            f"WARNING: check_done_proof: cannot scan {ac_root} for {child_id}: {exc}",
            file=sys.stderr,
        )
        return None
    if not matches:
        return None
    return _load_ac_yaml_or_none(matches[0])


def _judge_child(
    child_id: str,
    ac_root: Path | None,
    all_covered_ids: set[str],
    store_ids: frozenset[str],
    seen: set[str],
) -> tuple[bool, list[str]]:
    """Judge one AC-id child of a composite: is it live, and what is unproven?

    Args:
        child_id: The child's AC id.
        ac_root: The ``acceptance-criteria`` root, or ``None`` (fail closed).
        all_covered_ids: AC ids carrying a covers tag anywhere under the test root.
        store_ids: Every AC id in the whole store (retirement successor check).
        seen: The caller's cycle guard, shared with nested composites.

    Returns:
        ``(live, unproven)``. A retired child is not live and proves nothing; an
        unresolvable child is not live and is itself unproven (fail closed).
    """
    from done_proof import is_covers_tag_waived  # local: avoids module-load cycle

    child_data = _resolve_child_ac(ac_root, child_id) if ac_root is not None else None
    if child_data is None:
        return False, [child_id]
    if ac_retirement.is_retired(child_data, store_ids):
        return False, []  # ACS-900d-4-iv: stays in covered_by, owes and gives no proof
    if child_data.get("work_status") != "done":
        return True, [child_id]
    if _composite_child_ids(child_data.get("covered_by")):
        nested = _unproven_composite_children(
            child_data, ac_root, all_covered_ids, store_ids=store_ids, _seen=seen
        )
        return True, nested
    proven = child_id in all_covered_ids or is_covers_tag_waived(child_data)
    return True, [] if proven else [child_id]


def _unproven_composite_children(
    data: dict,
    ac_root: Path | None,
    all_covered_ids: set[str],
    *,
    store_ids: frozenset[str] | None = None,
    _seen: set[str] | None = None,
) -> list[str]:
    """Return the ids of ``covered_by`` children that fail to prove a composite done.

    Implements the BO-2500b-1-ii/iii model: a composite's fulfilment is
    DERIVED from its children rather than proven by a covers tag naming its
    own id. Compositeness is a ``covered_by`` list containing at least one
    AC-id child, at any level, matching
    :func:`scripts.ac_store.done_proof._verify_composite_eligible` (used by
    ``mark_ac_done.py``) — not by ``level`` alone, and never a test-file-path
    entry (:func:`_composite_child_ids`, shared with
    :func:`check_staged_done_proofs` so both agree). A child proves
    itself when ``work_status: done`` AND either (a) it is a leaf (no AC-id
    children) carrying its own ``# covers: <child-id>`` tag or waiving it via
    :func:`done_proof.is_covers_tag_waived` (BO-2500a-1-ii: test_required false
    plus a non-empty test_rationale), or (b) it is a
    composite whose own children all recursively prove it.

    A composite is NEVER treated as proven unconditionally: a ``covered_by``
    with no AC-id children has nothing to derive fulfilment from and is
    reported as its own unproven id. This is the guard against the ACD-400a
    falsely-done-composite defect (20 recorded instances in this repo) —
    composites must be provably done via their children, not skipped.

    Retired children (ACS-900d-4-iv, :func:`ac_retirement.is_retired`) are
    neither a block nor a proof: a todo retired child does not hold the parent
    back and a done, covered retired child does not prove it. When EVERY child
    is retired the composite falls back to the single-record rule -- its own
    covers tag or waiver (``[]`` when it has one, ``[<own id>]`` when not). A
    child whose supersession is structurally invalid (missing successor, empty
    list, self-reference) is NOT retired and counts as live.

    Args:
        data: Parsed YAML mapping of the composite AC being evaluated.
        ac_root: Root ``acceptance-criteria`` directory to resolve children
            under, or ``None`` when it could not be determined (children then
            fail closed as unproven).
        all_covered_ids: Set of AC ids found in ``# covers:``/``// covers:``
            tags anywhere under the test root (from
            :func:`_collect_all_covered_ids`).
        store_ids: Every AC id in the whole store. Computed once from
            *ac_root* when omitted; hook callers pass one shared set per run.
        _seen: Internal cycle guard against a malformed ``covered_by`` cycle;
            callers should not pass this.

    Returns:
        Empty list when every AC-id child in ``covered_by`` is proven done
        and covered; otherwise a list of the unproven child (or composite)
        ids. Test-path entries never appear in the result.
    """
    from done_proof import is_covers_tag_waived  # local: avoids module-load cycle

    seen = _seen if _seen is not None else set()
    store_ids = collect_store_ids(ac_root) if store_ids is None else store_ids
    own_id = str(data.get("id", "?"))
    child_ids = _composite_child_ids(data.get("covered_by"))
    if not child_ids:
        return [own_id]

    unproven: list[str] = []
    live_children = 0
    for child_id_str in child_ids:
        if child_id_str in seen:
            continue
        seen.add(child_id_str)
        live, child_unproven = _judge_child(child_id_str, ac_root, all_covered_ids, store_ids, seen)
        live_children += live
        unproven.extend(child_unproven)

    if live_children == 0 and not unproven:
        # ACS-900d-4-iv: every child is retired, so there is nothing to derive
        # fulfilment from. The composite falls back to the single-record rule:
        # its OWN covers tag, or a valid covers-tag waiver. Never vacuously proven.
        own_proof = own_id in all_covered_ids or is_covers_tag_waived(data)
        return [] if own_proof else [own_id]
    return unproven


def _own_proof_verdict(
    ac_id: str, ac_status_map: dict[str, dict], dangling_tags: list[dict]
) -> dict:
    """Judge a composite whose children are ALL retired by the single-record rule.

    ACS-900d-4-iv: with no live child there is nothing to derive fulfilment
    from, so the composite needs its OWN covers tag (the caller reaches here
    only when none is linked) or a valid covers-tag waiver. It is never proven
    vacuously.

    Args:
        ac_id: The composite being judged.
        ac_status_map: ``{ac_id: entry}`` from ``_build_ac_status_map``.
        dangling_tags: Dangling-tag diagnostics, passed through unchanged.

    Returns:
        The standard eligibility verdict.
    """
    from done_proof import is_covers_tag_waived  # local: avoids module-load cycle

    waived = is_covers_tag_waived(ac_status_map.get(ac_id))
    return {
        "eligible": waived,
        "reason": "" if waived else f"no linked test found for {ac_id}",
        "passing_tests": [],
        "failing_tests": [],
        "dangling_tags": dangling_tags,
    }


def _verify_composite_eligible(
    ac_id: str,
    covered_by: list[str],
    *,
    ac_status_map: dict[str, dict],
    all_tags: list[dict],
    dangling_tags: list[dict],
) -> dict:
    """Require coverage and passing test outcomes for every leaf descendant.

    Args:
        ac_id: Composite identifier used in refusal diagnostics.
        covered_by: Direct child identifiers, resolved recursively in the store.
        ac_status_map: AC records containing status and child references.
        all_tags: Real covers-tag records collected by the shared scanner.
        dangling_tags: Existing dangling-tag diagnostics, passed through unchanged.

    Returns:
        The standard eligibility verdict, with Python node and TypeScript file
        outcomes. TypeScript files shared by several covered children run once.
    """
    from done_proof import (
        JsRunnerUnavailable,
        _build_failure_reason,
        _collect_linked_tests,
        _run_python_test_phase,
        _run_ts_test_phase,
        _split_linked_tests_by_language,
        is_covers_tag_waived,
    )

    leaf_child_ids = _resolve_all_child_ids(covered_by, ac_status_map)
    if not leaf_child_ids and not _has_live_child(covered_by, ac_status_map):
        return _own_proof_verdict(ac_id, ac_status_map, dangling_tags)
    if not leaf_child_ids:
        return {
            "eligible": False,
            "reason": f"composite {ac_id} has no coverable children",
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    per_child_tests = {
        child_id: _collect_linked_tests(child_id, all_tags) for child_id in leaf_child_ids
    }
    uncovered_children = sorted(
        child_id
        for child_id, tests in per_child_tests.items()
        if not tests and not is_covers_tag_waived(ac_status_map.get(child_id))
    )
    if uncovered_children:
        return {
            "eligible": False,
            "reason": (
                f"composite {ac_id} has uncovered children: "
                + ", ".join(uncovered_children)
            ),
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    linked_tests = [test for tests in per_child_tests.values() for test in tests]
    py_linked, ts_linked = _split_linked_tests_by_language(linked_tests)
    py_passing, py_failing, pytest_results, incomplete_reason = _run_python_test_phase(
        ac_id, py_linked
    )
    if incomplete_reason is not None:
        return {
            "eligible": False,
            "reason": incomplete_reason,
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    try:
        ts_passing, ts_failing = _run_ts_test_phase(ts_linked)
    except JsRunnerUnavailable as exc:
        return {
            "eligible": False,
            "reason": f"JS runner unavailable for {ac_id}: {exc}",
            "passing_tests": py_passing,
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    passing_tests = py_passing + ts_passing
    failing_tests = py_failing + ts_failing
    return {
        "eligible": not failing_tests,
        "reason": (
            _build_failure_reason(ac_id, py_failing, ts_failing, pytest_results)
            if failing_tests else ""
        ),
        "passing_tests": passing_tests,
        "failing_tests": failing_tests,
        "dangling_tags": dangling_tags,
    }


# DECISION HISTORY
# ================================================================================
# - 2026-10-05 07:01 UTC [python-coder]: Extracted composite orchestration from
#   done_proof and reused the leaf language phases so TS-only and mixed children
#   are verified by their actual runners without weakening descendant coverage.
#   (#TICKETLESS reason=user-authorized-composite-proof-ci-repair)
# - 2026-10-06 [python-coder]: BO-202 moved _composite_child_ids,
#   _unproven_composite_children and their helpers here verbatim from
#   check_done_proof.py so mark_ac_done.py imports the same function objects
#   instead of copying them. (ticket 06 EPIC-BuildToolingRunsThrough)
# - 2026-10-15 [python-coder]: ACS-900d-4. is_superseded_ac (KI-ACS-016: any
#   non-empty superseded_by OR req_status superseded) is gone; both composite
#   rollups now ask ac_retirement.is_retired (superseded status, existing
#   successors, no self-reference). _has_resolvable_child and
#   _resolve_all_child_ids moved here from done_proof.py (re-exported there) to
#   repay done_proof.py's file-size ratchet. A composite whose children are ALL
#   retired falls back to the single-record rule instead of being refused
#   unconditionally. (#TICKETLESS reason=acs-900d-4-ac-driven-no-ticket-file)
