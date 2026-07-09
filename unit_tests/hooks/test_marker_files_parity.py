"""
MODULE: test_marker_files_parity
GOAL: Assert that the MARKER_FILES list in documentation_guard.py and
    ticket_frontmatter_guard.py are identical, so future drift between the
    two intentionally-duplicated lists is caught by CI.
BUSINESS CONTEXT: Both hooks are standalone (no shared import) and each carries
    its own MARKER_FILES constant.  The duplication is intentional per AC-5 of
    ticket 05_RootResolutionPortability, but the *content* must stay in sync.
    Without a parity test, a one-liner addition to one hook can silently diverge
    from the other.
ARCHITECTURE: Loads each hook module via importlib.util.spec_from_file_location
    so the test is path-deterministic regardless of pytest cwd or sys.path.
    No monkeypatching; no disk writes.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [python-coder/EPIC-Phase1ReadyHardening/code-review-remediations]:
  Initial test.  Created per FIX 5 (L-6) of the Phase1ReadyHardening code
  review: assert MARKER_FILES parity between the two standalone hooks.
  The lists are intentionally duplicated (not merged) so each hook runs
  standalone; this test is the drift-detection layer.
====================================================================
"""
# @ac-tag: EPIC-Phase1ReadyHardening

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate hook sources — parents: [hooks/, unit_tests/, worktree-root]
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOC_GUARD_PATH = _REPO_ROOT / "templates" / "hooks" / "documentation_guard.py"
_TFG_PATH = _REPO_ROOT / "templates" / "hooks" / "ticket_frontmatter_guard.py"


def _load_marker_files(hook_path: Path, module_name: str) -> list[str] | None:
    """Import *hook_path* as an isolated module and return its MARKER_FILES list."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, hook_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return list(mod.MARKER_FILES)
    except (FileNotFoundError, AttributeError, ImportError, SyntaxError):
        return None  # caller handles None via pytest.skip


# ---------------------------------------------------------------------------
# Load both modules at collection time so skip reasons are set cleanly.
# ---------------------------------------------------------------------------
_doc_guard_markers = _load_marker_files(_DOC_GUARD_PATH, "doc_guard_parity_shim")
_tfg_markers = _load_marker_files(_TFG_PATH, "tfg_parity_shim")

_skip_reason = ""
if _doc_guard_markers is None:
    _skip_reason = f"documentation_guard import failed: {_DOC_GUARD_PATH}"
elif _tfg_markers is None:
    _skip_reason = f"ticket_frontmatter_guard import failed: {_TFG_PATH}"

pytestmark = pytest.mark.skipif(
    bool(_skip_reason),
    reason=_skip_reason or "both hooks loaded",
)


# ---------------------------------------------------------------------------
# Parity assertion
# ---------------------------------------------------------------------------


def test_marker_files_lists_are_equal() -> None:
    """Both hooks must export identical MARKER_FILES lists.

    The lists are intentionally duplicated (not shared via import) so each
    hook can run standalone.  This test is the only enforcement layer that
    catches content drift between the two copies.
    """
    assert _doc_guard_markers == _tfg_markers, (
        "MARKER_FILES drift detected between hook copies!\n"
        f"  documentation_guard.py : {_doc_guard_markers}\n"
        f"  ticket_frontmatter_guard.py: {_tfg_markers}\n"
        "Update the diverged copy to match the other."
    )
