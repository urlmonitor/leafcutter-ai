"""
MODULE: tests.kernel.adapters.test_cli_io
GOAL: Test the CLI input helpers (JSON from file or stdin, run-id and actor parsing, the single
    JSON output line) and the envelope status precedence the service relies on.
BUSINESS CONTEXT: Request content is untrusted; a bad path, a traversing run id or an oversized
    document must become a clean rejection, and the envelope must never claim a status the run
    record contradicts (Rev 3 sections 11.2 and 7.9).
ARCHITECTURE: Pure unit tests over `cli_io` and `service_envelope`; temp files only.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from kernel.adapters import cli_io
from kernel.adapters.cli_io import CliInputError, parse_actor, read_json_input, safe_run_id
from kernel.contracts import ActorKind, RunStatus, utc_now
from kernel.contracts.enums import ObservabilityStatus
from kernel.persistence.base import CancelInfo, RunRecord
from kernel.service_envelope import build_envelope, effective_status


class TestReadJsonInput(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def test_reads_a_file_and_stdin_the_same_way(self) -> None:
        path = self.tmp / "in.json"
        path.write_text('{"goal": "x \\u00e9"}', encoding="utf-8")
        self.assertEqual(read_json_input(str(path)), {"goal": "x é"})
        self.assertEqual(read_json_input("-", io.StringIO('{"a": 1}')), {"a": 1})
        self.assertEqual(read_json_input(None, io.StringIO("[1]")), [1])

    def test_a_goal_with_shell_metacharacters_arrives_as_data(self) -> None:
        goal = "rm -rf / ; $(reboot) `x` && echo \"hi\" | cat > /dev/null"
        self.assertEqual(read_json_input("-", io.StringIO(json.dumps({"goal": goal})))["goal"],
                         goal)

    def test_problems_become_cli_input_errors_with_stable_codes(self) -> None:
        cases = {"input_unreadable": lambda: read_json_input(str(self.tmp / "missing.json")),
                 "input_not_json": lambda: read_json_input("-", io.StringIO("{oops"))}
        for code, call in cases.items():
            with self.assertRaises(CliInputError) as caught:
                call()
            self.assertEqual(caught.exception.code, code)

    def test_oversized_input_is_refused(self) -> None:
        big = io.StringIO('"' + "x" * (cli_io.MAX_INPUT_BYTES + 10) + '"')
        with self.assertRaises(CliInputError) as caught:
            read_json_input("-", big)
        self.assertEqual(caught.exception.code, "input_too_large")

    def test_a_non_utf8_file_is_unreadable_not_a_crash(self) -> None:
        path = self.tmp / "bin.json"
        path.write_bytes(b"\xff\xfe\x00bad")
        with self.assertRaises(CliInputError) as caught:
            read_json_input(str(path))
        self.assertEqual(caught.exception.code, "input_unreadable")


class TestIdsAndActors(unittest.TestCase):
    def test_run_ids_must_be_plain_path_segments(self) -> None:
        self.assertEqual(safe_run_id("run-ab12"), "run-ab12")
        for bad in ("../x", "a/b", "a\\b", "..", "", "x" * 300, "con", "trailing."):
            with self.assertRaises(CliInputError, msg=bad) as caught:
                safe_run_id(bad)
            self.assertEqual(caught.exception.code, "invalid_run_id")

    def test_actor_keeps_its_prefix_and_kind(self) -> None:
        actor = parse_actor("human:demo")
        self.assertEqual((actor.id, actor.kind), ("human:demo", ActorKind.HUMAN))
        self.assertEqual(parse_actor("host:claude_code").kind, ActorKind.HOST)

    def test_actor_without_a_known_kind_is_refused(self) -> None:
        for bad in ("demo", "robot:x", "human:", ":x", "human: spaced id"):
            with self.assertRaises(CliInputError, msg=bad) as caught:
                parse_actor(bad)
            self.assertEqual(caught.exception.code, "invalid_actor")

    def test_emit_writes_one_ascii_line(self) -> None:
        out = io.StringIO()
        cli_io.emit({"text": "café", "n": 1}, out)
        self.assertEqual(out.getvalue().count("\n"), 1)
        self.assertTrue(out.getvalue().isascii())
        self.assertEqual(json.loads(out.getvalue()), {"text": "café", "n": 1})


class TestEnvelopeStatus(unittest.TestCase):
    def record(self, **fields) -> RunRecord:
        return RunRecord(run_id="run-1", root_task_id="task-1", **fields)

    def test_cancellation_outranks_everything(self) -> None:
        record = self.record(cancel=CancelInfo(by="human:x", at=utc_now()))
        self.assertEqual(effective_status(record, {"status": RunStatus.COMPLETED}),
                         RunStatus.CANCELLED)

    def test_a_terminal_graph_status_beats_the_record(self) -> None:
        record = self.record(status=RunStatus.WAITING_HOST)
        self.assertEqual(effective_status(record, {"status": RunStatus.PARTIAL}),
                         RunStatus.PARTIAL)

    def test_a_terminal_record_beats_a_non_terminal_graph_status(self) -> None:
        record = self.record(status=RunStatus.BLOCKED)
        self.assertEqual(effective_status(record, {"status": RunStatus.RUNNING}),
                         RunStatus.BLOCKED)

    def test_before_the_first_checkpoint_the_record_status_is_reported(self) -> None:
        record = self.record()
        envelope = build_envelope(record, {}, trace=None, observability=ObservabilityStatus.OK)
        self.assertEqual((envelope.status, envelope.root_task_id), (RunStatus.RUNNING, "task-1"))
        self.assertIsNone(envelope.trace_refs.trace_id)

    def test_a_failed_run_without_an_outcome_still_carries_an_error(self) -> None:
        record = self.record(status=RunStatus.FAILED)
        envelope = build_envelope(record, {}, trace=None, observability=ObservabilityStatus.OK,
                                  diagnostics=["boom"])
        self.assertEqual(envelope.errors[0].code, "failed")
        self.assertIn("boom", envelope.errors[0].message)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:50 [python-coder]: Shell metacharacters are tested as plain data through the
#   same reader the CLI uses, which is the whole of the no-interpolation guarantee.
#   (#KernelBootstrapV0/P7)
# ====================================================================
