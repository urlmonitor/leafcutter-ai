"""
MODULE: ac_parent_id
GOAL: Utility for deriving a parent AC ID from a child AC ID by stripping the
    last hyphen-delimited segment, or the trailing alpha suffix when the ID is
    at the first-letter sub-level.
BUSINESS CONTEXT: The AC store uses a hierarchical ID scheme:
    - L0 root:  PREFIX-NNN                      (e.g. ACS-100)
    - L1 alpha: PREFIX-NNNx                     (e.g. ACS-100a)
    - L2 num:   PREFIX-NNNx-N                   (e.g. ACS-100a-1)
    - L3+ ext:  PREFIX-NNNx-N-y[-z ...]        (e.g. ACS-100a-1-i)
    Deriving the parent ID is the foundation for every parent-child enforcement
    feature (pre-commit hooks, store-wide scans, agent auto-updates) — they all
    call derive_parent_id() rather than implementing their own parsing.
ARCHITECTURE: Pure-stdlib function; no external dependencies. Regex-based
    parsing using the canonical AC ID patterns defined in ADR-007.
    derive_parent_id() is the public API. All helpers are module-private.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md

DECISION HISTORY:
  - 2026-06-08 [python-coder/ACS-100i-1]: Created ac_parent_id.py.
    Implements derive_parent_id() per ACS-100i-1 Gherkin spec.
    Root pattern (PREFIX-NNN) returns None; alpha-level IDs strip trailing
    letters; hyphen-delimited IDs strip the last '-segment'. (#EPIC-AcParentChildLinkEnforcement/01)
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Canonical regex patterns (aligned with ADR-007)
# ---------------------------------------------------------------------------

# Root-level AC: exactly PREFIX + hyphen + three digits (no further segments).
# Examples: ACS-100, FIN-001, AUTH-007
_ROOT_PATTERN = re.compile(r"^([A-Z]{2,6})-([0-9]{3})$")

# First-letter sub-level: PREFIX-NNNx where x is one or more lowercase letters
# directly appended to the numeric part (no hyphen before the letters).
# Examples: ACS-100a, ACS-400e, FIN-001b
# The parent of ACS-100a is ACS-100 (strip trailing alpha suffix).
_ALPHA_SUBLEVEL_PATTERN = re.compile(r"^([A-Z]{2,6}-[0-9]{3})([a-z]+)$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def derive_parent_id(ac_id: str) -> str | None:
    """Derive the parent AC ID from a child AC ID by stripping the last segment.

    The derivation rules are:

    1. If *ac_id* matches the root pattern ``PREFIX-NNN`` (no additional
       segments), it has no parent — return ``None``.
    2. If *ac_id* matches the first-letter sub-level pattern ``PREFIX-NNNx``
       (where *x* is one or more lowercase letters directly appended without a
       hyphen), strip the trailing letters to derive the parent root ID.
    3. Otherwise strip the last hyphen-delimited segment (everything after the
       final ``-``).

    Args:
        ac_id: The AC identifier string to process (e.g. ``"ACS-300h-1"``).

    Returns:
        The derived parent AC ID string, or ``None`` when *ac_id* is a root AC.

    Examples::

        >>> derive_parent_id("ACS-300h-1")
        'ACS-300h'
        >>> derive_parent_id("ACS-300h-2-i")
        'ACS-300h-2'
        >>> derive_parent_id("ACS-100")
        None
        >>> derive_parent_id("ACS-100a")
        'ACS-100'
    """
    # Rule 1: root pattern — no parent.
    if _ROOT_PATTERN.match(ac_id):
        return None

    # Rule 2: first-letter sub-level (alpha suffix directly on the numeric part).
    m = _ALPHA_SUBLEVEL_PATTERN.match(ac_id)
    if m:
        return m.group(1)  # e.g. "ACS-100" from "ACS-100a"

    # Rule 3: strip last hyphen-delimited segment.
    last_hyphen = ac_id.rfind("-")
    if last_hyphen == -1:
        # Malformed ID — no hyphen at all; treat as root-equivalent.
        return None

    return ac_id[:last_hyphen]


def is_root_ac(ac_id: str) -> bool:
    """Return True when *ac_id* is a root-level AC (no parent can be derived).

    A root-level AC matches the pattern ``PREFIX-NNN`` exactly.

    Args:
        ac_id: The AC identifier to check.

    Returns:
        ``True`` when *ac_id* is a root AC, ``False`` otherwise.

    Examples::

        >>> is_root_ac("ACS-100")
        True
        >>> is_root_ac("ACS-100a")
        False
        >>> is_root_ac("ACS-100a-1")
        False
    """
    return _ROOT_PATTERN.match(ac_id) is not None
