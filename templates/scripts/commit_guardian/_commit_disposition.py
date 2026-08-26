"""
Commit-time attribution disposition over a whole-collection uniqueness verdict.

MODULE: _commit_disposition
GOAL: Provide ``compute_commit_disposition``, which turns the EXISTING
    whole-collection ``UniquenessVerdict`` (produced once by
    ``run_uniqueness_pass``) into a commit-time decision: which contested
    numbers should BLOCK the current commit versus merely be REPORTED. Split
    out of check_identifier_uniqueness.py to keep every new file under the
    project's 400-line limit, following the _uniqueness_types.py /
    _uniqueness_scanners.py / _work_items_scanner.py precedent already
    established in this directory.
BUSINESS CONTEXT: A whole-collection pass necessarily inspects artifacts the
    current author never touched -- two claimants of one number can be
    authored weeks apart from different working copies and never share a
    diff. Blocking every commit on every pre-existing collision in that
    backlog would stop unrelated work dead the moment the pass is switched
    on. The resolution: INSPECTION stays whole-collection (a check whose
    input set is the changed files cannot observe a collision whose second
    claimant is outside the diff), but ATTRIBUTION -- which findings BLOCK
    THIS commit -- is scoped to the current change set. A contested number
    with at least one claimant in the change set blocks; one with no
    claimant in the change set is reported, with a visible count, and does
    not block. This mirrors the resolution already documented in this
    repository's CI "AC store valid" job for its own pre-existing orphan
    backlog.
ARCHITECTURE: Pure, in-memory filtering over an already-computed verdict --
    performs NO filesystem walk and NO git invocation of its own. The single
    collection walk stays owned by ``run_uniqueness_pass``; this module only
    intersects its output against a caller-supplied staged-path set. Path
    comparison resolves both sides (``Path.resolve()``) so relative and
    absolute path strings compare correctly regardless of which the caller
    passed.

Public contract:
    disposition = compute_commit_disposition(verdict, staged_paths)
    disposition.blocking                  -> bool
    disposition.unattributed_count        -> int
    disposition.findings                  -> list[CommitFinding]
    disposition.unresolvable_namespaces   -> list[str] (ADDITIVE, GE-122e-3/H-1;
                                              see the 2026-08-25 DECISION
                                              HISTORY entry below)
    commit_finding.namespace        -> str
    commit_finding.number           -> str
    commit_finding.paths            -> list[str]
    commit_finding.attributed       -> bool

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1-i.yaml
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1-i]: Created. Extracted the
    commit-time attribution decision into its own sibling module rather than
    growing check_identifier_uniqueness.py past a clean size, matching the
    existing three-way split (_uniqueness_types.py / _uniqueness_scanners.py
    / _work_items_scanner.py) already used in this directory. Deliberately
    does not add a second collection walk: it is a pure filter over the
    verdict that ``run_uniqueness_pass`` already produced.
  - 2026-08-25 [python-coder/GE-122e-3, bug-fix, pr-reviewer finding [H-1],
    feedback-id fb_2026-08-24_94dc4ba4]: Fixed `.blocking` deriving SOLELY
    from `any(f.attributed for f in commit_findings)`. GE-122e-3's own
    "THE CONTRACT DECISION" (see
    unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py) makes an
    unresolvable namespace report `NamespaceVerdict(passed=False,
    findings=[])` -- deliberately EMPTY findings, since there is nothing to
    name; the root/config itself is the finding. Such a namespace can never
    produce a single CommitFinding, so it could never set `.blocking=True`
    here -- a misconfigured install (wrong/renamed collection_root, deleted
    ticket_lifecycle.json) silently exited 0 on an ordinary commit. Fixed by
    additionally checking `verdict.namespaces` directly for any
    `ns_verdict.passed is False and not ns_verdict.findings` -- an
    unresolvable namespace now blocks REGARDLESS of what is staged (it is a
    misconfiguration of the gate itself, not a per-file collision that
    attribution can legitimately excuse), while a genuine collision whose
    claimants are all outside the staged diff keeps its EXISTING
    non-blocking/unattributed treatment unchanged (GE-122a-1-i's own
    contract, pinned by
    TestUnresolvableNamespaceVsUnattributedCollisionContrast). Also added
    `unresolvable_namespaces` as an ADDITIVE field (empty list when none) so
    `main()`'s operator message can name which namespace failed to resolve,
    rather than only exiting non-zero with no explanation -- `.blocking`,
    `.unattributed_count`, and `.findings` keep their exact prior meaning;
    every existing consumer of this dataclass is unaffected by a field it
    never reads.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from _uniqueness_types import UniquenessVerdict  # type: ignore[import]


@dataclass(frozen=True)
class CommitFinding:
    """One contested number's commit-time attribution.

    Attributes:
        namespace: The namespace name the underlying Finding came from
            (e.g. "acceptance-criteria", "work-items").
        number: The contested identifier/number (same value as the source
            Finding.number).
        paths: EVERY claimant path for this number (same value as the source
            Finding.paths -- attribution never narrows which paths are
            reported).
        attributed: True iff at least one of `paths` is in the current
            change set. Attribution decides BLOCK vs REPORT-ONLY; it never
            decides whether the finding is reported at all.
    """

    namespace: str
    number: str
    paths: list[str]
    attributed: bool


@dataclass(frozen=True)
class CommitDisposition:
    """The commit-time BLOCK/REPORT decision across every namespace.

    Attributes:
        blocking: True iff at least one CommitFinding, in any namespace, is
            attributed, OR at least one namespace is unresolvable (reports
            ``passed=False`` with an EMPTY ``findings`` list -- per
            GE-122e-3's "THE CONTRACT DECISION", there is nothing to name
            because the root/config itself is the finding). An unresolvable
            namespace blocks REGARDLESS of what is staged: it is a
            misconfiguration of the gate itself, not a property of the diff,
            so diff-scoped attribution deliberately does not apply to it --
            distinct from a genuine collision whose claimants are all
            outside the staged diff, which stays non-blocking/unattributed
            exactly as before (see `unresolvable_namespaces` below for how
            to tell the two apart from the outside).
        unattributed_count: Count of CommitFindings, across all namespaces,
            with no claimant path in the change set. Reported-but-unattributed
            findings never block, but the count is always surfaced so a
            silently-tolerated backlog cannot accumulate unseen. Unchanged by
            the `unresolvable_namespaces` addition -- an unresolvable
            namespace contributes zero CommitFindings (nothing to attribute),
            so it never affects this count either way.
        findings: One CommitFinding per contested number across every
            namespace (mirrors the source verdict's findings 1:1).
        unresolvable_namespaces: ADDITIVE field (GE-122e-3/H-1). Namespace
            names whose own NamespaceVerdict reported ``passed=False`` with
            an EMPTY ``findings`` list -- i.e. the namespace's root/config
            could not be resolved at all, as opposed to a genuine collision.
            Empty when every namespace was resolved (whether clean or
            genuinely collided). Lets a caller (``main()``'s operator
            message) name WHICH namespace failed to resolve, rather than
            only knowing that something did.
    """

    blocking: bool
    unattributed_count: int
    findings: list[CommitFinding]
    unresolvable_namespaces: list[str] = field(default_factory=list)


def _resolve_staged(staged_paths: Iterable[str | Path]) -> set[Path]:
    """Normalize the caller-supplied change set to resolved absolute paths.

    Args:
        staged_paths: Iterable of staged file paths (relative or absolute,
            str or Path) -- e.g. the output of `git diff --cached --name-only`.

    Returns:
        Set of resolved absolute Path objects, suitable for membership
        comparison against a Finding's own (already-anchored) claimant paths.
    """
    return {Path(raw).resolve() for raw in staged_paths}


def compute_commit_disposition(
    verdict: UniquenessVerdict,
    staged_paths: Iterable[str | Path],
) -> CommitDisposition:
    """Filter an existing whole-collection verdict into a commit disposition.

    Reuses the verdict passed in -- this function performs no collection
    walk of its own (see the ticket's own Implementation Notes: "Must not
    add a second collection walk... reuse the single pass and filter its
    verdict"). Inspection (which findings exist at all) is whatever the
    verdict already says; only attribution (which findings BLOCK) is scoped
    to `staged_paths`.

    Args:
        verdict: The UniquenessVerdict from a single run_uniqueness_pass
            call.
        staged_paths: The current change set (e.g. from
            `git diff --cached --name-only`).

    Returns:
        The CommitDisposition: `.blocking` True iff any finding has at least
        one claimant path in `staged_paths`, OR at least one namespace is
        unresolvable (`passed=False` with an empty `findings` list -- a
        misconfiguration of the gate itself, which blocks regardless of what
        is staged; see GE-122e-3's "THE CONTRACT DECISION" and the
        `unresolvable_namespaces` field docstring on `CommitDisposition`).
    """
    staged_resolved = _resolve_staged(staged_paths)

    commit_findings: list[CommitFinding] = []
    for namespace, ns_verdict in verdict.namespaces.items():
        for finding in ns_verdict.findings:
            attributed = any(Path(claimant).resolve() in staged_resolved for claimant in finding.paths)
            commit_findings.append(
                CommitFinding(
                    namespace=namespace,
                    number=finding.number,
                    paths=list(finding.paths),
                    attributed=attributed,
                )
            )

    # An unresolvable namespace (passed=False, findings=[]) is a
    # misconfiguration of the gate itself -- see GE-122e-3's "THE CONTRACT
    # DECISION" -- never a per-file collision, so it must block regardless
    # of the staged set. It can never produce a CommitFinding (there is
    # nothing to name), so it must be checked directly against the source
    # verdict rather than derived from `commit_findings`.
    unresolvable_namespaces = [
        namespace
        for namespace, ns_verdict in verdict.namespaces.items()
        if ns_verdict.passed is False and not ns_verdict.findings
    ]

    return CommitDisposition(
        blocking=any(f.attributed for f in commit_findings) or bool(unresolvable_namespaces),
        unattributed_count=sum(1 for f in commit_findings if not f.attributed),
        findings=commit_findings,
        unresolvable_namespaces=unresolvable_namespaces,
    )
