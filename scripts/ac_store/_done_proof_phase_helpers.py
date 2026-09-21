"""
MODULE: _done_proof_phase_helpers
GOAL: Sibling extraction of done_proof.py's already-decomposed private
    orchestration helpers, so done_proof.py itself fits back under the
    repository's file-size ratchet.
BUSINESS CONTEXT: BP-100n-4-ii. A previous pass (see done_proof.py's own
    DECISION HISTORY, 2026-09-14) reduced verify_done_eligible() and
    run_vitest_and_parse() to low-complexity orchestration bodies by
    extracting their branches into small, independently testable private
    helpers -- but decomposing IN PLACE added ~131 counted lines of new
    signatures and docstrings to a file that was already over its 1347-line
    ratchet baseline (scripts/commit_guardian/check_file_size.py), which
    refuses any further growth of an already-oversized file. This module
    moves those already-extracted helpers to a sibling file rather than
    undoing the complexity fix: a PURE relocation, not a rewrite. Every
    verdict, message string, and exit code is unchanged from the inline code
    these helpers replaced before BP-100n-4's first pass.
ARCHITECTURE: Two independent helper groups, moved verbatim from
    done_proof.py:

    JS runner seam internals (used by ``done_proof.run_vitest_and_parse``,
    which stays in done_proof.py as public API):
        _build_abs_path_map, _ensure_vitest_binary, _build_vitest_command,
        _execute_vitest, _parse_vitest_stdout, _build_raw_results_from_json

    ``verify_done_eligible`` orchestration layer (used by
    ``done_proof.verify_done_eligible``, which stays in done_proof.py as
    public API):
        _split_linked_tests_by_language, _handle_no_direct_tests,
        _maybe_reachability_verdict, _run_python_test_phase,
        _run_ts_test_phase, _classify_ts_outcomes, _build_failure_reason

    CIRCULAR-IMPORT NOTE: done_proof.py imports this module's helpers at
    TOP LEVEL (its two call sites -- run_vitest_and_parse and
    verify_done_eligible -- need them). This module's own helpers call BACK
    into done_proof.py for the classification/IO primitives that stayed
    behind (JsRunnerUnavailable, run_vitest_and_parse, _discover_project_dir,
    _run_pytest_and_parse, _pytest_incomplete_run_reason, _classify_outcomes,
    _has_resolvable_child, _verify_composite_eligible,
    _check_reachability_for_linked_tests, _describe_non_passing). A
    top-level ``from done_proof import ...`` on THIS side would deadlock the
    import: done_proof imports this module before it finishes its own
    definitions, so this module would then be importing a done_proof that
    has not finished loading yet. Each function below instead does its
    ``from done_proof import ...`` LOCALLY, inside its own body -- the same
    lazy-import seam done_proof.py's own module docstring already documents
    for test_enforcement.py's reverse dependency on done_proof. By the time
    any of these functions actually RUNS, done_proof has finished loading
    (both modules are only ever driven through done_proof.verify_done_eligible
    / done_proof.run_vitest_and_parse, never through a bare call into this
    module at import time), so the local import always succeeds regardless
    of which of the two modules a caller happens to import first.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# JS runner seam internals (BP-100n-4-ii relocation from done_proof.py --
# pure move, no behaviour change; see done_proof.py's own DECISION HISTORY,
# 2026-09-14, for the original extraction that produced these helpers)
# ---------------------------------------------------------------------------


def _build_abs_path_map(test_files: list[Path]) -> dict[str, str]:
    """Map each caller-supplied test file path to its resolved absolute form.

    BP-100n-4 extraction from :func:`done_proof.run_vitest_and_parse` (pure
    refactor — no behaviour change). The returned dict is keyed by the
    ORIGINAL spelling so callers can look results up by the same path object
    they passed in, regardless of the subprocess's ``cwd``.

    Args:
        test_files: Test file paths as supplied by the caller (may be
            relative or absolute).

    Returns:
        Dict mapping ``str(f)`` (original spelling) to ``str(Path(f).resolve())``.
    """
    return {str(f): str(Path(f).resolve()) for f in test_files}


def _ensure_vitest_binary(vitest_bin: Path) -> None:
    """Raise when *vitest_bin* does not exist on disk.

    BP-100n-4 extraction from :func:`done_proof.run_vitest_and_parse` (pure
    refactor — no behaviour change).

    Args:
        vitest_bin: Expected path to the vitest executable under
            ``<project_dir>/node_modules/.bin/vitest``.

    Raises:
        JsRunnerUnavailable: When *vitest_bin* is not a file.
    """
    from done_proof import JsRunnerUnavailable

    if not vitest_bin.exists():
        raise JsRunnerUnavailable(
            f"vitest binary not found: {vitest_bin}; ensure node_modules is installed"
        )


def _build_vitest_command(
    vitest_bin: Path, abs_by_original: dict[str, str], test_files: list[Path]
) -> list[str]:
    """Build the vitest CLI invocation for *test_files*.

    BP-100n-4 extraction from :func:`done_proof.run_vitest_and_parse` (pure
    refactor — no behaviour change).

    Args:
        vitest_bin: Resolved path to the vitest executable.
        abs_by_original: ``{original-spelling: absolute-spelling}`` map from
            :func:`_build_abs_path_map`, used so every file argument is
            absolute regardless of the subprocess's ``cwd``.
        test_files: The caller's test file paths, in their original order
            and spelling.

    Returns:
        The argv list to pass to ``subprocess.run``.
    """
    cmd = [str(vitest_bin), "run", "--reporter=json"]
    cmd.extend(abs_by_original[str(f)] for f in test_files)
    return cmd


def _execute_vitest(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    """Launch the vitest subprocess and return its completed run.

    BP-100n-4 extraction from :func:`done_proof.run_vitest_and_parse` (pure
    refactor — no behaviour change).

    Args:
        cmd: The argv list from :func:`_build_vitest_command`.
        cwd: Directory to run the subprocess in.

    Returns:
        The completed subprocess, or ``None`` when the run exceeded its
        120s timeout (a genuine timeout is reported by the caller as a
        fail-closed result, not raised).

    Raises:
        JsRunnerUnavailable: When the vitest binary is missing
            (``FileNotFoundError``) or the subprocess raises ``OSError`` at
            launch time.  A run that starts but reports failures is NOT this
            exception — that is a normal ``"FAILED"`` result.
    """
    from done_proof import JsRunnerUnavailable

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(cwd),
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
        return None


def _parse_vitest_stdout(stdout: str) -> dict | None:
    """Parse vitest's JSON reporter stdout.

    BP-100n-4 extraction from :func:`done_proof.run_vitest_and_parse` (pure
    refactor — no behaviour change).

    Args:
        stdout: Raw stdout captured from the vitest subprocess.

    Returns:
        The parsed JSON object, or ``None`` when *stdout* is not valid JSON
        (logged to stderr as a warning; the caller reports this as a
        fail-closed result, not an exception).
    """
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(
            f"WARNING: done_proof: vitest JSON parse error: {exc}",
            file=sys.stderr,
        )
        return None


def _build_raw_results_from_json(data: dict) -> dict[str, str]:
    """Build an absolute-path → outcome map from vitest's parsed JSON output.

    BP-100n-4 extraction from :func:`done_proof.run_vitest_and_parse` (pure
    refactor — no behaviour change). Vitest/Jest JSON reporter uses
    ``testFilePath`` or ``name`` for the file path and ``status`` for the
    per-suite outcome (``"passed"`` | ``"failed"``).

    Args:
        data: The JSON object parsed by :func:`_parse_vitest_stdout`.

    Returns:
        Dict mapping resolved absolute file path strings to ``"PASSED"`` or
        ``"FAILED"``.  A file-level status other than ``"passed"`` is mapped
        to ``"FAILED"`` (fail-closed); an entry with no discoverable file
        path is skipped entirely.
    """
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
    return raw_results


# ---------------------------------------------------------------------------
# verify_done_eligible orchestration layer (BP-100n-4-ii relocation from
# done_proof.py -- pure move, no behaviour change)
# ---------------------------------------------------------------------------


def _split_linked_tests_by_language(
    linked_tests: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split covers-linked test tag dicts into Python and TypeScript/TSX subsets.

    Args:
        linked_tests: Tag dicts for the queried AC id from
            :func:`done_proof._collect_linked_tests`.

    Returns:
        ``(py_linked, ts_linked)`` — the subset with a ``.py`` file suffix,
        and the subset with a ``.ts``/``.tsx`` file suffix, respectively.
    """
    py_linked = [t for t in linked_tests if Path(t["file"]).suffix == ".py"]
    ts_linked = [
        t for t in linked_tests if Path(t["file"]).suffix in (".ts", ".tsx")
    ]
    return py_linked, ts_linked


def _handle_no_direct_tests(
    ac_id: str,
    *,
    ac_status_map: dict[str, dict],
    all_tags: list[dict],
    dangling_tags: list[dict],
) -> dict:
    """Return the verdict for an AC with zero direct covers-tagged tests.

    BO-2500a-6: an AC with no direct linked test is classified as a
    COMPOSITE (deriving its proof from its children — see
    :func:`done_proof._verify_composite_eligible`) when its own
    ``covered_by`` field resolves to at least one real AC record; otherwise
    it is a LEAF and is refused with the original "no linked test found"
    message.

    Args:
        ac_id: The AC identifier string being evaluated.
        ac_status_map: Mapping ``{ac_id: {"status": ..., "covered_by": [...]}}``
            from the AC store.
        all_tags: All covers tag dicts produced by the scanner.
        dangling_tags: Dangling-tag entries computed once by the caller.

    Returns:
        A verdict dict with the same shape as
        :func:`done_proof.verify_done_eligible`.
    """
    from done_proof import _has_resolvable_child, _verify_composite_eligible

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


def _maybe_reachability_verdict(
    reachability_spec: dict | None,
    py_linked: list[dict],
    dangling_tags: list[dict],
) -> dict | None:
    """Return an early ineligible verdict when the reachability gate refuses.

    BO-2900a-1-i: reachability is an ADDITIONAL condition layered on top of
    the pre-existing pass/fail gate below, evaluated first so a proof that
    never reached the target is refused without depending on whatever the
    separate pytest subprocess run happens to report. A no-op
    *reachability_spec* (``None``), or an AC with no Python linked tests,
    makes this function a no-op.

    Args:
        reachability_spec: Optional ``{"target": str, "entry_point": str}``,
            as accepted by :func:`done_proof.verify_done_eligible`.
        py_linked: The AC's Python covers-tagged linked tests.
        dangling_tags: Dangling-tag entries computed once by the caller,
            attached to the returned verdict when one is produced.

    Returns:
        The ineligible verdict dict when the reachability gate refuses at
        least one linked test; ``None`` when the gate does not apply, or
        every linked test reached the target through the entry point.
    """
    from done_proof import _check_reachability_for_linked_tests

    if reachability_spec is None or not py_linked:
        return None
    reachability_verdict = _check_reachability_for_linked_tests(
        py_linked, reachability_spec
    )
    if reachability_verdict is not None:
        reachability_verdict["dangling_tags"] = dangling_tags
    return reachability_verdict


def _run_python_test_phase(
    ac_id: str, py_linked: list[dict]
) -> tuple[list[str], list[str], dict[str, str], str | None]:
    """Run pytest on the AC's linked Python tests and classify outcomes.

    Args:
        ac_id: The AC identifier being evaluated (folded into the timeout
            reason string, when one occurs).
        py_linked: The AC's Python covers-tagged linked tests. An empty list
            is a legal no-op (the AC may link only TypeScript/TSX tests).

    Returns:
        ``(passing, failing, pytest_results, incomplete_reason)``. When
        *py_linked* is empty, all four are empty/``None``. When the pytest
        subprocess did not run to completion — it exceeded its budget, or
        was killed by the machine, or ended for any other reason before
        every linked test reported — ``passing``/``failing`` are empty and
        ``incomplete_reason`` says the run did not finish, per
        :func:`done_proof._pytest_incomplete_run_reason`. The caller MUST
        check ``incomplete_reason`` before trusting ``passing``/``failing``:
        without it, tests that never reported read as tests that did not
        pass (BO-2500a-7).
    """
    from done_proof import (
        _classify_outcomes,
        _pytest_incomplete_run_reason,
        _run_pytest_and_parse,
    )

    if not py_linked:
        return [], [], {}, None
    py_files = list({t["file"] for t in py_linked})
    pytest_results = _run_pytest_and_parse(py_files)
    incomplete_reason = _pytest_incomplete_run_reason(ac_id, pytest_results)
    if incomplete_reason is not None:
        return [], [], pytest_results, incomplete_reason
    py_passing, py_failing = _classify_outcomes(py_linked, pytest_results)
    return py_passing, py_failing, pytest_results, None


def _classify_ts_outcomes(
    ts_linked: list[dict], vitest_results: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Split TS/TSX linked tests into passing and non-passing file-path lists.

    Args:
        ts_linked: The AC's TypeScript/TSX covers-tagged linked tests.
        vitest_results: ``{<abs-path-str>: "PASSED" | "FAILED"}`` from
            :func:`done_proof.run_vitest_and_parse`.

    Returns:
        ``(ts_passing, ts_failing)`` — file path strings, deduplicated by
        file (a file linked more than once is classified once).
    """
    ts_passing: list[str] = []
    ts_failing: list[str] = []
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
    return ts_passing, ts_failing


def _run_ts_test_phase(ts_linked: list[dict]) -> tuple[list[str], list[str]]:
    """Run vitest on the AC's linked TS/TSX tests and classify outcomes.

    Only invoked when >= 1 linked ``.ts``/``.tsx`` test exists (BO-2500e-2 /
    BO-2500e-4-i) — an empty *ts_linked* is a no-op that never calls
    :func:`done_proof.run_vitest_and_parse`.

    Args:
        ts_linked: The AC's TypeScript/TSX covers-tagged linked tests.

    Returns:
        ``(ts_passing, ts_failing)`` file path strings.

    Raises:
        JsRunnerUnavailable: Propagated unchanged from
            :func:`done_proof.run_vitest_and_parse` when the vitest binary
            is missing or cannot be launched — the caller decides how to
            report it.
    """
    from done_proof import _discover_project_dir, run_vitest_and_parse

    if not ts_linked:
        return [], []
    ts_files_unique = list({t["file"] for t in ts_linked})
    project_dir = _discover_project_dir(ts_files_unique)
    vitest_results = run_vitest_and_parse(ts_files_unique, project_dir=project_dir)
    return _classify_ts_outcomes(ts_linked, vitest_results)


def _build_failure_reason(
    ac_id: str,
    py_failing: list[str],
    ts_failing: list[str],
    pytest_results: dict[str, str],
) -> str:
    """Build the combined operator-facing reason string for a failing verdict.

    The three refusal causes call for different operator actions — fix the
    code, un-skip the test, write a test — so each Python failing nodeid is
    named individually via :func:`done_proof._describe_non_passing`
    (ACS-200f-1); TS/TSX failures are named together as a single clause.

    Args:
        ac_id: The AC identifier being evaluated (folded into the TS clause).
        py_failing: Non-passing Python nodeids/paths from
            :func:`done_proof._classify_outcomes`.
        ts_failing: Non-passing TypeScript/TSX file paths from
            :func:`_classify_ts_outcomes`.
        pytest_results: ``{nodeid: outcome}`` from
            :func:`done_proof._run_pytest_and_parse`, used to look up each
            Python failure's real outcome.

    Returns:
        A ``"; "``-joined reason string combining the Python and TS/TSX
        failure clauses, in that order.
    """
    from done_proof import _describe_non_passing

    reason_parts: list[str] = []
    if py_failing:
        for nid in py_failing:
            reason_parts.append(_describe_non_passing(nid, pytest_results))
    if ts_failing:
        ts_names = ", ".join(ts_failing)
        reason_parts.append(f"JS test(s) failed for {ac_id}: {ts_names}")
    return "; ".join(reason_parts)


# DECISION HISTORY
# ================================================================================
# - 2026-09-14 [python-coder/BP-100n-4-ii]: Created this sibling module by
#   relocating 13 private helpers straight out of done_proof.py -- no logic,
#   message text, or verdict shape changed. The relocation was needed
#   because decomposing verify_done_eligible() and run_vitest_and_parse()
#   IN PLACE (done_proof.py's own 2026-09-14 DECISION HISTORY entry) added
#   ~131 counted lines of new signatures/docstrings to a file that was
#   already over its 1347-line ratchet baseline
#   (scripts/commit_guardian/check_file_size.py refuses any further growth
#   of an already-oversized file). See done_proof.py's own DECISION HISTORY
#   addendum for the corresponding note. Each helper here that needs a
#   done_proof.py symbol imports it LOCALLY (inside the function body)
#   rather than at this module's top level, because done_proof.py imports
#   THIS module's helpers at its own top level -- a top-level
#   `from done_proof import ...` here would deadlock that import (see this
#   module's own ARCHITECTURE section). Added to build_ac_store's deploy_map
#   in scripts/build_phases.py in the same change, so the deployed
#   check_done_proof hook (which imports done_proof, which imports this
#   module) does not crash with ModuleNotFoundError -- the same class of gap
#   done_proof.py's own module docstring already documents for itself.
#   (#BP-100n-4)
# ================================================================================
