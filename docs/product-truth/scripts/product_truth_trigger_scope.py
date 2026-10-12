"""
MODULE: product_truth_trigger_scope
GOAL: The record checker's own resolvable-pointer trigger scope (ADR-049
    sub-decision 2) -- the single source of truth the record checker's
    automatic-check hook entry (`check-product-truth-validate`) must derive
    its `files:` activation regex from, instead of a hand-restated literal.
BUSINESS CONTEXT: The checker's resolvable-pointer surface is currently
    acceptance-criterion ids plus bounded JSON schemas, runtime models and
    example receipts. The AC pointer and JSON contract checkers share this
    automatic gate. ADR-049 requires that widening the resolvable surface adds
    that kind's repository root here, in the SAME commit, so the hook's
    trigger scope can never silently fall behind what the checker actually
    resolves (GE-120: green must mean checked). A tiny, standalone module
    (rather than living inline in product_truth_checks.py) because that
    module sits at its own GE-127a-1/GE-127b-1 400-content-line ratchet
    ceiling with no headroom left -- same module-split precedent as
    product_truth_index_checks.py / product_truth_example_checks.py, which
    product_truth_checks.py re-exports from for the identical reason.
ARCHITECTURE: Leaf module -- no imports beyond the stdlib. Re-exported by
    product_truth_checks.py so `from product_truth_checks import
    RESOLVABLE_POINTER_TRIGGER_PATTERNS, resolvable_pointer_trigger_pattern`
    keeps resolving there (unit_tests/product_truth/test_uxp_700c_3.py's
    import contract), the same re-export shape that module already uses for
    its other sibling check modules.
"""
from __future__ import annotations

#: One anchored regex alternative per repository root the record checker's
#: RESOLVABLE pointer surface can name -- the record's own root, plus one
#: root per pointer kind the AC pointer and JSON contract checkers resolve.
#: Schema/example roots and the explicit model import surface are bounded
#: by product_truth_contract_sources.py. Widening this surface for a new
#: kind MUST add that kind's root here in the SAME commit (ADR-049
#: sub-decision 3) -- unless the new kind's target set cannot be expressed
#: as a bounded set of repository roots, in which case a new ADR is required
#: instead of a catch-all regex (that `unless` clause).
RESOLVABLE_POINTER_TRIGGER_PATTERNS: tuple[str, ...] = (
    r"^docs/product-truth/",
    r"^docs/analysis/",
    r"^docs/acceptance-criteria/.*\.yaml$",
    r"^kernel/contracts/",
    r"^kernel/memory/",
    r"^kernel/providers/base\.py$",
    r"^knowledge/",
    r"^kernel/schemas/",
    r"^kernel/persistence/base\.py$",
    r"^integrations/retrieval_needs_llm\.py$",
    r"^config/",
    r"^reports/",
    r"^templates/agents/flow-author\.md$",
    r"^docs/how-to/(authoring-product-truth-artifacts|product-truth-schema-reference)\.md$",
)


def resolvable_pointer_trigger_pattern() -> str:
    """The union regex the record checker's automatic-check `files:` scope MUST equal.

    ADR-049 sub-decision 2: the hook's activation condition
    (`check-product-truth-validate` in scripts/commit_guardian/
    commit_guardian.json, its templates/ mirror, and .pre-commit-config.yaml)
    is DERIVED from :data:`RESOLVABLE_POINTER_TRIGGER_PATTERNS` rather than
    hand-restated, so a pointer kind becoming resolvable without the gate's
    trigger scope widening in the same commit is a failing test, not a
    silent drift discovered later.

    Returns:
        The parenthesised alternation of every pattern in
        ``RESOLVABLE_POINTER_TRIGGER_PATTERNS``, e.g.
        ``"(^docs/product-truth/|^docs/acceptance-criteria/.*\\.yaml$)"``.
    """
    return "(" + "|".join(RESOLVABLE_POINTER_TRIGGER_PATTERNS) + ")"


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 09:00 [python-coder]: UXP-700c-3 -- new module. ADR-049
  sub-decision 2 requires product_truth_checks.py to export the record
  checker's resolvable-pointer trigger scope, but that file had no headroom
  left under its own GE-127a-1/GE-127b-1 400-content-line ratchet (397/400
  before this change) for the constant plus its docstring. Same
  module-split precedent product_truth_index_checks.py /
  product_truth_example_checks.py already established: a tiny standalone
  module, re-exported through product_truth_checks.py's own import block so
  `from product_truth_checks import RESOLVABLE_POINTER_TRIGGER_PATTERNS,
  resolvable_pointer_trigger_pattern` keeps resolving for
  unit_tests/product_truth/test_uxp_700c_3.py. The existing hand-written
  `check-product-truth-validate` hook `files:` regex
  (`(^docs/product-truth/|^docs/acceptance-criteria/.*\\.yaml$)`) already
  equalled the derived value, so no hook registry file changed in this
  commit. (#EPIC-TruthfulProjectRecord/24) (ADR-049)
====================================================================
"""
