"""Behavioral tests for the ticket_path pointer in a phase dispatch (H-4).

Covers:
  BO-1900d-1 — "Given a dispatch payload whose keys are exactly the allowlisted
               pointers (ticket_path, worktree_path, branch, files_touched)
               with well-formed values ... the phase agent is spawned with only
               those pointer values."

SCOPE NOTE ON BO-1900d-1's SECOND CLAUSE. The AC also says "no free-composed
prose prompt is attached to the dispatch". That half is NOT satisfiable under
the current runtime contract and is deliberately NOT asserted here: the workflow
``agent(prompt, opts)`` call accepts only ``{agentType, schema, label, phase,
model, effort, isolation}``. There is no arbitrary-args channel — an extra
``ticket_path`` key placed in the opts object is dropped before the agent ever
sees it. Prose is the ONLY channel from a workflow driver to a phase agent.

What IS assertable, and what these tests assert, is the pointer half: the
dispatch must name the ticket as an explicit ``ticket_path: <path>`` pointer
token, in the form the agent templates and the in-repo convention already use —
not merely mention the path in narrative prose.

WHY THIS IS THE FIX AND NOT WORDING PEDANTRY.

  templates/agents/_signoff_block.md, line 1 and line 35, carried by 30 agent
  templates including every phase agent:

      ## Sign-off (when ticket_path is provided)
      If you were invoked with a `ticket_path` argument:
      ...
      8. Skip this entire section if no `ticket_path` was provided.

  templates/workflows-js/build-epic.js:357 — the in-repo convention for handing
  an agent a pointer through the prose channel:

      `Drive ticket to completion: ${ticket.path}. Worktree: ${worktreePath}.
       Execute all needed phase agents in order. worktree_path: ${worktreePath}`

  ...note the trailing literal `worktree_path: <path>` token.

  templates/workflows-js/build-feature.js:1119 and build-ticket.js:960 — what
  the two twins send today:

      `You are the ${phaseName} phase agent for ticket: ${worktreeTicketPath}.
       Read the ticket before starting. ...`

  The path is present, but as narrative ("for ticket: <path>"), never as the
  `ticket_path` pointer the templates' own conditional keys on. Whether a gate
  records its sign-off is therefore left to whether the model reads the
  narrative form as satisfying its conditional — which is a very plausible
  mechanism for BUG-23 being INCONSISTENT rather than uniformly absent (run
  wf_cc2b46d9-f6f: ticket 09 recorded test-runner and lost pr-reviewer; ticket
  03 recorded pr-reviewer and lost test-runner; ticket 01 lost both).

  The coupling between the drivers and those 30 templates exists whether or not
  it is tested. An untested coupling is the status quo that produced BUG-23.

The matcher below is deliberately permissive about surrounding wording: it
accepts `ticket_path: <path>`, `ticket_path = <path>`, `"ticket_path": "<path>"`
and backtick-quoted variants. It pins the POINTER, not the sentence.

n_location_rule is 2 — the dispatch call in build-feature.js and its twin in
build-ticket.js must stay identical — so the single-ticket test runs against
both drivers via subTest.

Every test EXECUTES a real driver through harness_build_ticket_guard.mjs and
asserts on the dispatch strings the run actually emitted. A source-reading test
cannot do this job: both the broken driver and the fixed one contain the
ticket path in their dispatch template, and only running the driver shows the
assembled string a phase agent would receive.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

FOUR_PHASES = ["test-writer", "python-coder", "test-runner", "commit"]


def ticket_path_pointer(prompt: str, path: str) -> bool:
    """True when ``prompt`` names ``path`` as an explicit ticket_path pointer.

    Accepted forms (the key and the value may each be quoted with ", ' or `):

        ticket_path: /abs/path.md
        ticket_path=/abs/path.md
        "ticket_path": "/abs/path.md"
        `ticket_path`: `/abs/path.md`

    Rejected: any purely narrative mention such as "for ticket: /abs/path.md",
    because that is not the token the agent templates' sign-off conditional
    keys on.
    """
    if not isinstance(prompt, str):
        return False
    pattern = (
        r"[\"'`]?\bticket_path\b[\"'`]?\s*[:=]\s*[\"'`]?" + re.escape(path)
    )
    return re.search(pattern, prompt) is not None


class _DispatchPointerCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo1900d_")
        self._tmpdirs.append(path)
        return path

    def assert_prompt_precondition(self, dispatch, ticket_path, driver):
        """Non-vacuity guard, run BEFORE the pointer assertion.

        If these fail the scenario is broken, not the driver: the harness must
        have captured a real prompt, and that prompt must already contain the
        path SOMEWHERE. Only then is a failure of the pointer assertion
        attributable to the missing pointer form rather than to a lost prompt
        or a mis-wired scenario.
        """
        prompt = dispatch.get("prompt")
        self.assertTrue(
            isinstance(prompt, str) and prompt.strip(),
            f"harness precondition: no prompt captured for the "
            f"'{dispatch.get('label')}' dispatch in {driver}. The assertion "
            "below would then fail for the wrong reason.",
        )
        self.assertIn(
            ticket_path,
            prompt,
            f"harness precondition: the '{dispatch.get('label')}' dispatch in "
            f"{driver} does not mention the ticket path at all. The scenario is "
            f"mis-wired. Prompt: {prompt!r}",
        )


class TestEveryPhaseDispatchNamesTheTicketPathPointer(_DispatchPointerCase):
    """BO-1900d-1: the phase agent is spawned with the ticket_path pointer."""

    def test_every_phase_dispatch_carries_the_ticket_path_pointer(self):
        # covers: BO-1900d-1
        """Each of four gates is dispatched; each dispatch must name the ticket
        as a ``ticket_path`` pointer, not only in narrative prose.

        A gate whose template says "Skip this entire section if no
        `ticket_path` was provided" and which was handed no such pointer has
        been told, by its own instructions, that recording its sign-off is
        optional.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree,
                    "01_pointer_case.md",
                    FOUR_PHASES,
                    title="Pointer case ticket",
                )
                observation = H.run_driver(
                    script,
                    H.single_ticket_scenario(
                        worktree,
                        ticket_path,
                        {
                            "title": "Pointer case ticket",
                            "phases": FOUR_PHASES,
                            "has_test_requirements": True,
                            "results": results,
                        },
                    ),
                )

                dispatches = H.phase_dispatches(observation)
                self.assertEqual(
                    len(dispatches),
                    len(FOUR_PHASES),
                    f"harness precondition: {driver} dispatched "
                    f"{len(dispatches)} phase agent(s), expected "
                    f"{len(FOUR_PHASES)}. Labels: "
                    f"{[d.get('label') for d in dispatches]}",
                )

                for dispatch in dispatches:
                    self.assert_prompt_precondition(dispatch, ticket_path, driver)
                    self.assertTrue(
                        ticket_path_pointer(dispatch["prompt"], ticket_path),
                        f"{driver} dispatched the '{dispatch['label']}' phase "
                        "agent without a `ticket_path` pointer. The path appears "
                        "in the prompt only as narrative, so the agent's own "
                        "sign-off conditional ('Skip this entire section if no "
                        "`ticket_path` was provided', _signoff_block.md:35) may "
                        "read as unsatisfied and the gate records nothing.\n"
                        f"  prompt sent: {dispatch['prompt']!r}\n"
                        f"  opts keys sent: {dispatch.get('opts_keys')}\n"
                        f"  opts.ticket_path: {dispatch.get('opts_ticket_path')!r} "
                        "(note: the opts channel cannot carry it — "
                        "agent(prompt, opts) accepts only agentType / schema / "
                        "label / phase / model / effort / isolation, so the "
                        "pointer belongs in the prompt)",
                    )

    def test_each_epic_member_dispatch_points_at_its_own_ticket(self):
        # covers: BO-1900d-1
        """Two tickets in one epic drive: every dispatch must carry a
        ``ticket_path`` pointer naming ITS OWN ticket.

        A pointer that is present but hardcoded to one member is worse than an
        absent one — it sends a gate to sign off the wrong record. This is also
        the uniformity dimension: a pointer added at one call site and missed at
        another reproduces exactly the per-ticket unreliability of BUG-23.
        """
        worktree = self._worktree()
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Pointer")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        gates = ["test-runner", "commit"]
        paths = {
            name: H.write_ticket_record(
                worktree, name, gates, title=name, subdir=epic_subdir
            )
            for name in ("01_a.md", "02_b.md")
        }
        tickets = {
            path: {
                "title": os.path.basename(path),
                "phases": gates,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in gates}),
            }
            for path in paths.values()
        }
        present = [{"path": p, "status": "todo"} for p in paths.values()]
        observation = H.run_driver(
            H.BUILD_FEATURE_JS,
            H.epic_scenario(
                worktree,
                epic_path,
                tickets,
                [{"present": present}, {"present": present}],
            ),
        )

        dispatches = H.phase_dispatches(observation)
        self.assertEqual(
            len(dispatches),
            len(gates) * len(paths),
            "harness precondition: the epic drive must dispatch every gate of "
            f"every member. Got: {[d.get('label') for d in dispatches]}",
        )

        for dispatch in dispatches:
            own_path = dispatch.get("ticket_path")
            self.assertIn(
                own_path,
                list(paths.values()),
                "harness precondition: the dispatch could not be attributed to "
                f"a known member. Prompt: {dispatch.get('prompt')!r}",
            )
            self.assert_prompt_precondition(dispatch, own_path, "build-feature.js")
            self.assertTrue(
                ticket_path_pointer(dispatch["prompt"], own_path),
                f"the '{dispatch['label']}' dispatch for {own_path} carries no "
                "`ticket_path` pointer naming that member. Every dispatch on "
                "every work item must carry it, or the guarantee is a property "
                "of a lucky ticket rather than of the drive.\n"
                f"  prompt sent: {dispatch['prompt']!r}",
            )
            for other in paths.values():
                if other == own_path:
                    continue
                self.assertFalse(
                    ticket_path_pointer(dispatch["prompt"], other),
                    f"the '{dispatch['label']}' dispatch for {own_path} names "
                    f"{other} as its ticket_path pointer. A pointer aimed at "
                    "the wrong record is worse than no pointer: the gate signs "
                    f"off another ticket.\n  prompt sent: {dispatch['prompt']!r}",
                )


if __name__ == "__main__":
    unittest.main()
