"""
MODULE: unit_tests/workflows/test_bo2600b_lane_scope_aiming.py
GOAL: RED behavioural tests for BO-2600b-1, BO-2600b-1-i, and BO-2600b-1-ii —
      the fast lane (templates/workflows-js/fast-lane-ship.js) must ALWAYS
      pass --exclude-structural-parent to the select_connected resolver
      command it composes at its Resolve phase (line ~307), with no per-run
      operator switch.

=== Why this is not a grep test (CLAUDE.md "Verify Behaviorally, Not by Grep") ===

A test asserting the literal substring "--exclude-structural-parent" appears
near "select_connected" in the JS source would pass on a commented-out flag,
a flag on the wrong subcommand, or dead code. Instead, every test here:

  1. Drives templates/workflows-js/fast-lane-ship.js under
     unit_tests/_workflow_engine_harness.py's run_workflow_under_e2(), which
     executes the script's real top-level control flow in a Node.js
     subprocess and records every agent() dispatch verbatim.
  2. Locates the recorded "resolve-connected" agent() call (the Resolve
     phase's status-checker dispatch) and extracts the *exact* Bash command
     line the workflow composed for the resolver to run — the very text an
     agent would have been told to execute.
  3. Executes that extracted command for real (as a subprocess) against a
     purpose-built fixture AC store — never the live repo store, so these
     tests do not drift as the real store changes — and asserts on the
     JSON id list select_connected actually prints.

This proves the flag reaches the process that resolves scope, not merely
that its string sits somewhere in the workflow file.

=== Fixture-authenticity ===

All AC YAML fixtures are written with yaml.safe_dump (never a hand-typed
YAML literal), mirroring the pattern already used in
unit_tests/build_orchestration/test_bo_2600a_2.py and
unit_tests/build_orchestration/test_fast_lane_connected.py. The one
hand-typed string in this file (the "AC id ... not found" fragment) is
never used as a fixture body — it is only asserted as a substring of a
message that is itself obtained by actually running the real fast_lane.py
CLI against the fixture (see test_empty_tight_set_is_not_reported...).

=== Fixture geometry (verified against the real resolve_connected_build_set
implementation via a throwaway harness run before this file was authored —
NOT hand-derived) ===

Fixture A (BO-2600b-1 — target leaf -> structural parent -> grandparent):

    FLT-900a      (L1) covered_by: [FLT-900a-1, FLT-900a-2, FLT-900a-3]
      FLT-900a-1    (L2, leaf) depends_on: [FLT-900a]          <- structural parent dep
                    covered_by: [FLT-900a-1-i]
        FLT-900a-1-i  (L3, leaf, TARGET)
                      depends_on: [FLT-900a-1, FLT-900b-1]     <- own structural parent + a genuine peer dep
      FLT-900a-2    (L2, leaf, no deps)     <- reachable ONLY by widening through FLT-900a
      FLT-900a-3    (L2, leaf, no deps)     <- reachable ONLY by widening through FLT-900a
    FLT-900b-1    (L2, leaf, no deps)       <- genuine prerequisite, NOT a structural parent of the target

    wide  (exclude_structural_parent=False) = ['FLT-900a-1', 'FLT-900b-1', 'FLT-900a-1-i', 'FLT-900a-2', 'FLT-900a-3']
    tight (exclude_structural_parent=True)  = ['FLT-900b-1', 'FLT-900a-1-i']

Fixture B (BO-2600b-1-i — aiming AT a parent that is itself a leaf with children):

    FLT-910       (L0) covered_by: [FLT-910a]
      FLT-910a      (L2, leaf, TARGET/"parent") depends_on: [FLT-910]
                    covered_by: [FLT-910a-1, FLT-910a-2, FLT-910a-3]
        FLT-910a-1    (L3, leaf, no children)
        FLT-910a-2    (L3, leaf, no children)
        FLT-910a-3    (L3, leaf) covered_by: [FLT-910a-3-i]
          FLT-910a-3-i  (L3, leaf, GRANDCHILD)

    wide  = tight = ['FLT-910a', 'FLT-910a-1', 'FLT-910a-2', 'FLT-910a-3', 'FLT-910a-3-i']
    (identical in both modes — the exclusion only prunes the depends_on walk,
    never the subtree union, so aiming at the parent is unaffected by the flag.)

Fixture C (BO-2600b-1-ii — empty tight set):

    FLT-920       (L0) covered_by: [FLT-920a]
      FLT-920a      (L2, leaf, TARGET) work_status: done, depends_on: [FLT-920]

    wide = tight = []  (the target is already done and has no children, so no
    route into the store's unfinished work exists from this entry point.)

=== Red baseline ===

RED today because fast-lane-ship.js's Resolve phase (line ~307) composes:

    python3 ${gateScript} select_connected --ac ${targetAc} --ac-root ${acStoreRoot}

with no --exclude-structural-parent flag at all. Every test that asserts
`has_flag` (or relies on the tight set actually being tight) fails against
today's code — the extracted command lacks the flag, so the real subprocess
run returns the WIDE set, not the tight one.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_REAL_FAST_LANE_PY = _REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"


# ---------------------------------------------------------------------------
# Fixture helpers (yaml.safe_dump only — fixture-authenticity mandate)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal, valid AC YAML using yaml.safe_dump (never hand-typed)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_fixture_a(worktree_root: Path) -> Path:
    """Fixture A — see module docstring. Returns the AC store root."""
    ac_root = worktree_root / "docs" / "acceptance-criteria"
    ac_root.mkdir(parents=True, exist_ok=True)
    _write_ac(ac_root, "FLT-900a", level="L1", work_status="todo",
              covered_by=["FLT-900a-1", "FLT-900a-2", "FLT-900a-3"])
    _write_ac(ac_root, "FLT-900a-1", level="L2", work_status="todo",
              depends_on=["FLT-900a"], covered_by=["FLT-900a-1-i"])
    _write_ac(ac_root, "FLT-900a-1-i", level="L3", work_status="todo",
              depends_on=["FLT-900a-1", "FLT-900b-1"])
    _write_ac(ac_root, "FLT-900a-2", level="L2", work_status="todo")
    _write_ac(ac_root, "FLT-900a-3", level="L2", work_status="todo")
    _write_ac(ac_root, "FLT-900b-1", level="L2", work_status="todo")
    return ac_root


def _build_fixture_b(worktree_root: Path) -> Path:
    """Fixture B — parent-aim shape (BO-2600b-1-i). Returns the AC store root."""
    ac_root = worktree_root / "docs" / "acceptance-criteria"
    ac_root.mkdir(parents=True, exist_ok=True)
    _write_ac(ac_root, "FLT-910", level="L0", work_status="todo",
              covered_by=["FLT-910a"])
    _write_ac(ac_root, "FLT-910a", level="L2", work_status="todo",
              depends_on=["FLT-910"],
              covered_by=["FLT-910a-1", "FLT-910a-2", "FLT-910a-3"])
    _write_ac(ac_root, "FLT-910a-1", level="L3", work_status="todo")
    _write_ac(ac_root, "FLT-910a-2", level="L3", work_status="todo")
    _write_ac(ac_root, "FLT-910a-3", level="L3", work_status="todo",
              covered_by=["FLT-910a-3-i"])
    _write_ac(ac_root, "FLT-910a-3-i", level="L3", work_status="todo")
    return ac_root


def _build_fixture_c(worktree_root: Path) -> Path:
    """Fixture C — empty tight set shape (BO-2600b-1-ii). Returns the AC store root."""
    ac_root = worktree_root / "docs" / "acceptance-criteria"
    ac_root.mkdir(parents=True, exist_ok=True)
    _write_ac(ac_root, "FLT-920", level="L0", work_status="todo",
              covered_by=["FLT-920a"])
    _write_ac(ac_root, "FLT-920a", level="L2", work_status="done",
              depends_on=["FLT-920"])
    return ac_root


# ---------------------------------------------------------------------------
# Harness-driving helpers
# ---------------------------------------------------------------------------


def _worktree_label_response(worktree_root: Path) -> dict[str, Any]:
    return {
        "worktree_path": str(worktree_root),
        "branch": "fast-lane/test-bo2600b",
        "ac_store_path": str(worktree_root / "docs" / "acceptance-criteria"),
        "created": True,
    }


def _run_lane(
    worktree_root: Path,
    ac_id: str,
    extra_label_responses: dict[str, Any] | None = None,
    extra_args: dict[str, Any] | None = None,
) -> HarnessResult:
    label_responses = {"fastlane-worktree": _worktree_label_response(worktree_root)}
    if extra_label_responses:
        label_responses.update(extra_label_responses)
    args = {"ac": ac_id}
    if extra_args:
        args.update(extra_args)
    return run_workflow_under_e2(_WORKFLOW_PATH, label_responses=label_responses, args=args)


def _find_resolve_connected_call(result: HarnessResult):
    calls = [c for c in result.agent_calls if c.label == "resolve-connected"]
    assert calls, (
        "fast-lane-ship.js did not dispatch a 'resolve-connected' agent() call. "
        f"Captured calls: {[(c.label, c.agent_type) for c in result.agent_calls]}. "
        f"Harness stderr: {result.stderr!r}"
    )
    return calls[0]


def _extract_resolver_invocation(result: HarnessResult) -> tuple[str, str, bool]:
    """Extract (ac, ac_root, has_exclude_flag) from the recorded resolver dispatch.

    Locates the 'resolve-connected' agent() call this run recorded and parses
    the literal Bash command line it told the resolver agent to run — the
    exact ``python3 ... select_connected --ac ... --ac-root ...`` line
    composed by fast-lane-ship.js's Resolve phase.
    """
    call = _find_resolve_connected_call(result)
    prompt_text = call.prompt
    assert isinstance(prompt_text, str) and prompt_text.strip(), (
        f"resolve-connected agent() call's prompt is not a usable instruction string: {prompt_text!r}"
    )
    lines = [ln for ln in prompt_text.splitlines() if "select_connected" in ln]
    assert lines, (
        "No line containing 'select_connected' was found in the resolver prompt "
        f"fast-lane-ship.js composed:\n{prompt_text}"
    )
    line = lines[0]
    ac_match = re.search(r"--ac\s+(\S+)", line)
    ac_root_match = re.search(r"--ac-root\s+(\S+)", line)
    assert ac_match and ac_root_match, (
        f"Could not parse --ac / --ac-root out of the composed resolver command line: {line!r}"
    )
    has_flag = "--exclude-structural-parent" in line
    return ac_match.group(1), ac_root_match.group(1), has_flag


def _run_real_select_connected(ac: str, ac_root: str, exclude_flag: bool) -> list[str]:
    """Actually execute the real fast_lane.py select_connected CLI (a real subprocess).

    This is the "real-effect round-trip": the composed command's --ac /
    --ac-root values (and now-optional flag) are re-run against the real,
    already-shipped resolver implementation (BO-2600a-1/BO-2600a-2, both
    done) — never mocked — so the assertion lands on the actual resolved id
    list, not on the text of the workflow file.
    """
    cmd = [sys.executable, str(_REAL_FAST_LANE_PY), "select_connected", "--ac", ac, "--ac-root", ac_root]
    if exclude_flag:
        cmd.append("--exclude-structural-parent")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, (
        f"select_connected exited {proc.returncode} for cmd={cmd}. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    return json.loads(proc.stdout)


def _real_missing_id_message(ac_root: str, missing_id: str) -> str:
    """Obtain the REAL 'AC id not found' message by actually running the CLI.

    Never hand-typed: this is the authentic stderr text resolve_connected_build_set
    raises, captured by really invoking the shipped script against *ac_root*.
    """
    cmd = [sys.executable, str(_REAL_FAST_LANE_PY), "select_connected", "--ac", missing_id, "--ac-root", ac_root]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert proc.returncode != 0, "expected a non-zero exit for a missing AC id"
    return proc.stderr.strip()


# ---------------------------------------------------------------------------
# BO-2600b-1 — the lane always excludes the structural parent
# ---------------------------------------------------------------------------


class TestFastLaneAlwaysExcludesStructuralParent(unittest.TestCase):
    """BO-2600b-1: fast-lane-ship.js's Resolve phase must always compose
    select_connected with --exclude-structural-parent — no per-run switch.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_root = _build_fixture_a(self.worktree_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolved_set_excludes_structural_parent_siblings(self) -> None:
        # covers: BO-2600b-1
        """The set the lane's own resolver command resolves excludes the two
        siblings (FLT-900a-2, FLT-900a-3) and the structural parent itself
        (FLT-900a-1), all reachable ONLY by walking up structural-parent
        links — never by descending from the target.

        RED today: fast-lane-ship.js does not compose --exclude-structural-parent,
        so the real subprocess run returns the WIDE set and these ids ARE present.
        """
        result = _run_lane(self.worktree_root, "FLT-900a-1-i")
        ac, ac_root, has_flag = _extract_resolver_invocation(result)

        self.assertTrue(
            has_flag,
            "fast-lane-ship.js's Resolve phase must compose select_connected "
            "with --exclude-structural-parent on every run (BO-2600b-1). The "
            "extracted resolver command line lacked the flag."
        )

        resolved = _run_real_select_connected(ac, ac_root, has_flag)

        for sibling in ("FLT-900a-2", "FLT-900a-3", "FLT-900a-1"):
            self.assertNotIn(
                sibling,
                resolved,
                f"{sibling} is reachable only by expanding the target's structural "
                f"parent chain (FLT-900a-1-i -> FLT-900a-1 -> FLT-900a) and must be "
                f"ABSENT from the lane's resolved set (BO-2600b-1). Got: {resolved}"
            )

        self.assertIn("FLT-900a-1-i", resolved, "The target itself must be in the resolved set.")

    def test_resolved_set_keeps_genuine_prerequisites(self) -> None:
        # covers: BO-2600b-1
        """A prerequisite that is NOT the target's structural parent
        (FLT-900b-1) is still present in the resolved set — the exclusion
        only skips a depends_on entry that equals the node's own structural
        parent, never a genuine peer dependency.
        """
        result = _run_lane(self.worktree_root, "FLT-900a-1-i")
        ac, ac_root, has_flag = _extract_resolver_invocation(result)

        resolved = _run_real_select_connected(ac, ac_root, has_flag)

        self.assertIn(
            "FLT-900b-1",
            resolved,
            "FLT-900b-1 is a genuine peer dependency of the target (not its "
            "structural parent) and must remain in the resolved set even with "
            f"the exclusion in force (BO-2600b-1). Got: {resolved}"
        )
        # Full-set equality pins the tight scope down completely, not just partially.
        self.assertCountEqual(
            resolved,
            ["FLT-900b-1", "FLT-900a-1-i"],
            f"Expected the exact tight set {{'FLT-900b-1', 'FLT-900a-1-i'}}. Got: {resolved}"
        )

    def test_needs_no_second_argument_for_the_tight_set(self) -> None:
        # covers: BO-2600b-1
        """The lane is invoked with only {ac: <id>} and still produces the
        tight set — and supplying an arbitrary extra workflow input changes
        nothing, because no per-run scope switch exists at this entry point.
        """
        result_plain = _run_lane(self.worktree_root, "FLT-900a-1-i")
        ac1, ac_root1, has_flag1 = _extract_resolver_invocation(result_plain)

        # An operator cannot opt back into the wide set via some undocumented
        # extra field either — there is no second argument to find.
        result_with_bogus_arg = _run_lane(
            self.worktree_root, "FLT-900a-1-i", extra_args={"scope": "wide"}
        )
        ac2, ac_root2, has_flag2 = _extract_resolver_invocation(result_with_bogus_arg)

        self.assertTrue(
            has_flag1,
            "Given only {ac: <id>}, the composed resolver command must still "
            "carry --exclude-structural-parent (BO-2600b-1)."
        )
        self.assertEqual(
            has_flag1,
            has_flag2,
            "Supplying an extra, unsanctioned workflow input must not change "
            "whether --exclude-structural-parent is composed — there is no "
            "per-run scope switch reachable from this entry point (BO-2600b-1)."
        )

        resolved = _run_real_select_connected(ac1, ac_root1, has_flag1)
        self.assertCountEqual(
            resolved,
            ["FLT-900b-1", "FLT-900a-1-i"],
            f"The single-argument invocation must resolve exactly the tight set. Got: {resolved}"
        )


# ---------------------------------------------------------------------------
# BO-2600b-1-i — aiming at a parent still resolves the whole branch beneath it
# ---------------------------------------------------------------------------


class TestAimingAtAParentResolvesWholeSubtree(unittest.TestCase):
    """BO-2600b-1-i: the always-exclude decision must not narrow a
    deliberately broad aim — excluding structural-parent prerequisites
    applies only to the depends_on walk, never to the subtree gathered
    beneath the criterion the operator aimed at.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_root = _build_fixture_b(self.worktree_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_aiming_at_a_parent_resolves_the_whole_subtree(self) -> None:
        # covers: BO-2600b-1-i
        """Aiming at FLT-910a (a leaf that is itself a parent) resolves the
        parent plus all three not-done descendants, grandchild included.
        """
        result = _run_lane(self.worktree_root, "FLT-910a")
        ac, ac_root, has_flag = _extract_resolver_invocation(result)

        self.assertTrue(
            has_flag,
            "BO-2600b-1-i presumes the lane already passes "
            "--exclude-structural-parent (BO-2600b-1) — this criterion pins "
            "down that doing so does not narrow a parent-aimed run. The "
            "composed resolver command lacked the flag, so this safety "
            "property cannot yet be verified against the lane's real behaviour."
        )

        resolved = _run_real_select_connected(ac, ac_root, has_flag)

        self.assertCountEqual(
            resolved,
            ["FLT-910a", "FLT-910a-1", "FLT-910a-2", "FLT-910a-3", "FLT-910a-3-i"],
            f"Aiming at the parent must resolve the parent plus every not-done "
            f"descendant, including the grandchild FLT-910a-3-i. Got: {resolved}"
        )

    def test_exclusion_removes_nothing_from_a_parent_aimed_run(self) -> None:
        # covers: BO-2600b-1-i
        """For a parent-aimed run, the set resolved WITH the exclusion in
        force equals the set the same command resolves WITHOUT it — the
        load-bearing safety property of BO-2600b-1's always-exclude decision.
        """
        result = _run_lane(self.worktree_root, "FLT-910a")
        ac, ac_root, has_flag = _extract_resolver_invocation(result)

        self.assertTrue(
            has_flag,
            "BO-2600b-1-i presumes the lane already passes "
            "--exclude-structural-parent (BO-2600b-1) before its own "
            "with/without comparison is meaningful against the real lane."
        )

        resolved_excluded = _run_real_select_connected(ac, ac_root, True)
        resolved_included = _run_real_select_connected(ac, ac_root, False)

        self.assertCountEqual(
            resolved_excluded,
            resolved_included,
            "Excluding structural-parent prerequisites must remove NOTHING "
            "from a parent-aimed run's resolved set. "
            f"excluded={resolved_excluded} included={resolved_included}"
        )


# ---------------------------------------------------------------------------
# BO-2600b-1-ii — an empty tight set is a clean stop that says why
# ---------------------------------------------------------------------------


class TestEmptyTightSetIsACleanStopThatSaysWhy(unittest.TestCase):
    """BO-2600b-1-ii: when the tight walk resolves to nothing, the run stops
    cleanly, reports it as a completed run (never a resolution failure), and
    states BOTH that the set is empty and that structural-parent
    prerequisites were excluded — so an operator can tell an empty set apart
    from a set the exclusion emptied.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_root = _build_fixture_c(self.worktree_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_empty_tight_set_stops_without_building(self) -> None:
        # covers: BO-2600b-1-ii
        """A fixture whose tight set is empty (FLT-920a: already done, its
        only route to unfinished work ran through its structural parent)
        produces a nothing-to-build terminal payload and dispatches no
        test-writer or coder invocation.
        """
        real_tight = _run_real_select_connected(
            "FLT-920a", str(self.ac_root), exclude_flag=True
        )
        self.assertEqual(real_tight, [], "Fixture invariant: the tight set must be empty.")

        result = _run_lane(
            self.worktree_root,
            "FLT-920a",
            extra_label_responses={
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            },
        )

        self.assertIsInstance(
            result.result, dict,
            f"Expected a terminal payload dict from the run. Got: {result.result!r}"
        )
        self.assertEqual(
            result.result.get("status"), "ok",
            f"An empty tight set must be a completed run (status: ok), not a failure. "
            f"Got: {result.result}"
        )
        self.assertTrue(
            result.result.get("nothing_to_build"),
            f"The terminal payload must flag nothing_to_build. Got: {result.result}"
        )

        dispatched_types = {c.agent_type for c in result.agent_calls if c.agent_type}
        for forbidden in ("test-writer", "python-coder", "frontend-coder", "sql-coder"):
            self.assertNotIn(
                forbidden,
                dispatched_types,
                f"An empty tight set must dispatch no build work, but a "
                f"{forbidden!r} agent call was recorded. All calls: "
                f"{[(c.label, c.agent_type) for c in result.agent_calls]}"
            )

    def test_empty_set_payload_states_the_exclusion_was_in_force(self) -> None:
        # covers: BO-2600b-1-ii
        """The nothing-to-build payload states BOTH that the set is empty
        AND that structural-parent prerequisites were excluded from the
        prerequisite walk — so an operator can tell an empty set apart from
        a set the exclusion emptied.

        RED today: the current nothing_to_build message only says
        "Nothing to build: the connected set for <id> is empty ..." with no
        mention of the exclusion at all.
        """
        result = _run_lane(
            self.worktree_root,
            "FLT-920a",
            extra_label_responses={
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            },
        )

        self.assertIsInstance(result.result, dict)
        self.assertTrue(
            result.result.get("nothing_to_build"),
            f"Fixture setup sanity: expected a nothing_to_build run. Got: {result.result}"
        )

        payload = result.result
        message = str(payload.get("message", "")).lower()
        mentions_exclusion_in_message = "exclu" in message and (
            "structural" in message or "structural-parent" in message
        )
        has_explicit_flag_field = any(
            bool(payload.get(key))
            for key in ("structural_parent_excluded", "exclude_structural_parent")
        )

        self.assertTrue(
            mentions_exclusion_in_message or has_explicit_flag_field,
            "The nothing-to-build payload must state that structural-parent "
            "prerequisites were excluded from the prerequisite walk — either "
            "in the human-readable message or via an explicit boolean field "
            "(BO-2600b-1-ii). An operator seeing a bare 'nothing to build' "
            "cannot tell whether the exclusion ate their work. "
            f"Got payload: {payload}"
        )

    def test_empty_tight_set_is_not_reported_as_a_resolution_failure(self) -> None:
        # covers: BO-2600b-1-ii
        """The empty-set run returns the completed nothing-to-build outcome,
        while a run against a truly missing id still returns the
        resolution-failure outcome — the empty-tight-set path must never be
        widened until it also swallows a genuinely missing id.
        """
        empty_result = _run_lane(
            self.worktree_root,
            "FLT-920a",
            extra_label_responses={
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            },
        )
        self.assertEqual(
            empty_result.result.get("status"),
            "ok",
            f"The empty-tight-set run must be status 'ok'. Got: {empty_result.result}"
        )

        missing_id = "FLT-999-does-not-exist"
        real_missing_message = _real_missing_id_message(str(self.ac_root), missing_id)
        self.assertIn(
            "not found", real_missing_message.lower(),
            "Fixture setup sanity: the real CLI's own error text must mention "
            f"'not found'. Got: {real_missing_message!r}"
        )

        missing_result = _run_lane(
            self.worktree_root,
            missing_id,
            extra_label_responses={
                "resolve-connected": {"ac_ids": [], "message": real_missing_message},
            },
        )
        self.assertEqual(
            missing_result.result.get("status"),
            "error",
            "A resolution failure (missing AC id) must NOT be reported as a "
            "clean nothing-to-build outcome — that distinction must survive "
            f"the exclusion change (BO-2600b-1-ii). Got: {missing_result.result}"
        )
        self.assertNotEqual(
            missing_result.result.get("classification"),
            None,
        )
        self.assertFalse(
            missing_result.result.get("nothing_to_build"),
            f"A resolution failure must not carry nothing_to_build=true. "
            f"Got: {missing_result.result}"
        )


if __name__ == "__main__":
    unittest.main()
