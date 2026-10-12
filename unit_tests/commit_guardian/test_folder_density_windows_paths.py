"""
MODULE: unit_tests/commit_guardian/test_folder_density_windows_paths.py
COVERS: GE-133a-1 -- a folder key built by str(Path(...).parent) on Windows uses
backslashes; ground_for must still match declared forward-slash paths by whole
path components.
"""

from __future__ import annotations

import sys
from pathlib import Path

_CG_DIR = Path(__file__).resolve().parents[2] / "templates" / "scripts" / "commit_guardian"
sys.path.insert(0, str(_CG_DIR))

from _density_set_aside import ground_for  # noqa: E402

ENTRIES = [("docs/decisions", "g")]


def test_ground_for_matches_backslash_folder_keys() -> None:
    # covers: GE-133a-1
    # angle: boundary
    """A backslash-separated folder (as Windows Path gives) equals or lies beneath a
    declared forward-slash path; a lookalike sibling is still not inside."""
    bs = chr(92)  # a literal backslash, as str(Path(...).parent) yields on Windows
    assert ground_for(f"docs{bs}decisions", ENTRIES) == "g"
    assert ground_for(f"docs{bs}decisions{bs}sub", ENTRIES) == "g"
    assert ground_for(f"docs{bs}decisions-archive", ENTRIES) is None
    # forward-slash forms keep working
    assert ground_for("docs/decisions", ENTRIES) == "g"
    assert ground_for("docs/decisions/sub", ENTRIES) == "g"
    assert ground_for("docs/decisions-archive", ENTRIES) is None
