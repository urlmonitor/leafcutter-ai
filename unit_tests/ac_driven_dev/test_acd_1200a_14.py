"""
MODULE: unit_tests/ac_driven_dev/test_acd_1200a_14.py
GOAL: RED test stubs for ACD-1200a-14. Verifies that _write_implemented_by
      produces a clean repo-relative implemented_by entry even when the ticket
      path is NOT under the passed worktree directory.

BUSINESS CONTEXT: When a ticket's absolute path lies outside the passed worktree
  (e.g. the tickets-root is the main checkout, but the generator runs from a
  separate worktree directory), the current fallback in _write_implemented_by
  calls _normalise_repo_relative() which only strips a leading '/'.  The result
  is a mangled path like 'fake/checkout-alpha/tickets/00_inbox/TICKET-test.md'
  rather than the clean repo-relative form 'tickets/00_inbox/TICKET-test.md'.

  The fix must derive the repo root canonically via git rev-parse --show-toplevel
  (or a shared repo-root helper, injectable via a new ``repo_root`` parameter for
  testing), then relativise both the incoming path AND every existing
  implemented_by entry through that same repo root, not against the passed
  worktree directory.

ARCHITECTURE: Tests call _write_implemented_by directly with a temp AC YAML
  file and controlled fake absolute paths.  All three tests pass
  ``repo_root=<Path>`` as a keyword argument that does NOT currently exist in
  the function signature.  This causes TypeError immediately on the call,
  making every test robustly RED before the fix lands.

  Even if a partial fix adds the ``repo_root`` parameter but ignores it, the
  assertEqual assertions on the stored values would still fail because the
  current fallback (_normalise_repo_relative) produces a path with a
  host-specific prefix rather than the clean tickets/... form.

TICKET: TICKET-20260721-ACD-1200a-14.md
COVERS: ACD-1200a-14
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_driven_dev/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _write_implemented_by  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: create a minimal AC YAML fixture file
# ---------------------------------------------------------------------------


def _make_temp_ac_yaml(
    tmpdir: Path,
    ac_id: str,
    implemented_by: list[str] | None = None,
) -> Path:
    """Create a minimal AC YAML file in *tmpdir* and return its Path.

    Args:
        tmpdir: Directory in which to create the file.
        ac_id:  The AC identifier (used for the file name and the id field).
        implemented_by: Optional pre-existing implemented_by list to embed.

    Returns:
        Absolute path to the newly created YAML file.
    """
    data: dict = {
        "id": ac_id,
        "title": f"Fixture AC for {ac_id}",
        "work_status": "todo",
    }
    if implemented_by is not None:
        data["implemented_by"] = implemented_by
    ac_file = tmpdir / f"{ac_id}.yaml"
    ac_file.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return ac_file


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestACD1200a14OutsideWorktreeNormalisation(unittest.TestCase):
    """ACD-1200a-14: ticket path outside the worktree must still record
    a clean repo-relative implemented_by entry, using a git-derived repo root
    for relativisation rather than the passed worktree directory.
    """

    def test_ticket_outside_worktree_recorded_repo_relative(self) -> None:
        # covers: ACD-1200a-14
        """AC-1: The recorded value is still a repo-relative path with no leading '/',
        no absolute filesystem prefix, and no worktree-specific directory segment,
        even when the ticket path is NOT under the passed worktree.

        Scenario
        --------
        - fake_repo_root: /fake/main-repo
        - fake_worktree:  /fake/worktrees/some-wt  (does NOT share the ticket path)
        - ticket:         /fake/main-repo/tickets/00_inbox/TICKET-14-test.md
          → ticket is outside fake_worktree, so relative_to(fake_worktree) raises
            ValueError and the current code falls back to _normalise_repo_relative.
        - Expected stored: 'tickets/00_inbox/TICKET-14-test.md'

        MUST be RED before the fix for TWO reasons
        ------------------------------------------
        1. _write_implemented_by() does not accept 'repo_root' as a keyword
           argument yet — the call raises TypeError immediately.
        2. Even if a partial fix accepts repo_root but ignores it, the current
           fallback (_normalise_repo_relative) strips only the leading '/' and
           produces 'fake/main-repo/tickets/00_inbox/TICKET-14-test.md' rather
           than 'tickets/00_inbox/TICKET-14-test.md' — the assertEqual below fails.
        """
        fake_repo_root = Path("/fake/main-repo")
        fake_worktree = Path("/fake/worktrees/some-wt")
        abs_ticket = str(fake_repo_root / "tickets/00_inbox/TICKET-14-test.md")
        expected = "tickets/00_inbox/TICKET-14-test.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            ac_file = _make_temp_ac_yaml(Path(tmpdir), "ACD-1200a-14-fixture-1")

            # 'repo_root' is not in the current function signature.
            # This raises TypeError, making the test RED.
            _write_implemented_by(
                ac_file,
                abs_ticket,
                "ACD-1200a-14-fixture-1",
                worktree=fake_worktree,
                repo_root=fake_repo_root,  # NEW param — does not exist yet → TypeError
            )

            data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
            impl_by: list = data.get("implemented_by") or []

            self.assertTrue(
                len(impl_by) >= 1,
                "Expected at least one entry in implemented_by after calling "
                "_write_implemented_by; list is empty.",
            )

            stored = impl_by[0]

            self.assertFalse(
                stored.startswith("/"),
                (
                    "AC-1 FAIL: stored entry starts with '/' — "
                    f"it is an absolute path rather than a repo-relative one. "
                    f"Entry: {stored!r}."
                ),
            )

            self.assertNotIn(
                "worktrees/",
                stored,
                (
                    "AC-1 FAIL: stored entry contains 'worktrees/' — "
                    f"a per-checkout worktree segment leaked into the stored value. "
                    f"Entry: {stored!r}."
                ),
            )

            self.assertEqual(
                stored,
                expected,
                (
                    "AC-1 FAIL: stored entry is not the clean repo-relative form. "
                    f"Expected: {expected!r}. Got: {stored!r}. "
                    "The fix must relativise via the git-derived (or injected) "
                    "repo root rather than simply stripping leading '/'."
                ),
            )

    def test_same_ac_records_identical_value_regardless_of_location(self) -> None:
        # covers: ACD-1200a-14
        """AC-2: The same AC records an identical repo-relative value regardless of
        which tickets-root or worktree location the ticket lives in.

        Scenario
        --------
        Two separate AC fixture files receive _write_implemented_by calls for the
        same logical ticket but from two DIFFERENT checkout roots (simulating the
        same repo cloned or checked out at two different absolute paths):

          - checkout_alpha: /fake/checkout-alpha   →  worktree /fake/worktrees/wt-A
          - checkout_beta:  /fake/checkout-beta    →  worktree /fake/worktrees/wt-B

        The ticket lives at:
          - /fake/checkout-alpha/tickets/00_inbox/TICKET-14-test.md (under alpha)
          - /fake/checkout-beta/tickets/00_inbox/TICKET-14-test.md  (under beta)

        Both are outside their respective worktrees (ticket not under /fake/worktrees/).
        Each call passes its own checkout root as repo_root.

        Expected stored value (both): 'tickets/00_inbox/TICKET-14-test.md'

        MUST be RED before the fix
        --------------------------
        1. 'repo_root' keyword argument does not exist → TypeError on first call.
        2. Even without TypeError, the current fallback produces:
             stored_alpha = 'fake/checkout-alpha/tickets/00_inbox/TICKET-14-test.md'
             stored_beta  = 'fake/checkout-beta/tickets/00_inbox/TICKET-14-test.md'
           These DIFFER → assertEqual(stored_alpha, stored_beta) fails.
           And both differ from 'tickets/00_inbox/TICKET-14-test.md' → assertEqual
           against expected also fails.
        """
        checkout_alpha = Path("/fake/checkout-alpha")
        checkout_beta = Path("/fake/checkout-beta")
        worktree_a = Path("/fake/worktrees/wt-A")
        worktree_b = Path("/fake/worktrees/wt-B")

        abs_ticket_alpha = str(checkout_alpha / "tickets/00_inbox/TICKET-14-test.md")
        abs_ticket_beta = str(checkout_beta / "tickets/00_inbox/TICKET-14-test.md")
        expected = "tickets/00_inbox/TICKET-14-test.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_file_alpha = _make_temp_ac_yaml(tmp, "ACD-1200a-14-fixture-2a")
            ac_file_beta = _make_temp_ac_yaml(tmp, "ACD-1200a-14-fixture-2b")

            # 'repo_root' not in current signature → TypeError (test is RED)
            _write_implemented_by(
                ac_file_alpha,
                abs_ticket_alpha,
                "ACD-1200a-14-fixture-2a",
                worktree=worktree_a,
                repo_root=checkout_alpha,  # does not exist yet → TypeError
            )
            _write_implemented_by(
                ac_file_beta,
                abs_ticket_beta,
                "ACD-1200a-14-fixture-2b",
                worktree=worktree_b,
                repo_root=checkout_beta,  # does not exist yet → TypeError
            )

            data_alpha = yaml.safe_load(ac_file_alpha.read_text(encoding="utf-8"))
            data_beta = yaml.safe_load(ac_file_beta.read_text(encoding="utf-8"))
            impl_alpha: list = data_alpha.get("implemented_by") or []
            impl_beta: list = data_beta.get("implemented_by") or []

            self.assertTrue(
                len(impl_alpha) >= 1,
                "Expected an entry in AC file (alpha checkout).",
            )
            self.assertTrue(
                len(impl_beta) >= 1,
                "Expected an entry in AC file (beta checkout).",
            )

            stored_alpha = impl_alpha[0]
            stored_beta = impl_beta[0]

            self.assertEqual(
                stored_alpha,
                stored_beta,
                (
                    "AC-2 FAIL: Different checkout locations produced different "
                    "stored values for the same logical ticket. "
                    f"stored_alpha={stored_alpha!r}, stored_beta={stored_beta!r}. "
                    "The same logical ticket must record an identical repo-relative "
                    "value regardless of which checkout or worktree the generator ran from."
                ),
            )

            self.assertEqual(
                stored_alpha,
                expected,
                (
                    "AC-2 FAIL: stored value is not the expected clean repo-relative "
                    f"form. Expected: {expected!r}. Got: {stored_alpha!r}. "
                    "The fix must use the repo root (not the raw path) to relativise."
                ),
            )

    def test_repo_root_git_derived_and_applied_to_existing_entries(self) -> None:
        # covers: ACD-1200a-14
        """AC-3: The repo root used for relativisation is derived canonically and
        applied to BOTH the incoming path AND every existing implemented_by entry
        (not just the new one being appended).

        Scenario
        --------
        The AC YAML is pre-seeded with an existing absolute-path entry — the kind
        that buggy pre-fix code would have written before ACD-1200a-12 (or that
        ACD-1200a-12 partially fixed but left with a host-specific prefix in
        fallback cases).

          - fake_repo_root:  /fake/main-repo
          - fake_worktree:   /fake/worktrees/some-wt
          - existing entry:  '/fake/main-repo/tickets/00_inbox/TICKET-old.md'  (absolute)
          - new ticket:      '/fake/main-repo/tickets/00_inbox/TICKET-14-test.md'

        After the call ALL entries in implemented_by must be clean repo-relative
        paths with no leading '/' and no host-specific directory prefix.

        Expected final entries: ['tickets/00_inbox/TICKET-old.md',
                                 'tickets/00_inbox/TICKET-14-test.md']

        MUST be RED before the fix
        --------------------------
        1. 'repo_root' keyword argument does not exist → TypeError on call.
        2. Even without TypeError, the current code does NOT retroactively normalise
           existing entries: '/fake/main-repo/tickets/...' remains verbatim in the
           stored YAML (starting with '/') — the assertFalse(entry.startswith('/'))
           check fails for the pre-existing entry.
        3. And the assertEqual on stored values fails because the fallback
           _normalise_repo_relative would produce 'fake/main-repo/tickets/...'
           (not starting with 'tickets/').
        """
        fake_repo_root = Path("/fake/main-repo")
        fake_worktree = Path("/fake/worktrees/some-wt")

        # Pre-existing entry stored as absolute path (simulating buggy old code)
        existing_bad_entry = str(fake_repo_root / "tickets/00_inbox/TICKET-old.md")
        new_ticket = str(fake_repo_root / "tickets/00_inbox/TICKET-14-test.md")

        expected_old = "tickets/00_inbox/TICKET-old.md"
        expected_new = "tickets/00_inbox/TICKET-14-test.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            ac_file = _make_temp_ac_yaml(
                Path(tmpdir),
                "ACD-1200a-14-fixture-3",
                implemented_by=[existing_bad_entry],  # pre-seeded absolute-path entry
            )

            # 'repo_root' not in current signature → TypeError (test is RED)
            _write_implemented_by(
                ac_file,
                new_ticket,
                "ACD-1200a-14-fixture-3",
                worktree=fake_worktree,
                repo_root=fake_repo_root,  # does not exist yet → TypeError
            )

            data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
            impl_by: list = data.get("implemented_by") or []

            self.assertTrue(
                len(impl_by) >= 1,
                "Expected at least one entry in implemented_by after calling "
                "_write_implemented_by; list is empty.",
            )

            # Every entry (pre-existing AND newly appended) must be repo-relative
            for entry in impl_by:
                self.assertFalse(
                    entry.startswith("/"),
                    (
                        "AC-3 FAIL: An implemented_by entry starts with '/' — "
                        "the pre-existing absolute-path entry was not normalised "
                        f"through the repo root. Entry: {entry!r}. "
                        "Both the incoming path and every existing entry must be "
                        "normalised through the git-derived repo root."
                    ),
                )
                self.assertTrue(
                    entry.startswith("tickets/"),
                    (
                        "AC-3 FAIL: An implemented_by entry does not start with 'tickets/'. "
                        f"Entry: {entry!r}. "
                        "After applying the repo root, every entry must be a pure "
                        "repo-relative path starting with 'tickets/'."
                    ),
                )

            # Both the normalised old entry and the new entry must be present
            self.assertIn(
                expected_old,
                impl_by,
                (
                    f"AC-3 FAIL: Normalised old entry {expected_old!r} not found. "
                    "The pre-existing absolute-path entry must be retroactively "
                    f"normalised to repo-relative form. Found: {impl_by!r}."
                ),
            )
            self.assertIn(
                expected_new,
                impl_by,
                (
                    f"AC-3 FAIL: New entry {expected_new!r} not found in "
                    f"implemented_by. Found: {impl_by!r}."
                ),
            )


if __name__ == "__main__":
    unittest.main()
