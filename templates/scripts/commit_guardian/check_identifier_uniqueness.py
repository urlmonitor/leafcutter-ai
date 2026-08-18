"""
Whole-collection uniqueness pass over the numbered artifact namespaces.

MODULE: check_identifier_uniqueness
GOAL: Provide a single importable entry point, ``run_uniqueness_pass``, that
    walks the whole on-disk collection (not a staged diff) and reports every
    number claimed by two or more artifacts across three namespaces:
    acceptance-criterion identifiers, decision-record integers, and
    architecture-diagram level-and-sequence identifiers. Returns exactly one
    finding per contested number -- never one finding per claimant file --
    together with a per-namespace count of artifacts inspected.
BUSINESS CONTEXT: GE-122 ("numbers mean one thing") exists because a number
    that resolves to two different artifacts is a silent ambiguity: a reader
    who follows "GE-119" or "ADR-029" has no way to know which of two records
    they landed on. A per-file check cannot see this -- it judges one file at
    a time and never learns that a sibling file claims the same number. This
    module is the load-bearing PRODUCER for the whole GE-122 tree: six sibling
    ACs (GE-122a-1-i, GE-122c-1, GE-122c-2, GE-122d-1, GE-122d-3, GE-122e-3)
    consume the verdict object this module returns, which is why the pass is
    a plain importable function rather than logic embedded inside one
    pre-commit hook script -- GE-122d-1 requires the same evaluation to run at
    three separate commit-lifecycle stages, which is unsatisfiable if the
    logic lives inside a single stage's script.
ARCHITECTURE: Thin orchestrator over two sibling modules (split out to keep
    every new file under the project's 400-line limit, following the
    _ac_store_index.py / _ac_store_index_disk.py precedent already
    established in this directory):
      - _uniqueness_types.py: the Finding / NamespaceVerdict / UniquenessVerdict
        dataclasses (re-exported here for the public contract).
      - _uniqueness_scanners.py: the three purely-filesystem namespace walks
        (acceptance-criteria, decisions, diagrams) and their inspected_count
        tracking.
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

Exit codes (CLI usage -- ``python check_identifier_uniqueness.py``):
    0 - every namespace passed (no contested numbers).
    1 - at least one namespace reported a contested number.

DOC_LINKS:
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml

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
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

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

__all__ = [
    "Finding",
    "NamespaceVerdict",
    "UniquenessVerdict",
    "run_uniqueness_pass",
    "main",
]

_HOOK_PREFIX = "[check_identifier_uniqueness]"

_NS_AC = "acceptance-criteria"
_NS_DECISIONS = "decisions"
_NS_DIAGRAMS = "diagrams"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_uniqueness_pass(collection_root: str | Path) -> UniquenessVerdict:
    """Run the whole-collection uniqueness pass over three fixed namespaces.

    Pure orchestration: each namespace walk (in _uniqueness_scanners) owns
    its own I/O boundary and fails open per file, so this function performs
    no filesystem access itself and needs no try/except of its own.

    Args:
        collection_root: Root directory of the collection to inspect (the
            directory containing docs/acceptance-criteria/,
            docs/architecture/adrs/, and docs/architecture/diagrams/).

    Returns:
        The UniquenessVerdict covering the acceptance-criteria, decisions,
        and diagrams namespaces.
    """
    root = Path(collection_root)
    namespaces = {
        _NS_AC: scan_acceptance_criteria(root / "docs" / "acceptance-criteria"),
        _NS_DECISIONS: scan_decisions(root / "docs" / "architecture" / "adrs"),
        _NS_DIAGRAMS: scan_diagrams(root / "docs" / "architecture" / "diagrams"),
    }
    passed = all(ns.passed for ns in namespaces.values())
    return UniquenessVerdict(passed=passed, namespaces=namespaces)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the pass against the current working directory and print a report.

    Returns:
        0 when every namespace passes; 1 when any namespace reports a
        contested number.
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
            joined_paths = ", ".join(finding.paths)
            print(f"  {finding.number} claimed by: {joined_paths}", file=sys.stderr)
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
