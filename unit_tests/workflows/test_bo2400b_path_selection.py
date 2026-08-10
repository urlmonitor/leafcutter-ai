"""
MODULE: unit_tests/workflows/test_bo2400b_path_selection.py
GOAL: RED test stubs for BO-2400b-1, BO-2400b-2, BO-2400b-3, BO-2400b-3-i, BO-2400b-3-ii.

=== Interface contract under test (to be implemented by python-coder) ===

Location: scripts/build_orchestration/path_selection.py

    choose_lane(
        *,
        scope: str,
        attended: bool,
        defect_cost: str,
        override: str | None = None,
    ) -> dict

  Returns a decision object with ALL of the following keys:
      "lane"        str   -- "fast" or "heavy"
      "reason"      str   -- Human-readable explanation of why this lane was chosen.
                             Must be non-empty for every non-trivially-fast decision
                             (heavy, ambiguous, overridden).
      "ambiguous"   bool  -- True iff the scope input did not clearly map to
                             "scoped" or "large" and the heavy default was applied.
      "overridden"  bool  -- True iff an explicit override= was supplied and applied.

  DECISION RULE (single documented rule — BO-2400b-3):

  Step 1 — Override check (unconditional win):
    If override is "fast" or "heavy":
      lane = override
      overridden = True
      reason must name the override value AND what the rule would have computed,
      so the supersession is auditable (BO-2400b-3-ii).

  Step 2 — No override; apply the documented rule:

    FAST lane iff ALL of the following are true:
      - scope == "scoped"     (small blast radius; clearly within scope)
      - attended is True      (interactive; human-attended build)
      - defect_cost == "low"  (low cost if a defect escapes to production)

    HEAVY lane when ANY of the following is true:
      - scope == "large"      (large blast radius)
      - attended is False     (unattended / batch)
      - defect_cost == "high" (high cost of an escaped defect)

    AMBIGUOUS when scope is NOT "scoped" and NOT "large":
      - lane = "heavy"       (fail-closed safe default; BO-2400b-3-i)
      - ambiguous = True
      - reason must describe why the scope was treated as ambiguous

  The function must be pure and deterministic:
    - Same inputs always produce the same output.
    - No I/O, no randomness, no global mutable state.

=== Red baseline ===

  All tests in this file are RED until python-coder creates
  scripts/build_orchestration/path_selection.py and implements choose_lane.
  The ImportError produced by the missing module IS the intended red state.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as sibling workflow/ac_store tests
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

# These imports will raise ImportError until python-coder implements
# choose_lane in scripts/build_orchestration/path_selection.py.
# That ImportError IS the intended red state — it confirms production
# code does not yet exist.
from path_selection import choose_lane  # noqa: E402


# ---------------------------------------------------------------------------
# BO-2400b-1 — Scoped interactive work routes to the fast lane
# ---------------------------------------------------------------------------


class TestScopedInteractiveFastLane(unittest.TestCase):
    """BO-2400b-1: A scoped+interactive request routes to the fast lane."""

    def test_ac1_scoped_interactive_routes_fast_lane(self) -> None:
        # covers: BO-2400b-1
        """AC-1: scoped + attended + low defect-cost selects the fast lane.

        All three signals must be present.  To make this green, choose_lane
        must return lane='fast' when scope='scoped', attended=True,
        defect_cost='low'.
        """
        result = choose_lane(scope="scoped", attended=True, defect_cost="low")
        self.assertEqual(
            result["lane"],
            "fast",
            "A scoped+attended+low-defect-cost request must route to the fast lane.",
        )
        self.assertFalse(
            result.get("ambiguous", False),
            "A clearly scoped+interactive request must not be marked ambiguous.",
        )
        self.assertFalse(
            result.get("overridden", False),
            "No override was supplied; overridden must be False.",
        )

    def test_ac1_partial_match_high_defect_cost_routes_heavy(self) -> None:
        # covers: BO-2400b-1
        """AC-1 IT-requirement: partial fast-lane match (high defect-cost) must NOT route fast.

        All three signals are needed for fast.  scoped + attended + high
        defect-cost is missing the defect-cost signal, so the rule must choose
        heavy, not fast.
        """
        result = choose_lane(scope="scoped", attended=True, defect_cost="high")
        self.assertEqual(
            result["lane"],
            "heavy",
            "High defect-cost alone is sufficient to deny fast-lane selection.",
        )

    def test_ac1_partial_match_unattended_routes_heavy(self) -> None:
        # covers: BO-2400b-1
        """AC-1 IT-requirement: unattended with small scope still routes heavy."""
        result = choose_lane(scope="scoped", attended=False, defect_cost="low")
        self.assertEqual(
            result["lane"],
            "heavy",
            "Unattended request (even with small scope) must NOT route to the fast lane.",
        )

    def test_ac1_result_has_all_required_keys(self) -> None:
        # covers: BO-2400b-1
        """AC-1: The decision object must expose lane, reason, ambiguous, and overridden."""
        result = choose_lane(scope="scoped", attended=True, defect_cost="low")
        for key in ("lane", "reason", "ambiguous", "overridden"):
            self.assertIn(
                key,
                result,
                f"Decision object must contain key '{key}'.",
            )
        self.assertIsInstance(result["lane"], str)
        self.assertIsInstance(result["reason"], str)
        self.assertIsInstance(result["ambiguous"], bool)
        self.assertIsInstance(result["overridden"], bool)

    def test_ac1_fast_lane_value_is_exact_string(self) -> None:
        # covers: BO-2400b-1
        """AC-1: lane must be the exact string 'fast' (not 'FAST', 'fast-lane', etc.)."""
        result = choose_lane(scope="scoped", attended=True, defect_cost="low")
        self.assertEqual(result["lane"], "fast")


# ---------------------------------------------------------------------------
# BO-2400b-2 — Large, unattended, or high-defect-cost routes heavy
# ---------------------------------------------------------------------------


class TestHeavyPipelineConditions(unittest.TestCase):
    """BO-2400b-2: Any single heavy-routing condition is sufficient for the heavy pipeline."""

    def test_ac2_large_scope_routes_heavy(self) -> None:
        # covers: BO-2400b-2
        """AC-2: Large scope alone is sufficient to route to the heavy pipeline."""
        result = choose_lane(scope="large", attended=True, defect_cost="low")
        self.assertEqual(
            result["lane"],
            "heavy",
            "Large scope must route to the heavy pipeline regardless of other signals.",
        )

    def test_ac2_unattended_routes_heavy(self) -> None:
        # covers: BO-2400b-2
        """AC-2: Unattended alone is sufficient to route to the heavy pipeline."""
        result = choose_lane(scope="scoped", attended=False, defect_cost="low")
        self.assertEqual(
            result["lane"],
            "heavy",
            "An unattended request must route to the heavy pipeline.",
        )

    def test_ac2_high_defect_cost_routes_heavy(self) -> None:
        # covers: BO-2400b-2
        """AC-2: High defect-cost alone is sufficient to route to the heavy pipeline."""
        result = choose_lane(scope="scoped", attended=True, defect_cost="high")
        self.assertEqual(
            result["lane"],
            "heavy",
            "High defect-cost alone is sufficient to route to the heavy pipeline.",
        )

    def test_ac2_all_heavy_signals_routes_heavy(self) -> None:
        # covers: BO-2400b-2
        """AC-2: All three heavy conditions together must still produce heavy (OR logic)."""
        result = choose_lane(scope="large", attended=False, defect_cost="high")
        self.assertEqual(result["lane"], "heavy")

    def test_ac2_large_scope_with_low_defect_cost_routes_heavy(self) -> None:
        # covers: BO-2400b-2
        """AC-2: Large scope + low defect-cost + attended still routes heavy.

        Even one heavy signal (large scope) is sufficient; other signals being
        'good' do not override the heavy condition.
        """
        result = choose_lane(scope="large", attended=True, defect_cost="low")
        self.assertEqual(result["lane"], "heavy")

    def test_ac2_heavy_reason_is_non_empty(self) -> None:
        # covers: BO-2400b-2
        """AC-2 IT-requirement: heavy routing from the rule must produce a non-empty reason.

        The reason makes the routing decision auditable — it must name what
        heavy signal triggered the decision.
        """
        result = choose_lane(scope="large", attended=True, defect_cost="low")
        self.assertEqual(result["lane"], "heavy")
        self.assertIsInstance(result.get("reason"), str)
        self.assertGreater(
            len(result["reason"]),
            0,
            "Heavy-pipeline selection must produce a non-empty reason string.",
        )


# ---------------------------------------------------------------------------
# BO-2400b-3 — Single documented rule; deterministic
# ---------------------------------------------------------------------------


class TestDeterministicSingleRule(unittest.TestCase):
    """BO-2400b-3: The lane derives from a single documented rule; identical inputs yield
    the identical lane on every call."""

    def test_ac3_lane_decision_is_deterministic_fast(self) -> None:
        # covers: BO-2400b-3
        """AC-3: Routing the same fast-lane inputs twice yields the same lane and reason."""
        inputs = dict(scope="scoped", attended=True, defect_cost="low")
        result_a = choose_lane(**inputs)
        result_b = choose_lane(**inputs)
        self.assertEqual(
            result_a["lane"],
            result_b["lane"],
            "Same inputs must always produce the same lane (deterministic).",
        )
        self.assertEqual(
            result_a["reason"],
            result_b["reason"],
            "Same inputs must always produce the same reason (deterministic).",
        )

    def test_ac3_lane_decision_is_deterministic_heavy(self) -> None:
        # covers: BO-2400b-3
        """AC-3: Routing the same heavy-lane inputs twice yields the same lane and reason."""
        inputs = dict(scope="large", attended=False, defect_cost="high")
        result_a = choose_lane(**inputs)
        result_b = choose_lane(**inputs)
        self.assertEqual(result_a["lane"], result_b["lane"])
        self.assertEqual(result_a["reason"], result_b["reason"])

    def test_ac3_determinism_across_input_matrix(self) -> None:
        # covers: BO-2400b-3
        """AC-3: Determinism holds across a matrix of distinct (scope, attended, defect_cost)
        combinations.  Each pair of consecutive calls must agree on lane and reason.
        """
        cases = [
            dict(scope="scoped", attended=True, defect_cost="low"),
            dict(scope="scoped", attended=True, defect_cost="high"),
            dict(scope="scoped", attended=False, defect_cost="low"),
            dict(scope="large", attended=True, defect_cost="low"),
            dict(scope="large", attended=False, defect_cost="high"),
            dict(scope="scoped", attended=False, defect_cost="high"),
        ]
        for inputs in cases:
            with self.subTest(inputs=inputs):
                r1 = choose_lane(**inputs)
                r2 = choose_lane(**inputs)
                self.assertEqual(
                    r1["lane"],
                    r2["lane"],
                    f"Non-deterministic lane for inputs {inputs}",
                )

    def test_ac3_lane_derived_from_documented_rule(self) -> None:
        # covers: BO-2400b-3
        """AC-3: choose_lane must have a non-trivial docstring encoding the decision rule.

        The documented rule must be auditable from the source — not a hidden
        per-run judgment.  A substantial docstring is the minimum proof.
        """
        self.assertIsNotNone(
            choose_lane.__doc__,
            "choose_lane must have a docstring documenting the lane-decision rule.",
        )
        self.assertGreater(
            len((choose_lane.__doc__ or "").strip()),
            20,
            "The choose_lane docstring must be substantial — it IS the documented rule.",
        )


# ---------------------------------------------------------------------------
# BO-2400b-3-i — Ambiguous scope defaults to heavy; reason recorded
# ---------------------------------------------------------------------------


class TestAmbiguousScopeDefaultsHeavy(unittest.TestCase):
    """BO-2400b-3-i: Inputs that don't clearly classify route to the heavy pipeline;
    the reason for the ambiguity is recorded."""

    def test_ac3i_unknown_scope_defaults_heavy(self) -> None:
        # covers: BO-2400b-3-i
        """AC-3-i: An 'unknown' scope value is ambiguous; the rule must default to heavy."""
        result = choose_lane(scope="unknown", attended=True, defect_cost="low")
        self.assertEqual(
            result["lane"],
            "heavy",
            "Ambiguous ('unknown') scope must default to the heavy pipeline (fail-closed).",
        )
        self.assertTrue(
            result.get("ambiguous"),
            "An ambiguous-scope request must set ambiguous=True.",
        )

    def test_ac3i_ambiguity_reason_recorded(self) -> None:
        # covers: BO-2400b-3-i
        """AC-3-i: The reason must be non-empty and reference the ambiguity."""
        result = choose_lane(scope="unknown", attended=True, defect_cost="low")
        reason = result.get("reason", "")
        self.assertGreater(
            len(reason),
            0,
            "The reason field must be non-empty when scope is ambiguous.",
        )
        self.assertTrue(
            any(
                kw in reason.lower()
                for kw in ("ambiguous", "unclear", "unknown", "unrecognised", "unrecognized")
            ),
            f"Reason must reference the ambiguity cause; got: {reason!r}",
        )

    def test_ac3i_fast_lane_never_chosen_on_ambiguous_scope(self) -> None:
        # covers: BO-2400b-3-i
        """AC-3-i IT-requirement: fast lane is never selected on an ambiguous scope.

        Even if attended=True and defect_cost='low', an unclear scope must
        produce lane='heavy' (fail-closed default).
        """
        for ambiguous_scope in ("unknown", "mixed", "partial", ""):
            with self.subTest(scope=ambiguous_scope):
                result = choose_lane(
                    scope=ambiguous_scope, attended=True, defect_cost="low"
                )
                self.assertNotEqual(
                    result["lane"],
                    "fast",
                    f"Ambiguous scope '{ambiguous_scope}' must NOT select the fast lane.",
                )

    def test_ac3i_ambiguous_sets_ambiguous_true(self) -> None:
        # covers: BO-2400b-3-i
        """AC-3-i: ambiguous=True is required for ambiguous-scope inputs (not just heavy)."""
        result = choose_lane(scope="mixed", attended=True, defect_cost="low")
        self.assertTrue(
            result.get("ambiguous"),
            "ambiguous must be True when the scope is not a recognised value.",
        )

    def test_ac3i_non_ambiguous_heavy_does_not_set_ambiguous(self) -> None:
        # covers: BO-2400b-3-i
        """AC-3-i: ambiguous must be False when heavy is chosen due to a clear heavy signal.

        When scope='large', the rule clearly routes heavy — that is NOT an
        ambiguous classification, so ambiguous must remain False.
        """
        result = choose_lane(scope="large", attended=True, defect_cost="low")
        self.assertEqual(result["lane"], "heavy")
        self.assertFalse(
            result.get("ambiguous"),
            "A clearly-heavy (large-scope) request must NOT be marked ambiguous.",
        )


# ---------------------------------------------------------------------------
# BO-2400b-3-ii — Explicit lane override wins; supersession recorded
# ---------------------------------------------------------------------------


class TestLaneOverrideWins(unittest.TestCase):
    """BO-2400b-3-ii: An explicit override takes precedence over the rule; the override
    and its supersession of the rule are both recorded."""

    def test_ac3ii_override_fast_wins_over_heavy_rule(self) -> None:
        # covers: BO-2400b-3-ii
        """AC-3-ii: override='fast' selects fast even when the rule would choose heavy.

        A large-scope + unattended + high-defect-cost request would normally
        route to the heavy pipeline.  An explicit override='fast' must win.
        """
        result = choose_lane(
            scope="large", attended=False, defect_cost="high", override="fast"
        )
        self.assertEqual(
            result["lane"],
            "fast",
            "override='fast' must win over the rule's heavy selection.",
        )
        self.assertTrue(
            result.get("overridden"),
            "overridden must be True when an explicit lane override is applied.",
        )

    def test_ac3ii_override_heavy_wins_over_fast_rule(self) -> None:
        # covers: BO-2400b-3-ii
        """AC-3-ii: override='heavy' selects heavy even when the rule would choose fast."""
        result = choose_lane(
            scope="scoped", attended=True, defect_cost="low", override="heavy"
        )
        self.assertEqual(
            result["lane"],
            "heavy",
            "override='heavy' must win over the rule's fast selection.",
        )
        self.assertTrue(result.get("overridden"))

    def test_ac3ii_override_supersession_recorded_in_reason(self) -> None:
        # covers: BO-2400b-3-ii
        """AC-3-ii IT-requirement: the reason must name the override and that it superseded
        the rule (including what the rule would have chosen).

        To make this green, choose_lane must:
        - Compute the rule's lane before applying the override.
        - Record both the override value and the rule's original choice in reason.
        """
        result = choose_lane(
            scope="large", attended=False, defect_cost="high", override="fast"
        )
        reason = result.get("reason", "")
        self.assertGreater(
            len(reason),
            0,
            "Reason must be non-empty when an override is applied.",
        )
        self.assertTrue(
            any(
                kw in reason.lower()
                for kw in ("override", "overridden", "forced", "superseded")
            ),
            f"Reason must reference the override; got: {reason!r}",
        )

    def test_ac3ii_overridden_flag_false_without_override(self) -> None:
        # covers: BO-2400b-3-ii
        """AC-3-ii: overridden must be False when no override is supplied."""
        result = choose_lane(scope="scoped", attended=True, defect_cost="low")
        self.assertFalse(
            result.get("overridden"),
            "overridden must be False when no override is provided.",
        )

    def test_ac3ii_override_none_same_as_no_override(self) -> None:
        # covers: BO-2400b-3-ii
        """AC-3-ii: Passing override=None explicitly must behave identically to omitting it."""
        result_default = choose_lane(scope="scoped", attended=True, defect_cost="low")
        result_none = choose_lane(
            scope="scoped", attended=True, defect_cost="low", override=None
        )
        self.assertEqual(
            result_default["lane"],
            result_none["lane"],
            "override=None must not change the routing outcome.",
        )
        self.assertFalse(result_none.get("overridden"))

    def test_ac3ii_override_recorded_regardless_of_rule_agreement(self) -> None:
        # covers: BO-2400b-3-ii
        """AC-3-ii: overridden must be True even when override agrees with the rule.

        override='heavy' on an already-heavy (large scope) request still
        counts as an override that must be recorded — the caller explicitly
        made a decision, and that decision must be auditable.
        """
        result = choose_lane(
            scope="large", attended=True, defect_cost="low", override="heavy"
        )
        self.assertEqual(result["lane"], "heavy")
        self.assertTrue(
            result.get("overridden"),
            "overridden must be True whenever an override is supplied, even if it "
            "agrees with the rule's computed lane.",
        )


if __name__ == "__main__":
    unittest.main()
