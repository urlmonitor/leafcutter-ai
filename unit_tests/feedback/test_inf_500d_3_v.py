"""
MODULE: test_inf_500d_3_v
GOAL: RED tests for AC INF-500d-3-v -- every instruction that records a failed feedback submission
    (the shared sign-off block, python-coder, documentation-verifier, user-surface-smoker,
    ticket-supervisor, epic-supervisor) records the reasoned marker from the run's own failure line,
    never a bare ``(submit-failed)``; ticket-supervisor no longer describes a commandless secondary
    ``--category tooling-issue`` submission.
AC: INF-500d-3-v (source_ac); depends on INF-500d-3 (vocabulary, ``submit-failed:`` line, precedence),
    INF-500d-3-ii (per-run error files) and INF-500d-3-vi (epic-supervisor keeps its error stream).

CONTRACT THIS FILE FIXES (llm-expert edits the six surfaces against it; the read-back contract is
spelled out in ``_inf_500d_3_marker``):

    1. Every submit command redirects its error stream to a per-run file (3-ii names); the shared block
       and python-coder gain that redirect.
    2. Each surface has, as its own command lines naming the SAME per-run file: a read-back that prints
       the ``submit-failed:`` line by its prefix (sed -n / awk, exit 0 when absent) and a recovery search
       that prints the ``sidecar:`` line (exit 0 when absent). No chaining, pipes or subshells.
    3. Precedence (INF-500d-3): stdout id; id in the recovery file the ``sidecar:`` line names; the
       ``submit-failed:`` line verbatim in parentheses; ``written-uncited`` with the submitted category
       when a ``sidecar:`` or ``[submit_feedback] sink:`` line exists; else ``facility-unavailable``.
       Each surface names ``written-uncited`` and ``facility-unavailable`` and carries no list of its own.
    4. No surface still says ``(submit-failed)``; ticket-supervisor's payload ``feedback_id`` documents a
       real id or the reasoned marker, and its CFCS emit contract no longer describes a tooling-issue call.

The deployed copies of the shared block are DISCOVERED at test time (the shared reference layout).
"""
# @ac-tag: INF-500d-3-v

from __future__ import annotations

import re
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_3_helpers as h3
from unit_tests.feedback._inf_500d_3_ii_check import RUN_A, fill, judge_redirect, logical_lines, redirects
from unit_tests.feedback._inf_500d_3_ii_run import run_shell
from unit_tests.feedback._inf_500d_3_marker import (
    DECOY_NEWEST_ID,
    EVENT_KINDS,
    RECOVERED_ID,
    SINK_PREFIX,
    block_copies,
    category_of,
    compound_operators,
    decide,
    distinct,
    execute,
    failure_line,
    lift_recipes,
    plant_decoys,
    reason_ids,
    remove_declaration,
    remove_entry_point,
    run_case,
    shared_block_region,
    six_surface_recipes,
)
from unit_tests.feedback._inf_500d_4_vi_helpers import _all_deployed_surfaces

pytestmark = pytest.mark.shared_layout_reader

PYC = "agents/python-coder.md"
DOCV = "agents/documentation-verifier.md"
SMOKER = "agents/user-surface-smoker.md"
SUP = "agents/ticket-supervisor.md"
EPIC = "agents/epic-supervisor.md"
SIX = (PYC, DOCV, SMOKER, SUP, EPIC)
LINE = failure_line("writer-not-allowed", "subagent-quality")
MARKER = f"({LINE})"
ERROR = "ERROR: the writer is not allowed to file this category"
BARE = re.compile(r"\(submit-failed\)")
BARE_NEGATED = re.compile(r"(?i)\b(never|do not|must not)\b[^\n]{0,60}\(submit-failed\)")
TODAY_BARE = (
    "`feedback-id: (submit-failed)` and continue — a failed submit is **not** a phase failure.",  # shared block
    "`feedback-id: (submit-failed)` and continue — a failed submit is not a phase failure.",  # python-coder
    "`(submit-failed)` as the fallback value. A failed feedback submission is NOT a phase failure",  # verifier
    "`(submit-failed)` as the fallback value.",  # smoker
    "use `(submit-failed)` as the fallback. Include `feedback_id:` in the structured",  # ticket-supervisor event
    '"feedback_id":           "<fb_YYYY-MM-DD_XXXXXXXX or (submit-failed)>"',  # payload field
    '# FB_ID=$(python scripts/feedback/submit_feedback.py 2>/dev/null) || FB_ID="(submit-failed)"',  # epic-supervisor
)
TODAY_SECONDARY = (
    "proceed with the adjudication outcome unchanged. If a secondary tooling-issue entry is\n"
    "possible (submit_feedback.py itself loaded but rejected the category), emit it with\n"
    "`--category tooling-issue` as a secondary call.\n")
_SECONDARY = re.compile(r"(?is)tooling-issue[^.]{0,200}?(secondary|submission|submit|emit|call)"
                        r"|(secondary|emit)[^.]{0,200}?tooling-issue")
_ROUTING = re.compile(r"(?i)\b(if|when)\b[^\n]{0,60}(marker|submit-failed|feedback-id)[^\n]{0,60}"
                      r"\b(stop|abort|halt|fail the|downgrade|retry|respawn)\b")


def _surfaces(layout) -> dict[str, str]:
    return _all_deployed_surfaces(layout)


def _recipes(layout) -> list:
    labelled, problems = six_surface_recipes(_surfaces(layout))
    assert not problems, "\n  ".join(["a surface carries no liftable submit command:", *problems])
    return distinct(labelled)


def _marker_problems(label: str, recipe, layout) -> list[str]:
    """Run ``recipe`` against an entry point that fails with the writer-not-allowed line; judge what is recorded."""
    if not recipe.readbacks:
        return [f"{label}: no command reads the submit-failed: line back from the per-run file"]
    out = run_case(recipe, layout, [ERROR, LINE], rc=1)
    problems = []
    if out.stdout != "":
        problems.append(f"{label}: stdout is not empty: {out.stdout!r}")
    if out.rc != 1:
        problems.append(f"{label}: the submit command's own status was masked (exit {out.rc})")
    if out.recorded != f"feedback-id: {MARKER}":
        problems.append(f"{label}: records {out.recorded!r}, expected 'feedback-id: {MARKER}'")
    return problems


def _scanned_texts(layout) -> dict[str, str]:
    """Every deployed copy of the shared block plus the full text of the five other surfaces."""
    surfaces = _surfaces(layout)
    texts = {f"{rel}#block": region for rel, region in block_copies(surfaces).items()}
    texts.update({rel: surfaces[rel] for rel in SIX})
    return texts


def _without_block(text: str) -> str:
    region = shared_block_region(text)
    return text.replace(region, "") if region else text


# ---------------------------------------------------------------------------
# the reasoned marker, surface by surface
# ---------------------------------------------------------------------------

def test_shared_signoff_block_and_every_deployed_copy_record_the_reasoned_marker(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: criterion
    """Every discovered copy of the block is lifted and run; each records the writer-not-allowed marker; all copies agree."""
    copies = block_copies(_surfaces(shared_reference_layout))
    assert len(copies) >= 5, f"only {len(copies)} deployed copies of the shared sign-off block discovered"
    lifted = {rel: lift_recipes(rel, region) for rel, region in copies.items()}
    empty = sorted(rel for rel, found in lifted.items() if not found)
    assert not empty, f"{len(empty)} copies carry no redirecting submit command, e.g. {empty[:3]}"
    signatures = {tuple((r.submit.command, r.readbacks, r.searches) for r in found) for found in lifted.values()}
    assert len(signatures) == 1, f"the {len(copies)} copies of the shared block do not agree: {len(signatures)} variants"
    layout = h3.make_layout(tmp_path)
    problems = [p for recipe in next(iter(lifted.values())) for p in _marker_problems("shared block", recipe, layout)]
    assert not problems, "\n  ".join(problems)


def test_python_coder_own_signoff_step_records_the_reasoned_marker(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: criterion
    """Every redirecting submit step in the deployed python-coder (own section and appended block) records the marker."""
    recipes = lift_recipes(PYC, _surfaces(shared_reference_layout)[PYC])
    assert recipes, "python-coder carries no redirecting submit command (no per-run error file)"
    layout = h3.make_layout(tmp_path)
    problems = [p for label, recipe in distinct([("python-coder", r) for r in recipes])
                for p in _marker_problems(label, recipe, layout)]
    problems +=[f"python-coder: {why}" for recipe in recipes for why in judge_redirect(recipe.submit)]
    assert not problems, "\n  ".join(problems)


def _own_phase_recipes(layout, rel: str, phase: str) -> list:
    found = [r for r in lift_recipes(rel, _surfaces(layout)[rel]) if f"--phase {phase}" in fill(r.submit.command, RUN_A)]
    assert found, f"{rel} carries no redirecting submit command with --phase {phase}"
    return found


def test_documentation_verifier_records_the_reasoned_marker(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: criterion
    """documentation-verifier's own submit command and read-back: the marker is the run's line in parentheses."""
    layout = h3.make_layout(tmp_path)
    problems = [p for r in _own_phase_recipes(shared_reference_layout, DOCV, "documentation-verifier")
                for p in _marker_problems("documentation-verifier", r, layout)]
    assert not problems, "\n  ".join(problems)


def test_user_surface_smoker_records_the_reasoned_marker(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: criterion
    """user-surface-smoker's own submit command and read-back: the marker is the run's line in parentheses."""
    layout = h3.make_layout(tmp_path)
    problems = [p for r in _own_phase_recipes(shared_reference_layout, SMOKER, "user-surface-smoker")
                for p in _marker_problems("user-surface-smoker", r, layout)]
    assert not problems, "\n  ".join(problems)


def _event_block(text: str, recipe) -> str:
    """The instruction text from an event's command to the next numbered case or the emit contract."""
    start = text.index(recipe.submit.command.split(" 2>")[0][:60])
    tail = text[start:]
    end = re.search(r"\n\d+\. \*\*|\n\*\*CFCS emit contract", tail)
    return tail[:end.start()] if end else tail


def _payload_field_problems(text: str) -> list[str]:
    """Problems with the blocked payload's ``feedback_id`` field line."""
    field = [ln for ln in text.splitlines() if '"feedback_id"' in ln]
    if not field:
        return ["the blocked payload block no longer documents a feedback_id field"]
    if BARE.search(field[0]) or not re.search(r"\(submit-failed:[^)]+\)", field[0]) or "fb_" not in field[0]:
        return [f"the payload feedback_id field must name a real id and the reasoned marker form: {field[0].strip()!r}"]
    return []


def _emit_contract_problems(text: str) -> list[str]:
    """Problems with the CFCS emit contract paragraph."""
    contract = re.search(r"(?s)\*\*CFCS emit contract:\*\*.*?(?:\n\s*\n|\Z)", text)
    if not contract or "submit-failed:" not in contract.group(0) or BARE.search(contract.group(0)):
        return ["the CFCS emit contract paragraph does not carry the reasoned form"]
    return []


def test_ticket_supervisor_four_events_record_the_reasoned_marker_and_the_payload_field_documents_no_bare_form(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Four event commands run and read back; the payload field, event sentences and emit contract carry the reasoned form."""
    text = _surfaces(shared_reference_layout)[SUP]
    events = [r for r in lift_recipes(SUP, text) if r.event_kind]
    assert sorted(r.event_kind for r in events) == sorted(EVENT_KINDS), [r.event_kind for r in events]
    layout = h3.make_layout(tmp_path)
    problems = [p for r in events for p in _marker_problems(f"ticket-supervisor {r.event_kind}", r, layout)]
    for r in events:
        block = _event_block(text, r)
        if "submit-failed:" not in block or BARE.search(block):
            problems.append(f"{r.event_kind}: the event's own instruction keeps its stdout-only or bare wording")
    problems += _payload_field_problems(text)
    problems += _emit_contract_problems(text)
    assert not problems, "\n  ".join(problems)


def test_epic_supervisor_cross_ticket_recipe_records_the_reasoned_marker(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: criterion
    """epic-supervisor's lifted command and read-back record the writer-not-allowed line, not a facility-unavailable default."""
    recipes = lift_recipes(EPIC, _surfaces(shared_reference_layout)[EPIC])
    assert len(recipes) == 1, f"epic-supervisor must carry exactly one redirecting submit command, found {len(recipes)}"
    problems = _marker_problems("epic-supervisor", recipes[0], h3.make_layout(tmp_path))
    assert not problems, "\n  ".join(problems)


# ---------------------------------------------------------------------------
# reason and category are copied from the run's own line
# ---------------------------------------------------------------------------

def _grid(reasons: list[str], own_category: str):
    """(stderr lines, exit status, the one failure line) -- the category differs from the command's own."""
    category = "blocker" if own_category != "blocker" else "complete"
    cases = []
    for index, reason in enumerate(reasons):
        line = failure_line(reason, category)
        cases.append(([f"ERROR: before {index}", line, f"ERROR: after {index}"], index % 3 + 1, line))
    line = failure_line("malformed-submission", category)
    cases.append((["ERROR: see submit-failed: docs", "ERROR: it said submit-failed:bogus:zzz here", line, "ERROR: end"], 2, line))
    return cases


def test_marker_reason_and_category_are_copied_from_the_runs_own_failure_line_for_every_reason(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Five reasons x exit statuses 1-3 x ERROR lines around and inside; wrong read-backs and deciders are flagged."""
    layout = h3.make_layout(tmp_path / "grid")
    reasons = reason_ids(layout)
    own = "complete"
    cases = _grid(reasons, own)
    probe = layout.tmpdir / "mut.txt"
    readbacks = {"the first line of the error file": "head -n 1 {f}", "a match anywhere in a line": "grep 'submit-failed:' {f}",
                 "the last line": "tail -n 1 {f}", "the whole file (assumes one line)": "cat {f}"}
    conforming = "sed -n 's/^\\(submit-failed:.*\\)$/\\1/p' {f}"

    def wrong(command: str) -> bool:
        for lines, _rc, line in cases:
            probe.write_text("\n".join(lines) + "\n", encoding="utf-8")
            if run_shell(command.format(f=probe), layout).stdout.splitlines() != [line]:
                return True
        return False

    assert not wrong(conforming), "control row: a prefix print must be right on every case"
    for label, command in readbacks.items():
        assert wrong(command), f"the grid cannot tell the wrong read-back apart: {label}"
    by_status = {1: "facility-unavailable", 2: "facility-unavailable", 3: "facility-unavailable"}
    deciders = {"category rebuilt from --category": lambda ln, rc: f"({ln.rsplit(':', 1)[0]}:{own})",
                "one fixed reasoned value": lambda ln, rc: f"(submit-failed:facility-unavailable:{ln.rsplit(':', 1)[1]})",
                "reason read off the exit status": lambda ln, rc: f"(submit-failed:{by_status[rc]}:{ln.rsplit(':', 1)[1]})"}
    for label, decider in deciders.items():
        assert any(decider(ln, rc) != f"({ln})" for _l, rc, ln in cases), f"the grid cannot tell the wrong decider apart: {label}"

    problems = []
    for label, recipe in _recipes(shared_reference_layout):
        if not recipe.readbacks:
            problems.append(f"{label}: no read-back command")
            continue
        for lines, rc, line in _grid(reasons, category_of(recipe.submit.command)):
            out = run_case(recipe, layout, lines, rc, category=None)
            if out.rc != rc:
                problems.append(f"{label}: exit {out.rc}, expected the entry point's own {rc}")
            if [o.splitlines() for o in out.readback_out] != [[line]] * len(recipe.readbacks):
                problems.append(f"{label} rc={rc}: the read-back returned {out.readback_out!r}, not exactly {line!r}")
            if out.recorded != f"feedback-id: ({line})":
                problems.append(f"{label} rc={rc}: records {out.recorded!r}")
    assert not problems, "\n  ".join(problems[:12])


# ---------------------------------------------------------------------------
# scans (paired with the executed recipes; never alone)
# ---------------------------------------------------------------------------

_NAMED = re.compile(r"\b((?:written|facility|destination|malformed|writer)-[a-z][a-z-]*)\b")
_REASONED = re.compile(r"submit-failed:([a-z][a-z0-9-]*):")


def _vocabulary_problems(text: str, ids: list[str]) -> list[str]:
    named = {m.group(1) for m in _REASONED.finditer(text)} | {m.group(1) for m in _NAMED.finditer(text)}
    problems = [f"names {token!r}, which is not in the vocabulary" for token in sorted(named - set(ids))]
    own_list = sorted(named & set(ids))
    if len(own_list) >= 4:
        problems.append(f"carries its own list of reasons: {own_list}")
    return problems


def test_every_reason_identifier_named_in_a_deployed_instruction_is_a_vocabulary_member(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Every named reason is a vocabulary member and the caller-detected two are named; planted wrong ones are flagged."""
    ids = reason_ids(h3.make_layout(tmp_path))
    assert _vocabulary_problems("submit-failed:made-up-reason:complete", ids), "blind to an invented reason"
    assert _vocabulary_problems("use written-but-not-captured when the id is missing", ids), "blind to a renamed identifier"
    assert _vocabulary_problems(" ".join(f"{i}," for i in ids), ids), "blind to an instruction with its own list"
    assert not _vocabulary_problems("submit-failed:writer-not-allowed:complete, written-uncited, facility-unavailable", ids)

    texts = _scanned_texts(shared_reference_layout)
    assert len(texts) >= 10, f"only {len(texts)} deployed texts scanned"
    problems = [f"{label}: {p}" for label, text in sorted(texts.items()) for p in _vocabulary_problems(text, ids)]
    for rel in SIX:
        text = texts[rel]
        problems += [f"{rel}: never names {ident!r}" for ident in ("written-uncited", "facility-unavailable") if ident not in text]
    assert not problems, "\n  ".join(problems[:15])


def _bare_offences(text: str) -> list[str]:
    return [ln.strip()[:100] for ln in text.splitlines() if BARE.search(ln) and not BARE_NEGATED.search(ln)]


def test_no_deployed_copy_of_the_six_surfaces_still_tells_the_agent_to_record_a_bare_submit_failed(
        shared_reference_layout):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Each sentence as it reads today is flagged by the scan; the reasoned form and a negated mention are not."""
    for sentence in TODAY_BARE:
        assert _bare_offences(sentence), f"the scan is blind to: {sentence!r}"
    assert not _bare_offences("record `feedback-id: (submit-failed:writer-not-allowed:complete)` and continue")
    assert not _bare_offences("<fb_YYYY-MM-DD_XXXXXXXX or (submit-failed:<reason>:<category>)>")
    assert not _bare_offences("Never record `(submit-failed)` on its own.")

    texts = _scanned_texts(shared_reference_layout)
    assert len(texts) >= 10, f"only {len(texts)} deployed texts scanned"
    offences = [f"{label}: {o}" for label, text in sorted(texts.items()) for o in _bare_offences(text)]
    assert not offences, "\n  ".join([f"{len(offences)} bare (submit-failed) instruction(s) remain:", *offences[:10]])


def test_no_deployed_instruction_surface_of_the_family_carries_a_bare_submit_failed_anywhere(
        shared_reference_layout):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Whole-text scan, prose included, of the signoff skill, the block copies, the five surfaces and live-surface-tester."""
    skill_bullet = ("- **Don't** skip the `submit_feedback.py` call (§2a). If the script fails, use "
                    "`feedback-id: (submit-failed)` and proceed — do not abort signoff.")
    assert _bare_offences(skill_bullet), "the scan is blind to the signoff skill's 'Don't skip' bullet as it reads today"
    assert not _bare_offences("use `feedback-id: (submit-failed:<reason>:<category>)` and proceed")

    surfaces = _surfaces(shared_reference_layout)
    texts = _scanned_texts(shared_reference_layout)
    texts["skills/signoff/SKILL.md"] = surfaces["skills/signoff/SKILL.md"]
    texts["agents/live-surface-tester.md"] = surfaces["agents/live-surface-tester.md"]
    assert len(texts) >= 12, f"only {len(texts)} deployed texts scanned"
    offences = [f"{label}: {o}" for label, text in sorted(texts.items()) for o in _bare_offences(text)]
    assert not offences, "\n  ".join([f"{len(offences)} bare (submit-failed) mention(s) remain:", *offences[:10]])


# ---------------------------------------------------------------------------
# the other cases of the capture precedence
# ---------------------------------------------------------------------------

def test_a_recovery_file_holding_an_id_wins_over_any_failure_marker(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """The sidecar line names a recovery file holding the id; recorded value is that id, never a marker, never a decoy."""
    layout = h3.make_layout(tmp_path)
    assert decide("", [LINE], [Path("/nonexistent")], False, "complete") == MARKER, "control: a marker without an id"
    problems = []
    for label, recipe in _recipes(shared_reference_layout):
        if not recipe.searches:
            problems.append(f"{label}: no command reads the sidecar: line back from the per-run file")
            continue
        for variant, extra in (("sidecar only", []), ("sidecar and failure line", [LINE])):
            plant_decoys(layout)
            named = layout.tmpdir / "feedback_id_777.txt"
            named.write_text(RECOVERED_ID + "\n", encoding="utf-8")
            out = run_case(recipe, layout, [ERROR, f"sidecar:{named}", *extra], rc=1)
            if out.value != RECOVERED_ID:
                problems.append(f"{label} ({variant}): records {out.recorded!r}, expected 'feedback-id: {RECOVERED_ID}'")
            if DECOY_NEWEST_ID in out.recorded or "submit-failed" in out.recorded:
                problems.append(f"{label} ({variant}): a decoy id or a marker was recorded: {out.recorded!r}")
    assert not problems, "\n  ".join(problems[:12])


def test_a_missing_or_empty_named_recovery_file_records_written_uncited_with_the_submitted_category(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Missing, empty and sink-line-only error files give written-uncited with the category of the command."""
    layout = h3.make_layout(tmp_path)
    problems = []
    for label, recipe in _recipes(shared_reference_layout):
        if not (recipe.readbacks and recipe.searches):
            problems.append(f"{label}: needs a read-back and a recovery search over the per-run file")
            continue
        for category in ("complete", "blocker", "subagent-quality"):
            plant_decoys(layout)
            named = layout.tmpdir / "feedback_id_888.txt"
            for variant in ("missing", "empty", "sink only"):
                named.unlink(missing_ok=True)
                if variant == "empty":
                    named.write_text("", encoding="utf-8")
                lines = ([ERROR, f"sidecar:{named}"] if variant != "sink only"
                         else [f"{SINK_PREFIX} {layout.tmpdir}/feedback.jsonl"])
                out = run_case(recipe, layout, lines, rc=1, category=category)
                expected = f"feedback-id: (submit-failed:written-uncited:{category})"
                if out.recorded != expected:
                    problems.append(f"{label} {variant} {category}: records {out.recorded!r}, expected {expected!r}")
    assert not problems, "\n  ".join(problems[:12])


def test_an_absent_submit_entry_point_records_facility_unavailable_with_the_submitted_category(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """With submit_feedback.py removed the error file holds none of the three lines: facility-unavailable:complete."""
    expect_none = decide("", [], [], False, "complete")
    expect_line = f"({failure_line('writer-not-allowed', 'blocker')})"
    assert expect_none == "(submit-failed:facility-unavailable:complete)"
    # wrong version -> (value with no line in the file, value with a failure line in the file)
    wrong = {"written-uncited as the default": ("(submit-failed:written-uncited:complete)", expect_line),
             "the bare form when the file holds nothing": ("(submit-failed)", expect_line),
             "facility-unavailable even when a line exists": (expect_none, "(submit-failed:facility-unavailable:blocker)"),
             "the reason chosen from exit status 2": ("(submit-failed:malformed-submission:complete)", expect_line)}
    for label, values in wrong.items():
        assert values != (expect_none, expect_line), f"the two cases cannot tell the wrong version apart: {label}"

    absent, present = h3.make_layout(tmp_path / "absent"), h3.make_layout(tmp_path / "present")
    remove_entry_point(absent)
    problems = []
    for label, recipe in _recipes(shared_reference_layout):
        if not recipe.readbacks:
            problems.append(f"{label}: no read-back command")
            continue
        gone = execute(recipe, absent, category="complete")
        held = [ln for ln in gone.err_text.splitlines() if ln.startswith(("submit-failed:", "sidecar:", SINK_PREFIX))]
        if held or gone.stdout or gone.rc == 0:
            problems.append(f"{label}: the absent entry point did not fail cleanly (rc={gone.rc}, lines={held})")
        if gone.recorded != "feedback-id: (submit-failed:facility-unavailable:complete)":
            problems.append(f"{label}: records {gone.recorded!r} for an absent entry point")
        there = run_case(recipe, present, [ERROR, failure_line("writer-not-allowed", "blocker")], rc=2, category="complete")
        if "facility-unavailable" in there.recorded:
            problems.append(f"{label}: facility-unavailable recorded although a failure line exists: {there.recorded!r}")
    assert not problems, "\n  ".join(problems[:12])


# ---------------------------------------------------------------------------
# fail-open: the recording never changes the sign-off or the route
# ---------------------------------------------------------------------------

def _routing_offences(text: str) -> list[str]:
    return [s.strip()[:100] for s in re.split(r"(?<=[.!?])\s+|\n", text)
            if _ROUTING.search(s) and not re.search(r"(?i)\b(never|not|must not|no|without)\b", s)]


def test_failed_submission_recipes_leave_the_signoff_and_the_route_untouched(shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Read-backs exit 0, the submit status is unmasked, no command chains or pipes, no step routes on the marker."""
    assert _routing_offences("When the marker is written, stop sign-off."), "the scan is blind to an abort on the marker"
    assert _routing_offences("If the marker is recorded, respawn the failing agent again.")
    assert not _routing_offences("Record the marker and continue; never stop sign-off because of it.")
    assert compound_operators("sed -n 'p' f | head") and compound_operators("a && b") and compound_operators("x $(y)")
    assert not compound_operators("python3 s.py --note \"a | b; c\" 2>/tmp/f.txt")

    layout = h3.make_layout(tmp_path)
    problems = []
    for label, recipe in _recipes(shared_reference_layout):
        commands = [recipe.submit.command, *recipe.readbacks, *recipe.searches]
        problems += [f"{label}: {c[:60]!r} chains, pipes or opens a subshell: {compound_operators(c)}" for c in commands
                     if compound_operators(c)]
        if not recipe.readbacks:
            problems.append(f"{label}: no read-back command")
            continue
        for variant, lines in (("failure line", [ERROR, LINE]), ("no line at all", [ERROR]),
                               ("sidecar line only", [f"sidecar:{layout.tmpdir}/feedback_id_999.txt"])):
            out = run_case(recipe, layout, lines, rc=3)
            if out.rc != 3:
                problems.append(f"{label} ({variant}): the submit status was masked: {out.rc}")
            bad = [rc for rc in (*out.readback_rc, *out.search_rc) if rc != 0]
            if bad:
                problems.append(f"{label} ({variant}): a read command exited {bad} (a grep that exits 1 on no match?)")
    for rel, text in _scanned_texts(shared_reference_layout).items():
        problems += [f"{rel}: routes on the marker: {o}" for o in _routing_offences(text)]
    assert not problems, "\n  ".join(problems[:12])


# ---------------------------------------------------------------------------
# ticket-supervisor: every described submission has a command; the secondary one is gone
# ---------------------------------------------------------------------------

def _prose_submissions(text: str) -> list[str]:
    """Lines that describe a feedback submission without being one of the lifted commands."""
    found = []
    for _number, logical in logical_lines(text):
        if "submit_feedback.py" in logical:
            continue
        if re.search(r"--category\s+\S+", logical) or re.search(
                r"(?i)secondary[^\n]{0,80}(call|submission|entry|emit)|(emit|submit)[^\n]{0,80}secondary", logical):
            found.append(logical.strip()[:100])
    return found


def test_every_feedback_submission_ticket_supervisor_describes_is_given_with_its_command(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: discrimination
    """Exactly four commands, each with its per-run file and read-back; no prose describes a submission with none."""
    assert _prose_submissions(TODAY_SECONDARY), "the enumeration is blind to the secondary tooling-issue sentence"
    assert not _prose_submissions("python3 scripts/feedback/submit_feedback.py --category subagent-quality 2>/tmp/x.txt")

    text = _without_block(_surfaces(shared_reference_layout)[SUP])
    events = [r for r in lift_recipes(SUP, text) if r.event_kind]
    assert sorted(r.event_kind for r in events) == sorted(EVENT_KINDS), f"expected exactly the four event commands: {events}"
    assert len(redirects("ticket-supervisor", text)) == 4, "ticket-supervisor must carry exactly four submit commands"
    bare = [r.event_kind for r in events if not r.readbacks]
    assert not bare, f"events without a read-back of their own per-run file: {bare}"
    prose = _prose_submissions(text)
    assert not prose, "\n  ".join(["a submission is described with no command:", *prose])


def test_the_secondary_tooling_issue_submission_is_gone_and_the_emit_contract_still_reads_true(
        shared_reference_layout):
    # covers: INF-500d-3-v
    # angle: discrimination
    """No description of a secondary tooling-issue call; four commands remain; the contract still says non-blocking."""
    assert _SECONDARY.search(TODAY_SECONDARY), "the scan is blind to the sentence as it reads today"
    assert not _SECONDARY.search("All four emit calls are non-blocking side-effects; the outcome is unchanged.")

    text = _without_block(_surfaces(shared_reference_layout)[SUP])
    hits = [m.group(0).strip()[:100] for m in _SECONDARY.finditer(text)]
    assert not hits, "\n  ".join(["ticket-supervisor still describes a tooling-issue submission:", *hits])
    lifted = [r.command for r in redirects("ticket-supervisor", text)]
    assert len(lifted) == 4 and not any("tooling-issue" in ln for ln in lifted), "the four event commands must remain, none for tooling-issue"
    contract = re.search(r"(?s)\*\*CFCS emit contract:\*\*.*?(?:\n\s*\n|\Z)", text)
    assert contract, "the CFCS emit contract paragraph is gone"
    paragraph = contract.group(0)
    assert re.search(r"(?i)non-blocking", paragraph) and re.search(r"(?i)unchanged", paragraph), paragraph
    assert "secondary" not in paragraph.lower(), "a dangling sentence about the secondary call remains"


# ---------------------------------------------------------------------------
# reachability: the real submit script
# ---------------------------------------------------------------------------

def test_lifted_recipes_run_against_the_real_submit_script_and_read_back_its_own_failure_line(
        shared_reference_layout, tmp_path):
    # covers: INF-500d-3-v
    # angle: reachability
    """No sink declaration: the real script writes destination-unwritable; the read-back and marker follow; a declared sink yields an id."""
    broken, healthy = h3.make_layout(tmp_path / "undeclared"), h3.make_layout(tmp_path / "declared")
    remove_declaration(broken)
    problems = []
    for label, recipe in _recipes(shared_reference_layout):
        if not recipe.readbacks:
            problems.append(f"{label}: no read-back command")
            continue
        out = execute(recipe, broken)
        expected = f"(submit-failed:destination-unwritable:{out.category})"
        if out.failure_lines != [expected[1:-1]] or out.recorded != f"feedback-id: {expected}":
            problems.append(f"{label}: wrote {out.err_text!r}, recorded {out.recorded!r}, expected {expected!r}")
        ok = execute(recipe, healthy)
        if not h3.ID_RE.fullmatch(ok.stdout.strip()) or ok.failure_lines:
            problems.append(f"{label}: the control run with a declared sink gave {ok.stdout!r} and {ok.failure_lines}")
    assert not problems, "\n  ".join(problems[:12])
