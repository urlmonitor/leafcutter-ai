"""
MODULE: tests.kernel.adapters.test_cli
GOAL: Test the `python -m kernel` command line as real child processes: each command, the
    one-JSON-document stdout contract, the documented exit codes (0, 2, 3, 4, 5), stdin and file
    input, rejections with the packet to repair, and path and input safety.
BUSINESS CONTEXT: The Claude Code skill branches on the exit code and parses stdout blindly; a
    stray log line or a wrong code would break a run the kernel handled correctly (Rev 3 11.2).
ARCHITECTURE: The harness (`cli_harness`) runs the shipped `kernel.adapters.cli.main` over the
    scripted rig; `real_cli` runs `python -m kernel` itself for commands that need no provider.
    Each test shares one session (run root) across its few processes to keep the suite fast.
"""

from __future__ import annotations

import json
import unittest

from tests.kernel.adapters.cli_support import CliSession, host_answer, real_cli
from tests.kernel.adapters.support import task_input_json
from tests.kernel.interaction.support import host_rig


class CliCase(unittest.TestCase):
    kind = "host"

    def setUp(self) -> None:
        self.session = CliSession(self.kind)
        self.addCleanup(self.session.close)


class TestLifecycle(CliCase):
    def test_run_from_stdin_then_status_then_resume_from_file(self) -> None:
        # covers: DK-600a-1
        stdin = json.dumps(task_input_json(host_rig()))
        started = self.session.cli("run", "--json", stdin=stdin)  # no flag: stdin
        self.assertEqual(started.code, 0, started.stderr)
        envelope = started.document()
        self.assertEqual(envelope["status"], "waiting_host")
        self.assertEqual(envelope["pending_interaction"]["operation"], "bounded_research")
        self.assertTrue(envelope["pending_interaction"]["output_json_schema"])
        run_id = envelope["run_id"]

        status = self.session.cli("status", "--run-id", run_id, "--json")
        self.assertEqual((status.code, status.document()["status"]), (0, "waiting_host"))
        self.assertEqual(status.document()["pending_interaction"]["id"],
                         envelope["pending_interaction"]["id"])

        path = self.session.write("answer.json", host_answer(envelope))
        done = self.session.cli("resume", "--run-id", run_id, "--input-file", str(path), "--json")
        self.assertEqual(done.code, 0, done.stderr)
        final = done.document()
        self.assertEqual(final["status"], "completed")
        self.assertIsNone(final["pending_interaction"])
        self.assertIsNotNone(final["output"])

    def test_resume_reads_stdin_with_a_dash_and_accepts_the_design_flag_spelling(self) -> None:
        envelope = self.session.start()
        raw = json.dumps(host_answer(envelope))
        done = self.session.cli("resume", "--run-id", envelope["run_id"], "--response", "-",
                                stdin=raw)
        self.assertEqual((done.code, done.document()["status"]), (0, "completed"))

    def test_logs_go_to_stderr_not_stdout(self) -> None:
        envelope = self.session.start()
        result = self.session.cli("status", "--run-id", envelope["run_id"])
        self.assertEqual(result.code, 0)
        result.document()  # raises unless stdout is exactly one JSON line


class TestRejections(CliCase):
    def test_invalid_host_output_exits_3_and_redelivers_the_packet_then_repair_works(self) -> None:
        envelope = self.session.start()
        run_id, packet = envelope["run_id"], envelope["pending_interaction"]
        bad = self.session.write("bad.json", host_answer(envelope, response={"evidence": "x"}))
        rejected = self.session.cli("resume", "--run-id", run_id, "--input-file", str(bad))
        self.assertEqual(rejected.code, 3)
        body = rejected.document()
        self.assertIn(body["error"]["code"], ("schema_invalid", "semantic_invalid"))
        self.assertEqual(body["error"]["details"]["pending_interaction"]["id"], packet["id"])
        self.assertEqual(body["envelope"]["status"], "waiting_host")
        good = self.session.write("good.json", host_answer(envelope))
        fixed = self.session.cli("resume", "--run-id", run_id, "--input-file", str(good))
        self.assertEqual((fixed.code, fixed.document()["status"]), (0, "completed"))

    def test_stale_revision_exits_3_with_the_code_and_state_unchanged(self) -> None:
        envelope = self.session.start()
        stale = self.session.write("stale.json", host_answer(
            envelope, revision=envelope["state_revision"] + 9))
        result = self.session.cli("resume", "--run-id", envelope["run_id"],
                                  "--input-file", str(stale))
        self.assertEqual(result.code, 3)
        error = result.document()["error"]
        self.assertEqual(error["code"], "stale_revision")
        self.assertIn("message", error)
        after = self.session.cli("status", "--run-id", envelope["run_id"]).document()
        self.assertEqual(after["state_revision"], envelope["state_revision"])

    def test_unparseable_and_invalid_inputs_exit_3_without_creating_a_run(self) -> None:
        not_json = self.session.inprocess("run", stdin="{nope")
        self.assertEqual((not_json.code, not_json.document()["error"]["code"]),
                         (3, "input_not_json"))
        invalid = self.session.inprocess("run", stdin=json.dumps({"goal": "x"}))
        self.assertEqual((invalid.code, invalid.document()["error"]["code"]),
                         (3, "invalid_task_input"))
        self.assertTrue(invalid.document()["error"]["details"]["errors"])
        missing = self.session.inprocess("run", "--input-file",
                                         str(self.session.tmp / "absent.json"))
        self.assertEqual((missing.code, missing.document()["error"]["code"]),
                         (3, "input_unreadable"))
        self.assertFalse((self.session.root / "runs").exists())


class TestUnknownAndUnsafe(CliCase):
    def test_unknown_run_exits_4(self) -> None:
        result = self.session.inprocess("status", "--run-id", "run-does-not-exist")
        self.assertEqual(result.code, 4)
        self.assertEqual(result.document()["error"]["code"], "run_not_found")

    def test_run_ids_that_are_not_plain_segments_are_rejected_before_any_file_access(self) -> None:
        for bad in ("../escape", "a/b", "..", "C:evil"):
            result = self.session.inprocess("status", "--run-id", bad)
            self.assertEqual((result.code, result.document()["error"]["code"]),
                             (3, "invalid_run_id"), bad)

    def test_usage_errors_exit_2_with_nothing_on_stdout(self) -> None:
        for argv in (["bogus"], ["status"], ["cancel", "--run-id", "r"]):
            result = self.session.inprocess(*argv)
            self.assertEqual(result.code, 2, argv)
            self.assertEqual(result.stdout, "")
            self.assertIn("usage", result.stderr)
        shipped = real_cli(["bogus"])  # the real entry point, argparse fails before any setup
        self.assertEqual((shipped.code, shipped.stdout), (2, ""))

    def test_without_a_jev_credential_run_exits_5_with_a_json_error(self) -> None:
        path = self.session.write("task.json", task_input_json(host_rig()))
        result = self.session.cli("run", "--input-file", str(path), nojev=True)
        self.assertEqual(result.code, 5)
        self.assertEqual(result.document()["error"]["code"], "provider_unavailable")
        self.assertFalse((self.session.root / "runs").exists())


class TestCancel(CliCase):
    def test_cancel_then_resume_is_refused(self) -> None:
        envelope = self.session.start()
        run_id = envelope["run_id"]
        cancelled = self.session.cli("cancel", "--run-id", run_id, "--actor", "human:demo")
        self.assertEqual(cancelled.code, 0, cancelled.stderr)
        self.assertEqual(cancelled.document()["status"], "cancelled")
        path = self.session.write("late.json", host_answer(envelope))
        late = self.session.cli("resume", "--run-id", run_id, "--input-file", str(path))
        self.assertEqual(late.code, 3)
        self.assertEqual(late.document()["error"]["code"], "cancelled_or_superseded")

    def test_a_malformed_actor_exits_3(self) -> None:
        result = self.session.inprocess("cancel", "--run-id", "run-x", "--actor", "nobody")
        self.assertEqual((result.code, result.document()["error"]["code"]), (3, "invalid_actor"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:00 [python-coder]: Usage errors run the shipped `python -m kernel` (argparse
#   fails before any environment is built), the rest run the harness over the scripted rig.
#   (#KernelBootstrapV0/P7)
# ====================================================================
