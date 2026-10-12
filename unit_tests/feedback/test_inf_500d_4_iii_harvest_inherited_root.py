"""
MODULE: test_inf_500d_4_iii_harvest_inherited_root
GOAL: RED tests for "an ordinary harvest in an inherited-root install must drain the
    declared knowledge sink instead of reporting it STALE"
    (EPIC-OneDurableLogRootForEveryWorkspace, follow-up to the INF-500d-4-i gap fix).
AC: INF-500d-4-iii (a worktree inherits the enduring root, so its declared sink lies
    outside the project by design), INF-400c-4-v (a hand-moved install is reported
    STALE, distinctly from a sink never written to; a second sink is announced),
    INF-400c-4 (the sink and its readers agree), INF-500d-4-i (stale means "the
    enduring project root it records no longer exists"); ADR-069 section 3.

THE DEFECT: a real ``build.py --log-root <enduring root outside the project>`` (what
    the worktree bootstrap runs) writes a full declaration. An ordinary
    ``harvest_learnings.py`` run in that install then exits 1 with "Declared
    knowledge-emission sink is STALE", because
    ``sink_resolution.stale_declaration_message`` compares the declared sink with
    ``<project>/debugging/logs/...`` -- a path an inherited root never has. The
    harvester therefore cannot drain an inherited-root sink at all.

WHAT "STALE" MEANS (the contract these tests pin):
    * INF-400c-4-v: a declared path whose directory is no longer there (the install
      was moved by hand), reported distinctly from a sink never written to.
    * INF-500d-4-i: "the enduring project root it records no longer exists".
    The two agree -- both are about the declared location being GONE. Neither says a
    declared location that differs from ``<project>/debugging/logs`` is stale, and
    ADR-069 section 3 makes exactly that difference the designed state of every
    worktree. So: stale = the directory holding the declared ``operational_log_root``
    no longer exists (the log directory itself may be missing on a first write).

REAL-ARTIFACT NOTE: the declaration is written by the real build helper
    (``h.declare`` with a root outside the project); every assertion runs the
    deployed ``harvest_learnings.py`` as a subprocess against records in the
    declared sink. Nothing mocks a write and no build.py is spawned.
"""
# @ac-tag: INF-500d-4-iii

from __future__ import annotations

import json
import re
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h

_TEXTS = ("inherited root learning one", "inherited root learning two")
_EXISTING_NONZERO = {1, 2, 3, 4}


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _harvester(out_root: Path) -> Path:
    return out_root / "scripts" / "knowledge" / "harvest_learnings.py"


def _install(base: Path, *, enduring_exists: bool = True, with_sink: bool = True):
    """A worktree-shaped install whose declaration inherits a root OUTSIDE the project.

    Returns ``(project, out_root, sink, destination)``. ``sink`` holds ``_TEXTS`` as
    real ``knowledge_captured`` records when ``with_sink``; ``destination`` is the
    absolute file the records route to.
    """
    enduring = base / "enduring_project"
    log_root = enduring / "debugging" / "logs"
    if enduring_exists:
        log_root.mkdir(parents=True)
    project = base / "worktree"
    project.mkdir()
    out_root = h.deploy_install(project)
    h.declare(out_root, log_root)
    declared = h.read_declaration(out_root)
    assert declared["operational_log_root"] == str(log_root), "fixture: the real helper must record the inherited root"
    sink = Path(declared["knowledge_emission_sink"])
    assert project not in sink.parents, "fixture: an inherited root puts the sink outside the project"
    destination = base / "surfaces" / "glossary.md"
    if with_sink:
        lines = [
            json.dumps({
                "event": "knowledge_captured", "timestamp": f"2026-10-12T10:0{i}:00Z",
                "agent": "python-coder", "component": "knowledge_system",
                "destination": str(destination), "entry_kind": "glossary",
                "ticket": "tickets/00_inbox/t.md", "text": text,
            })
            for i, text in enumerate(_TEXTS)
        ]
        sink.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return project, out_root, sink, destination


def _harvest(out_root: Path, cwd: Path, tmpdir: Path, *args: str):
    return h.run_py(_harvester(out_root), list(args), cwd, tmpdir)


def _output(proc) -> str:
    return proc.stdout + proc.stderr


def test_ordinary_harvest_in_an_inherited_root_install_drains_the_declared_sink(tmp_path):
    # covers: INF-500d-4-iii
    # covers: INF-400c-4-v
    # angle: reachability
    """From the project root, an ordinary run routes both records out of the inherited-root sink, exit 0,
    never reports STALE, and keeps its processed-state beside the declared sink (not in the worktree)."""
    tmpdir = _tmpdir(tmp_path)
    project, out_root, sink, destination = _install(tmp_path)

    proc = _harvest(out_root, project, tmpdir)

    assert "stale" not in _output(proc).lower(), (
        f"an inherited root is the designed state (ADR-069 section 3), not a stale declaration:\n{_output(proc)}")
    assert proc.returncode == 0, f"an ordinary harvest must drain an inherited-root sink:\n{_output(proc)}"
    assert re.search(r"\b2 learnings routed\b", proc.stdout), f"both records must be routed: {proc.stdout!r}"
    assert destination.read_text(encoding="utf-8").splitlines() == list(_TEXTS), "routing must write each text exactly once"
    assert (sink.parent / "harvest_state.json").is_file(), "the processed-state belongs beside the declared sink"
    assert not (project / "debugging").exists(), "a harvest must not conjure a log directory inside the disposable worktree"


def test_harvest_from_an_isolated_directory_and_from_the_project_root_drain_one_and_the_same_sink(tmp_path):
    # covers: INF-500d-4-iii
    # covers: INF-400c-4-i
    # angle: seam
    """A dry run from an isolated directory sees both records and writes nothing; the real run from there
    routes them; a later run from the project root finds them already processed (one sink, one state)."""
    tmpdir = _tmpdir(tmp_path)
    project, out_root, sink, destination = _install(tmp_path)
    isolated = project / "isolated_working_directory"
    isolated.mkdir()

    dry = _harvest(out_root, isolated, tmpdir, "--dry-run")
    assert dry.returncode == 0, f"dry run from an isolated directory must succeed:\n{_output(dry)}"
    assert re.search(r"\b2 learnings routed\b", dry.stdout), f"the dry run must see the declared sink's records: {dry.stdout!r}"
    assert not destination.exists(), "a dry run writes nothing to a knowledge surface"

    real = _harvest(out_root, isolated, tmpdir)
    assert real.returncode == 0, f"a real run from an isolated directory must drain:\n{_output(real)}"
    assert destination.read_text(encoding="utf-8").splitlines() == list(_TEXTS)

    again = _harvest(out_root, project, tmpdir)
    assert again.returncode == 0, f"{_output(again)}"
    assert re.search(r"\b2 previously processed\b", again.stdout), (
        f"the project root must read the SAME sink and state the isolated run used: {again.stdout!r}")
    assert destination.read_text(encoding="utf-8").splitlines() == list(_TEXTS), "no record may be routed twice"
    assert not (isolated / "debugging").exists() and not (project / "debugging").exists(), (
        "neither working directory may grow a log directory of its own")


def test_an_inherited_root_whose_sink_was_never_written_is_a_no_work_run_not_a_stale_declaration(tmp_path):
    # covers: INF-400c-4-v
    # covers: INF-500d-4-iii
    # angle: boundary
    """Control for the stale test below: the enduring root EXISTS but nothing was ever emitted. That is a
    no-work run (exit 0, never 'stale'), so 'stale' cannot be derived from the sink file being absent."""
    tmpdir = _tmpdir(tmp_path)
    project, out_root, sink, destination = _install(tmp_path, with_sink=False)
    assert not sink.exists()

    proc = _harvest(out_root, project, tmpdir)

    assert "stale" not in _output(proc).lower(), f"a never-written sink under a live root is not stale:\n{_output(proc)}"
    assert proc.returncode == 0, f"a never-written sink is a no-work run:\n{_output(proc)}"
    assert not sink.exists(), "asking must not conjure the sink file"
    assert not destination.exists()

    # Boundary: the enduring PROJECT root exists but the log directory under it was never created
    # (the ordinary first write). Still no-work, not stale -- only a vanished enduring root is stale.
    first_base = tmp_path / "first_write"
    first_base.mkdir()
    f_project, f_out, f_sink, _f_dest = _install(first_base, with_sink=False)
    f_sink.parent.rmdir()
    assert f_sink.parent.parent.is_dir() and not f_sink.parent.exists()
    first = _harvest(f_out, f_project, _tmpdir(first_base))
    assert "stale" not in _output(first).lower(), f"a missing log directory under a live root is a first write:\n{_output(first)}"
    assert first.returncode == 0, _output(first)
    assert not f_sink.exists()


def test_a_declaration_whose_recorded_enduring_root_is_gone_is_still_refused_as_stale(tmp_path):
    # covers: INF-500d-4-i
    # covers: INF-400c-4-v
    # angle: failure
    """The recorded enduring root no longer exists: the ordinary run exits non-zero with an existing status,
    says STALE, names the declared path, and creates nothing (it must not conjure the missing root)."""
    tmpdir = _tmpdir(tmp_path)
    project, out_root, sink, destination = _install(tmp_path, enduring_exists=False, with_sink=False)
    before = h.snapshot(tmp_path)

    proc = _harvest(out_root, project, tmpdir)

    out = _output(proc)
    assert proc.returncode in _EXISTING_NONZERO, f"a stale declaration must reuse an existing non-zero status: {proc.returncode}\n{out}"
    assert "stale" in out.lower(), f"the report must say the declaration went stale:\n{out}"
    assert str(sink) in out, f"the report must name the declared path it could not reach ({sink}):\n{out}"
    assert not (tmp_path / "enduring_project").exists(), "mkdir on the declared location turns a stale install into a healthy-looking empty one"
    assert h.snapshot(tmp_path) == before, "refusing a stale declaration must create nothing anywhere"
    assert not destination.exists()


def test_a_second_sink_is_still_announced_once_naming_both_locations_when_an_inherited_root_is_drained(tmp_path):
    # covers: INF-400c-4-v
    # covers: INF-500d-4-iii
    # angle: failure
    """INF-400c-4-v: where the declared sink differs from where records already accumulate, say so ONCE naming
    both, and never touch the older file. The announcement must not be lost behind the (wrong) STALE refusal."""
    tmpdir = _tmpdir(tmp_path)
    project, out_root, sink, destination = _install(tmp_path)
    legacy = project / "leafcutter-ai" / "debugging" / "logs" / "knowledge_emissions.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"event": "knowledge_captured", "text": "history that stays where it is"}) + "\n",
                      encoding="utf-8")
    legacy_digest = h.sha256(legacy)

    proc = _harvest(out_root, project, tmpdir)

    assert proc.returncode == 0, f"the drain must still succeed beside a legacy file:\n{_output(proc)}"
    notes = [line for line in proc.stdout.splitlines() if line.startswith("NOTE: declared knowledge-emission sink is")]
    assert len(notes) == 1, f"the divergence must be stated exactly once on stdout: {proc.stdout!r}"
    assert str(sink) in notes[0] and str(legacy) in notes[0], f"the note must name both locations: {notes[0]!r}"
    assert h.sha256(legacy) == legacy_digest, "the older file is named, never touched"
    assert destination.read_text(encoding="utf-8").splitlines() == list(_TEXTS)

    # Control: with no older file nothing is announced.
    quiet_base = tmp_path / "quiet"
    quiet_base.mkdir()
    q_project, q_out, _q_sink, _q_dest = _install(quiet_base)
    quiet = _harvest(q_out, q_project, _tmpdir(quiet_base))
    assert quiet.returncode == 0, _output(quiet)
    assert "NOTE: declared knowledge-emission sink" not in quiet.stdout


def test_a_bare_build_into_a_working_directory_still_states_it_is_declaring_a_second_sink(tmp_path):
    # covers: INF-400c-4-v
    # angle: seam
    """INF-400c-4-v build side, in a fresh process: a declaration with no inherited root prints the
    SECOND-sink NOTE; the inherited-root declaration of the tests above is the other branch."""
    tmpdir = _tmpdir(tmp_path)
    out_root = tmp_path / "wt" / ".leafcutter"
    out_root.mkdir(parents=True)
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from pathlib import Path;"
        "from build_phases_knowledge import build_knowledge_sink_declaration as b;"
        "sys.exit(0 if b(Path(sys.argv[2]), {}, False, True) == 1 else 7)"
    )
    proc = h.run_code(code, [str(h.SCRIPTS_DIR), str(out_root)], tmp_path, tmpdir)

    assert proc.returncode == 0, f"the real build helper must declare:\n{_output(proc)}"
    assert "SECOND" in proc.stdout and "sink" in proc.stdout.lower(), (
        f"a build that gives a working directory its own sink must say so: {proc.stdout!r}")
    assert h.read_declaration(out_root)["operational_log_root"] == str(tmp_path / "wt" / "debugging" / "logs")
