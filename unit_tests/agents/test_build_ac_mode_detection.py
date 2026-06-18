"""
Unit tests for build-ac mode detection logic (ticket 05: EPIC-GoalToEpic).

These tests cover the three routing modes added to the build-ac agent template
in Step 2 (Generate a Ticket from the AC):

  1. Leaf AC (L2/L3 with covered_by empty/absent) → single-ticket path unchanged
  2. L0/L1 with non-empty covered_by → epic-generation mode
  3. L1 with empty covered_by → error + decompose suggestion, no writes

Tests are structured as failing stubs: they import the mode-detection helper
that does not yet exist (implemented by llm-expert in the next phase). All
tests are expected to fail with ImportError or AttributeError until the
implementation is in place.

AC coverage:
  ACD-1200e-1  — leaf AC → single-ticket path unchanged
  ACD-1200e-2  — L0/L1 with children → epic-generation mode
  ACD-1200e-2-i — L1 with no children → error + decompose suggestion
"""

import unittest

# This import will fail until llm-expert writes the implementation.
# That is the intended red state for this test stub.
try:
    from scripts.build_ac_mode_detection import (
        detect_ac_mode,
        AC_MODE_LEAF,
        AC_MODE_GOAL,
        AC_MODE_L1_NO_CHILDREN,
        LEAF_MESSAGE_NONE,  # No mode message for leaf path
        GOAL_MESSAGE_TEMPLATE,  # "ACD-{id} is a goal — generating epic..."
        L1_NO_CHILDREN_MESSAGE_TEMPLATE,  # "ACD-{id} is an L1 with no leaf ACs..."
    )
    IMPORT_OK = True
except ImportError:
    IMPORT_OK = False

    # Stubs so test bodies can still be parsed and collected
    AC_MODE_LEAF = "leaf"
    AC_MODE_GOAL = "goal"
    AC_MODE_L1_NO_CHILDREN = "l1_no_children"
    LEAF_MESSAGE_NONE = None
    GOAL_MESSAGE_TEMPLATE = "ACD-{id} is a goal — generating epic from all leaf ACs beneath it."
    L1_NO_CHILDREN_MESSAGE_TEMPLATE = (
        "ACD-{id} is an L1 with no leaf ACs beneath it. "
        "Decompose into L2/L3 first, or use /ba to generate behavioral specifications."
    )

    def detect_ac_mode(ac_id: str, level: str, covered_by: list) -> dict:
        raise ImportError(
            "scripts.build_ac_mode_detection is not yet implemented — "
            "this is the expected red state for TDD test stub. "
            "llm-expert must implement detect_ac_mode() to make this test green."
        )


class TestBuildAcModeDetection(unittest.TestCase):
    """Tests for the mode-detection branch in build-ac Step 2."""

    # ------------------------------------------------------------------
    # AC-1 / ACD-1200e-1: Leaf AC → single-ticket path unchanged
    # ------------------------------------------------------------------

    def test_ac1_leaf_l2_empty_covered_by_returns_leaf_mode(self):
        # covers: ACD-1200e-1
        """AC-1: An L2 AC with covered_by=[] is detected as a leaf (single-ticket path)."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACS-101a-1", level="L2", covered_by=[])
        self.assertEqual(result["mode"], AC_MODE_LEAF)

    def test_ac1_leaf_l3_absent_covered_by_returns_leaf_mode(self):
        # covers: ACD-1200e-1
        """AC-1: An L3 AC with covered_by absent (None) is detected as a leaf."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACS-101b-2", level="L3", covered_by=None)
        self.assertEqual(result["mode"], AC_MODE_LEAF)

    def test_ac1_leaf_mode_has_no_user_message(self):
        # covers: ACD-1200e-1
        """AC-1: Leaf path produces no mode-switch message to the user."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACS-101a-1", level="L2", covered_by=[])
        # The leaf path must not emit a user-facing mode message (backward compatible)
        self.assertIsNone(result.get("message"))

    def test_ac1_leaf_does_not_invoke_goal_to_epic(self):
        # covers: ACD-1200e-1
        """AC-1: detect_ac_mode does NOT set invoke_goal_to_epic=True for leaf ACs."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACS-101a-1", level="L2", covered_by=[])
        self.assertFalse(result.get("invoke_goal_to_epic", False))

    # ------------------------------------------------------------------
    # AC-2 / ACD-1200e-2: L0 or L1 with children → epic-generation mode
    # ------------------------------------------------------------------

    def test_ac2_l0_with_children_returns_goal_mode(self):
        # covers: ACD-1200e-2
        """AC-2: An L0 AC with non-empty covered_by switches to epic-generation mode."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(
            ac_id="ACD-050",
            level="L0",
            covered_by=["ACD-050a", "ACD-050b"],
        )
        self.assertEqual(result["mode"], AC_MODE_GOAL)

    def test_ac2_l1_with_children_returns_goal_mode(self):
        # covers: ACD-1200e-2
        """AC-2: An L1 AC with non-empty covered_by also switches to epic-generation mode."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(
            ac_id="ACD-050a",
            level="L1",
            covered_by=["ACD-050a-1", "ACD-050a-2"],
        )
        self.assertEqual(result["mode"], AC_MODE_GOAL)

    def test_ac2_goal_mode_emits_correct_message(self):
        # covers: ACD-1200e-2
        """AC-2: Goal mode prints the required user-facing mode switch message."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(
            ac_id="ACD-050",
            level="L0",
            covered_by=["ACD-050a", "ACD-050b"],
        )
        expected_message = "ACD-050 is a goal — generating epic from all leaf ACs beneath it."
        self.assertEqual(result["message"], expected_message)

    def test_ac2_goal_mode_sets_invoke_flag(self):
        # covers: ACD-1200e-2
        """AC-2: Goal mode sets invoke_goal_to_epic=True so the caller invokes the pipeline."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(
            ac_id="ACD-050a",
            level="L1",
            covered_by=["ACD-050a-1", "ACD-050a-2"],
        )
        self.assertTrue(result.get("invoke_goal_to_epic", False))

    def test_ac2_goal_mode_does_not_follow_single_ticket_path(self):
        # covers: ACD-1200e-2
        """AC-2: Goal mode MUST NOT set use_single_ticket_path=True."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(
            ac_id="ACD-050",
            level="L0",
            covered_by=["ACD-050a"],
        )
        self.assertFalse(result.get("use_single_ticket_path", False))

    # ------------------------------------------------------------------
    # AC-3 / ACD-1200e-2-i: L1 with no children → error path
    # ------------------------------------------------------------------

    def test_ac3_l1_no_children_returns_l1_no_children_mode(self):
        # covers: ACD-1200e-2-i
        """AC-3: An L1 AC with covered_by=[] is detected as L1-no-children (error path)."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACD-070a", level="L1", covered_by=[])
        self.assertEqual(result["mode"], AC_MODE_L1_NO_CHILDREN)

    def test_ac3_l1_no_children_emits_correct_message(self):
        # covers: ACD-1200e-2-i
        """AC-3: L1-no-children path emits the required decompose suggestion message."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACD-070a", level="L1", covered_by=[])
        expected_message = (
            "ACD-070a is an L1 with no leaf ACs beneath it. "
            "Decompose into L2/L3 first, or use /ba to generate behavioral specifications."
        )
        self.assertEqual(result["message"], expected_message)

    def test_ac3_l1_no_children_does_not_invoke_goal_to_epic(self):
        # covers: ACD-1200e-2-i
        """AC-3: L1-no-children error path MUST NOT invoke epic-generation pipeline."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACD-070a", level="L1", covered_by=[])
        self.assertFalse(result.get("invoke_goal_to_epic", False))

    def test_ac3_l1_no_children_does_not_follow_single_ticket_path(self):
        # covers: ACD-1200e-2-i
        """AC-3: L1-no-children error path MUST NOT follow single-ticket path either."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACD-070a", level="L1", covered_by=[])
        self.assertFalse(result.get("use_single_ticket_path", False))

    def test_ac3_l1_no_children_none_covered_by_also_errors(self):
        # covers: ACD-1200e-2-i
        """AC-3: An L1 AC with covered_by=None is also treated as L1-no-children."""
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACD-070a", level="L1", covered_by=None)
        self.assertEqual(result["mode"], AC_MODE_L1_NO_CHILDREN)

    # ------------------------------------------------------------------
    # Boundary / disambiguation tests
    # ------------------------------------------------------------------

    def test_l0_empty_covered_by_is_not_valid_goal(self):
        # covers: ACD-1200e-2
        """
        An L0 AC with covered_by=[] should not silently become a leaf —
        it must either be treated as L1-no-children or raise an error,
        since L0 with no children is not a sensible tree root.
        The implementation must not return AC_MODE_LEAF for this case.
        """
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        result = detect_ac_mode(ac_id="ACD-000", level="L0", covered_by=[])
        # L0 with empty covered_by is treated the same as L1 with no children
        # (neither a leaf nor a valid goal). Must NOT be AC_MODE_LEAF.
        self.assertNotEqual(result["mode"], AC_MODE_LEAF)

    def test_l2_with_covered_by_falls_back_to_leaf_mode(self):
        # covers: ACD-1200e-1
        """
        An L2 AC with non-empty covered_by is unexpected (L2 should be a leaf),
        but if present, the mode detection must still not crash — it should
        treat it as a leaf (backward-compatible) since the primary routing
        criterion is the level field for goal detection.
        """
        if not IMPORT_OK:
            self.fail(
                "ImportError: cannot import detect_ac_mode from "
                "scripts.build_ac_mode_detection — implementation not yet written."
            )
        # Level L2 always means leaf, even if covered_by is non-empty
        result = detect_ac_mode(ac_id="ACD-weird", level="L2", covered_by=["ACD-weird-1"])
        self.assertEqual(result["mode"], AC_MODE_LEAF)


if __name__ == "__main__":
    unittest.main()
