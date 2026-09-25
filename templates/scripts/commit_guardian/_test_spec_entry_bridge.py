"""
MODULE: _test_spec_entry_bridge
GOAL: Reuse scripts/ac_store/_ac_schema_test_spec_validators.py's
    test_spec_entry_errors() from the commit-guardian hook tree, across every
    layout check_ac_schema.py runs in.
BUSINESS CONTEXT: TQ-500f-1 / TQ-500f-2-i require check_ac_schema.py -- the
    REAL commit gate, not only the standalone validate_ac_schema.py CLI --
    to name the offending test_spec entry, the field 'angle'/'must_catch',
    and (for must_catch) which rule failed. Reimplementing that logic here
    would fork it from the one copy validate_ac_schema.py already uses; this
    bridge reuses it instead (one implementation, two callers).
ARCHITECTURE: A sibling module inside templates/scripts/commit_guardian/ --
    deploys purely by being a sibling of check_ac_schema.py (the same whole-
    directory-copy mechanism _ac_store_locator.py's own docstring documents),
    so it needs no entry of its own in any hardcoded deploy_map. Resolves
    ac_store onto sys.path via the existing _ac_store_locator sibling (the
    same resolver check_done_proof.py already uses for `done_proof`), then
    imports the real validator. Fails open (returns []) when the sibling
    ac_store cannot be resolved -- e.g. a templates/ source-tree layout whose
    deploy-source ac_store/ stub holds no .py files -- per this hook
    family's fail-open posture (check_ac_schema.py's own ARCHITECTURE note),
    but per GE-120a-1's "_emit_could_not_check" precedent (see
    check_ac_parent_covered_by.py) that posture must be LOUD, not silent: the
    ImportError branch below prints one reader-actionable WARNING to stderr,
    at module-import time (so exactly once per hook run, never once per
    file), naming the unreachable module and that entry-naming validation
    did not run. The unresolvable-directory case and the resolvable-
    directory-missing-module case both surface as the same ImportError here
    (ensure_ac_store_on_syspath() is a documented no-op when it finds
    nothing, so the later `from _ac_schema_test_spec_validators import ...`
    raises identically either way), so one except branch covers both.

DECISION HISTORY:
  - 2026-09-25 [python-coder/TQ-500f-1, TQ-500f-2-i]: Created after a review
    finding that the entry-naming checks landed only in validate_ac_schema.py
    (the standalone CLI), leaving the real commit gate emitting jsonschema's
    generic message. Split into its own sibling (rather than inlined into
    check_ac_schema.py, already over its 400-line ratchet limit at HEAD) so
    the wiring costs that file only an import line and a call line.
  - 2026-09-25 [python-coder/TQ-500f-2-i round 2]: A second review found the
    ImportError branch printed nothing -- fail-open but silent, unlike this
    hook family's established "WARNING: ... validation was SKIPPED" posture.
    Added a one-time stderr WARNING at module scope naming the missing
    module and that entry-naming validation did not run; exit behaviour is
    unchanged (this module never contributes to the error list itself).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _ac_store_locator import ensure_ac_store_on_syspath

ensure_ac_store_on_syspath()

try:
    from _ac_schema_test_spec_validators import (  # type: ignore[import]
        test_spec_entry_errors as _shared_test_spec_entry_errors,
    )
except ImportError as _import_exc:
    _shared_test_spec_entry_errors = None
    print(
        "[check-ac-schema] WARNING: could not import "
        f"_ac_schema_test_spec_validators ({_import_exc}); "
        "test_spec[].angle/.must_catch entry-naming validation did not run "
        "(generic jsonschema validation is unaffected).",
        file=sys.stderr,
    )


def test_spec_entry_errors(
    path: Path, data: dict[str, Any], schema: dict[str, Any] | None
) -> list[str]:
    """Return test_spec[].angle/.must_catch entry-naming errors, or [] if unavailable.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        data: Parsed YAML content.
        schema: Parsed config/ac_store_schema.json content, or None.

    Returns:
        Error message strings from the shared validator, or an empty list
        when scripts/ac_store/_ac_schema_test_spec_validators.py could not
        be resolved (fail-open, per this hook family's posture -- a WARNING
        naming the missing module was already printed once, at import time).
    """
    if _shared_test_spec_entry_errors is None:
        return []
    return _shared_test_spec_entry_errors(path, data, schema)
