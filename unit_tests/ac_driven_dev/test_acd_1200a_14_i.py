"""
MODULE: unit_tests/ac_driven_dev/test_acd_1200a_14_i.py
GOAL: RED test stubs for ACD-1200a-14-i — when git rev-parse cannot resolve a
      repo root (not a git repo, or git unavailable), the back-reference write in
      _write_implemented_by must degrade to a documented fallback root WITH a
      WARNING, and must NEVER record a raw absolute filesystem path.

BUSINESS CONTEXT: This is the L3 edge-case bound for ACD-1200a-14. The parent
      AC (ACD-1200a-14) adds git-based repo-root derivation to _write_implemented_by.
      This edge case ensures that a git failure (e.g. the tickets tree is not
      inside a git repository) does not crash the generator and does not silently
      record an absolute filesystem path in the AC YAML store.

ARCHITECTURE: Tests import _write_implemented_by from generate_ticket_from_ac.py
      and monkeypatch subprocess.run to simulate git rev-parse success/failure
      without requiring a real git repository. All AC YAML fixtures live in
      isolated tempfile directories — no real AC store files are touched.

TICKET: TICKET-20260721-ACD-1200a-14-i.md
COVERS: ACD-1200a-14-i

DECISION HISTORY:
- 2026-07-21 [ACD-1200a-14-i/test-writer]: Initial RED stubs. All three tests are
  intentionally RED before the python-coder fix lands.

  RED reasons per test:
    test_git_rev_parse_failure_falls_back_with_warning:
      Current code has no subprocess call and no WARNING log statement inside
      _write_implemented_by.  assertLogs('generate_ticket_from_ac', level='WARNING')
      raises AssertionError because zero WARNING records are emitted.

    test_fallback_value_still_repo_relative_no_leading_slash:
      Current code uses _normalise_repo_relative which strips the leading '/' but
      leaves the full directory tree intact, producing a string like
      'tmp/fake-worktree/tickets/00_inbox/TICKET-test.md' instead of the expected
      clean repo-relative 'tickets/00_inbox/TICKET-test.md'. The assertEqual
      assertion therefore fails.

    test_no_fallback_when_git_resolves_repo_root:
      Current code does not call git rev-parse at all.  When worktree=None and the
      ticket_path is absolute, it falls back to _normalise_repo_relative which again
      returns the wrong path.  The assertEqual assertion fails, confirming the git-
      based derivation has not yet been implemented.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_driven_dev/ is 3 levels below the repo root.
# Path(__file__).resolve().parent         = unit_tests/ac_driven_dev/
# Path(__file__).resolve().parent.parent  = unit_tests/
# Path(__file__).resolve().parent.parent.parent = <repo root>
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _write_implemented_by  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: minimal AC YAML fixture
# ---------------------------------------------------------------------------


def _make_temp_ac_yaml(tmpdir: Path, ac_id: str) -> Path:
    """Create a minimal AC YAML file in *tmpdir* and return its Path.

    Contains only the fields _write_implemented_by needs to parse without
    error: id, title, and work_status.

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


class TestACD1200a14iGitRevParseFallback(unittest.TestCase):
    """ACD-1200a-14-i: when git rev-parse fails, _write_implemented_by must
    degrade gracefully — log a WARNING, never record a raw absolute path, and
    not propagate an exception.

    These tests are intentionally RED before the python-coder fix; they will
    turn GREEN once _write_implemented_by is extended to:
      1. Call git rev-parse --show-toplevel to derive the repo root.
      2. Catch a git failure (CalledProcessError / FileNotFoundError) and log a
         WARNING via the module's logger.
      3. Fall back to the existing repo-root helper's non-git path when git fails.
      4. Always store a repo-relative path (never a raw absolute path).
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Test 1: AC-1 — the write falls back and emits WARNING when git fails
    # ------------------------------------------------------------------

    def test_git_rev_parse_failure_falls_back_with_warning(self) -> None:
        # covers: ACD-1200a-14-i
        """AC-1: When git rev-parse --show-toplevel cannot resolve a repo root,
        _write_implemented_by must not crash and must emit a WARNING.

        Scenario: subprocess.run is patched to raise CalledProcessError (exit 128),
        simulating 'git rev-parse --show-toplevel' failing because the working
        directory is not inside a git repository.  The write must still succeed
        (no exception propagated) and must log at WARNING level.

        RED reason: The current _write_implemented_by has no subprocess call and no
        WARNING-level logging statement.  assertLogs('generate_ticket_from_ac',
        level='WARNING') will raise:
            AssertionError: no logs of level WARNING or higher triggered on logger
            'generate_ticket_from_ac'
        because zero WARNING records are emitted by the current implementation.

        Must be GREEN after python-coder adds git rev-parse + fallback + WARNING.
        """
        ac_file = _make_temp_ac_yaml(self.tmp, "ACD-1200a-14-i-f1")
        abs_ticket_path = "/tmp/fake-nonexistent-worktree/tickets/TICKET-test.md"

        with unittest.mock.patch("subprocess.run") as mock_sub:
            # Simulate git rev-parse failing with exit code 128
            mock_sub.side_effect = subprocess.CalledProcessError(
                128, ["git", "rev-parse", "--show-toplevel"]
            )

            # assertLogs FAILS if no WARNING is emitted — RED on current code
            with self.assertLogs("generate_ticket_from_ac", level="WARNING"):
                # The write must not raise (AC-1: fall back, do not crash)
                _write_implemented_by(ac_file, abs_ticket_path, "ACD-1200a-14-i-f1")

        # Confirm the entry was written (write succeeded despite git failure)
        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = data.get("implemented_by") or []
        self.assertGreaterEqual(
            len(impl_by),
            1,
            "Expected at least one implemented_by entry after the write.",
        )

        stored = impl_by[0]
        self.assertFalse(
            stored.startswith("/"),
            (
                "AC-2 early check: stored value must not be a raw absolute path; "
                f"got {stored!r}. The fallback root must produce a repo-relative path."
            ),
        )

    # ------------------------------------------------------------------
    # Test 2: AC-2 — stored value is still repo-relative (no leading /)
    # ------------------------------------------------------------------

    def test_fallback_value_still_repo_relative_no_leading_slash(self) -> None:
        # covers: ACD-1200a-14-i
        """AC-2: The recorded value via the fallback root is repo-relative with
        no leading '/' and no absolute filesystem path components.

        Specifically, the stored value must be the clean repo-relative form
        'tickets/00_inbox/TICKET-test.md', not a normalised-but-wrong string
        like 'tmp/fake-worktree/tickets/00_inbox/TICKET-test.md' (which is what
        the current _normalise_repo_relative helper produces when handed a full
        absolute path without a worktree parameter).

        RED reason: The current code uses _normalise_repo_relative which strips the
        leading '/' but preserves all intermediate directory components, yielding
        'tmp/fake-nonexistent-worktree/tickets/00_inbox/TICKET-test.md'.
        The assertEqual assertion therefore fails because the stored value is not
        'tickets/00_inbox/TICKET-test.md'.

        Must be GREEN after python-coder adds git rev-parse fallback that resolves
        the actual tickets-root ancestor and relativises correctly.
        """
        ac_file = _make_temp_ac_yaml(self.tmp, "ACD-1200a-14-i-f2")
        relative_ticket = "tickets/00_inbox/TICKET-test.md"
        abs_ticket_path = f"/tmp/fake-nonexistent-worktree/{relative_ticket}"

        with unittest.mock.patch("subprocess.run") as mock_sub:
            # Simulate git not available or not a repo
            mock_sub.side_effect = subprocess.CalledProcessError(
                128, ["git", "rev-parse", "--show-toplevel"]
            )
            # Suppress the WARNING that the fixed code will emit
            # (test 1 covers the WARNING assertion; this test focuses on stored value)
            import logging

            logging.disable(logging.CRITICAL)
            try:
                _write_implemented_by(ac_file, abs_ticket_path, "ACD-1200a-14-i-f2")
            finally:
                logging.disable(logging.NOTSET)

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = data.get("implemented_by") or []

        self.assertGreaterEqual(len(impl_by), 1, "Expected at least one implemented_by entry.")
        stored = impl_by[0]

        # Primary AC-2 assertion — must be exact repo-relative form
        # FAILS on current code: _normalise_repo_relative yields wrong path
        self.assertEqual(
            stored,
            relative_ticket,
            (
                f"AC-2 FAIL: stored implemented_by entry is not the expected repo-relative "
                f"form '{relative_ticket}'. Got {stored!r}. "
                "The fallback root must relativise correctly — not just strip the leading '/'."
            ),
        )

        # Secondary assertions (belt-and-suspenders, all pass after fix)
        self.assertFalse(
            stored.startswith("/"),
            f"AC-2: stored value must not begin with '/'; got {stored!r}.",
        )
        self.assertFalse(
            Path(stored).is_absolute(),
            f"AC-2: stored value must not be an absolute path; got {stored!r}.",
        )
        self.assertNotIn(
            "fake-nonexistent-worktree",
            stored,
            (
                "AC-2: stored value must not contain worktree-specific directory "
                f"components; got {stored!r}."
            ),
        )

    # ------------------------------------------------------------------
    # Test 3: AC-3 — no fallback (and no WARNING) when git resolves the root
    # ------------------------------------------------------------------

    def test_no_fallback_when_git_resolves_repo_root(self) -> None:
        # covers: ACD-1200a-14-i
        """AC-3: When git rev-parse does resolve a repo root, the fallback is NOT
        taken — no WARNING is logged, and the stored value is correctly relativised
        against the git-derived root (not via the fallback helper).

        Scenario: subprocess.run is patched to return a successful CompletedProcess
        whose stdout is a known fake git root.  The ticket path is absolute and
        inside that fake root.  The stored value must be the expected repo-relative
        path (not the result of _normalise_repo_relative, which would strip only the
        leading '/' leaving worktree-path components intact).

        RED reason: The current code does not call git rev-parse at all.  When
        worktree=None and ticket_path is absolute, _normalise_repo_relative strips
        the leading '/' and returns the wrong path.  The assertEqual assertion fails
        because the stored value is 'tmp/fake-git-root/tickets/00_inbox/TICKET-test.md'
        instead of 'tickets/00_inbox/TICKET-test.md'.

        Must be GREEN after python-coder adds git rev-parse logic:
        - subprocess.run is called with ['git', 'rev-parse', '--show-toplevel']
        - The returned stdout is used to relativise the absolute ticket_path
        - No WARNING is logged (git succeeded → fallback not used)
        - stored == 'tickets/00_inbox/TICKET-test.md'
        """
        ac_file = _make_temp_ac_yaml(self.tmp, "ACD-1200a-14-i-f3")
        relative_ticket = "tickets/00_inbox/TICKET-test.md"
        fake_git_root = "/tmp/fake-git-root"
        abs_ticket_path = f"{fake_git_root}/{relative_ticket}"

        with unittest.mock.patch("subprocess.run") as mock_sub:
            # Simulate git rev-parse succeeding and returning the fake root
            mock_sub.return_value = unittest.mock.MagicMock(
                returncode=0,
                stdout=f"{fake_git_root}\n",
                stderr="",
            )

            # No WARNING should be logged (git succeeded; fallback not triggered)
            # assertNoLogs raises AssertionError if any WARNING IS logged.
            # On current code: no WARNING → assertNoLogs passes. But the primary
            # RED signal is the assertEqual below.
            with self.assertNoLogs("generate_ticket_from_ac", level="WARNING"):
                _write_implemented_by(ac_file, abs_ticket_path, "ACD-1200a-14-i-f3")

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = data.get("implemented_by") or []

        self.assertGreaterEqual(len(impl_by), 1, "Expected at least one implemented_by entry.")
        stored = impl_by[0]

        # Primary AC-3 assertion: git root was used; stored == clean relative form
        # FAILS on current code: _normalise_repo_relative gives wrong path
        self.assertEqual(
            stored,
            relative_ticket,
            (
                f"AC-3 FAIL: stored value {stored!r} does not match the expected "
                f"repo-relative form '{relative_ticket}'. When git resolves a repo root "
                "the path must be relativised against it, not normalised naively."
            ),
        )

        self.assertFalse(
            stored.startswith("/"),
            f"AC-3: stored value must not begin with '/'; got {stored!r}.",
        )


if __name__ == "__main__":
    unittest.main()
