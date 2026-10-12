"""
MODULE: scripts/build_orchestration/_wvr_verdict.py
GOAL: Turn the reading of one pytest run into per-(test, wrong version) result
    rows, and the rows into the runner's one JSON verdict.
BUSINESS CONTEXT: TQ-500g-1-i / -ii. A wrong version counts as caught by a test
    only when that test failed under it by an assertion (it reached the code) and
    passed on the code as written. A failure by absence is ``did_not_load``, a
    pass is ``survived``, and anything that is neither caught nor survived leaves
    the work unfinished. The verdict comes from the runs alone: no claim made by
    an agent or by the manifest is read here.
ARCHITECTURE: Pure functions over :class:`_wvr_pytest.PytestRun`; no I/O. The
    verdict shape is TQ-500g-1-i's ``delivers_to``: ``gate_passed``,
    ``applicable``, ``verified``, ``outcome``, ``reason`` (``survivor`` |
    ``unfinished`` | ``failing on the code as written`` | text | null),
    ``results``, ``survivors``, ``unfinished``. A survivor outranks unfinished
    in ``reason`` because it is the definitive stop.
"""

from __future__ import annotations

from _wvr_pytest import PytestRun
from _wvr_scope import ScopedTest

DID_NOT_LOAD = "wrong version did not load: not a valid run"
NOT_APPLIED = "wrong version not applied: it changes nothing"
NOT_PREPARED = "wrong version could not be prepared"
NON_BLOCKING = frozenset({"caught", "not_in_scope", "not_applicable"})
UNFINISHED = frozenset({"did_not_load", "not_applied", "invalid", "not_run"})
NO_SOURCE_OUTCOME = "wrong-version runs not applicable: no source requirement"


def row(test: str, wrong_version: str, result: str, detail: str) -> dict:
    """Build one result row; ``blocking`` follows from the result word."""
    return {
        "test": test,
        "wrong_version": wrong_version,
        "result": result,
        "blocking": result not in NON_BLOCKING,
        "detail": detail,
    }


def read_one(test: ScopedTest, run: PytestRun, wrong_version: str) -> tuple[str, str]:
    """Read one test's result under one wrong version from the run.

    Args:
        test: The in-scope test (its node is resolved).
        run: A finished (``ran``) reading of the run.
        wrong_version: The wrong version's display name.

    Returns:
        ``(result, detail)``.
    """
    identity = test.node.identity
    outcome = run.outcome.get(identity)
    if outcome is None:
        if identity.split("::")[0] in run.collection_failed:
            return "did_not_load", f"{DID_NOT_LOAD} (the test file failed to collect)"
        return "not_run", "the test produced no result in this run"
    if outcome == "PASSED":
        return "survived", f"passed under '{wrong_version}': the test did not notice it"
    if outcome != "FAILED":
        return "not_run", f"the test ended {outcome}, neither passed nor failed"
    kind = run.kind.get(identity)
    if kind == "assertion":
        return "caught", f"failed under '{wrong_version}' by an assertion, after reaching the code"
    if kind == "absence":
        return "did_not_load", f"{DID_NOT_LOAD} (the failure was an import, name or attribute lookup)"
    return "invalid", "the kind of the failure could not be determined from the run"


def classify_run(
    ran: list[ScopedTest], holders: list[ScopedTest], run: PytestRun, wrong_version: str, group: bool
) -> list[dict]:
    """Build the rows of one wrong-version run.

    Args:
        ran: Every test that was run.
        holders: The tests whose own entry names the wrong version.
        run: The reading of the run.
        wrong_version: The wrong version's display name.
        group: True for "the fix undone", which also stops the work when no
            test in scope fails under it.

    Returns:
        The result rows. A cut-short run gives ``not_run`` for every test.
    """
    if run.status != "ran":
        detail = f"the run was cut short ({run.status}): {run.detail}"
        return [row(t.label, wrong_version, "not_run", detail) for t in ran]
    rows: list[dict] = []
    results: list[str] = []
    for test in ran:
        result, detail = read_one(test, run, wrong_version)
        results.append(result)
        if test in holders or result != "survived":
            rows.append(row(test.label, wrong_version, result, detail))
    if group and results and all(r == "survived" for r in results):
        rows.append(row("", wrong_version, "survived", f"no test in scope failed under '{wrong_version}'"))
    return rows


def _unfinished(rows: list[dict]) -> list[dict]:
    """One entry per wrong version that has an unfinished result."""
    seen: dict[str, dict] = {}
    for r in rows:
        if r["result"] in UNFINISHED and r["wrong_version"] not in seen:
            word = "could_not_prepare" if r["detail"].startswith(NOT_PREPARED) else r["result"]
            seen[r["wrong_version"]] = {"wrong_version": r["wrong_version"], "result": word, "detail": r["detail"]}
    return list(seen.values())


def assemble(rows: list[dict], *, reason_override: str | None = None, applicable: bool = True,
             outcome: str | None = None) -> dict:
    """Compose the verdict from *rows*.

    Args:
        rows: Every result row.
        reason_override: A fixed stop reason (baseline failure, failed put-back,
            internal error); the rows are still reported.
        applicable: False when no wrong-version runs were owed.
        outcome: A fixed outcome text; derived from the rows when omitted.

    Returns:
        The verdict dict in TQ-500g-1-i's shape.
    """
    survivors = [{"test": r["test"], "wrong_version": r["wrong_version"]} for r in rows if r["result"] == "survived"]
    unfinished = [] if reason_override else _unfinished(rows)
    reason = reason_override or ("survivor" if survivors else "unfinished" if unfinished else None)
    gate_passed = reason is None
    if outcome is None:
        outcome = (
            "wrong-version runs passed: every wrong version was caught" if gate_passed
            else f"wrong-version runs stopped the work: {reason}"
        )
    return {
        "gate_passed": gate_passed, "applicable": applicable, "verified": bool(rows) and not unfinished and not reason_override,
        "outcome": outcome, "reason": reason, "results": rows, "survivors": survivors, "unfinished": unfinished,
    }
