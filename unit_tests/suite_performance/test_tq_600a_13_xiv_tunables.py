"""
Tests for TQ-600a-13-xiv, tunables half -- the staleness bound is read from scripts/ci/post_merge_tunables.json, and
the module refuses to run when it is not above the heartbeat bound.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiv.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/post_merge_hold.py reads its tunables from the module attribute ``TUNABLES_FILE`` (a Path, EXISTS), at
evaluation time. When the tunables are invalid (``staleness_hours <= heartbeat_max_hours``, NaN, infinity or not a
number) ``evaluate`` FAILS CLOSED (review fix M-1, ``_hold_config``): state ``could_not_read``, reason beginning
"Post-merge hold configuration is invalid" (a headline different from the run-history one), naming the file
``post_merge_tunables.json``, both keys, both values, and "edit". With ``staleness_hours`` above
``heartbeat_max_hours`` and a fresh green run it passes. The files here are written with ``json.dumps`` from the
committed file's own content (NaN via ``allow_nan=True``), never typed.
======================================================================
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from ._ending_harness import CHECK, Cases
from ._hold_harness import TUNABLES, make_run, tunables
from ._notice_fakes import import_production
from ._xiv_support import XivTestCase, headline

UNREADABLE_HEADLINE = "Post-merge run history could not be read"  # the -ix headline, copied from the AC's -ix wording


class TestTq600a13xivTunables(XivTestCase):
    def _evaluate_with(self, staleness, heartbeat):
        """``(state, reason)`` of one evaluation of a fresh green run with those two tunables written to a real file."""
        base = tunables()
        base.update({"staleness_hours": staleness, "heartbeat_max_hours": heartbeat})
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / TUNABLES.name
            path.write_text(json.dumps(base, allow_nan=True), encoding="utf-8")
            hold = import_production("scripts.ci.post_merge_hold")
            with mock.patch.object(hold, "TUNABLES_FILE", path):
                verdict = self.verdict([make_run(7, "success", hours_ago=1)])
        return verdict["state"], str(verdict["reason"])

    def test_tq600a_13_xiv_a_bound_not_above_the_heartbeat_refuses_to_run(self):
        # covers: TQ-600a-13-xiv
        # angle: failure
        """Equal, below, NaN, infinite and non-numeric bounds each give could_not_read for a fresh green run, with a
        reason that begins with the configuration headline (different from the run-history headline), names the file,
        both keys and both values, and says to edit; one hour above passes, so the refusal is the comparison and not
        a blanket failure.

        Wrong versions caught: no check at all; `<` instead of `<=` (equal slips through); NaN/inf/str comparing false
        and passing; the run-history headline reused for a configuration fault; a message naming one key or no value.
        """
        cases = Cases()
        rows = (("equal", 12, 12), ("below", 10, 12), ("NaN", float("nan"), 12), ("infinite", float("inf"), 12), ("a string", "thirty", 12), ("NaN heartbeat", 30, float("nan")))
        for label, staleness, heartbeat in rows:
            with cases.case(f"staleness_hours {label}"):
                state, reason = self._evaluate_with(staleness, heartbeat)
                CHECK.assertEqual("could_not_read", state, reason)
                CHECK.assertTrue(reason.startswith("Post-merge hold configuration is invalid"), reason)
                CHECK.assertNotEqual(headline(UNREADABLE_HEADLINE), headline(reason))
                for needle in ("post_merge_tunables.json", "staleness_hours", "heartbeat_max_hours", str(staleness), str(heartbeat), "edit"):
                    CHECK.assertIn(needle, reason.lower() if needle == "edit" else reason)
                CHECK.assertIn("To restore a verdict:", reason)
        with cases.case("staleness one above the heartbeat bound"):
            CHECK.assertEqual("pass", self._evaluate_with(13, 12)[0])
        cases.check()

    def test_tq600a_13_xiv_the_bound_comes_from_the_tunables_file_not_a_literal(self):
        # covers: TQ-600a-13-xiv
        # angle: discrimination
        """Retune the file to 50 h: a green run 31 h old, stale against the committed 30, now passes; retune to 20 h:
        one 21 h old is stale. A literal 30 in the module would ignore both.

        Wrong version caught: `30` hard-coded in the module while the file carries a decorative key.
        """
        cases = Cases()
        for staleness, hours, state in ((50, 31, "pass"), (20, 21, "stale")):
            with cases.case(f"staleness_hours {staleness}, run {hours} h old"):
                base = tunables()
                base["staleness_hours"] = staleness
                with tempfile.TemporaryDirectory() as raw:
                    path = Path(raw) / TUNABLES.name
                    path.write_text(json.dumps(base), encoding="utf-8")
                    hold = import_production("scripts.ci.post_merge_hold")
                    with mock.patch.object(hold, "TUNABLES_FILE", path):
                        CHECK.assertEqual(state, self.verdict([make_run(7, "success", hours_ago=hours)])["state"])
        cases.check()
