"""
MODULE: test_inf_700b_3
GOAL: RED behavioural tests for AC INF-700b-3 -- a capture-health report that tells a reader which kind of
    quiet a period was (ADR-034 Amendment 3, A3.1-A3.7). Also closes INF-700b-1-i AC-4 (the
    nothing-to-record period descriptor) and gives INF-700b-1-ii its period-level coverage.
EXPECTED RED TODAY: ``scripts/knowledge/health/capture_health_report.py`` does not exist, and
    ``build_phases_knowledge.py`` lists it in neither deploy list, so the shared layout lacks it.
NOTE: every test runs the report as a SUBPROCESS (source tree with ``--stream``; deployed copy from a private
    copy of the shared layout). No test reads the live telemetry stream or spawns build.py.
"""
# @ac-tag: INF-700b-3

from __future__ import annotations

import datetime
import json
import shutil

import pytest

from tests.knowledge import _inf_700b_3_support as S

_DAY = ("2026-10-22", "2026-10-23")


def _utc_window() -> tuple[str, str]:
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - datetime.timedelta(days=1)).isoformat(), (now + datetime.timedelta(days=1)).isoformat()


def test_period_with_runs_and_no_learnings_reports_nothing_to_record(tmp_path):
    # covers: INF-700b-3
    # angle: criterion
    """Three nothing-to-record attempts: attempts=3 recorded=0 failed=0 and the nothing-to-record verdict.

    Wrong versions caught: a verdict of broken/no-run/learnings-recorded; omitting the zero figures;
    counting failed from anything but outcome 'failed'.
    """
    lines = [S.attempt(S.NOTHING, f"2026-10-22T0{h}:00:00+00:00") for h in (1, 2, 3)]
    out = S.source_report(S.write_stream(tmp_path / "t.jsonl", lines), *_DAY, tmp_path)
    S.assert_period(out, (3, 0, 3, 0), S.NOTHING)
    assert S.TARGET not in out.stdout and "(not recorded)" not in out.stdout


def test_period_with_a_failed_capture_reports_broken_and_names_the_missing_target(tmp_path):
    # covers: INF-700b-3
    # covers: INF-700b-1-ii
    # angle: criterion
    """One failed attempt: failed=1, verdict capture-path-broken, the LITERAL target in the report body.

    Second stream: duplicates collapse to one ``missing-target:`` line, distinct targets are all named and a
    failed attempt with a null target prints ``(not recorded)``. Wrong version caught: a count with no name.
    """
    stamp = "2026-10-22T10:00:00+00:00"
    one = S.write_stream(tmp_path / "one.jsonl", [S.attempt("failed", stamp, target=S.TARGET),
                                                   S.attempt(S.NOTHING, stamp)])
    out = S.source_report(one, *_DAY, tmp_path)
    S.assert_period(out, (2, 0, 1, 1), S.BROKEN)
    assert f"missing-target: {S.TARGET}" in out.stdout and "(not recorded)" not in out.stdout
    many = [S.attempt("failed", stamp, target=t) for t in (S.TARGET, "a/b.py", S.TARGET)]
    many.append(S.attempt("failed", stamp, target=None))
    out = S.source_report(S.write_stream(tmp_path / "many.jsonl", many), *_DAY, tmp_path)
    S.assert_period(out, (4, 0, 0, 4), S.BROKEN)
    assert out.stdout.count(f"missing-target: {S.TARGET}") == 1
    assert "missing-target: a/b.py" in out.stdout and "missing-target: (not recorded)" in out.stdout


def test_period_with_no_attempt_records_is_a_third_distinct_case(tmp_path):
    # covers: INF-700b-3
    # angle: boundary
    """An empty period (empty stream, or records only outside the window) is 'no run reached the step'.

    The zero figures are printed explicitly and the verdict differs from the nothing-to-record verdict.
    """
    empty = S.write_stream(tmp_path / "empty.jsonl", [])
    elsewhere = S.write_stream(tmp_path / "else.jsonl", [S.attempt(S.NOTHING, "2026-10-25T00:00:00+00:00")])
    for stream in (empty, elsewhere):
        out = S.source_report(stream, *_DAY, tmp_path)
        S.assert_period(out, (0, 0, 0, 0), S.NO_RUN)
        assert S.verdict(out.stdout) != S.NOTHING


def test_capture_health_and_routing_backlog_do_not_share_a_number(tmp_path):
    # covers: INF-700b-3
    # angle: seam
    """Same stream, emission sink (a) empty (b) unroutable records (c) a directory: byte-identical output.

    failed=5 each time; no backlog word or harvester counter name anywhere; the sink file is untouched; and
    the module source imports nothing from harvest_learnings (AST check).
    """
    lines = [S.attempt("failed", f"2026-10-22T0{h}:00:00+00:00", target=S.TARGET) for h in range(5)]
    stream = S.write_stream(tmp_path / "agent_telemetry.jsonl", lines)
    sink = tmp_path / "knowledge_emissions.jsonl"
    outputs = []
    for content in ("", '{"event": "knowledge_captured", "entry_kind": "bogus", "text": "t"}\n', None):
        if content is None:
            sink.unlink()
            sink.mkdir()
        else:
            sink.write_text(content, encoding="utf-8")
        before = None if content is None else sink.read_bytes()
        out = S.source_report(stream, *_DAY, tmp_path)
        S.assert_period(out, (5, 0, 0, 5), S.BROKEN)
        assert before is None or sink.read_bytes() == before, "the report must not write the emission sink"
        outputs.append(out.stdout)
        text = (out.stdout + out.stderr).lower()
        assert not [w for w in S.FORBIDDEN_WORDS if w in text], text
    assert outputs[0] == outputs[1] == outputs[2], "output must not depend on the emission sink"
    source = S.SOURCE_SCRIPT.read_text(encoding="utf-8")
    assert S.harvester_imports(source) == [], "the report must not import harvest_learnings"


def test_report_is_reproducible_from_the_real_mixed_telemetry_stream(tmp_path):
    # covers: INF-700b-3
    # angle: real_artifact
    """A frozen stream shaped like the live one plus the historic garbage completes and is reproducible.

    Exit 0; 5 attempts counted (the key-less one included); 2 malformed (bad outcome, bad timestamp) and 8
    unrecognised (probe, agent_start, legacy, truncated, bare fragment, [], "x", 7) kept apart from the
    period figures; a blank line never changes the malformed count; the out-of-window failure is excluded;
    a second fresh process prints byte-identical output; the A2.6 and A2.4 limits are printed once each.
    """
    stream = S.write_stream(tmp_path / "mixed.jsonl", S.mixed_stream_lines())
    first = S.source_report(stream, "2026-10-21", "2026-10-24", tmp_path)
    S.assert_period(first, (5, 1, 3, 1), S.BROKEN)
    got = S.figures(first.stdout)
    assert got["malformed"] == 2 and got["unrecognised"] in (8, 9), got
    assert "out/of/window.py" not in first.stdout and f"missing-target: {S.TARGET}" in first.stdout
    assert first.stdout.count("A2.6") == 1 and first.stdout.count("A2.4") == 1, first.stdout
    assert S.source_report(stream, "2026-10-21", "2026-10-24", tmp_path).stdout == first.stdout


def test_records_with_unparseable_timestamps_are_excluded_from_every_period(tmp_path):
    # covers: INF-700b-3
    # angle: failure
    """Bad or absent timestamps count as malformed and join no period; naive and offset times are read as UTC.

    Valid control: one nothing-to-record. The two malformed rows are 'failed', so counting them anywhere would
    flip the verdict to broken. A naive stamp is UTC, a ``-02:00`` stamp that falls on 03:00Z the next day is
    outside the day, and date-only arguments mean midnight UTC. Offset stamps whose text order disagrees with
    their UTC order (``2026-10-22T23:00:00-02:00`` is outside; ``2026-10-21T23:30:00-02:00`` is inside), plus
    ``Z`` and ``+00:00`` spellings, pin that the window compares instants, never timestamp strings.

    Wrong version caught: comparing the raw timestamp text with ``since.isoformat()`` / ``until.isoformat()``.
    """
    no_ts = S.attempt_record("failed", "2026-10-22T09:00:00+00:00", target=S.TARGET)
    del no_ts["timestamp"]
    lines = [S.attempt("failed", "yesterday", target=S.TARGET), json.dumps(no_ts),
             S.attempt(S.NOTHING, "2026-10-22T10:00:00"),
             S.attempt("failed", "2026-10-23T01:00:00-02:00", target="late/utc.py"),
             # 01:00Z on the 23rd: OUTSIDE the day, yet its text sorts inside [since, until) as a string
             S.attempt("failed", "2026-10-22T23:00:00-02:00", target="late/offset.py"),
             # 01:30Z on the 22nd: INSIDE the day, yet its text sorts before ``since`` as a string
             S.attempt(S.NOTHING, "2026-10-21T23:30:00-02:00"),
             S.attempt(S.NOTHING, "2026-10-22T05:00:00Z"),
             S.attempt(S.NOTHING, "2026-10-22T06:00:00+00:00")]
    out = S.source_report(S.write_stream(tmp_path / "ts.jsonl", lines), *_DAY, tmp_path)
    S.assert_period(out, (4, 0, 4, 0), S.NOTHING)
    assert S.figures(out.stdout)["malformed"] == 2
    assert "late/utc.py" not in out.stdout and "late/offset.py" not in out.stdout


def test_inf_700b_3_reachable_from_entry_point(tmp_path):
    # covers: INF-700b-3
    # covers: INF-700b-1-ii
    # covers: INF-700b
    # angle: reachability
    """Run the CLI once per fixture period over ONE stream; the three verdicts differ pairwise.

    Day 1 holds nothing-to-record attempts, day 2 a failed attempt naming its target, day 3 nothing, and a
    later record keeps the stream non-empty. Entry point: ``python scripts/knowledge/health/capture_health_report.py
    --since S --until U --stream <tmp>`` as a subprocess (the source tree has no declaration).
    """
    lines = [S.attempt(S.NOTHING, "2026-10-20T10:00:00+00:00"), S.attempt(S.NOTHING, "2026-10-20T11:00:00+00:00"),
             S.attempt("failed", "2026-10-21T10:00:00+00:00", target=S.TARGET),
             S.attempt(S.NOTHING, "2026-10-23T10:00:00+00:00")]
    stream = S.write_stream(tmp_path / "t.jsonl", lines)
    periods = (("2026-10-20", "2026-10-21", S.NOTHING), ("2026-10-21", "2026-10-22", S.BROKEN),
               ("2026-10-22", "2026-10-23", S.NO_RUN))
    seen = []
    for since, until, name in periods:
        out = S.source_report(stream, since, until, tmp_path)
        assert out.returncode == 0 and S.verdict(out.stdout) == name, out
        assert (S.TARGET in out.stdout) == (name == S.BROKEN), out.stdout
        seen.append(S.verdict(out.stdout))
    assert len(set(seen)) == 3, f"the three verdicts must be pairwise different: {seen}"


@pytest.mark.shared_layout_reader
def test_nothing_to_record_period_reports_zero_captured_and_zero_failed(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-i
    # covers: INF-700b-3
    # angle: criterion
    """Real emit_event.py writes nothing-to-record attempts only; the DEPLOYED report prints the zeros.

    recorded=0 and failed=0 are explicit numbers, attempts=3, verdict nothing-to-record, not the no-run
    verdict. The stream is located from the copy's own declaration (no ``--stream``).
    """
    proj = S._project(tmp_path, shared_reference_layout, "live")
    S.emit_attempt(proj, tmp_path, S.NOTHING, "--ticket", "tickets/TICKET-x.md")
    S.emit_attempt(proj, tmp_path, S.NOTHING)
    S.emit_attempt(proj, tmp_path, S.NOTHING)
    since, until = _utc_window()
    out = S.run_report(S.deployed_script(proj), "--since", since, "--until", until, cwd=proj["project"])
    S.assert_period(out, (3, 0, 3, 0), S.NOTHING)
    assert S.verdict(out.stdout) != S.NO_RUN


def test_period_with_recorded_learnings_and_no_failures_is_a_fourth_distinct_verdict(tmp_path):
    # covers: INF-700b-3
    # angle: boundary
    """recorded and no failed is learnings-recorded; precedence holds; the window is half-open; unit is attempts.

    Cases: recorded only; recorded + nothing; recorded + failed (broken wins); nothing only; one record exactly
    at ``since`` (in) and one exactly at ``until`` (out). attempts == recorded + nothing + failed each time and
    the output says attempts, never agent runs.
    """
    stamp = "2026-10-22T10:00:00+00:00"
    cases = {"r": ([S.attempt("recorded", stamp)] * 2, (2, 2, 0, 0), S.RECORDED),
             "rn": ([S.attempt("recorded", stamp), S.attempt(S.NOTHING, stamp), S.attempt(S.NOTHING, stamp)],
                    (3, 1, 2, 0), S.RECORDED),
             "rf": ([S.attempt("recorded", stamp), S.attempt("failed", stamp, target=S.TARGET)],
                    (2, 1, 0, 1), S.BROKEN),
             "n": ([S.attempt(S.NOTHING, stamp)], (1, 0, 1, 0), S.NOTHING)}
    names = set()
    for key, (lines, expected, name) in cases.items():
        out = S.source_report(S.write_stream(tmp_path / f"{key}.jsonl", lines), *_DAY, tmp_path)
        S.assert_period(out, expected, name)
        assert "attempts" in out.stdout and "agent run" not in out.stdout.lower()
        names.add(name)
    assert names == {S.RECORDED, S.BROKEN, S.NOTHING} and S.NO_RUN not in names
    edge = [S.attempt(S.NOTHING, "2026-10-22T00:00:00+00:00"), S.attempt("failed", "2026-10-23T00:00:00+00:00",
                                                                           target=S.TARGET)]
    out = S.source_report(S.write_stream(tmp_path / "edge.jsonl", edge), "2026-10-22T00:00:00",
                          "2026-10-23T00:00:00", tmp_path)
    S.assert_period(out, (1, 0, 1, 0), S.NOTHING)


@pytest.mark.shared_layout_reader
def test_unlocatable_stream_fails_closed_and_is_not_reported_as_no_run(shared_reference_layout, tmp_path):
    # covers: INF-700b-3
    # angle: failure
    """Deployed copy, no --stream: an unusable declaration refuses; a usable one with no file is case (c).

    Absent declaration, stale enduring root and a telemetry stream outside the log root each exit non-zero,
    name knowledge_sink.json on stderr and print nothing on stdout. A usable declaration whose stream file does
    not exist reports no-run-reached-the-step; a directory in place of the stream exits non-zero with no verdict.
    Control: the same copy with a stream holding an attempt exits 0.
    """
    args = ("--since", "2026-10-01", "--until", "2099-01-01")
    for case in ("absent", "stale", "elsewhere"):
        proj = S._project(tmp_path / case, shared_reference_layout, "live" if case == "elsewhere" else case)
        if case == "elsewhere":
            S.redeclare_stream_elsewhere(proj)
        out = S.run_report(S.deployed_script(proj), *args, cwd=proj["project"])
        assert out.returncode != 0 and out.stdout.strip() == "", (case, out)
        assert "knowledge_sink.json" in out.stderr, (case, out.stderr)
    live = S._project(tmp_path / "live", shared_reference_layout, "live")
    assert not S._stream(live).exists()
    out = S.run_report(S.deployed_script(live), *args, cwd=live["project"])
    S.assert_period(out, (0, 0, 0, 0), S.NO_RUN)
    S._stream(live).mkdir()
    out = S.run_report(S.deployed_script(live), *args, cwd=live["project"])
    assert out.returncode != 0 and S.verdict(out.stdout) is None and out.stderr.strip(), out
    control = S._project(tmp_path / "control", shared_reference_layout, "live")
    S.emit_attempt(control, tmp_path / "control", S.NOTHING)
    ok = S.run_report(S.deployed_script(control), *args, cwd=control["project"])
    S.assert_period(ok, (1, 0, 1, 0), S.NOTHING)


@pytest.mark.shared_layout_reader
def test_capture_health_report_is_deployed_through_both_knowledge_script_lists(shared_reference_layout, tmp_path):
    # covers: INF-700b-3
    # angle: real_artifact
    """Both hand-kept deploy lists name the script, and the deployed copy runs from the copied shared layout.

    The names are read from the list/tuple literals of ``build_knowledge_scripts`` and
    ``_manifest_knowledge_scripts`` (docstrings do not count). No build.py is spawned.
    """
    assert S.DEPLOY_ENTRY in S.deploy_list_entries("build_knowledge_scripts"), "missing from deploy_scripts"
    assert S.DEPLOY_ENTRY in S.deploy_list_entries("_manifest_knowledge_scripts"), "missing from manifest tuple"
    assert (shared_reference_layout / ".leafcutter" / "scripts" / "knowledge" / "health" / S.SCRIPT_NAME).is_file()
    proj = S._project(tmp_path, shared_reference_layout, "live")
    assert S.deployed_script(proj).is_file() and shutil.which("python3") is not None
    S.emit_attempt(proj, tmp_path, "recorded")
    since, until = _utc_window()
    out = S.run_report(S.deployed_script(proj), "--since", since, "--until", until, cwd=proj["project"])
    S.assert_period(out, (1, 1, 0, 0), S.RECORDED)
