"""
MODULE: _ac_store_file_discovery
GOAL: Discover AC YAML files under docs/acceptance-criteria/ for
    check_ac_schema.py's cross-file lookup index, when the cached
    _ac_store_index module is not importable.
BUSINESS CONTEXT: check_ac_schema.py's Phase 1 cross-file checks need a
    full AC id -> parsed-record index. The preferred source is
    _ac_store_index.get_ac_index() (mtime-cached, shared across the four AC
    guardrail hooks); this module holds the direct-walk fallback path taken
    when that module cannot be imported. It therefore must NOT live inside
    _ac_store_index.py itself -- the fallback exists precisely for the case
    where that module is unavailable, so nesting it there would make the
    fallback unreachable exactly when it is needed.
ARCHITECTURE: A sibling module inside templates/scripts/commit_guardian/ --
    deploys purely by being a sibling of check_ac_schema.py (the same whole-
    directory-copy mechanism _ac_store_locator.py's own docstring documents),
    so it needs no entry of its own in any hardcoded deploy_map.

DECISION HISTORY:
  - 2026-09-25 [python-coder/TQ-500f-1, TQ-500f-2-i]: Relocated _find_ac_files
    out of check_ac_schema.py (a pure move, no behaviour change) to buy back
    check-file-size-ratchet headroom (scripts/commit_guardian/
    _file_size_ratchet.py's docstring-stripped counted length) after wiring
    in the test_spec[].angle/.must_catch entry-naming bridge pushed that
    file's counted length from 566 to 568 against its 566-line HEAD ratchet.
"""

from __future__ import annotations

from pathlib import Path

#: Same literal check_ac_schema.py's own AC_GLOB_PATTERN/_AC_STORE_DIR
#: constants hold -- duplicated here rather than imported, matching the
#: precedent _ac_store_locator.py already set (it hardcodes "ac_store"
#: directly rather than importing a constant from its caller).
_AC_GLOB_PATTERN = "docs/acceptance-criteria"


def find_ac_files(root: Path) -> list[Path]:
    """Discover all .yaml files under docs/acceptance-criteria/.

    Args:
        root: Repository root directory.

    Returns:
        Sorted list of Paths, excluding index.yaml (the component registry).
    """
    ac_dir = root / _AC_GLOB_PATTERN
    if not ac_dir.is_dir():
        return []
    return sorted(p for p in ac_dir.rglob("*.yaml") if p.name != "index.yaml")
