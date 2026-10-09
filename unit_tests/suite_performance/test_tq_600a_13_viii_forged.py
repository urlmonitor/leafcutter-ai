"""
Tests for TQ-600a-13-viii, the record's forgery resistance -- only the Actions bot's marker comment counts as "already
recorded". Without that, a person could post the hidden marker on the notice and suppress the owner's one place to see every
bypass. Drives the REAL ``main`` against the recording fake with a passing current proof served.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-viii.yaml
(every exemption granted is recorded on issue N, at most once per pull request per red run)
"""

from __future__ import annotations

from ._comment_harness import BOT, HUMAN, OTHER_BOT, PR
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, HEAD, NOTICE, ExemptCase
from ._notice_fakes import import_production

RED_RUN_ID, PROOF_RUN_ID = 107, 205


def marker():
    """The hidden marker line, from the production module (the test must not restate its format)."""
    return import_production("scripts.ci._hold_exempt").marker_for(PR, RED_RUN_ID, PROOF_RUN_ID, HEAD)


class TestTq600a13viiiForged(ExemptCase):
    def test_tq600a_13_viii_a_forged_marker_does_not_suppress_the_record(self):
        # covers: TQ-600a-13-viii
        # angle: discrimination
        """The exact marker for this pull request and red run, posted on the notice by a person, by another bot, and by a person
        with extra text around it, does not count as recorded: the exemption is still granted and recorded once by the Actions
        bot. Control: the same marker authored by `github-actions[bot]` is already recorded, so nothing is written.

        Wrong version caught: any comment carrying the marker (whoever wrote it) suppressing the record.
        """
        cases = Cases()
        forgers = {"a person": HUMAN, "another bot": OTHER_BOT, "a person quoting the marker in prose": HUMAN}
        for label, author in forgers.items():
            with cases.case(label):
                self.svc.reset()
                self.stage()
                text = f"please ignore\n{marker()}\n" if "prose" in label else f"{marker()}\n"
                self.svc.add_comment(NOTICE, text, user=author)
                ran = self.drive_body(DECL)
                CHECK.assertEqual(0, ran.code, ran.out)
                self.expect_one_record()
                CHECK.assertEqual([BOT], [c["user"] for c in self.svc.pr_comments[NOTICE][1:]])
        with cases.case("control: the Actions bot's own marker is already recorded"):
            self.svc.reset()
            self.stage()
            self.svc.add_comment(NOTICE, f"{marker()}\nrecorded earlier\n", user=BOT)
            ran = self.drive_body(DECL)
            CHECK.assertEqual(0, ran.code, ran.out)
            CHECK.assertEqual([], self.record_writes())
        cases.check()
