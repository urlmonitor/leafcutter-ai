"""
MODULE: done_proof
GOAL: Verify that an AC is eligible to be marked done based on covers-tag linkage.
BUSINESS CONTEXT: Part of the BO-2500 mechanical done-proof gate.  An AC may only
    be marked done when at least one test tagged ``# covers:<id>`` (Python) or
    ``// covers:<id>`` (TypeScript/JavaScript) exists in the test tree AND every
    such test passes in the current pytest / vitest run.  This module implements
    ``verify_done_eligible()``, the authoritative eligibility oracle consumed by
    ``mark_ac_done.py`` and the pre-commit hook (BO-2500b-1).
ARCHITECTURE: Subprocess-invoking utility.  Scans the test tree for covers tags
    (both Python ``# covers:`` and TypeScript ``// covers:`` via the shared
    COVERS_TAG_RE seam from test_enforcement), builds an AC status map from the AC
    YAML store, runs pytest on linked .py test files and vitest on linked .ts/.tsx
    test files as subprocesses, parses results, and returns a structured eligibility
    verdict.

    JS runner seam (BO-2500e-2):
        run_vitest_and_parse(test_files, *, project_dir) -> dict[str, str]
        Returns {<abs-path-str>: "PASSED" | "FAILED"} per file.
        Raises JsRunnerUnavailable when vitest cannot be launched.
        In verify_done_eligible this seam is called ONCE (batched) for all
        linked .ts/.tsx files when ≥1 exists; Python-only ACs never invoke it.

    Directory exclusions (BO-2500e):
        Both .py and .ts/.tsx scanning exclude node_modules, .next, dist,
        coverage, .git, __pycache__, and .venv from recursive traversal so
        that a repo-root test_root does not traverse thousands of JS files.

    All external I/O is wrapped per the Error Handling Policy (Rule 1).
    Pure classification helpers carry no try/except (Rule 4).

    Flow:
        verify_done_eligible(ac_id, *, ac_root, test_root) -> dict
            └── _build_ac_status_map(ac_root)
            └── _scan_test_root_for_covers_tags(test_root)
            │       └── _scan_single_test_file(py_file)      [.py]
            │       └── _scan_single_ts_file(ts_file)         [.ts/.tsx]
            └── _collect_dangling_tags(all_tags, ac_status_map)
            └── _collect_linked_tests(ac_id, all_tags)
            └── [py path] _run_pytest_and_parse(py_files)
            │                └── _parse_pytest_verbose_output(stdout)
            │            _classify_outcomes(py_linked, pytest_results)
            │                    └── _find_nodeid_for_test(func, basename, results)
            └── [ts path] run_vitest_and_parse(ts_files, project_dir=…)
                         _discover_project_dir(ts_files) → project_dir
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

# Import the single shared covers-tag seam (BO-2500e-1).
# test_enforcement lazily imports done_proof inside a function body,
# so this top-level import does NOT create a circular dependency.
from test_enforcement import COVERS_TAG_RE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches a pytest -v result line: <nodeid> <OUTCOME>
# Handles relative and absolute paths including "../" prefixes.
# Outcomes: PASSED, FAILED, XFAIL, XPASS, SKIPPED, ERROR.
_PYTEST_RESULT_RE = re.compile(
    r"^(\S+::test_\w+(?:\[.*?\])?)\s+(PASSED|FAILED|XFAIL|XPASS|SKIPPED|ERROR)",
    re.MULTILINE,
)

# Matches a function definition whose name starts with "test_".
_TEST_DEF_RE = re.compile(r"^\s*def\s+(test_\w+)")

# Directory names excluded from ALL test-file scanning (.py AND .ts/.tsx).
# Prevents traversing node_modules and other non-test subtrees.
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


# ---------------------------------------------------------------------------
# JS runner seam
# ---------------------------------------------------------------------------


class JsRunnerUnavailable(Exception):
    """Raised by run_vitest_and_parse when vitest cannot be invoked.

    Distinct from a test failure: this exception means the runner itself
    could not start (missing binary, OS error on launch).  A test run that
    starts but reports failures is a normal FAILED result, not this exception.
    """


def _discover_project_dir(ts_files: list[Path]) -> Path:
    """Find the nearest ancestor directory of *ts_files* containing vitest config.

    Walks upward from each file's parent, returning the first directory that
    contains ``vitest.config.ts`` (preferred) or ``package.json`` (fallback).
    If no such ancestor is found, returns the parent of the first file.

    Args:
        ts_files: List of TypeScript test file paths.

    Returns:
        Directory to use as ``cwd`` / ``project_dir`` for the vitest invocation.
    """
    for ts_file in ts_files:
        candidate = ts_file.parent
        while True:
            if (candidate / "vitest.config.ts").exists():
                return candidate
            if (candidate / "package.json").exists():
                return candidate
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
    return ts_files[0].parent if ts_files else Path.cwd()


def run_vitest_and_parse(
    test_files: list[Path],
    *,
    project_dir: Path,
) -> dict[str, str]:
    """Invoke vitest scoped to *test_files* and parse per-file outcomes.

    Runs ``<project_dir>/node_modules/.bin/vitest run <files> --reporter=json``
    with ``cwd=project_dir``, captures stdout, and parses the JSON output into
    a per-file ``{<absolute-path-str>: "PASSED" | "FAILED"}`` mapping.

    A file is ``"PASSED"`` iff its file-level result in the JSON output is
    ``"passed"`` with no failing assertions.  Any other status — or absence
    from the JSON output — is mapped to ``"FAILED"`` (fail-closed).

    Args:
        test_files: Absolute paths of TypeScript test files to run.
        project_dir: Directory that owns ``node_modules/.bin/vitest`` and
            ``vitest.config.ts`` (or ``package.json``).  Used as the subprocess
            ``cwd``.

    Returns:
        Dict mapping absolute file path strings to ``"PASSED"`` or ``"FAILED"``.
        Every path in *test_files* appears exactly once in the returned dict.

    Raises:
        JsRunnerUnavailable: When the vitest binary is missing, the executable
            cannot be found by the OS (``FileNotFoundError``), or the subprocess
            raises ``OSError`` at launch time.  A run that starts but reports
            failures is NOT this exception — that is a normal ``"FAILED"`` result.
    """
    if not test_files:
        return {}

    # Resolve to absolute BEFORE launching. The subprocess runs with
    # cwd=project_dir, so a relative binary path or a relative test-file path
    # would be re-resolved against that new cwd (yielding e.g.
    # "leafcutter-web/leafcutter-web/node_modules/.bin/vitest") and fail. The CI
    # done-proof gate runs from the repository root with relative paths, so this
    # is the normal case there, not an edge case.
    project_dir_abs = project_dir.resolve()

    # Map the caller's path spelling -> its absolute form. The returned dict is
    # keyed by the ORIGINAL spelling so callers can look results up by the same
    # path object they passed in.
    abs_by_original: dict[str, str] = {
        str(f): str(Path(f).resolve()) for f in test_files
    }

    vitest_bin = project_dir_abs / "node_modules" / ".bin" / "vitest"
    if not vitest_bin.exists():
        raise JsRunnerUnavailable(
            f"vitest binary not found: {vitest_bin}; ensure node_modules is installed"
        )

    cmd = [str(vitest_bin), "run", "--reporter=json"]
    cmd.extend(abs_by_original[str(f)] for f in test_files)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_dir_abs),
        )
    except FileNotFoundError as exc:
        raise JsRunnerUnavailable(
            f"vitest binary not invokable (FileNotFoundError): {exc}"
        ) from exc
    except OSError as exc:
        raise JsRunnerUnavailable(
            f"vitest OS error on launch: {exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        print(
            f"WARNING: done_proof: vitest timed out after 120 s: {exc}",
            file=sys.stderr,
        )
        return {str(f): "FAILED" for f in test_files}

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(
            f"WARNING: done_proof: vitest JSON parse error: {exc}",
            file=sys.stderr,
        )
        return {str(f): "FAILED" for f in test_files}

    # Build a path → outcome map from the JSON testResults array.
    # Vitest/Jest JSON reporter uses "testFilePath" or "name" for the file path
    # and "status" for the per-suite outcome ("passed" | "failed").
    raw_results: dict[str, str] = {}
    for item in data.get("testResults", []):
        file_path = (
            item.get("testFilePath")
            or item.get("file")
            or item.get("name")
            or ""
        )
        if not file_path:
            continue
        status = str(item.get("status", "failed")).lower()
        # Vitest reports absolute paths; normalise so lookups match the absolute
        # forms computed above regardless of how the caller spelled them.
        raw_results[str(Path(file_path).resolve())] = (
            "PASSED" if status == "passed" else "FAILED"
        )

    # Fail-closed: any requested file absent from JSON output → FAILED.
    # Keyed by the caller's original path spelling; matched by absolute path.
    return {
        str(f): raw_results.get(abs_by_original[str(f)], "FAILED") for f in test_files
    }


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


def _is_excluded_path(path: Path) -> bool:
    """Return True when any component of *path* is an excluded scan directory.

    Checks every part of the absolute path against *_EXCLUDED_SCAN_DIRS*.
    This prevents scanning into node_modules, .next, dist, coverage, .git,
    __pycache__, and .venv subtrees.

    Args:
        path: Absolute path to a candidate test file.

    Returns:
        True when any path component matches an excluded directory name.
    """
    return any(part in _EXCLUDED_SCAN_DIRS for part in path.parts)


def _scan_single_test_file(py_file: Path) -> list[dict]:
    """Scan one Python file for ``# covers:`` tags and associate each with its function.

    Tracks the most-recently-seen ``def test_*`` definition as the enclosing
    function for any tag found on subsequent lines.  Tags appearing before any
    ``def test_`` line are skipped (``current_function`` is None).

    Uses the shared :data:`~test_enforcement.COVERS_TAG_RE` seam so both
    Python ``# covers:`` and JavaScript ``// covers:`` syntax are recognised
    (though only ``#`` style appears in real Python source).

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
        tag_match = COVERS_TAG_RE.search(line)
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


def _scan_single_ts_file(ts_file: Path) -> list[dict]:
    """Scan one TypeScript/TSX file for ``// covers:`` tags.

    Unlike Python scanning, there is no ``def test_`` enclosing function
    requirement.  Every ``// covers: <id>`` (or ``# covers: <id>``) tag on
    any line is collected and associated with the file itself (``function``
    is ``None``).  Uses the shared :data:`~test_enforcement.COVERS_TAG_RE`
    seam (BO-2500e-1).

    Args:
        ts_file: Path to the TypeScript or TSX source file to scan.

    Returns:
        List of tag dicts with keys: ``ac_id``, ``location`` (``"<file>:<lineno>"``),
        ``function`` (``None``), ``file`` (Path).  Empty list when the file
        cannot be read or contains no covers tags.
    """
    results: list[dict] = []
    try:
        with open(ts_file, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(
            f"WARNING: done_proof: cannot read {ts_file}: {exc}",
            file=sys.stderr,
        )
        return results
    for lineno, line in enumerate(lines, 1):
        tag_match = COVERS_TAG_RE.search(line)
        if tag_match:
            results.append(
                {
                    "ac_id": tag_match.group(1),
                    "location": f"{ts_file}:{lineno}",
                    "function": None,
                    "file": ts_file,
                }
            )
    return results


def _scan_test_root_for_covers_tags(test_root: Path) -> list[dict]:
    """Scan all test files under *test_root* for covers tags.

    Scans both Python (``*.py``) and TypeScript/TSX (``*.ts``, ``*.tsx``) files.
    Excluded directories (``node_modules``, ``.next``, ``dist``, ``coverage``,
    ``.git``, ``__pycache__``, ``.venv``) are skipped so that a repo-root
    *test_root* does not traverse thousands of non-test files.

    Args:
        test_root: Root directory to search recursively for test files.

    Returns:
        Flat list of tag dicts (one per tag found), each with keys:
        ``ac_id``, ``location``, ``function``, ``file``.
    """
    results: list[dict] = []
    try:
        py_files = sorted(test_root.rglob("*.py"))
        ts_files = sorted(test_root.rglob("*.ts"))
        tsx_files = sorted(test_root.rglob("*.tsx"))
    except OSError as exc:
        print(
            f"WARNING: done_proof: cannot scan {test_root}: {exc}",
            file=sys.stderr,
        )
        return results
    for py_file in py_files:
        if not _is_excluded_path(py_file):
            results.extend(_scan_single_test_file(py_file))
    for ts_file in list(ts_files) + list(tsx_files):
        if not _is_excluded_path(ts_file):
            results.extend(_scan_single_ts_file(ts_file))
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
    """Split linked Python tests into passing and non-passing nodeid lists.

    Only ``PASSED`` counts as passing.  ``XFAIL``, ``XPASS``, ``SKIPPED``,
    ``FAILED``, and ``ERROR`` all count as non-passing (fail-closed).  A test
    whose nodeid cannot be located in *pytest_results* is treated as non-passing.

    Args:
        linked_tests: Tag dicts for the queried AC id (from ``_collect_linked_tests``),
            filtered to Python (.py) tests only.
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

    * At least one test tagged ``# covers: <ac_id>`` (Python) or
      ``// covers: <ac_id>`` (TypeScript/JavaScript) exists anywhere under
      *test_root*, AND
    * Every such test produces a ``PASSED`` outcome in the current pytest / vitest run.

    Python tests are run via ``pytest -v``; TypeScript/TSX tests are run via
    ``run_vitest_and_parse`` (BO-2500e-2).  Both must pass when linked tests of
    both kinds exist.

    When only Python tests are linked, the JS runner is **not invoked at all**
    (BO-2500e-4-i).  When ≥1 .ts/.tsx test is linked, ``run_vitest_and_parse`` is
    called exactly once with all linked TS files batched together.

    ``JsRunnerUnavailable`` (missing vitest binary, OS launch error) causes
    ``eligible=False`` with a reason naming the unavailability — the oracle fails
    CLOSED (BO-2500e-3-i).

    ``XFAIL``, ``XPASS``, ``SKIPPED``, ``FAILED``, and ``ERROR`` pytest outcomes
    count as non-passing, preventing xfail-masking from satisfying the gate.

    Also scans *test_root* for covers tags whose target id is not an active AC in
    *ac_root* (deprecated, superseded, or nonexistent) and reports them as dangling.
    Dangling detection now includes ``.ts``/``.tsx`` covers tags (BO-2500e-1).

    Args:
        ac_id: The AC identifier string to evaluate.
        ac_root: Root directory of the AC YAML store, used for active-status
            resolution (``status: active`` required to count).
        test_root: Root directory to scan recursively for test files containing
            covers tags (both ``*.py`` and ``*.ts``/``*.tsx``).

    Returns:
        A dict with keys:

        ``eligible`` (bool)
            ``True`` iff at least one covers-linked test exists and every such
            test passes (in all languages).

        ``reason`` (str)
            Empty string when ``eligible`` is ``True``; a human-readable
            explanation otherwise, naming the AC id and the specific cause
            (missing test, failing test nodeid, etc.).

        ``passing_tests`` (list[str])
            nodeids / file paths of covers-linked tests that passed.

        ``failing_tests`` (list[str])
            nodeids / file paths of covers-linked tests that were not passing.

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

    # Split linked tests by language: .py → pytest path; .ts/.tsx → vitest path.
    py_linked = [t for t in linked_tests if Path(t["file"]).suffix == ".py"]
    ts_linked = [
        t for t in linked_tests if Path(t["file"]).suffix in (".ts", ".tsx")
    ]

    # --- Python path ---
    py_passing: list[str] = []
    py_failing: list[str] = []
    if py_linked:
        py_files = list({t["file"] for t in py_linked})
        pytest_results = _run_pytest_and_parse(py_files)
        py_passing, py_failing = _classify_outcomes(py_linked, pytest_results)

    # --- TypeScript/JavaScript path (BO-2500e-2 / BO-2500e-4-i) ---
    # Only invoked when ≥1 linked .ts/.tsx test exists.
    ts_passing: list[str] = []
    ts_failing: list[str] = []
    if ts_linked:
        ts_files_unique = list({t["file"] for t in ts_linked})
        project_dir = _discover_project_dir(ts_files_unique)
        try:
            vitest_results = run_vitest_and_parse(
                ts_files_unique, project_dir=project_dir
            )
        except JsRunnerUnavailable as exc:
            return {
                "eligible": False,
                "reason": (
                    f"JS runner unavailable for {ac_id}: {exc}"
                ),
                "passing_tests": py_passing,
                "failing_tests": [],
                "dangling_tags": dangling_tags,
            }
        # Map each linked .ts file to its vitest outcome (fail-closed if absent).
        seen_ts_files: set[str] = set()
        for t in ts_linked:
            f_str = str(t["file"])
            if f_str in seen_ts_files:
                continue
            seen_ts_files.add(f_str)
            outcome = vitest_results.get(f_str, "FAILED")
            if outcome == "PASSED":
                ts_passing.append(f_str)
            else:
                ts_failing.append(f_str)

    # --- Combine and classify ---
    passing_tests = py_passing + ts_passing
    failing_tests = py_failing + ts_failing

    if failing_tests:
        reason_parts: list[str] = []
        if py_failing:
            for nid in py_failing:
                # Keep existing pytest reason format for .py tests
                reason_parts.append(f"linked test non-passing: {nid}")
        if ts_failing:
            ts_names = ", ".join(ts_failing)
            reason_parts.append(
                f"JS test(s) failed for {ac_id}: {ts_names}"
            )
        return {
            "eligible": False,
            "reason": "; ".join(reason_parts),
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
