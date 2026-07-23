"""
MODULE: test_next_diagram_seq
GOAL: Regression test for BP-1401 — next_seq() must scan the diagrams/
      subdirectory recursively, not just the top level of docs/architecture/.
BUSINESS CONTEXT: C4 diagram files live in docs/architecture/diagrams/, but
      next_seq() was using a non-recursive Path.glob() anchored at arch_dir
      (docs/architecture/).  The top level of docs/architecture/ has zero
      c{level}-NNN-*.md files, so the glob matched nothing and next_seq()
      returned 1 for every level regardless of how many diagrams already
      existed — guaranteeing sequence-number collisions.
ARCHITECTURE: Uses importlib.util.spec_from_file_location to load the script
      as a module without executing the __main__ guard.  Builds a temporary
      directory tree that mirrors the real on-disk layout (architecture/ with a
      diagrams/ subdirectory) so the test is a real-artifact behavioral test
      rather than a synthetic one.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading — mirrors the convention used throughout unit_tests/
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "next_diagram_seq.py"
)


def _load_module():
    """Load next_diagram_seq as a module without executing the __main__ guard."""
    spec = importlib.util.spec_from_file_location("next_diagram_seq", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    _mod = _load_module()
    MODULE_AVAILABLE = True
    _load_error = ""
except Exception as exc:  # noqa: BLE001 — discovery error
    MODULE_AVAILABLE = False
    _load_error = str(exc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@unittest.skipUnless(MODULE_AVAILABLE, f"next_diagram_seq not loadable: {_load_error}")
class TestNextSeqSubdirectoryLayout(unittest.TestCase):
    """BP-1401: next_seq() must discover diagrams in the diagrams/ subdirectory.

    The real on-disk layout is:
        docs/architecture/            ← arch_dir (no c{level}-*.md files here)
            diagrams/                 ← subdirectory where ALL diagrams live
                c3-001-foo.md
                c3-002-bar.md
                c2-001-baz.md

    The bug: next_seq() called arch_dir.glob("c3-*.md") which scans ONLY the
    top level — finding nothing — and returned 1 regardless of existing diagrams.
    The fix requires a recursive scan (rglob or deeper glob).
    """

    def setUp(self) -> None:
        # Build a temporary directory tree that exactly mirrors the real layout.
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)

        # arch_dir = <tmp>/architecture/   (no diagram files at this level)
        self.arch_dir = tmp / "architecture"
        self.arch_dir.mkdir()

        # diagrams/ subdirectory — this is where every real C4 diagram lives
        diagrams_dir = self.arch_dir / "diagrams"
        diagrams_dir.mkdir()

        # Populate with two c3 diagrams and one c2 diagram so we can test
        # both a level with multiple files and a level with a single file.
        (diagrams_dir / "c3-001-interactive-pause-resume-run-lifecycle.md").write_text(
            "# c3-001 placeholder\n", encoding="utf-8"
        )
        (diagrams_dir / "c3-002-interactive-pause-resume-sequence.md").write_text(
            "# c3-002 placeholder\n", encoding="utf-8"
        )
        (diagrams_dir / "c2-001-ac-driven-pipeline.md").write_text(
            "# c2-001 placeholder\n", encoding="utf-8"
        )

        # Deliberately place NOTHING matching c{level}-*.md at the top level of
        # arch_dir — this mirrors the real repository and is the trigger for the bug.
        # (Other non-diagram markdown files may exist at the top level in prod.)
        (self.arch_dir / "agent_knowledge_plane.md").write_text(
            "# prose doc — must NOT be picked up by next_seq\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_ac1_next_seq_finds_diagrams_in_subdirectory(self) -> None:
        # covers: BP-1401
        """BP-1401: next_seq(3, arch_dir) must return 3 when c3-001 and c3-002
        exist in the diagrams/ subdirectory.

        The non-recursive glob bug causes next_seq to see zero c3 files at the
        top level and return 1 instead of the correct answer (max=002, +1 = 3).

        To make this test GREEN the fix must make next_seq scan recursively
        (e.g. arch_dir.rglob("c3-*.md")) so it finds diagrams wherever they
        live under arch_dir.
        """
        result = _mod.next_seq(3, self.arch_dir)
        self.assertEqual(
            result,
            3,
            msg=(
                f"next_seq(3, arch_dir) returned {result!r} but expected 3. "
                "The c3 diagrams live in arch_dir/diagrams/ and the non-recursive "
                "glob at arch_dir sees nothing there, so it falls back to 1. "
                "The fix must use a recursive scan."
            ),
        )

    def test_ac1_next_seq_returns_one_for_unseen_level(self) -> None:
        # covers: BP-1401
        """BP-1401: next_seq(4, arch_dir) must return 1 when no c4 diagrams exist.

        This guards against a naive fix that hard-codes the expected result.
        A level with no existing diagrams at all must still return 1.
        """
        result = _mod.next_seq(4, self.arch_dir)
        self.assertEqual(
            result,
            1,
            msg=(
                f"next_seq(4, arch_dir) returned {result!r} but expected 1. "
                "No c4 diagrams exist in the fixture tree; the function must "
                "return 1 (the first available sequence number) for an empty level."
            ),
        )


if __name__ == "__main__":
    unittest.main()
