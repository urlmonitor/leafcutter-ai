"""
MODULE: tests.kernel.persistence.test_gap_and_artifact_stores
GOAL: Test FileGapStore (dedup by gap key, occurrence counts, example runs, drafts) and
    FileArtifactStore (refs, hashes, safe names, no path traversal).
BUSINESS CONTEXT: Gaps feed the capability backlog without duplicates; artifact names come from
    kernel code paths fed by host input, so a hostile name must never write outside the run.
ARCHITECTURE: unittest with a TemporaryDirectory per test; stores are re-created to prove the
    data is on disk, and contract checks compare against the memory doubles.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kernel.contracts import CapabilityGap, GapType, RequestKind
from kernel.contracts.base import new_id
from kernel.persistence import (
    ArtifactStorePort,
    GapStorePort,
    InvalidArtifactName,
    MemoryGapStore,
)
from kernel.persistence.artifacts import FileArtifactStore
from kernel.persistence.fsutil import UnsafePathComponent
from kernel.persistence.gap_store import FileGapStore
from tests.kernel.helpers import narrow

RUN = "run-0123456789abcdef"


def _gap(key: str, run: str, when: datetime, count: int = 1) -> CapabilityGap:
    return CapabilityGap(
        id=new_id("gap"), gap_key=key * 8, gap_type=GapType("unsupported"), goal="g",
        normalized_need="n", request_kind=RequestKind("capability"), input_schema="i.v1",
        output_schema="o.v1", occurrence_count=count, example_run_ids=[run],
        first_seen=when, last_seen=when)


class _TempRoot(unittest.TestCase):
    """Provides a per-test run root."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class TestFileGapStore(_TempRoot):
    """FileGapStore aggregation and persistence."""

    def test_satisfies_the_port(self) -> None:
        self.assertIsInstance(FileGapStore(self.root), GapStorePort)

    def test_dedups_by_key_sums_counts_and_bounds_examples(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        store = FileGapStore(self.root)
        for i in range(7):
            store.record(_gap("a", f"run-{i}", t0 + timedelta(hours=i)))
        store.record(_gap("b", "run-x", t0, count=3))
        gaps = {g.gap_key: g for g in FileGapStore(self.root).load_gaps()}
        self.assertEqual(set(gaps), {"a" * 8, "b" * 8})
        self.assertEqual(gaps["a" * 8].occurrence_count, 7)
        self.assertEqual(len(gaps["a" * 8].example_run_ids), 5)
        self.assertEqual(gaps["b" * 8].occurrence_count, 3)
        self.assertEqual(gaps["a" * 8].first_seen, t0)

    def test_matches_the_memory_double(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        observations = [_gap("a", f"run-{i}", t0 + timedelta(hours=i)) for i in range(3)]
        memory, files = MemoryGapStore(), FileGapStore(self.root)
        for obs in observations:
            memory.record(obs)
            files.record(obs)
        self.assertEqual(files.load_gaps(), memory.load_gaps())

    def test_replayed_observation_is_not_double_counted(self) -> None:
        store = FileGapStore(self.root)
        gap = _gap("a", "run-1", datetime(2026, 1, 1, tzinfo=UTC))
        store.record(gap)
        store.record(gap)
        self.assertEqual(store.load_gaps()[0].occurrence_count, 1)

    def test_unreadable_line_is_skipped(self) -> None:
        store = FileGapStore(self.root)
        store.record(_gap("a", "run-1", datetime(2026, 1, 1, tzinfo=UTC)))
        with open(store.observations_file, "ab") as handle:
            handle.write(b"{torn")
        self.assertEqual(len(store.load_gaps()), 1)
        store.record(_gap("b", "run-2", datetime(2026, 1, 2, tzinfo=UTC)))
        self.assertEqual(len(store.load_gaps()), 2)

    def test_draft_is_written_under_the_gap_key_only(self) -> None:
        store = FileGapStore(self.root)
        gap = _gap("c", "run-1", datetime(2026, 1, 1, tzinfo=UTC))
        ref = store.write_draft(gap, "# draft\n")
        self.assertEqual(ref, f"drafts/{gap.gap_key}.md")
        self.assertEqual((store.gaps_dir / ref).read_text(encoding="utf-8"), "# draft\n")
        hostile = gap.model_copy(update={"gap_key": "../../escape"})
        with self.assertRaises(UnsafePathComponent):
            store.write_draft(hostile, "x")


class TestFileArtifactStore(_TempRoot):
    """FileArtifactStore refs, reads and path safety."""

    def test_satisfies_the_port(self) -> None:
        self.assertIsInstance(FileArtifactStore(self.root), ArtifactStorePort)

    def test_write_returns_ref_hash_size_and_absolute_path(self) -> None:
        store = FileArtifactStore(self.root)
        ref = store.write_artifact(RUN, "report.md", "hello")
        self.assertEqual(ref.ref, "report.md")
        self.assertEqual(ref.sha256, hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(ref.size_bytes, 5)
        self.assertTrue(Path(narrow(ref.path)).is_absolute())
        self.assertEqual(store.absolute_path(RUN, "report.md"), ref.path)
        self.assertEqual(FileArtifactStore(self.root).read_artifact(RUN, "report.md"), b"hello")

    def test_bytes_content_and_overwrite(self) -> None:
        store = FileArtifactStore(self.root)
        store.write_artifact(RUN, "b.bin", b"\x00\x01")
        store.write_artifact(RUN, "b.bin", b"\x02")
        self.assertEqual(store.read_artifact(RUN, "b.bin"), b"\x02")

    def test_unknown_ref_is_a_key_error_and_has_no_path(self) -> None:
        store = FileArtifactStore(self.root)
        with self.assertRaises(KeyError):
            store.read_artifact(RUN, "missing.md")
        self.assertIsNone(store.absolute_path(RUN, "missing.md"))

    def test_hostile_names_are_rejected_and_nothing_escapes(self) -> None:
        store = FileArtifactStore(self.root)
        for bad in ("../x", "a/b", "a\\b", "/abs", "C:\\x", "", ".hidden", "x" * 200):
            with self.subTest(name=bad), self.assertRaises(InvalidArtifactName):
                store.write_artifact(RUN, bad, "x")
            with self.subTest(read=bad), self.assertRaises(InvalidArtifactName):
                store.read_artifact(RUN, bad)
        self.assertFalse(list(self.root.parent.glob("x*.md")))
        with self.assertRaises(UnsafePathComponent):
            store.write_artifact("../run", "a.md", "x")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Gap and artifact stores share one file because both need only a temp run root.
#   (#KernelBootstrapV0/P2)
# ====================================================================
