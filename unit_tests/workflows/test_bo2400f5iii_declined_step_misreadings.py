"""
MODULE: unit_tests/workflows/test_bo2400f5iii_declined_step_misreadings.py
GOAL: RED behavioural tests for BO-2400f-5-iii test_spec entries 2 and 3 — the
      two DANGEROUS misreadings the AC's own test_rationale calls out: a
      declined resolve read as an empty connected set (looks like success,
      BO-2400f-2's clean no-op), and a declined producibility read as "every
      member producible" (goes on to claim).

=== Why each is RED today, precisely ===

Resolve (`resolve-connected`): a plain-string decline reply has no `.ac_ids`
or `.message` property (JS property access on a string is always undefined),
so `acIds` becomes `[]` and `resolverMsg` becomes `""`. `""` matches none of
the "/not found|no build set|.../i" resolver-error patterns, so the run falls
straight into the EXISTING "empty set — clean no-op" branch
(fast-lane-ship.js ~line 922): `status: "ok", nothing_to_build: true`. This
reproduces the AC's named must_catch failure mode EXACTLY, on today's code,
with no changes.

Producibility (`check-producibility`): a plain-string decline reply makes
`producibilityVerdictReadable` false (no boolean `.producible`), so today's
code ALREADY takes the fail-closed "could not be determined" refusing branch
and does NOT proceed to claim — by luck, not by design for this AC (that
branch predates this AC, from BO-2400f-12). It is missing the one thing this
AC actually requires: `halt_kind: 'declined_step'`. That assertion is what
fails today.

=== Not a grep test — see test_bo2400f5iii_declined_step_core.py's docstring
for the harness rationale (same mechanism, not repeated here). ===
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows._bo2400f5iii_fixtures import (  # noqa: E402
    CONTENTION_MARKERS,
    calls_with_label,
    decline_reply_for,
    run_lane,
)


class TestDeclinedResolveIsNotReadAsAnEmptyConnectedSet(unittest.TestCase):
    """test_spec[2] (angle: failure).

    must_catch: "a declined resolve ends as a clean no-op that looks like
    success".
    """

    def test_declined_resolve_is_not_read_as_an_empty_connected_set(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: failure
        result = run_lane({"resolve-connected": decline_reply_for("status-checker")})

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}

        # The exact must_catch failure mode: today's code reports this as a
        # clean, successful no-op.
        self.assertNotEqual(
            payload.get("status"),
            "ok",
            f"A declined resolve must NOT be reported as a successful no-op. "
            f"Got: {payload}",
        )
        self.assertIsNot(
            payload.get("nothing_to_build"),
            True,
            f"A declined resolve must NOT be reported as an empty connected "
            f"set (BO-2400f-2's clean no-op is for a genuinely empty set, not "
            f"an unreadable reply). Got: {payload}",
        )
        self.assertEqual(
            payload.get("halt_kind"),
            "declined_step",
            f"A declined resolve must halt as a declined step. Got: {payload}",
        )

        # No later step may have been dispatched — a declined resolve reaches
        # neither the producibility guard nor the claim step.
        self.assertFalse(
            calls_with_label(result, "check-producibility"),
            "A declined resolve must not reach the producibility guard.",
        )
        self.assertFalse(
            calls_with_label(result, "claim-connected"),
            "A declined resolve must not reach the claim step.",
        )


class TestDeclinedProducibilityDoesNotProceedToClaim(unittest.TestCase):
    """test_spec[3] (angle: failure).

    must_catch: "a declined producibility read as every member producible,
    followed by a claim".
    """

    def test_declined_producibility_does_not_proceed_to_claim(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: failure
        result = run_lane({"check-producibility": decline_reply_for("status-checker")})

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}

        self.assertFalse(
            calls_with_label(result, "claim-connected"),
            f"A declined producibility check must NOT proceed to the claim "
            f"step. Calls: {[(c.label, c.agent_type) for c in result.agent_calls]}",
        )
        self.assertEqual(
            payload.get("halt_kind"),
            "declined_step",
            f"A declined producibility check must halt as a declined step "
            f"(today's fail-closed 'could not be determined' branch happens "
            f"to also skip the claim, but carries no halt_kind — that gap is "
            f"what this asserts). Got: {payload}",
        )
        as_text = str(payload).lower()
        for marker in CONTENTION_MARKERS:
            self.assertNotIn(
                marker, as_text,
                f"A declined producibility check must not read like contention. Got: {payload}",
            )
        self.assertNotIn(
            "every member is producible",
            as_text,
            f"A decline must never be read as 'every member is producible'. Got: {payload}",
        )


if __name__ == "__main__":
    unittest.main()
