"""
MODULE: _covered_by_rule_bridge
GOAL: Reuse scripts/ac_store/_ac_covered_by_rule.py's covered_by_declaration_errors()
    from the commit-guardian hook tree, across every layout check_ac_schema.py runs in.
BUSINESS CONTEXT: GE-124g-1 / ADR-079 require the commit gate -- not only the
    standalone validate_ac_schema.py CLI -- to refuse a front-end declaration or
    element pin written into covered_by. Reimplementing the rule here would fork it
    from the copy the standalone validator uses; this bridge reuses it instead.
ARCHITECTURE: A sibling of check_ac_schema.py, deployed by the same whole-directory
    copy as _test_spec_entry_bridge.py, so it needs no deploy_map entry of its own.
    Resolves ac_store through _ac_store_locator, then imports the real rule. When the
    ac_store sibling cannot be resolved the bridge returns [] (this hook family's
    fail-open posture) but prints one WARNING at import time, so the skipped rule is
    loud rather than silent.

DECISION HISTORY:
  - 2026-10-23 [python-coder/GE-124g-1]: Created on the _test_spec_entry_bridge.py
    pattern so check_ac_schema.py pays only an import and a call.
    (#EPIC-EveryScreenSaysWhichRequirementItIs/44) (ADR-079)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _ac_store_locator import ensure_ac_store_on_syspath

ensure_ac_store_on_syspath()

try:
    from _ac_covered_by_rule import (  # type: ignore[import]
        covered_by_declaration_errors as _shared_errors,
    )
except ImportError as _import_exc:
    _shared_errors = None
    print(
        f"[check-ac-schema] WARNING: could not import _ac_covered_by_rule ({_import_exc}); "
        "the covered_by declaration rule (GE-124g-1) did not run.",
        file=sys.stderr,
    )


def covered_by_errors(path: Path, data: dict[str, Any]) -> list[str]:
    """Return covered_by declaration/pin errors, or [] when the shared rule is unavailable.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        data: Parsed AC record.

    Returns:
        Error strings from the shared rule; empty when it could not be resolved
        (a WARNING was already printed once, at import time).
    """
    return [] if _shared_errors is None else _shared_errors(path, data)
