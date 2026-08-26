"""
MODULE: unit_tests/workflows/test_bo2400f_10i_release_wiring.py
GOAL: RED behavioral tests for BO-2400f-10-i — every one of the nine release
      dispatch sites in templates/workflows-js/fast-lane-ship.js asks a
      status-checker persona to run a Bash command that mutates AC
      work_status. status-checker's own registry entry
      (config/agent_registry.json) declares ``permits_shell: false`` — a
      structural charter mismatch that is exactly why KI-BO-020 found that no
      fast-lane run has ever actually released anything: status-checker
      declines the reassignment, and the discarded (BO-2400f-10-ii) reply
      leaves the run looking like a clean halt.

These tests drive templates/workflows-js/fast-lane-ship.js's REAL top-level
control flow via unit_tests/_workflow_engine_harness.py's
run_workflow_under_e2() — nothing here is a grep over the source text. The
harness executes the script as a real Node.js subprocess and records every
agent() dispatch verbatim, including its `label` and `agentType`.

=== Red baseline ===

RED today because:
  - every recorded release-* dispatch carries agentType "status-checker",
    whose config/agent_registry.json entry declares permits_shell: false —
    the charter test fails on that mismatch (the assertion itself does NOT
    hardcode the expected agent name; it reads the registry for whichever
    agentType was actually dispatched).
  - the two review-triggered release sites (no-verdict and high-findings)
    both carry the SAME label "release-on-review-fail", so a run through
    each path is indistinguishable to any test or tool keyed on label.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"


def _write_ac(ac_root: Path, ac_id: str) -> Path:
    """Write a minimal, valid AC YAML using yaml.safe_dump (fixture-authenticity)."""
    subdir = ac_root / "build-orchestration"
    subdir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic release-wiring fixture {ac_id}",
        "component": "build-orchestration",
        "level": "L3",
        "status": "active",
        "work_status": "todo",
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "covered_by": [],
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _worktree_label_response(worktree_root: Path) -> dict[str, Any]:
    return {
        "worktree_path": str(worktree_root),
        "branch": "fast-lane/test-bo2400f-10i",
        "ac_store_path": str(worktree_root / "docs" / "acceptance-criteria"),
        "created": True,
    }


def _base_label_responses(worktree_root: Path, ac_ids: list[str]) -> dict[str, Any]:
    """The minimal set of overrides needed to sail the lane past claim and
    reach the coder phase with everything green, so a scenario can override
    just the ONE label it wants to fail at."""
    return {
        "fastlane-worktree": _worktree_label_response(worktree_root),
        "resolve-connected": {"ac_ids": ac_ids, "message": f"{len(ac_ids)} to build"},
        "claim-connected": {
            "claimed": ac_ids,
            "excluded_claimed": [],
            "target_refused": False,
            "message": f"claimed {len(ac_ids)} ACs",
        },
        "test-writer-connected": {
            "status": "ok",
            "tests_written": ["unit_tests/x/test_stub.py"],
            "gate_passed": True,
            "reason": None,
            "green_at_baseline": [],
            "message": "red baseline established",
        },
        "coder-connected": {
            "status": "ok",
            "files_modified": [],
            "green": True,
            "coverage_ok": True,
            "uncovered_ac_ids": [],
            "message": "implemented",
        },
        "fastlane-review": {
            "verdict_obtained": True,
            "high_findings": [],
            "medium_findings": [],
            "low_suppressed_count": 0,
            "message": "clean review",
        },
        "fastlane-commit": {
            "status": "ok",
            "branch": "fast-lane/test-bo2400f-10i",
            "message": "committed",
        },
    }


class _FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_root = self.worktree_root / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True)
        self.ac_ids = ["FLT-9111a", "FLT-9111b"]
        for ac_id in self.ac_ids:
            _write_ac(self.ac_root, ac_id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_to(self, overrides: dict[str, Any]) -> HarnessResult:
        label_responses = _base_label_responses(self.worktree_root, self.ac_ids)
        label_responses.update(overrides)
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )


def _release_calls(result: HarnessResult) -> list:
    return [c for c in result.agent_calls if c.label and c.label.startswith("release-on-")]


def _load_registry() -> dict:
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _registry_entry(agent_id: str) -> dict | None:
    registry = _load_registry()
    for entry in registry.get("agents", []):
        if entry.get("id") == agent_id:
            return entry
    return None


# ---------------------------------------------------------------------------
# The nine halting scenarios, each with the ONE label override that forces a
# halt at that phase (all six named preconditions above already sail past
# everything before it).
# ---------------------------------------------------------------------------

_HALT_SCENARIOS: dict[str, dict[str, Any]] = {
    "context-bundle-fail": {
        "fastlane-context-bundle": {"obtained": False, "bundle": "", "message": "boom"},
    },
    "test-writer-fail": {
        "test-writer-connected": {"status": "blocker", "message": "could not write tests"},
    },
    "red-baseline-fail": {
        "test-writer-connected": {
            "status": "ok",
            "tests_written": [],
            "gate_passed": False,
            "reason": "no_new_covering_tests",
            "green_at_baseline": [],
            "message": "no covering test found",
        },
    },
    "coder-fail": {
        "coder-connected": {"status": "blocker", "message": "could not implement"},
    },
    "coverage-fail": {
        "coder-connected": {
            "status": "ok",
            "files_modified": ["scripts/foo.py"],
            "green": True,
            "coverage_ok": False,
            "uncovered_ac_ids": ["FLT-9111b"],
            "message": "partial coverage",
        },
    },
    "review-no-verdict-fail": {
        "fastlane-review": {
            "verdict_obtained": False,
            "high_findings": [],
            "medium_findings": [],
            "low_suppressed_count": 0,
            "message": "could not read diff",
        },
    },
    "review-high-findings-fail": {
        "fastlane-review": {
            "verdict_obtained": True,
            "high_findings": ["hardcoded secret"],
            "medium_findings": [],
            "low_suppressed_count": 0,
            "message": "one high finding",
        },
    },
    "changelog-fail": {
        "coder-connected": {
            "status": "ok",
            "files_modified": ["scripts/foo.py"],
            "green": True,
            "coverage_ok": True,
            "uncovered_ac_ids": [],
            "message": "implemented",
        },
        "fastlane-changelog": {
            "status": "error",
            "entry_added": False,
            "entry_path": None,
            "message": "emit_entry.py failed",
        },
    },
    "commit-fail": {
        "fastlane-commit": {"status": "error", "message": "pre-commit hook rejected"},
    },
}


class TestReleaseSiteCount(_FixtureCase):
    def test_every_one_of_the_nine_halting_paths_reaches_a_release_step(self) -> None:
        # covers: BO-2400f-10-i
        """Each of the nine named halting scenarios records at least one
        release-on-* dispatch."""
        missing = []
        for scenario, overrides in _HALT_SCENARIOS.items():
            result = self._run_to(overrides)
            if not _release_calls(result):
                missing.append(
                    (scenario, result.stderr, [c.label for c in result.agent_calls])
                )
        self.assertFalse(
            missing,
            f"scenarios with NO recorded release-on-* dispatch: {missing}",
        )


class TestReleaseLabelUniqueness(_FixtureCase):
    def test_every_release_site_has_a_unique_label(self) -> None:
        # covers: BO-2400f-10-i
        """THE KNOWN DEFECT: release-on-review-fail is reused for both the
        no-verdict and the high-findings halt, so the two are
        indistinguishable by label. Collecting the labels recorded across all
        nine scenarios must yield nine DISTINCT labels."""
        labels: dict[str, str] = {}
        for scenario, overrides in _HALT_SCENARIOS.items():
            result = self._run_to(overrides)
            calls = _release_calls(result)
            self.assertTrue(calls, f"scenario {scenario!r} recorded no release call")
            labels[scenario] = calls[0].label

        distinct = set(labels.values())
        self.assertEqual(
            len(distinct),
            len(labels),
            f"release labels are not unique per scenario — collisions: {labels}",
        )


class TestReleaseExecutorCharter(_FixtureCase):
    def test_release_executor_charter_covers_mutating_ac_claim_state(self) -> None:
        # covers: BO-2400f-10-i
        """THE LOAD-BEARING CHARTER TEST. Read config/agent_registry.json at
        test time and assert the actually-dispatched agentType's OWN
        declared entry does not explicitly forbid running shell commands
        (permits_shell: false) — never hardcode the expected agent name."""
        result = self._run_to(_HALT_SCENARIOS["coder-fail"])
        calls = _release_calls(result)
        self.assertTrue(calls, f"no release call recorded. stderr={result.stderr!r}")

        violations = []
        for call in calls:
            agent_id = call.agent_type
            self.assertIsNotNone(agent_id, "release dispatch must declare an agentType")
            entry = _registry_entry(agent_id)
            self.assertIsNotNone(
                entry, f"agentType {agent_id!r} has no config/agent_registry.json entry"
            )
            assert entry is not None  # narrowing for mypy; assertIsNotNone above is the real check
            if entry.get("permits_shell") is False:
                violations.append(agent_id)

        self.assertFalse(
            violations,
            f"release dispatch used agentType(s) whose registry entry explicitly "
            f"declares permits_shell: false (cannot run the release Bash command): "
            f"{violations}",
        )

    def test_status_checker_is_not_the_release_executor_on_any_path(self) -> None:
        # covers: BO-2400f-10-i
        """The concrete regression guard for KI-BO-020: no recorded release
        step, across any of the nine halting scenarios, dispatches
        agentType 'status-checker'."""
        offenders = []
        for scenario, overrides in _HALT_SCENARIOS.items():
            result = self._run_to(overrides)
            for call in _release_calls(result):
                if call.agent_type == "status-checker":
                    offenders.append((scenario, call.label))
        self.assertFalse(
            offenders,
            f"release dispatch used agentType 'status-checker' on: {offenders}",
        )


class TestReleaseTargetsClaimedIds(_FixtureCase):
    def test_each_release_step_carries_the_ids_this_run_actually_claimed(self) -> None:
        # covers: BO-2400f-10-i
        """With claim-connected stubbed to a NARROWER claimed list than the
        full resolved set, the release invocation embedded in the prompt
        must target the narrower (actually-claimed) list, not the full
        resolved set."""
        narrow_overrides = dict(_HALT_SCENARIOS["coder-fail"])
        narrow_overrides["claim-connected"] = {
            "claimed": ["FLT-9111a"],
            "excluded_claimed": ["FLT-9111b"],
            "target_refused": False,
            "message": "claimed 1 of 2 (other owned by a concurrent run)",
        }
        result = self._run_to(narrow_overrides)
        calls = _release_calls(result)
        self.assertTrue(calls, f"no release call recorded. stderr={result.stderr!r}")
        prompt = calls[0].prompt or ""
        self.assertIn("FLT-9111a", prompt)
        self.assertNotIn(
            "FLT-9111b",
            prompt,
            "release invocation must not target an AC excluded from this run's claim",
        )

    def test_each_release_step_targets_the_store_the_run_claimed_in(self) -> None:
        # covers: BO-2400f-10-i
        """The --ac-root value embedded in the release prompt is the same
        acStoreRoot the claim step used — read from the worktree the lane
        itself resolved, not a hardcoded/second path."""
        result = self._run_to(_HALT_SCENARIOS["coder-fail"])
        claim_calls = [c for c in result.agent_calls if c.label == "claim-connected"]
        release_calls = _release_calls(result)
        self.assertTrue(claim_calls, "no claim-connected call recorded")
        self.assertTrue(release_calls, f"no release call recorded. stderr={result.stderr!r}")

        expected_ac_root = str(self.ac_root)
        self.assertIn(expected_ac_root, claim_calls[0].prompt or "")
        self.assertIn(expected_ac_root, release_calls[0].prompt or "")


class TestNoClaimNoRelease(_FixtureCase):
    def test_a_run_that_never_claimed_dispatches_no_release_step(self) -> None:
        # covers: BO-2400f-10-i
        """On a path that halts BEFORE the claim step (an unproducible
        resolved set), no release-on-* dispatch is recorded at all — there
        is nothing to release."""
        label_responses = _base_label_responses(self.worktree_root, self.ac_ids)
        label_responses["check-producibility"] = {
            "producible": False,
            "unproducible": [{"ac_id": self.ac_ids[1], "reason": "doc-only"}],
        }
        result = run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )
        self.assertFalse(
            _release_calls(result),
            f"a run that never claimed must dispatch NO release step. "
            f"Calls: {[c.label for c in result.agent_calls]}",
        )


class TestClaimDispatchUnaltered(_FixtureCase):
    def test_the_claim_dispatch_is_not_altered_by_this_change(self) -> None:
        # covers: BO-2400f-10-i
        """No-collateral-change guard: exactly one claim-connected dispatch
        is still recorded, with agentType status-checker (the claim dispatch
        belongs to BO-2400f-7 and must be left alone by this fix)."""
        result = self._run_to(_HALT_SCENARIOS["coder-fail"])
        claim_calls = [c for c in result.agent_calls if c.label == "claim-connected"]
        self.assertEqual(len(claim_calls), 1, f"expected exactly one claim-connected call: {result.agent_calls}")
        self.assertEqual(claim_calls[0].agent_type, "status-checker")


if __name__ == "__main__":
    unittest.main()
