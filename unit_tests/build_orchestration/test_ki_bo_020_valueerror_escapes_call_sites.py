"""
MODULE: unit_tests/build_orchestration/test_ki_bo_020_valueerror_escapes_call_sites.py
GOAL: RED-under-the-hood (XFAIL-marked) test stubs pinning the CORRECT contract
    for the three call sites of
    scripts/build_orchestration/fast_lane.py::_update_ac_work_status that
    currently leak its ValueError (KI-BO-020,
    docs/known-issues/build-orchestration.md).

THE DEFECT (KI-BO-020). `_update_ac_work_status`
(scripts/build_orchestration/fast_lane.py:130-210) deliberately raises
`ValueError` at :180-185 when an AC YAML record contains more than one
column-0 `work_status:` line -- correctly refusing to guess which line is the
real key. But all three call sites catch only `OSError`:

    - claim_build_set      -- scripts/build_orchestration/fast_lane.py:289
    - release_claim        -- scripts/build_orchestration/fast_lane.py:347
    - mark_done_built_acs  -- scripts/build_orchestration/fast_lane.py:462

so the `ValueError` escapes uncaught. Two confirmed consequences:

    1. `claim_build_set` flips records to in_progress on disk as it iterates,
       then loses its entire return payload to the escaping exception. The
       runner builds its release-on-failure list from that payload, so
       records already flipped before the bad one are never released --
       stranded in in_progress with nothing pointing at them.
    2. `release_claim` is the mechanism that un-sticks a stranded AC, and it
       aborts mid-loop on the very same exception. Every record positioned
       AFTER the offending one in the call's id list is never reached, stays
       in_progress permanently, and is then excluded from all future runs by
       filter_already_claimed. Recovery today is a hand edit.

WHY `@unittest.expectedFailure` RATHER THAN A HARD RED. This ticket's mandate
    is explicit: "Do NOT modify scripts/build_orchestration/fast_lane.py or
    any other existing file -- a concurrent build is rewriting that module
    right now." The fix (widening each `except OSError` to also catch
    `ValueError`) is therefore out of scope for this change and is NOT
    applied on this branch. A plain hard-red test here would break this
    branch's own green baseline for a fix that isn't being made in this
    branch, which is not the ask. `@unittest.expectedFailure` records the
    CORRECT target contract (each test body asserts the behaviour that
    SHOULD hold once the call sites are fixed) while keeping `pytest`'s exit
    code and file-level result green (xfailed, not failed) until that fix
    lands elsewhere.

WHAT REMOVING THE DECORATOR WILL PROVE. Once a future change widens the
    `except OSError` clauses at the three line numbers above to also catch
    `ValueError` (treating it the same way the existing OSError branch
    already does at each site -- log a warning and continue/report rather
    than propagate), removing `@unittest.expectedFailure` from each test
    below and re-running this file must show 4 passed, 0 failed. An
    `unexpected success` (XPASS) on any of these tests before that fix lands
    would itself be a signal worth investigating -- it would mean the
    described escape no longer reproduces the way KI-BO-020 documents it.

FIXTURE-AUTHENTICITY MANDATE. The base records for all four tests are
    copied byte-for-byte from real, on-disk, PO-reviewed AC YAML files in
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/ --
    never hand-typed. The two-column-0-`work_status:`-line ambiguity that
    triggers the defect is constructed by duplicating the real fixture's own
    `work_status:` line in place (see `_duplicate_work_status_line` below),
    not by hand-authoring a synthetic record. A hand-typed fixture would
    reproduce this test author's mental model of "what a broken record looks
    like" and could hide exactly the kind of format-shaped bug this
    project's CLAUDE.md "Real-artifact behavioral spot-check" convention
    exists to catch (see also
    docs/known-issues/build-orchestration.md KI-BO-003, which the sibling
    suite test_ki_bo_003_ac_yaml_preservation.py in this same directory
    documents at length). No mocks and no patched `open()` are used anywhere
    in this file -- every test drives the real functions against real files
    on a real filesystem (tempfile.TemporaryDirectory()).

Run with AC_ENFORCE_STRICT=1 to see the true (unmasked) xfail count -- this
repo's pytest_ac_enforcement plugin otherwise xfails not-yet-done ACs, which
would make it hard to tell this file's deliberate xfails apart from that
masking:

    AC_ENFORCE_STRICT=1 python -m pytest \
        unit_tests/build_orchestration/test_ki_bo_020_valueerror_escapes_call_sites.py -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring (mirrors the sibling KI-BO-003 suite in this directory).
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

# Real, on-disk, PO-reviewed AC YAML fixtures -- never hand-typed. Small,
# single-page records with exactly one column-0 `work_status:` line and no
# other occurrence of the string "work_status" anywhere in the file (verified
# by inspection), so duplicating that one line is an unambiguous edit.
_FIXTURE_FIRST = _AC_STORE_DIR / "BO-2400e-1.yaml"     # positioned first
_FIXTURE_BAD = _AC_STORE_DIR / "BO-2400c-1-i.yaml"     # positioned middle; gets the 2nd work_status: line
_FIXTURE_LAST = _AC_STORE_DIR / "BO-2400e-2.yaml"      # positioned last

# ---------------------------------------------------------------------------
# Defensive import guard. A concurrent build is actively rewriting
# fast_lane.py; if a signature or name changes underneath us, tests should
# fail with a clear, self-explaining message (still caught as the expected
# failure) rather than a bare collection-time ImportError.
# ---------------------------------------------------------------------------

_IMPORT_OK = False
_IMPORT_ERR = ""
claim_build_set: Any = None
release_claim: Any = None
mark_done_built_acs: Any = None

try:
    from fast_lane import (  # type: ignore[no-redef]
        claim_build_set,
        mark_done_built_acs,
        release_claim,
    )
    _IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _IMPORT_ERR = str(_exc)


def _require_impl(test_case: unittest.TestCase) -> None:
    """Fail with a descriptive message when the three call sites are not importable."""
    if not _IMPORT_OK:
        test_case.fail(
            "claim_build_set / release_claim / mark_done_built_acs not "
            f"importable from fast_lane. Import error: {_IMPORT_ERR}"
        )


# ---------------------------------------------------------------------------
# Real-artifact fixture construction helpers.
# ---------------------------------------------------------------------------


def _set_work_status_line(text: str, new_status: str) -> str:
    """Rewrite the single column-0 `work_status:` line's value in *text*.

    Operates on the real fixture bytes read from disk -- this is a targeted
    edit of one line, not a re-authoring of the record.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("work_status:"):
            newline_suffix = "\n" if line.endswith("\n") else ""
            lines[i] = f"work_status: {new_status}{newline_suffix}"
            break
    return "".join(lines)


def _duplicate_work_status_line(text: str) -> str:
    """Insert a second column-0 `work_status:` line directly after the first.

    This reproduces the KI-BO-020 ambiguous-record shape (the condition that
    makes `_update_ac_work_status` raise `ValueError`) by editing the real
    fixture's own line in place -- not by hand-authoring a synthetic record.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("work_status:"):
            lines.insert(i + 1, line)
            break
    return "".join(lines)


class _RealAcStoreMixin:
    """Shared real-filesystem, real-AC-YAML fixture builder for all four tests.

    Builds a temp AC store of three records -- a clean one, the malformed
    (two-`work_status:`-line) one, and another clean one, with the malformed
    record positioned in the MIDDLE of the id list so tests can distinguish
    "the loop stopped dead" (nothing after the bad record is ever touched)
    from "the loop skipped the bad record and kept going" (the correct,
    fixed behaviour).
    """

    def _build_temp_store(self, pre_status: str) -> tuple[Path, str, str, str]:
        tmp_path = Path(self._tmp.name)  # type: ignore[attr-defined]

        id_first = "BO-2400e-1"
        id_bad = "BO-2400c-1-i"
        id_last = "BO-2400e-2"

        text_first = _set_work_status_line(
            _FIXTURE_FIRST.read_text(encoding="utf-8"), pre_status
        )
        text_bad = _set_work_status_line(
            _FIXTURE_BAD.read_text(encoding="utf-8"), pre_status
        )
        text_bad = _duplicate_work_status_line(text_bad)
        text_last = _set_work_status_line(
            _FIXTURE_LAST.read_text(encoding="utf-8"), pre_status
        )

        bad_match_count = sum(
            1 for line in text_bad.splitlines() if line.startswith("work_status:")
        )
        assert bad_match_count == 2, (  # noqa: S101 -- test-setup sanity check
            "Test setup sanity check: expected exactly two column-0 "
            f"work_status: lines in the constructed bad record, got {bad_match_count}."
        )

        (tmp_path / _FIXTURE_FIRST.name).write_text(text_first, encoding="utf-8")
        (tmp_path / _FIXTURE_BAD.name).write_text(text_bad, encoding="utf-8")
        (tmp_path / _FIXTURE_LAST.name).write_text(text_last, encoding="utf-8")

        return tmp_path, id_first, id_bad, id_last

    _ID_TO_FILENAME = {
        "BO-2400e-1": _FIXTURE_FIRST.name,
        "BO-2400c-1-i": _FIXTURE_BAD.name,
        "BO-2400e-2": _FIXTURE_LAST.name,
    }

    def _read_work_status(self, ac_root: Path, ac_id: str) -> str | None:
        filename = self._ID_TO_FILENAME[ac_id]
        text = (ac_root / filename).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        return data.get("work_status") if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# 1. claim_build_set must not leak ValueError.
# ---------------------------------------------------------------------------


class TestClaimBuildSetDoesNotLeakValueError(_RealAcStoreMixin, unittest.TestCase):
    """KI-BO-020 call site 1: scripts/build_orchestration/fast_lane.py:289."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root, self.id_first, self.id_bad, self.id_last = self._build_temp_store(
            pre_status="todo"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure
    def test_claim_build_set_does_not_leak_valueerror(self) -> None:
        # covers: KI-BO-020
        """claim_build_set must not propagate ValueError to its caller.

        A malformed record (two column-0 work_status: lines) sits in the
        middle of the requested build set alongside two clean records. The
        call must return a payload -- not raise -- so the caller (the
        fast-lane runner) can still see what was claimed and decide whether
        to release it. Today this raises uncaught (KI-BO-020); the widened
        except clause at fast_lane.py:289 must come off this test once that
        lands.
        """
        _require_impl(self)
        try:
            result = claim_build_set(
                [self.id_first, self.id_bad, self.id_last], ac_root=self.ac_root
            )
        except ValueError as exc:
            self.fail(
                "claim_build_set leaked ValueError instead of catching it "
                f"(KI-BO-020, fast_lane.py:289): {exc!r}"
            )

        self.assertIsInstance(
            result,
            dict,
            "claim_build_set must return a payload dict even when one "
            "record in the batch cannot be updated.",
        )
        self.assertIn("claimed", result)
        self.assertFalse(
            result.get("success", True),
            "A batch containing a record that could not be updated must be "
            "reported as a failed run (success=False), consistent with the "
            "existing OSError-handling pattern at this same call site.",
        )


# ---------------------------------------------------------------------------
# 2. Records already flipped to in_progress must not be stranded when the
#    claim call aborts on the bad record.
# ---------------------------------------------------------------------------


class TestClaimedRecordsAreNotStrandedWhenClaimAborts(_RealAcStoreMixin, unittest.TestCase):
    """KI-BO-020 consequence 1: the lost claim payload strands flipped records."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root, self.id_first, self.id_bad, self.id_last = self._build_temp_store(
            pre_status="todo"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure
    def test_records_already_flipped_are_not_stranded_when_claim_aborts(self) -> None:
        # covers: KI-BO-020
        """No AC may be left work_status: in_progress on disk without being
        named in the returned `claimed` list.

        This is THE strand described in KI-BO-020: claim_build_set flips
        `id_first` to in_progress before it reaches the malformed `id_bad`
        record. If the ValueError then escapes, the caller never receives
        the payload naming `id_first` as claimed, so nothing downstream ever
        releases it -- it is permanently stuck. Once the call site widens its
        except clause to also catch ValueError (matching the existing
        OSError-handling shape at fast_lane.py:289, which returns
        immediately with whatever was accumulated in `claimed` so far), this
        invariant holds and the `@unittest.expectedFailure` decorator comes
        off.
        """
        _require_impl(self)
        exc_raised: ValueError | None = None
        result: dict | None = None
        try:
            result = claim_build_set(
                [self.id_first, self.id_bad, self.id_last], ac_root=self.ac_root
            )
        except ValueError as exc:
            exc_raised = exc

        in_progress_ids = [
            ac_id
            for ac_id in (self.id_first, self.id_bad, self.id_last)
            if self._read_work_status(self.ac_root, ac_id) == "in_progress"
        ]

        if exc_raised is not None:
            self.fail(
                "claim_build_set raised ValueError and returned no payload "
                f"at all, but {in_progress_ids!r} were already flipped to "
                "in_progress on disk before the exception escaped "
                f"(KI-BO-020 strand): {exc_raised!r}"
            )

        assert result is not None  # narrows type for the check below
        claimed = result.get("claimed", [])
        stranded = [ac_id for ac_id in in_progress_ids if ac_id not in claimed]
        self.assertEqual(
            stranded,
            [],
            "Records left work_status: in_progress on disk without being "
            f"reported in the returned 'claimed' list: {stranded!r}. Such "
            "records are invisible to every downstream release-on-failure "
            "path (KI-BO-020 strand).",
        )


# ---------------------------------------------------------------------------
# 3. release_claim -- the un-sticking mechanism itself -- must not abort
#    mid-loop on the bad record.
# ---------------------------------------------------------------------------


class TestReleaseClaimCompletesDespiteOneBadRecord(_RealAcStoreMixin, unittest.TestCase):
    """KI-BO-020 consequence 2: the mechanism that un-sticks a stranded AC breaks."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # release_claim releases claimed-but-not-done ACs, so the realistic
        # starting state is in_progress (as claim_build_set would have left
        # them).
        self.ac_root, self.id_first, self.id_bad, self.id_last = self._build_temp_store(
            pre_status="in_progress"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure
    def test_release_claim_completes_every_record_despite_one_bad_record(self) -> None:
        # covers: KI-BO-020
        """release_claim must still release every OTHER record even when one
        record in the middle of the list cannot be updated.

        `id_bad` sits between `id_first` and `id_last`. An implementation
        that aborts its loop on the escaping ValueError (today's behaviour)
        releases `id_first` (processed before the bad record) but never
        reaches `id_last` -- which is exactly the "everything after the
        offending record stays in_progress forever" failure KI-BO-020
        documents for this call site (fast_lane.py:347). Once the except
        clause there is widened to also catch ValueError -- matching the
        existing per-record `except OSError: ... continue` shape already
        used at this call site -- both `id_first` and `id_last` come back
        as `todo` and this test's `@unittest.expectedFailure` decorator
        comes off.
        """
        _require_impl(self)
        try:
            release_claim(
                [self.id_first, self.id_bad, self.id_last], [], ac_root=self.ac_root
            )
        except ValueError as exc:
            self.fail(
                "release_claim aborted mid-loop instead of skipping the bad "
                "record and continuing (KI-BO-020, fast_lane.py:347): "
                f"{exc!r}. id_last ({self.id_last!r}) was never reached and "
                "stays in_progress forever without this fix."
            )

        self.assertEqual(
            self._read_work_status(self.ac_root, self.id_first),
            "todo",
            "The record processed before the bad one must still be "
            "released to todo.",
        )
        self.assertEqual(
            self._read_work_status(self.ac_root, self.id_last),
            "todo",
            "The record positioned AFTER the bad one in the id list must "
            "still be released to todo -- an aborting loop leaves it "
            "permanently in_progress (KI-BO-020 consequence 2, the "
            "un-sticking mechanism itself breaking).",
        )


# ---------------------------------------------------------------------------
# 4. mark_done_built_acs must not leak ValueError.
# ---------------------------------------------------------------------------


class TestMarkDoneBuiltAcsDoesNotLeakValueError(_RealAcStoreMixin, unittest.TestCase):
    """KI-BO-020 call site 3: scripts/build_orchestration/fast_lane.py:462."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root, self.id_first, self.id_bad, self.id_last = self._build_temp_store(
            pre_status="in_progress"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure
    def test_mark_done_built_acs_does_not_leak_valueerror(self) -> None:
        # covers: KI-BO-020
        """mark_done_built_acs must not propagate ValueError to its caller.

        All three records were built and all three passed their coverage
        gate, but the malformed middle record cannot actually be flipped to
        done. The call must report that record as `skipped_uncovered` --
        the same shape the existing OSError branch at this call site already
        uses -- rather than letting the exception escape and lose the whole
        payload. The widened except clause at fast_lane.py:462 must come off
        this test once that lands.
        """
        _require_impl(self)
        built = [self.id_first, self.id_bad, self.id_last]
        covered = list(built)
        try:
            result = mark_done_built_acs(built, covered, ac_root=self.ac_root)
        except ValueError as exc:
            self.fail(
                "mark_done_built_acs leaked ValueError instead of catching "
                f"it (KI-BO-020, fast_lane.py:462): {exc!r}"
            )

        self.assertIsInstance(result, dict)
        self.assertIn("marked_done", result)
        self.assertIn("skipped_uncovered", result)
        self.assertIn(
            self.id_bad,
            result["skipped_uncovered"],
            "A record that cannot be written must be reported as "
            "skipped_uncovered, not silently disappear from the payload.",
        )
        self.assertEqual(
            self._read_work_status(self.ac_root, self.id_first),
            "done",
            "Records other than the bad one must still be marked done.",
        )
        self.assertEqual(
            self._read_work_status(self.ac_root, self.id_last),
            "done",
            "The record positioned after the bad one must still be "
            "reached and marked done -- an aborting loop would leave it "
            "unprocessed.",
        )


if __name__ == "__main__":
    unittest.main()
