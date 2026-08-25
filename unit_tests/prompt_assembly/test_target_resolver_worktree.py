"""Behavioral tests for the resolved target's working copy (BUG-01).

Covers:
  BO-1900a-4   — resolving an epic target says the isolated working copy is NOT
                 YET DETERMINED, never a stand-in location.
  BO-1900a-4-i — no phase agent is spawned while the isolated working copy is
                 still undetermined.

Every test EXECUTES a real driver through harness_build_ticket_guard.mjs with no
working copy supplied, and asserts on the resolved target the run emitted and on
the phase agents it actually dispatched. Per CLAUDE.md "Gate / Workflow ACs —
Verify Behaviorally, Not by Grep": the emitted value was path-shaped and
plausible, so nothing short of inspecting what a run produced can distinguish
the defect from correct behaviour — and a source-reading test cannot separate a
consumed guard from an ignored one.

Observed at the second journal entry of run wf_09a91c7e-d5f: the resolver
returned an epic target whose isolated-working-copy value was a verbatim copy of
the epic's work-store folder. A work-store folder is not a working copy. Nothing
broke only because the very next step overwrote the value — that is luck, not
design.

THE RESOLVED-TARGET CONTRACT THIS SUITE PINS. The drivers have no filesystem
access, so the only channel on which a consumer can read the resolved target is
the value the run emits. These tests accept either shape:

    {"resolved_target": {"worktree_path": <marker-or-location>, ...}, ...}
    {"worktree_path": <marker-or-location>, "target_type": ..., ...}

`null` (or an absent working-copy key) is the unambiguous not-yet-determined
marker: absent is not a location, and nothing path-shaped may stand in for it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

GATES = ["test-runner", "commit"]

_UNDETERMINED_TOKENS = (
    "undetermined",
    "not determined",
    "not yet determined",
    "not established",
    "unresolved",
    "pending",
    "tbd",
)
_HOLDBACK_TOKENS = _UNDETERMINED_TOKENS + (
    "no worktree",
    "without a worktree",
    "no isolated working copy",
    "no working copy",
)

_WORKING_COPY_KEYS = (
    "worktree_path",
    "working_copy",
    "worktree",
    "isolated_worktree",
    "isolated_working_copy",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def resolved_target(result):
    """The resolved target the run emitted, or None if it emitted none."""
    if not isinstance(result, dict):
        return None
    nested = result.get("resolved_target")
    if isinstance(nested, dict):
        return nested
    if any(k in result for k in ("worktree_path", "target_type", "epic_path")):
        return result
    return None


def working_copy(target):
    """The working-copy value on a resolved target. Absent reads as None."""
    for key in _WORKING_COPY_KEYS:
        if key in target:
            return target[key]
    return None


def classify_working_copy(target) -> str:
    """A CONSUMER's view: classify the resolved target using ONLY the target.

    This function is deliberately given no knowledge of the epic's work-store
    folder — that is the property BO-1900a-4 requires, and the property that
    would have let a downstream step catch the defect.
    """
    value = working_copy(target)
    if value is None:
        return "undetermined"
    if isinstance(value, bool):
        return "location"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "undetermined"
        if "/" in stripped or stripped.startswith(("~", ".")):
            return "location"
        if any(token in stripped.lower() for token in _UNDETERMINED_TOKENS):
            return "undetermined"
    return "location"


def _mentions_any(result, tokens) -> bool:
    text = _serialized(result).lower()
    return any(token in text for token in tokens)


class _ResolverCase(unittest.TestCase):
    """Scenarios where NO isolated working copy has been established."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _store(self) -> str:
        """A WORK STORE — the shared clone. Emphatically not a working copy."""
        path = tempfile.mkdtemp(prefix="bo1900_store_")
        self._tmpdirs.append(path)
        return path

    def undetermined_scenarios(self):
        """Yield (driver, script, scenario, store_paths) with no working copy.

        build-feature.js: the resolver answers exactly as today's prompt
        instructs — reporting the epic's work-store folder as worktree_path —
        and the step that would establish the isolated copy has not run.

        build-ticket.js: no worktree_path in args and the ambient git check
        cannot answer, so the working copy is equally undetermined.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            store = self._store()
            epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Resolver")
            epic_path = os.path.join(store, epic_subdir)
            os.makedirs(epic_path, exist_ok=True)
            ticket_path = H.write_ticket_record(
                store, "01_item.md", GATES, title="Resolver item", subdir=epic_subdir
            )
            ticket_cfg = {
                "title": "Resolver item",
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            }

            scenario = {
                "record_dir": store,
                # NOTE: no worktree_path in args — the caller has not resolved one.
                "args": {"target": epic_path, "ticket_path": ticket_path},
                "resolve": {
                    "target_type": "epic",
                    "epic_path": epic_path,
                    "ticket_path": ticket_path,
                    # The observed defect, verbatim: the work-store folder
                    # standing in for the isolated working copy.
                    "worktree_path": epic_path,
                },
                # No isolated working copy has been established for this drive.
                "worktree_agent": None,
                "worktree_check": None,
                "epic": {
                    "path": epic_path,
                    "title": "EPIC-Resolver",
                    "reads": [
                        {"present": [{"path": ticket_path, "status": "todo"}]},
                        {"present": [{"path": ticket_path, "status": "todo"}]},
                    ],
                },
                "tickets": {ticket_path: ticket_cfg},
            }
            yield driver, script, scenario, {
                "store": store,
                "epic_path": epic_path,
                "ticket_path": ticket_path,
            }

    def established_scenarios(self):
        """Yield the same drives with an isolated working copy established."""
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = tempfile.mkdtemp(prefix="bo1900_worktree_")
            self._tmpdirs.append(worktree)
            ticket_path = H.write_ticket_record(
                worktree, "01_item.md", GATES, title="Resolver item"
            )
            scenario = H.single_ticket_scenario(
                worktree,
                ticket_path,
                {
                    "title": "Resolver item",
                    "phases": GATES,
                    "has_test_requirements": True,
                    "results": H.phase_results({g: True for g in GATES}),
                },
            )
            yield driver, script, scenario, worktree


# ---------------------------------------------------------------------------
# BO-1900a-4 — the resolver must say "not yet determined"
# ---------------------------------------------------------------------------


class TestResolvedTargetReportsUndeterminedWorkingCopy(_ResolverCase):
    """BO-1900a-4: there is no correct working-copy value to emit at resolution
    time, because none has been created yet. The only honest output is that the
    question is not yet answered, said in a way a consumer cannot mistake for an
    answer."""

    def test_epic_target_resolves_with_the_working_copy_not_yet_determined(self):
        # covers: BO-1900a-4
        """Run the resolution with no working copy supplied and assert the
        resolved target reports the working copy as not yet determined."""
        for driver, script, scenario, paths in self.undetermined_scenarios():
            with self.subTest(driver=driver):
                result = H.run_driver(script, scenario)["result"]
                target = resolved_target(result)

                self.assertIsNotNone(
                    target,
                    f"{driver} emitted no resolved target at all, so no consumer "
                    "can learn whether the isolated working copy is determined. "
                    "Emit it as {'resolved_target': {'worktree_path': null, ...}} "
                    "or as top-level target fields on the payload. Output: "
                    f"{_serialized(result)}",
                )
                self.assertEqual(
                    classify_working_copy(target),
                    "undetermined",
                    f"{driver} resolved the target before any isolated working "
                    "copy was created or chosen, so the resolved target must "
                    "state that the working copy is not yet determined. It "
                    f"carries {working_copy(target)!r} instead. Resolved target: "
                    f"{json.dumps(target, sort_keys=True)}",
                )

    def test_the_resolved_target_never_carries_the_work_store_folder_as_the_working_copy(
        self,
    ):
        # covers: BO-1900a-4
        """The exact observed defect: the working copy equal to the epic's
        work-store folder.

        Also negative against every other pre-existing location the drive could
        reach for — the process's current directory and the store root.
        """
        for driver, script, scenario, paths in self.undetermined_scenarios():
            with self.subTest(driver=driver):
                result = H.run_driver(script, scenario)["result"]
                target = resolved_target(result)
                self.assertIsNotNone(
                    target,
                    f"{driver} emitted no resolved target. Output: "
                    f"{_serialized(result)}",
                )
                value = working_copy(target)

                forbidden = {
                    "the epic's work-store folder": paths["epic_path"],
                    "the work store root": paths["store"],
                    "the process's current directory": os.getcwd(),
                }
                for label, location in forbidden.items():
                    self.assertNotEqual(
                        value,
                        location,
                        f"{driver} carried {label} as the isolated working copy "
                        f"({value!r}). A work-store folder is not a working copy; "
                        "emitting a plausible substitute is the specific "
                        "behaviour this AC forbids, because it sends phase agents "
                        "to work — and commit — in the shared clone.",
                    )

    def test_not_yet_determined_is_recognisable_without_comparison(self):
        # covers: BO-1900a-4
        """A consumer must classify the resolved target as undetermined FROM THE
        TARGET ALONE, without being told the epic's work-store folder.

        classify_working_copy() in this module is that consumer: it is given the
        resolved target and nothing else. Whatever represents not-yet-determined
        must also not be a path-shaped value that any consumer could join, open,
        or run a command in.
        """
        for driver, script, scenario, paths in self.undetermined_scenarios():
            with self.subTest(driver=driver):
                result = H.run_driver(script, scenario)["result"]
                target = resolved_target(result)
                self.assertIsNotNone(
                    target,
                    f"{driver} emitted no resolved target. Output: "
                    f"{_serialized(result)}",
                )
                value = working_copy(target)

                self.assertEqual(
                    classify_working_copy(target),
                    "undetermined",
                    f"{driver}: a consumer that does not know the epic's "
                    "work-store folder cannot tell this resolved target apart "
                    f"from a real location. It reads {value!r}.",
                )
                if isinstance(value, str):
                    self.assertNotIn(
                        "/",
                        value,
                        f"{driver}: the not-yet-determined marker is path-shaped "
                        f"({value!r}). Absent is not a location — a consumer must "
                        "not be able to join, open, or run a command in it.",
                    )

    def test_the_working_copy_appears_once_a_later_step_establishes_it(self):
        # covers: BO-1900a-4
        """CONTROL CASE: after the step that establishes the isolated copy, the
        resolved target carries that location and no longer reads as
        undetermined.

        Without this, a fix that always reports undetermined would pass every
        negative case and break every drive.
        """
        for driver, script, scenario, worktree in self.established_scenarios():
            with self.subTest(driver=driver):
                result = H.run_driver(script, scenario)["result"]
                self.assertIn(
                    worktree,
                    _serialized(result),
                    f"{driver}: once a working copy has been established for the "
                    "target, the resolved target must carry that location. "
                    f"Output: {_serialized(result)}",
                )
                target = resolved_target(result)
                if target is not None and working_copy(target) is not None:
                    self.assertEqual(
                        classify_working_copy(target),
                        "location",
                        f"{driver}: the resolved target must no longer read as "
                        f"undetermined once the copy exists. Target: "
                        f"{json.dumps(target, sort_keys=True)}",
                    )

    def test_both_drivers_resolve_the_same_way(self):
        # covers: BO-1900a-4
        """The twins' stated obligation, verified rather than asserted in a
        comment: run the same scenario against each driver as it exists on disk
        and assert both produce the same undetermined contract."""
        classifications = {}
        for driver, script, scenario, paths in self.undetermined_scenarios():
            result = H.run_driver(script, scenario)["result"]
            target = resolved_target(result)
            classifications[driver] = (
                classify_working_copy(target) if target is not None else "no-target"
            )

        self.assertEqual(
            sorted(set(classifications.values())),
            ["undetermined"],
            "both twin drivers must emit the same not-yet-determined contract "
            "when no isolated working copy has been established. Observed: "
            f"{classifications}. The twin obligation is currently enforced only "
            "by a comment in the file headers.",
        )


# ---------------------------------------------------------------------------
# BO-1900a-4-i — the refusal that makes the marker load-bearing
# ---------------------------------------------------------------------------


class TestNoDispatchWhileWorkingCopyUndetermined(_ResolverCase):
    """BO-1900a-4-i: an unanswered question about where the work belongs stops
    the drive instead of being answered by whatever is nearest."""

    def test_no_phase_agent_is_dispatched_while_the_working_copy_is_undetermined(self):
        # covers: BO-1900a-4-i
        """The harness records exactly which phase agents a run spawned; that
        list is the assertion."""
        for driver, script, scenario, paths in self.undetermined_scenarios():
            with self.subTest(driver=driver):
                observation = H.run_driver(script, scenario)
                self.assertEqual(
                    observation["dispatched"],
                    [],
                    f"{driver} spawned {len(observation['dispatched'])} phase "
                    f"agent(s) — {observation['dispatched']} — while the isolated "
                    "working copy was still undetermined. The work must be held "
                    "back instead.",
                )

    def test_the_holdback_reason_names_the_undetermined_working_copy(self):
        # covers: BO-1900a-4-i
        """An operator must not be left with a silent no-op, nor with a reason
        that fails to identify the undetermined working copy as the cause."""
        for driver, script, scenario, paths in self.undetermined_scenarios():
            with self.subTest(driver=driver):
                result = H.run_driver(script, scenario)["result"]

                self.assertNotEqual(
                    (result or {}).get("status"),
                    "ok",
                    f"{driver} reported success while the working copy was never "
                    f"determined. Output: {_serialized(result)}",
                )
                self.assertTrue(
                    _mentions_any(result, _HOLDBACK_TOKENS),
                    f"{driver} stopped without stating that the isolated working "
                    "copy is undetermined. The holdback reason must name it, so "
                    "the operator knows what to fix rather than reading a generic "
                    f"abort. Output: {_serialized(result)}",
                )

    def test_the_ambient_location_is_not_used_as_a_fallback(self):
        # covers: BO-1900a-4-i
        """Resolving an undetermined working copy to the process's current
        location is the single most likely wrong implementation, is invisible in
        a passing test suite, and is precisely how a phase agent ends up
        committing into the shared clone."""
        for driver, script, scenario, paths in self.undetermined_scenarios():
            with self.subTest(driver=driver):
                observation = H.run_driver(script, scenario)

                substitutes = {
                    "the epic's work-store folder": paths["epic_path"],
                    "the work store root": paths["store"],
                    "the process's current directory": os.getcwd(),
                }
                for dispatch in observation["dispatches"]:
                    for label, location in substitutes.items():
                        self.assertNotEqual(
                            dispatch.get("ticket_path"),
                            location,
                            f"{driver} dispatched the {dispatch['label']} phase "
                            f"against {label} ({location}) as a stand-in working "
                            "copy.",
                        )
                self.assertEqual(
                    observation["dispatched"],
                    [],
                    f"{driver} reached for a substitute location instead of "
                    f"holding the work back: {observation['dispatches']}",
                )

    def test_the_phase_dispatches_once_a_working_copy_is_established(self):
        # covers: BO-1900a-4-i
        """CONTROL CASE: supply an established working copy and the expected
        phase agents are dispatched — so the refusal above is attributable to
        the undetermined marker and not to a driver that stopped dispatching.

        This is the trap the pre-coder gate hit and had to be widened for.
        """
        for driver, script, scenario, worktree in self.established_scenarios():
            with self.subTest(driver=driver):
                observation = H.run_driver(script, scenario)
                self.assertEqual(
                    observation["dispatched"],
                    GATES,
                    f"{driver}: with a working copy established, the needed "
                    f"phases must dispatch normally. Dispatched: "
                    f"{observation['dispatched']}",
                )


if __name__ == "__main__":
    unittest.main()
