"""
MODULE: test_inf_500d_4_v_extract_epic_facts_default
GOAL: RED tests for the cwd-relative default of ``scripts/retrospective/extract_epic_facts.py``
    (EPIC-OneDurableLogRootForEveryWorkspace, gap 2).
AC: INF-500d-4-v (every telemetry reader's default is the DECLARED stream, states where
    it looked, refuses rather than reporting a false-quiet zero, honours an explicit
    path); ADR-069. extract_epic_facts.py is a telemetry reader, so it falls under
    "EVERY READER'S DEFAULT IS THE DECLARED VALUE" and "NO FALSE-QUIET ZERO".

THE GAP: ``--telemetry`` defaults to the relative ``debugging/logs/agent_telemetry.jsonl``
    and the script silently drops to ``telemetry_events: {}`` when it is absent. The
    retrospective prompt now passes the declared stream, but the script's own default
    must come from the declaration too, or refuse.

CONTRACT THIS FILE FIXES (python-coder implements against exactly this), for the
    DEPLOYED copy at ``<output_root>/scripts/retrospective/extract_epic_facts.py``:
      1. No ``--telemetry``, usable declaration: read ``operational_telemetry_stream``
         from ``<output_root>/config/knowledge_sink.json`` (found relative to the
         script, not the cwd), from any cwd; one stderr line names the absolute file
         it read. The cwd-relative file is never consulted.
      2. No ``--telemetry``, no usable declaration (absent, built with
         ``--no-log-root``, ``operational_log_root`` dropped, stream outside the
         root): non-zero exit, empty stdout (no JSON, so no ``telemetry_events: {}``),
         stderr names the declaration and ``operational_log_root``.
      3. An explicit ``--telemetry`` is honoured as given, whether or not the install
         declares anything, and is the file the stderr line names.

SEAM NOTE (reported, not hand-waved): ``emit_event.py`` writes the ticket under the key
    ``ticket_path`` while ``_read_telemetry`` reads ``ticket``. The seam test below
    pipes the REAL emitter's output into the real reader. It goes red until the reader
    counts what the producer writes; a hand-typed ``ticket`` fixture would hide that.

REAL-ARTIFACT NOTE: declarations come from the real build helpers; telemetry lines in
    the declared stream are written by the REAL ``emit_event.py``; the decoy file in
    the cwd is the only hand-written line. No build.py is spawned.
"""
# @ac-tag: INF-500d-4-v

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_RETRO_SRC = h.REPO_ROOT / "scripts" / "retrospective"
_NO_USABLE_DECLARATION = (
    "absent", "built_with_no_log_root", "root_entries_dropped", "stream_outside_the_declared_root",
)


def _install(base: Path, *, variant: str | None, log_root: Path) -> tuple[Path, Path, Path, Path]:
    """Deploy a worktree-shaped install plus the deployed retrospective script and an epic folder."""
    project = base / "wt"
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    shutil.copytree(_RETRO_SRC, out_root / "scripts" / "retrospective",
                    ignore=shutil.ignore_patterns("__pycache__"))
    if variant is None:
        h.declare(out_root, log_root)
    elif variant == "built_with_no_log_root":
        h.build_knowledge_sink_declaration(out_root, {h.CONFIG_KEY: False}, False, True)
    elif variant == "root_entries_dropped":
        h.declare(out_root, log_root)
        h.rewrite_declaration(out_root, operational_log_root=None, feedback_sink=None)
    elif variant == "stream_outside_the_declared_root":
        h.declare(out_root, log_root)
        h.rewrite_declaration(
            out_root, operational_telemetry_stream=str(project / "debugging" / "logs" / "agent_telemetry.jsonl"))
    elif variant != "absent":  # pragma: no cover - guards the parametrisation
        raise AssertionError(variant)
    epic = project / "tickets" / "00_inbox" / "epics" / "EPIC-Probe"
    epic.mkdir(parents=True)
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, epic, cwd


def _enduring(base: Path) -> Path:
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    return root


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _emit(out_root: Path, cwd: Path, tmpdir: Path, ticket: Path, *extra: str) -> None:
    """File one real telemetry event through the deployed emitter (via the .claude/skills symlink)."""
    script = out_root.parent / ".claude" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
    proc = h.run_py(script, ["--event", "agent_start", "--agent", "ticket-supervisor",
                             "--ticket", str(ticket), "--phase", "python-coder", *extra], cwd, tmpdir)
    assert proc.returncode == 0, proc.stderr


def _extract(out_root: Path, epic: Path, cwd: Path, tmpdir: Path, *args: str):
    return h.run_py(out_root / "scripts" / "retrospective" / "extract_epic_facts.py",
                    [str(epic), *args], cwd, tmpdir)


def _decoy(cwd: Path) -> Path:
    """A cwd-relative stream the buggy default would read: different events, different count."""
    decoy = cwd / "debugging" / "logs" / "agent_telemetry.jsonl"
    decoy.parent.mkdir(parents=True)
    decoy.write_text(
        "".join(json.dumps({"event_type": "decoy_event", "ticket": f"{cwd.parent}/x/{n}.md"}) + "\n"
                for n in range(3)),
        encoding="utf-8")
    return decoy


def test_default_reads_the_declared_stream_and_states_which_file(tmp_path):
    # covers: INF-500d-4-v
    # angle: criterion
    """Declared install, no --telemetry, run from the worktree root AND a nested cwd that holds a decoy
    relative stream: the facts come from the declared stream R/agent_telemetry.jsonl, and stderr names
    that absolute file. The decoy's events never appear."""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path)
    project, out_root, epic, cwd = _install(tmp_path, variant=None, log_root=root)
    _decoy(cwd)
    _emit(out_root, project, tmpdir, epic / "01_t.md")  # real emitter -> the declared stream
    declared = root / "agent_telemetry.jsonl"
    assert len(h.read_records(declared)) == 1

    for where in (project, cwd):
        proc = _extract(out_root, epic, where, tmpdir)
        assert proc.returncode == 0, proc.stderr
        assert str(declared) in proc.stderr, (
            f"extract_epic_facts did not state which telemetry file it read; stderr={proc.stderr!r}")
        events = json.loads(proc.stdout)["telemetry_events"]
        assert "decoy_event" not in events, f"read the cwd-relative file instead of the declared one: {events}"


@pytest.mark.parametrize("variant", _NO_USABLE_DECLARATION)
def test_default_without_a_usable_declaration_refuses_instead_of_reporting_zero(tmp_path, variant):
    # covers: INF-500d-4-v
    # angle: discrimination
    """No --telemetry and no usable declaration -> non-zero exit, nothing on stdout (a printed
    ``telemetry_events: {}`` is the false-quiet zero), stderr naming the declaration and the missing root.
    Wrong versions caught: still defaulting to the cwd-relative file (decoy present, so it would be
    READ and counted); defaulting to the declared stream although it is not under a declared root;
    swallowing the problem and printing an empty result."""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path)
    project, out_root, epic, cwd = _install(tmp_path, variant=variant, log_root=root)
    _decoy(cwd)
    before = h.snapshot(project, root.parent)

    proc = _extract(out_root, epic, cwd, tmpdir)

    assert proc.returncode != 0, f"reported a result with no usable declaration: {proc.stdout!r}"
    assert proc.stdout.strip() == "", f"printed facts (a false-quiet zero) instead of refusing: {proc.stdout!r}"
    assert "knowledge_sink.json" in proc.stderr, f"refusal does not name the declaration: {proc.stderr!r}"
    assert "operational_log_root" in proc.stderr or variant == "absent", (
        f"refusal does not name the missing root: {proc.stderr!r}")
    assert h.snapshot(project, root.parent) == before, "a read-only reader created something"


def test_explicit_telemetry_is_honoured_in_a_declared_install(tmp_path):
    # covers: INF-500d-4-v
    # angle: boundary
    """An explicit --telemetry wins over the declared stream and is the file the stderr line names."""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path)
    project, out_root, epic, cwd = _install(tmp_path, variant=None, log_root=root)
    _emit(out_root, project, tmpdir, epic / "01_t.md")  # one event in the DECLARED stream
    explicit = tmp_path / "explicit" / "events.jsonl"
    explicit.parent.mkdir()
    explicit.write_text(
        "".join(json.dumps({"event_type": "explicit_event", "ticket": f"{epic}/0{n}.md"}) + "\n"
                for n in range(2)),
        encoding="utf-8")

    proc = _extract(out_root, epic, cwd, tmpdir, "--telemetry", str(explicit))

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["telemetry_events"] == {"explicit_event": 2}
    assert str(explicit) in proc.stderr, f"stderr does not name the file it read: {proc.stderr!r}"


@pytest.mark.parametrize("variant", ("absent", "built_with_no_log_root"))
def test_explicit_telemetry_is_honoured_with_no_usable_declaration(tmp_path, variant):
    # covers: INF-500d-4-v
    # angle: boundary
    """INF-500d-4-v: explicit arguments are honoured as given -- the refusal is for the DEFAULT only."""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path)
    _project, out_root, epic, cwd = _install(tmp_path, variant=variant, log_root=root)
    explicit = tmp_path / "explicit.jsonl"
    explicit.write_text(json.dumps({"event_type": "explicit_event", "ticket": f"{epic}/01.md"}) + "\n",
                        encoding="utf-8")

    proc = _extract(out_root, epic, cwd, tmpdir, "--telemetry", str(explicit))

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["telemetry_events"] == {"explicit_event": 1}


def test_real_emitter_events_are_counted_by_the_reader(tmp_path):
    # covers: INF-500d-4-v
    # angle: seam
    """Pipe the REAL emit_event output (default stream, from the declaration) into the REAL reader (default
    stream, from the declaration). Three events for a ticket under the epic and one outside it must be
    counted as exactly {agent_start: 3}. Red today because the emitter writes ``ticket_path`` and the reader
    filters on ``ticket``, so a retrospective always reports zero events from a healthy stream."""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path)
    project, out_root, epic, _cwd = _install(tmp_path, variant=None, log_root=root)
    for n in range(3):
        _emit(out_root, project, tmpdir, epic / f"0{n}_t.md")
    _emit(out_root, project, tmpdir, project / "tickets" / "00_inbox" / "epics" / "EPIC-Other" / "01_t.md")

    proc = _extract(out_root, epic, project, tmpdir)

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["telemetry_events"] == {"agent_start": 3}
