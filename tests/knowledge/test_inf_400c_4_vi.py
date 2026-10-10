"""
MODULE: test_inf_400c_4_vi
GOAL: Prove the harvester's default ``--state`` (and so its default
    ``--marker``) is anchored beside the RESOLVED sink, never to the process's
    working directory.
BUSINESS CONTEXT: A cwd-relative state default dropped a gitignored file into
    the package root whenever a run routed an event from there, and build.py's
    closure guard (AC BP-900g-8) then aborted every later build. See
    docs/known-issues/knowledge-management/open-high-ki-km-20261008-harvest-state-default-is-cwd-relative.md.
ARCHITECTURE: Behavioural tests that run the deployed harvester as a real
    subprocess from a working directory that is NOT the sink's directory,
    plus one source scan for the literal the closure guard would read. All
    files live under pytest ``tmp_path``; no build.py is spawned.
AC: INF-400c-4-vi (source_ac)
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _inf_400c_4_helpers import (  # noqa: E402
    _KNOWLEDGE_SRC_DIR,
    _TIMEOUT_SECONDS,
    _deploy_harvester,
    _write_declaration,
)

_STATE_NAME = "harvest_state.json"
_MARKER_NAME = "harvest_last_run.json"


def _install(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Return (harvester, sink, declared_dir, cwd) for a built-style install."""
    project_root = tmp_path / "project"
    deployed_root = project_root / "install"
    harvester = _deploy_harvester(deployed_root)
    # The routing vocabulary is loaded lazily by the harvester, so the shared
    # helper's required-sibling list does not carry it.
    shutil.copy2(
        _KNOWLEDGE_SRC_DIR / "entry_kind_vocabulary.py", harvester.parent
    )
    # Same layout a real build declares: <project_root>/debugging/logs/.
    declared_dir = project_root / "debugging" / "logs"
    sink = declared_dir / "knowledge_emissions.jsonl"
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=str(sink),
        operational_telemetry_stream=str(declared_dir / "agent_telemetry.jsonl"),
    )
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    return harvester, sink, declared_dir, cwd


def _write_routable_event(sink: Path, destination: Path) -> None:
    sink.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "knowledge_captured",
        "timestamp": "2026-10-08T10:00:00Z",
        "agent": "test-agent",
        "component": "test-component",
        "destination": str(destination),
        "entry_kind": "adr",
        "text": "A real learning about anchoring defaults.",
    }
    sink.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _run(harvester: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(harvester), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
        cwd=str(cwd),
    )


def test_default_state_and_marker_land_beside_the_resolved_sink_not_in_cwd(tmp_path):
    # covers: INF-400c-4-vi
    harvester, sink, declared_dir, cwd = _install(tmp_path)
    _write_routable_event(sink, tmp_path / "memory" / "x.md")

    proc = _run(harvester, cwd)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (declared_dir / _STATE_NAME).is_file(), proc.stdout + proc.stderr
    assert (declared_dir / _MARKER_NAME).is_file()
    assert list(cwd.iterdir()) == [], f"harvester wrote into cwd: {list(cwd.rglob('*'))}"


def test_explicit_state_still_wins_over_the_sink_anchored_default(tmp_path):
    # covers: INF-400c-4-vi
    harvester, sink, declared_dir, cwd = _install(tmp_path)
    _write_routable_event(sink, tmp_path / "memory" / "x.md")
    explicit = tmp_path / "chosen" / "my_state.json"

    proc = _run(harvester, cwd, "--state", str(explicit))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert explicit.is_file()
    assert (explicit.parent / _MARKER_NAME).is_file()
    assert not (declared_dir / _STATE_NAME).exists()
    assert list(cwd.iterdir()) == []


def test_status_creates_nothing_and_exits_zero_without_state(tmp_path):
    # covers: INF-400c-4-vi
    harvester, sink, declared_dir, cwd = _install(tmp_path)

    proc = _run(harvester, cwd, "--status")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["last_run"] == "never-run"
    assert list(cwd.iterdir()) == []
    assert not declared_dir.exists()


def test_no_directory_qualified_state_or_marker_literal_remains_in_knowledge_scripts():
    # covers: INF-400c-4-vi
    # build.py's closure guard reads path literals out of deployed scripts, so
    # any "dir/harvest_state.json" string constant (docstrings included) is a
    # latent undeployed-dependency report the moment such a file exists.
    offenders: list[str] = []
    for source in sorted(_KNOWLEDGE_SRC_DIR.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            for name in (_STATE_NAME, _MARKER_NAME):
                if f"/{name}" in node.value:
                    offenders.append(f"{source.name}: {node.value[:80]!r}")
    assert offenders == []
