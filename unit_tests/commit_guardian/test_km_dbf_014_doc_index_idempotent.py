"""
MODULE: test_km_dbf_014_doc_index_idempotent
GOAL: Verify that regenerating docs/INDEX.md without any documentation change
    produces a byte-identical file (KM-DBF-014), while a genuine documentation
    change still causes the regenerated index to differ (anti-overshoot guard).
BUSINESS CONTEXT: generate_doc_index.py:340 stamps the header with
    ``datetime.now(timezone.utc)`` and docs/INDEX.md is rewritten unconditionally
    on every run. This contradicts the module's own stated intent (line ~345:
    "never to datetime.now() ... so that regenerating without source changes
    does not bump it"), which the module honours for `last_updated` / `created`
    but not for the `> Generated: {timestamp}` header line. Consequence: the
    doc-index pre-commit hook produces a diff on essentially every commit, which
    is the reliable ingredient behind "Stashed changes conflicted with hook
    auto-fixes" restore failures (see KM-DBF-014 AC notes).
ARCHITECTURE: Unit tests against generate_doc_index.write_index()/generate_index(),
    run entirely inside tempfile.TemporaryDirectory() trees. No I/O to the real
    docs/ tree. The system clock is replaced with a small fake so timing behaviour
    is deterministic rather than dependent on wall-clock minute boundaries.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Path setup: unit_tests/commit_guardian/ is 3 levels below the repo root
# (matches the existing sibling test_generate_doc_index_last_updated.py).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_doc_index as gdi  # noqa: E402


# ---------------------------------------------------------------------------
# Fake clock
# ---------------------------------------------------------------------------


class _FrozenClock:
    """Drop-in replacement for the ``datetime`` name inside generate_doc_index.

    Each call to ``.now(tz)`` returns the current internal instant and then
    advances it by ``step_minutes``. With ``step_minutes=0`` the same instant
    is returned on every call (a genuinely frozen clock, used by the
    anti-overshoot guard test). With ``step_minutes > 0`` every call returns a
    strictly later instant than the previous one, by a known fixed amount
    (used by the idempotency test) — this guarantees two generator runs are
    always far enough apart to differ under the buggy minute-granularity
    ``strftime("%Y-%m-%d %H:%M UTC")`` format, regardless of how fast the test
    process actually executes. A real-clock test would be a false-green trap:
    two fast consecutive calls can land in the same minute and the assertion
    would pass vacuously even with the bug present.
    """

    def __init__(self, start: datetime, step_minutes: int = 0) -> None:
        self._current = start
        self._step = timedelta(minutes=step_minutes)

    def now(self, tz: timezone | None = None) -> datetime:  # noqa: ARG002
        value = self._current
        self._current = self._current + self._step
        return value


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKmDbf014DocIndexIdempotent(unittest.TestCase):
    """KM-DBF-014: regenerating without doc changes must be byte-identical."""

    def test_regenerating_without_doc_changes_is_byte_identical(self) -> None:
        # covers: KM-DBF-014
        """Two consecutive write_index() runs, no doc change in between, must
        produce byte-identical output.

        Clock handling: the module's ``datetime`` name is monkeypatched with a
        ``_FrozenClock`` that advances by 2 minutes on every ``.now()`` call.
        generate_index() calls ``datetime.now(timezone.utc)`` twice per run
        (once for the header timestamp, once for the `created` fallback), so
        the second write_index() call is guaranteed to observe a clock value
        strictly later (by minutes, not by luck) than the first — this is
        deliberately controlled rather than relying on the real wall clock
        ticking over a minute boundary between two fast test calls, which
        would let this assertion pass vacuously (false green) even with the
        defect present.

        FAILS today: the `> Generated: {timestamp}` header line advances on
        the second run even though no documentation content changed, so
        content1 != content2.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "docs").mkdir(parents=True, exist_ok=True)

            fake_clock = _FrozenClock(
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), step_minutes=2
            )

            with mock.patch.object(gdi, "datetime", fake_clock):
                out1 = gdi.write_index(repo_root)
                content1 = out1.read_text(encoding="utf-8")

                # No documentation change happens here — this is the "regenerate
                # with nothing new to say" scenario the AC is about.
                out2 = gdi.write_index(repo_root)
                content2 = out2.read_text(encoding="utf-8")

        self.assertEqual(
            content1,
            content2,
            "Regenerating docs/INDEX.md with no documentation change must produce "
            "a byte-identical file. If this differs, the header timestamp (or some "
            "other field) is being stamped with the current time on every run "
            "instead of being suppressed/preserved when no doc content changed.",
        )

    def test_regeneration_still_reflects_a_changed_doc(self) -> None:
        # covers: KM-DBF-014
        """Anti-overshoot guard: when a documentation file DOES change between
        runs, the regenerated index must reflect that change.

        This guards against a fix that satisfies test 1 by the degenerate
        route of "never rewrite the file" (e.g. short-circuiting write_index()
        whenever an existing INDEX.md is present). The clock is held
        genuinely frozen (step_minutes=0, identical instant returned on every
        call) across both runs so the header/timestamp fields cannot be the
        source of any observed difference — the only variable between run 1
        and run 2 is the doc content edit itself.

        Expected to PASS both BEFORE and AFTER the KM-DBF-014 fix — it is not
        part of the red baseline, it documents the behaviour the fix must not
        break.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            how_to_dir = repo_root / "docs" / "how-to"
            how_to_dir.mkdir(parents=True, exist_ok=True)
            doc_path = how_to_dir / "sample-guide.md"
            doc_path.write_text(
                '---\ndescription: "Original description."\n---\n\n# Sample Guide\n',
                encoding="utf-8",
            )

            fixed_clock = _FrozenClock(
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), step_minutes=0
            )

            with mock.patch.object(gdi, "datetime", fixed_clock):
                out1 = gdi.write_index(repo_root)
                content1 = out1.read_text(encoding="utf-8")

                # A genuine documentation change happens here.
                doc_path.write_text(
                    '---\ndescription: "Updated description."\n---\n\n# Sample Guide\n',
                    encoding="utf-8",
                )

                out2 = gdi.write_index(repo_root)
                content2 = out2.read_text(encoding="utf-8")

        self.assertIn(
            "Original description.",
            content1,
            "First run must render the original doc description.",
        )
        self.assertNotIn(
            "Updated description.",
            content1,
            "First run must not already show the updated description.",
        )
        self.assertIn(
            "Updated description.",
            content2,
            "Second run must render the updated doc description.",
        )
        self.assertNotEqual(
            content1,
            content2,
            "Regenerating docs/INDEX.md after a real documentation change must "
            "produce different content. A fix for KM-DBF-014 that makes the "
            "generator never rewrite the file (or otherwise ignores real "
            "content changes) would be an over-correction and must fail this test.",
        )


if __name__ == "__main__":
    unittest.main()
