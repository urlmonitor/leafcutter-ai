"""
MODULE: unit_tests/commit_guardian/test_folder_density_shipped_declaration.py
COVERS: GE-133a-1 -- the SHIPPED set_aside_locations declaration, unmodified.

A real ``git commit`` in a scratch repo whose pre-commit hook runs the DEPLOYED
check_folder_density.py with the deployed commit_guardian.json copied
UNMODIFIED out of shared_reference_layout (see _ge_133a_harness.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_133a_harness import FAMILY, Scratch, deployed_guardian, make_files, too_dense  # noqa: E402

STORE_GROUND = (
    "Holds acceptance-criteria records that tools read and write and nobody navigates by hand. "
    "It is flat by design, one folder per feature family, and its folders are bounded by the "
    "AC store's tree limits rather than by a file count."
)
DECISIONS_GROUND = (
    "Holds kernel decision records, one file per decision, written and read by the kernel's "
    "publish, index and precedent tools; people review records in PRs, not by browsing the folder."
)


@pytest.mark.shared_layout_reader
def test_shipped_declaration_sets_aside_both_record_stores(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-133a-1
    # angle: deployed
    """The shipped declaration sets aside docs/decisions/ and docs/acceptance-criteria/,
    each reported with its AC-worded ground; a lookalike folder is still judged."""
    s = Scratch(shared_reference_layout, tmp_path)
    # Restore the deployed configuration byte-for-byte (Scratch swaps in a scratch declaration).
    s.config.write_bytes((deployed_guardian(shared_reference_layout) / "commit_guardian.json").read_bytes())
    make_files(s.repo, "docs/decisions", 15, tag="dec")
    make_files(s.repo, FAMILY, 15)
    make_files(s.repo, "docs/decisions-archive", 15, tag="old")
    s.baseline()
    make_files(s.repo, "docs/decisions", 2, tag="dec", start=100)
    make_files(s.repo, FAMILY, 4, start=100)
    make_files(s.repo, "docs/decisions-archive", 1, tag="new", start=900)
    rc, out = s.commit()
    named = too_dense(out)
    assert set(named) == {"docs/decisions-archive"}, f"only the lookalike may be judged, got {named!r}: {out!r}"
    assert named["docs/decisions-archive"] == 16
    assert rc != 0, f"lookalike folder was not refused: {out!r}"
    assert f"docs/decisions/ set aside: {DECISIONS_GROUND}" in out, f"decisions not set aside with its ground: {out!r}"
    assert f"{FAMILY}/ set aside: {STORE_GROUND}" in out, f"store folder not set aside with its ground: {out!r}"
    assert "2 folders set aside" in out, out
