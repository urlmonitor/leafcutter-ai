"""
MODULE: test_inf_500d_4_vi
GOAL: RED tests for AC INF-500d-4-vi -- agent instructions no longer send reports
    to the workspace that is about to be deleted.
AC: INF-500d-4-vi (source_ac); depends on INF-500d-4-iv (writers default to the
    declared sink) and INF-500d-4-v (readers default to it and state it).

CONTRACT THIS FILE FIXES (llm-expert implements the prompt edits against it):

    1. NO SHIPPED SURFACE CARRIES A LOG DESTINATION OF ITS OWN. No deployed
       agent / skill / workflow / command passes ``--jsonl`` / ``--log`` /
       ``--feedback`` / ``--telemetry`` a workspace-relative ``debugging/logs/<file>``
       value, appends to one (``>>``, ``SINK_PATH=...``, "append to ..."), or
       restates one in the eleven declared prompts, in ANY quote style.
    2. Every submit_feedback / emit_event command the prompts tell an agent to
       run, executed verbatim from the worktree root, lands its record in the
       DECLARED sink and writes nothing beneath the worktree.
    3. The reader commands the reader prompts prescribe read the declared sink
       and the reader's stderr line states it; no decoy sink in the worktree
       is read.
    4. The signoff id-capture contract is unchanged: stdout is exactly the id;
       the ``sidecar:`` grep finds exactly one match (the sidecar), not the
       sink line.
    5. Telemetry calls keep their trailing ``|| true`` (still exit 0 when the
       interpreter itself cannot be found).

HOW THE PROMPTS ARE EXERCISED (behavioural, not grep-only): see
    ``_inf_500d_4_vi_helpers``. The prompt text comes from the DEPLOYED copies in
    the shared reference layout; the shell commands in them are lifted out and run
    with ``bash -c`` from a worktree root against a temp install with a declaration
    written by the REAL build helper. No build.py is spawned here.
"""
# @ac-tag: INF-500d-4-vi

from __future__ import annotations

import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_3_ii_check import RUN_A, fill, name_problems
from unit_tests.feedback._inf_500d_4_vi_helpers import (
    _ANY_MENTION,
    _DECLARED,
    _MIN_WRITERS,
    _READER_TOOLS,
    _WRITER_TOOLS,
    _all_deployed_surfaces,
    _commands,
    _declared_prompts,
    _destination_hits,
    _enduring,
    _inspect,
    _lifted,
    _prepare,
    _run_writers,
    _shell,
    _tmpdir,
    _workspace_logs,
    _worktree,
)

pytestmark = pytest.mark.shared_layout_reader


def test_no_deployed_surface_names_a_workspace_relative_log_destination(shared_reference_layout):
    # covers: INF-500d-4-vi
    # angle: deployed
    """Scan every DEPLOYED agent, skill, workflow and command; none may name debugging/logs/<file> as a destination."""
    surfaces = _all_deployed_surfaces(shared_reference_layout)
    missing = [f"{s}: {rel}" for s, rel in _DECLARED.items() if rel not in surfaces]
    assert not missing, f"declared surfaces absent from the scan: {missing}"

    inspected, offences = _inspect(surfaces)
    assert inspected >= len(_DECLARED), f"only {inspected} surfaces inspected"
    assert not offences, (
        f"{len(offences)} deployed line(s) still name a workspace-relative log destination "
        f"({inspected} surfaces inspected):\n  " + "\n  ".join(offences)
    )


def test_scanner_is_not_vacuous_and_matches_every_quote_style():
    # covers: INF-500d-4-vi
    # angle: discrimination
    """The scan flags the shipped bad forms in bare, single, double, backtick and ./ styles, and refuses to scan nothing."""
    bad = [
        "python3 scripts/feedback/submit_feedback.py --jsonl debugging/logs/feedback.jsonl 2>/tmp/e.txt",
        "python3 submit_feedback.py --jsonl 'debugging/logs/feedback.jsonl'",
        'python3 submit_feedback.py --jsonl "debugging/logs/feedback.jsonl"',
        "python3 submit_feedback.py --jsonl `debugging/logs/feedback.jsonl`",
        "python emit_event.py --log=./debugging/logs/agent_telemetry.jsonl || true",
        'SINK_PATH="debugging/logs/agent_telemetry.jsonl"',
        "echo '{}' >> debugging/logs/agent_telemetry.jsonl",
        "Appends structured events to `debugging/logs/agent_telemetry.jsonl`",
    ]
    for sample in bad:
        assert _destination_hits(sample), f"the scan is blind to: {sample}"
    good = [
        "python3 scripts/feedback/submit_feedback.py --ticket x --phase y --category z --note n",
        "python emit_event.py --log /abs/enduring/logs/agent_telemetry.jsonl || true",
    ]
    for sample in good:
        assert not _destination_hits(sample), f"the scan flags an innocent line: {sample}"
    with pytest.raises(AssertionError, match="ZERO surfaces"):
        _inspect({})


def test_no_declared_prompt_restates_a_log_path_in_any_style(shared_reference_layout):
    # covers: INF-500d-4-vi
    # angle: criterion
    """None of the eleven declared prompts mentions debugging/logs at all: a location is obtained, never restated."""
    prompts = _declared_prompts(shared_reference_layout)
    assert len(prompts) == len(_DECLARED)
    mentions = [
        f"{name}:{number}: {line.strip()[:140]}"
        for name, text in prompts.items()
        for number, line in enumerate(text.splitlines(), start=1)
        if _ANY_MENTION.search(line)
    ]
    assert not mentions, f"{len(mentions)} line(s) still restate a log path:\n  " + "\n  ".join(mentions)


def test_every_writer_command_the_prompts_prescribe_lands_in_the_declared_sink(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # angle: criterion
    """Run each submit_feedback / emit_event command verbatim from the worktree root: the record lands at the declared sink only."""
    prompts = _declared_prompts(shared_reference_layout)
    commands = _lifted(prompts, _WRITER_TOOLS)
    for (surface, tool), floor in _MIN_WRITERS.items():
        have = sum(1 for c in commands if c.surface == surface and c.tool == tool)
        assert have >= floor, f"{surface} carries {have} {tool} command(s); at least {floor} must remain"

    root = _enduring(tmp_path)
    project, out_root = _worktree(tmp_path, "wt", root)
    tmpdir = _tmpdir(tmp_path)

    breaches = _run_writers(commands, project, out_root, root, tmpdir)
    assert not breaches, "\n  ".join(["a prompt's command did not land at the declared sink:", *breaches])

    submits = sum(1 for c in commands if c.tool == "submit_feedback")
    emits = sum(1 for c in commands if c.tool == "emit_event")
    assert len(h.read_records(root / "feedback.jsonl")) == submits
    assert len(h.read_records(root / "agent_telemetry.jsonl")) == emits
    assert _workspace_logs(project) == [], "a prompt's command wrote a log beneath the disposable worktree"


def test_preflight_reachability_probes_leave_the_worktree_untouched(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # angle: criterion
    """The sink pre-flight blocks in building-epics and epic-supervisor must not create debugging/logs in the worktree."""
    prompts = _declared_prompts(shared_reference_layout)
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
    if not blocks:
        # A change may delete the probe outright; then no surface may still mention it.
        assert all(marker not in prompts[s] for s in ("building-epics", "epic-supervisor"))
        return

    root = _enduring(tmp_path)
    project, _out = _worktree(tmp_path, "wt", root)
    tmpdir = _tmpdir(tmp_path)
    for surface, body in blocks:
        _shell(body, project, tmpdir)
        assert _workspace_logs(project) == [], (
            f"{surface}: the pre-flight probe created {_workspace_logs(project)} beneath the disposable worktree")


def test_reader_commands_read_the_declared_sink_and_state_it(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # angle: seam
    """Reader prompts' commands run against real producer output: they read the declared sink, never a decoy in the worktree."""
    prompts = _declared_prompts(shared_reference_layout)
    readers = [c for c in _lifted(prompts, _READER_TOOLS)
               if c.surface in ("retrospective-agent", "feedback-review", "feedback-analyst", "feedback-report")]
    readers.sort(key=lambda c: c.tool == "resolve_feedback")  # the mutating call goes last
    for surface, tool in (("retrospective-agent", "aggregate"), ("feedback-review", "aggregate"),
                          ("feedback-analyst", "trend_report"), ("retrospective-agent", "generate_health_report")):
        assert any(c.surface == surface and c.tool == tool for c in readers), f"{surface} no longer runs {tool}.py"

    root = _enduring(tmp_path)
    project, out_root = _worktree(tmp_path, "wt", root)
    tmpdir = _tmpdir(tmp_path)
    sink = root / "feedback.jsonl"
    ids = h.seed_reports(out_root, project, tmpdir, sink, 3, tag="declared",
                         category="subagent-quality", phase="ticket-supervisor")
    decoy = project / "debugging" / "logs" / "feedback.jsonl"
    decoy.parent.mkdir(parents=True)
    h.seed_reports(out_root, project, tmpdir, decoy, 1, tag="decoy",
                   category="subagent-quality", phase="ticket-supervisor")

    breaches = []
    for cmd in readers:
        proc = _shell(_prepare(cmd, out_root, tmpdir, feedback_id=ids[0]), project, tmpdir)
        # the reader's own statement, "read N records from <file>" (a separate NOTE may name a legacy file; that is not a read)
        stated = re.findall(r"read (\d+) records? from (\S+?)(?:;|\s|$)", proc.stderr)
        read_paths = {path for _count, path in stated}
        declared_files = {str(sink), str(root / "agent_telemetry.jsonl")}
        label = f"{cmd.where} [{cmd.tool}]"
        if proc.returncode != 0:
            breaches.append(f"{label}: exited {proc.returncode}: {proc.stderr.strip()[:200]!r}")
        elif read_paths - declared_files:
            breaches.append(f"{label}: read {sorted(read_paths - declared_files)}, not the declared sink: {proc.stderr.strip()[:200]!r}")
        elif str(sink) not in read_paths:
            breaches.append(f"{label}: stderr does not state the declared sink {sink}: {proc.stderr!r}")
        elif {c for c, p in stated if p == str(sink)} != {"3"}:
            breaches.append(f"{label}: stated count {stated}; the declared sink holds 3 records")
        elif cmd.tool == "aggregate" and "--format json" in cmd.raw:
            total = json.loads(proc.stdout)["summary"]["total"]
            if total != 3:
                breaches.append(f"{label}: total={total}; the declared sink holds 3, the decoy 1")
    assert not breaches, "\n  ".join(["a reader prompt did not read the declared sink:", *breaches])


@pytest.mark.parametrize("variant", ["as_written", "with_the_old_override"])
def test_signoff_id_capture_contract_survives_the_prompt_change(shared_reference_layout, tmp_path, variant):
    # covers: INF-500d-4-vi
    # angle: discrimination
    """Signoff Call 1 / Call 2 as written: id on stdout, sidecar grep finds exactly one match, record in the declared sink."""
    prompts = _declared_prompts(shared_reference_layout)
    submit = next((c for c in _commands("signoff", prompts["signoff"]) if c.tool == "submit_feedback"), None)
    assert submit is not None, "signoff no longer carries a submit_feedback command"
    grep_line = next((ln.strip() for ln in prompts["signoff"].splitlines() if ln.strip().startswith("grep -o 'sidecar:")), None)
    assert grep_line is not None, "signoff no longer carries the sidecar recovery grep"

    root = _enduring(tmp_path)
    project, out_root = _worktree(tmp_path, "wt", root)
    tmpdir = _tmpdir(tmp_path)
    # INF-500d-3-ii: the error stream goes to a file of this run's own (ticket + phase), so Call 1, Call 2 and the
    # grep line are all filled in for the SAME concrete run before they are executed.
    run = RUN_A
    command = _prepare(replace(submit, raw=fill(submit.raw, run)), out_root, tmpdir)
    redirect = re.search(r"2>\s*(\S+)", command)
    assert redirect, f"signoff Call 1 must redirect stderr to a file: {command}"
    err_file = redirect.group(1)
    assert err_file.startswith(f"{tmpdir}/"), f"signoff Call 1 must redirect stderr into the temp dir: {command}"
    assert err_file != f"{tmpdir}/feedback_err.txt", "signoff Call 1 still redirects to the one file every caller shares"
    # The name is judged as the instruction prescribes it (/tmp/<name>), before the test confines /tmp to its tmpdir.
    prescribed = err_file.replace(f"{tmpdir}/", "/tmp/", 1)
    assert not name_problems(prescribed, run.ticket, run.phase), name_problems(prescribed, run.ticket, run.phase)
    if variant == "with_the_old_override":
        # Control: the pre-change shape (explicit workspace-relative --jsonl) must be CAUGHT by this harness.
        command = command.replace(" 2>", " --jsonl debugging/logs/feedback.jsonl 2>", 1)

    proc = _shell(command, project, tmpdir)
    assert proc.returncode == 0, proc.stderr
    if variant == "with_the_old_override":
        assert _workspace_logs(project), "control failed: the harness cannot see a workspace-relative write"
        assert not (root / "feedback.jsonl").exists(), "control failed: the override should have bypassed the declared sink"
        return

    feedback_id = proc.stdout.strip()
    assert re.fullmatch(r"fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}", feedback_id), f"stdout must be exactly the id, got {proc.stdout!r}"
    assert proc.stdout == feedback_id + "\n"

    grep_filled = fill(grep_line, run).replace("/tmp/", f"{tmpdir}/")
    assert grep_filled.rstrip().endswith(err_file), f"Call 2 must search the file Call 1 wrote ({err_file}): {grep_filled}"
    grep = _shell(grep_filled, project, tmpdir)
    matches = grep.stdout.splitlines()
    assert len(matches) == 1, f"the sidecar grep must find exactly one match, found {matches!r} in {Path(err_file).read_text()!r}"
    sidecar = Path(matches[0].split("sidecar:", 1)[1])
    assert sidecar.read_text(encoding="utf-8").strip() == feedback_id
    assert [r["feedback_id"] for r in h.read_records(root / "feedback.jsonl")] == [feedback_id]
    assert _workspace_logs(project) == []


def test_telemetry_calls_keep_their_best_effort_tail(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # angle: failure
    """Every emit_event command ends in '|| true' and still exits 0 when the interpreter cannot be found."""
    prompts = _declared_prompts(shared_reference_layout)
    emits = _lifted(prompts, ("emit_event",))
    assert len(emits) >= 9, f"only {len(emits)} telemetry commands found; the prompts carry at least 9 today"

    tmpdir = _tmpdir(tmp_path)
    project = tmp_path / "wt"
    project.mkdir()
    no_tools = h.empty_bin_path(tmp_path)
    control = _shell("python emit_event.py", project, tmpdir, path=no_tools)
    assert control.returncode != 0, "control failed: a bare failing command must exit non-zero on an empty PATH"
    for cmd in emits:
        assert cmd.raw.rstrip().endswith("|| true"), f"{cmd.where}: telemetry call lost its trailing '|| true': {cmd.raw[-80:]!r}"
        proc = _shell(_prepare(cmd, project / ".leafcutter", tmpdir), project, tmpdir, path=no_tools)
        assert proc.returncode == 0, f"{cmd.where}: a telemetry failure would stop the drive (rc={proc.returncode})"


def test_inf_500d_4_vi_reachable_from_entry_point(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # angle: reachability
    """Entry point: the CLI scripts (submit_feedback.py, emit_event.py, aggregate.py) via subprocess, with the exact commands
    lifted from the deployed prompts. File in worktree A, delete A, then read from worktree B: everything is in one place."""
    prompts = _declared_prompts(shared_reference_layout)
    writers = _lifted(prompts, _WRITER_TOOLS)
    review_read = next((c for c in _commands("feedback-review", prompts["feedback-review"]) if c.tool == "aggregate"), None)
    assert review_read is not None and writers

    root = _enduring(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    project_a, out_a = _worktree(tmp_path, "wt_a", root)
    project_b, out_b = _worktree(tmp_path, "wt_b", root)

    breaches = _run_writers(writers, project_a, out_a, root, tmpdir)
    assert not breaches, "\n  ".join(breaches)
    filed = sum(1 for c in writers if c.tool == "submit_feedback")
    shutil.rmtree(project_a)  # the drive finishes; its workspace is removed

    proc = _shell(_prepare(review_read, out_b, tmpdir), project_b, tmpdir)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["summary"]["total"] == filed, (
        f"a reader in another workspace must find all {filed} reports filed by the removed one; stdout={proc.stdout[:200]!r}")
    assert [ln for ln in proc.stderr.splitlines() if str(root / "feedback.jsonl") in ln], proc.stderr
    assert _workspace_logs(project_b) == []
