"""
MODULE: test_inf_500d_3_vi
GOAL: RED tests for AC INF-500d-3-vi -- epic-supervisor keeps its cross-ticket-pattern submission's
    error stream in a per-run file and records the script's own reason, not a default.
AC: INF-500d-3-vi (source_ac); depends on INF-500d-3 (the ``submit-failed:`` line) and INF-500d-3-ii
    (the per-run error-file naming rule).

CONTRACT THIS FILE FIXES (llm-expert edits templates/agents/epic-supervisor.md against it):

    1. The cross-ticket pattern submission is ONE runnable shell command (not a ``#``-commented line in
       the Python pseudo-code), beginning ``python3``, with no ``$(...)`` capture and no ``||`` fallback.
    2. Its error stream goes to ``/tmp/feedback_err_<ticket basename placeholder>_epic-supervisor_cross-ticket-pattern.txt``
       with a placeholder the INF-500d-3-ii fill replaces (underscore spelling, ``ticket`` plus ``basename``
       or ``name``), the ticket being the one the command's own ``--ticket`` argument names.
    3. A separate command line reads the ``submit-failed:`` line of that same file by its prefix and
       exits 0 (see ``_inf_500d_3_marker`` for the full read-back contract).
    4. No epic-supervisor step sends a submission's error stream to /dev/null, a merged stream, a pipe or
       a deleted path, and the blocked payloads surfaced to the user never change with the submission.

The prompt text comes from the DEPLOYED copy in the shared reference layout (no build.py here).
"""
# @ac-tag: INF-500d-3-vi

from __future__ import annotations

import dataclasses
import re

import pytest

from unit_tests.feedback import _inf_500d_3_helpers as h3
from unit_tests.feedback._inf_500d_3_ii_check import (
    TICKET_A,
    TICKET_B,
    Run,
    check,
    collisions,
    fill,
    judge_redirect,
    logical_lines,
    name_problems,
    redirects,
)
from unit_tests.feedback._inf_500d_3_ii_run import error_file, prepare, run_shell
from unit_tests.feedback._inf_500d_3_marker import (
    _QUOTED,
    execute,
    failure_line,
    lift_recipes,
    remove_declaration,
    run_case,
)
from unit_tests.feedback._inf_500d_4_vi_helpers import _all_deployed_surfaces

pytestmark = pytest.mark.shared_layout_reader

EPIC = "agents/epic-supervisor.md"
PHASE = "epic-supervisor"
EVENT = "cross-ticket-pattern"
CATEGORY = "subagent-quality"
LINE = failure_line("destination-unwritable", CATEGORY)
MARKER = f"({LINE})"
FORBIDDEN = (f"(submit-failed:facility-unavailable:{CATEGORY})", "(submit-failed)")
ERROR_LINE = "ERROR: destination could not be written"
GOOD = ('python3 scripts/feedback/submit_feedback.py --ticket "<affected_ticket_path>" --phase epic-supervisor '
        '--category subagent-quality --tags "agent-<phase>,cross-ticket-pattern,n-<count>" --note "x" '
        "2>/tmp/feedback_err_<affected_ticket_basename>_epic-supervisor_cross-ticket-pattern.txt")


def _epic_text(layout) -> str:
    return _all_deployed_surfaces(layout)[EPIC]


def _the_recipe(layout):
    recipes = lift_recipes(EPIC, _epic_text(layout))
    assert len(recipes) == 1, (
        f"epic-supervisor must carry exactly one redirecting cross-ticket submit command, found {len(recipes)}")
    return recipes[0]


def _run(ticket: str) -> Run:
    return Run(PHASE, ticket)


def _command_problems(command: str) -> list[str]:
    """Why ``command`` cannot be lifted and run as written by the INF-500d-3-ii harness."""
    problems = []
    stripped = command.lstrip()
    if stripped.startswith("#"):
        problems.append("hash-commented: bash runs it as nothing")
    if not stripped.startswith("python3 "):
        problems.append("does not begin with python3")
    if "$(" in command and "||" in command:
        problems.append("dollar-parenthesis capture with a double-pipe fallback")
    found = redirects("probe", command.lstrip("# "))
    if not found:
        problems.append("no error-stream redirect to a file")
    for red in found:
        problems += judge_redirect(red)
    return problems


def _hidden_stream(logical: str) -> list[str]:
    """Ways a line sends a submission's error stream somewhere it cannot be read back."""
    problems = []
    bare = _QUOTED.sub("", logical)
    if "submit_feedback.py" in logical:
        if re.search(r"2>\s*/dev/null", logical):
            problems.append("error stream to /dev/null")
        if re.search(r"2>&[\d-]|&>", logical):
            problems.append("error stream merged into stdout or closed")
        if "|" in bare:
            problems.append("error stream (or stdout) piped to another command")
    if re.search(r"\brm\b", bare) and "feedback_err" in logical:
        problems.append("per-run error file removed")
    return problems


# ---------------------------------------------------------------------------
# discovery and naming
# ---------------------------------------------------------------------------

def test_epic_supervisor_submission_is_discovered_and_names_a_per_run_error_file_for_its_ticket(
        shared_reference_layout):
    # covers: INF-500d-3-vi
    # angle: criterion
    """AC-1: exactly one redirecting command is discovered; its name differs per ticket and carries ticket, phase, event."""
    text = _epic_text(shared_reference_layout)
    found = redirects(EPIC, text)
    assert len(found) == 1, f"redirects() must discover exactly one epic-supervisor submit command, got {len(found)}"
    red = found[0]
    names = {t: fill(red.target, _run(t)) for t in (TICKET_A, TICKET_B)}
    assert names[TICKET_A] != names[TICKET_B], f"two tickets resolve to one file: {names}"
    assert not collisions(red.target, red.command)
    arg = re.search(r'--ticket\s+"?([^"\s]+)"?', red.command)
    assert arg, f"the command names no --ticket: {red.command!r}"
    for ticket, name in names.items():
        assert not name_problems(name, ticket, PHASE), name_problems(name, ticket, PHASE)
        assert EVENT in name, f"the event kind {EVENT!r} is missing from {name!r}"
        assert fill(arg.group(1), _run(ticket)).endswith(f"{ticket}.md"), "the --ticket argument names another ticket"
    assert not check({EPIC: text}).problems, check({EPIC: text}).message


# ---------------------------------------------------------------------------
# run as written
# ---------------------------------------------------------------------------

def test_lifted_epic_supervisor_command_runs_as_written_and_leaves_the_error_stream_in_its_file(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-vi
    # angle: real_artifact
    """The lifted command (bash, confined TMPDIR) leaves exactly the entry point's two stderr lines in its per-run file."""
    recipe = _the_recipe(shared_reference_layout)
    layout = h3.make_layout(tmp_path)
    out = run_case(recipe, layout, [ERROR_LINE, LINE], rc=1, run=_run(TICKET_A))
    command = recipe.submit.command
    assert command.startswith("python3 ") and "$(" not in command and "||" not in command, command
    assert out.stdout == "", f"stdout must stay empty: {out.stdout!r}"
    assert out.rc == 1, f"the entry point's own non-zero status was masked: {out.rc}"
    assert out.err_file == error_file(recipe.submit, _run(TICKET_A), layout)
    assert out.err_file.is_file(), f"the per-run file {out.err_file} was not written"
    assert out.err_text.splitlines() == [ERROR_LINE, LINE], out.err_text


def test_the_lifted_command_is_a_single_simple_runnable_shell_command_the_3_ii_check_accepts(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-vi
    # angle: discrimination
    """No hash-commented fragments, python3, the whole 3-ii check passes with epic-supervisor counted, exits like the script."""
    # Control rows first: each wrong version is refused by the same predicate; the conforming command is not.
    assert _command_problems(GOOD) == []
    wrong = {
        "hash-commented": "# " + GOOD,
        "python": GOOD.replace("python3", "python", 1),
        "capture with fallback": f'FB_ID=$({GOOD}) || FB_ID="x"',
        "path placeholder": GOOD.replace("<affected_ticket_basename>", "<any_affected_ticket_path>"),
        "hyphenated placeholder": GOOD.replace("<affected_ticket_basename>", "<affected-ticket-basename>"),
    }
    for label, command in wrong.items():
        assert _command_problems(command), f"the predicate is blind to: {label}"

    surfaces = _all_deployed_surfaces(shared_reference_layout)
    text = surfaces[EPIC]
    commented = [ln for _n, ln in logical_lines(text) if "submit_feedback.py" in ln and ln.startswith("#")]
    assert not commented, f"a hash-commented submission is left in epic-supervisor: {commented[0][:120]!r}"
    old_python = [ln for _n, ln in logical_lines(text) if "submit_feedback.py" in ln and re.search(r"\bpython\s", ln)]
    assert not old_python, f"python instead of python3: {old_python[0][:120]!r}"
    red = redirects(EPIC, text)
    assert len(red) >= 1, "the 3-ii check inspects no epic-supervisor redirect"
    assert _command_problems(red[0].command) == [], _command_problems(red[0].command)
    result = check(surfaces)
    assert result.ok, result.message

    recipe = _the_recipe(shared_reference_layout)
    failing = run_case(recipe, h3.make_layout(tmp_path / "fail"), [ERROR_LINE, LINE], rc=1, run=_run(TICKET_A))
    assert failing.rc == 1
    healthy = h3.make_layout(tmp_path / "ok")
    proc = run_shell(prepare(recipe.submit.command, _run(TICKET_A), healthy), healthy)
    assert proc.returncode == 0, proc.stderr
    assert h3.ID_RE.fullmatch(proc.stdout.strip()), proc.stdout


# ---------------------------------------------------------------------------
# the read-back records the script's own reason
# ---------------------------------------------------------------------------

def test_read_back_records_destination_unwritable_from_the_kept_error_file(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-vi
    # angle: criterion
    """After the failing run the lifted read-back returns the run's own line; another ticket's file is never read."""
    recipe = _the_recipe(shared_reference_layout)
    assert recipe.readbacks, "epic-supervisor has no command that reads the submit-failed: line back from the kept file"
    layout = h3.make_layout(tmp_path)
    decoy = error_file(recipe.submit, _run(TICKET_B), layout)
    decoy.write_text(failure_line("facility-unavailable", CATEGORY) + "\n", encoding="utf-8")
    out = run_case(recipe, layout, [ERROR_LINE, LINE], rc=1, run=_run(TICKET_A))
    assert out.readback_rc == [0] * len(recipe.readbacks), f"a read-back exited non-zero: {out.readback_rc}"
    assert [o.splitlines() for o in out.readback_out] == [[LINE]] * len(recipe.readbacks), out.readback_out
    assert out.value == MARKER
    assert out.recorded == f"feedback-id: {MARKER}"
    assert decoy.read_text(encoding="utf-8").strip() == failure_line("facility-unavailable", CATEGORY)


def test_swapping_in_the_facility_unavailable_fallback_over_a_dev_null_redirect_is_caught(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-vi
    # angle: discrimination
    """Mutants (/dev/null, merged stream, bare fallback) fail the assertions the deployed text passes."""
    recipe = _the_recipe(shared_reference_layout)

    def passes(value: str) -> bool:
        return value == MARKER and value not in FORBIDDEN

    deployed = run_case(recipe, h3.make_layout(tmp_path / "real"), [ERROR_LINE, LINE], rc=1, run=_run(TICKET_A))
    assert passes(deployed.value), f"the deployed text records {deployed.value!r}, not {MARKER!r}"

    def mutated(label: str, pattern: str):
        command = re.sub(r"2>\s*\S+", pattern, recipe.submit.command)
        assert command != recipe.submit.command, f"cannot mutate the redirect for {label}"
        swapped = dataclasses.replace(recipe, submit=dataclasses.replace(recipe.submit, command=command))
        return run_case(swapped, h3.make_layout(tmp_path / label), [ERROR_LINE, LINE], rc=1, run=_run(TICKET_A))

    for label, pattern in (("devnull", "2>/dev/null"), ("merged", "2>&1")):
        assert not passes(mutated(label, pattern).value), f"the {label} mutant still records {MARKER!r}"
    assert not passes("(submit-failed)"), "the bare fallback must fail the assertions"
    by_status = {1: "facility-unavailable"}
    assert not passes(f"(submit-failed:{by_status[1]}:{CATEGORY})"), "a reason read off the exit status"


# ---------------------------------------------------------------------------
# no step hides the error stream
# ---------------------------------------------------------------------------

def test_no_step_in_epic_supervisor_discards_or_hides_a_submission_error_stream(shared_reference_layout):
    # covers: INF-500d-3-vi
    # angle: discrimination
    """Scan every logical line (comments and pseudo-code included); positive controls prove each wrong form is flagged."""
    controls = {
        "/dev/null": GOOD.replace("2>/tmp/feedback_err_<affected_ticket_basename>_epic-supervisor_cross-ticket-pattern.txt",
                                  "2>/dev/null"),
        "merged stream": GOOD.replace("2>/tmp/", "2>&1 /tmp/"),
        "pipe": GOOD + " | tee /tmp/x.txt",
        "closed descriptor": GOOD.replace("2>/tmp/", "2>&- /tmp/"),
    }
    for label, planted in controls.items():
        assert _hidden_stream(planted), f"the scan is blind to: {label}"
    assert _hidden_stream("rm /tmp/feedback_err_<affected_ticket_basename>_epic-supervisor_cross-ticket-pattern.txt")
    assert _hidden_stream(GOOD) == [], "the scan flags a conforming per-run file"

    text = _epic_text(shared_reference_layout)
    submit_lines = [(n, ln) for n, ln in logical_lines(text) if "submit_feedback.py" in ln]
    assert submit_lines, "epic-supervisor carries no submit_feedback.py command at all"
    assert redirects(EPIC, text), "no epic-supervisor submission redirects to a readable per-run file"
    offences = [f"{n}: {why}" for n, ln in logical_lines(text) for why in _hidden_stream(ln)]
    assert not offences, "\n  ".join(["epic-supervisor hides a submission's error stream:", *offences])


# ---------------------------------------------------------------------------
# the surfaced payloads do not depend on the submission
# ---------------------------------------------------------------------------

_PAYLOAD_RULES = {
    "writes the marker into a child payload": re.compile(
        r"(?i)(payload|child)[^\n]{0,60}feedback_id[^\n]{0,40}(=|\bset\b|\bwrite\b|\brecord\b|\bcarr)"
        r"|(\bset\b|\bwrite\b|\bput\b)[^\n]{0,40}(marker|FB_ID)[^\n]{0,40}(payload|feedback_id)"
        r"|(\bset\b|\bwrite\b|\bput\b)[^\n]{0,60}feedback_id[^\n]{0,80}(payload|child)"),
    "surfaces payloads only after a successful submission": re.compile(
        r"(?i)(only (after|if|when)|once)[^\n]{0,60}(submission|submit_feedback|submit)[^\n]{0,40}(succe|exit 0|ok\b)"),
    "halts when the marker is recorded": re.compile(
        r"(?i)\b(if|when)\b[^\n]{0,60}(marker|submit-failed|FB_ID)[^\n]{0,60}\b(halt|stop|abort)\b"),
}


def _routing_offences(text: str) -> list[str]:
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if re.search(r"(?i)\b(never|not|must not|no)\b", sentence):
            continue
        found += [f"{label}: {sentence.strip()[:100]!r}" for label, rule in _PAYLOAD_RULES.items() if rule.search(sentence)]
    return found


def test_blocked_payload_rule_is_identical_when_the_submission_fails_or_succeeds(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-vi
    # angle: discrimination
    """Both recipes are run for real; the instruction keeps the marker out of every payload and the non-blocking contract."""
    controls = ('Set the feedback_id field of each child payload to the marker.',
                'payload["feedback_id"] = FB_ID',
                "Surface the blocked payloads only after the submission succeeded.",
                "If the marker is recorded, halt the drive.")
    for planted in controls:
        assert _routing_offences(planted), f"the scan is blind to: {planted!r}"
    assert not _routing_offences("Surface the blocked payloads. The marker is never written into a payload.")

    recipe = _the_recipe(shared_reference_layout)
    failing = run_case(recipe, h3.make_layout(tmp_path / "fail"), [ERROR_LINE, LINE], rc=1, run=_run(TICKET_A))
    assert failing.stdout == "" and failing.rc == 1
    healthy_layout = h3.make_layout(tmp_path / "ok")
    healthy = execute(recipe, healthy_layout, _run(TICKET_A))
    assert h3.ID_RE.fullmatch(healthy.stdout.strip()), f"the successful run printed no id: {healthy.stdout!r}"
    assert healthy.failure_lines == [], f"a successful run left a failure line: {healthy.failure_lines}"

    text = _epic_text(shared_reference_layout)
    assert re.search(r"(?is)must not alter the blocked payload", text), "the non-blocking contract paragraph is gone"
    assert re.search(r"(?i)unchanged", text), "the user-facing output is no longer stated unchanged"
    offences = _routing_offences(text)
    assert not offences, "\n  ".join(["epic-supervisor routes on the submission:", *offences])


# ---------------------------------------------------------------------------
# reachability
# ---------------------------------------------------------------------------

def test_epic_supervisor_recipe_reachable_as_bash_against_the_real_submit_script(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-vi
    # angle: reachability
    """The real submit_feedback.py with no sink declaration writes its own line; the read-back and marker follow."""
    recipe = _the_recipe(shared_reference_layout)
    assert recipe.readbacks, "no lifted read-back to follow the real script's failure line"
    broken = h3.make_layout(tmp_path / "undeclared")
    remove_declaration(broken)
    out = execute(recipe, broken, _run(TICKET_A))
    assert out.stdout == "" and out.rc != 0, (out.stdout, out.rc)
    assert out.failure_lines == [LINE], f"read-back returned {out.failure_lines!r}; the script wrote {out.err_text!r}"
    assert out.value == MARKER

    control = h3.make_layout(tmp_path / "declared")
    ok = execute(recipe, control, _run(TICKET_A))
    assert h3.ID_RE.fullmatch(ok.stdout.strip()), ok.stdout
    assert ok.failure_lines == [], ok.err_text
    assert any(ln.startswith("sidecar:") for ln in ok.err_text.splitlines()), ok.err_text
