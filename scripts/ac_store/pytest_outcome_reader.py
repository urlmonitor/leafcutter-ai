"""
MODULE: scripts/ac_store/pytest_outcome_reader.py
GOAL: The ONE shared reading of a ``pytest -v`` run into ``{nodeid: outcome}``
    (TQ-500g-4, TQ-500g-4-i): a test that failed in any sub-case reads FAILED,
    and a run that exits 1 with no identifiable failing test is inconclusive.
BUSINESS CONTEXT: pytest 9 prints ``<nodeid> PASSED`` for a test whose only
    failures sit inside ``self.subTest()`` and reports them on separate
    ``SUBFAILED[<msg>] <nodeid> - ...`` lines. A reader that drops those lines
    reads a failing test as passed (KI-TQ-20260928-subtest-failures-read-as-
    passed). Every check that reads a test run -- done_proof, the kind-aware
    reader, the fast lane's red-baseline gate -- goes through this module and
    keeps no private regex or outcome table.
ARCHITECTURE: Sibling of done_proof.py (extracted from it, which is over the
    file-size ratchet). No leading underscore: it is imported from
    scripts/build_orchestration/ via done_proof, and an underscore reads to the
    declaring-files inspector as a same-directory sibling. Registered in
    AC_STORE_DEPLOY_MAP (scripts/build_phases_ac_store.py). Imports nothing from
    the rest of the package, so it loads in either order. The
    ``{nodeid: outcome}`` contract and outcome words are unchanged; failed
    sub-case messages travel on the additive ``PytestOutcomes.subfailed``
    attribute, never as new outcome strings.
"""

from __future__ import annotations

import re

# Sentinel key a reader returns whenever the run did not finish or cannot be
# trusted. Shaped so it never collides with a real nodeid (every real nodeid
# contains "::").
_PYTEST_RUN_INCOMPLETE_SENTINEL = "__done_proof_pytest_timeout__"

# Matches a pytest -v result line: <nodeid> <OUTCOME>
# Handles relative and absolute paths including "../" prefixes.
# Outcomes: PASSED, FAILED, XFAIL, XPASS, SKIPPED, ERROR.
_PYTEST_RESULT_RE = re.compile(
    r"^(\S+::test_\w+(?:\[.*?\])?)\s+(PASSED|FAILED|XFAIL|XPASS|SKIPPED|ERROR)",
    re.MULTILINE,
)

# pytest 9 sub-case failure line, e.g.
#   SUBFAILED[retry_due unset] test_x.py::T::test_a - AssertionError: ...
#   SUBFAILED(i=1) test_x.py::T::test_a - ...        (no msg given)
# SUBPASSED lines are informational and deliberately never match. The node id
# runs to " - " or end of line, so a parametrize id with a space stays whole.
_SUBFAILED_RE = re.compile(
    r"^SUBFAILED(?:\[(?P<msg>.*?)\]|\((?P<params>.*?)\))?\s+(?P<nodeid>\S+::.*?)(?=\s+-\s|\s*$)",
    re.MULTILINE,
)

_NOT_PASSING_FAILURES = ("FAILED", "ERROR")


class PytestOutcomes(dict):
    """A ``{nodeid: outcome}`` dict that also carries failed sub-case names.

    Equality, iteration and ``.get`` behave exactly as for a plain dict, so
    every existing consumer keeps working unchanged.

    Attributes:
        subfailed: ``{nodeid: [sub-case message, ...]}`` for each test read
            FAILED because at least one of its sub-cases failed.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.subfailed: dict[str, list[str]] = {}


def _inconclusive_message(returncode: int) -> str:
    """Return the contradiction reason for an exit-1 run with no failing test."""
    return (
        f"pytest exited with status {returncode} (run reported failure) but "
        "no failing test could be identified in its output"
    )


def parse_pytest_outcomes(output: str, returncode: int | None = None) -> PytestOutcomes:
    """Read ``pytest -v`` stdout (and exit status) into per-test outcomes.

    A node id with at least one ``SUBFAILED`` line reads FAILED whatever its own
    result line says (a sub-case failure never reads as a pass). When
    *returncode* is ``1`` and no test reads FAILED or ERROR, the run
    contradicts itself and is returned as the incomplete-run sentinel
    (inconclusive, never a pass). Exit 0 and exit 1 with a parsed failure keep
    their per-test reading; other exit statuses are the caller's business.

    Args:
        output: Raw stdout of a ``pytest -v`` run.
        returncode: The run's exit status, or ``None`` to skip the cross-check.

    Returns:
        :class:`PytestOutcomes` mapping nodeid to ``PASSED``/``FAILED``/``XFAIL``/
        ``XPASS``/``SKIPPED``/``ERROR``; or ``{sentinel: message}`` when the run
        is inconclusive.
    """
    outcomes = PytestOutcomes((m.group(1), m.group(2)) for m in _PYTEST_RESULT_RE.finditer(output))
    for match in _SUBFAILED_RE.finditer(output):
        nodeid = match.group("nodeid")
        label = match.group("msg") if match.group("msg") is not None else match.group("params")
        outcomes[nodeid] = "FAILED"
        outcomes.subfailed.setdefault(nodeid, []).append(label or "unnamed sub-case")
    if returncode == 1 and not any(v in _NOT_PASSING_FAILURES for v in outcomes.values()):
        return PytestOutcomes({_PYTEST_RUN_INCOMPLETE_SENTINEL: _inconclusive_message(returncode)})
    return outcomes


def describe_subcases(outcomes: dict[str, str], nodeid: str) -> str:
    """Return `` (failed sub-case: <msg>; ...)`` for *nodeid*, or ``""``.

    Args:
        outcomes: A result of :func:`parse_pytest_outcomes` (any plain dict
            yields ``""``).
        nodeid: The pytest nodeid to describe.

    Returns:
        A suffix naming each failed sub-case, empty when there is none.
    """
    names = getattr(outcomes, "subfailed", {}).get(nodeid)
    return f" (failed sub-case: {'; '.join(names)})" if names else ""
