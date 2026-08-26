"""
MODULE: unit_tests/build_orchestration/test_bo2400e_4_crlf_preservation.py
GOAL: RED test stubs pinning KI-BO-022 / KI-BO-028 -- the CRLF-preservation
    gap in scripts/build_orchestration/fast_lane.py::_update_ac_work_status
    (and the public entry points that route through it), which BO-2400e-4's
    2026-08-25 REOPENED notes record as false against the literal criterion.

BUSINESS CONTEXT: BO-2400e-4's criterion is that a progress update changes
    "the only difference between the record before and after ... is the
    value that says how far the work has got, ... every other part of the
    record keeps its original text and its original position within the
    record". The existing suite
    (test_ki_bo_003_ac_yaml_preservation.py) pins this for key order, block
    scalars, comments, and quoting -- but every one of its fixtures and
    assertions round-trips through TEXT-MODE reads/writes, so it can never
    observe a line-ending defect: a CRLF record read via
    `yaml_path.open(encoding="utf-8")` (the read side of
    `_update_ac_work_status`, fast_lane.py) and written back via
    `os.fdopen(tmp_fd, "w", encoding="utf-8")` (`_atomic_write_text`) is
    silently downgraded to LF end-to-end by Python's universal-newline
    translation, because neither call passes `newline=""`. The AC's own
    reopened notes name this exact pair of call sites.

    Exposure is honestly recorded as latent -- a 2026-08-25 store scan found
    zero CRLF records today -- but the AC was reopened precisely because the
    criterion, read literally, is false, and the population is "one
    contributor's git config away from being non-empty" (a single Windows
    tool write, under this repo's WSL2/`/mnt/c` development environment,
    would make it live).

FIXTURE-AUTHENTICITY: the base content is byte-for-byte copied from the
    real, PO-reviewed AC YAML
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/
    BO-2400a-3-i.yaml -- the same fixture the sibling KI-BO-003 suite uses,
    chosen there (and here) because it carries multi-line block scalars, an
    authored key order, and a non-empty amended_by list, none of which a
    hand-typed fixture would reproduce (project CLAUDE.md "Real-artifact
    behavioral spot-check"). Because no CRLF record exists anywhere in the
    store to copy verbatim, this file's LF endings are mechanically
    converted to CRLF -- a straight `\n` -> `\r\n` replace over the REAL
    bytes, matching what "a single Windows-tool write" (the exposure path
    the AC's notes name) would produce -- rather than hand-authoring new
    YAML content. Every value, key, comment, and block scalar is the real
    fixture's; only the line-ending byte sequence is synthesized, because
    that is the one dimension no real on-disk record currently exercises.

WHY BINARY READS: reading the result in text mode (open(..., "r"),
    encoding="utf-8") re-applies the exact universal-newline translation
    this test exists to catch, and would make a broken implementation look
    correct. Every post-condition assertion below reads the file via
    `Path.read_bytes()`.

NOT A GREP TEST: both classes below drive the real production functions
    (`claim_build_set`, `_update_ac_work_status`) and assert on the actual
    bytes written to a real temp file -- never a string search of the
    source.

Run with AC_ENFORCE_STRICT=1 to see the true (unmasked) result -- this
repo's pytest_ac_enforcement plugin otherwise xfails not-yet-done ACs:

    AC_ENFORCE_STRICT=1 python3 -m pytest \
        unit_tests/build_orchestration/test_bo2400e_4_crlf_preservation.py -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

_AC_STORE_DIR = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "build-orchestration"
    / "BO-2400-fast-lane-build"
)

# Real, PO-reviewed AC YAML -- has an authored key order, a `criteria: |`
# block scalar, a `notes: |` block scalar, and a non-empty `amended_by`
# list. Same fixture the sibling KI-BO-003 suite uses, for the same reason.
_AC_FIXTURE_SOURCE = _AC_STORE_DIR / "BO-2400a-3-i.yaml"

# ---------------------------------------------------------------------------
# Import the production functions under test.
# ---------------------------------------------------------------------------

_IMPORT_OK = False
_IMPORT_ERR = ""
claim_build_set: Any = None
_update_ac_work_status: Any = None

try:
    from fast_lane import (  # type: ignore[no-redef]
        _update_ac_work_status,
        claim_build_set,
    )
    _IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _IMPORT_ERR = str(_exc)


def _require_impl(test_case: unittest.TestCase) -> None:
    """Fail with a descriptive message when the production functions are not
    importable from fast_lane.
    """
    if not _IMPORT_OK:
        test_case.fail(
            "claim_build_set / _update_ac_work_status not importable from "
            f"fast_lane. Import error: {_IMPORT_ERR}"
        )


def _make_crlf_fixture(
    target_dir: Path, filename: str, *, work_status_before: str = "todo"
) -> bytes:
    """Write a CRLF-converted copy of the real BO-2400a-3-i.yaml fixture into
    *target_dir* and return the bytes written.

    Rewrites the fixture's own on-disk `work_status: done` to
    *work_status_before* (a realistic pre-flip state) before converting line
    endings, mirroring the sibling KI-BO-003 suite's
    `test_round_trip_twice_still_one_line_diff` pattern -- the surrounding
    document (criteria/notes blocks, amended_by list, key order) stays the
    real fixture's untouched content.

    Args:
        target_dir: Directory to write the fixture file into.
        filename: Name of the file to create.
        work_status_before: The work_status value the fixture should carry
            before any update under test is applied.

    Returns:
        The exact bytes written to disk.

    Raises:
        RuntimeError: If the source fixture is not purely LF-encoded, since
            the CRLF-count assertions in this file depend on that.
    """
    text = _AC_FIXTURE_SOURCE.read_bytes().decode("utf-8")
    if "\r\n" in text:
        raise RuntimeError(
            "Source fixture already contains CRLF line endings -- the "
            "byte-count assumptions in this test file no longer hold; pick "
            "a different LF-only real store fixture."
        )
    text = text.replace("work_status: done", f"work_status: {work_status_before}", 1)
    crlf_bytes = text.replace("\n", "\r\n").encode("utf-8")
    (target_dir / filename).write_bytes(crlf_bytes)
    return crlf_bytes


def _parse_ignoring_crlf(raw_bytes: bytes) -> dict:
    """Parse YAML from *raw_bytes*, normalising CRLF to LF first so PyYAML's
    own newline handling never confounds the value-level assertions here
    (which are deliberately separate from the byte-level CRLF assertions).
    """
    return yaml.safe_load(raw_bytes.decode("utf-8").replace("\r\n", "\n"))


# ---------------------------------------------------------------------------
# Real production entry point: claim_build_set (the fast lane's actual
# "work_status flip", dispatched by the CLI's "claim" subcommand).
# ---------------------------------------------------------------------------


class TestCrlfPreservedThroughClaimBuildSet(unittest.TestCase):
    """BO-2400e-4 / KI-BO-022: claim_build_set is the real fast-lane entry
    point that performs a work_status flip (todo -> in_progress) via
    _update_ac_work_status. This drives that PUBLIC production entry point
    directly, not the private helper -- matching the sibling KI-BO-003
    suite's own documented gap ("every test... calls _update_ac_work_status
    DIRECTLY... if BO-2400e-3's durable write repoints the three call sites
    at [a new writer], this suite goes on testing an orphaned function") --
    so a preserving fix that lands on the helper but is not actually
    reachable from every real caller is still caught here.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "ac_store"
        self.ac_root.mkdir()
        self.fixture_path = self.ac_root / "BO-2400a-3-i.yaml"
        self.original_bytes = _make_crlf_fixture(self.ac_root, "BO-2400a-3-i.yaml")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_crlf_line_endings_survive_the_real_claim_flip(self) -> None:
        # covers: BO-2400e-4
        """The record's CRLF line endings must be present in the SAME COUNT
        after claim_build_set flips work_status todo -> in_progress -- the
        real production "work_status flip" the fast lane's CLI dispatches.
        Read in BINARY: a text-mode read would re-apply the very
        universal-newline translation this test exists to catch and would
        make a broken implementation look correct.
        """
        _require_impl(self)
        before_crlf_count = self.original_bytes.count(b"\r\n")
        self.assertGreater(
            before_crlf_count,
            0,
            "Fixture setup sanity check: the CRLF-converted fixture must "
            "actually contain CRLF sequences to test against.",
        )

        result = claim_build_set(["BO-2400a-3-i"], ac_root=self.ac_root)

        self.assertTrue(
            result["success"],
            f"claim_build_set must succeed against a well-formed store: {result}",
        )
        self.assertEqual(
            result["claimed"],
            ["BO-2400a-3-i"],
            "claim_build_set must report the AC as claimed.",
        )

        after_bytes = self.fixture_path.read_bytes()

        # Value-level check FIRST: this test cannot be satisfied by a no-op
        # that simply never writes the file -- work_status really must flip.
        after_value = _parse_ignoring_crlf(after_bytes)["work_status"]
        self.assertEqual(
            after_value,
            "in_progress",
            "claim_build_set must actually flip work_status to in_progress "
            "on disk.",
        )

        after_crlf_count = after_bytes.count(b"\r\n")
        self.assertEqual(
            after_crlf_count,
            before_crlf_count,
            "Every CRLF line ending in the record must survive a "
            "work_status flip in the same count (BO-2400e-4 / KI-BO-022). "
            "_update_ac_work_status reads via "
            "yaml_path.open(encoding='utf-8') and _atomic_write_text writes "
            "via os.fdopen(tmp_fd, 'w', encoding='utf-8') -- neither passes "
            "newline='', so Python's universal-newline handling silently "
            f"downgrades CRLF to LF end-to-end. Before: {before_crlf_count} "
            f"CRLF sequences; after: {after_crlf_count}.",
        )


# ---------------------------------------------------------------------------
# Tighter, diff-shaped pin directly on the private helper the AC's reopened
# notes name explicitly.
# ---------------------------------------------------------------------------


class TestCrlfPreservedThroughDirectUpdateHelper(unittest.TestCase):
    """A tighter pin directly on _update_ac_work_status -- the function
    KI-BO-022's notes name explicitly by line reference -- mirroring the
    sibling KI-BO-003 suite's diff-based assertion style, but reading bytes
    so the assertion cannot be satisfied by a translation the text-mode
    comparison would silently undo.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.fixture_path = self.tmp_path / "BO-2400a-3-i.yaml"
        self.original_bytes = _make_crlf_fixture(self.tmp_path, "BO-2400a-3-i.yaml")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_every_line_including_the_changed_one_stays_crlf(self) -> None:
        # covers: BO-2400e-4
        """After a work_status-only update, EVERY line of the record --
        including the rewritten work_status line itself -- must still end in
        CRLF. No bare LF (a '\\n' not immediately preceded by '\\r') may
        appear anywhere in the file: a single downgraded line anywhere fails
        this, which is the strongest single-file invariant available.
        """
        _require_impl(self)

        _update_ac_work_status(self.fixture_path, "in_progress")

        after_bytes = self.fixture_path.read_bytes()

        after_value = _parse_ignoring_crlf(after_bytes)["work_status"]
        self.assertEqual(
            after_value,
            "in_progress",
            "_update_ac_work_status must actually update work_status to the "
            "new value -- a no-op write is not an acceptable way to keep "
            "CRLF intact.",
        )

        bare_lf_count = after_bytes.count(b"\n") - after_bytes.count(b"\r\n")
        self.assertEqual(
            bare_lf_count,
            0,
            "Every line ending in the record must remain CRLF after a "
            "work_status-only update -- found "
            f"{bare_lf_count} bare-LF line ending(s) introduced by the "
            "update (BO-2400e-4 / KI-BO-022 -- neither the read at "
            "yaml_path.open(encoding='utf-8') nor the write at "
            "os.fdopen(tmp_fd, 'w', encoding='utf-8') passes newline='').",
        )

    def test_ac1_diff_against_original_shows_only_crlf_endings(self) -> None:
        # covers: BO-2400e-4
        """A byte-level diff of the changed work_status line against the
        original must show the replacement line ALSO terminated by CRLF --
        i.e. the criterion's "every other part... keeps its original text
        and its original position" extends to the line-ending bytes of the
        one line that IS allowed to change, not just to the untouched lines.
        """
        _require_impl(self)
        before_lines = self.original_bytes.split(b"\r\n")

        _update_ac_work_status(self.fixture_path, "done")

        after_bytes = self.fixture_path.read_bytes()
        # If line endings survived, splitting on CRLF reproduces the same
        # number of segments as the original (one changed value, same
        # structure). If CRLF was downgraded to LF, this split collapses the
        # whole document into a single segment instead.
        after_segments = after_bytes.split(b"\r\n")
        self.assertEqual(
            len(after_segments),
            len(before_lines),
            "Splitting the updated file on CRLF must yield the same number "
            "of line-segments as the original -- if any line (including the "
            "changed work_status line) lost its CRLF terminator, this count "
            "drops sharply (in the current defective behaviour, to 1, since "
            "the whole file becomes one LF-only blob when split on CRLF). "
            f"Before: {len(before_lines)} CRLF-delimited segments; "
            f"after: {len(after_segments)}.",
        )


if __name__ == "__main__":
    unittest.main()
