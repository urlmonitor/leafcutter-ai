"""
MODULE: done_proof
GOAL: Verify that an AC is eligible to be marked done based on covers-tag linkage.
BUSINESS CONTEXT: Part of the BO-2500 mechanical done-proof gate.  An AC may only
    be marked done when at least one test tagged ``# covers:<id>`` exists in the
    test tree AND every such test passes in the current pytest run.  This module
    implements ``verify_done_eligible()``, the authoritative eligibility oracle
    consumed by ``mark_ac_done.py`` and the pre-commit hook (BO-2500b-1).
ARCHITECTURE: Subprocess-invoking utility.  Scans the test tree for covers tags,
    builds an AC info map (status + covered_by) from the AC YAML store, runs
    pytest on linked test files as a subprocess, parses the ``-v`` output for
    PASSED/FAILED/XFAIL/SKIP/ERROR outcomes, and returns a structured
    eligibility verdict.

    Composite vs leaf (BO-2500a-6): an AC's own ``covered_by`` field decides
    its classification — never a hard-coded AC-id allowlist.  A COMPOSITE
    (``covered_by`` non-empty AND containing at least one id that resolves to
    a real AC record in the store) derives its proof from its children
    instead of requiring a direct ``# covers:`` tag of its own; a LEAF
    (empty/absent ``covered_by``, OR a ``covered_by`` whose entries are all
    unresolvable — e.g. legacy pre-child-id entries that hold test-file
    paths, see BO-2500a-6 remediation M-2) is unchanged and still requires
    one.

    All external I/O is wrapped per the Error Handling Policy (Rule 1).
    Pure classification helpers carry no try/except (Rule 4).

    Flow:
        verify_done_eligible(ac_id, *, ac_root, test_root) -> dict
            └── _build_ac_status_map(ac_root)
            └── _scan_test_root_for_covers_tags(test_root)
            │       └── _scan_single_test_file(py_file)
            └── _collect_dangling_tags(all_tags, ac_status_map)
            └── _collect_linked_tests(ac_id, all_tags)
            └── [no direct test] _has_resolvable_child(covered_by, ac_status_map)
            └── [no direct test + composite] _verify_composite_eligible(...)
            │       └── _resolve_all_child_ids(covered_by, ac_status_map)
            │       └── _collect_linked_tests(child_id, all_tags)
            │       └── _run_pytest_and_parse(test_files)
            │       └── _classify_outcomes(child_tests, pytest_results)
            └── [leaf] _run_pytest_and_parse(test_files)
            │       └── _parse_pytest_verbose_output(stdout)
            └── _classify_outcomes(linked_tests, pytest_results)
                    └── _find_nodeid_for_test(func_name, basename, results)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches "# covers: AC-ID" anywhere in a line, capturing the AC ID.
_COVERS_TAG_RE = re.compile(r"#\s*covers:\s*(\S+)")

# Matches a pytest -v result line: <nodeid> <OUTCOME>
# Handles relative and absolute paths including "../" prefixes.
# Outcomes: PASSED, FAILED, XFAIL, XPASS, SKIPPED, ERROR.
_PYTEST_RESULT_RE = re.compile(
    r"^(\S+::test_\w+(?:\[.*?\])?)\s+(PASSED|FAILED|XFAIL|XPASS|SKIPPED|ERROR)",
    re.MULTILINE,
)

# Matches a function definition whose name starts with "test_".
_TEST_DEF_RE = re.compile(r"^\s*def\s+(test_\w+)")


# ---------------------------------------------------------------------------
# Internal helpers — I/O layer
# ---------------------------------------------------------------------------


def _build_ac_status_map(ac_root: Path) -> dict[str, dict]:
    """Walk *ac_root* and return ``{ac_id: {"status": ..., "covered_by": [...]}}``.

    Only YAML files that can be parsed and contain both ``id`` and ``status``
    fields are included.  Unreadable files are logged to stderr and skipped.
    ``covered_by`` is retained (in addition to ``status``) so callers can
    classify an AC as composite (non-empty ``covered_by``) vs leaf (empty or
    absent) without a second store walk — see BO-2500a-6.  A ``covered_by``
    value that is absent, ``null``, or not a list is normalised to ``[]``.

    Args:
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict mapping AC id strings to a dict with keys ``"status"`` (str) and
        ``"covered_by"`` (list[str]).  An empty dict is returned when
        *ac_root* does not exist or contains no parseable YAML files.
    """
    status_map: dict[str, dict] = {}
    if not ac_root.exists():
        return status_map
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(
                f"WARNING: done_proof: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        ac_id = data.get("id")
        status = data.get("status")
        if ac_id and status is not None:
            covered_by = data.get("covered_by")
            if not isinstance(covered_by, list):
                covered_by = []
            status_map[str(ac_id)] = {
                "status": str(status),
                "covered_by": [str(child_id) for child_id in covered_by],
            }
    return status_map


def _scan_single_test_file(py_file: Path) -> list[dict]:
    """Scan one Python file for ``# covers:`` tags and associate each with its function.

    Tracks the most-recently-seen ``def test_*`` definition as the enclosing
    function for any tag found on subsequent lines.  Tags appearing before any
    ``def test_`` line are skipped (``current_function`` is None).

    Args:
        py_file: Path to the Python source file to scan.

    Returns:
        List of tag dicts with keys: ``ac_id``, ``location`` (``"<file>:<lineno>"``),
        ``function`` (Python function name), ``file`` (Path).  Empty list when
        the file cannot be read or contains no tags in a test function.
    """
    results: list[dict] = []
    try:
        with open(py_file, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(
            f"WARNING: done_proof: cannot read {py_file}: {exc}",
            file=sys.stderr,
        )
        return results
    current_function: str | None = None
    for lineno, line in enumerate(lines, 1):
        func_match = _TEST_DEF_RE.match(line)
        if func_match:
            current_function = func_match.group(1)
        tag_match = _COVERS_TAG_RE.search(line)
        if tag_match and current_function is not None:
            results.append(
                {
                    "ac_id": tag_match.group(1),
                    "location": f"{py_file}:{lineno}",
                    "function": current_function,
                    "file": py_file,
                }
            )
    return results


def _scan_test_root_for_covers_tags(test_root: Path) -> list[dict]:
    """Scan all Python files under *test_root* for ``# covers:`` tags.

    Args:
        test_root: Root directory to search recursively for ``*.py`` files.

    Returns:
        Flat list of tag dicts (one per tag found), each with keys:
        ``ac_id``, ``location``, ``function``, ``file``.
    """
    results: list[dict] = []
    try:
        py_files = sorted(test_root.rglob("*.py"))
    except OSError as exc:
        print(
            f"WARNING: done_proof: cannot scan {test_root}: {exc}",
            file=sys.stderr,
        )
        return results
    for py_file in py_files:
        results.extend(_scan_single_test_file(py_file))
    return results


def _parse_pytest_verbose_output(output: str) -> dict[str, str]:
    """Parse ``pytest -v`` stdout into a ``{nodeid: outcome}`` mapping.

    Args:
        output: Raw stdout string from a ``pytest -v`` run.

    Returns:
        Dict mapping pytest nodeid strings to their outcome strings
        (``PASSED``, ``FAILED``, ``XFAIL``, ``XPASS``, ``SKIPPED``, ``ERROR``).
    """
    return {m.group(1): m.group(2) for m in _PYTEST_RESULT_RE.finditer(output)}


def _run_pytest_and_parse(test_files: list[Path]) -> dict[str, str]:
    """Execute pytest on *test_files* and return ``{nodeid: outcome}``.

    Runs ``python -m pytest -v --tb=no --no-header`` on the given files as a
    subprocess.  The ``-v`` flag is required to produce per-test outcome lines;
    exit code alone cannot distinguish XFAIL/SKIP from PASSED.

    Args:
        test_files: Absolute paths to Python test files to execute.

    Returns:
        Dict mapping pytest nodeid strings to outcome strings.  Returns an
        empty dict when *test_files* is empty or the subprocess cannot be
        started.
    """
    if not test_files:
        return {}
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=no", "--no-header"]
    cmd.extend(str(f) for f in test_files)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"WARNING: done_proof: pytest timed out after 60 s: {exc}",
            file=sys.stderr,
        )
        return {}
    except OSError as exc:
        print(
            f"WARNING: done_proof: cannot run pytest: {exc}",
            file=sys.stderr,
        )
        return {}
    return _parse_pytest_verbose_output(proc.stdout)


# ---------------------------------------------------------------------------
# Internal helpers — pure classification layer (no I/O, no try/except)
# ---------------------------------------------------------------------------


def _collect_dangling_tags(
    all_tags: list[dict],
    ac_status_map: dict[str, dict],
) -> list[dict]:
    """Return one entry per dangling covers tag (non-active or nonexistent AC id).

    A tag is dangling when its ``ac_id`` is absent from *ac_status_map* (no YAML
    file found for that id) or when the resolved status is not ``"active"``.

    Args:
        all_tags: All covers tag dicts produced by the scanner.
        ac_status_map: Mapping ``{ac_id: {"status": ..., "covered_by": [...]}}``
            from the AC store.

    Returns:
        List of ``{"id": str, "location": str}`` dicts, one per unique dangling id
        (first occurrence's location is used when the same id appears multiple times).
    """
    seen: set[str] = set()
    dangling: list[dict] = []
    for tag in all_tags:
        tag_id = tag["ac_id"]
        if tag_id in seen:
            continue
        info = ac_status_map.get(tag_id)
        status = info.get("status") if info else None
        if status is None or status != "active":
            dangling.append({"id": tag_id, "location": tag["location"]})
            seen.add(tag_id)
    return dangling


def _collect_linked_tests(ac_id: str, all_tags: list[dict]) -> list[dict]:
    """Return the subset of *all_tags* whose ``ac_id`` matches the queried id.

    Args:
        ac_id: The AC identifier to look for.
        all_tags: All covers tag dicts produced by the scanner.

    Returns:
        List of tag dicts where ``tag["ac_id"] == ac_id``.
    """
    return [t for t in all_tags if t["ac_id"] == ac_id]


def _has_resolvable_child(covered_by: list[str], ac_status_map: dict[str, dict]) -> bool:
    """Return whether at least one entry of *covered_by* resolves to a real AC.

    BO-2500a-6 remediation M-2: legacy ACs written before the child-id
    convention hold TEST FILE PATHS in ``covered_by`` (e.g.
    ``['tests/test_skill_registry.py']``) rather than child AC ids. None of
    those entries resolve to a record in *ac_status_map*, so such an AC must
    be classified as a LEAF (falling back to the direct-linked-test
    requirement) rather than a COMPOSITE with phantom "uncovered children".
    The classification is data-driven — it never hard-codes an AC-id
    allowlist — it simply checks store resolvability.

    Args:
        covered_by: The AC's own ``covered_by`` list (may be empty, may hold
            AC ids, legacy test-file path strings, or a mix).
        ac_status_map: Mapping ``{ac_id: {"status": ..., "covered_by": [...]}}``
            from the AC store.

    Returns:
        ``True`` iff at least one entry of *covered_by* is a key in
        *ac_status_map* (i.e. resolves to a real AC record).
    """
    return any(entry in ac_status_map for entry in covered_by)


def _resolve_all_child_ids(
    covered_by: list[str],
    ac_status_map: dict[str, dict],
    _seen: set[str] | None = None,
) -> list[str]:
    """Flatten a composite's ``covered_by`` tree into its leaf descendant ids.

    A child that is itself a composite (its own ``covered_by`` is non-empty)
    is expanded recursively rather than treated as a leaf requiring a direct
    test — only leaf descendants (empty/absent ``covered_by``) need their own
    covers-tagged test.  Cycles are broken defensively via *_seen* (a
    malformed store could otherwise recurse forever); a child id already
    visited is not expanded a second time.

    A *covered_by* entry that does not resolve to a real AC record in
    *ac_status_map* (BO-2500a-6 remediation M-2 — e.g. a legacy test-file
    path string predating the child-id convention) is skipped entirely: it
    is neither a leaf requiring its own covers-tagged test nor a composite to
    expand, since it is not a store-resolvable AC id at all.  Callers decide
    whether to classify the AC itself as composite via
    :func:`_has_resolvable_child` before calling this function.

    Args:
        covered_by: The composite's own list of direct child AC ids.
        ac_status_map: Mapping ``{ac_id: {"status": ..., "covered_by": [...]}}``
            from the AC store, used to look up each child's own ``covered_by``.
        _seen: Internal recursion guard; callers should omit this argument.

    Returns:
        List of leaf AC id strings reachable from *covered_by*, in traversal
        order with duplicates removed by the cycle guard.  Unresolvable
        entries contribute nothing to the result.
    """
    seen = _seen if _seen is not None else set()
    leaf_ids: list[str] = []
    for child_id in covered_by:
        if child_id in seen:
            continue
        seen.add(child_id)
        child_info = ac_status_map.get(child_id)
        if child_info is None:
            continue  # unresolvable entry (e.g. legacy test-file path) — skip
        child_covered_by = child_info.get("covered_by", [])
        if child_covered_by:
            leaf_ids.extend(_resolve_all_child_ids(child_covered_by, ac_status_map, seen))
        else:
            leaf_ids.append(child_id)
    return leaf_ids


def _find_nodeid_for_test(
    func_name: str,
    file_basename: str,
    pytest_results: dict[str, str],
) -> str | None:
    """Find the pytest nodeid for a function, preferring a match in the expected file.

    Attempts an exact file-basename + function-name match first, then falls back
    to function-name suffix only.

    Args:
        func_name: Python function name (e.g. ``"test_foo"``).
        file_basename: Basename of the test file (e.g. ``"test_foo.py"``).
        pytest_results: Dict of ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        A matching nodeid string, or ``None`` if no match is found.
    """
    suffix = f"::{func_name}"
    for nodeid in pytest_results:
        if nodeid.endswith(suffix) and file_basename in nodeid:
            return nodeid
    for nodeid in pytest_results:
        if nodeid.endswith(suffix):
            return nodeid
    return None


def _classify_outcomes(
    linked_tests: list[dict],
    pytest_results: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Split linked tests into passing and non-passing nodeid lists.

    Only ``PASSED`` counts as passing.  ``XFAIL``, ``XPASS``, ``SKIPPED``,
    ``FAILED``, and ``ERROR`` all count as non-passing (fail-closed).  A test
    whose nodeid cannot be located in *pytest_results* is treated as non-passing.

    Args:
        linked_tests: Tag dicts for the queried AC id (from ``_collect_linked_tests``).
        pytest_results: ``{nodeid: outcome}`` dict from ``_run_pytest_and_parse``.

    Returns:
        ``(passing_nodeids, failing_nodeids)`` tuple of pytest nodeid string lists.
    """
    passing: list[str] = []
    failing: list[str] = []
    for test in linked_tests:
        func_name = test["function"]
        file_basename = Path(test["file"]).name
        matched = _find_nodeid_for_test(func_name, file_basename, pytest_results)
        if matched is None:
            # Could not locate result — treat as non-passing (fail-closed).
            failing.append(f"{test['file']}::{func_name}")
            continue
        if pytest_results[matched] == "PASSED":
            passing.append(matched)
        else:
            failing.append(matched)
    return passing, failing


# ---------------------------------------------------------------------------
# Internal helpers — composite eligibility layer (I/O via _run_pytest_and_parse)
# ---------------------------------------------------------------------------


def _verify_composite_eligible(
    ac_id: str,
    covered_by: list[str],
    *,
    ac_status_map: dict[str, dict],
    all_tags: list[dict],
    dangling_tags: list[dict],
) -> dict:
    """Derive a composite AC's eligibility verdict from its covered children.

    Per BO-2500a-6, a composite (an AC whose own ``covered_by`` is non-empty)
    does NOT require a direct ``# covers:`` tag of its own — its proof of
    done is derived from its children instead.  It is satisfied when every
    leaf descendant reachable through *covered_by* (see
    :func:`_resolve_all_child_ids`, which also handles a child that is
    itself a composite) has at least one covers-tagged test and every such
    test passes.  A child with zero linked tests makes the composite
    ineligible — the exemption only removes the requirement for the
    composite's OWN id, it does not let an uncovered child pass silently.

    Args:
        ac_id: The composite AC's own identifier (used only for the reason
            string; its id is never looked up in *all_tags*).
        covered_by: The composite's direct child AC ids (already known
            non-empty by the caller).
        ac_status_map: Mapping ``{ac_id: {"status": ..., "covered_by": [...]}}``
            from the AC store.
        all_tags: All covers tag dicts produced by the scanner.
        dangling_tags: Dangling-tag entries computed once by the caller,
            passed through unchanged (composite resolution does not add or
            remove dangling tags).

    Returns:
        A verdict dict with the same shape as :func:`verify_done_eligible`.
    """
    leaf_child_ids = _resolve_all_child_ids(covered_by, ac_status_map)
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
        child_id for child_id, tests in per_child_tests.items() if not tests
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

    all_child_tests = [test for tests in per_child_tests.values() for test in tests]
    test_files = list({t["file"] for t in all_child_tests})
    pytest_results = _run_pytest_and_parse(test_files)

    passing_tests: list[str] = []
    failing_tests: list[str] = []
    for tests in per_child_tests.values():
        child_passing, child_failing = _classify_outcomes(tests, pytest_results)
        passing_tests.extend(child_passing)
        failing_tests.extend(child_failing)

    if failing_tests:
        reasons = [
            f"linked test {pytest_results.get(nid, 'non-passing').lower()}: {nid}"
            for nid in failing_tests
        ]
        return {
            "eligible": False,
            "reason": "; ".join(reasons),
            "passing_tests": passing_tests,
            "failing_tests": failing_tests,
            "dangling_tags": dangling_tags,
        }

    return {
        "eligible": True,
        "reason": "",
        "passing_tests": passing_tests,
        "failing_tests": [],
        "dangling_tags": dangling_tags,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_done_eligible(
    ac_id: str,
    *,
    ac_root: Path,
    test_root: Path,
) -> dict:
    """Check whether *ac_id* is eligible to be marked done via covers-tag linkage.

    An AC is eligible when:

    * At least one test tagged ``# covers: <ac_id>`` exists anywhere under
      *test_root*, AND
    * Every such test produces a ``PASSED`` outcome in the current pytest run.

    ``XFAIL``, ``XPASS``, ``SKIPPED``, ``FAILED``, and ``ERROR`` outcomes all
    count as non-passing, preventing xfail-masking from silently satisfying
    the done gate.

    Also scans *test_root* for ``# covers:`` tags whose target id is not an
    active AC in *ac_root* (deprecated, superseded, or nonexistent) and reports
    them as dangling.

    Composite exemption (BO-2500a-6): when *ac_id* has no direct linked test
    but its own ``covered_by`` field (read from *ac_root*) contains at least
    one id that resolves to a real AC record in the store, it is classified
    as a COMPOSITE and its eligibility is derived from its covered children
    instead — see :func:`_verify_composite_eligible`. An AC with an
    empty/absent ``covered_by``, OR a ``covered_by`` whose entries are all
    unresolvable (BO-2500a-6 remediation M-2 — legacy ACs predating the
    child-id convention hold test-file paths there instead of child ids), is
    a LEAF and is unaffected: it still requires its own direct linked test
    exactly as before, with the original ``"no linked test found"`` message.

    Args:
        ac_id: The AC identifier string to evaluate.
        ac_root: Root directory of the AC YAML store, used for active-status
            resolution (``status: active`` required to count).
        test_root: Root directory to scan recursively for ``*.py`` test files
            containing ``# covers:`` tags.

    Returns:
        A dict with keys:

        ``eligible`` (bool)
            ``True`` iff at least one covers-linked test exists and every such
            test passes.

        ``reason`` (str)
            Empty string when ``eligible`` is ``True``; a human-readable
            explanation otherwise, naming the AC id and the specific cause
            (missing test, failing test nodeid, etc.).

        ``passing_tests`` (list[str])
            pytest nodeids of covers-linked tests that passed.

        ``failing_tests`` (list[str])
            pytest nodeids of covers-linked tests that were not passing.

        ``dangling_tags`` (list[dict])
            ``{"id": str, "location": str}`` entries for covers tags found
            anywhere in *test_root* that point at non-active or nonexistent ACs.
    """
    ac_status_map = _build_ac_status_map(ac_root)
    all_tags = _scan_test_root_for_covers_tags(test_root)
    dangling_tags = _collect_dangling_tags(all_tags, ac_status_map)
    linked_tests = _collect_linked_tests(ac_id, all_tags)

    if not linked_tests:
        ac_info = ac_status_map.get(ac_id)
        covered_by = ac_info.get("covered_by", []) if ac_info else []
        if _has_resolvable_child(covered_by, ac_status_map):
            return _verify_composite_eligible(
                ac_id,
                covered_by,
                ac_status_map=ac_status_map,
                all_tags=all_tags,
                dangling_tags=dangling_tags,
            )
        return {
            "eligible": False,
            "reason": f"no linked test found for {ac_id}",
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    test_files = list({t["file"] for t in linked_tests})
    pytest_results = _run_pytest_and_parse(test_files)
    passing_tests, failing_tests = _classify_outcomes(linked_tests, pytest_results)

    if failing_tests:
        reasons = [
            f"linked test {pytest_results.get(nid, 'non-passing').lower()}: {nid}"
            for nid in failing_tests
        ]
        return {
            "eligible": False,
            "reason": "; ".join(reasons),
            "passing_tests": passing_tests,
            "failing_tests": failing_tests,
            "dangling_tags": dangling_tags,
        }

    return {
        "eligible": True,
        "reason": "",
        "passing_tests": passing_tests,
        "failing_tests": [],
        "dangling_tags": dangling_tags,
    }
