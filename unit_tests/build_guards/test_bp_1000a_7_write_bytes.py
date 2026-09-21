"""
MODULE: test_bp_1000a_7_write_bytes
GOAL: Prove that build_phases._write() emits and compares BYTES, not
    platform-translated text, so a text artifact the build deploys lands
    holding exactly its content's UTF-8 bytes on every platform.
BUSINESS CONTEXT: On Windows, `Path.write_text(content, encoding="utf-8")`
    opens in text mode with newline=None, which translates every "\n" in
    `content` to os.linesep (CRLF on Windows). `_write()`'s own
    compare-before-write guard then reads the existing file back with
    `Path.read_text(encoding="utf-8")`, which applies universal-newline
    translation ON READ ON EVERY PLATFORM -- so a CRLF-on-disk file and its
    LF-in-template content decode to the same string and compare equal. The
    divergence (CRLF vs LF) becomes permanently invisible to the guard, and a
    forced re-run reports the file "unchanged" instead of repairing it. This
    breaks check-hook-parity / check-output-drift, which diff bytes.
ARCHITECTURE: Import-based -- calls build_phases._write() directly against a
    tmpdir target (never the repo tree), per the repo's real-artifact
    spot-check convention. Each test owns its own TemporaryDirectory.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import _write  # noqa: E402

_CONTENT = (
    "line one\n"
    "line two with non-ascii: éèüñ café\n"
    "line three\n"
)


class TestWriteEmitsExactBytes(unittest.TestCase):
    """_write() must emit exactly the content's UTF-8 bytes -- no CR inserted."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_write_emits_exactly_the_bytes_of_its_content(self) -> None:
        # covers: BP-1000a-7
        # angle: criterion
        """A fresh write of LF content must land on disk with no newline
        translation applied: the file's bytes must equal content.encode("utf-8")
        exactly, with no b"\\r\\n" present. RED on Windows today because
        target.write_text(content, encoding="utf-8") opens in text mode with
        newline=None and translates "\\n" to os.linesep (CRLF on Windows).
        """
        target = self.tmp_dir / "fresh_artifact.txt"
        self.assertFalse(target.exists())

        result = _write(target, _CONTENT, dry_run=False, force=False)

        self.assertTrue(result, "expected _write to report a write occurred")
        on_disk = target.read_bytes()
        expected = _CONTENT.encode("utf-8")
        self.assertEqual(
            on_disk,
            expected,
            "on-disk bytes must be byte-identical to the content's UTF-8 "
            "encoding -- no newline translation permitted",
        )
        self.assertNotIn(
            b"\r\n",
            on_disk,
            "no CRLF sequence may appear in the written file; the content "
            "uses LF only",
        )


class TestForcedRewriteRepairsLineEndingDivergence(unittest.TestCase):
    """A forced re-run must repair a CRLF-vs-LF-only divergence, not skip it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_forced_rewrite_repairs_a_line_ending_only_divergence(self) -> None:
        # covers: BP-1000a-7
        # angle: boundary
        """Pre-create the target holding the CRLF spelling of the content
        (simulating a prior Windows write, or any prior CRLF-corrupted
        artifact), then force a rewrite. The writer must detect the
        divergence and rewrite the file to the exact LF bytes, returning
        True. THIS MUST BE RED ON EVERY PLATFORM including Linux CI: the
        current compare-before-write guard reads the existing file with
        target.read_text(encoding="utf-8"), which performs universal-newline
        translation ON READ regardless of platform, so the CRLF-on-disk file
        decodes to the same string as the LF content, the guard believes
        they are equal, and the write is skipped -- leaving the CRLF bytes
        in place.
        """
        target = self.tmp_dir / "existing_artifact.txt"
        crlf_bytes = _CONTENT.replace("\n", "\r\n").encode("utf-8")
        target.write_bytes(crlf_bytes)
        self.assertNotEqual(
            target.read_bytes(),
            _CONTENT.encode("utf-8"),
            "precondition: on-disk bytes must actually diverge from content",
        )

        result = _write(target, _CONTENT, dry_run=False, force=True)

        self.assertTrue(
            result,
            "a forced rewrite of a line-ending-only divergence must report "
            "that a write occurred, not be counted as unchanged",
        )
        self.assertEqual(
            target.read_bytes(),
            _CONTENT.encode("utf-8"),
            "after a forced rewrite the on-disk bytes must equal the "
            "content's UTF-8 encoding exactly (CRLF repaired to LF)",
        )


class TestByteIdenticalFileIsStillSkipped(unittest.TestCase):
    """A file already byte-identical to the content must still be skipped."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_byte_identical_file_is_still_skipped(self) -> None:
        # covers: BP-1000a-7
        # angle: regression
        """Pins that the byte comparison introduces no churn: a file already
        holding exactly content.encode("utf-8") must be reported as skipped
        (False) on a forced run, and its bytes must remain unchanged. This
        test is expected to PASS against current code as well as after the
        fix -- its passing is not a sign of under-specification, it pins the
        no-churn guarantee the fix must not regress.
        """
        target = self.tmp_dir / "already_correct.txt"
        target.write_bytes(_CONTENT.encode("utf-8"))
        before = target.read_bytes()

        result = _write(target, _CONTENT, dry_run=False, force=True)

        self.assertFalse(
            result,
            "a byte-identical file must be skipped (no write) on a forced "
            "re-run, to avoid mtime churn on an already-correct install",
        )
        self.assertEqual(
            target.read_bytes(),
            before,
            "bytes must remain unchanged when the write is skipped",
        )


if __name__ == "__main__":
    unittest.main()
