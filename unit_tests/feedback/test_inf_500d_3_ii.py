"""
MODULE: test_inf_500d_3_ii
GOAL: RED tests for AC INF-500d-3-ii -- every agent sends its feedback submission's error
    stream to a file of its own, so its id-recovery search reads only its own submission.
AC: INF-500d-3-ii (source_ac); depends on INF-500d-3 (and INF-500d-3-i: unique recovery files).

CONTRACT THIS FILE FIXES (llm-expert edits the five instruction surfaces against it):

    1. Every deployed instruction that runs ``submit_feedback.py`` with its error stream
       redirected to a file (signoff Call 1, ticket-supervisor x4, documentation-verifier,
       user-surface-smoker, live-surface-tester) prescribes a name that, once its
       placeholders are filled for a run, is ONE path component (``/tmp/<name>`` or a bare
       ``<name>``; no other directory, no space or shell metacharacter) holding BOTH the
       ticket the run signs off on AND the phase it submits as.
    2. Placeholders are free to the author but are read by SPELLING (see
       ``_inf_500d_3_ii_check``): a placeholder containing ``ticket`` is the ticket
       (``<ticket_path>`` carries separators and so cannot be used in a name; use
       ``<ticket_basename>`` -> ``03-add-parser.md``); ``<agent_name>`` / ``<phase>`` is the
       phase. A fixed-phase surface (``--phase documentation-verifier``) carries its phase as
       a literal in the name. Recommended: ``/tmp/feedback_err_<ticket_basename>_<agent_name>.txt``.
    3. ticket-supervisor keeps its event-kind suffix (mechanical-retry, cross-agent-rework,
       brainstorm-escalation, halt) AND adds ticket + phase.
    4. The recovery search names the same file, written with the same placeholders, as the
       submit step that wrote it (signoff Call 2, live-surface-tester).

The check is behavioural: it fills the names in for python-coder on 03-add-parser and
pr-reviewer on 05-wire-cli, compares the results and RUNS the lifted commands. The prompt
text comes from the DEPLOYED copies in the shared reference layout (no build.py here).
"""
# @ac-tag: INF-500d-3-ii

from __future__ import annotations

import re

import pytest

from unit_tests.feedback import _inf_500d_3_helpers as h3
from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_3_ii_check import (
    COMBOS,
    EVENT_KINDS,
    RUN_A,
    RUN_B,
    TICKET_A,
    Run,
    TICKET_B,
    check,
    collisions,
    discover_surfaces,
    fill,
    name_problems,
    phase_of,
    redirects,
    searches,
)
from unit_tests.feedback._inf_500d_3_ii_run import (
    error_file,
    prepare,
    run_shell,
    search_command,
    sidecar_lines,
    start,
)
from unit_tests.feedback._inf_500d_4_vi_helpers import _all_deployed_surfaces

pytestmark = pytest.mark.shared_layout_reader

SIGNOFF = "skills/signoff/SKILL.md"
DOC_VERIFIER = "agents/documentation-verifier.md"
SMOKER = "agents/user-surface-smoker.md"
LIVE = "agents/live-surface-tester.md"
SUPERVISOR = "agents/ticket-supervisor.md"
OLD_SHARED = ("/tmp/feedback_err.txt", "feedback_err.txt")


def _surfaces(layout):
    return _all_deployed_surfaces(layout)


def _redirects_of(layout, rel):
    found = redirects(rel, _surfaces(layout)[rel])
    assert found, f"{rel} no longer carries a redirecting submit_feedback.py instruction"
    return found


def _assert_two_runs_differ(layout, rel):
    for red in _redirects_of(layout, rel):
        a, b = fill(red.target, RUN_A), fill(red.target, RUN_B)
        assert a != b, f"{rel}:{red.line} both runs resolve to the one file {a!r} (raw {red.target!r})"


def _plant(redirect_target: str, search_target: str | None = None) -> str:
    text = ("```bash\npython3 scripts/feedback/submit_feedback.py --ticket <ticket_path> --phase <agent_name> "
            f"--category complete --note \"x\" 2>{redirect_target}\n```\n")
    if search_target:
        text += f"```bash\ngrep -o 'sidecar:[^ ]*feedback_id_[0-9]*.txt' {search_target}\n```\n"
    return text


GOOD = "/tmp/feedback_err_<ticket_basename>_<agent_name>.txt"


# ---------------------------------------------------------------------------
# clause: the two runs resolve to two different files
# ---------------------------------------------------------------------------

def test_signoff_names_for_two_concurrent_runs_resolve_to_different_error_files(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: criterion
    """AC-1: python-coder on 03-add-parser and pr-reviewer on 05-wire-cli get different signoff Call 1 files."""
    _assert_two_runs_differ(shared_reference_layout, SIGNOFF)


def test_documentation_verifier_names_for_two_runs_resolve_to_different_error_files(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: criterion
    """The documentation-verifier redirect resolves to different files for the two runs."""
    _assert_two_runs_differ(shared_reference_layout, DOC_VERIFIER)


def test_user_surface_smoker_names_for_two_runs_resolve_to_different_error_files(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: criterion
    """The user-surface-smoker redirect resolves to different files for the two runs."""
    _assert_two_runs_differ(shared_reference_layout, SMOKER)


def test_live_surface_tester_names_for_two_runs_resolve_to_different_error_files(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: criterion
    """The 2> redirect AND the grep input of the live-surface-tester block differ per run and agree per run."""
    text = _surfaces(shared_reference_layout)[LIVE]
    reds, finds = redirects(LIVE, text), searches(LIVE, text)
    assert reds, "live-surface-tester carries no redirecting submit instruction"
    assert finds, "live-surface-tester no longer carries the sidecar recovery search"
    red, find = reds[0], finds[0]
    for target in (red.target, find.target):
        assert fill(target, RUN_A) != fill(target, RUN_B), f"both runs resolve {target!r} to one file"
    for run in (RUN_A, RUN_B):
        assert fill(find.target, run) == fill(red.target, run), f"the search and the redirect disagree for {run}"


def test_each_resolved_error_file_name_carries_the_ticket_and_the_phase_as_one_path_component(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: criterion
    """AC-2: for every discovered redirect and both runs, the name holds that run's ticket and phase, one component."""
    reds = [r for rel, text in sorted(_surfaces(shared_reference_layout).items()) for r in redirects(rel, text)]
    assert len(reds) >= 5, f"only {len(reds)} redirecting instructions discovered; five surfaces carry them today"
    bad = [f"{r.surface}:{r.line} ({run.phase}/{run.ticket}): {p}"
           for r in reds for run in (RUN_A, RUN_B)
           for p in name_problems(fill(r.target, run), run.ticket, phase_of(r.command, run))]
    assert not bad, "\n  ".join(["a prescribed name lacks the ticket, the phase or is not one component:", *bad])
    # Control rows: a name holding only one part, or a path, must be refused by the same predicate.
    assert name_problems("/tmp/feedback_err_03-add-parser.txt", TICKET_A, "python-coder")  # ticket only
    assert name_problems("/tmp/feedback_err_python-coder.txt", TICKET_A, "python-coder")  # phase only
    assert name_problems("/tmp/x/feedback_err_03-add-parser_python-coder.txt", TICKET_A, "python-coder")  # subdir
    assert name_problems("/tmp/err 03-add-parser python-coder.txt", TICKET_A, "python-coder")  # space
    assert not name_problems("/tmp/feedback_err_03-add-parser.md_python-coder.txt", TICKET_A, "python-coder")


# ---------------------------------------------------------------------------
# clause: no shipped instruction prescribes one fixed name shared by every caller
# ---------------------------------------------------------------------------

def test_no_deployed_instruction_prescribes_one_fixed_error_file_shared_by_every_caller(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: discrimination
    """Discover every redirect at check time; none may resolve two different callers to one file."""
    # The wrong versions the scan must catch, proven on the same predicate (a scan that cannot fail proves nothing).
    for fixed in OLD_SHARED:
        assert collisions(fixed, "python3 submit_feedback.py --phase <agent_name>"), f"blind to {fixed}"
    phase_only = "/tmp/feedback_err_<agent_name>.txt"
    cmd = "python3 submit_feedback.py --ticket <ticket_path> --phase <agent_name>"
    assert collisions(phase_only, cmd), "blind to a name keyed only on the phase (two tickets, one phase)"
    ticket_only = "/tmp/feedback_err_<ticket_basename>.txt"
    assert collisions(ticket_only, cmd), "blind to a name keyed only on the ticket (two phases, one ticket)"
    assert not collisions(GOOD, cmd)

    surfaces = _surfaces(shared_reference_layout)
    reds = [r for rel, text in sorted(surfaces.items()) for r in redirects(rel, text)]
    assert len(reds) >= 5
    shared = [f"{r.surface}:{r.line} {r.target!r}: {c}" for r in reds for c in collisions(r.target, r.command)]
    assert not shared, "\n  ".join(["instructions still prescribe a file that distinct callers share:", *shared])


def test_two_supervisors_halting_in_one_second_write_their_error_streams_to_different_files(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-ii
    # angle: discrimination
    """AC-3: four event kinds x tickets 03/05 resolve to eight different files; two halts run together keep their own."""
    reds = _redirects_of(shared_reference_layout, SUPERVISOR)
    by_kind = {kind: [r for r in reds if re.search(rf'[,"]{kind}[,"]', r.command)] for kind in EVENT_KINDS}
    for kind, found in by_kind.items():
        assert len(found) == 1, f"ticket-supervisor must carry exactly one {kind} submit step, found {len(found)}"
    names: dict[tuple[str, str], str] = {}
    for kind, (red,) in by_kind.items():
        for ticket in (TICKET_A, TICKET_B):
            names[(kind, ticket)] = fill(red.target, Run("ticket-supervisor", ticket))
        a, b = names[(kind, TICKET_A)], names[(kind, TICKET_B)]
        assert a != b, f"{kind}: tickets {TICKET_A} and {TICKET_B} share {a!r} (a name keyed on the event kind only)"
        assert kind in a and kind in b, f"{kind}: the event-kind suffix was dropped: {a!r}"
    assert len(set(names.values())) == len(names), f"event kinds and tickets collide: {names}"

    # Two supervisors halting at the same moment, run for real in one layout (one TMPDIR).
    layout = h3.make_layout(tmp_path)
    (halt,) = by_kind["halt"]
    sup_a, sup_b = (Run("ticket-supervisor", t) for t in (TICKET_A, TICKET_B))
    procs = [start(prepare(halt.command, run, layout), layout) for run in (sup_a, sup_b)]
    outs = [p.communicate(timeout=h.RUN_TIMEOUT) for p in procs]
    assert [p.returncode for p in procs] == [0, 0], outs
    file_a, file_b = error_file(halt, sup_a, layout), error_file(halt, sup_b, layout)
    assert file_a != file_b, f"both supervisors wrote their error stream to {file_a}"
    for run, path, (stdout, _err) in zip((sup_a, sup_b), (file_a, file_b), outs, strict=True):
        assert len(sidecar_lines(path)) == 1, f"{path} must hold exactly its own sidecar line: {path.read_text()!r}"
        mine = [r for r in h3.records(layout) if r["ticket"].endswith(f"{run.ticket}.md")]
        assert [r["feedback_id"] for r in mine] == [stdout.strip()]


# ---------------------------------------------------------------------------
# clause: the search reads only the file that run's own submission wrote
# ---------------------------------------------------------------------------

def test_recovery_search_reads_exactly_the_file_the_submit_step_wrote(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-ii
    # angle: seam
    """Signoff Call 2 and the live-surface-tester search name the redirect's file; run as written they find only the run's own id."""
    surfaces = _surfaces(shared_reference_layout)
    pairs = []
    for rel in (SIGNOFF, LIVE):
        reds, finds = redirects(rel, surfaces[rel]), searches(rel, surfaces[rel])
        assert reds and finds, f"{rel} lost its submit step or its recovery search"
        pairs.append((reds[0], finds[0]))
    for red, find in pairs:  # same placeholders, same file, for every caller
        for run in COMBOS:
            assert fill(find.target, run) == fill(red.target, run), (
                f"{red.surface}: the search reads {fill(find.target, run)!r}, the submit step wrote {fill(red.target, run)!r}")

    for index, (red, find) in enumerate(pairs):
        layout = h3.make_layout(tmp_path / f"seam{index}")
        ids = {}
        for run in (RUN_A, RUN_B):  # both submissions finish before either search runs
            proc = run_shell(prepare(red.command, run, layout), layout)
            assert proc.returncode == 0, proc.stderr
            ids[run] = proc.stdout.strip()
            assert h3.ID_RE.fullmatch(ids[run]), f"{red.surface}: the id is not on standard output: {proc.stdout!r}"
        for run in (RUN_A, RUN_B):
            found = run_shell(search_command(find, run, layout), layout)
            lines = found.stdout.splitlines()
            assert len(lines) == 1, f"{red.surface} {run}: the search must match exactly once, got {lines!r}"
            sidecar = layout.tmpdir / lines[0].split("sidecar:", 1)[1].rsplit("/", 1)[-1]
            assert sidecar.read_text(encoding="utf-8").strip() == ids[run], (
                f"{red.surface} {run}: the search returned another run's recovery file ({sidecar.name})")


def test_a_concurrent_agents_submission_cannot_write_to_a_runs_own_error_file(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-ii
    # angle: real_artifact
    """Call 1 of both runs started together: each error file holds only its own sidecar line and its search finds only its own file."""
    surfaces = _surfaces(shared_reference_layout)
    (red, *_), (find, *_) = redirects(SIGNOFF, surfaces[SIGNOFF]), searches(SIGNOFF, surfaces[SIGNOFF])
    layout = h3.make_layout(tmp_path)
    procs = [(run, start(prepare(red.command, run, layout), layout)) for run in (RUN_A, RUN_B)]
    done = {run: (p.communicate(timeout=h.RUN_TIMEOUT), p.returncode) for run, p in procs}
    assert all(rc == 0 for _out, rc in done.values()), done
    ids = {run: out[0].strip() for run, (out, _rc) in done.items()}
    files = {run: error_file(red, run, layout) for run in (RUN_A, RUN_B)}
    assert files[RUN_A] != files[RUN_B], f"both runs wrote their error stream to {files[RUN_A]}"
    for run in (RUN_A, RUN_B):
        lines = sidecar_lines(files[run])
        assert len(lines) == 1, f"{files[run]} must hold exactly one sidecar line: {files[run].read_text()!r}"
        assert files[run].read_text(encoding="utf-8").count("sidecar:") == 1
        found = run_shell(search_command(find, run, layout), layout).stdout.splitlines()
        assert found == lines, f"{run}: search returned {found!r}, expected only its own {lines!r}"
        recovery = layout.tmpdir / found[0].rsplit("/", 1)[-1]
        assert recovery.read_text(encoding="utf-8").strip() == ids[run]
    assert {r["feedback_id"] for r in h3.records(layout)} == set(ids.values())


# ---------------------------------------------------------------------------
# clause: the check counts, discovers, fails on zero, fails on a missing part
# ---------------------------------------------------------------------------

def test_check_reports_how_many_redirecting_instructions_it_inspected(shared_reference_layout):
    # covers: INF-500d-3-ii
    # angle: criterion
    """The check over the deployed layout carries an inspected count (>= the five surfaces) and prints it."""
    result = check(_surfaces(shared_reference_layout))
    assert result.inspected >= 5, result.message
    assert result.surfaces >= 5, result.message
    assert f"inspected {result.inspected} redirecting instruction" in result.message
    assert f"{result.surfaces} surface" in result.message


def test_check_discovers_a_new_redirecting_surface_without_a_hard_coded_file_list(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-ii
    # angle: discrimination
    """A new agent file that copies the pattern raises the count by one and is judged; discovery walks the tree."""
    base = _surfaces(shared_reference_layout)
    before = check(base)
    planted = {**base, "agents/brand-new-agent.md": _plant("/tmp/feedback_err.txt")}
    after = check(planted)
    assert after.inspected == before.inspected + 1, (before.message, after.message)
    assert after.surfaces == before.surfaces + 1
    assert any("brand-new-agent.md" in p for p in after.problems), "the new surface was counted but not judged"
    clean = check({**base, "agents/brand-new-agent.md": _plant(GOOD, GOOD)})
    assert clean.inspected == before.inspected + 1
    assert not any("brand-new-agent.md" in p for p in clean.problems)

    root = tmp_path / ".leafcutter"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "one.md").write_text(_plant(GOOD), encoding="utf-8")
    assert check(discover_surfaces(root)).inspected == 1
    (root / "agents" / "two.md").write_text(_plant(GOOD), encoding="utf-8")
    (root / "skills" / "deep").mkdir(parents=True)
    (root / "skills" / "deep" / "SKILL.md").write_text(_plant(GOOD), encoding="utf-8")
    assert check(discover_surfaces(root)).inspected == 3


def test_check_fails_when_zero_redirecting_instructions_are_inspected(tmp_path):
    # covers: INF-500d-3-ii
    # angle: discrimination
    """An empty tree, a missing directory and instructions with no redirected submit all fail, naming the zero count."""
    quiet = ("```bash\npython3 scripts/feedback/submit_feedback.py --ticket <ticket_path> --phase x "
             "--category complete --note n 2>/dev/null\n```\nPlain prose naming submit_feedback.py.\n")
    cases = {
        "empty tree": check({}),
        "missing directory": check(discover_surfaces(tmp_path / "does-not-exist")),
        "no redirected submit": check({"agents/quiet.md": quiet, "agents/other.md": "# nothing here\n"}),
    }
    for label, result in cases.items():
        assert not result.ok, f"{label}: the check passed having inspected nothing"
        assert result.inspected == 0, label
        assert "inspected 0 redirecting instruction" in result.message, (label, result.message)


def test_check_fails_when_a_prescribed_name_lacks_the_ticket_or_the_phase(tmp_path):
    # covers: INF-500d-3-ii
    # angle: discrimination
    """Phase only, ticket only and neither each fail by name; the conforming surface alone passes."""
    surfaces = {
        "agents/good.md": _plant(GOOD, GOOD),
        "agents/phase-only.md": _plant("/tmp/feedback_err_<agent_name>.txt"),
        "agents/ticket-only.md": _plant("/tmp/feedback_err_<ticket_basename>.txt"),
        "agents/neither.md": _plant("/tmp/feedback_err.txt"),
        "agents/path-ticket.md": _plant("/tmp/feedback_err_<ticket_path>_<agent_name>.txt"),
    }
    assert check({"agents/good.md": surfaces["agents/good.md"]}).ok
    result = check(surfaces)
    assert not result.ok and result.inspected == 5
    named = {name for name in surfaces if any(name in p for p in result.problems)}
    assert named == set(surfaces) - {"agents/good.md"}, result.message
    mismatch = check({"agents/m.md": _plant(GOOD, "/tmp/feedback_err.txt")})
    assert not mismatch.ok and "search reads" in mismatch.message, "a search/redirect mismatch must be caught"


# ---------------------------------------------------------------------------
# reachability: the prescribed commands run as written
# ---------------------------------------------------------------------------

def test_prescribed_submit_commands_run_as_written_from_the_deployed_instructions(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-ii
    # angle: reachability
    """Entry point: each deployed submit command, bash -c from a worktree root; exits 0 and leaves its per-run error file."""
    reds = [r for rel, text in sorted(_surfaces(shared_reference_layout).items()) for r in redirects(rel, text)]
    assert len(reds) >= 5
    layout = h3.make_layout(tmp_path)
    breaches = []
    for red in reds:
        files = {}
        for run in (RUN_A, RUN_B):
            proc = run_shell(prepare(red.command, run, layout), layout)
            files[run] = error_file(red, run, layout)
            if proc.returncode != 0:
                breaches.append(f"{red.surface}:{red.line} ({run.ticket}) exited {proc.returncode}: {proc.stderr[:160]!r}")
            elif len(sidecar_lines(files[run])) != 1:
                breaches.append(f"{red.surface}:{red.line} ({run.ticket}) left no error file with a sidecar line at {files[run]}")
        if files[RUN_A] == files[RUN_B]:
            breaches.append(f"{red.surface}:{red.line}: both runs wrote the one file {files[RUN_A].name}")
    assert not breaches, "\n  ".join(["a prescribed submit command did not leave a per-run error file:", *breaches])
