"""
MODULE: _declared_files_bridge
GOAL: The one call check_ac_schema.py makes to reach the ACD-1600c-4
    declared_files seam (scripts/ac_store/declared_files.py), so that
    already-oversized file gains a single import and a single call site
    instead of carrying the seam's import-resolution and fail-open logic
    itself.
BUSINESS CONTEXT: check_ac_schema.py is already well over the
    check-file-size ratchet (400 content-lines); the ratchet forbids growing
    an already-oversized file further. All declared_files wiring beyond one
    import and one call therefore lives here instead, mirroring the same
    "carry the glue in a sibling, not the oversized file" pattern
    _ac_store_locator.py already established for check_done_proof.py's
    `done_proof` import.
ARCHITECTURE: A sibling module inside templates/scripts/commit_guardian/ --
    build_commit_guardian (scripts/build_phases_lifecycle.py) copies EVERY
    file under that directory verbatim via `cg_dir.rglob("*")` to
    <target_root>/scripts/commit_guardian/, so this file deploys purely by
    being a sibling of check_ac_schema.py, with no deploy_map entry of its
    own required (same as _ac_store_locator.py, _ac_schema_validators.py,
    _test_spec_entry_bridge.py). Resolves scripts/ac_store/declared_files.py
    via _ac_store_locator.ensure_ac_store_on_syspath() (declared_files.py is
    a sibling of done_proof.py, the module that resolver already targets) --
    never a second resolver. Fail-open: `declared_files_messages` returns
    ([], []) when the seam is unavailable, exactly as an absent
    config/ac_store_schema.json falls back to manual validation elsewhere in
    this hook family. Non-blocking reports are accumulated here (module-level
    `_PENDING_REPORTS`) and drained once by `drain_reports()`, so the caller
    does not have to thread a mutable accumulator list through its own
    per-file validation signature -- one more line check_ac_schema.py cannot
    afford to add.

DECISION HISTORY:
  - 2026-09-28 [python-coder/ACD-1600c-4]: Created. Extracted out of
    check_ac_schema.py (coordinator directive after the first pass grew it
    551 -> 589 content-lines). Reports accumulate here instead of being
    threaded through _validate_file's signature, for the same reason.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _ac_store_locator import ensure_ac_store_on_syspath  # noqa: E402

_MODULE_CACHE: dict[str, Any] = {}
_PENDING_REPORTS: list[str] = []


def _load_declared_files_module() -> Any:
    """Import the ACD-1600c-4 declared_files seam once; cache the result.

    Returns:
        The imported `declared_files` module, or None (WARNING to stderr)
        when it is not deployed alongside this hook.
    """
    if "module" in _MODULE_CACHE:
        return _MODULE_CACHE["module"]
    ensure_ac_store_on_syspath()
    try:
        import declared_files  # type: ignore[import-not-found]
    except ImportError as exc:
        print(
            f"[_declared_files_bridge] WARNING: declared_files seam "
            f"unavailable ({exc}); declared_files checks skipped.",
            file=sys.stderr,
        )
        _MODULE_CACHE["module"] = None
        return None
    _MODULE_CACHE["module"] = declared_files
    return declared_files


def declared_files_messages(record: dict[str, Any], repo_root: Path) -> list[str]:
    """Refusals for one AC record, via the declared_files seam.

    The single call check_ac_schema.py makes -- fail-open to [] when the
    seam is not deployed, so an absent module never blocks a commit for
    reasons unrelated to declared_files. Non-blocking reports are queued
    into `_PENDING_REPORTS` for `drain_reports()` rather than returned here,
    so the caller's own signature need not carry a second return value.

    Args:
        record: Parsed AC YAML content.
        repo_root: Repository root declared_files paths are checked against.

    Returns:
        Refusal messages; empty when the record has none (or the seam is
        unavailable).
    """
    module = _load_declared_files_module()
    if module is None:
        return []
    refusals, reports = module.declared_files_commit_messages(record, repo_root)
    _PENDING_REPORTS.extend(reports)
    return refusals


def drain_reports() -> list[str]:
    """Return and clear every declared_files report queued so far.

    Returns:
        The queued report strings, in the order they were queued.
    """
    reports = list(_PENDING_REPORTS)
    _PENDING_REPORTS.clear()
    return reports
