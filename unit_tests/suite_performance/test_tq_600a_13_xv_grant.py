"""
Tests for TQ-600a-13-xv / -xi (security review 2026-10-12, M-2 and L-1, Python side) -- the minted token is checked against what was asked,
and the minted token is registered for masking before anything uses it.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml and TQ-600a-13-xi.yaml
"""

from __future__ import annotations

import sys

from ._app_fake import MASK, mask_lines, without_masks
from ._app_harness import AppTestCase
from ._ending_harness import Cases
from ._notice_fakes import REPO
from .test_tq_600a_13_xv_app import ACTIONS_WRITE, _Case, _named

NAME = REPO.split("/")[1]
GOOD_PERMISSIONS = {"actions": "write", "metadata": "read"}  # what the service really answers for {actions: write}: the implicit read-only metadata rides along
OTHER = {"name": "other", "full_name": f"{REPO.split('/')[0]}/other"}
THIS = {"name": NAME, "full_name": REPO}

WIDER = {  # label -> the part of the exchange answer to replace
    "contents: write added": {"permissions": {**GOOD_PERMISSIONS, "contents": "write"}},
    "issues: read added": {"permissions": {**GOOD_PERMISSIONS, "issues": "read"}},
    "a different permission altogether (checks: write)": {"permissions": {"checks": "write", "metadata": "read"}},
    "actions: read instead of write": {"permissions": {"actions": "read", "metadata": "read"}},
    "metadata widened to write": {"permissions": {"actions": "write", "metadata": "write"}},
    "no permissions in the answer": {"permissions": None},
    "permissions that are not a mapping": {"permissions": ["actions"]},
    "another repository as well": {"repositories": [THIS, OTHER]},
    "another repository instead": {"repositories": [OTHER]},
    "an empty repository list": {"repositories": []},
    "repositories that are not a list": {"repositories": "all"},
}


class TestAWiderGrantFailsClosed(_Case):
    def test_tq600a_13_xv_a_token_granted_wider_than_asked_is_not_used(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """M-2. The exchange answer is checked: the permissions must be exactly what was asked (plus the implicit read-only metadata) and
        the repositories, when present, exactly this one. Any widening: every would-be re-run is named `rerun_no_credential`, the job
        succeeds, not one re-run POST is made, and the token is never presented to the service or printed for use.
        Controls: the real answer (metadata read, this repository) and an answer that names no repositories re-run as usual."""
        rows = Cases()
        for label, grant in WIDER.items():
            result = self._run(grant=grant)
            with rows.case(f"{label}: nothing is re-run and every pull request is named"):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([], self.svc.rerun_ids())
                self.assertEqual(_named("rerun_no_credential"), sorted(result.unrerunnable or [], key=lambda e: e["pr"]))
            with rows.case(f"{label}: the wider token was never used"):
                self.assertEqual([], [a for a in self.svc.write_attempts if a["auth"] == "install"])
                self.assertEqual([], [path for path, auth in self.svc.read_auth if auth == "install"])
                self.assertEqual([], mask_lines(result.log), "a token that is not used is not even announced")
        for label, grant in {"the real answer": {}, "an answer naming no repositories": {"repositories": None}}.items():
            result = self._run(grant=grant)
            with rows.case(f"control, {label}: the holds are re-run"):
                self.assertEqual([1005, 1009, 1011], self.svc.rerun_ids())
                self.assertEqual([ACTIONS_WRITE], self.svc.exchanges)
        rows.check()


class TestTheHoldMasksItsCredentialsToo(AppTestCase):
    def test_tq600a_13_vi_the_hold_job_registers_its_jwt_and_token_for_masking(self):
        # covers: TQ-600a-13-vi
        # covers: TQ-600a-13-xv
        # angle: seam
        """L-1 for the hold (shell step only; post_merge_hold.py is unchanged). Execute the real job: its JWT and the installation token are
        each registered with `::add-mask::` exactly once, and neither appears anywhere else in the log."""
        self.seed("pass")
        executed = self.execute()
        log, svc = executed.text, self.svc
        jwts = sorted({b for b in svc.bearers if b.count(".") == 2})
        rows = Cases()
        with rows.case("the job ran and published"):
            self.assertEqual("success", executed.conclusion, log[-800:])
        with rows.case("the JWT and the token are each registered once, the JWT first"):
            self.assertEqual(jwts + svc.minted, mask_lines(log))
            self.assertLess(log.index(f"{MASK}{jwts[0]}"), log.index(f"{MASK}{svc.minted[0]}"))
        with rows.case("neither is printed anywhere else"):
            self.assertEqual([], [n[:8] for n in svc.credential_needles() if n in without_masks(log)])
            self.assertEqual([], executed.leaks)
        rows.check()


class TestTheMintedTokenIsMasked(_Case):
    def test_tq600a_13_xv_the_installation_token_is_registered_for_masking_before_its_first_use_and_printed_nowhere_else(self):
        # covers: TQ-600a-13-xv
        # angle: seam
        """L-1. Python prints `::add-mask::<token>` once, before the first re-run request, and the token appears in nothing else the
        job prints or writes. A mint that fails prints no mask line."""
        seen = []
        rows = Cases()
        result = self._run(on_rerun=lambda: seen.append(sys.stdout.getvalue()))
        token = self.svc.minted[0]
        with rows.case("exactly one masking command, for the minted token"):
            self.assertEqual([token], mask_lines(result.log))
            self.assertEqual(1, result.log.count(token))
        with rows.case("it was already printed when the first re-run request arrived"):
            self.assertEqual(3, len(seen))
            self.assertTrue(all(f"{MASK}{token}" in text for text in seen), "masked before every use")
        with rows.case("the token is nowhere else"):
            self.assertEqual([], self._leaks(result))
            self.assertNotIn(token, without_masks(result.log))
        result = self._run(exchange_status=403)
        with rows.case("a failed mint prints no masking command"):
            self.assertEqual([], mask_lines(result.log))
        rows.check()
