"""
MODULE: unit_tests/build_orchestration/test_bo2400e_3_i_unwritable_store.py
GOAL: RED behavioral tests pinning the BO-2400e-3-i contract -- "A store that
    cannot be written is announced, and the build does not carry on as if it
    had been" -- for the fast-lane CLI (scripts/build_orchestration/fast_lane.py
    main(), subcommand "claim") and its underlying claim_build_set /
    _update_ac_work_status call chain.

BUSINESS CONTEXT: BO-2400e-3-i covers the case where a progress write can
    NEVER succeed (the store location is read-only). The dangerous outcome is
    not the failure itself but the run continuing past it as though the
    progress had been recorded. CLAUDE.md Rule 3 forbids "log at WARNING and
    return" as a substitute for re-raising / halting -- that pattern is
    exactly what main()'s "claim" subcommand does today:

        claim_result = claim_build_set(to_build, ac_root=ac_root)
        claim_payload = {
            "claimed": claim_result["claimed"],
            "excluded_claimed": excluded_claimed,
            "target_refused": False,
        }
        print(json.dumps(claim_payload))
        return 0                                   # <-- ALWAYS 0

claim_build_set's own "success"/"error" fields (which DO carry the AC id and
    the underlying OS reason) are read from the dict and then silently
    discarded -- the printed JSON has no "success" or "error" key at all, and
    the exit code is 0 regardless of whether the write ever happened. Any
    caller of this CLI (fast-lane-build.js) that checks only the exit code,
    as main()'s own docstring says it should ("claim: 0 when ACs are claimed
    successfully; 1 when target_refused ... or an I/O error occurs"), will
    proceed to dispatch test-writer/coder against ACs that were never
    actually claimed.

TESTABILITY NOTE (mandatory per BO-2400e-3-i.yaml constraints): the read-only
    destination is a GENUINE temp directory with real permission bits changed
    via os.chmod -- both the containing directory (blocks creating any new
    temp/companion file) and the target file itself (blocks a direct
    truncating open()) are made unwritable, so the assertions hold regardless
    of which safe-write strategy BO-2400e-3 lands on. No open() is patched.

FIXTURE-AUTHENTICITY MANDATE: the AC record used as the write target is a
    byte-for-byte copy of the real, on-disk, PO-reviewed
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/
    BO-2400e-3.yaml.

Run with AC_ENFORCE_STRICT=1 to see the true (unmasked) result:

    AC_ENFORCE_STRICT=1 python3 -m pytest \\
        unit_tests/build_orchestration/test_bo2400e_3_i_unwritable_store.py -v
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

_SCRIPT_PATH = _MODULE_DIR / "fast_lane.py"

_AC_STORE_DIR = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "build-orchestration"
    / "BO-2400-fast-lane-build"
)
_AC_FIXTURE_SOURCE = _AC_STORE_DIR / "BO-2400e-3.yaml"
_AC_ID = "BO-2400e-3"

_IMPORT_OK = False
_IMPORT_ERR = ""
claim_build_set: Any = None

try:
    from fast_lane import claim_build_set  # type: ignore[no-redef]

    _IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _IMPORT_ERR = str(_exc)


def _require_impl(test_case: unittest.TestCase) -> None:
    if not _IMPORT_OK:
        test_case.fail(f"claim_build_set not importable from fast_lane. Import error: {_IMPORT_ERR}")


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run fast_lane.py as a real CLI subprocess; return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


class _UnwritableStoreCase(unittest.TestCase):
    """Shared setup: a genuinely read-only temp AC store containing one real
    AC record whose progress write can never succeed.
    """

    # KNOWN-DEFECT FIX (found while implementing BO-2400e-3, 2026-08-25): this
    # setUp originally hardcoded
    # ``real_text.replace("work_status: in_progress", "work_status: todo", 1)``
    # on the assumption that the real, on-disk BO-2400e-3.yaml fixture is
    # always currently in_progress while this ticket is being built. That
    # assumption does not hold across the live store's actual lifecycle (the
    # AC can legitimately be released back to todo between when this suite
    # was authored and when it runs), so the fixed-string match silently
    # stopped finding anything and the setup-sanity-check AssertionError
    # fired on every test in this class -- a false RED unrelated to the
    # unwritable-store contract these tests exist to pin. The fix below
    # locates whatever the CURRENT column-0 work_status line actually is and
    # rewrites its value to todo, rather than assuming one specific prior
    # value -- still exactly one line rewritten, no other byte fabricated.
    _WORK_STATUS_LINE_RE = re.compile(r"^work_status:.*$", re.MULTILINE)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name)
        self.record_path = self.ac_root / f"{_AC_ID}.yaml"
        real_text = _AC_FIXTURE_SOURCE.read_text(encoding="utf-8")
        match = self._WORK_STATUS_LINE_RE.search(real_text)
        if match is None:
            raise AssertionError(
                "Test setup sanity check: expected to find a column-0 "
                "'work_status:' line in the real BO-2400e-3.yaml fixture "
                "to rewrite to the todo precondition."
            )
        todo_text = real_text[: match.start()] + "work_status: todo" + real_text[match.end() :]
        self.record_path.write_text(todo_text, encoding="utf-8")
        self.original_bytes = self.record_path.read_bytes()
        self.original_dir_listing = sorted(p.name for p in self.ac_root.iterdir())

        # Make the write genuinely impossible under ANY safe-write strategy:
        # - file itself read-only blocks a direct truncating open("w")
        # - directory read-only (minus execute) blocks creating/renaming any
        #   companion/temp file used by a future atomic-write implementation
        os.chmod(self.record_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        os.chmod(self.ac_root, stat.S_IRUSR | stat.S_IXUSR)

    def tearDown(self) -> None:
        # Restore write permission before cleanup so TemporaryDirectory can
        # actually remove the tree.
        os.chmod(self.ac_root, stat.S_IRWXU)
        if self.record_path.exists():
            os.chmod(self.record_path, stat.S_IRWXU)
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# Announcement contract
# ---------------------------------------------------------------------------


class TestUnwritableStoreFailureIsAnnounced(_UnwritableStoreCase):
    def test_unwritable_store_failure_is_announced_with_requirement_and_reason(self) -> None:
        # covers: BO-2400e-3-i
        """Driving the REAL CLI surface (subcommand "claim"), the emitted
        output must name the failing requirement AND the underlying reason
        the write could not be made -- not a generic failure line, and not
        silence.

        RED today: main()'s "claim" subcommand discards claim_build_set's
        "error" field entirely; the printed JSON has no "error" key and no
        mention of BO-2400e-3 or the permission failure anywhere in stdout
        or stderr.
        """
        exit_code, stdout, stderr = _run_cli(
            ["claim", "--ac-ids", _AC_ID, "--ac-root", str(self.ac_root)]
        )
        combined = stdout + stderr
        self.assertIn(
            _AC_ID,
            combined,
            "The failure announcement must name the requirement it was "
            f"recording (BO-2400e-3-i). CLI output: {combined!r}",
        )
        reason_keywords = ("permission", "denied", "errno", "oserror", "read-only")
        self.assertTrue(
            any(keyword in combined.lower() for keyword in reason_keywords),
            "The failure announcement must carry the underlying reason the "
            "write could not be made (BO-2400e-3-i), not a generic message. "
            f"CLI output: {combined!r}",
        )


# ---------------------------------------------------------------------------
# No-mutation contract
# ---------------------------------------------------------------------------


class TestNoRecordChangedWhenWriteCannotBeMade(_UnwritableStoreCase):
    def test_no_record_is_changed_when_the_write_cannot_be_made(self) -> None:
        # covers: BO-2400e-3-i
        """Every record in the store must be byte-identical to its
        pre-attempt content after a failed claim attempt against an
        unwritable store.
        """
        _run_cli(["claim", "--ac-ids", _AC_ID, "--ac-root", str(self.ac_root)])

        # Restore permission only to READ the file back for comparison.
        os.chmod(self.record_path, stat.S_IRUSR)
        after = self.record_path.read_bytes()
        self.assertEqual(
            after,
            self.original_bytes,
            "No record may be changed when the write cannot be made at all "
            "(BO-2400e-3-i).",
        )


# ---------------------------------------------------------------------------
# No-debris contract
# ---------------------------------------------------------------------------


class TestNoLeftoverFragmentRemains(_UnwritableStoreCase):
    def test_no_leftover_fragment_remains_in_the_store(self) -> None:
        # covers: BO-2400e-3-i
        """The set of files present in the store directory after a failed
        attempt must equal the set present before it -- no staged companion
        or temp file left behind.

        This becomes newly reachable once BO-2400e-3's durable write lands:
        a design that stages a replacement file and then fails to rename it
        over the destination would turn a failed attempt into debris in a
        directory whose contents are themselves the build system's source
        of truth.
        """
        _run_cli(["claim", "--ac-ids", _AC_ID, "--ac-root", str(self.ac_root)])

        # Restore directory read permission enough to list it (already have
        # read+execute from setUp; execute lets us stat entries, read lets
        # us list names).
        after_listing = sorted(p.name for p in self.ac_root.iterdir())
        self.assertEqual(
            after_listing,
            self.original_dir_listing,
            "No leftover fragment may remain in the store directory after a "
            f"failed write attempt (BO-2400e-3-i). Before: "
            f"{self.original_dir_listing}, after: {after_listing}",
        )


# ---------------------------------------------------------------------------
# Control-flow (does-not-proceed) contract
# ---------------------------------------------------------------------------


class TestBuildDoesNotProceedAsThoughProgressRecorded(_UnwritableStoreCase):
    def test_build_does_not_proceed_as_though_progress_was_recorded(self) -> None:
        # covers: BO-2400e-3-i
        """Driving the REAL CLI surface against the unwritable store, the
        run must NOT report success -- the step that follows progress
        recording (dispatching test-writer/coder against the "claimed" ACs)
        must never be reached as though the claim had gone through.

        RED today: main()'s "claim" subcommand unconditionally
        `return 0` after calling claim_build_set, regardless of
        claim_result["success"]. An implementation that logs the failure
        and returns normally (the CLAUDE.md Rule 3 anti-pattern this AC
        exists to forbid) passes the announcement/no-mutation/no-debris
        tests above and fails only this one.
        """
        exit_code, stdout, _stderr = _run_cli(
            ["claim", "--ac-ids", _AC_ID, "--ac-root", str(self.ac_root)]
        )

        self.assertNotEqual(
            exit_code,
            0,
            "The CLI must not exit 0 when the progress write could not be "
            "made at all (BO-2400e-3-i) -- a zero exit tells the caller it "
            "is safe to proceed as though the AC had been claimed. "
            f"stdout={stdout!r}",
        )

        # Belt-and-braces: even if some future refactor changes the exit
        # code convention, the printed payload itself must never claim the
        # AC was claimed.
        try:
            payload = json.loads(stdout) if stdout.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        claimed = payload.get("claimed", [])
        self.assertNotIn(
            _AC_ID,
            claimed,
            "The printed result must not list the AC as claimed when its "
            f"write could not be made (BO-2400e-3-i). Payload: {payload!r}",
        )

    def test_claim_build_set_reports_failure_directly(self) -> None:
        # covers: BO-2400e-3-i
        """Sanity check at the function level (not just the CLI): calling
        claim_build_set directly against the unwritable store must return
        success=False and must NOT include the AC in "claimed" -- confirming
        the CLI-level bug above is a control-flow discard bug in main(),
        not a false negative anywhere else in the chain.
        """
        _require_impl(self)
        result = claim_build_set([_AC_ID], ac_root=self.ac_root)
        self.assertFalse(
            result["success"],
            "claim_build_set must report success=False when the underlying "
            f"write cannot be made (BO-2400e-3-i). Got: {result!r}",
        )
        self.assertNotIn(
            _AC_ID,
            result["claimed"],
            f"claim_build_set must not list {_AC_ID} as claimed when its "
            f"write failed (BO-2400e-3-i). Got: {result!r}",
        )


if __name__ == "__main__":
    unittest.main()
