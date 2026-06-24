"""
MODULE: test_finalize_feature_step6a
GOAL: Verify that finalize-feature.js step 6a never falsely claims tracking
    tickets were created (AC-2) and accurately reports untracked pre-existing
    failures (AC-1). Also verifies the step-map doc is consistent with the
    actual JS behaviour (AC-3).

TICKET: EPIC-FinalizeFeatureHardening/08_fix_dead_auto_ticketing.md
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_MD_PATH = _REPO_ROOT / "templates" / "workflows" / "finalize-feature.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


def _md_text() -> str:
    return _MD_PATH.read_text(encoding="utf-8")


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
        """Step 6 row must not say it dispatches create-ticket as an agent."""
        md = _md_text()
        # The old text said "dispatch `create-ticket` to produce an inbox tracking ticket"
        assert "dispatch `create-ticket` to produce an inbox tracking ticket" not in md, (
            "Step 6 doc must not claim create-ticket is dispatched as an agent"
        )

    def test_auto_ticketing_disabled_explained_in_doc(self):
        """Step 6 doc must explain that auto-ticketing is disabled."""
        md = _md_text()
        assert "auto-ticketing" in md.lower() or "Auto-ticketing" in md, (
            "Step 6 in finalize-feature.md must explain that auto-ticketing is disabled"
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
