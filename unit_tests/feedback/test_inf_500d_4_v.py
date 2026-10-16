"""
MODULE: test_inf_500d_4_v
GOAL: RED tests for AC INF-500d-4-v -- whoever reads the reports afterwards
    finds every drive's reports in one place, and the reader says which file it
    read and how many records it found.
AC: INF-500d-4-v (source_ac); depends on INF-500d-4-iii (declaration, ADR-069).

CONTRACT THIS FILE FIXES (python-coder implements against exactly this):

    1. With no explicit path argument, ``aggregate.py``, ``list_tags.py``,
       ``trend_report.py``, ``link_feedback.py`` and ``resolve_feedback.py`` use
       ``feedback_sink``; ``generate_health_report.py`` uses ``feedback_sink`` and
       ``operational_telemetry_stream``, all from the deployed workspace's own
       ``<output_root>/config/knowledge_sink.json``. The ``parents[3]`` defaults,
       the ``_find_project_root`` walk, trend_report's upward search and the
       health report's CWD-relative defaults are gone.
    2. Each reader prints ONE stderr line naming the absolute file it read and
       the number of records it found (KI-FC-001); stdout formats are unchanged.
    3. ``link_feedback.py`` / ``resolve_feedback.py`` rewrite the declared sink
       under the same exclusive ``flock`` ``submit_feedback.py`` takes, for the
       whole read-modify-write, so a concurrent append is not lost.
    4. A populated pre-declaration ``<output_root>/debugging/logs/feedback.jsonl``
       that differs from the declared sink is NAMED once (both paths), never
       merged, copied, moved or deleted.
    5. With no usable declaration and no explicit path a reader exits non-zero
       naming the expected declaration; it never reports an empty result.
    6. Read-only readers create no file or directory.

REAL-ARTIFACT NOTE: every record in every fixture sink is written by the REAL
    ``submit_feedback.py`` (feedback) or the REAL ``emit_agent_telemetry``
    (telemetry); the declaration comes from the real build helper; every reader
    is the REAL deployed script run as a subprocess from a worktree's current
    directory with decoy sinks seeded where the old defaults would find them. No
    build.py is spawned.
"""
# @ac-tag: INF-500d-4-v

from __future__ import annotations

import fcntl
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_TELEMETRY_DRIVER = (
    "import importlib.util, sys\n"
    "from pathlib import Path\n"
    "spec = importlib.util.spec_from_file_location('agent_telemetry', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "sys.modules['agent_telemetry'] = m\n"
    "spec.loader.exec_module(m)\n"
    "for _ in range(int(sys.argv[3])):\n"
    "    m.emit_agent_telemetry({'lane': 'fast', 'agent': sys.argv[4], 'duration_ms': 100,\n"
    "                            'tokens_in': 1, 'tokens_out': 1, 'cache_read_tokens': 0,\n"
    "                            'status': 'ok'}, sink_path=Path(sys.argv[2]))\n"
)


def _worktree(base: Path, name: str, *, log_root: Path | None) -> tuple[Path, Path, Path]:
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    if log_root is not None:
        h.declare(out_root, log_root)
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, cwd


def _enduring(base: Path) -> Path:
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    return root


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


_READERS = {
    "aggregate": (("scripts", "feedback", "aggregate.py"), ["--json"]),
    "list_tags": (("scripts", "feedback", "list_tags.py"), []),
    "trend_report": (("skills", "feedback-analysis", "scripts", "trend_report.py"), ["--format", "json"]),
}


def _reader(out_root: Path, name: str) -> tuple[Path, list[str]]:
    parts, args = _READERS[name]
    return out_root.joinpath(*parts), list(args)


def _stated_count_line(proc, sink: Path, count: int, *, label: str = "") -> None:
    """Exactly one stderr line names ``sink`` (absolute) and carries ``count`` as a number."""
    lines = [line for line in proc.stderr.splitlines() if str(sink) in line]
    assert len(lines) == 1, f"{label}expected one stderr line naming {sink}, got {proc.stderr!r}"
    assert re.search(rf"(?<![\d.]){count}(?![\d.])", lines[0]), f"{label}the line must state the record count {count}: {lines[0]!r}"


def test_reports_from_two_removed_worktrees_are_all_found_by_the_reader(tmp_path):
    # covers: INF-500d-4-v
    # angle: real_artifact
    """Two worktrees file into R and are removed; aggregate from the project root reports every id and says what it read."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    main_project, main_out, main_cwd = _worktree(tmp_path, "main", log_root=root)
    first_project, first_out, first_cwd = _worktree(tmp_path, "drive1", log_root=root)
    second_project, second_out, second_cwd = _worktree(tmp_path, "drive2", log_root=root)
    first_ids = h.seed_reports(first_out, first_cwd, tmpdir, sink, 3, tag="drive-one")
    second_ids = h.seed_reports(second_out, second_cwd, tmpdir, sink, 2, tag="drive-two")
    shutil.rmtree(first_project)
    shutil.rmtree(second_project)

    script, args = _reader(main_out, "aggregate")
    proc = h.run_py(script, args, main_project, tmpdir)

    assert proc.returncode == 0, proc.stderr
    found = [entry["feedback_id"] for entry in json.loads(proc.stdout)]
    assert sorted(found) == sorted([*first_ids, *second_ids]), "the later drive displaced, or the reader missed, an earlier drive's reports"
    _stated_count_line(proc, sink.resolve(), 5)


@pytest.mark.parametrize("reader", sorted(_READERS))
def test_each_reader_defaults_to_the_declared_feedback_sink(tmp_path, reader):
    # covers: INF-500d-4-v
    # angle: criterion
    """From inside a worktree, each reader reads R's records, not the decoy sinks the old defaults would find."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    real_ids = h.seed_reports(out_root, cwd, tmpdir, sink, 4, tag="rtag-real")
    # Decoys in exactly the places the old defaults resolve: parents[3] (the project), parents[2] / the
    # upward search (the install tree, which is CLOSER to trend_report than the project).
    for decoy in (project / "debugging" / "logs" / "feedback.jsonl",
                  out_root / "debugging" / "logs" / "feedback.jsonl"):
        h.seed_reports(out_root, cwd, tmpdir, decoy, 7, tag="decoy-tag", category="tooling-issue")
    before = h.snapshot(tmp_path)

    script, args = _reader(out_root, reader)
    proc = h.run_py(script, args, cwd, tmpdir)

    assert proc.returncode == 0, proc.stderr
    if reader == "aggregate":
        assert sorted(e["feedback_id"] for e in json.loads(proc.stdout)) == sorted(real_ids)
    elif reader == "list_tags":
        tags = {line.split()[1]: int(line.split()[0]) for line in proc.stdout.splitlines() if line.strip()}
        assert tags == {"rtag-real": 4}, f"list_tags read the wrong file: {tags}"
    else:
        report = json.loads(proc.stdout)
        assert report["summary"]["total_entries"] == 4
        assert report["by_category"] == {"complete": 4}, f"trend_report read the wrong file: {report['by_category']}"
    _stated_count_line(proc, sink.resolve(), 4, label=f"{reader}: ")
    assert h.snapshot(tmp_path) == before, f"{reader}: a read-only reader created a file or directory"


def test_mutating_readers_rewrite_the_record_in_the_declared_sink(tmp_path):
    # covers: INF-500d-4-v
    # angle: criterion
    """link_feedback and resolve_feedback change their target inside R/feedback.jsonl and create nothing under the worktree."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    to_link, to_resolve, untouched = h.seed_reports(out_root, cwd, tmpdir, sink, 3, tag="rtag-mut")
    original = {r["feedback_id"]: r for r in h.read_records(sink)}
    before = h.snapshot(project)

    link = h.run_py(out_root / "scripts" / "feedback" / "link_feedback.py",
                    ["--feedback-id", to_link, "--ticket", "TICKET-fix.md"], cwd, tmpdir)
    resolve = h.run_py(out_root / "scripts" / "feedback" / "resolve_feedback.py",
                       ["--feedback-id", to_resolve, "--note", "done in drive"], cwd, tmpdir)

    assert link.returncode == 0, f"link_feedback could not find the record in the declared sink: {link.stderr!r}"
    assert resolve.returncode == 0, f"resolve_feedback could not find the record in the declared sink: {resolve.stderr!r}"
    after = {r["feedback_id"]: r for r in h.read_records(sink)}
    assert after[to_link]["addressed_by"] == [{"type": "ticket", "ref": "TICKET-fix.md"}]
    assert after[to_resolve]["resolved_at"] and after[to_resolve]["resolution_note"] == "done in drive"
    assert after[untouched] == original[untouched] and len(after) == 3
    _stated_count_line(link, sink.resolve(), 3, label="link_feedback: ")
    _stated_count_line(resolve, sink.resolve(), 3, label="resolve_feedback: ")
    assert h.snapshot(project) == before, "a mutating reader created a file under the worktree it ran from"


def _runs_for(process: subprocess.Popen[str], seconds: float) -> bool:
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        return True
    return False


def test_rewrite_does_not_lose_a_concurrent_append(tmp_path):
    # covers: INF-500d-4-v
    # angle: boundary
    """While the sink's exclusive lock is held the rewrite waits on it; a racing append and the rewrite both survive."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    seeds = h.seed_reports(out_root, cwd, tmpdir, sink, 2, tag="rtag-race")
    target = seeds[0]

    holder = open(sink, "a", encoding="utf-8")  # noqa: SIM115 - the lock must outlive a with-block here
    fcntl.flock(holder, fcntl.LOCK_EX)
    resolver = appender = None
    try:
        resolver = h.popen_py(out_root / "scripts" / "feedback" / "resolve_feedback.py",
                              ["--feedback-id", target, "--note", "racing"], cwd, tmpdir)
        waited_for_the_lock = _runs_for(resolver, 2.0)
        appender = h.popen_py(h.submit_script(out_root), h.submit_args(note="racing append"), cwd, tmpdir)
        time.sleep(0.5)
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        holder.close()
    resolver_out, resolver_err = resolver.communicate(timeout=h.RUN_TIMEOUT)
    appender_out, appender_err = appender.communicate(timeout=h.RUN_TIMEOUT)

    assert waited_for_the_lock, (
        "resolve_feedback finished while another writer held the sink's exclusive lock, so it does not take "
        f"the same lock submit_feedback takes; stdout={resolver_out!r} stderr={resolver_err!r}"
    )
    assert resolver.returncode == 0, resolver_err
    assert appender.returncode == 0, appender_err
    records = h.read_records(sink)
    assert sorted(r["feedback_id"] for r in records) == sorted([*seeds, appender_out.strip()]), "an append was lost (or duplicated)"
    resolved = next(r for r in records if r["feedback_id"] == target)
    assert resolved["resolved_at"] and resolved["resolution_note"] == "racing", "the rewrite's change was lost"


def test_health_report_joins_the_declared_feedback_and_telemetry_logs(tmp_path):
    # covers: INF-500d-4-v
    # angle: criterion
    """With no path arguments, from a worktree, the report joins R's two streams and not the decoys beside the worktree."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    telemetry_driver_target = str(out_root / "scripts" / "agent-health" / "agent_telemetry.py")
    feedback_sink = root / "feedback.jsonl"
    telemetry_sink = root / "agent_telemetry.jsonl"
    quality = {"category": "subagent-quality", "phase": "ticket-supervisor", "tags": "agent-python-coder,mechanical-retry"}

    h.run_code(_TELEMETRY_DRIVER, [telemetry_driver_target, str(telemetry_sink), "3", "python-coder"], cwd, tmpdir)
    h.seed_reports(out_root, cwd, tmpdir, feedback_sink, 2, tag=quality["tags"], category=quality["category"], phase=quality["phase"])
    # The old CWD-relative defaults land here: different numbers, so reading them cannot pass.
    decoy_logs = cwd / "debugging" / "logs"
    h.run_code(_TELEMETRY_DRIVER, [telemetry_driver_target, str(decoy_logs / "agent_telemetry.jsonl"), "1", "python-coder"], cwd, tmpdir)
    h.seed_reports(out_root, cwd, tmpdir, decoy_logs / "feedback.jsonl", 9, tag=quality["tags"], category=quality["category"], phase=quality["phase"])
    assert len(h.read_records(telemetry_sink)) == 3, "fixture check: the real telemetry producer must have written R's stream"

    proc = h.run_py(out_root / "scripts" / "agent-health" / "generate_health_report.py", ["--format", "json"], cwd, tmpdir)

    assert proc.returncode == 0, proc.stderr
    rows = {row["agent"]: row for row in json.loads(proc.stdout)}
    assert set(rows) == {"python-coder"}, rows
    assert rows["python-coder"]["invocations"] == 3, f"telemetry was not read from the declared stream: {rows}"
    assert rows["python-coder"]["top_failure_archetypes"] == [{"tag": "mechanical-retry", "count": 2}], f"feedback was not read from the declared sink: {rows}"
    _stated_count_line(proc, telemetry_sink.resolve(), 3, label="telemetry: ")
    _stated_count_line(proc, feedback_sink.resolve(), 2, label="feedback: ")


def test_reader_names_a_populated_legacy_sink_once(tmp_path):
    # covers: INF-500d-4-v
    # angle: boundary
    """A populated install-tree feedback.jsonl that differs from the declared sink is named once with both paths, untouched."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=root)
    legacy = out_root / "debugging" / "logs" / "feedback.jsonl"
    h.seed_reports(out_root, cwd, tmpdir, sink, 2, tag="rtag-new")
    script, args = _reader(out_root, "aggregate")

    quiet = h.run_py(script, args, cwd, tmpdir)  # control: no legacy file yet, so no notice may appear
    assert quiet.returncode == 0, quiet.stderr
    assert str(legacy) not in quiet.stderr, f"a notice fired with no legacy sink present: {quiet.stderr!r}"

    h.seed_reports(out_root, cwd, tmpdir, legacy, 3, tag="rtag-old")
    digests = (h.sha256(sink), h.sha256(legacy))
    proc = h.run_py(script, args, cwd, tmpdir)

    assert proc.returncode == 0, proc.stderr
    notices = [line for line in proc.stderr.splitlines() if str(legacy) in line]
    assert len(notices) == 1, f"the legacy sink must be named exactly once: {proc.stderr!r}"
    assert str(sink.resolve()) in notices[0], f"the notice must name both paths: {notices[0]!r}"
    assert (h.sha256(sink), h.sha256(legacy)) == digests, "a reader merged, moved or rewrote a sink"
    assert len(json.loads(proc.stdout)) == 2, "the reader must read only the declared sink, never merge the legacy one"


@pytest.mark.parametrize("decoy", ["no_file_anywhere", "populated_workspace_sink"])
@pytest.mark.parametrize("reader", sorted(_READERS))
def test_reader_without_a_declaration_refuses_instead_of_reporting_zero(tmp_path, reader, decoy):
    # covers: INF-500d-4-v
    # angle: discrimination
    """No declaration and no path argument: non-zero, the expected declaration named, and no empty (or decoy) result."""
    tmpdir = _tmpdir(tmp_path)
    project, out_root, cwd = _worktree(tmp_path, "wt", log_root=None)
    if decoy == "populated_workspace_sink":
        h.seed_reports(out_root, cwd, tmpdir, project / "debugging" / "logs" / "feedback.jsonl", 3, tag="decoy-tag")
    before = h.snapshot(tmp_path)

    script, args = _reader(out_root, reader)
    proc = h.run_py(script, args, cwd, tmpdir)

    assert proc.returncode != 0, f"{reader} reported a result instead of refusing: stdout={proc.stdout!r}"
    assert str(h.declaration_path(out_root)) in proc.stderr, f"stderr must name the expected declaration: {proc.stderr!r}"
    assert proc.stdout.strip() == "", f"a refusal must print no result (an empty or decoy-based one reads as 'no feedback'): {proc.stdout!r}"
    assert h.snapshot(tmp_path) == before


def test_inf_500d_4_v_reachable_from_entry_point(tmp_path):
    # covers: INF-500d-4-v
    # angle: reachability
    """Resolve a removed drive's report from the project root, then read it back through aggregate's --unresolved/--resolved."""
    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    main_project, main_out, _main_cwd = _worktree(tmp_path, "main", log_root=root)
    drive_project, drive_out, drive_cwd = _worktree(tmp_path, "drive", log_root=root)
    kept, resolved_id = h.seed_reports(drive_out, drive_cwd, tmpdir, sink, 2, tag="rtag-chain")
    shutil.rmtree(drive_project)

    resolve = h.run_py(main_out / "scripts" / "feedback" / "resolve_feedback.py",
                       ["--feedback-id", resolved_id], main_project, tmpdir)
    assert resolve.returncode == 0, f"the removed drive's report could not be resolved from the project root: {resolve.stderr!r}"
    script, _args = _reader(main_out, "aggregate")
    unresolved = h.run_py(script, ["--unresolved", "--json"], main_project, tmpdir)
    resolved = h.run_py(script, ["--resolved", "--json"], main_project, tmpdir)

    assert [e["feedback_id"] for e in json.loads(unresolved.stdout)] == [kept]
    assert [e["feedback_id"] for e in json.loads(resolved.stdout)] == [resolved_id]
    assert len(h.read_records(sink)) == 2
