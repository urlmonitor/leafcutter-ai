"""
MODULE: product_truth_example_checks
GOAL: The example_product cross-check (UXP-700d-3-ii, ADR-044 sec 6): every
    loaded flow, mock-data, mockup, and AC record's declared `example_product`
    is compared against the product root it actually lives under, and every
    disagreement is appended to the checker's existing `errors` list, naming
    both values.
BUSINESS CONTEXT: UXP-700d-3-i registered the `example_product` schema key and
    backfilled every existing example artifact/criterion so this check's first
    commit reports nothing new against the real store. Without this check the
    marker is a second hand-written field that drifts silently from the
    product root (`product_ownership.py`), which is the exact defect ADR-044
    exists to close.
ARCHITECTURE: Leaf module, new sibling of product_truth_checks.py --
    validate_product_truth.py (399/400 content lines) and
    product_truth_checks.py (396/400) both had no room left for this check's
    full body, so it lives here instead and is re-exported through
    product_truth_checks.py for the existing import path
    (`vpt.check_example_product` still resolves). Every finding-decision rule
    is imported verbatim from product_ownership.py (ADR-044 sec 7: "the check
    MUST import ... it MUST NOT re-declare the root constants or re-split
    ids"); this module only loops over the record shapes the checker already
    loads and formats the messages the pure helpers' finding kinds imply.
"""
from __future__ import annotations

from product_ownership import (
    PROJECT_PRODUCT,
    example_product_findings,
    example_product_findings_for_ac,
    product_of_artifact_id,
    product_root_of_doc_link,
)

#: Human-readable text for each finding kind, keyed by
#: product_ownership.FINDING_*. Built once so _format_finding stays a single
#: dispatch rather than a chain of string-literal branches.
_FINDING_TEXT = {
    "mismatch": "example_product={declared!r} disagrees with its product root {root!r}",
    "undeclared": "undeclared -- lives under example product root {root!r} but declares no example_product",
    "project-declared": "example_product={declared!r} names the project's own product {project!r}",
}


def _format_finding(holder: str, kind: str, declared: str | None, root: str | None) -> str:
    """Render one finding as an `[example]`-prefixed error string.

    Every finding names the declared value (rendered as `'absent'` when
    None) and, when there is one, the root it was compared against -- ADR-044
    sec 6's own requirement, independent of which finding kind fired.

    Args:
        holder: The artifact or AC id the finding is about.
        kind: One of product_ownership's FINDING_* values.
        declared: The holder's own `example_product` value, or None.
        root: The product root it was compared against, or None.

    Returns:
        The formatted `errors`-list entry.
    """
    declared_text = "absent" if declared is None else declared
    body = _FINDING_TEXT[kind].format(declared=declared_text, root=root, project=PROJECT_PRODUCT)
    return f"[example] {holder}: {body}"


def _check_artifact_collection(artifacts: dict, errors: list[str]) -> None:
    """Compare every artifact's declared value against its own id's root."""
    for artifact in artifacts.values():
        artifact_id = artifact["id"]
        root = product_of_artifact_id(artifact_id)
        declared = artifact.get("example_product")
        for kind in example_product_findings(declared, root):
            errors.append(_format_finding(artifact_id, kind, declared, root))


def _implemented_by_step_roots(record: dict) -> list[str]:
    """Return the product roots of every implemented-by-step doc_links entry."""
    roots = []
    for link in record.get("doc_links") or []:
        if not isinstance(link, dict):
            continue
        root = product_root_of_doc_link(link.get("path", ""), link.get("relationship", ""))
        if root is not None:
            roots.append(root)
    return roots


def check_example_product(flows: dict, mocks: dict, mockups: dict, ac_records: dict, errors: list[str]) -> None:
    """Cross-check every loaded record's `example_product` against its root.

    Flows/mocks/mockups are compared against the product root of their own
    id (`product_ownership.product_of_artifact_id`); an AC is compared
    against the roots of its `implemented-by-step` doc_links only (zero when
    it has none, per ADR-044 sec 6's own boundary clause). Every finding is
    appended to *errors*, the checker's existing error channel -- this
    introduces no new outcome value (ADR-042).

    Args:
        flows: `{flow_id -> flow}`.
        mocks: `{mock_id -> mock}`.
        mockups: `{mockup_id -> mockup}`.
        ac_records: `{ac_id -> record}`, each carrying `example_product` and
            `doc_links` (validate_product_truth.load_ac_records()'s shape).
        errors: Shared error list; findings are appended.
    """
    for artifacts in (flows, mocks, mockups):
        _check_artifact_collection(artifacts, errors)
    for ac_id, record in ac_records.items():
        declared = record.get("example_product")
        roots = _implemented_by_step_roots(record)
        for kind, root in example_product_findings_for_ac(declared, roots):
            errors.append(_format_finding(ac_id, kind, declared, root))


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-17 [python-coder]: New module. UXP-700d-3-ii's cross-check
  (ADR-044 sec 6) had nowhere to land: validate_product_truth.py stood at
  399/400 content lines and product_truth_checks.py at 396/400, and this
  check's full loop-plus-formatting body would not fit either file's
  remaining headroom. Every finding-decision rule is imported verbatim from
  product_ownership.py (example_product_findings,
  example_product_findings_for_ac, product_root_of_doc_link) per ADR-044 sec
  7; this module is re-exported through product_truth_checks.py's existing
  `from product_truth_example_checks import check_example_product` line so
  `vpt.check_example_product` still resolves for callers, matching the
  precedent product_truth_index_checks.py already set for
  product_truth_checks.py. (#EPIC-TruthfulProjectRecord/35)
====================================================================
"""
