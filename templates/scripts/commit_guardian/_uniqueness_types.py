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
    _uniqueness_scanners.py (which builds them) and re-exported by
    check_identifier_uniqueness.py (the public entry point).

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1]: Extracted from check_identifier_uniqueness.py
    to keep both that module and its sibling _uniqueness_scanners.py under
    the 400-line new-file limit (check-file-size pre-commit hook).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One contested number and every artifact path that claims it.

    Attributes:
        number: The contested identifier/number (e.g. "GE-119", "029", "c2-003").
        paths: Every claimant path for this number (always >= 2 entries).
    """

    number: str
    paths: list[str]


@dataclass(frozen=True)
class NamespaceVerdict:
    """The uniqueness result for one namespace.

    Attributes:
        passed: True iff no contested number was found in this namespace.
        inspected_count: Count of artifacts walked in this namespace, tracked
            during the walk itself -- not derived from successful parses.
        findings: One Finding per contested number in this namespace.
    """

    passed: bool
    inspected_count: int
    findings: list[Finding]


@dataclass(frozen=True)
class UniquenessVerdict:
    """The whole-collection uniqueness result across all namespaces.

    Attributes:
        passed: True iff every namespace passed.
        namespaces: Mapping of namespace name to its NamespaceVerdict.
    """

    passed: bool
    namespaces: dict[str, NamespaceVerdict]
