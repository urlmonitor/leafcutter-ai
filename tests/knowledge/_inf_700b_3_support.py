"""
MODULE: _inf_700b_3_support
GOAL: Helpers for tests/knowledge/test_inf_700b_3.py -- the capture-health report (AC INF-700b-3).
    Fixture records come from the REAL producer (``emit_event.build_record``, loaded by file path) and are
    serialised with ``json.dumps``; the historic garbage lines (probe, bare fragment, truncated JSON) are
    the only literals, because no producer writes them any more.
INTERFACE UNDER TEST (ADR-034 Amendment 3): ``health/capture_health_report.py --since S --until U [--stream PATH]``
    prints ``attempts=N recorded=R nothing-to-record=X failed=F`` / ``malformed=M unrecognised=U`` figures,
    one ``verdict: <name>`` line and one ``missing-target: <text>`` line per distinct missing target.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from tests.knowledge.test_inf_700b_1_emit_helper import _project, _run  # noqa: F401  (re-exported)
from tests.knowledge.test_inf_700b_1_i import _EVENT_REL, _stream  # noqa: F401  (re-exported)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "knowledge" / "health" / "capture_health_report.py"
DEPLOY_MODULE = REPO_ROOT / "scripts" / "build_phases_knowledge.py"
_EMIT_SOURCE = REPO_ROOT / "templates" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
SCRIPT_NAME = "capture_health_report.py"
DEPLOY_ENTRY = "health/" + SCRIPT_NAME  # the sub-path both deploy lists carry (folder-density)
TARGET = "skills/knowledge/emit_knowledge.py"

NOTHING = "nothing-to-record"
BROKEN = "capture-path-broken"
NO_RUN = "no-run-reached-the-step"
RECORDED = "learnings-recorded"
FORBIDDEN_WORDS = ("backlog", "skipped_unknown", "unroutable_by_kind", "write_failures", "state_persist_failed")


def _build_record():
    spec = importlib.util.spec_from_file_location("_emit_event_for_inf_700b_3", _EMIT_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_record


_BUILD = _build_record()


def attempt_record(outcome: str, ts: str | None, *, target: str | None = None, agent: str = "test-writer",
                   ticket: str | None = "tickets/TICKET-fixture.md") -> dict:
    """One ``capture_attempt`` record, shaped by the real ``emit_event.build_record``."""
    return _BUILD(event="capture_attempt", agent=agent, ticket=ticket, phase="knowledge-capture",
                  outcome=outcome, missing_target=target, timestamp=ts)


def attempt(outcome: str, ts: str, *, target: str | None = None) -> str:
    return json.dumps(attempt_record(outcome, ts, target=target))


def keyless(ts: str, outcome: str = NOTHING) -> str:
    """A record written before A2.2: the payload has NO ``missing_target`` key."""
    record = attempt_record(outcome, ts)
    del record["payload"]["missing_target"]
    return json.dumps(record)


def write_stream(path: Path, lines: list[str]) -> Path:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def mixed_stream_lines() -> list[str]:
    """Frozen stream shaped like the live one plus the historic garbage (period 2026-10-21..2026-10-24)."""
    other = _BUILD(event="agent_start", agent="ticket-supervisor", timestamp="2026-09-21T09:00:00+00:00")
    legacy = {"event": "knowledge_captured", "timestamp": "2026-10-22T09:00:00+00:00", "agent": "x", "text": "t"}
    return [
        "</content>", json.dumps({"probe": "pre-drive-check"}), json.dumps(other), json.dumps(legacy),
        attempt("recorded", "2026-10-21T10:00:00+00:00"), keyless("2026-10-21T12:18:57+00:00"),
        '{"event_type": "capture_attempt", "timestamp": "2026-10-22T0', "[]", '"x"', "7", "",
        attempt("nothing-to-record", "2026-10-22T11:00:00+00:00"),
        attempt("failed", "2026-10-22T12:00:00+00:00", target=TARGET),
        attempt("weird-outcome", "2026-10-22T13:00:00+00:00"),
        attempt("nothing-to-record", "not-a-date"),
        attempt("nothing-to-record", "2026-10-23T08:00:00+00:00"),
        attempt("failed", "2026-09-01T00:00:00+00:00", target="out/of/window.py"),
    ]


def run_report(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run *script* as a subprocess; an absent script is the absence red, said plainly."""
    assert script.is_file(), f"{SCRIPT_NAME} does not exist at {script}"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", str(script), *args], capture_output=True, text=True,
                          cwd=str(cwd), timeout=60, check=False, env=env)


def source_report(stream: Path, since: str, until: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return run_report(SOURCE_SCRIPT, "--since", since, "--until", until, "--stream", str(stream), cwd=cwd)


def figures(stdout: str) -> dict[str, int]:
    return {k: int(v) for k, v in re.findall(r"\b([a-z][a-z-]*)=(\d+)\b", stdout)}


def verdict(stdout: str) -> str | None:
    found = re.search(r"^verdict: (\S+)$", stdout, re.MULTILINE)
    return found.group(1) if found else None


def assert_period(out: subprocess.CompletedProcess[str], expected: tuple[int, int, int, int], name: str) -> None:
    """Exit 0, the four period figures exactly (all printed, zeros included), and the one verdict."""
    assert out.returncode == 0, out
    got = figures(out.stdout)
    keys = ("attempts", "recorded", "nothing-to-record", "failed")
    assert tuple(got.get(k) for k in keys) == expected, (got, out.stdout)
    assert got["attempts"] == got["recorded"] + got["nothing-to-record"] + got["failed"]
    assert verdict(out.stdout) == name, out.stdout


def emit_attempt(proj: dict[str, Path], tmp_path: Path, outcome: str, *extra: str) -> None:
    """Write one attempt with the REAL deployed emit_event.py (declared stream, no --log)."""
    argv = [sys.executable, "-B", str(proj["deployed"] / _EVENT_REL), "--event", "capture_attempt",
            "--agent", "test-writer", "--phase", "knowledge-capture", "--outcome", outcome, *extra]
    done = _run(argv, proj["project"], tmp_path)
    assert done.returncode == 0 and done.stderr == "", done


def deployed_script(proj: dict[str, Path]) -> Path:
    return proj["deployed"] / "scripts" / "knowledge" / "health" / SCRIPT_NAME


def redeclare_stream_elsewhere(proj: dict[str, Path]) -> None:
    """Round-trip the copy's declaration, moving the telemetry stream out from under the log root."""
    path = proj["deployed"] / "config" / "knowledge_sink.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["operational_telemetry_stream"] = str(proj["world"] / "elsewhere" / "agent_telemetry.jsonl")
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def harvester_imports(source: str) -> list[str]:
    """Every import (static or by string to a loader call) that names ``harvest_learnings``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if "harvest_learnings" in a.name]
        elif isinstance(node, ast.ImportFrom):
            if "harvest_learnings" in (node.module or "") or any("harvest_learnings" in a.name for a in node.names):
                found.append(node.module or "")
        elif isinstance(node, ast.Call):
            found += [a.value for a in node.args if isinstance(a, ast.Constant)
                      and isinstance(a.value, str) and "harvest_learnings" in a.value]
    return found


def deploy_list_entries(function: str) -> set[str]:
    """String elements of every list/tuple literal inside *function* (docstrings are NOT counted)."""
    tree = ast.parse(DEPLOY_MODULE.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    return {e.value for seq in ast.walk(node) if isinstance(seq, (ast.List, ast.Tuple))
            for e in seq.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
