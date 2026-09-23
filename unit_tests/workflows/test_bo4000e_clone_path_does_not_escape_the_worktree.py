"""
MODULE: unit_tests/workflows/test_bo4000e_clone_path_does_not_escape_the_worktree.py
GOAL: Behavioral tests for BO-4000e — an absolute MAIN-CLONE path coming back
    from resolve is re-rooted into the run's worktree before it reaches the
    planner or any phase agent, so no dispatch ever names the clone.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_ecb6b1ae-a1c, 2026-09-21. resolve
    returned epic_path as an absolute main-clone path. toWorktreePath returns
    an absolute path as-is by BO-3900's ratified contract, so every
    toWorktreePath call in the drive was a no-op and the whole run planned and
    dispatched against the clone while realWorktreePath pointed at the
    worktree. The branch's committed progress was invisible: ticket 01 was
    `status: done` in the worktree and `status: todo` with
    `test-writer: failed` in the clone, so a finished ticket was re-driven from
    scratch and halted on a stale failure. Phase agents then WROTE to the clone
    — it was left dirty on `main` with sign-offs and a .pending/ directory.
ARCHITECTURE: The fix corrects the INPUT rather than BO-3900's rule:
    repoRelativeTicketPath() reduces an absolute main-clone ticket path to its
    repo-relative tail so toWorktreePath's relative branch re-roots it onto the
    worktree exactly once. BO-3900's return-an-absolute-path-as-is contract is
    deliberate (it prevents double-joining) and is untouched. Verified by
    running build-feature.js's own top-level body under
    unit_tests/_workflow_engine_harness.py and reading the real dispatches.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"

_EPIC_TAIL = "tickets/00_inbox/epics/" + bfx.EPIC_NAME
# What resolve actually handed back in the incident: the epic inside the CLONE.
CLONE_EPIC_PATH = bfx.MAIN_CHECKOUT + "/" + _EPIC_TAIL
# Where that same epic lives inside the run's own worktree.
WORKTREE_EPIC_PATH = bfx.NAMED_LOCATION + "/" + _EPIC_TAIL
TICKET = _EPIC_TAIL + "/01_TICKET-x.md"

# Dispatches that legitimately name the main checkout, and why. `resolve-target`
# runs before any worktree exists and is handed the raw target. The repository-facts
# probes ASK git about the repository and must anchor on a path known to be inside it
# (BO-4000d); anchoring them on the worktree would be circular, since establishing
# whether that worktree is real is the very question they answer. None of these
# performs work on a ticket. Every label NOT listed here does, and must be
# worktree-resident — keeping this set as small as it is, is what stops the record
# from being satisfied vacuously.
_REPOSITORY_PROBE_LABELS = frozenset({
    "resolve-target", "worktree-facts-resolved", "worktree-base",
    "worktree-facts-location", "branch-standing",
})


def _run(epic_path: str):
    """Drive build-feature.js with *epic_path* as resolve's epic_path.

    The worktree is pre-resolved and confirmed healthy, so the run takes
    BO-4000 scenario 1 (reuse) and goes straight on to planning — which is
    where the clone path did its damage.
    """
    responses = bfx.success_label_responses(
        ticket_paths=[TICKET],
        resolved_worktree_path=bfx.NAMED_LOCATION,
    )
    responses["resolve-target"] = {
        "target_type": "epic",
        "epic_path": epic_path,
        "ticket_path": None,
        "worktree_path": bfx.NAMED_LOCATION,
    }
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=responses, args={"target": epic_path}
    )


def _prompts(result) -> list[str]:
    """Every captured dispatch prompt, as text."""
    return [str(call.prompt) for call in result.agent_calls]


class TestCloneEpicPathIsRerootedIntoTheWorktree(unittest.TestCase):
    def test_no_dispatch_names_a_location_inside_the_main_clone(self) -> None:
        # covers: BO-4000e
        # angle: criterion
        """The whole point: once a worktree is established, nothing the run
        dispatches may name a path inside the main checkout. This is the
        property whose absence let phase agents edit the clone on `main`.
        """
        result = _run(CLONE_EPIC_PATH)
        offenders = sorted({
            f"{call.label}: ...{str(call.prompt)[max(0, str(call.prompt).index(bfx.MAIN_CHECKOUT + '/')):][:120]}..."
            for call in result.agent_calls
            if call.label not in _REPOSITORY_PROBE_LABELS
            and bfx.MAIN_CHECKOUT + "/" in str(call.prompt)
        })
        self.assertEqual(
            offenders, [],
            "a dispatch named a path inside the main clone; the drive is "
            "operating outside its worktree",
        )

    def test_the_planner_is_given_the_worktree_copy_of_the_epic(self) -> None:
        # covers: BO-4000e
        # angle: real_artifact
        """Paired positive: it is not enough that the clone path is absent —
        the worktree-rooted epic path must actually be the one handed on, or
        this record would pass on a run that dispatched nothing at all.
        """
        result = _run(CLONE_EPIC_PATH)
        self.assertTrue(
            any(WORKTREE_EPIC_PATH in p for p in _prompts(result)),
            f"no dispatch named {WORKTREE_EPIC_PATH!r}",
        )


class TestOtherResolveShapesAreUnaffected(unittest.TestCase):
    def test_a_repo_relative_epic_path_still_lands_in_the_worktree(self) -> None:
        # covers: BO-4000e
        # angle: boundary
        """The shape that already worked keeps working — the fix must not be
        a repair that only the broken input benefits from.
        """
        result = _run(_EPIC_TAIL)
        self.assertTrue(
            any(WORKTREE_EPIC_PATH in p for p in _prompts(result)),
            f"no dispatch named {WORKTREE_EPIC_PATH!r}",
        )

    def test_an_epic_path_already_inside_the_worktree_is_left_where_it_is(self) -> None:
        # covers: BO-4000e
        # angle: seam
        """Idempotence. Re-rooting strips to the repo-relative tail and joins
        once, so a path that is already worktree-resident must come back
        unchanged rather than acquiring a second copy of the tail.
        """
        result = _run(WORKTREE_EPIC_PATH)
        prompts = _prompts(result)
        self.assertTrue(
            any(WORKTREE_EPIC_PATH in p for p in prompts),
            f"no dispatch named {WORKTREE_EPIC_PATH!r}",
        )
        doubled = bfx.NAMED_LOCATION + "/" + _EPIC_TAIL + "/" + _EPIC_TAIL
        self.assertEqual(
            [p for p in prompts if doubled in p], [],
            "the epic tail was joined onto a path that already carried it",
        )


if __name__ == "__main__":
    unittest.main()
