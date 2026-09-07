"""
MODULE: test_bo_2200c_3_i
GOAL: RED tests for BO-2200c-3-i — fail-soft when parent can't be resolved.
BUSINESS CONTEXT: When the parent L1 AC cannot be resolved (parent file absent,
    derive_parent_id returns None, or parent has no documentation_triggers), the
    generator must emit the contract line WITHOUT a genre rather than crashing.
    The missing genre must be represented with an explicit "(unspecified genre)"
    marker so the omission is visible, not silently blank.
ARCHITECTURE: Tests use a temporary empty ac_root to force the parent-not-found
    failure path. Both sub-cases are covered: no crash, and explicit marker.

These tests are RED before the BO-2200c-3-i implementation because:
  - _build_agent_contracts_section does not accept an ac_root parameter.
  - Parent resolution does not exist; there is no fail-soft path.
  - The "(unspecified genre)" marker is never emitted.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-3-i.yaml
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agent_contracts_section  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEAF_AC_ID = "BO-9999t-1"


def _make_leaf_ac() -> dict:
    """Return a leaf AC whose own documentation_triggers is empty.

    With an empty ac_root and an empty leaf documentation_triggers, all paths
    to a genre fail: the parent is not found and the leaf provides no fallback.
    The "(unspecified genre)" marker must appear instead of crashing or producing
    a silently blank genre.
    """
    return {
        "id": _LEAF_AC_ID,
        "title": "Test leaf AC for fail-soft genre marker",
        "component": "build-orchestration",
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "documentation_triggers": [],
        "criteria": (
            "Given a leaf AC whose parent cannot be found,\n"
            "When the generator builds the contract line,\n"
            "Then the contract line carries an explicit (unspecified genre) marker.\n"
            "And the path and content constraint are still written."
        ),
        "doc_links": [
            {
                "path": "docs/reference/test-schema.md",
                "relationship": "describes",
                "status": "exists",
            }
        ],
    }


def _make_agents_map_with_doc_expert() -> dict:
    """Return a pre-computed agents map with documentation-expert as needed."""
    return {
        "test-writer": "needed",
        "python-coder": "needed",
        "documentation-expert": "needed",
        "pr-reviewer": "needed",
        "commit": "needed",
        "pull-request": "needed",
    }


# ---------------------------------------------------------------------------
# TestUnresolvedParentFailSoft
# BO-2200c-3-i
# ---------------------------------------------------------------------------


class TestUnresolvedParentFailSoft(unittest.TestCase):
    """BO-2200c-3-i: Unresolved parent yields a genre-less contract line, not a crash.

    RED before implementation: _build_agent_contracts_section does not accept
    ac_root; parent resolution does not exist; no fail-soft path exists.

    Fix: when the parent cannot be resolved (file absent in ac_root), emit the
    contract line without a valid genre, using "(unspecified genre)" as the
    explicit marker. Log a WARNING per error-handling policy.
    """

    def test_unresolved_parent_yields_genre_less_line_no_crash(self) -> None:
        # covers: BO-2200c-3-i
        """When the parent L1 file is absent from ac_root, the generator must NOT
        crash, and must still emit a contract line with the path and constraint.

        The test uses an empty temporary ac_root so that no parent YAML is found.
        The assertion verifies:
        1. No exception is raised.
        2. The '### documentation-expert' subsection is present.
        3. A '- [ ] AC-N:' line is present (path + constraint written).

        Red state: _build_agent_contracts_section does not accept ac_root; the call
        will fail with a TypeError (unexpected keyword argument) or, if signature is
        changed without the fail-soft logic, may raise on None parent.

        Green state: the function emits a contract line without crashing, even when
        the parent file is absent.
        """
        leaf_ac = _make_leaf_ac()
        agents_map = _make_agents_map_with_doc_expert()

        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp)
            # ac_root is EMPTY — no parent YAML present.

            # Must not raise.
            section = _build_agent_contracts_section(
                leaf_ac,
                _LEAF_AC_ID,
                agents_map,
                ac_root=ac_root,
            )

        self.assertIn(
            "### documentation-expert",
            section,
            "The '### documentation-expert' subsection must be present even when "
            "the parent cannot be resolved.\n"
            f"Actual section:\n{section}",
        )
        # A contract line must still be emitted (path + constraint written).
        #
        # The separator was an em-dash until 2026-08-26. BO-2200c-5 moved the
        # line to the pipe-delimited shape documentation-verifier documents as
        # its parse rule, so producer and consumer agree on one format. What
        # BO-2200c-3-i asserts is unchanged: a line is still emitted, carrying
        # a path and a constraint, when the genre cannot be resolved.
        self.assertRegex(
            section,
            r"- \[ \] AC-\d+: .+ \| .*/.+ \| .+",
            "A '- [ ] AC-N:' line carrying a genre field, a path (with '/') and a "
            "constraint, pipe-delimited, must be present even when the genre "
            "cannot be resolved.\n"
            f"Actual section:\n{section}",
        )

    def test_missing_genre_marked_explicitly(self) -> None:
        # covers: BO-2200c-3-i
        """When the parent L1 cannot be resolved, the contract line carries the
        explicit marker '(unspecified genre)' rather than being silently blank.

        The AC requires the omission to be VISIBLE to the documentation-expert
        writer, so they know the genre is unresolved rather than inferring it
        from a missing bracket or a blank field.

        Red state: the marker "(unspecified genre)" is never emitted by the
        current implementation. It either emits "explanation" (leaf fallback) or
        raises a TypeError because ac_root is not a recognised parameter.

        Green state: "(unspecified genre)" appears in the contract line when the
        parent cannot be found, e.g.:
            - [ ] AC-1: [(unspecified genre)] docs/reference/... — ...
        """
        leaf_ac = _make_leaf_ac()
        agents_map = _make_agents_map_with_doc_expert()

        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp)

            section = _build_agent_contracts_section(
                leaf_ac,
                _LEAF_AC_ID,
                agents_map,
                ac_root=ac_root,
            )

        self.assertIn(
            "(unspecified genre)",
            section,
            "The explicit '(unspecified genre)' marker must appear in the contract "
            "line when the parent L1 cannot be resolved. A silently blank genre or "
            "a fallback to 'explanation' does not satisfy BO-2200c-3-i — the omission "
            "must be visible.\n\n"
            "Red state: the marker is never emitted. Either 'explanation' (the leaf "
            "fallback) or a TypeError prevents the check from reaching this assertion.\n\n"
            f"Actual section:\n{section}",
        )


if __name__ == "__main__":
    unittest.main()
