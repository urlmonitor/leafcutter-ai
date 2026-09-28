"""
MODULE: test_bo_400e_4_batching
GOAL: Cover ADR-048 Section 3's no-batching half -- N tickets closing in the
    same build-feature.js run must produce N distinct ticket-completion-write
    dispatches, each naming exactly one ticket's own path, never one dispatch
    that closes several tickets at once.
BUSINESS CONTEXT: Added per coordinator ruling, 2026-09-22, on the
    green-on-first-run finding in the sibling BO-400e-4 test modules.

    ADR-048 Section 3 states two distinct requirements:

      "one ticket's close MUST NOT be conducted in a conversation, session,
       or context that has already handled another ticket's close in the
       same run, and several tickets' closes MUST NOT be batched into one
       dispatch."

    THE FIRST HALF (session/conversation freshness) is NOT tested anywhere
    in this module, and deliberately so. `harness_build_ticket_guard.mjs`'s
    mocked `agent()` is a plain synchronous JS function with no session or
    conversation concept at all -- inventing one here to make that half
    "testable" would mean asserting against a model this suite made up, not
    against the real dispatcher's behaviour, and a green result would prove
    nothing about the real engine. Per the coordinator's ruling: do not
    chase it with a fabricated harness feature.

    That half is instead satisfied BY CONSTRUCTION, not by a test result:
    `writeTicketCompletion`'s own `agent()` call (build-feature.js:1301-1314)
    passes only `{agentType: "status-checker", schema: COMPLETION_WRITE_SCHEMA,
    label: "ticket-completion-write", phase: "Phase Dispatch"}`. The
    workflow engine's `agent()` global itself accepts NO session,
    conversation, or resume-handle key at all -- see build-feature.js:2105-
    2107's own comment: "Prose is the ONLY channel. agent(prompt, opts)
    accepts exactly {agentType, schema, label, phase, model, effort,
    isolation} -- an extra ... key placed in opts is dropped before the
    agent ever sees it." There is no `session_id`, `conversation_id`, or
    `resume` key in that list, and no code path anywhere in this driver
    constructs one. So the driver has no mechanism through which it COULD
    ask two dispatches to share a context even if it wanted to -- each
    `agent()` call is necessarily a fresh invocation. This is an argument
    from the engine's own construction, cited above with exact line
    numbers; it is not a test result, and no test below asserts it.

    THE SECOND HALF (no batching) IS a real, falsifiable property of a run,
    and is what the test below asserts: N tickets closing in the same run
    must produce N distinct `ticket-completion-write` dispatches, each
    naming exactly one ticket's own path -- never one dispatch that closes
    several tickets at once. A future "batch the closes for efficiency"
    refactor would turn this test RED, which is exactly the regression this
    half of Section 3 exists to catch. Per the coordinator's ruling, this
    test is EXPECTED to be green today (there is no current batching to
    reproduce); its value is as a REGRESSION GUARD against a batching
    refactor being introduced later, exactly like this suite's other
    behavioural tests guard the already-satisfied order-independence
    property.
ARCHITECTURE: Carried out of test_bo_400e_4.py (GE-127a-1 / GE-127b-1
    file-size split, no behaviour change). Subclasses
    test_bo_400e_4_fixtures._FourTicketOneRunCase but uses its OWN, smaller
    two-ticket fixture (CLOSING_PHASES / CLOSING_NAMES) rather than the
    identical-trio-plus-control fixture the other sibling modules share --
    N=2 fully-signed-off tickets is the smallest N that can distinguish "one
    dispatch per closing ticket" from "one dispatch closes several tickets
    at once".
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from test_bo_400e_4_fixtures import EPIC_SUBDIR, _FourTicketOneRunCase  # noqa: E402


class TestEachClosingTicketGetsItsOwnCompletionWriteDispatchNeverBatched(
    _FourTicketOneRunCase
):
    #: A different, smaller fixture than the identical-trio-plus-control
    #: fixture in test_bo_400e_4_fixtures: TWO tickets, BOTH fully signed
    #: off, so BOTH close in the same run. N=2 is the smallest N that can
    #: distinguish "one dispatch per closing ticket" from "one dispatch
    #: closes several tickets at once" -- N=1 (the control ticket elsewhere
    #: in this suite) cannot, because there is nothing else in the run for
    #: it to be batched with.
    CLOSING_PHASES = ["test-writer", "python-coder", "commit"]
    CLOSING_NAMES = ("05_closing_one.md", "06_closing_two.md")

    def _write_closing_ticket(self, worktree: str, name: str) -> str:
        return H.write_ticket_record(
            worktree,
            name,
            self.CLOSING_PHASES,
            title=name,
            subdir=EPIC_SUBDIR,
            agent_statuses=dict.fromkeys(self.CLOSING_PHASES, "signed_off"),
            seeded_signoffs=[(p, "ok") for p in self.CLOSING_PHASES],
        )

    @classmethod
    def _closing_cfg(cls, name: str) -> dict:
        ordered = [{"agent": p, "status": "signed_off"} for p in cls.CLOSING_PHASES]
        return {"title": name, "has_test_requirements": True, "ordered_phases": ordered}

    def test_each_closing_ticket_gets_its_own_completion_write_dispatch_never_batched(
        self,
    ):
        # covers: BO-400e-4
        # angle: criterion
        """ADR-048 Section 3, no-batching half only (see the module-level
        note above this class for the session-freshness half, which is
        satisfied by construction and is not what this test asserts). Two
        tickets, both fully signed off, carried by ONE build-feature.js run:
        both must close, and each close must be its OWN
        ticket-completion-write dispatch naming exactly one ticket path --
        never a single dispatch that closes both at once."""
        worktree = self._worktree()
        epic_path = os.path.join(worktree, EPIC_SUBDIR)
        os.makedirs(epic_path, exist_ok=True)

        paths = [self._write_closing_ticket(worktree, n) for n in self.CLOSING_NAMES]
        tickets_cfg = {
            p: self._closing_cfg(n) for p, n in zip(paths, self.CLOSING_NAMES)
        }
        present = [{"path": p, "status": "todo"} for p in paths]
        reads = [{"present": present}]
        scenario = H.epic_scenario(worktree, epic_path, tickets_cfg, reads)
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        self.assertIsNone(observation["error"], observation.get("error"))

        # Precondition: both tickets really did close.
        for path in paths:
            record = H.read_record(path)
            self.assertEqual(
                record["lifecycle_status"],
                "done",
                f"harness precondition failed for {os.path.basename(path)}: "
                f"{record}",
            )

        completion_writes = [
            w
            for w in (observation.get("writes") or [])
            if w.get("label") == "ticket-completion-write"
        ]
        self.assertEqual(
            len(completion_writes),
            len(paths),
            f"expected exactly {len(paths)} ticket-completion-write dispatches "
            f"(one per closing ticket), got {len(completion_writes)}: "
            f"{completion_writes}",
        )

        # NO BATCHING: each dispatch's own prompt must name exactly ONE of
        # the two closing tickets' real on-disk paths -- never both.
        for write in completion_writes:
            named = [p for p in paths if p in (write.get("prompt") or "")]
            self.assertEqual(
                len(named),
                1,
                f"a single ticket-completion-write dispatch named "
                f"{len(named)} ticket path(s) -- a batched close. write: "
                f"{write}",
            )

        # And each of the two closing tickets got its OWN write -- not the
        # same write attributed to it twice, and not one ticket's write
        # missing while the other's covers for it.
        write_ticket_paths = sorted(w["ticket_path"] for w in completion_writes)
        self.assertEqual(
            write_ticket_paths,
            sorted(paths),
            f"the two closing tickets did not each receive their own distinct "
            f"completion-write dispatch: {write_ticket_paths} vs {sorted(paths)}",
        )
