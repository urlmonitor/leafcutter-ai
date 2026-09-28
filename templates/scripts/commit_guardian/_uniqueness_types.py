"""
Verdict dataclasses shared by the whole-collection uniqueness pass.

MODULE: _uniqueness_types
GOAL: Define the three small, frozen dataclasses (Finding, NamespaceVerdict,
    UniquenessVerdict) that make up the public contract returned by
    check_identifier_uniqueness.run_uniqueness_pass(). Split into its own
    file so check_identifier_uniqueness.py and its sibling scanner module
    both stay within the project's 400-line-per-new-file limit without
    duplicating the type definitions.
BUSINESS CONTEXT: Six downstream ACs (GE-122a-1-i, GE-122c-1, GE-122c-2,
    GE-122d-1, GE-122d-3, GE-122e-3) consume these exact attributes --
    ``verdict.passed``, ``verdict.namespaces[name].{passed, inspected_count,
    findings}``, ``finding.{number, paths}`` -- so the shapes here must not
    be narrowed without updating every consumer.
ARCHITECTURE: Pure data holders, no behaviour, no I/O -- imported by
    _uniqueness_scanners.py and _work_items_scanner.py (which build them)
    and re-exported by check_identifier_uniqueness.py (the public entry
    point).

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-2.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1]: Extracted from check_identifier_uniqueness.py
    to keep both that module and its sibling _uniqueness_scanners.py under
    the 400-line new-file limit (check-file-size pre-commit hook).
  - 2026-08-18 [python-coder/GE-122a-2]: Added Finding.declared_states as an
    ADDITIVE field with a default_factory=dict default so the three sibling
    namespaces (acceptance-criteria, decisions, diagrams), which never set
    it, are unaffected -- a widening, not a narrowing, per Source-of-Truth
    Discipline Rule 5. Used by the new work-items namespace to carry each
    claimant path's own declared lifecycle status (e.g. "todo", "done") so a
    reader can identify the stale copy without reopening either file.
  - 2026-09-07 [python-coder/GE-122d-3]: Added ``NamespaceVerdict.outcome``
    (one of the three sanctioned literal values below) and
    ``NamespaceVerdict.unreadable_paths`` as ADDITIVE fields, both defaulted
    so every existing construction site (this module has none of its own;
    _uniqueness_scanners.py, _work_items_scanner.py, and several tests
    construct NamespaceVerdict directly) keeps compiling and keeps its exact
    prior meaning for ``.passed`` / ``.inspected_count`` / ``.findings``. A
    per-file read or parse failure inside an otherwise-resolvable namespace
    was previously silently fail-open at the file level (the file counted
    toward ``inspected_count`` but contributed no claim, and the namespace
    still reported a clean pass) -- GE-122d-3 requires that condition to be
    reported as a distinct, machine-checkable outcome rather than absorbed
    into an ordinary clean result. ``outcome`` is a plain string rather than
    an Enum to keep this module dependency-free and trivially JSON-
    serializable (the authoring-time hook round-trips a verdict through
    ``json.dumps``); the three literal values are fixed here as module-level
    constants so every producer and consumer spells them identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Every artifact in the namespace was read successfully and no number is
#: claimed twice.
OUTCOME_CLEAN = "clean"

#: Every artifact was read successfully but at least one number is claimed
#: by two or more of them (``findings`` non-empty).
OUTCOME_CONTESTED = "contested"

#: At least one artifact could not be read or parsed at all (or the
#: namespace's own root/config could not be resolved) -- uniqueness for this
#: namespace was therefore never established, regardless of whether the
#: artifacts that WERE read collided with each other.
OUTCOME_COULD_NOT_ESTABLISH = "could_not_establish"


@dataclass(frozen=True)
class Finding:
    """One contested number and every artifact path that claims it.

    Attributes:
        number: The contested identifier/number (e.g. "GE-000", "029", "c2-003").
            Illustrative ids here are deliberately unissued: citing a RETIRED
            identifier in a docstring makes it a live reference again, which is
            what GE-122e-1's citation guard exists to prevent.
        paths: Every claimant path for this number (always >= 2 entries).
        declared_states: Optional mapping of claimant path -> that copy's own
            declared state (e.g. a work item's frontmatter ``status:``
            value). Empty for namespaces that have no notion of a per-copy
            declared state (acceptance-criteria, decisions, diagrams);
            populated by the work-items namespace so a reader can see which
            copy is stale without opening either file.
    """

    number: str
    paths: list[str]
    declared_states: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NamespaceVerdict:
    """The uniqueness result for one namespace.

    Attributes:
        passed: True iff no contested number was found in this namespace AND
            every artifact this namespace is responsible for was actually
            read (``unreadable_paths`` empty, ``outcome`` != "could_not_establish").
        inspected_count: Count of artifacts walked in this namespace, tracked
            during the walk itself -- not derived from successful parses.
            Includes an artifact whose read or parse ultimately failed: it
            was still ATTEMPTED, which is what this field has always meant.
        findings: One Finding per contested number in this namespace. Stays
            empty for a "could_not_establish" outcome caused by an unreadable
            artifact alone -- an unreadable file is not a collision, it is a
            gap in what was inspected at all.
        outcome: ADDITIVE (GE-122d-3). One of ``OUTCOME_CLEAN``,
            ``OUTCOME_CONTESTED``, ``OUTCOME_COULD_NOT_ESTABLISH`` (module-
            level constants above). Defaults to ``OUTCOME_CLEAN`` so every
            pre-existing construction site that never sets it keeps behaving
            exactly as before. This is the "distinct VALUE in the pass's
            return type" GE-119a-1/GE-122d-3 require: a caller can switch on
            it directly, with no string-matching of printed prose and no
            reliance on any exit code.
        unreadable_paths: ADDITIVE (GE-122d-3). The specific artifact path(s)
            this namespace could not read or parse at all -- non-empty iff
            ``outcome == OUTCOME_COULD_NOT_ESTABLISH`` and the cause is a
            per-artifact read/parse failure (as opposed to the namespace's
            own root/config being entirely absent, where the "artifact" named
            here is the root/config path itself, since there is nothing more
            specific to name). Defaults to an empty list.
    """

    passed: bool
    inspected_count: int
    findings: list[Finding]
    outcome: str = OUTCOME_CLEAN
    unreadable_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UniquenessVerdict:
    """The whole-collection uniqueness result across all namespaces.

    Attributes:
        passed: True iff every namespace passed.
        namespaces: Mapping of namespace name to its NamespaceVerdict.
    """

    passed: bool
    namespaces: dict[str, NamespaceVerdict]
