"""
MODULE: test_finalize_feature_single_writer_close
GOAL: Verify BO-400e-3-i — finalization closes a ticket through the same checking
    mechanism the drivers use (scripts/set_ticket_status.py), or leaves it open and
    says so. No step may write the finished state by editing the record directly,
    and the blanket override is never used.

BUSINESS CONTEXT: FIELD EVIDENCE — found 2026-09-23 by BO-400e-5's close-path
    sequence diagram, not by a drive and not by a test. That record required every
    participant able to write the recorded state to appear, "so that a route which is
    not drawn is a route which does not exist"; enumerating the writers surfaced this
    one. finalize-feature.js step 3.5 sub-step C read each open ticket, replaced the
    status line in its frontmatter and wrote the file back — no parity check, no
    transition validation, no possibility of refusal — over every still-open ticket of
    the epic being finalized. A ticket the drivers had correctly REFUSED to close was
    closed anyway, one step later in the lifecycle. Filed as KI-BO-20260923-0630;
    ADR-047 §1 says the finished state has exactly one writer.

ARCHITECTURE: Structural tests over the text of finalize-feature.js. The deliverable
    here IS prompt text — instructions a dispatched agent receives, not control flow
    the unit layer can execute — so asserting on that text is asserting on the shipped
    artifact rather than on a proxy for it; the usual "a grep test passes on dead code"
    objection does not apply when the source is the deliverable. This also follows the
    established precedent for this same file and same step in
    test_finalize_feature_step35_scope.py, which guards step 3.5's instructions the
    same way, including two negative assertions of this exact shape
    (test_no_whole_store_scan_instruction, test_no_worktree_walk_instruction).

    The negative test scans the WHOLE finalization prompt rather than sub-step C, so a
    direct write reintroduced in a different sub-step fails it too.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

_STATUS_SCRIPT = "set_ticket_status.py"


def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


class TestFinalizationUsesTheCheckingMechanism:
    """BO-400e-3-i: the close goes through the one writer, like the drivers' close does."""

    def test_finalization_closes_through_the_checking_mechanism(self) -> None:
        # covers: BO-400e-3-i
        # angle: criterion
        """Sub-step C must invoke the status script with --status done.

        Sub-step D directly below already invokes mark_ac_done.py this way; C was the
        only step in the prompt that reached for the file itself.
        """
        js = _js_text()
        assert _STATUS_SCRIPT in js, (
            "finalize-feature.js must invoke scripts/set_ticket_status.py to close a "
            "ticket — it is the sole writer of the finished state (ADR-047 §1)"
        )
        assert re.search(rf"{re.escape(_STATUS_SCRIPT)}[^\n]*--status done", js), (
            "the status script must be invoked with --status done in the closure step"
        )

    def test_no_step_writes_the_finished_state_directly(self) -> None:
        # covers: BO-400e-3-i
        # angle: failure
        """No instruction anywhere may tell the agent to write the status line itself.

        Scanned across the whole file rather than within sub-step C, so the defect
        simply moving to another sub-step does not pass.
        """
        js = _js_text()
        direct_write = re.compile(
            r"(Replace|Rewrite|Edit|Set|Change)[^\n]{0,80}`?status:[^\n]{0,80}"
            r"(frontmatter|line)|(frontmatter|line)[^\n]{0,80}`?status:[^\n]{0,60}"
            r"(with|to)\s+`?status:\s*done",
            re.IGNORECASE,
        )
        offenders = [m.group(0).strip() for m in direct_write.finditer(js)]
        assert offenders == [], (
            "finalize must not instruct a direct frontmatter write of the finished "
            f"state; found: {offenders}"
        )

    def test_the_blanket_override_is_not_used(self) -> None:
        # covers: BO-400e-3-i
        # angle: failure
        """--force must never appear on a status-script invocation.

        The override also switches off the parity check, so reaching for it here would
        reinstate the ungated write behind a flag rather than remove it (ADR-047).
        """
        js = _js_text()
        forced = [
            line.strip()
            for line in js.splitlines()
            if _STATUS_SCRIPT in line and "--force" in line
        ]
        assert forced == [], (
            f"the status script must never be invoked with --force; found: {forced}"
        )

    def test_a_refused_close_leaves_the_ticket_open_and_is_reported(self) -> None:
        # covers: BO-400e-3-i
        # angle: boundary
        """A non-zero exit must name the ticket and leave it unclosed.

        Without this the step could invoke the mechanism and then ignore its refusal,
        which is the same defect wearing the mechanism's name.
        """
        js = _js_text()
        assert re.search(r"non-zero[^\n]{0,200}(REFUS|not closed)", js, re.IGNORECASE), (
            "the closure step must state what happens on a non-zero exit — the ticket "
            "is not closed, and the refusal is reported against it by name"
        )
