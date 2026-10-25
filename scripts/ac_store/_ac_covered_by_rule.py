"""
MODULE: _ac_covered_by_rule
GOAL: The one definition of the rule that keeps a front-end declaration or an
    element pin out of an acceptance criterion's ``covered_by`` list.
BUSINESS CONTEXT: GE-124g-1 / ADR-079. ``covered_by`` records links to tests and
    child criteria. A front-end file naming a criterion in its component-level
    declaration is an unverified claim the file makes about itself, and an
    element pin is a claim about one rendered element; neither is coverage.
    Declarations belong in ``declared_by``, pins in ``pinned_by``. There is no
    warn tier, no per-item exception and no configuration key for this rule.
ARCHITECTURE: Pure function, stdlib only, no I/O. Called by
    scripts/ac_store/validate_ac_schema.py directly and by the commit hook
    check_ac_schema.py through the sibling bridge _covered_by_rule_bridge.py,
    so both gates share this single definition. Deployed to
    <output_root>/scripts/ac_store/ via build_phases_ac_store's deploy_map.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-079-declarations-never-enter-covered-by.md

DECISION HISTORY:
  - 2026-10-23 [python-coder/GE-124g-1]: Created. Detection rule per ADR-079: a pin
    slug (``decl-`` followed by dash-separated lowercase alphanumerics) belongs in
    ``pinned_by``; a path whose extension is one of the in-scope front-end
    extensions and that is neither a test nor a story file belongs in
    ``declared_by``. Test and story files share those extensions, so they are
    excluded first (``.test.``/``.spec.``/``.stories.`` in the basename, or a
    ``__tests__`` path segment); otherwise every legitimate front-end coverage
    entry would be refused. Lives in ac_store (not the hook tree) because the hook
    already reaches ac_store through a bridge and the standalone validator cannot
    import from the hook tree in the deployed layout.
    (#EPIC-EveryScreenSaysWhichRequirementItIs/44) (ADR-079)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PIN_SLUG = re.compile(r"^decl-[a-z0-9]+(-[a-z0-9]+)*$")
_FRONTEND_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".html"}
_TEST_MARKERS = (".test.", ".spec.", ".stories.")
_REF_SPLIT = re.compile(r"::|#")


def _target_field(value: str) -> str | None:
    """Name the field a ``covered_by`` value belongs in, or None when it is legitimate.

    Args:
        value: One ``covered_by`` entry.

    Returns:
        ``"pinned_by"`` for a pin slug, ``"declared_by"`` for a front-end source
        path, None for anything else (including front-end test and story refs).
    """
    text = value.strip()
    if _PIN_SLUG.match(text):
        return "pinned_by"
    path = Path(_REF_SPLIT.split(text, maxsplit=1)[0].strip())
    if path.suffix.lower() not in _FRONTEND_SUFFIXES:
        return None
    if "__tests__" in path.parts or any(m in path.name for m in _TEST_MARKERS):
        return None
    return "declared_by"


def covered_by_declaration_errors(path: Path, data: dict[str, Any]) -> list[str]:
    """Reject front-end declarations and element pins written into ``covered_by``.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        data: Parsed AC record.

    Returns:
        One error per offending entry naming the criterion, the value and the
        field it belongs in; empty when ``covered_by`` is clean or absent.
    """
    entries = data.get("covered_by")
    if not isinstance(entries, list):
        return []
    errors = []
    for value in (v for v in entries if isinstance(v, str)):
        field = _target_field(value)
        if field:
            errors.append(
                f"{path}: criterion {data.get('id')}: covered_by entry '{value}' is not "
                f"coverage; it belongs in {field} (GE-124g-1)"
            )
    return errors
