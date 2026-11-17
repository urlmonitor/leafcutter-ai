"""
MODULE: test_inf_500d_3_iii
GOAL: Regression guard for AC INF-500d-3-iii -- reading the feedback id from standard
    output keeps working unchanged, and still returns each agent its own id under
    concurrent submissions. It adds no behaviour to submit_feedback.py: it pins the
    stdout contract while INF-500d-3-i changes the recovery file beside it.
HOW: twenty real ``submit_feedback.py`` processes of a copied layout run at once
    against a declared sink and a confined TMPDIR (``_inf_500d_3_helpers``); the
    capture forms shipped in the deployed instructions are lifted and run as written.
    No build.py is spawned.
"""
# @ac-tag: INF-500d-3-iii

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from unit_tests.feedback import _inf_500d_3_helpers as t
from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_3_ii_check import RUN_A, fill
from unit_tests.feedback._inf_500d_4_vi_helpers import _commands, _declared_prompts, _prepare, _shell, _workspace_logs

_TICKET = "tickets/00_inbox/TICKET-inf-500d-4-probe.md"


@pytest.fixture(scope="module")
def twenty(tmp_path_factory):
    layout = t.make_layout(tmp_path_factory.mktemp("twenty_iii"))
    return layout, t.launch(layout, 20, "stdout-probe")


def _by_key(layout) -> dict:
    return {(r["category"], r["phase"], r["note"]): r for r in t.records(layout)}


def _deployed(layout_root, rel: str) -> str:
    path = layout_root / ".leafcutter" / rel
    assert path.is_file(), f"not deployed: {path}"
    return path.read_text(encoding="utf-8")


def _capture_in_layout(script: str, layout, expect_note: str) -> str:
    """Run a lifted capture script as written (placeholders filled, script path in the copied layout); return FB_ID."""
    command = script.replace("scripts/feedback/", f"{layout.out_root}/scripts/feedback/")
    proc = _shell(command + '\nprintf "%s" "$FB_ID"', layout.project, layout.tmpdir)
    assert proc.returncode == 0, proc.stderr
    sink_ids = [r["feedback_id"] for r in t.records(layout) if r["note"] == expect_note]
    assert len(sink_ids) == 1, f"the sink holds {len(sink_ids)} records for {expect_note!r}"
    assert proc.stdout == sink_ids[0], f"FB_ID {proc.stdout!r} is not the record's id {sink_ids[0]!r}"
    return proc.stdout


def test_each_of_twenty_concurrent_submissions_prints_exactly_one_line_on_stdout(twenty):
    # covers: INF-500d-3-iii
    # angle: criterion
    """Every one of twenty overlapping processes exits 0 with exactly one newline-terminated stdout line."""
    _layout, runs = twenty
    assert [r.rc for r in runs] == [0] * 20, [r.stderr for r in runs if r.rc]
    bad = [(r.note, r.stdout) for r in runs if not (r.stdout.endswith("\n") and len(r.stdout.splitlines()) == 1)]
    assert not bad, f"stdout must be exactly one line: {bad}"


def test_each_stdout_line_is_a_feedback_id_of_the_documented_form(twenty):
    # covers: INF-500d-3-iii
    # angle: criterion
    """Each stdout line fully matches fb_YYYY-MM-DD_xxxxxxxx; no recovery or sink line leaks onto stdout."""
    _layout, runs = twenty
    bad = [(r.note, r.stdout) for r in runs if not re.fullmatch(r"fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}\n", r.stdout)]
    assert not bad, f"not a feedback id: {bad}"
    assert not [r.note for r in runs if "sidecar:" in r.stdout or "sink:" in r.stdout]
    assert all(len(t.sidecar_lines(r)) == 1 for r in runs), "the recovery line belongs on stderr, once per submission"


def test_twenty_concurrent_ids_are_pairwise_distinct(twenty):
    # covers: INF-500d-3-iii
    # angle: criterion
    """The runs overlap inside one or two adjacent seconds, and the twenty printed ids are twenty distinct values."""
    layout, runs = twenty
    seconds = {r["timestamp"] for r in t.records(layout)}
    assert 1 <= len(seconds) <= 2, f"the submissions did not overlap: record timestamps {sorted(seconds)}"
    assert len({r.id for r in runs}) == 20


def test_each_printed_id_names_the_record_its_own_submission_appended(twenty):
    # covers: INF-500d-3-iii
    # angle: seam
    """Matched by the record's own category, phase and note (never by position), each id is its own record's id."""
    layout, runs = twenty
    sink = t.records(layout)
    by_key = _by_key(layout)
    assert len(sink) == 20 and len(by_key) == 20, "each submission must have appended exactly one distinct record"
    wrong = [(r.key, r.id, by_key[r.key]["feedback_id"]) for r in runs if by_key[r.key]["feedback_id"] != r.id]
    assert not wrong, f"an id names another submission's record: {wrong}"
    assert {k for k in by_key} == {r.key for r in runs}


def test_declared_sink_holds_the_twenty_records_read_back_from_disk(twenty):
    # covers: INF-500d-3-iii
    # angle: real_artifact
    """The copied layout's declared sink file holds exactly twenty parseable JSON lines; nothing lands in the worktree."""
    layout, _runs = twenty
    lines = [ln for ln in layout.sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 20
    assert len(t.records(layout)) == 20
    assert _workspace_logs(layout.project) == [], "a record or log directory landed beneath the worktree"
    assert layout.sink.parent == layout.root


@pytest.mark.shared_layout_reader
def test_live_surface_tester_capture_block_runs_unchanged_and_returns_the_single_line_id(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iii
    # angle: seam
    """The FB_ID=$(...) block of the deployed live-surface-tester, run as written, returns the record's id."""
    text = _deployed(shared_reference_layout, "agents/live-surface-tester.md")
    start = text.index("FB_ID=$(python scripts/feedback/submit_feedback.py")
    end = text.index('FB_ID="${FB_ID:-(submit-failed)}"', start) + len('FB_ID="${FB_ID:-(submit-failed)}"')
    block = text[start:end].replace("<ticket_path>", _TICKET).replace("<one-sentence summary>", "live capture probe")
    block = fill(block, RUN_A)  # INF-500d-3-ii: the per-run error-stream name placeholders
    assert "<" not in block.replace("<<", ""), f"unfilled placeholder in the lifted block: {block}"
    layout = t.make_layout(tmp_path)
    block = block.replace("/tmp/", f"{layout.tmpdir}/")
    fb_id = _capture_in_layout(block, layout, "live capture probe")
    assert t.ID_RE.match(fb_id)


@pytest.mark.shared_layout_reader
def test_epic_supervisor_capture_form_runs_unchanged_and_returns_the_single_line_id(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iii
    # angle: seam
    """The epic-supervisor FB_ID=$(... 2>/dev/null) || FB_ID=(submit-failed) form, run in bash, returns the record's id."""
    text = _deployed(shared_reference_layout, "agents/epic-supervisor.md")
    line = next(ln for ln in text.splitlines() if ln.strip().startswith("# FB_ID=$(python scripts/feedback/submit_feedback.py"))
    # The deployed pseudo-code collapsed a multi-line shell comment onto one line, leaving the continuation
    # markers ('#') between the arguments. Only comment markers are removed; every word is kept.
    command = re.sub(r"\s+#\s+", " ", line.strip().removeprefix("# "))
    command = (command.replace("<any_affected_ticket_path>", _TICKET).replace("<phase>", "python-coder")
               .replace("<count>", "3").replace("<summary_prefix>", "epic capture probe"))
    assert "<" not in command, f"unfilled placeholder: {command}"
    layout = t.make_layout(tmp_path)
    note = "Cross-ticket pattern: python-coder failed with 'epic capture probe' on 3 tickets."
    fb_id = _capture_in_layout(command, layout, note)
    assert fb_id != "(submit-failed)" and t.ID_RE.match(fb_id)


@pytest.mark.shared_layout_reader
def test_signoff_reads_stdout_first_and_falls_back_to_the_recovery_file_only_when_stdout_is_empty(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-iii
    # angle: seam
    """Signoff Call 1 precedes Call 2; Call 2 is conditioned on empty stdout and recovers the id when stdout is forced empty."""
    text = _declared_prompts(shared_reference_layout)["signoff"]
    call1, call2 = text.index("**Call 1**"), text.index("**Call 2**")
    assert call1 < call2, "signoff must run the stdout call before the recovery call"
    assert "only if Call 1 stdout was empty" in text[call2:call2 + 120]
    grep_line = fill(next(ln.strip() for ln in text.splitlines() if ln.strip().startswith("grep -o 'sidecar:")), RUN_A)
    submit = next(c for c in _commands("signoff", text) if c.tool == "submit_feedback")
    submit = replace(submit, raw=fill(submit.raw, RUN_A))  # INF-500d-3-ii: fill the per-run error-file placeholders

    layout = t.make_layout(tmp_path)
    command = _prepare(submit, layout.out_root, layout.tmpdir)
    normal = _shell(command, layout.project, layout.tmpdir)
    assert normal.returncode == 0 and t.ID_RE.match(normal.stdout.strip()), "Call 1 alone must yield the id"
    assert normal.stdout.splitlines() == [normal.stdout.strip()]

    layout2 = t.make_layout(tmp_path / "forced_empty")
    silent = _shell(_prepare(submit, layout2.out_root, layout2.tmpdir) + " >/dev/null", layout2.project, layout2.tmpdir)
    assert silent.returncode == 0 and silent.stdout == ""
    match = _shell(grep_line.replace("/tmp/", f"{layout2.tmpdir}/"), layout2.project, layout2.tmpdir).stdout.splitlines()
    assert len(match) == 1, match
    recovered = (layout2.tmpdir / match[0].split("sidecar:", 1)[1]).read_text(encoding="utf-8")
    assert recovered == t.records(layout2)[0]["feedback_id"], "Call 2 did not recover the submission's own id"


def test_submit_feedback_is_reachable_as_twenty_concurrent_subprocesses(twenty):
    # covers: INF-500d-3-iii
    # angle: reachability
    """popen_py with real argv: each of the twenty subprocesses printed a one-line id that the sink also holds."""
    layout, runs = twenty
    sink_ids = {r["feedback_id"] for r in t.records(layout)}
    assert all(r.rc == 0 and re.fullmatch(h.FEEDBACK_ID_RE.strip("^$") + r"\n", r.stdout) for r in runs)
    assert {r.id for r in runs} == sink_ids and len(sink_ids) == 20
