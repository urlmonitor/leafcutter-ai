"""
MODULE: test_inf_700b_1_ii
GOAL: RED behavioural tests for AC INF-700b-1-ii -- an agent whose knowledge-capture step cannot
    complete (the Yes-path helper command exits non-zero, e.g. its script is absent) takes the
    proceed-anyway branch AND leaves one countable ``capture_attempt`` / ``failed`` row on the
    operational telemetry stream, naming the agent, the ticket and the literal missing target.
AC: INF-700b-1-ii (source_ac); ADR-034 Amendment 2 (A2.2, A2.6); ADR-069; INF-400c-4-iii.

RE-AIMED DESIGN (architect-review 2026-10-21 16:30): ``emit_event.py`` already accepts
    ``--event capture_attempt --outcome failed --missing-target`` (ticket 02), so no Python is left to
    change. The remaining deliverable is INSTRUCTION TEXT: a ``## Failed capture attempt`` section in the
    DEPLOYED agent-telemetry SKILL.md holding the ONE command, plus pointers to it from signoff section 7
    and the three v3 emission blocks. Every behavioural test therefore lifts the command out of that
    deployed section and runs it through ``bash -c``; nothing is hand-written and nothing is imported.

WHAT IS EXPECTED TO BE RED TODAY AND WHY
    * The deployed agent-telemetry SKILL.md has no ``## Failed capture attempt`` section.
    * Signoff section 7 and the three v3 emission blocks do not name it (section 7 still says
      "not re-specified here").

REAL-ARTIFACT NOTE: prompt text comes from the DEPLOYED shared layout (``shared_reference_layout``,
    ``@pytest.mark.shared_layout_reader``); anything that writes runs from a private COPY of the
    deployed ``.leafcutter`` tree with its declaration round-tripped through ``json``.
"""
# @ac-tag: INF-700b-1-ii

from __future__ import annotations

import datetime
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from tests.knowledge.test_inf_700b_1_emit_helper import (
    _AGENT_SURFACES,
    _bind,
    _candidate_snippets,
    _deployed,
    _emission_block,
    _extract_command,
    _project,
    _run,
    _script_token,
    _section_seven,
    _snapshot,
)
from tests.knowledge.test_inf_700b_1_i import (
    _CHECKER,
    _REPO_ROOT,
    _TICKET,
    _bind_event,
    _emit_knowledge,
    _event_line,
    _ledger,
    _seed_sink,
    _stream,
    _telemetry_section,
)

_HEADING = "Failed capture attempt"
_HARVEST = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"
_COMMAND_SHAPE = re.compile(
    r"^python3 (?P<root>\S+)/skills/agent-telemetry/scripts/emit_event\.py --agent <agent> "
    r"--event capture_attempt --phase knowledge-capture --outcome failed "
    r"--missing-target '<missing target>' --ticket <ticket> \|\| true$"
)
_FORBIDDEN_IN_BASH = (("||", re.compile(r"\|\|")), ("&&", re.compile(r"&&")),
                      (";", re.compile(r";")), ("a pipe", re.compile(r"\|")))
_READ_BACK = ("import json, sys\n"
              "print(json.dumps([json.loads(ln) for ln in open(sys.argv[1], encoding='utf-8')]))\n")


# ---------------------------------------------------------------------------
# helpers: the deployed section, its one command, the failing Yes-path command
# ---------------------------------------------------------------------------

def _failed_section(layout: Path) -> str:
    """The DEPLOYED agent-telemetry SKILL.md text under ``## Failed capture attempt`` (to the next ``## ``)."""
    text = (Path(layout) / ".leafcutter" / "skills" / "agent-telemetry" / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(_HEADING)}\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, f"deployed agent-telemetry SKILL.md has no '## {_HEADING}' section"
    return match.group(1)


def _failed_line(layout: Path) -> str:
    """The section's ONE command line, checked byte-exact apart from the output root and placeholders."""
    lines = []
    for snippet in _candidate_snippets(_failed_section(layout)):
        joined = re.sub(r"\\\r?\n", " ", snippet)
        lines += [ln.strip() for ln in joined.splitlines() if "emit_event.py" in ln]
    assert len(lines) == 1, f"the section must hold exactly ONE emit_event.py command, got {lines!r}"
    match = _COMMAND_SHAPE.match(lines[0])
    assert match, f"the section's command differs from the prescribed one: {lines[0]!r}"
    nothing = _event_line(_telemetry_section(layout))
    assert nothing is not None and nothing.split()[1].startswith(match.group("root")), (
        "the failed command must use the same output root as the nothing-to-record command")
    return lines[0]


def _failing_yes_path(layout: Path, proj: dict[str, Path], tmp_path: Path) -> str:
    """Run section 7's own Yes-path command with its script absent; return the literal script path it named."""
    tokens = _extract_command(_section_seven(layout))
    assert tokens is not None, "deployed signoff section 7 names no emit_knowledge.py command"
    script = _script_token(tokens)
    (proj["project"] / script).unlink()
    helper = _run(_bind(tokens, proj["project"]), proj["project"], tmp_path)
    assert helper.returncode != 0, f"the Yes-path command must fail when its script is absent: {helper}"
    return script


def _a1_quote(value: str) -> str:
    """Single-quote *value* the ADR-034 A1.1 way: an embedded ``'`` is written ``'\\''`` (not shlex's form)."""
    return "'" + value.replace("'", "'\\''") + "'"


def _sentences(section: str) -> list[str]:
    """The section's PROSE (code fences dropped, whitespace collapsed) split into sentences."""
    prose = re.sub(r"\s+", " ", re.sub(r"```.*?```", " ", section, flags=re.DOTALL)).strip()
    return [s for s in re.split(r"(?<=[.!?])\s+", prose) if s]


def _missing_target_problems(section: str) -> list[str]:
    """H-1a: ONE sentence about ``<missing target>`` must name the first path after python3 AND say never a
    category / never a skill name (a split across two sentences does not count)."""
    for sentence in (s.lower() for s in _sentences(section) if "<missing target>" in s):
        if (re.search(r"first path after `?python3", sentence) and "emit_knowledge.py" in sentence
                and re.search(r"never (a )?category", sentence) and re.search(r"skill name", sentence)):
            return []
    return ["no single sentence about `<missing target>` names the first path after `python3` of the "
            "emit_knowledge.py command AND says it is never a category or a skill name"]


def _polarity_problems(section: str) -> list[str]:
    """H-1b + M-3: run ONLY when the helper exited non-zero; exit 0 means no record, and the helper
    "handled its own failure" (not "already recorded" it)."""
    low = [s.lower() for s in _sentences(section)]
    problems = []
    if not any(re.search(r"only when\b.*\bexit(s|ed)? non-zero", s) for s in low):
        problems.append("no sentence ties 'only when ... exited non-zero' to running the command")
    if not any(re.search(r"\bexit(s|ed)? 0\b.*\bno record\b", s) and "non-zero" not in s for s in low):
        problems.append("no sentence ties 'exits 0' to 'no record' (with non-zero absent from that sentence)")
    if "already recorded its own failure" in " ".join(low):
        problems.append("claims the helper 'already recorded its own failure' (untrue on exit 0 with an unusable declaration)")
    if "handled its own failure" not in " ".join(low):
        problems.append("does not say the helper 'handled its own failure'")
    return problems


def _failed_cmd(layout: Path, proj: dict[str, Path], missing: str, *, ticket: str | None = _TICKET,
                agent: str = "test-writer", quote=shlex.quote) -> str:
    """Bind the section's own line: only python, the script path and the angle-bracket values change."""
    line = _failed_line(layout).replace("'<missing target>'", quote(missing))
    if ticket is None:
        line = line.replace(" --ticket <ticket>", "")
    return _bind_event(line, proj["deployed"] / "skills" / "agent-telemetry" / "scripts" / "emit_event.py",
                       agent, ticket or "")


def _bash(cmd: str, proj: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=str(proj["project"]),
                          timeout=60, check=False)


def _failed_rows(proj: dict[str, Path]) -> list[dict]:
    return [r for r in _ledger(proj) if r["payload"]["outcome"] == "failed"]


def _fail_open_sentence(text: str) -> str:
    """The Yes-path ``**Fail open:**`` sentence: from the LAST marker to the next blank line or code fence."""
    start = text.rindex("**Fail open:**")
    return re.split(r"\n\s*\n|```", text[start:], maxsplit=1)[0]


def _assert_record_write_failure_is_fail_open(layout: Path, tmp_path: Path, case: str) -> None:
    """The failed command exits 0, leaves the primary output alone and says why on stderr."""
    proj = _project(tmp_path / case, layout, case)
    if case == "live":
        _stream(proj).mkdir()
    missing = "skills/knowledge/emit_knowledge.py"
    out = _bash(_failed_cmd(layout, proj, missing) + "\necho PRIMARY-OUTPUT", proj)
    assert out.returncode == 0 and out.stdout == "PRIMARY-OUTPUT\n", (case, out)
    assert out.stderr.strip(), f"{case}: the condition must be reported on stderr"
    assert "emit_event" in out.stderr and ("telemetry" in out.stderr or "declaration" in out.stderr), out.stderr


def _assert_no_forbidden_in_bash(seven: str) -> None:
    """No bash fence of signoff section 7 uses ``||``, ``&&``, ``;`` or a pipe."""
    for fence in re.findall(r"```[A-Za-z]*\n(.*?)```", seven, re.DOTALL):
        for label, pattern in _FORBIDDEN_IN_BASH:
            assert not pattern.search(fence), f"signoff section 7 bash block contains {label}: {fence!r}"


def _agent_pointer_problems(layout: Path, surfaces: dict[str, str]) -> list[str]:
    """Per v3 agent surface: the pointer says to load/invoke agent-telemetry, or the agent lists it."""
    problems = []
    for name, rel in _AGENT_SURFACES.items():
        agent_text = (_deployed(layout) / rel).read_text(encoding="utf-8")
        frontmatter = agent_text.split("---", 2)[1] if agent_text.startswith("---") else ""
        loads = re.search(r"\b(load|invoke)\b", surfaces[name], re.IGNORECASE)
        lists = re.search(r"skill_id:\s*agent-telemetry\b", frontmatter)
        if not (loads or lists):
            problems.append(f"{name}: the pointer neither says to load/invoke the agent-telemetry skill nor "
                            f"lists it in frontmatter skills:")
    return problems


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
def test_failed_capture_writes_one_record_naming_the_missing_target(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-ii
    # angle: criterion
    """Drive the proceed-anyway branch: the Yes-path helper fails, then the section's command is run.

    Exactly one ``capture_attempt`` / ``failed`` row appears, naming the agent, the ticket and the
    LITERAL script path of the failing Yes-path command (not a category, not the skill name). Wrong
    versions caught: no row; a row whose ``missing_target`` is a placeholder, the skill name or a
    category; a row with outcome ``nothing-to-record`` or an overloaded ``outcome``; two rows.
    """
    good = ("`<missing target>` is the first path after `python3` in the `emit_knowledge.py` command "
            "you ran, never a category or a skill name.")
    assert _missing_target_problems(good) == [], "control: a correct sentence passes the checker"
    for wrong in (good.replace("never a category or a skill name", "the skill name"),
                  good.replace(", never a category or a skill name", ". It is never a category or a skill name"),
                  good.replace("first path after `python3`", "name of the skill")):
        assert _missing_target_problems(wrong), f"the checker must reject the wrong version: {wrong!r}"
    assert _missing_target_problems(_failed_section(shared_reference_layout)) == []
    proj = _project(tmp_path, shared_reference_layout, "live")
    assert _failed_rows(proj) == [] and _ledger(proj) == [], "control: the ledger starts empty"
    missing = _failing_yes_path(shared_reference_layout, proj, tmp_path)
    result = _bash(_failed_cmd(shared_reference_layout, proj, missing), proj)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == "", result
    rows = _ledger(proj)
    assert len(rows) == 1, f"exactly one failure record expected, got {rows!r}"
    row = rows[0]
    assert (row["event_type"], row["agent_name"], row["ticket_path"]) == ("capture_attempt", "test-writer", _TICKET)
    assert row["payload"]["outcome"] == "failed" and row["payload"]["phase"] == "knowledge-capture", row
    assert row["payload"]["missing_target"] == missing, f"missing target must be the literal {missing!r}: {row}"
    assert missing.endswith("emit_knowledge.py") and "<" not in missing
    assert set(row["payload"]) == {"phase", "outcome", "retry_count", "missing_target"}


@pytest.mark.shared_layout_reader
def test_successful_capture_writes_no_failure_record(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-ii
    # angle: criterion
    """A completed capture adds no AGENT-run failed row, and a failed run is distinguishable by outcome.

    Three completed shapes on three private projects: the helper succeeds (one ``recorded``); the helper
    handles its OWN failed append (one ``failed`` whose target is the sink, not the helper script); the
    nothing-to-record command runs (one ``nothing-to-record``). The section must also tell the agent a
    helper that exits 0 needs no record. The control: on the nothing-to-record project, running the
    failed command adds exactly one ``failed`` beside it, so the two periods differ by outcome value.
    """
    layout = shared_reference_layout
    ok_text = ("An agent runs this only when the helper exited non-zero. A helper that exits 0, even with a "
               "warning, has handled its own failure, so add no record.")
    assert _polarity_problems(ok_text) == [], "control: correct polarity passes the checker"
    for wrong in (ok_text.replace("only when the helper exited non-zero", "only when the helper exited 0"),
                  ok_text.replace("add no record", "add a record"),
                  ok_text.replace("A helper that exits 0", "A helper that exits non-zero"),
                  ok_text.replace("handled", "already recorded")):
        assert _polarity_problems(wrong), f"the checker must reject the wrong version: {wrong!r}"
    problems = _polarity_problems(_failed_section(layout))
    assert not problems, "the section's trigger/exit-0 prose is wrong: " + "; ".join(problems)
    ok = _project(tmp_path / "ok", layout, "live")
    assert _emit_knowledge(ok, tmp_path / "ok", "A genuine learning about the capture helper.").returncode == 0
    assert [r["payload"]["outcome"] for r in _ledger(ok)] == ["recorded"]
    own = _project(tmp_path / "own", layout, "live")
    own["sink"].mkdir()
    assert _emit_knowledge(own, tmp_path / "own", "A genuine learning about the capture helper.").returncode == 0
    own_rows = _failed_rows(own)
    assert len(own_rows) == 1 and own_rows[0]["payload"]["missing_target"] == str(own["sink"]), own_rows
    assert not own_rows[0]["payload"]["missing_target"].endswith("emit_knowledge.py"), "no agent-run row here"
    quiet = _project(tmp_path / "quiet", layout, "live")
    nothing = _bind_event(_event_line(_telemetry_section(layout)) or "", quiet["deployed"] / "skills"
                          / "agent-telemetry" / "scripts" / "emit_event.py", "test-writer", _TICKET)
    assert _bash(nothing, quiet).returncode == 0
    assert [r["payload"]["outcome"] for r in _ledger(quiet)] == ["nothing-to-record"]
    for proj in (ok, quiet):
        assert _failed_rows(proj) == [], "a completed capture must leave no failure record"
    missing = _failing_yes_path(layout, quiet, tmp_path / "quiet")
    assert _bash(_failed_cmd(layout, quiet, missing), quiet).returncode == 0
    assert [r["payload"]["outcome"] for r in _ledger(quiet)] == ["nothing-to-record", "failed"]


@pytest.mark.shared_layout_reader
def test_failure_record_never_lands_in_the_knowledge_emission_sink(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-ii
    # angle: seam
    """Pipe the REAL failure record's producer into the REAL harvester: zero records read (INF-400c-4-iii).

    The knowledge sink is declared and empty. After the failed command runs, the telemetry stream has
    the row (control: the write happened) while the sink is byte-identical and the harvester CLI reports
    ``0 learnings routed`` with exit 0. Wrong version caught: the row appended to the knowledge sink.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    proj["sink"].write_text("", encoding="utf-8")
    before = _snapshot(proj["world"])
    missing = _failing_yes_path(shared_reference_layout, proj, tmp_path)
    assert _bash(_failed_cmd(shared_reference_layout, proj, missing), proj).returncode == 0
    assert len(_failed_rows(proj)) == 1, "control: the failure record was written to the telemetry stream"
    assert proj["sink"].read_bytes() == b"", "nothing may be appended to the knowledge-emission sink"
    assert _snapshot(proj["world"]) - before == {str(_stream(proj).relative_to(proj["world"]))}
    harvest = subprocess.run([sys.executable, "-B", str(_HARVEST), "--sink", str(proj["sink"]), "--state",
                              str(tmp_path / "state.json")], capture_output=True, text=True, timeout=60,
                             check=False, cwd=str(proj["project"]))
    assert harvest.returncode == 0, harvest
    assert "0 learnings routed" in harvest.stdout + harvest.stderr, (harvest.stdout, harvest.stderr)


@pytest.mark.shared_layout_reader
def test_failure_record_survives_the_process_that_wrote_it(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-ii
    # angle: real_artifact
    """Read the row back from disk in a FRESH interpreter after the writer process has exited.

    The command text comes from the deployed section, the bytes from the real emit_event.py, and the
    reader is ``python -I`` on the declared stream path: the row is durable, parseable JSON with an
    ISO-8601 timestamp, and a retried attempt is a new row (counts attempts, not agents).
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    missing = _failing_yes_path(shared_reference_layout, proj, tmp_path)
    cmd = _failed_cmd(shared_reference_layout, proj, missing)
    assert _bash(cmd, proj).returncode == 0
    fresh = subprocess.run([sys.executable, "-I", "-c", _READ_BACK, str(_stream(proj))], capture_output=True,
                           text=True, timeout=60, check=False)
    assert fresh.returncode == 0, fresh
    rows = json.loads(fresh.stdout)
    assert len(rows) == 1 and rows[0]["payload"]["outcome"] == "failed", rows
    assert rows[0]["payload"]["missing_target"] == missing and rows[0]["agent_name"] == "test-writer"
    datetime.datetime.fromisoformat(rows[0]["timestamp"])
    assert _bash(cmd, proj).returncode == 0
    assert len(_failed_rows(proj)) == 2, "a retried attempt is a new record, not an amendment"
    quoted = "/tmp/o'brien/skills/knowledge/emit_knowledge.py"
    a1 = _failed_cmd(shared_reference_layout, proj, quoted, quote=_a1_quote)
    assert "'\\''" in a1 and "'\"'\"'" not in a1, f"control: the command uses the A1.1 form: {a1!r}"
    assert _bash(a1, proj).returncode == 0
    assert [r["payload"]["missing_target"] for r in _failed_rows(proj)][-1] == quoted, "A1.1-escaped path must round-trip"
    prose = " ".join(s for s in _sentences(_failed_section(shared_reference_layout)) if "'\\''" in s)
    assert prose and "quote" in prose.lower(), (
        "the section must state the A1.1 rule: a single quote inside the path is written as `'\\''`")


@pytest.mark.shared_layout_reader
def test_capture_step_does_not_block_signoff_when_the_record_write_fails(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-ii
    # angle: failure
    """Unwritable stream or unusable declaration: exit 0, stderr says why, primary output unchanged.

    Also holds the wording that makes the branch discoverable and safe: signoff section 7's bash blocks
    use none of ``||``, ``&&``, ``;`` or a pipe; section 7 (its proceed-anyway paragraph and its Yes-path
    Fail-open sentence) and the three v3 emission blocks' Yes-path Fail-open sentences all point at the
    named section; the four-surface parity checker still resolves all four surfaces.
    """
    layout = shared_reference_layout
    for case in ("live", "stale"):
        _assert_record_write_failure_is_fail_open(layout, tmp_path, case)
    seven = _section_seven(layout)
    _assert_no_forbidden_in_bash(seven)
    paragraph = seven.rstrip().removesuffix("---").rstrip().rsplit("\n\n", 1)[-1]
    surfaces = {"signoff section 7": _fail_open_sentence(seven)}
    surfaces |= {name: _fail_open_sentence(_emission_block(layout, rel)) for name, rel in _AGENT_SURFACES.items()}
    problems = [f"{n}: Yes-path Fail-open sentence does not name '{_HEADING}' in agent-telemetry: {s!r}"
                for n, s in surfaces.items() if _HEADING not in s or "agent-telemetry" not in s]
    problems += _agent_pointer_problems(layout, surfaces)
    if _HEADING not in paragraph or "agent-telemetry" not in paragraph or "not re-specified here" in paragraph:
        problems.append(f"signoff section 7's proceed-anyway paragraph is not re-pointed: {paragraph!r}")
    assert not problems, "\n".join(problems)
    live = _project(tmp_path / "parity", layout, "live")
    parity = subprocess.run([sys.executable, "-B", str(_CHECKER), "--target-dir", str(live["project"])],
                            capture_output=True, text=True, timeout=120, check=False, cwd=str(_REPO_ROOT))
    assert parity.returncode == 0 and "Inspected 4 surfaces" in parity.stdout, (parity.stdout, parity.stderr)


@pytest.mark.shared_layout_reader
def test_inf_700b_1_ii_reachable_from_entry_point(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-ii
    # angle: reachability
    """Run the command lifted from the DEPLOYED ``## Failed capture attempt`` section, ticket omitted.

    Reached through ``bash -c`` (the line ends ``|| true``) against a declared install whose telemetry
    stream and knowledge sink are temp files: exactly one new JSONL line with event ``capture_attempt``,
    outcome ``failed``, the literal missing target and a null ticket; the knowledge sink is byte-identical.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    seeded = _seed_sink(proj)
    missing = ".leafcutter/scripts/knowledge/emit_knowledge.py"
    result = _bash(_failed_cmd(shared_reference_layout, proj, missing, ticket=None), proj)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == "", result
    rows = _ledger(proj)
    assert len(rows) == 1, f"exactly one new JSONL line on the telemetry stream, got {rows!r}"
    assert rows[0]["event_type"] == "capture_attempt" and rows[0]["payload"]["outcome"] == "failed", rows[0]
    assert rows[0]["payload"]["missing_target"] == missing and rows[0]["ticket_path"] is None, rows[0]
    assert proj["sink"].read_bytes() == seeded, "nothing new in the knowledge-emission sink"
