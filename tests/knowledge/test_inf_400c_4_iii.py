"""
MODULE: test_inf_400c_4_iii
GOAL: RED test stubs for AC INF-400c-4-iii -- phase telemetry (the
    operational stream) and knowledge emissions must be separate streams,
    and the harvester must drain only its own.
AC: INF-400c-4-iii (source_ac)

FIXTURE AUTHENTICITY (rule 2h.2): ``tests/fixtures/harvest_learnings/
agent_telemetry_33_lines.jsonl`` is a VERBATIM byte-for-byte copy of the
real, on-disk ``debugging/logs/agent_telemetry.jsonl`` (md5-verified against
the live artefact at authoring time: 28 knowledge_captured records with an
``event`` key, 4 pre-drive writability probes with no ``event`` key, and 1
line that is not JSON -- exactly the shape the AC's Given clause describes).
It is read directly with ``Path.read_bytes()``/``read_text()``, never via
``conftest.load_fixture`` (that helper is JSON-only and this artifact, taken
as a whole, is not a single JSON document).

DEPENDS ON: INF-400c-4 (build-time knowledge-sink declaration; largely
    landed in this worktree -- see ``harvest_learnings.py``'s
    ``_resolve_default_sink``/``_read_sink_declaration``/``--print-sink``)
    and INF-400g-2 (``emit_event.py``, the operational-stream emitter,
    which DOES exist in this worktree at
    ``templates/skills/agent-telemetry/scripts/emit_event.py`` despite the
    AC's own it_requirements warning that no record of its shape has ever
    been WRITTEN to the real sink -- the script itself is present; nothing
    has invoked it in production yet).

WHAT IS EXPECTED TO BE RED AND WHY: the harvester already never opens the
    operational stream at all (grep confirms zero references to
    ``agent_telemetry`` anywhere in ``harvest_learnings.py``), so several of
    the "harvester never reaches across" tests below may already be GREEN
    at authoring time -- that is a genuine pre-existing invariant, not
    something to weaken. The clause this AC actually ADDS beyond what
    already exists is the "ONE STREAM ANCHOR, NOT TWO" requirement: the
    operational stream must be reached by the SAME build-time-fixed-anchor
    treatment INF-400c-4 already gives the knowledge sink. Today
    ``emit_event.py --log`` defaults to the bare relative path
    ``debugging/logs/agent_telemetry.jsonl`` with no build-time declaration
    backing it (confirmed by reading the script), so a caller working from
    an isolated working directory writes to a DIFFERENT file than one
    working from the project root. ``TestTwoStreamsPerRepositoryNot...``
    below is written to be genuinely RED against that real gap.

REACHABILITY / SEAM NOTES (BP-1100g-2 / seam angle): every test below drives
    the REAL CLI entry points via subprocess -- ``scripts/knowledge/
    harvest_learnings.py`` and the REAL, self-contained (stdlib-only)
    ``templates/skills/agent-telemetry/scripts/emit_event.py`` -- never an
    in-process import-and-call of an inner helper.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_fixture  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"
_EMIT_EVENT_PATH = (
    _REPO_ROOT / "templates" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
)
_FIXTURE_33_LINES = (
    _REPO_ROOT / "tests" / "fixtures" / "harvest_learnings" / "agent_telemetry_33_lines.jsonl"
)


def _make_event(
    entry_kind: str,
    destination: str,
    ticket: str = "tickets/test.md",
    timestamp: str = "2026-06-05T14:00:00Z",
    agent: str = "python-coder",
    component: str = "knowledge_system",
) -> dict[str, Any]:
    """Return a well-formed knowledge_captured event dict."""
    return {
        "event": "knowledge_captured",
        "timestamp": timestamp,
        "ticket": ticket,
        "agent": agent,
        "component": component,
        "destination": destination,
        "entry_kind": entry_kind,
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _run_harvest_cli(
    sink: Path, state: Path, extra_args: list[str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the real harvester CLI as a subprocess (reachability, not import)."""
    args = [sys.executable, str(_HARVEST_PATH), "--sink", str(sink), "--state", str(state)]
    if extra_args:
        args += extra_args
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=str(cwd) if cwd is not None else None,
    )


def _run_emit_event(
    log_path: Path | None,
    event: str,
    agent: str = "test-agent",
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the real, self-contained emit_event.py CLI as a subprocess.

    When *log_path* is None, the CLI's own default (``--log`` omitted) is
    exercised -- this is deliberate for
    ``TestTwoStreamsPerRepositoryNotTwoStreamsPerWorkingDirectory``, which
    proves the default is NOT anchored to the project root.
    """
    args = [sys.executable, str(_EMIT_EVENT_PATH), "--agent", agent, "--event", event]
    if log_path is not None:
        args += ["--log", str(log_path)]
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=str(cwd) if cwd is not None else None,
    )


class TestHarvesterReportsZeroWhenItsOwnSinkIsEmptyAndTheOperationalStreamIsFull(
    unittest.TestCase
):
    """AC INF-400c-4-iii, test_spec descriptor 1: with the declared sink
    empty and the real 33-line operational stream present and full, the
    harvester must report zero records read and must not touch the
    operational stream at all."""

    def test_harvester_reports_zero_when_its_own_sink_is_empty_and_the_operational_stream_is_full(
        self,
    ) -> None:
        # covers: INF-400c-4-iii
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            operational_stream = tmp / "debugging" / "logs" / "agent_telemetry.jsonl"
            operational_stream.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(_FIXTURE_33_LINES, operational_stream)
            before_digest = hashlib.sha256(operational_stream.read_bytes()).hexdigest()

            declared_sink = tmp / "debugging" / "logs" / "knowledge_emissions.jsonl"
            declared_sink.write_text("", encoding="utf-8")

            proc = _run_harvest_cli(declared_sink, tmp / "state.json")

            report = proc.stdout + proc.stderr
            self.assertEqual(
                proc.returncode,
                0,
                f"a run over an empty declared sink must exit 0; stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}",
            )
            self.assertIn(
                "0 learnings routed",
                report,
                f"must report zero records read from the (empty) declared sink; report={report!r}",
            )
            after_digest = hashlib.sha256(operational_stream.read_bytes()).hexdigest()
            self.assertEqual(
                before_digest,
                after_digest,
                "the full 33-line operational stream must be byte-identical "
                "after this run -- the harvester must never touch it",
            )


class TestHarvesterSucceedsWhileTheOperationalStreamIsUnopenable(unittest.TestCase):
    """AC INF-400c-4-iii, test_spec descriptor 2 -- the no-widening proof
    that cannot pass on a fallback that is never taken. The operational
    stream is replaced with a DIRECTORY (unopenable as a file under any
    user, including root, unlike a chmod 000 file); the harvester must
    still complete and write its one routable record."""

    def test_harvester_succeeds_while_the_operational_stream_is_unopenable(self) -> None:
        # covers: INF-400c-4-iii
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            operational_stream = tmp / "debugging" / "logs" / "agent_telemetry.jsonl"
            operational_stream.mkdir(parents=True)  # a directory, not a file: always unopenable

            destination = tmp / "dest.md"
            declared_sink = tmp / "debugging" / "logs" / "knowledge_emissions.jsonl"
            routable_event = _make_event(entry_kind="adr", destination=str(destination))
            routable_event["text"] = "A genuine learning that must still be written."
            _write_jsonl(declared_sink, [routable_event])

            proc = _run_harvest_cli(declared_sink, tmp / "state.json")

            report = proc.stdout + proc.stderr
            self.assertEqual(
                proc.returncode,
                0,
                "a reader that reaches across to the unopenable operational "
                f"stream at any point fails this test; stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}",
            )
            self.assertIn(
                "1 learnings routed",
                report,
                f"the one routable record must have been routed; report={report!r}",
            )
            self.assertTrue(
                destination.is_file(),
                "the routed record's destination file must have been written",
            )
            self.assertIn(
                "A genuine learning that must still be written.",
                destination.read_text(encoding="utf-8"),
            )


class TestOperationalStreamIsByteIdenticalBeforeAndAfterAHarvestRun(unittest.TestCase):
    """AC INF-400c-4-iii, test_spec descriptor 3: a full harvest run over the
    real 28-record corpus must leave the real 33-line operational stream
    byte-identical -- no drain, no watermark, no rewrite reaches it."""

    def test_operational_stream_is_byte_identical_before_and_after_a_harvest_run(self) -> None:
        # covers: INF-400c-4-iii
        # angle: real_artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            operational_stream = tmp / "debugging" / "logs" / "agent_telemetry.jsonl"
            operational_stream.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(_FIXTURE_33_LINES, operational_stream)
            before_bytes = operational_stream.read_bytes()
            before_digest = hashlib.sha256(before_bytes).hexdigest()

            knowledge_records = load_fixture("harvest_learnings/unroutable_corpus_28")
            self.assertEqual(28, len(knowledge_records), "fixture drift -- expected 28 events")
            declared_sink = tmp / "debugging" / "logs" / "knowledge_emissions.jsonl"
            _write_jsonl(declared_sink, knowledge_records)

            proc = _run_harvest_cli(declared_sink, tmp / "state.json")

            after_bytes = operational_stream.read_bytes()
            after_digest = hashlib.sha256(after_bytes).hexdigest()
            self.assertEqual(
                before_digest,
                after_digest,
                "the operational stream must be byte-identical before and "
                f"after a full harvest run; harvester stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}",
            )
            self.assertEqual(
                33,
                len(after_bytes.splitlines()),
                "line count must be unchanged: nothing moved, filtered, "
                "rotated, archived or rewritten",
            )


class TestAKnowledgeRecordAndAnOperationalRecordLandInDifferentFiles(unittest.TestCase):
    """AC INF-400c-4-iii, test_spec descriptor 4 (seam): the REAL emit_event.py
    producer writes one operational record; a direct append (the documented
    default knowledge-emission path) writes one knowledge record; the REAL
    harvester consumer then reads the knowledge sink. Each file must hold
    only its own kind, and the harvester's observable routing result must
    reflect only the knowledge record."""

    def test_a_knowledge_record_and_an_operational_record_land_in_different_files(self) -> None:
        # covers: INF-400c-4-iii
        # angle: seam
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            declared_sink = tmp / "debugging" / "logs" / "knowledge_emissions.jsonl"
            operational_stream = tmp / "debugging" / "logs" / "agent_telemetry.jsonl"

            destination = tmp / "dest.md"
            knowledge_event = _make_event(entry_kind="adr", destination=str(destination))
            knowledge_event["text"] = "A learning emitted through the declared knowledge path."
            _write_jsonl(declared_sink, [knowledge_event])

            emit_proc = _run_emit_event(
                operational_stream, event="agent_start", agent="ticket-supervisor"
            )
            self.assertEqual(
                emit_proc.returncode,
                0,
                f"emit_event.py must exit 0; stderr={emit_proc.stderr!r}",
            )

            self.assertTrue(declared_sink.is_file())
            self.assertTrue(operational_stream.is_file())

            kn_lines = [
                json.loads(line)
                for line in declared_sink.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            op_lines = [
                json.loads(line)
                for line in operational_stream.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(1, len(kn_lines))
            self.assertEqual(1, len(op_lines))
            self.assertIn("event", kn_lines[0])
            self.assertEqual("knowledge_captured", kn_lines[0]["event"])
            self.assertNotIn(
                "event_type", kn_lines[0], "the knowledge sink must never carry an operational-shaped record"
            )
            self.assertIn("event_type", op_lines[0])
            self.assertEqual("agent_start", op_lines[0]["event_type"])
            self.assertNotIn(
                "entry_kind", op_lines[0], "the operational stream must never carry a knowledge-shaped record"
            )

            # Real consumer half of the seam: the harvester reads the
            # knowledge sink and its result reflects only the knowledge
            # record -- the operational record next to it is invisible to it.
            harvest_proc = _run_harvest_cli(declared_sink, tmp / "state.json")
            report = harvest_proc.stdout + harvest_proc.stderr
            self.assertIn("1 learnings routed", report, f"report={report!r}")
            self.assertTrue(destination.is_file())


class TestTwoStreamsPerRepositoryNotTwoStreamsPerWorkingDirectory(unittest.TestCase):
    """AC INF-400c-4-iii, test_spec descriptor 5 (boundary) -- the clause
    this AC adds on top of INF-400c-4. The knowledge sink is already
    anchored to the project root regardless of caller cwd (via
    config/knowledge_sink.json beside a copy of harvest_learnings.py placed
    at a controlled fake project root). The operational stream's emitter,
    emit_event.py, has NO such anchor today: its --log default is a bare
    relative path resolved against the caller's cwd. This test drives both
    real producers from two different working directories -- the project
    root and an isolated working directory that is then removed -- and
    proves the operational stream fragments while the knowledge stream does
    not, which is the real gap python-coder must close."""

    def test_two_streams_per_repository_not_two_streams_per_working_directory(self) -> None:
        # covers: INF-400c-4-iii
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()

            fake_harvester_dir = proj / "scripts" / "knowledge"
            fake_harvester_dir.mkdir(parents=True)
            fake_harvester = fake_harvester_dir / "harvest_learnings.py"
            shutil.copy(_HARVEST_PATH, fake_harvester)

            declared_knowledge_sink = proj / "debugging" / "logs" / "knowledge_emissions.jsonl"
            config_dir = proj / "config"
            config_dir.mkdir()
            (config_dir / "knowledge_sink.json").write_text(
                json.dumps({"knowledge_emission_sink": str(declared_knowledge_sink)}),
                encoding="utf-8",
            )

            isolated_dir = proj / "isolated_worktree"
            isolated_dir.mkdir()

            operational_stream = proj / "debugging" / "logs" / "agent_telemetry.jsonl"

            root_query = subprocess.run(
                [sys.executable, str(fake_harvester), "--print-sink"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                cwd=str(proj),
            )
            isolated_query = subprocess.run(
                [sys.executable, str(fake_harvester), "--print-sink"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                cwd=str(isolated_dir),
            )
            self.assertEqual(
                root_query.stdout.strip(),
                isolated_query.stdout.strip(),
                "the declared knowledge sink must resolve to the SAME "
                "absolute path regardless of cwd; "
                f"root={root_query.stdout!r} isolated={isolated_query.stdout!r}",
            )

            knowledge_event_root = _make_event(
                entry_kind="adr", destination=str(proj / "kd_root.md")
            )
            knowledge_event_root["text"] = "root learning"
            knowledge_event_isolated = _make_event(
                entry_kind="adr", destination=str(proj / "kd_isolated.md")
            )
            knowledge_event_isolated["text"] = "isolated learning"
            declared_knowledge_sink.parent.mkdir(parents=True, exist_ok=True)
            with open(declared_knowledge_sink, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(knowledge_event_root) + "\n")
                fh.write(json.dumps(knowledge_event_isolated) + "\n")

            root_emit = _run_emit_event(None, event="agent_start", cwd=proj)
            isolated_emit = _run_emit_event(None, event="agent_end", cwd=isolated_dir)
            self.assertEqual(0, root_emit.returncode)
            self.assertEqual(0, isolated_emit.returncode)

            # Count every stream file anywhere under the project BEFORE the
            # isolated working directory is removed -- a per-working-
            # directory operational anchor produces a THIRD file here.
            stream_files = sorted(
                p
                for p in proj.rglob("*.jsonl")
                if p.name in ("agent_telemetry.jsonl", "knowledge_emissions.jsonl")
            )
            self.assertEqual(
                2,
                len(stream_files),
                "exactly one knowledge stream and one operational stream "
                "must exist for the whole project, not one pair per working "
                f"directory; found: {[str(p) for p in stream_files]}",
            )

            shutil.rmtree(isolated_dir)

            self.assertTrue(
                operational_stream.is_file(),
                "the project-root operational stream must exist after the "
                "isolated working directory has been removed",
            )
            op_lines = [
                json.loads(line)
                for line in operational_stream.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            op_event_types = {rec.get("event_type") for rec in op_lines}
            self.assertEqual(
                {"agent_start", "agent_end"},
                op_event_types,
                "the project-root operational stream must hold BOTH the "
                "record emitted from the project root and the record "
                "emitted from the (now-removed) isolated working directory "
                f"-- found only: {op_event_types}",
            )

            kn_lines = [
                json.loads(line)
                for line in declared_knowledge_sink.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(2, len(kn_lines))
            for rec in kn_lines:
                self.assertNotIn("event_type", rec)
            for rec in op_lines:
                self.assertNotIn("entry_kind", rec)


if __name__ == "__main__":
    unittest.main()
