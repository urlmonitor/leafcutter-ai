"""
MODULE: test_inf_500d_4_i_no_log_root_writers
GOAL: RED tests for the "--no-log-root leaves the telemetry and knowledge writers
    pointing into the disposable worktree" gap of EPIC-OneDurableLogRootForEveryWorkspace.
AC: INF-500d-4-i (the sink says so rather than quietly using the disposable
    location), INF-500d-4-iv (writers default to the declared root; with no usable
    declaration emit_event warns, names it and writes nothing), INF-400c-4-i and
    INF-400c-4-iii (reopened for exactly this defect); ADR-069 section 4.

THE GAP: ``build_log_root.declaration_values`` with ``--no-log-root`` (what the
    worktree bootstrap passes after a WARNING when it cannot read the main install's
    root) omits only ``operational_log_root`` and ``feedback_sink``. It still records
    ``operational_telemetry_stream`` and ``knowledge_emission_sink`` under
    ``<worktree>/debugging/logs``. ``emit_event.py`` only checks its stream is
    absolute, and ``sink_resolution.py --print-location`` / ``harvest_learnings.py
    --print-sink`` only check their own key, so every writer keeps writing into a
    directory that is deleted after the drive.

CONTRACT THIS FILE FIXES (python-coder implements against exactly this): a stream
    is usable only when the declaration also records an absolute
    ``operational_log_root`` AND the stream sits directly under it. When it is not
    usable:
      * ``emit_event.py`` (no --log): exit 0, stderr WARNING naming
        ``operational_log_root``, nothing written anywhere;
      * ``sink_resolution.py --print-location telemetry|knowledge`` and
        ``harvest_learnings.py --print-sink``: empty stdout, ERROR on stderr naming
        ``operational_log_root``, non-zero exit;
      * an ordinary ``harvest_learnings.py`` run: non-zero exit, nothing created.
    With a full declaration every writer lands under the declared root.

KNOWLEDGE SIDE: the knowledge "writer" is the agent following the four emit
    surfaces, which obtain the sink through ``harvest_learnings.py --print-sink``
    and append there. The tests therefore simulate that literally: run the query,
    and append wherever it prints. INF-400c-4-v's "states it is creating a second
    sink" allowance is for a BARE build that declares a root; ADR-069 section 4 and
    INF-500d-4-i govern ``--no-log-root`` (omit the root, writers refuse), so the
    refusal is what is asserted.

REAL-ARTIFACT NOTE: declarations are produced by the real build helpers (the real
    ``build_knowledge_sink_declaration`` with the real ``build_log_root`` input, then
    ``h.rewrite_declaration`` round-trips); every assertion runs the deployed
    scripts as subprocesses. No build.py is spawned.
"""
# @ac-tag: INF-500d-4-i

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_VARIANTS = ("built_with_no_log_root", "root_entries_dropped", "streams_outside_the_declared_root")


def _enduring(base: Path) -> Path:
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    return root


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _install(base: Path, name: str, *, variant: str | None, log_root: Path) -> tuple[Path, Path, Path]:
    """A worktree-shaped install. ``variant=None`` is the full declaration naming ``log_root``."""
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    if variant is None:
        h.declare(out_root, log_root)
    elif variant == "built_with_no_log_root":
        # EXACTLY what `build.py --no-log-root` (the bootstrap's fallback) records.
        h.build_knowledge_sink_declaration(out_root, {h.CONFIG_KEY: False}, False, True)
    elif variant == "root_entries_dropped":
        h.declare(out_root, log_root)
        h.rewrite_declaration(out_root, operational_log_root=None, feedback_sink=None)
    elif variant == "streams_outside_the_declared_root":
        h.declare(out_root, log_root)
        disposable = project / "debugging" / "logs"
        h.rewrite_declaration(
            out_root,
            operational_telemetry_stream=str(disposable / "agent_telemetry.jsonl"),
            knowledge_emission_sink=str(disposable / "knowledge_emissions.jsonl"),
        )
    else:  # pragma: no cover - guards the parametrisation
        raise AssertionError(variant)
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, cwd


def _emit(out_root: Path, cwd: Path, tmpdir: Path, project: Path):
    script = out_root.parent / ".claude" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
    args = ["--event", "agent_start", "--agent", "ticket-supervisor",
            "--ticket", str(project / "01_t.md"), "--phase", "python-coder"]
    return h.run_py(script, args, cwd, tmpdir)


def _query(out_root: Path, name: str, cwd: Path, tmpdir: Path):
    return h.run_py(out_root / "scripts" / "knowledge" / "sink_resolution.py",
                    ["--print-location", name], cwd, tmpdir)


def _print_sink(out_root: Path, cwd: Path, tmpdir: Path):
    return h.run_py(out_root / "scripts" / "knowledge" / "harvest_learnings.py",
                    ["--print-sink"], cwd, tmpdir)


def _assert_refused(proc, what: str) -> None:
    assert proc.stdout.strip() == "", f"{what} printed a location instead of refusing: {proc.stdout!r}"
    assert proc.returncode != 0, f"{what} exited 0 although no usable enduring root is declared"
    assert "ERROR" in proc.stderr, f"{what} refused without an ERROR on stderr: {proc.stderr!r}"
    assert "operational_log_root" in proc.stderr, (
        f"{what} did not name the missing/unmatched operational_log_root: {proc.stderr!r}")


@pytest.mark.parametrize("variant", _VARIANTS)
def test_emit_event_without_a_usable_root_warns_and_writes_nothing(tmp_path, variant):
    # covers: INF-500d-4-iv
    # covers: INF-500d-4-i
    # covers: INF-400c-4-iii
    # angle: failure
    """Control: a full declaration lands the event under R. Negative: no usable root -> exit 0, WARNING
    naming operational_log_root, and not one file or directory appears anywhere under the worktree or R."""
    tmpdir = _tmpdir(tmp_path)
    good_root = _enduring(tmp_path / "control")
    c_project, c_out, c_cwd = _install(tmp_path / "control", "wt", variant=None, log_root=good_root)
    control = _emit(c_out, c_cwd, tmpdir, c_project)
    assert control.returncode == 0, control.stderr
    assert len(h.read_records(good_root / "agent_telemetry.jsonl")) == 1  # control row passes

    root = _enduring(tmp_path / "negative")
    project, out_root, cwd = _install(tmp_path / "negative", "wt", variant=variant, log_root=root)
    before = h.snapshot(project, root.parent)
    proc = _emit(out_root, cwd, tmpdir, project)
    after = h.snapshot(project, root.parent)

    assert proc.returncode == 0, f"telemetry is best-effort and must still exit 0: {proc.stderr}"
    assert after == before, f"emit_event wrote into the disposable worktree: {sorted(after - before)}"
    assert "WARNING" in proc.stderr, f"no WARNING on stderr: {proc.stderr!r}"
    assert "operational_log_root" in proc.stderr, f"the warning does not name the root: {proc.stderr!r}"


@pytest.mark.parametrize("variant", _VARIANTS)
def test_print_location_telemetry_refuses_instead_of_printing_a_worktree_path(tmp_path, variant):
    # covers: INF-500d-4-i
    # covers: INF-500d-4-iv
    # angle: failure
    """plan-feature.js, the retrospective prompt and the pre-drive check all obtain the stream from this
    query. Control: a full declaration prints R/agent_telemetry.jsonl. Negative: empty stdout + ERROR."""
    tmpdir = _tmpdir(tmp_path)
    good_root = _enduring(tmp_path / "control")
    _c_project, c_out, c_cwd = _install(tmp_path / "control", "wt", variant=None, log_root=good_root)
    control = _query(c_out, "telemetry", c_cwd, tmpdir)
    assert (control.returncode, control.stdout.strip()) == (0, str(good_root / "agent_telemetry.jsonl"))

    root = _enduring(tmp_path / "negative")
    project, out_root, cwd = _install(tmp_path / "negative", "wt", variant=variant, log_root=root)
    before = h.snapshot(project, root.parent)
    proc = _query(out_root, "telemetry", cwd, tmpdir)

    _assert_refused(proc, "--print-location telemetry")
    assert h.snapshot(project, root.parent) == before, "the read-only query created something"


@pytest.mark.parametrize("variant", _VARIANTS)
def test_print_location_knowledge_refuses_instead_of_printing_a_worktree_path(tmp_path, variant):
    # covers: INF-500d-4-i
    # covers: INF-400c-4-i
    # angle: failure
    """The knowledge half of the same query: a stream the declaration does not anchor under a declared root
    is not an answer. Control: full declaration prints R/knowledge_emissions.jsonl."""
    tmpdir = _tmpdir(tmp_path)
    good_root = _enduring(tmp_path / "control")
    _c_project, c_out, c_cwd = _install(tmp_path / "control", "wt", variant=None, log_root=good_root)
    control = _query(c_out, "knowledge", c_cwd, tmpdir)
    assert (control.returncode, control.stdout.strip()) == (0, str(good_root / "knowledge_emissions.jsonl"))

    root = _enduring(tmp_path / "negative")
    project, out_root, cwd = _install(tmp_path / "negative", "wt", variant=variant, log_root=root)
    proc = _query(out_root, "knowledge", cwd, tmpdir)

    _assert_refused(proc, "--print-location knowledge")


@pytest.mark.parametrize("variant", _VARIANTS)
def test_an_agent_following_the_knowledge_surface_cannot_append_into_the_worktree(tmp_path, variant):
    # covers: INF-400c-4-i
    # covers: INF-500d-4-i
    # angle: reachability
    """The four emit surfaces say: run ``harvest_learnings.py --print-sink`` and append there. Do exactly
    that. Control: the record is in R/knowledge_emissions.jsonl and survives the worktree's removal.
    Negative: --print-sink refuses (empty stdout, ERROR), so the agent has nowhere to append and the
    worktree gains no file."""
    tmpdir = _tmpdir(tmp_path)
    record = json.dumps({"event_type": "knowledge_captured", "text": "probe"}) + "\n"

    good_root = _enduring(tmp_path / "control")
    c_project, c_out, c_cwd = _install(tmp_path / "control", "wt", variant=None, log_root=good_root)
    control = _print_sink(c_out, c_cwd, tmpdir)
    assert control.returncode == 0 and control.stdout.strip() == str(good_root / "knowledge_emissions.jsonl")
    with open(control.stdout.strip(), "a", encoding="utf-8") as fh:
        fh.write(record)
    shutil.rmtree(c_project)
    assert (good_root / "knowledge_emissions.jsonl").read_text(encoding="utf-8") == record

    root = _enduring(tmp_path / "negative")
    project, out_root, cwd = _install(tmp_path / "negative", "wt", variant=variant, log_root=root)
    before = h.snapshot(project, root.parent)
    proc = _print_sink(out_root, cwd, tmpdir)
    if proc.returncode == 0 and proc.stdout.strip():  # the agent follows the surface literally
        target = Path(proc.stdout.strip())
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(record)

    assert h.snapshot(project, root.parent) == before, "the agent's append landed in the disposable worktree"
    _assert_refused(proc, "harvest_learnings.py --print-sink")


def test_an_ordinary_harvest_run_refuses_and_creates_nothing_without_a_usable_root(tmp_path):
    # covers: INF-400c-4-iii
    # covers: INF-500d-4-i
    # angle: failure
    """The harvester resolves its default sink from the same declaration. Built with --no-log-root (the
    worktree-local streams are still declared) it must not drain/create state under the worktree's
    debugging/logs: non-zero exit, nothing created anywhere, and the refusal names the missing root.
    (Only the --no-log-root shape is pinned here: with the root entries dropped from an otherwise
    enduring declaration the harvester already refuses, for its own STALE reason.)"""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path / "negative")
    project, out_root, cwd = _install(
        tmp_path / "negative", "wt", variant="built_with_no_log_root", log_root=root)
    before = h.snapshot(project, root.parent)
    proc = h.run_py(out_root / "scripts" / "knowledge" / "harvest_learnings.py", [], cwd, tmpdir)

    assert h.snapshot(project, root.parent) == before, "the harvester created files in the worktree"
    assert proc.returncode != 0, f"harvest ran against the worktree sink: {proc.stdout!r} {proc.stderr!r}"
    assert "operational_log_root" in proc.stdout + proc.stderr, "the refusal does not name the missing root"


def test_with_a_full_declaration_every_writer_lands_under_the_declared_root(tmp_path):
    # covers: INF-500d-4-iv
    # covers: INF-400c-4-iii
    # angle: criterion
    """Positive control for the whole file: telemetry (emit_event), the knowledge append (via --print-sink)
    and both location queries all resolve under R, from the worktree root and a nested directory, and
    nothing appears under the worktree. Guards against a fix that refuses everything."""
    tmpdir = _tmpdir(tmp_path)
    root = _enduring(tmp_path)
    project, out_root, cwd = _install(tmp_path, "wt", variant=None, log_root=root)
    before = h.snapshot(project)

    for where in (project, cwd):
        assert _emit(out_root, where, tmpdir, project).returncode == 0
        sink = _print_sink(out_root, where, tmpdir)
        assert sink.returncode == 0, sink.stderr
        with open(sink.stdout.strip(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event_type": "knowledge_captured"}) + "\n")
        assert _query(out_root, "telemetry", where, tmpdir).stdout.strip() == str(root / "agent_telemetry.jsonl")
        assert _query(out_root, "knowledge", where, tmpdir).stdout.strip() == str(root / "knowledge_emissions.jsonl")

    assert len(h.read_records(root / "agent_telemetry.jsonl")) == 2
    assert len(h.read_records(root / "knowledge_emissions.jsonl")) == 2
    assert h.snapshot(project) == before, "a writer left something in the worktree"
