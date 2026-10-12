"""
MODULE: test_inf_500d_4_i_fresh_install
GOAL: RED tests for the review-fix round of EPIC-OneDurableLogRootForEveryWorkspace --
    defects H-1 and H-2: the FIRST write on a freshly installed (ordinary, plain-checkout)
    project, and the writer that conjures a root that is gone.
AC: INF-500d-4-i (the report sink writes to the declared location, and refuses only when the
    enduring location cannot be determined), INF-500d-4-iv (writers default to the declared
    root; with no usable declaration emit_event warns and writes nothing), INF-400c-4-v (a
    declaration whose location is gone is STALE, distinct from a stream never written to);
    ADR-069.

THE DEFECTS THIS FILE PINS
    H-1  An ORDINARY build records ``<project>/debugging/logs`` but never creates
         ``<project>/debugging``. ``feedback_sink._failure`` refuses unless ``sink.parent`` or
         ``sink.parent.parent`` exists, so on a fresh install the first ``submit_feedback``
         exits 1 "stale". ``sink_resolution.enduring_root_exists`` calls the very same state
         live -- the two copies of "is the enduring root gone?" disagree. The probe the epic
         runbooks run before a drive reports "unreachable" for it too.
    H-2  ``emit_event.py`` does ``log_path.parent.mkdir(parents=True)`` and applies no
         staleness check, so a declaration whose project is gone is quietly turned back into a
         healthy-looking empty tree.

WHAT "LIVE" AND "GONE" MEAN (one rule, three copies): the directory holding the declared
    ``operational_log_root`` -- its parent, or the project above ``debugging`` for the
    conventional layout -- exists. Only that is live. A missing log directory (or a missing
    ``debugging``) under a live project is a FIRST WRITE; a vanished project is STALE.

REAL-ARTIFACT NOTE: every run is the REAL deployed script as a subprocess in a temp deployed
    layout; the declaration is written by the real build helper (``h.declare`` with no root is an
    ordinary build). The reachability probe is lifted from the DEPLOYED building-epics and
    epic-supervisor prompts in the shared reference layout and run with ``bash -c``. No
    build.py is spawned and nothing mocks a write.
"""
# @ac-tag: INF-500d-4-i
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback import _inf_500d_4_vi_helpers as vh


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _fresh_install(base: Path, name: str = "wt") -> tuple[Path, Path, Path, Path]:
    """A project declared the way an ORDINARY build declares it, with nothing under ``debugging`` yet.

    Returns ``(project, out_root, cwd, log_root)``.
    """
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    h.declare(out_root)  # no log_root: an ordinary build records <project>/debugging/logs
    log_root = Path(h.read_declaration(out_root)["operational_log_root"])
    assert log_root == project / "debugging" / "logs", "fixture: the real helper must record the conventional root"
    assert not (project / "debugging").exists(), "fixture: an ordinary build creates no debugging directory"
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, cwd, log_root


def _gone_install(base: Path, name: str = "wt") -> tuple[Path, Path, Path, Path]:
    """An install whose declaration names a project that no longer exists. Returns the same four paths."""
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    log_root = base / "vanished_project" / "debugging" / "logs"
    h.declare(out_root, log_root)
    assert not log_root.parent.parent.exists(), "fixture: the declared project must be gone"
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, cwd, log_root


# ---------------------------------------------------------------------------
# H-1: the first write on a fresh install
# ---------------------------------------------------------------------------

def test_first_report_on_a_fresh_install_lands_in_the_declared_sink(tmp_path):
    # covers: INF-500d-4-i
    # angle: criterion
    """submit_feedback on a declared fresh install (project exists, `debugging/` absent) exits 0 and writes the
    declared sink, creating only the missing log directories beneath the live project."""
    project, out_root, cwd, log_root = _fresh_install(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    before = h.snapshot(project)

    proc = h.submit(out_root, cwd, tmpdir)

    assert proc.returncode == 0, (
        f"the first write of an ordinary install was refused (feedback_sink treats a missing `debugging` as a "
        f"vanished root):\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}")
    sink = log_root / "feedback.jsonl"
    assert sink.is_file(), f"nothing was written to the declared sink {sink}"
    assert [r["feedback_id"] for r in h.read_records(sink)] == [proc.stdout.strip()]
    created = h.snapshot(project) - before
    assert created == {str(project / "debugging"), str(log_root), str(sink)}, (
        f"only the missing log directories and the sink may appear, nothing else: {sorted(created)}")


def test_a_gone_project_is_still_refused_while_the_fresh_install_is_not(tmp_path):
    # covers: INF-500d-4-i
    # angle: discrimination
    """Wrong version this catches: 'fix' H-1 by deleting the existence check. The fresh install writes AND the
    vanished project is refused with nothing created, through the same entry point."""
    fresh_project, fresh_out, fresh_cwd, fresh_root = _fresh_install(tmp_path, "fresh")
    gone_project, gone_out, gone_cwd, gone_root = _gone_install(tmp_path, "gone")
    tmpdir = _tmpdir(tmp_path)

    fresh = h.submit(fresh_out, fresh_cwd, tmpdir)
    assert fresh.returncode == 0, f"the fresh install must accept its first write: {fresh.stderr!r}"

    before = h.snapshot(tmp_path)
    refused = h.submit(gone_out, gone_cwd, tmpdir)
    assert refused.returncode != 0, f"a vanished project must be refused: stdout={refused.stdout!r}"
    assert refused.stdout == ""
    assert re.search(r"no longer exists|does not exist", h.without_paths(refused.stderr, tmp_path), re.IGNORECASE), (
        f"the refusal must say the enduring root is gone: {refused.stderr!r}")
    assert h.snapshot(tmp_path) == before, "a refused write must create nothing anywhere"
    assert not gone_root.parent.parent.exists(), "the writer conjured the vanished project"


def test_first_telemetry_event_on_a_fresh_install_lands_in_the_declared_stream(tmp_path):
    # covers: INF-500d-4-iv
    # angle: criterion
    """emit_event on a declared fresh install writes the declared stream. (Green today -- emit_event makes its
    parents -- and kept so that the H-2 staleness fix cannot copy H-1's too-strict existence check into it.)"""
    project, out_root, _cwd, log_root = _fresh_install(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    before = h.snapshot(project)

    proc = h.run_py(h.emit_script(out_root), h.emit_args(), project, tmpdir)

    assert proc.returncode == 0, proc.stderr
    stream = log_root / "agent_telemetry.jsonl"
    assert stream.is_file(), f"the first event of a fresh install was dropped: stderr={proc.stderr!r}"
    assert [r["event_type"] for r in h.read_records(stream)] == ["agent_start"]
    created = h.snapshot(project) - before
    assert created == {str(project / "debugging"), str(log_root), str(stream)}, sorted(created)


# ---------------------------------------------------------------------------
# H-1: the two copies of "is the enduring root gone?" must agree
# ---------------------------------------------------------------------------

_LIVENESS_PROBE = """
import json, sys
from pathlib import Path
cases = json.loads(sys.argv[2])
first = Path(sys.argv[1])
sys.path.insert(0, str(first / "scripts" / "knowledge"))
sys.path.insert(0, str(first / "scripts" / "feedback"))
import sink_resolution
import feedback_sink
result = {}
for name, root in cases.items():
    out = Path(root)
    sink, why = feedback_sink.resolve_feedback_sink(out)
    result[name] = {
        "sink_resolution_live": sink_resolution.enduring_root_exists(out),
        "feedback_sink_live": sink is not None,
        "feedback_sink_refusal": why,
    }
print(json.dumps(result))
"""

# name -> (declared root relative to the temp base, directories that exist beforehand, expected "live")
_LIVENESS_CASES = {
    "fresh_conventional": ("live_a/debugging/logs", ["live_a"], True),
    "conventional_with_debugging_only": ("live_b/debugging/logs", ["live_b/debugging"], True),
    "conventional_fully_present": ("live_c/debugging/logs", ["live_c/debugging/logs"], True),
    "flat_root_log_dir_missing": ("live_d/logs", ["live_d"], True),
    "conventional_project_gone": ("gone_e/debugging/logs", [], False),
    "flat_root_project_gone": ("gone_f/logs", [], False),
}


def test_the_two_copies_of_the_enduring_root_check_agree_on_every_layout(tmp_path):
    # covers: INF-500d-4-i
    # covers: INF-400c-4-v
    # angle: seam
    """sink_resolution.enduring_root_exists (the harvester's rule) and feedback_sink's check (the report writer's
    rule) are fed the same declarations in a fresh process: they must agree, and exactly the layouts whose
    project exists are live. The exact expectations keep the table from agreeing vacuously."""
    tmpdir = _tmpdir(tmp_path)
    installs: dict[str, Path] = {}
    for name, (root_rel, existing, _live) in _LIVENESS_CASES.items():
        for rel in existing:
            (tmp_path / rel).mkdir(parents=True)
        project = tmp_path / f"install_{name}"
        project.mkdir()
        installs[name] = h.deploy_install(project)
        h.declare(installs[name], tmp_path / root_rel)

    first = next(iter(installs.values()))
    proc = h.run_code(_LIVENESS_PROBE, [str(first), json.dumps({k: str(v) for k, v in installs.items()})], tmp_path, tmpdir)
    assert proc.returncode == 0, f"the probe could not load both deployed copies in a fresh process:\n{proc.stderr}"
    verdicts = json.loads(proc.stdout)
    assert set(verdicts) == set(_LIVENESS_CASES) and len(verdicts) == 6

    disagree = {n: v for n, v in verdicts.items() if v["sink_resolution_live"] != v["feedback_sink_live"]}
    assert not disagree, (
        "the harvester and the report writer disagree about whether the enduring root exists:\n"
        + json.dumps(disagree, indent=2))
    wrong = {n: (v["sink_resolution_live"], _LIVENESS_CASES[n][2]) for n, v in verdicts.items()
             if v["sink_resolution_live"] != _LIVENESS_CASES[n][2]}
    assert not wrong, f"(got, expected) liveness differs for: {wrong}"


# ---------------------------------------------------------------------------
# H-1: the pre-drive probe
# ---------------------------------------------------------------------------

def _probe_blocks(prompts: dict[str, str]) -> list[tuple[str, str]]:
    """Every fenced block of building-epics and epic-supervisor that carries the reachability probe marker."""
    marker = "pre-drive-reachability-check"
    blocks: list[tuple[str, str]] = []
    for surface in ("building-epics", "epic-supervisor"):
        fence, current = False, []
        for line in prompts[surface].splitlines():
            if line.strip().startswith("```"):
                if fence and marker in "\n".join(current):
                    blocks.append((surface, "\n".join(current)))
                fence, current = not fence, []
            elif fence:
                current.append(line)
    return blocks


def _probe(body: str, project: Path, tmpdir: Path) -> str:
    """Run a lifted probe block from the worktree root, then print the SINK_OK variable it sets."""
    proc = vh._shell(body + '\necho "SINK_OK=${SINK_OK}"', project, tmpdir)
    return proc.stdout


@pytest.mark.shared_layout_reader
def test_the_predrive_probe_is_not_unreachable_when_only_the_log_directory_is_missing(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-i
    # angle: reachability
    """The probe lifted from the deployed prompts, run verbatim against a fresh install, says OK and creates
    nothing; against a vanished project or no declaration it still says unreachable (the control)."""
    blocks = _probe_blocks(vh._declared_prompts(shared_reference_layout))
    assert {s for s, _ in blocks} == {"building-epics", "epic-supervisor"}, (
        f"both runbooks must still carry the probe: {[s for s, _ in blocks]}")

    tmpdir = _tmpdir(tmp_path)
    breaches = []
    for index, (surface, body) in enumerate(blocks):
        fresh_project, _out, _cwd, _root = _fresh_install(tmp_path, f"fresh_{index}")
        before = h.snapshot(fresh_project)
        out = _probe(body, fresh_project, tmpdir)
        if "SINK_OK=1" not in out or "unreachable" in out.lower():
            breaches.append(f"{surface}: a fresh install (only the log directory missing) reads as unreachable: {out!r}")
        if h.snapshot(fresh_project) != before:
            breaches.append(f"{surface}: the read-only probe created {sorted(h.snapshot(fresh_project) - before)}")

        gone_project, _gout, _gcwd, _groot = _gone_install(tmp_path, f"gone_{index}")
        out = _probe(body, gone_project, tmpdir)
        if "SINK_OK=0" not in out:
            breaches.append(f"{surface}: a vanished project must still read as unreachable: {out!r}")

        bare = tmp_path / f"undeclared_{index}"
        bare.mkdir()
        h.deploy_install(bare)
        out = _probe(body, bare, tmpdir)
        if "SINK_OK=0" not in out:
            breaches.append(f"{surface}: an undeclared install must still read as unreachable: {out!r}")
    assert not breaches, "\n  ".join(["the pre-drive reachability probe:", *breaches])


# ---------------------------------------------------------------------------
# H-2: emit_event must not conjure a root
# ---------------------------------------------------------------------------

def test_emit_event_does_not_conjure_a_root_whose_project_is_gone(tmp_path):
    # covers: INF-500d-4-iv
    # covers: INF-400c-4-v
    # angle: failure
    """A declared root whose project dir is gone: emit_event exits 0 (telemetry is best-effort), warns naming the
    declaration, writes nothing and creates no directory anywhere; the live-but-empty install still writes."""
    project, out_root, _cwd, log_root = _gone_install(tmp_path, "gone")
    tmpdir = _tmpdir(tmp_path)
    before = h.snapshot(tmp_path)

    proc = h.run_py(h.emit_script(out_root), h.emit_args(), project, tmpdir)

    assert proc.returncode == 0, "telemetry stays non-fatal (BP-400a-1-i)"
    assert str(h.declaration_path(out_root)) in proc.stderr, f"the warning must name the declaration: {proc.stderr!r}"
    assert re.search(r"stale|no longer exists|does not exist|gone", h.without_paths(proc.stderr, tmp_path), re.IGNORECASE), (
        f"the warning must say WHY the declaration is unusable (the project is gone): {proc.stderr!r}")
    created = h.snapshot(tmp_path) - before
    assert not created, f"emit_event conjured a vanished root (mkdir parents=True): {sorted(created)}"
    assert not log_root.parent.parent.exists()

    # Control: the same entry point on a live-but-empty install (project exists, `debugging` does not) writes,
    # so the silence above is the vanished project's doing and not a blanket refusal.
    live_project, live_out, _lcwd, live_root = _fresh_install(tmp_path, "live")
    ok = h.run_py(h.emit_script(live_out), h.emit_args(), live_project, tmpdir)
    assert ok.returncode == 0, ok.stderr
    assert len(h.read_records(live_root / "agent_telemetry.jsonl")) == 1, f"the live install dropped its event: {ok.stderr!r}"

    # An explicit --log is the caller's own responsibility and is still honoured on the vanished install.
    explicit = tmp_path / "explicit" / "agent_telemetry.jsonl"
    forced = h.run_py(h.emit_script(out_root), [*h.emit_args(), "--log", str(explicit)], project, tmpdir)
    assert forced.returncode == 0
    assert len(h.read_records(explicit)) == 1


def test_a_live_project_accepts_telemetry_for_both_declared_root_shapes(tmp_path):
    # covers: INF-500d-4-iv
    # angle: boundary
    """Boundary of the vanished-project rule (green today, kept as its guard): a live project accepts an event for
    the conventional `<project>/debugging/logs` root and for a flat `<enduring>/logs` root alike."""
    base_a = tmp_path / "conv"
    base_a.mkdir()
    base_b = tmp_path / "flat"
    base_b.mkdir()
    conv_project, conv_out, _c1, conv_root = _fresh_install(base_a)

    flat_project = base_b / "wt"
    flat_project.mkdir()
    flat_out = h.deploy_install(flat_project)
    flat_live = base_b / "live_flat"
    flat_live.mkdir()
    h.declare(flat_out, flat_live / "logs")
    tmpdir = _tmpdir(tmp_path)

    for label, project, out_root, stream in (
        ("conventional", conv_project, conv_out, conv_root / "agent_telemetry.jsonl"),
        ("flat", flat_project, flat_out, flat_live / "logs" / "agent_telemetry.jsonl"),
    ):
        proc = h.run_py(h.emit_script(out_root), h.emit_args(), project, tmpdir)
        assert proc.returncode == 0, f"{label}: {proc.stderr!r}"
        assert [json.loads(line)["event_type"] for line in stream.read_text(encoding="utf-8").splitlines()] == ["agent_start"], (
            f"{label}: the event must land at the declared stream: {proc.stderr!r}")
