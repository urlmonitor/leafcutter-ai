"""
MODULE: unit_tests/workflows/test_bo3900e_depends_on_resolved_beside_ticket.py
GOAL: Behavioral tests for BO-3900e — a ticket's depends_on prerequisite is
    resolved where the ticket frontmatter hook resolves it (beside the
    dependant's own ticket), never joined onto the worktree root, and the
    run-set membership check and the per-ticket release gate can never
    disagree about where it lives.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_3d2879c1-2ae, 2026-09-16. Ticket
    07_TICKET-20260909-UXP-700a-3.md named its sibling
    02_TICKET-20260909-UXP-700a-1.md by BARE filename in depends_on. Both
    readers resolved it via toWorktreePath(entry, worktreePath), landing on
    "<worktree-root>/02_TICKET-20260909-UXP-700a-1.md" — a file that never
    existed there, though the real sibling read status: done beside ticket
    07. The gate reported "not_in_run_set" and withheld 7 of 9 tickets. See
    BO-3900e.yaml.
ARCHITECTURE: The criterion/boundary/seam/failure angles drive the REAL
    resolveDependsOnPath() extracted out of build-feature.js's own source
    text via unit_tests/workflows/_bo3900e_resolver_harness.py, with a
    caller-controlled per-path readTicketRecordBack stub — the ONLY way to
    prove the candidate fallback ORDER (done/ subfolder, ticket-itself-in-
    done/) precisely, since unit_tests/_workflow_engine_harness.py's agent()
    mock gives one static reply per label and cannot tell one candidate
    path apart from another. The reachability angle drives build-feature.js's
    own top-level body through unit_tests/_workflow_engine_harness.py's
    run_workflow_under_e2(), per BO-3900's own test_rationale: a helper-only
    test stays green even if a call site never invokes the real helper.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo3900_fixtures as bo3900fx  # noqa: E402
from unit_tests.workflows import _bo3900e_fixtures as fx  # noqa: E402
from unit_tests.workflows._bo3900e_resolver_harness import (  # noqa: E402
    resolve_depends_on_path,
)

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"


class TestBareSiblingPrerequisiteIsReadBesideTheTicket(unittest.TestCase):
    def test_bare_sibling_prerequisite_is_read_beside_the_ticket(self) -> None:
        # covers: BO-3900e
        # angle: criterion
        """A done prerequisite named by bare filename is read from the
        dependant's own folder (beside the ticket), not joined onto the
        worktree root — the incident's own shape. A candidate readable only
        at the worktree-root join (the old bug's own location) is absent
        from the map, so a resolution that fell back to it would report
        `resolved: None` here, not the sibling.
        """
        result = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.PREDECESSOR_ENTRY_BARE,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {fx.PREDECESSOR_SIBLING_PATH: fx.readback_done()},
        )
        self.assertEqual(result["resolved"], fx.PREDECESSOR_SIBLING_PATH)
        self.assertNotEqual(result["resolved"], fx.PREDECESSOR_ROOT_JOINED_PATH)
        self.assertEqual(result["record"]["lifecycle_status"], "done")


class TestDoneSubfolderAndLegacyPrefixesResolve(unittest.TestCase):
    def test_prerequisite_in_done_subfolder_and_legacy_tickets_prefix_resolve(
        self,
    ) -> None:
        # covers: BO-3900e
        # angle: boundary
        """A sibling moved to done/, a ticket that is itself in done/, a
        `tickets/`-prefixed entry, and an absolute entry each resolve to
        the documented location — mirroring the ticket frontmatter hook's
        own order (ticket-authoring SKILL.md, "depends_on Resolution").
        """
        moved_to_done = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.PREDECESSOR_ENTRY_BARE,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {fx.PREDECESSOR_DONE_SUBFOLDER_PATH: fx.readback_done()},
        )
        self.assertEqual(moved_to_done["resolved"], fx.PREDECESSOR_DONE_SUBFOLDER_PATH)

        ticket_itself_in_done = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            "02_TICKET-b.md",
            fx.TICKET_IN_DONE_WORKTREE,
            fx.WORKTREE,
            {fx.PREDECESSOR_EPIC_ROOT_PATH: fx.readback_done()},
        )
        self.assertEqual(
            ticket_itself_in_done["resolved"], fx.PREDECESSOR_EPIC_ROOT_PATH
        )

        tickets_prefixed = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.ENTRY_TICKETS_PREFIXED,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {fx.ENTRY_TICKETS_PREFIXED_RESOLVED: fx.readback_done()},
        )
        self.assertEqual(
            tickets_prefixed["resolved"], fx.ENTRY_TICKETS_PREFIXED_RESOLVED
        )

        absolute = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.ENTRY_ABSOLUTE,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {fx.ENTRY_ABSOLUTE_RESOLVED: fx.readback_done()},
        )
        self.assertEqual(absolute["resolved"], fx.ENTRY_ABSOLUTE_RESOLVED)


class TestMembershipCheckAndReleaseGateShareOneResolver(unittest.TestCase):
    def test_membership_check_and_release_gate_resolve_depends_on_identically(
        self,
    ) -> None:
        # covers: BO-3900e
        # angle: seam
        """The run-set membership check and the release gate both call the
        SAME resolveDependsOnPath(...) — verified structurally at each call
        site's own source window, so a fix applied to only one of them (the
        defect's own historical shape: two call sites resolving
        independently) is caught. Both windows are also proven to compute
        an identical resolution for the same inputs, since it is literally
        one function.
        """
        source = _BUILD_FEATURE_JS.read_text(encoding="utf-8")
        membership_anchor = source.find("const dependencyRecord = await readTicketRecordBack(normalized);")
        release_gate_anchor = source.find(
            "const dependencyRecord = await readTicketRecordBack(worktreeTicketPath);"
        )
        self.assertNotEqual(membership_anchor, -1, "membership-check call site not found")
        self.assertNotEqual(release_gate_anchor, -1, "release-gate call site not found")
        membership_window = source[membership_anchor : membership_anchor + 400]
        release_gate_window = source[release_gate_anchor : release_gate_anchor + 400]
        self.assertIn(
            "resolveDependsOnPath(",
            membership_window,
            "membership check no longer resolves depends_on through the shared resolver",
        )
        self.assertIn(
            "resolveDependsOnPath(",
            release_gate_window,
            "release gate no longer resolves depends_on through the shared resolver",
        )

        as_membership_check_would_see_it = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.PREDECESSOR_ENTRY_BARE,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {fx.PREDECESSOR_SIBLING_PATH: fx.readback_done()},
        )
        as_release_gate_would_see_it = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.PREDECESSOR_ENTRY_BARE,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {fx.PREDECESSOR_SIBLING_PATH: fx.readback_done()},
        )
        self.assertEqual(
            as_membership_check_would_see_it["resolved"],
            as_release_gate_would_see_it["resolved"],
        )


class TestMissingPrerequisiteReportedBesideTheTicket(unittest.TestCase):
    def test_missing_prerequisite_is_reported_beside_the_ticket_not_at_the_root(
        self,
    ) -> None:
        # covers: BO-3900e
        # angle: failure
        """A prerequisite that exists nowhere is reported at its sibling
        path — the first candidate beside the ticket — never at a
        worktree-root join the ticket never named (the old bug's shape).
        """
        result = resolve_depends_on_path(
            _BUILD_FEATURE_JS,
            fx.PREDECESSOR_ENTRY_BARE,
            fx.TICKET_07_WORKTREE,
            fx.WORKTREE,
            {},
        )
        self.assertIsNone(result["resolved"])
        self.assertEqual(result["reported"], fx.PREDECESSOR_SIBLING_PATH)
        self.assertNotEqual(result["reported"], fx.PREDECESSOR_ROOT_JOINED_PATH)


class TestReachableFromTheWorkflowTopLevelBody(unittest.TestCase):
    def test_prerequisite_resolution_is_reachable_from_the_workflow_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900e
        # angle: reachability
        """A resumed epic run through _workflow_engine_harness.py — ticket
        07 depends on sibling 02 by bare filename, and 02 already reads
        status: done — dispatches the sibling's OWN readTicketRecordBack
        probe at its sibling path (beside ticket 07), never at the
        worktree-root join the incident's own bug produced. Drives
        build-feature.js's own top-level body, not a reimplementation nor
        an extracted copy of the resolver: the incident's own defect was
        the SHIPPED script's call site joining onto the root, which a test
        of the resolver alone (see the criterion angle above) would not
        have caught if that call site had kept calling the old helper.
        """
        label_responses = bo3900fx.base_epic_label_responses(
            epic_path=fx.EPIC_PATH,
            worktree_path=fx.WORKTREE,
            ticket_paths=[fx.TICKET_07_REL],
        )
        label_responses["signoff-readback"] = fx.readback_done(
            depends_on=[fx.PREDECESSOR_ENTRY_BARE]
        )
        result = run_workflow_under_e2(
            _BUILD_FEATURE_JS,
            label_responses=label_responses,
            args={"target": fx.EPIC_PATH},
        )
        readback_calls = [c for c in result.agent_calls if c.label == "signoff-readback"]
        joined_prompts = "\n".join(c.prompt or "" for c in readback_calls)
        self.assertIn(
            fx.PREDECESSOR_SIBLING_PATH,
            joined_prompts,
            f"sibling was never probed at its own path; stderr={result.stderr!r}",
        )
        self.assertNotIn(fx.PREDECESSOR_ROOT_JOINED_PATH, joined_prompts)
        planner_calls = [c for c in result.agent_calls if c.label == "ticket-planner"]
        self.assertTrue(
            planner_calls,
            f"ticket 07 was never dispatched to ticket-planner; stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()


# DECISION HISTORY
# ================================================================================
# - 2026-09-16 12:00 [python-coder]: Created — BO-3900e's own depends_on resolver
#   tests, driven from run wf_3d2879c1-2ae's field evidence.
#   (#TICKETLESS reason=ac-bo-3900e-direct-implementation)
