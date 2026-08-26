"""
MODULE: unit_tests/workflows/test_bo2400f_10ii_release_reporting.py
GOAL: RED behavioral tests for BO-2400f-10-ii — every one of the nine
      `return { status: "blocked", ... }` halt payloads in
      templates/workflows-js/fast-lane-ship.js discards the release step's
      own return value (`await agent(...)` with no binding). This file
      proves that discard by planting a distinctive, otherwise-impossible
      marker in the stubbed release reply and showing it never surfaces in
      the run's terminal payload — the load-bearing case being the OBSERVED
      refusal shape from run wf_bd4984e8-438 (KI-BO-020):
      {"status": "refused", "reason": "out-of-scope-..."}.

All assertions drive the real script via
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() and inspect
HarnessResult.result (the script's own top-level `return` value,
JSON-round-tripped) — never the JS source text.

=== Red baseline ===

RED today because none of the nine halt payloads carry ANY release-outcome
field (release_attempted / released_ac_ids / unreleased_ac_ids /
release_executor / release_error), regardless of what the release dispatch
is stubbed to return — the `await agent(...)` call's return value is dropped
at every one of the nine call sites.
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

# The literal refusal shape observed on run wf_bd4984e8-438 (KI-BO-020) — a
# status-checker declining role reassignment.
_OBSERVED_REFUSAL = {
    "status": "refused",
    "reason": "out-of-scope-for-status-checker",
}

_SUCCESSFUL_RELEASE = {"released": ["FLT-9121a", "FLT-9121b"]}

# A distinctive, otherwise-impossible marker value. If this string appears
# anywhere in the terminal payload, the release reply was actually read
# rather than discarded.
_CANARY = "CANARY-RELEASE-OUTCOME-4f9c21"
_CANARY_RELEASE_REPLY = {"released": [_CANARY]}


def _write_ac(ac_root: Path, ac_id: str) -> Path:
    subdir = ac_root / "build-orchestration"
    subdir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic release-reporting fixture {ac_id}",
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
        "branch": "fast-lane/test-bo2400f-10ii",
        "ac_store_path": str(worktree_root / "docs" / "acceptance-criteria"),
        "created": True,
    }


def _base_label_responses(worktree_root: Path, ac_ids: list[str]) -> dict[str, Any]:
    return {
        "fastlane-worktree": _worktree_label_response(worktree_root),
        "resolve-connected": {"ac_ids": ac_ids, "message": f"{len(ac_ids)} to build"},
        "claim-connected": {
            "claimed": ac_ids,
            "excluded_claimed": [],
            "target_refused": False,
            "message": f"claimed {len(ac_ids)} ACs",
        },
        # Force a halt at the earliest available gate (test-writer) so every
        # test in this file exercises the SAME halting phase and only the
        # release reply varies between scenarios.
        "test-writer-connected": {"status": "blocker", "message": "boom"},
    }


class _FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_root = self.worktree_root / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True)
        self.ac_ids = ["FLT-9121a", "FLT-9121b"]
        for ac_id in self.ac_ids:
            _write_ac(self.ac_root, ac_id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_with_release_reply(self, release_reply: Any) -> HarnessResult:
        label_responses = _base_label_responses(self.worktree_root, self.ac_ids)
        label_responses["release-on-test-writer-fail"] = release_reply
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )


def _payload_text(result: HarnessResult) -> str:
    """Flatten the terminal payload to a searchable string for canary checks."""
    import json as _json

    if result.result is None:
        return ""
    try:
        return _json.dumps(result.result)
    except TypeError:
        return str(result.result)


class TestReleaseResultIsReadNotDiscarded(_FixtureCase):
    def test_the_release_result_is_read_rather_than_discarded(self) -> None:
        # covers: BO-2400f-10-ii
        """THE MECHANICAL RED SIGNAL. Stub the release reply with a
        distinctive marker and assert it is observable in the terminal
        payload. Today it never is — the await'd value is dropped."""
        result = self._run_with_release_reply(_CANARY_RELEASE_REPLY)
        self.assertIsNotNone(
            result.result, f"workflow produced no terminal payload. stderr={result.stderr!r}"
        )
        self.assertIn(
            _CANARY,
            _payload_text(result),
            f"canary release value never surfaced in the terminal payload: {result.result!r}",
        )


class TestRefusedReleaseNamedInHalt(_FixtureCase):
    def test_a_refused_release_is_named_in_the_halt_payload(self) -> None:
        # covers: BO-2400f-10-ii
        """THE LOAD-BEARING TEST. With the release stubbed to the literal
        refusal shape observed on run wf_bd4984e8-438, the terminal payload
        must say the release did NOT happen."""
        result = self._run_with_release_reply(_OBSERVED_REFUSAL)
        payload = result.result or {}
        self.assertFalse(
            payload.get("release_attempted", False) is True,
            f"a refused release must not be reported as release_attempted=True: {payload!r}",
        )
        self.assertTrue(
            payload.get("unreleased_ac_ids"),
            f"a refused release must list the ids left at in_progress: {payload!r}",
        )

    def test_a_refused_release_payload_still_names_the_triggering_failure(self) -> None:
        # covers: BO-2400f-10-ii
        """ORDERING clause: failing_phase and the original halt message are
        still present, UNALTERED, alongside the new release fact."""
        result = self._run_with_release_reply(_OBSERVED_REFUSAL)
        payload = result.result or {}
        self.assertEqual(payload.get("failing_phase"), "test-writer")
        self.assertIn("test-writer", (payload.get("message") or ""))

    def test_a_refused_release_payload_lists_the_ids_left_in_progress(self) -> None:
        # covers: BO-2400f-10-ii
        """The payload names EACH claimed id left at in_progress — the ids
        themselves, not merely a count."""
        result = self._run_with_release_reply(_OBSERVED_REFUSAL)
        payload = result.result or {}
        unreleased = payload.get("unreleased_ac_ids") or []
        for ac_id in self.ac_ids:
            self.assertIn(ac_id, unreleased, f"{ac_id} missing from unreleased_ac_ids: {payload!r}")

    def test_a_refused_release_payload_says_a_later_run_will_be_refused(self) -> None:
        # covers: BO-2400f-10-ii
        """The payload states the consequence per BO-2400f-8: a later run
        aimed at these ids will be refused while they stay in_progress."""
        result = self._run_with_release_reply(_OBSERVED_REFUSAL)
        payload = result.result or {}
        full_text = _payload_text(result)
        self.assertTrue(
            "refused" in full_text.lower() and "in_progress" in full_text.lower(),
            f"payload does not state the later-run-refused consequence: {payload!r}",
        )


class TestSuccessfulReleaseNamed(_FixtureCase):
    def test_a_successful_release_payload_names_the_released_ids(self) -> None:
        # covers: BO-2400f-10-ii
        """With the release stubbed to a successful outcome, the payload
        names the ids returned to todo."""
        result = self._run_with_release_reply(_SUCCESSFUL_RELEASE)
        payload = result.result or {}
        released = payload.get("released_ac_ids") or []
        self.assertEqual(
            sorted(released),
            sorted(_SUCCESSFUL_RELEASE["released"]),
            f"payload does not name the released ids: {payload!r}",
        )
        self.assertTrue(payload.get("release_attempted") is True)

    def test_a_successful_release_returned_as_a_json_STRING_is_read_as_success(self) -> None:
        # covers: BO-2400f-10-ii
        """A successful release whose reply arrives as a JSON *string* is read
        as a success, not reported as a failure.

        THIS IS THE SHAPE THE ENGINE ACTUALLY PRODUCES when a dispatch carries
        no schema: agent() returns the agent's final text verbatim. Every other
        test in this file stubs a dict, which the engine only ever produces for
        a dispatch that declares one — so all of them passed while the real lane
        reported every single release, successful or not, as failed.

        Observed on run wf_3b98fa8a-241: the release genuinely worked and all
        three criteria were todo on disk afterwards, while the terminal payload
        said `release_attempted: false`, listed all three under
        `unreleased_ac_ids`, and warned that a later run would be refused. An
        operator following that message would have gone to unstick criteria that
        were already free, and would have concluded the just-shipped release fix
        did not work.
        """
        reply_as_text = json.dumps(_SUCCESSFUL_RELEASE)
        self.assertIsInstance(reply_as_text, str)

        result = self._run_with_release_reply(reply_as_text)
        payload = result.result or {}

        self.assertTrue(
            payload.get("release_attempted") is True,
            f"a string-shaped successful release must read as attempted: {payload!r}",
        )
        self.assertEqual(
            sorted(payload.get("released_ac_ids") or []),
            sorted(_SUCCESSFUL_RELEASE["released"]),
            f"payload does not name the released ids: {payload!r}",
        )
        self.assertEqual(
            payload.get("unreleased_ac_ids") or [],
            [],
            f"nothing was left behind, so unreleased_ac_ids must be empty: {payload!r}",
        )
        self.assertIsNone(
            payload.get("release_error"),
            f"a successful release must record no error: {payload!r}",
        )

    def test_a_non_json_release_reply_is_still_reported_as_not_released(self) -> None:
        # covers: BO-2400f-10-ii
        """Tolerating a JSON string must not become tolerating anything.

        The string path exists so a real success is read as success — not so
        that prose, an apology, or a truncated reply quietly counts as one. A
        reply with no parseable object still takes the failure branch.
        """
        result = self._run_with_release_reply("I was unable to run that command.")
        payload = result.result or {}
        self.assertTrue(
            payload.get("release_attempted") is False,
            f"unparseable prose must not read as a release: {payload!r}",
        )
        self.assertTrue(
            payload.get("unreleased_ac_ids"),
            f"claimed ids must be reported as unreleased: {payload!r}",
        )

    def test_the_released_and_refused_payloads_differ(self) -> None:
        # covers: BO-2400f-10-ii
        """Driving the SAME halting path twice, once with a successful
        release and once with a refusal, must produce two DIFFERENT
        terminal payloads."""
        success_result = self._run_with_release_reply(_SUCCESSFUL_RELEASE)
        refused_result = self._run_with_release_reply(_OBSERVED_REFUSAL)
        self.assertNotEqual(
            success_result.result,
            refused_result.result,
            "a successful release and a refused release produced identical "
            f"terminal payloads: {success_result.result!r}",
        )


class TestUnreadableReleaseReplies(_FixtureCase):
    def test_an_unreadable_release_reply_is_reported_as_not_released(self) -> None:
        # covers: BO-2400f-10-ii
        """Null, empty-object, and missing-outcome-key replies must ALL fail
        closed to release_attempted: not True with every claimed id in
        unreleased_ac_ids."""
        for label, reply in [("null", None), ("empty", {}), ("missing-key", {"foo": "bar"})]:
            with self.subTest(reply=label):
                result = self._run_with_release_reply(reply)
                payload = result.result or {}
                self.assertFalse(
                    payload.get("release_attempted") is True,
                    f"reply {label!r} must not be treated as a successful release: {payload!r}",
                )
                unreleased = payload.get("unreleased_ac_ids") or []
                for ac_id in self.ac_ids:
                    self.assertIn(
                        ac_id,
                        unreleased,
                        f"reply {label!r}: {ac_id} missing from unreleased_ac_ids: {payload!r}",
                    )


class TestReportingAcrossMultiplePaths(_FixtureCase):
    def test_release_reporting_holds_on_more_than_one_halting_path(self) -> None:
        # covers: BO-2400f-10-ii
        """The release-outcome fields are present on more than just the
        test-writer-fail halt — also check the coder-fail halt."""
        label_responses = _base_label_responses(self.worktree_root, self.ac_ids)
        # Sail past test-writer this time so we reach coder-fail instead.
        label_responses["test-writer-connected"] = {
            "status": "ok",
            "tests_written": [],
            "gate_passed": True,
            "reason": None,
            "green_at_baseline": [],
            "message": "ok",
        }
        label_responses["coder-connected"] = {"status": "blocker", "message": "boom"}
        label_responses["release-on-coder-fail"] = _OBSERVED_REFUSAL
        result = run_workflow_under_e2(
            _WORKFLOW_PATH, label_responses=label_responses, args={"ac": self.ac_ids[0]}
        )
        payload = result.result or {}
        self.assertEqual(payload.get("failing_phase"), "python-coder")
        self.assertFalse(payload.get("release_attempted") is True)
        self.assertTrue(payload.get("unreleased_ac_ids"))


class TestFailedReleaseDoesNotChangeHaltStatus(_FixtureCase):
    def test_a_failed_release_does_not_change_the_runs_halting_status(self) -> None:
        # covers: BO-2400f-10-ii
        """status, classification and failing_phase are identical whether
        the release succeeds or is refused — only the new release_* fields
        differ."""
        success_result = self._run_with_release_reply(_SUCCESSFUL_RELEASE)
        refused_result = self._run_with_release_reply(_OBSERVED_REFUSAL)
        success_payload = success_result.result or {}
        refused_payload = refused_result.result or {}
        self.assertEqual(success_payload.get("status"), refused_payload.get("status"))
        self.assertEqual(
            success_payload.get("classification"), refused_payload.get("classification")
        )
        self.assertEqual(
            success_payload.get("failing_phase"), refused_payload.get("failing_phase")
        )


if __name__ == "__main__":
    unittest.main()
