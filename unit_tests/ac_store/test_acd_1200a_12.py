"""
MODULE: test_acd_1200a_12
GOAL: RED test stubs for ACD-1200a-12. Verifies that generate_ticket_from_ac.py
      normalises the ``implemented_by`` back-reference to a repo-relative path
      (no leading '/', no absolute filesystem path, no worktree-specific directory
      prefix) before writing it into the AC YAML store.

      These tests are intentionally RED before the fix. The current
      _write_implemented_by at line ~1404 does:
          implemented_by.append(ticket_path)
      which stores whatever raw string is passed in, without normalisation. So an
      absolute path like '/home/testuser/worktrees/fake-wt/tickets/TICKET-test.md'
      is stored verbatim — failing both the no-leading-slash assertion (Test 1) and
      the no-worktree-prefix assertion (Test 2).

      Additionally, Test 2 passes ``worktree=<path>`` as a keyword argument to
      _write_implemented_by, which currently has no such parameter — this raises
      TypeError immediately, making Test 2 robustly RED.

TICKET: TICKET-20260720-ACD-1200a-12.md
COVERS: ACD-1200a-12
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _write_implemented_by, _normalise_repo_relative  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: create a minimal AC YAML fixture file
# ---------------------------------------------------------------------------


def _make_temp_ac_yaml(tmpdir: Path, ac_id: str) -> Path:
    """Create a minimal AC YAML file in *tmpdir* and return its Path.

    The file contains only the fields required for _write_implemented_by to
    parse without error: id, title, and work_status.

    Args:
        tmpdir: Directory in which to create the file.
        ac_id:  The AC identifier (used for the file name and the id field).

    Returns:
        Absolute path to the newly created YAML file.
    """
    data = {
        "id": ac_id,
        "title": f"Fixture AC for {ac_id}",
        "work_status": "todo",
    }
    ac_file = tmpdir / f"{ac_id}.yaml"
    ac_file.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return ac_file


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestImplementedByPathNormalisation(unittest.TestCase):
    """ACD-1200a-12: implemented_by must store a repo-relative path, never an
    absolute path or worktree-specific path.
    """

    def test_implemented_by_path_is_repo_relative(self):
        # covers: ACD-1200a-12
        """AC-1 & AC-2: stored implemented_by entry must be a repo-relative path.

        Call _write_implemented_by with an absolute ticket path.  After the call,
        read the updated YAML and assert that the stored entry does NOT start with
        '/' and is NOT an absolute filesystem path.

        Must be RED before the fix: the current implementation stores the raw
        ticket_path string verbatim (line ~1434: implemented_by.append(ticket_path)),
        so passing an absolute path results in a stored value that starts with '/'.
        assertFalse(stored.startswith('/')) will therefore FAIL.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_file = _make_temp_ac_yaml(tmp, "ACD-1200a-12-fixture-1")

            absolute_ticket_path = "/home/testuser/worktrees/fake-wt/tickets/TICKET-test.md"

            _write_implemented_by(ac_file, absolute_ticket_path, "ACD-1200a-12-fixture-1")

            data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
            implemented_by: list = data.get("implemented_by") or []

            self.assertTrue(
                len(implemented_by) >= 1,
                "Expected at least one implemented_by entry after calling "
                "_write_implemented_by, but the list is empty.",
            )

            stored = implemented_by[0]

            self.assertFalse(
                stored.startswith("/"),
                (
                    "AC-2 FAIL: The stored implemented_by entry starts with '/' — "
                    "it is an absolute filesystem path, not a repo-relative path. "
                    f"Stored value: {stored!r}. "
                    "python-coder must normalise the path to repo-relative form "
                    "(e.g. 'tickets/00_inbox/TICKET-test.md') before writing."
                ),
            )

            self.assertFalse(
                Path(stored).is_absolute(),
                (
                    "AC-1 FAIL: The stored implemented_by entry is an absolute path "
                    f"({stored!r}). It must be a repo-relative path such as "
                    "'tickets/00_inbox/TICKET-test.md'."
                ),
            )

    def test_implemented_by_path_has_no_worktree_prefix(self):
        # covers: ACD-1200a-12
        """AC-3: stored implemented_by entry must contain no worktree-specific prefix.

        Call _write_implemented_by with absolute ticket paths rooted at two
        DIFFERENT fake worktrees but pointing to the SAME repo-relative ticket path.
        Assert that:
        - stored_1 does not start with '/'
        - stored_1 does not contain '/worktrees/'
        - stored_1 == stored_2  (same entry regardless of source worktree)
        - stored_1 == 'tickets/00_inbox/TICKET-test.md'  (clean repo-relative form)

        Must be RED before the fix for TWO reasons:
        1. _write_implemented_by currently has no 'worktree' parameter — passing
           worktree=<path> as a keyword argument raises TypeError immediately.
        2. Even if the call succeeded with the current code, the raw absolute path
           would be stored and the assertions would all fail.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_file_1 = _make_temp_ac_yaml(tmp, "ACD-1200a-12-fixture-2a")
            ac_file_2 = _make_temp_ac_yaml(tmp, "ACD-1200a-12-fixture-2b")

            fake_wt1 = Path("/home/testuser/worktrees/wt-1")
            fake_wt2 = Path("/home/testuser/worktrees/wt-2")

            relative_ticket = "tickets/00_inbox/TICKET-test.md"
            abs_from_wt1 = str(fake_wt1 / relative_ticket)
            abs_from_wt2 = str(fake_wt2 / relative_ticket)

            # The 'worktree' keyword argument does not exist in the current signature.
            # This will raise TypeError with the current code, making the test RED.
            _write_implemented_by(
                ac_file_1,
                abs_from_wt1,
                "ACD-1200a-12-fixture-2a",
                worktree=fake_wt1,
            )
            _write_implemented_by(
                ac_file_2,
                abs_from_wt2,
                "ACD-1200a-12-fixture-2b",
                worktree=fake_wt2,
            )

            data_1 = yaml.safe_load(ac_file_1.read_text(encoding="utf-8"))
            data_2 = yaml.safe_load(ac_file_2.read_text(encoding="utf-8"))
            impl_1: list = data_1.get("implemented_by") or []
            impl_2: list = data_2.get("implemented_by") or []

            self.assertTrue(len(impl_1) >= 1, "Expected an implemented_by entry in AC file 1.")
            self.assertTrue(len(impl_2) >= 1, "Expected an implemented_by entry in AC file 2.")

            stored_1 = impl_1[0]
            stored_2 = impl_2[0]

            self.assertFalse(
                stored_1.startswith("/"),
                f"AC-2 FAIL: stored_1 starts with '/' — absolute path: {stored_1!r}",
            )

            self.assertNotIn(
                "/worktrees/",
                stored_1,
                (
                    "AC-3 FAIL: stored_1 contains a worktree-specific directory segment "
                    f"('/worktrees/'). Stored value: {stored_1!r}. "
                    "The recorded path must be the same repo-relative value regardless "
                    "of which worktree the generator ran in."
                ),
            )

            self.assertEqual(
                stored_1,
                stored_2,
                (
                    "AC-3 FAIL: stored_1 != stored_2 — the same logical ticket path "
                    "produced different stored values when generated from different "
                    f"worktrees. stored_1={stored_1!r}, stored_2={stored_2!r}."
                ),
            )

            self.assertEqual(
                stored_1,
                relative_ticket,
                (
                    "AC-1 & AC-3 FAIL: stored_1 is not the expected clean repo-relative "
                    f"form '{relative_ticket}'. Got: {stored_1!r}."
                ),
            )


if __name__ == "__main__":
    unittest.main()
