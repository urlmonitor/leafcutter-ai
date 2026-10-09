"""
MODULE: unit_tests/workflows/test_bo2400f5iii_declined_step_replay_and_boundary.py
GOAL: RED behavioural tests for BO-2400f-5-iii test_spec entries 4, 5, and 6 —
      the 2026-09-25 incident replay, the command-step-runner exit_status
      discrimination, and the empty/unparseable-reply boundary.

=== Why each is RED today ===

Replay (`OBSERVED_2026_09_25_REPLY`): today's per-step guards each read this
reply through their OWN pre-existing logic (resolve's empty-set no-op,
producibility's fail-closed refusal, claim's BO-2400f-7-iii "never attempted"
halt) — none of which sets `halt_kind`. That is the one thing missing.

Command-step-runner discrimination: fast-lane-ship.js defines no
`classifyStepReply` function at all today (confirmed:
`grep -n "classifyStepReply" templates/workflows-js/fast-lane-ship.js` returns
nothing), so extracting it (the same technique
test_bo_2700_defer_epic_pr.py uses for selectDispatchPhases()) fails in
setUpClass before any assertion runs — a valid RED (AttributeError-class
failure, not a syntax error in THIS test file).

Boundary (empty / unparseable claim reply): both shapes fall through to the
existing "claim was never attempted" halt (BO-2400f-7-iii), which carries no
`halt_kind` field either.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows._bo2400f5iii_fixtures import (  # noqa: E402
    OBSERVED_2026_09_25_CLAIM_REPLY,
    OBSERVED_2026_09_25_REFUSAL_PREFIX,
    OBSERVED_2026_09_25_REPLY,
    WORKFLOW_PATH,
    run_lane,
)

_INCIDENT_REPLAY_LABELS = ("resolve-connected", "check-producibility", "claim-connected")
_INCIDENT_FORBIDDEN_MARKERS = ("already claimed", "in progress", "concurrent run")


class TestObserved20260925RefusalYieldsDeclinedStepWithoutContentionWording(
    unittest.TestCase
):
    """test_spec[4] (angle: real_artifact)."""

    def test_observed_2026_09_25_refusal_yields_declined_step_without_contention_wording(
        self,
    ) -> None:
        # covers: BO-2400f-5-iii
        # angle: real_artifact
        #
        # NOTE: no subTest() — see test_bo2400f5iii_declined_step_core.py's
        # matching note; a subTest() failure would leave THIS outer nodeid
        # reading PASSED to fast_lane.py's verify_red_baseline text parser.
        problems: list[str] = []
        for label in _INCIDENT_REPLAY_LABELS:
            # claim-connected is a command step: it sees the incident as the
            # runner-shaped decline; the other steps keep the plain reply.
            replay = (
                OBSERVED_2026_09_25_CLAIM_REPLY
                if label == "claim-connected"
                else OBSERVED_2026_09_25_REPLY
            )
            result = run_lane({label: replay})
            if result.result is None:
                problems.append(f"[{label}] no terminal payload. stderr={result.stderr!r}")
                continue
            payload = result.result

            if payload.get("halt_kind") != "declined_step":
                problems.append(
                    f"[{label}] The replayed 2026-09-25 refusal must yield a "
                    f"declined-step halt. Got: {payload}"
                )
                continue
            as_text = str(payload)
            if "status-checker" not in as_text:
                problems.append(f"[{label}] The halt must name status-checker. Got: {payload}")
            if OBSERVED_2026_09_25_REFUSAL_PREFIX not in as_text:
                problems.append(
                    f"[{label}] The halt must quote the agent's own refusal "
                    f"verbatim. Got: {payload}"
                )
            as_text_lower = as_text.lower()
            for marker in _INCIDENT_FORBIDDEN_MARKERS:
                if marker in as_text_lower:
                    problems.append(
                        f"[{label}] No contention wording ('{marker}') may "
                        f"appear when replaying this incident. Got: {payload}"
                    )

        self.assertEqual(problems, [], "\n".join(problems))


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level `function <name>(...) { ... }` by brace-counting —
    same technique as test_bo_2700_defer_epic_pr.py's own helper of the same
    name, applied here to fast-lane-ship.js's assumed classifyStepReply.
    """
    start = source.index(f"function {name}(")
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"could not extract function {name}")


class TestCommandStepRunnerReplyWithoutExitStatusIsADeclineAndNonzeroExitIsAResult(
    unittest.TestCase
):
    """test_spec[5] (angle: discrimination). covers: BO-2400f-5-iii, BO-2400a-1-i.

    ASSUMED API (see _bo2400f5iii_fixtures.py module docstring): a pure
    `classifyStepReply(reply, {step, agent, isCommandStep})` returning
    `{kind: 'result'|'declined'|'failed', ...}`, extracted from the real
    on-disk source and run under `node`.
    """

    func_src: str

    @classmethod
    def setUpClass(cls) -> None:
        source = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.func_src = _extract_function(source, "classifyStepReply")

    def _classify(self, reply, meta) -> dict:
        driver = (
            self.func_src
            + "\nconsole.log(JSON.stringify(classifyStepReply("
            + "JSON.parse(process.argv[2]), JSON.parse(process.argv[3]))));\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".mjs", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(driver)
            path = fh.name
        try:
            proc = subprocess.run(
                ["node", path, json.dumps(reply), json.dumps(meta)],
                capture_output=True, text=True, timeout=15, check=True,
            )
        finally:
            Path(path).unlink(missing_ok=True)
        return json.loads(proc.stdout.strip())

    def test_command_step_runner_reply_without_exit_status_is_a_decline_and_nonzero_exit_is_a_result(
        self,
    ) -> None:
        # covers: BO-2400f-5-iii
        # covers: BO-2400a-1-i
        # angle: discrimination
        meta = {"step": "claim", "agent": "command-step-runner", "isCommandStep": True}
        decline_reply = {
            "declined": True,
            "step": "claim",
            "agent": "command-step-runner",
            "reason": "no workspace named",
        }
        nonzero_result_reply = {
            "command": "python3 fast_lane.py claim --ac-ids BO-STUB-1",
            "workspace": "/tmp/fastlane-harness-wt",
            "exit_status": 1,
            "stdout": "",
            "stderr": "already in_progress",
        }

        decline_verdict = self._classify(decline_reply, meta)
        result_verdict = self._classify(nonzero_result_reply, meta)

        self.assertEqual(
            decline_verdict.get("kind"), "declined",
            f"A command-step-runner reply with no exit_status key must "
            f"classify as declined. Got: {decline_verdict}",
        )
        self.assertNotEqual(
            result_verdict.get("kind"), "declined",
            f"A command-step-runner reply carrying a (non-zero) exit_status "
            f"is that step's own result, never a decline. Got: {result_verdict}",
        )


class TestEmptyOrUnparseableReplyIsADeclinedStep(unittest.TestCase):
    """test_spec[6] (angle: boundary)."""

    def test_empty_or_unparseable_reply_is_a_declined_step(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: boundary
        #
        # NOTE: no subTest() — see test_bo2400f5iii_declined_step_core.py's
        # matching note.
        cases = {
            "empty-reply": None,
            "unparseable-prose-reply": (
                "Sure — here's a haiku about worktrees instead of the "
                "requested JSON: branches split like roots / a single "
                "command awaits / nothing here is claimed"
            ),
        }
        problems: list[str] = []
        for case_name, reply in cases.items():
            result = run_lane({"claim-connected": reply})
            if result.result is None:
                problems.append(f"[{case_name}] no terminal payload. stderr={result.stderr!r}")
                continue
            payload = result.result
            if payload.get("halt_kind") != "declined_step":
                problems.append(
                    f"[{case_name}] An empty or unparseable reply at a command "
                    f"step must halt as a declined step. Got: {payload}"
                )
                continue
            reason = str(payload.get("reason") or "").lower()
            if not any(
                word in reason for word in ("no readable", "unreadable", "unparseable", "empty")
            ):
                problems.append(
                    f"[{case_name}] reason must state explicitly that no "
                    f"readable result was returned. Got: {payload}"
                )

        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
