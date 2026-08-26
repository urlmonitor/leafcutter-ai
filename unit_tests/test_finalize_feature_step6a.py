"""
MODULE: test_finalize_feature_step6a
GOAL: Verify that finalize-feature.js step 6a never falsely claims tracking
    tickets were created (AC-2) and accurately reports untracked pre-existing
    failures (AC-1). Also verifies the step-map doc is consistent with the
    actual JS behaviour (AC-3).

    Also locks in the FIN-100e-1 / FIN-100e-2 reconciliation decision: those
    two AC records described a live create-ticket dispatch loop that was
    deliberately DISABLED under EPIC-FinalizeFeatureHardening (see the
    TestStep6aNoFalseTicketClaim / TestWithFailuresPath classes below for the
    disabled-behaviour lock-in). Per
    EPIC-BuildPipelinePhantomRemediation/04_fin100e_autoticketing_decision.md
    (option b, the ticket's stated default), FIN-100e-1 and FIN-100e-2 are now
    formally superseded (status: superseded_by, with an amended_by rationale)
    rather than left contradicting this disabled code. See
    TestStep6aContractMatchesDecision below.

TICKET: EPIC-FinalizeFeatureHardening/08_fix_dead_auto_ticketing.md,
    EPIC-BuildPipelinePhantomRemediation/04_fin100e_autoticketing_decision.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_MD_PATH = _REPO_ROOT / "templates" / "workflows" / "finalize-feature.md"
_AC_DIR = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "build_pipeline"
    / "FIN-100-pre-merge-safety-gate"
)
_FIN_100E_1_PATH = _AC_DIR / "FIN-100e-1.yaml"
_FIN_100E_2_PATH = _AC_DIR / "FIN-100e-2.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


def _md_text() -> str:
    """Return the prose workflow template text.

    Returns an empty string when the file has been retired (BP-300d deleted
    templates/workflows/finalize-feature.md). Tests that previously read this
    file must either use the empty-string fallback or repoint to _js_text().
    """
    if not _MD_PATH.exists():
        return ""
    return _MD_PATH.read_text(encoding="utf-8")


def _load_ac(path: Path) -> dict[str, Any]:
    """Read an AC YAML record straight off disk (real artifact, not a mock)."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# AC-1: step 6a emits an accurate report (not a false "tickets created" claim)
# ---------------------------------------------------------------------------

class TestStep6aNoFalseTicketClaim:
    """AC-1 / AC-2: step 6a must never push null into a 'created tickets' array
    and must not produce a message claiming tickets were created when they were not."""

    def test_no_push_null_into_created_tracking_tickets(self):
        """The old code did `createdTrackingTickets.push(null)` — this must be gone."""
        js = _js_text()
        # The null-push pattern should not exist
        assert "createdTrackingTickets.push(null)" not in js, (
            "step 6a must not push null into createdTrackingTickets; "
            "that variable has been replaced by untrackedFailures[]"
        )

    def test_created_tracking_tickets_variable_removed(self):
        """The `createdTrackingTickets` variable (which accumulated nulls) must be gone."""
        js = _js_text()
        assert "createdTrackingTickets" not in js, (
            "createdTrackingTickets was the source of the false count; "
            "it must be replaced by untrackedFailures[]"
        )

    def test_untracked_failures_variable_present(self):
        """untrackedFailures[] is the correct replacement accumulator."""
        js = _js_text()
        assert "untrackedFailures" in js, (
            "untrackedFailures[] must be declared and used in step 6a"
        )

    def test_untracked_failures_in_return_payload(self):
        """The return payload must expose untracked_failures, not created_tracking_tickets."""
        js = _js_text()
        assert "untracked_failures: untrackedFailures" in js, (
            "return payload must include untracked_failures: untrackedFailures"
        )
        assert "created_tracking_tickets" not in js, (
            "created_tracking_tickets must be removed from the return payload"
        )


# ---------------------------------------------------------------------------
# AC-2: success message accurately reflects zero tickets when none were created
# ---------------------------------------------------------------------------

class TestSuccessMessageAccuracy:
    """AC-2: the final success message must never say 'Tracking tickets created'
    unless tickets were actually created."""

    def test_false_tracking_tickets_created_message_removed(self):
        """The old message 'Tracking tickets created for pre-existing failures: N'
        must be gone (since N was always 0 — all entries were null)."""
        js = _js_text()
        assert "Tracking tickets created for pre-existing failures" not in js, (
            "This message claimed tickets were created when they were not; it must be removed"
        )

    def test_accurate_untracked_message_present(self):
        """The replacement message must mention 'not auto-ticketed' or equivalent."""
        js = _js_text()
        assert "not auto-ticketed" in js or "auto-ticketing disabled" in js, (
            "The success message must accurately state that auto-ticketing is disabled"
        )

    def test_no_path_produces_tracking_tickets_created_string(self):
        """Even partial matches of the old false claim must be absent."""
        js = _js_text()
        # The old pattern was: `Tracking tickets created for`
        assert "Tracking tickets created for" not in js


# ---------------------------------------------------------------------------
# AC-3: step-map doc describes actual behaviour (no stale create-ticket claim)
# ---------------------------------------------------------------------------

class TestStepMapDoc:
    """AC-3: finalize-feature.md must NOT claim step 6 dispatches create-ticket,
    and MUST describe the accurate untracked-failures reporting behaviour."""

    def test_no_stale_dispatch_create_ticket_in_step6(self):
        """Step 6 must not claim create-ticket is dispatched as an agent.

        The prose template (templates/workflows/finalize-feature.md) was retired
        by BP-300d. The live source of truth is now finalize-feature.js. This test
        guards the JS to ensure the stale dispatch claim was never introduced there.
        """
        # MD was retired (BP-300d); guard the live JS instead.
        js = _js_text()
        assert "dispatch `create-ticket` to produce an inbox tracking ticket" not in js, (
            "Step 6 (JS) must not claim create-ticket is dispatched as an agent"
        )

    def test_auto_ticketing_disabled_explained_in_doc(self):
        """Step 6 must explain that auto-ticketing is disabled.

        The prose template (templates/workflows/finalize-feature.md) was retired
        by BP-300d. The live source of truth is now finalize-feature.js, which
        contains the auto-ticketing explanation in the step 6 log() call.
        """
        # MD was retired (BP-300d); guard the live JS instead.
        js = _js_text()
        assert "auto-ticketing" in js.lower() or "Auto-ticketing" in js, (
            "Step 6 in finalize-feature.js must explain that auto-ticketing is disabled"
        )

    def test_untracked_failures_field_documented(self):
        """The doc or JS must reference untracked_failures as the return field."""
        md = _md_text()
        js = _js_text()
        assert "untracked_failures" in md or "untracked_failures" in js, (
            "untracked_failures must appear in either the step-map doc or the JS"
        )

    def test_manual_create_ticket_instruction_present(self):
        """Operators must be told to run /create-ticket manually."""
        # This instruction should appear in either the doc or the JS.
        md = _md_text()
        js = _js_text()
        assert "/create-ticket" in md or "/create-ticket" in js, (
            "The doc or JS must instruct the operator to run /create-ticket manually"
        )


# ---------------------------------------------------------------------------
# AC-4 (no-failures path): when triageReport is null, step 6a is skipped
# and untrackedFailures stays empty — no false claim is possible.
# ---------------------------------------------------------------------------

class TestNoFailuresPath:
    """AC-4 (no-failures path): when there are no pre_existing/flaky failures,
    untrackedFailures is empty and the success message makes no false claim."""

    def test_step6a_guarded_by_triage_report_null_check(self):
        """Step 6a must only run when triageReport is not null."""
        js = _js_text()
        # The guard 'if (triageReport !== null)' must wrap step 6a.
        assert "if (triageReport !== null)" in js, (
            "Step 6a must be guarded by 'if (triageReport !== null)' "
            "so it is skipped entirely when tests passed"
        )

    def test_untracked_failures_initialised_empty(self):
        """untrackedFailures must be initialised to [] (not to a populated array)."""
        js = _js_text()
        assert "const untrackedFailures = []" in js, (
            "untrackedFailures must be initialised to an empty array"
        )

    def test_success_message_only_emits_untracked_when_nonzero(self):
        """The success message for untracked failures is conditional on length > 0."""
        js = _js_text()
        # The pattern: (untrackedFailures.length > 0 ? ... : "")
        assert "untrackedFailures.length > 0" in js, (
            "The untracked-failures clause in the success message must be conditional "
            "on untrackedFailures.length > 0 so the no-failures path emits nothing"
        )


# ---------------------------------------------------------------------------
# AC-4 (with-failures path): when pre_existing/flaky entries exist, step 6a
# pushes objects into untrackedFailures and emits an informative log.
# ---------------------------------------------------------------------------

class TestWithFailuresPath:
    """AC-4 (with-failures path): when pre_existing/flaky entries exist,
    untrackedFailures is populated and an informative console.log is emitted."""

    def test_untracked_failures_push_with_test_id_and_category(self):
        """Step 6a must push {testId, category} objects (not null) into untrackedFailures."""
        js = _js_text()
        assert "untrackedFailures.push(" in js, (
            "Step 6a must push failure objects into untrackedFailures[]"
        )
        # Ensure it's not pushing null
        assert "untrackedFailures.push(null)" not in js

    def test_console_log_not_console_warn_for_report(self):
        """Step 6a must use console.log for the structured report (not console.warn,
        which implied an error condition that the user might suppress)."""
        js = _js_text()
        # The new approach uses console.log for the untracked report
        # Old code used console.warn; check that the misleading warn is gone.
        # We allow console.warn elsewhere in the file, but the step 6a block
        # specifically must not warn "automatic ticket creation skipped".
        assert "automatic ticket creation skipped" not in js, (
            "The misleading 'automatic ticket creation skipped' console.warn must be removed"
        )

    def test_report_mentions_auto_ticketing_disabled(self):
        """The structured report must clearly state auto-ticketing is disabled."""
        js = _js_text()
        assert "Auto-ticketing is disabled" in js or "auto-ticketing is disabled" in js, (
            "Step 6a must clearly state that auto-ticketing is disabled in its report"
        )


# ---------------------------------------------------------------------------
# FIN-100e-1 / FIN-100e-2 reconciliation: the code, this test module, and the
# two AC records must agree on ONE Step 6a contract. Today they do not: the
# code/this-test-module already lock in the DISABLED behaviour (see the
# classes above), but FIN-100e-1 ("one tracking ticket is created per
# pre-existing or flaky failure") and FIN-100e-2 ("ticket creation failure is
# non-fatal") are still `status: active` in the AC store, describing the
# opposite (a live create-ticket dispatch loop). This is a live decision the
# ticket asks the coder to resolve: either (a) re-enable the dispatch loop so
# the ACs' `status: active` claim becomes true, or (b, the ticket's stated
# default) formally supersede/retire the two ACs with a rationale and make
# this test module traceably reference that decision.
#
# EPIC-BuildPipelinePhantomRemediation/04_fin100e_autoticketing_decision.md
# ---------------------------------------------------------------------------

class TestStep6aContractMatchesDecision:
    """FIN-100e-1 / FIN-100e-2: the finalize-feature.js code, the Step 6a
    lock-in test, and the two AC records must agree on a single contract.
    Whichever option (a: re-enable, or b: supersede) the coder picks, the
    store and the code must stop contradicting each other."""

    def test_ac_status_matches_actual_js_dispatch_behaviour(self):
        # covers: FIN-100e-1
        # covers: FIN-100e-2
        """If FIN-100e-1/e-2 still claim `status: active` (a live create-ticket
        dispatch loop per pre_existing/flaky triage entry), finalize-feature.js
        must actually implement that loop (option a). Otherwise, both ACs
        must be formally retired -- `status` moved off `active` with a
        recorded rationale -- rather than left contradicting the disabled
        code (option b, the ticket's stated default).

        This is currently RED: the ACs are `status: active` (see FIN-100e-1
        line 9 / FIN-100e-2 line 9) but finalize-feature.js implements no
        create-ticket dispatch loop -- it deliberately reports
        untrackedFailures[] instead (see TestStep6aNoFalseTicketClaim above).
        """
        js = _js_text()
        ac1 = _load_ac(_FIN_100E_1_PATH)
        ac2 = _load_ac(_FIN_100E_2_PATH)

        dispatch_loop_present = (
            "create-ticket" in js
            and "createdTrackingTickets" in js
            and ("dispatch" in js.lower())
        )

        ac1_active = ac1.get("status") == "active"
        ac2_active = ac2.get("status") == "active"

        if ac1_active or ac2_active:
            # Option (a) is implied by an unretired `status: active` AC --
            # the dispatch loop the AC describes must actually exist.
            assert dispatch_loop_present, (
                "FIN-100e-1/FIN-100e-2 are still status:active (claiming "
                "Step 6a dispatches create-ticket per pre_existing/flaky "
                "entry, recording paths in created_tracking_tickets), but "
                "finalize-feature.js implements no such dispatch loop. "
                "Either re-enable the loop (option a) or formally supersede "
                "both ACs with a rationale (option b, the ticket's default) "
                "so the store stops asserting a behaviour the code was "
                "deliberately built not to perform."
            )
        else:
            # Option (b): both ACs must show a real retirement, not just an
            # arbitrary non-active status with no explanation.
            for ac_id, ac in (("FIN-100e-1", ac1), ("FIN-100e-2", ac2)):
                assert ac.get("status") in ("superseded_by", "deprecated"), (
                    f"{ac_id}.status is {ac.get('status')!r} -- neither "
                    "'active' (option a) nor a recognised retirement status "
                    "('superseded_by' / 'deprecated', option b). The "
                    "decision must be recorded unambiguously."
                )
                has_rationale = bool(ac.get("amended_by")) or bool(
                    ac.get("superseded_by")
                )
                assert has_rationale, (
                    f"{ac_id} is retired but carries no amended_by rationale "
                    "or superseded_by pointer explaining why Step 6a "
                    "auto-ticketing was disabled"
                )

    def test_disabled_step6a_test_documents_ac_supersession(self):
        # covers: FIN-100e-1
        # covers: FIN-100e-2
        """The ticket defaults to option (b) -- supersede FIN-100e-1/e-2 with
        a rationale -- unless the assignee confirms re-enabling is trivial
        and desired (no such confirmation is recorded on the ticket, and
        architect-review's sign-off comment independently recommends option
        (b) as lower-risk). This test locks in that default: this MODULE'S
        TOP DOCSTRING (the `MODULE:`/`GOAL:`/`TICKET:` header at the very top
        of this file) must be updated to name both FIN-100e-1 and FIN-100e-2,
        so the intentional disablement of Step 6a auto-ticketing is traceable
        from the lock-in test's own header back to the superseded AC records.

        Deliberately checks ONLY the module's top docstring (via `__doc__`)
        rather than the whole file: this test-writer phase's own explanatory
        comments further down this file already mention both AC IDs for
        readability, so scanning the whole file would pass trivially without
        the coder ever touching the header. Checking `__doc__` isolates the
        one piece of text only the implementing coder is expected to edit.

        If the assignee instead chooses option (a) -- re-enabling the
        dispatch loop, making FIN-100e-1/e-2 true again -- this specific
        assertion no longer applies and the coder should amend/remove it as
        part of that documented decision (see Source-of-Truth Discipline
        Rule 1: production_drift/consumer_drift classification belongs in
        `## Comments` before doing so).

        This is currently RED: the top docstring's `TICKET:` line still
        points at the old EPIC-FinalizeFeatureHardening ticket and names
        neither FIN-100e-1 nor FIN-100e-2.
        """
        header = __doc__ or ""
        assert "FIN-100e-1" in header, (
            "This test module's top docstring must reference FIN-100e-1 so "
            "the intentional Step 6a disablement is traceable to the "
            "superseded AC from the lock-in test's own header"
        )
        assert "FIN-100e-2" in header, (
            "This test module's top docstring must reference FIN-100e-2 so "
            "the intentional Step 6a disablement is traceable to the "
            "superseded AC from the lock-in test's own header"
        )
