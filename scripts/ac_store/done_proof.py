"""
MODULE: done_proof
GOAL: Verify that an AC is eligible to be marked done based on covers-tag linkage.
BUSINESS CONTEXT: Part of the BO-2500 mechanical done-proof gate.  An AC may only
    be marked done when at least one test tagged ``# covers:<id>`` exists in the
    test tree AND every such test passes in the current pytest run.  This module
    implements ``verify_done_eligible()``, the authoritative eligibility oracle
    consumed by ``mark_ac_done.py`` and the pre-commit hook (BO-2500b-1).
ARCHITECTURE: Subprocess-invoking utility.  Scans the test tree for covers tags,
    builds an AC status map from the AC YAML store, runs pytest on linked test
    files as a subprocess, parses the ``-v`` output for PASSED/FAILED/XFAIL/SKIP/
    ERROR outcomes, and returns a structured eligibility verdict.

    All external I/O is wrapped per the Error Handling Policy (Rule 1).
    Pure classification helpers carry no try/except (Rule 4).

    Flow:
        verify_done_eligible(ac_id, *, ac_root, test_root) -> dict
            └── _build_ac_status_map(ac_root)
            └── _scan_test_root_for_covers_tags(test_root)
            │       └── _scan_single_test_file(py_file)
            └── _collect_dangling_tags(all_tags, ac_status_map)
            └── _collect_linked_tests(ac_id, all_tags)
            └── _run_pytest_and_parse(test_files)
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


def _build_ac_status_map(ac_root: Path) -> dict[str, str]:
    """Walk *ac_root* and return ``{ac_id: status}`` for active-status resolution.

    Only YAML files that can be parsed and contain both ``id`` and ``status``
    fields are included.  Unreadable files are logged to stderr and skipped.

    Args:
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict mapping AC id strings to their ``status`` field value.  An empty
        dict is returned when *ac_root* does not exist or contains no parseable
        YAML files.
    """
    status_map: dict[str, str] = {}
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
            status_map[str(ac_id)] = str(status)
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
    ac_status_map: dict[str, str],
) -> list[dict]:
    """Return one entry per dangling covers tag (non-active or nonexistent AC id).

    A tag is dangling when its ``ac_id`` is absent from *ac_status_map* (no YAML
    file found for that id) or when the resolved status is not ``"active"``.

    Args:
        all_tags: All covers tag dicts produced by the scanner.
        ac_status_map: Mapping ``{ac_id: status}`` from the AC store.

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
        status = ac_status_map.get(tag_id)
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
