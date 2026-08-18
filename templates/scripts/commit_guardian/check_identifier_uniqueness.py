"""
Whole-collection uniqueness pass over the numbered artifact namespaces.

MODULE: check_identifier_uniqueness
GOAL: Provide a single importable entry point, ``run_uniqueness_pass``, that
    walks the whole on-disk collection (not a staged diff) and reports every
    number claimed by two or more artifacts across four namespaces:
    acceptance-criterion identifiers, decision-record integers,
    architecture-diagram level-and-sequence identifiers, and work-item
    (ticket) identifiers held by two or more lifecycle folders. Returns
    exactly one finding per contested number -- never one finding per
    claimant file -- together with a per-namespace count of artifacts
    inspected.
BUSINESS CONTEXT: GE-122 ("numbers mean one thing") exists because a number
    that resolves to two different artifacts is a silent ambiguity: a reader
    who follows a bare "GE-000" or "ADR-000" has no way to know which of two records
    they landed on. A per-file check cannot see this -- it judges one file at
    a time and never learns that a sibling file claims the same number. The
    work-items namespace covers the sibling failure shape (GE-122a-2): one
    identifier existing as two copies free to disagree about its own state.
    This module is the load-bearing PRODUCER for the whole GE-122 tree: six
    sibling ACs (GE-122a-1-i, GE-122c-1, GE-122c-2, GE-122d-1, GE-122d-3,
    GE-122e-3) consume the verdict object this module returns, which is why
    the pass is a plain importable function rather than logic embedded
    inside one pre-commit hook script -- GE-122d-1 requires the same
    evaluation to run at three separate commit-lifecycle stages, which is
    unsatisfiable if the logic lives inside a single stage's script.
ARCHITECTURE: Thin orchestrator over three sibling modules (split out to keep
    every new file under the project's 400-line limit, following the
    _ac_store_index.py / _ac_store_index_disk.py precedent already
    established in this directory):
      - _uniqueness_types.py: the Finding / NamespaceVerdict / UniquenessVerdict
        dataclasses (re-exported here for the public contract).
      - _uniqueness_scanners.py: the three purely-filesystem namespace walks
        (acceptance-criteria, decisions, diagrams) and their inspected_count
        tracking.
      - _work_items_scanner.py: the fourth namespace walk (work-items),
        reading tickets/ticket_lifecycle.json for the declared lifecycle
        folder list and reporting cross-folder identifier collisions
        together with each copy's declared status.
      - _commit_disposition.py: the commit-time attribution filter
        (``compute_commit_disposition``) that turns the whole-collection
        verdict into a BLOCK/REPORT decision scoped to the current git
        change set, without performing a second collection walk.
    Because this module can be loaded three different ways -- as a script
    (``python check_identifier_uniqueness.py``), as a subprocess target from
    the deployed layout, and via ``importlib.util.spec_from_file_location``
    from a test file that never adds this directory to ``sys.path`` -- the
    sibling imports are made robust by inserting this file's own directory
    into ``sys.path`` before importing, rather than relying on the caller's
    ``sys.path`` state or on running as ``__main__`` (which only the first
    two load paths guarantee).

Public contract (consumed by six downstream ACs -- do not narrow):
    verdict = run_uniqueness_pass(collection_root)
    verdict.passed                     -> bool
    verdict.namespaces                 -> dict[str, NamespaceVerdict]
    namespace_verdict.passed           -> bool
    namespace_verdict.inspected_count  -> int
    namespace_verdict.findings         -> list[Finding]
    finding.number                     -> str
    finding.paths                      -> list[str]
    finding.declared_states            -> dict[str, str] (ADDITIVE, GE-122a-2;
                                           empty {} for the three original
                                           namespaces, populated for
                                           "work-items")

Commit-time disposition contract (ADDITIVE, GE-122a-1-i; see
_commit_disposition.py's own module docstring for the full rationale):
    disposition = compute_commit_disposition(verdict, staged_paths)
    disposition.blocking            -> bool
    disposition.unattributed_count  -> int
    disposition.findings            -> list[CommitFinding]
    commit_finding.{namespace, number, paths, attributed}

Exit codes (CLI usage -- ``python check_identifier_uniqueness.py``):
    0 - no finding is attributed to the current git change set (this
        includes: every namespace passed; or every reported finding is a
        pre-existing collision with no claimant in the staged set).
    1 - at least one finding has a claimant in the current git change set,
        OR the staged set could not be determined at all (e.g. not run
        inside a git repository), in which case this falls back to the
        whole-collection outcome (0 if every namespace passed, else 1) so an
        unrelated git failure can never silently defeat the whole gate.

DOC_LINKS:
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-2.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1-i.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1]: Created. Single importable module
    with dataclass verdict objects (Finding, NamespaceVerdict,
    UniquenessVerdict) satisfying the six-consumer contract fixed by
    unit_tests/commit_guardian/test_ge_122a_1.py.
  - 2026-08-18 [python-coder/GE-122a-1 file-size split]: Split the scanning
    logic and dataclasses into sibling modules _uniqueness_scanners.py and
    _uniqueness_types.py to stay under the check-file-size 400-line limit
    for new files, adding an explicit sys.path bootstrap (rather than a
    soft try/except ImportError fallback) because this module must remain
    fully functional when dynamically loaded via
    importlib.util.spec_from_file_location, which does not add the loaded
    file's own directory to sys.path the way running it as __main__ does.
  - 2026-08-18 [python-coder/GE-122a-2]: Added the fourth "work-items"
    namespace via a new sibling module, _work_items_scanner.py. Changed
    main() to terminate via sys.exit() rather than merely returning an int,
    so that a direct in-process call to main() (as this module's own test
    suite now does, to assert on emitted output) observes the outcome as a
    raised SystemExit -- the exit code is this module's real contract with
    both a pre-commit hook and any other caller, CLI or in-process.
  - 2026-08-18 [python-coder/GE-122a-1-i]: Added compute_commit_disposition
    (new sibling module _commit_disposition.py) and changed main()'s exit
    code to be diff-scoped: a contested number with a claimant in the
    current git change set BLOCKS; one with no claimant in the change set
    is REPORTED (with a visible unattributed count) and does NOT block.
    Inspection itself remains whole-collection -- run_uniqueness_pass is
    still called exactly once; compute_commit_disposition only filters its
    already-produced verdict, never re-walks the collection. When the
    staged set cannot be determined at all (e.g. no git repository present,
    as several of this module's own pre-existing tests exercise by running
    main() against a bare tempdir), main() falls back to the prior
    whole-collection pass/fail exit code rather than treating an unrelated
    git failure as "nothing staged" -- the latter would silently let a
    broken git invocation defeat the gate entirely.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from _commit_disposition import (  # type: ignore[import]  # noqa: E402
    CommitDisposition,
    CommitFinding,
    compute_commit_disposition,
)
from _uniqueness_scanners import (  # type: ignore[import]  # noqa: E402
    scan_acceptance_criteria,
    scan_decisions,
    scan_diagrams,
)
from _uniqueness_types import (  # type: ignore[import]  # noqa: E402
    Finding,
    NamespaceVerdict,
    UniquenessVerdict,
)
from _work_items_scanner import scan_work_items  # type: ignore[import]  # noqa: E402

__all__ = [
    "Finding",
    "NamespaceVerdict",
    "UniquenessVerdict",
    "CommitFinding",
    "CommitDisposition",
    "run_uniqueness_pass",
    "compute_commit_disposition",
    "main",
]

_HOOK_PREFIX = "[check_identifier_uniqueness]"

_NS_AC = "acceptance-criteria"
_NS_DECISIONS = "decisions"
_NS_DIAGRAMS = "diagrams"
_NS_WORK_ITEMS = "work-items"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_uniqueness_pass(collection_root: str | Path) -> UniquenessVerdict:
    """Run the whole-collection uniqueness pass over four fixed namespaces.

    Pure orchestration: each namespace walk (in _uniqueness_scanners) owns
    its own I/O boundary and fails open per file, so this function performs
    no filesystem access itself and needs no try/except of its own.

    Args:
        collection_root: Root directory of the collection to inspect (the
            directory containing docs/acceptance-criteria/,
            docs/architecture/adrs/, docs/architecture/diagrams/, and
            tickets/).

    Returns:
        The UniquenessVerdict covering the acceptance-criteria, decisions,
        diagrams, and work-items namespaces.
    """
    root = Path(collection_root)
    tickets_root = root / "tickets"
    namespaces = {
        _NS_AC: scan_acceptance_criteria(root / "docs" / "acceptance-criteria"),
        _NS_DECISIONS: scan_decisions(root / "docs" / "architecture" / "adrs"),
        _NS_DIAGRAMS: scan_diagrams(root / "docs" / "architecture" / "diagrams"),
        _NS_WORK_ITEMS: scan_work_items(tickets_root, tickets_root / "ticket_lifecycle.json"),
    }
    passed = all(ns.passed for ns in namespaces.values())
    return UniquenessVerdict(passed=passed, namespaces=namespaces)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _print_finding(finding: Finding) -> None:
    """Print one finding line, including declared states when present.

    Args:
        finding: The Finding to report.
    """
    joined_paths = ", ".join(finding.paths)
    line = f"  {finding.number} claimed by: {joined_paths}"
    if finding.declared_states:
        joined_states = ", ".join(f"{path}={state}" for path, state in sorted(finding.declared_states.items()))
        line += f" (declared states: {joined_states})"
    print(line, file=sys.stderr)


def _get_staged_paths() -> list[str] | None:
    """Return the current change set via ``git diff --cached --name-only``.

    Wrapped per CLAUDE.md Rule 1 (external process I/O): a failure here
    (git not installed, or the current directory is not a git repository)
    is logged at WARNING and reported as ``None`` -- deliberately distinct
    from an empty list, which means "git ran successfully and nothing is
    staged". ``main()`` uses that distinction to fall back to the
    whole-collection pass/fail outcome only when the diff-scoped attribution
    decision genuinely cannot be made, so an unrelated git failure can never
    silently turn the gate into a report-only, never-blocking no-op.

    Returns:
        List of staged file path strings (as printed by git, one per line,
        relative to the git repository root), or ``None`` if the staged set
        could not be determined.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not determine the staged change set via git: {exc}",
            file=sys.stderr,
        )
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _print_unattributed_summary(disposition: CommitDisposition) -> None:
    """Print the visible reported-but-unattributed count, when non-zero.

    Per this module's own it_requirements: a silently-tolerated backlog of
    pre-existing, unattributed collisions is how drift accumulates -- a
    visible count is what makes the backlog shrink even while it does not
    block unrelated commits.

    Args:
        disposition: The CommitDisposition returned by
            compute_commit_disposition.
    """
    if not disposition.unattributed_count:
        return
    print(
        f"{_HOOK_PREFIX} {disposition.unattributed_count} reported-but-unattributed "
        "contested number(s) with no claimant in the current change set (not blocking)",
        file=sys.stderr,
    )


def main() -> None:
    """Run the pass against the current working directory and print a report.

    Terminates the process via ``sys.exit`` rather than merely returning an
    int, so that both CLI invocation (``python check_identifier_uniqueness.py``)
    and a direct in-process call to ``main()`` observe the outcome as a
    raised ``SystemExit`` -- the exit code is this module's real contract
    with a pre-commit hook and with any other caller.

    Inspection stays whole-collection: ``run_uniqueness_pass`` is called
    exactly once here, regardless of the git change set. Only the exit code
    is diff-scoped, via ``compute_commit_disposition`` filtering that single
    verdict.

    Exits:
        0 when no finding is attributed to the current git change set
        (including: every namespace passed; or every finding is a
        pre-existing, unattributed collision). 1 when at least one finding
        is attributed, or when the staged set itself could not be
        determined (fails open to the whole-collection pass/fail outcome).
    """
    verdict = run_uniqueness_pass(Path.cwd())
    for ns_name, ns_verdict in verdict.namespaces.items():
        if ns_verdict.passed:
            print(f"{_HOOK_PREFIX} {ns_name}: OK ({ns_verdict.inspected_count} inspected)")
            continue
        print(
            f"{_HOOK_PREFIX} {ns_name}: FAILED ({ns_verdict.inspected_count} inspected)",
            file=sys.stderr,
        )
        for finding in ns_verdict.findings:
            _print_finding(finding)

    staged_paths = _get_staged_paths()
    if staged_paths is None:
        sys.exit(0 if verdict.passed else 1)

    disposition = compute_commit_disposition(verdict, staged_paths)
    _print_unattributed_summary(disposition)
    sys.exit(1 if disposition.blocking else 0)


if __name__ == "__main__":
    main()
