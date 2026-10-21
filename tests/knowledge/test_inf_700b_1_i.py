"""
MODULE: test_inf_700b_1_i
GOAL: RED behavioural tests for AC INF-700b-1-i -- an agent with nothing to record leaves no
    knowledge record, yet leaves a durable capture-ATTEMPT record (outcome ``nothing-to-record``)
    on the operational telemetry stream, so silence in the knowledge sink means silence in the
    learning and a broken dispatch stays distinguishable from a quiet week.
AC: INF-700b-1-i (source_ac); ADR-034 Amendment 2 (A2.1-A2.7); ADR-069.

WHAT IS EXPECTED TO BE RED TODAY AND WHY
    * ``emit_event.py`` has no ``missing_target`` key and validates no ``capture_attempt`` outcome.
    * The DEPLOYED signoff section 7 and the three v3 emission blocks name no
      ``emit_event.py ... --event capture_attempt ... --outcome nothing-to-record`` command.
    * ``emit_knowledge.py`` appends empty / whitespace-only / metadata-only text, and writes no
      ``recorded`` capture attempt after a successful append.

REAL-ARTIFACT NOTE: prompt text is read from the DEPLOYED shared reference layout
    (``shared_reference_layout``, ``@pytest.mark.shared_layout_reader``); anything that writes runs
    from a private COPY of the deployed ``.leafcutter`` tree whose declaration is the deployed
    ``knowledge_sink.json`` round-tripped through ``json``. The scripts always run as fresh
    subprocesses (the no-learning commands through a real ``bash -c``); nothing is imported.
"""
# @ac-tag: INF-700b-1-i

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from tests.knowledge.test_inf_700b_1_emit_helper import (
    _AGENT_SURFACES,
    _HELPER_REL,
    _candidate_snippets,
    _emission_block,
    _project,
    _run,
    _section_seven,
    _snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECKER = _REPO_ROOT / "scripts" / "ci" / "check_sink_parity.py"
_EVENT_REL = Path("skills") / "agent-telemetry" / "scripts" / "emit_event.py"
_SURFACE_NAMES = ("signoff section 7", "product-owner", "business-analyst", "it-po")
# The agent each no-learning command records: section 7 carries the `<agent>` placeholder (bound to
# test-writer below); the product-owner block hard-codes its own name.
_SURFACE_AGENT = {"signoff section 7": "test-writer", "product-owner": "product-owner"}
_SEED = json.dumps({"event": "knowledge_captured", "agent": "seed", "text": "already here"}) + "\n"
_TICKET = "tickets/TICKET-probe.md"
_LEARNING = "The capture helper needs the declaration present before the first emit."
_EMIT_ARGS = ("--agent", "test-writer", "--component", "knowledge_system", "--destination",
              "(unrouted)", "--entry-kind", "unclassified", "--ticket", _TICKET)


# ---------------------------------------------------------------------------
# helpers: surfaces, command extraction, private project, reading the ledger
# ---------------------------------------------------------------------------

# Signoff section 7 no longer carries the command inline (BO-210c-1-iii forbids `||` in signoff bash
# blocks; INF-500d-4-vi requires it on every emit_event command). It points at this heading in the
# agent-telemetry skill, which holds the one command.
_TELEMETRY_HEADING = "Nothing-to-record capture attempt"


def _telemetry_section(layout: Path) -> str:
    """The DEPLOYED agent-telemetry SKILL.md section that carries the nothing-to-record command."""
    text = (Path(layout) / ".leafcutter" / "skills" / "agent-telemetry" / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(_TELEMETRY_HEADING)}\s*$(.*?)(?=^## |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    assert match, f"deployed agent-telemetry SKILL.md has no '## {_TELEMETRY_HEADING}' section"
    return match.group(1)


def _section_seven_pointer_problems(layout: Path) -> list[str]:
    """Section 7's no-learning branch must hold NO inline emit_event command and must name the anchor."""
    body = _section_seven(layout)
    start = body.index("**No path**")
    branch = body[start: body.index("**Yes path**", start)]
    problems = []
    if "emit_event.py" in branch:
        problems.append("signoff section 7's no-learning branch still carries an inline emit_event.py command")
    if "agent-telemetry" not in branch or _TELEMETRY_HEADING not in branch:
        problems.append(f"signoff section 7's no-learning branch does not name the agent-telemetry skill "
                        f"and its '{_TELEMETRY_HEADING}' section")
    return problems


def _surface(layout: Path, name: str) -> str:
    """Where the surface's no-learning COMMAND lives: telemetry skill for section 7, the agent block for S9."""
    if name == "signoff section 7":
        return _telemetry_section(layout)
    return _emission_block(layout, _AGENT_SURFACES[name])


def _event_line(text: str) -> str | None:
    """The raw shell line of the ``emit_event.py ... capture_attempt ... nothing-to-record`` command, or ``None``."""
    for snippet in _candidate_snippets(text):
        if all(token in snippet for token in ("emit_event.py", "--event capture_attempt", "nothing-to-record")):
            joined = re.sub(r"\\\r?\n", " ", snippet)
            for line in joined.splitlines():
                if "emit_event.py" in line:
                    return re.sub(r"[\[\]]", " ", line).strip()
    return None


def _bind_event(line: str, helper: Path, agent: str, ticket: str) -> str:
    """Make the surface's own line runnable: only python, the script path and angle-bracket values change.

    A hard-coded ``--agent <name>`` (the S9 blocks) is left alone; only the ``<agent>`` placeholder is bound.
    """
    cmd = re.sub(r"\S*emit_event\.py", shlex.quote(str(helper)), line, count=1)
    cmd = re.sub(r"^python3?\b", shlex.quote(sys.executable) + " -B", cmd)
    cmd = cmd.replace("<agent>", agent).replace("<ticket>", ticket)
    leftover = re.findall(r"<[^>\s]+>", cmd)
    assert not leftover, f"unfilled placeholders {leftover} in {line!r}"
    return cmd


def _stream(proj: dict[str, Path]) -> Path:
    declaration = json.loads((proj["deployed"] / "config" / "knowledge_sink.json").read_text(encoding="utf-8"))
    return Path(declaration["operational_telemetry_stream"])


def _ledger(proj: dict[str, Path]) -> list[dict]:
    stream = _stream(proj)
    if not stream.exists():
        return []
    return [json.loads(ln) for ln in stream.read_text(encoding="utf-8").splitlines()]


def _seed_sink(proj: dict[str, Path]) -> bytes:
    proj["sink"].write_text(_SEED, encoding="utf-8")
    return proj["sink"].read_bytes()


def _emit_knowledge(proj: dict[str, Path], tmp_path: Path, text: str, *, entry_kind: str = "unclassified",
                    ) -> subprocess.CompletedProcess[str]:
    args = list(_EMIT_ARGS)
    args[args.index("--entry-kind") + 1] = entry_kind
    argv = [sys.executable, "-B", str(proj["deployed"] / _HELPER_REL), *args, "--text", text]
    return _run(argv, proj["project"], tmp_path)


def _assert_one_attempt(proj: dict[str, Path], outcome: str, agent: str) -> dict:
    records = _ledger(proj)
    assert len(records) == 1, f"the telemetry stream must hold exactly one line, got {records!r}"
    record = records[0]
    assert record["event_type"] == "capture_attempt", record
    assert record["payload"]["outcome"] == outcome, record
    assert record["agent_name"] == agent, record
    assert record["payload"]["missing_target"] is None, record
    return record


# ---------------------------------------------------------------------------
# the writer, from its real entry point
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
def test_inf_700b_1_i_reachable_from_entry_point(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-i
    # angle: reachability
    """Run the DEPLOYED emit_event.py as a subprocess for the no-learning branch (no ``--log``).

    One ``capture_attempt`` / ``nothing-to-record`` record lands on the declared telemetry stream
    with the uniform payload keys (``missing_target`` null), the knowledge sink is byte-identical,
    and a bad outcome through the same entry point writes nothing (control: the good call wrote).
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    seeded = _seed_sink(proj)
    argv = [sys.executable, "-B", str(proj["deployed"] / _EVENT_REL), "--agent", "test-writer",
            "--event", "capture_attempt", "--phase", "knowledge-capture", "--outcome", "nothing-to-record",
            "--ticket", _TICKET]
    result = _run(argv, proj["project"], tmp_path)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == "", (result.stdout, result.stderr)
    record = _assert_one_attempt(proj, "nothing-to-record", "test-writer")
    assert record["payload"]["phase"] == "knowledge-capture" and record["ticket_path"] == _TICKET
    assert set(record["payload"]) == {"phase", "outcome", "retry_count", "missing_target"}
    assert proj["sink"].read_bytes() == seeded, "the knowledge sink must be byte-for-byte unchanged"
    bad = _run([*argv[:-4], "--outcome", "nothing_to_record"], proj["project"], tmp_path)
    assert bad.returncode == 0 and bad.stderr.strip(), "an unknown outcome warns on stderr and exits 0"
    assert len(_ledger(proj)) == 1, "an unknown outcome must write nothing"


# ---------------------------------------------------------------------------
# the no-learning branch of the DEPLOYED surfaces, through a real shell
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("surface", ("signoff section 7", "product-owner"))
def test_no_learning_branch_emits_no_knowledge_record(shared_reference_layout, tmp_path, surface):
    # covers: INF-700b-1-i
    # angle: criterion
    """Run the no-learning command the DEPLOYED surface prescribes, via ``bash -c``.

    Exactly one ``capture_attempt`` / ``nothing-to-record`` line on the declared telemetry stream (so
    the count is zero recorded, zero failed, one nothing-to-record), the knowledge sink byte-identical,
    no output at all, exit 0 (the agent's primary output and sign-off are unchanged).
    """
    if surface == "signoff section 7":
        pointer = _section_seven_pointer_problems(shared_reference_layout)
        assert not pointer, "; ".join(pointer)
    line = _event_line(_surface(shared_reference_layout, surface))
    assert line is not None, (
        f"{surface}: deployed text names no `emit_event.py --event capture_attempt ... "
        "--outcome nothing-to-record` command for the no-learning branch")
    assert line.endswith("|| true"), f"{surface}: the command must end in `|| true` (INF-500d-4-vi): {line!r}"
    proj = _project(tmp_path, shared_reference_layout, "live")
    seeded = _seed_sink(proj)
    before = _snapshot(proj["world"])
    cmd = _bind_event(line, proj["deployed"] / _EVENT_REL, "test-writer", _TICKET)
    # Section 7 is generic (`--agent <agent>`, bound to test-writer); the product-owner S9 block
    # hard-codes its own agent, which the binder leaves alone.
    expected_agent = _SURFACE_AGENT[surface]
    tokens = shlex.split(cmd)
    assert tokens[tokens.index("--agent") + 1] == expected_agent, f"{surface}: bound command {cmd!r}"
    env_run = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=str(proj["project"]),
                             timeout=60, check=False)
    assert env_run.returncode == 0, env_run
    assert env_run.stdout == "" and env_run.stderr == "", f"the no-learning command must print nothing: {env_run}"
    record = _assert_one_attempt(proj, "nothing-to-record", expected_agent)
    assert record["event_type"] == "capture_attempt"
    outcomes = [r["payload"]["outcome"] for r in _ledger(proj)]
    assert (outcomes.count("recorded"), outcomes.count("failed")) == (0, 0)
    assert proj["sink"].read_bytes() == seeded, "the knowledge sink must be byte-for-byte unchanged"
    created = _snapshot(proj["world"]) - before
    assert created == {str(_stream(proj).relative_to(proj["world"]))}, f"unexpected files created: {created}"


# ---------------------------------------------------------------------------
# the helper: refusal of contentless text (A2.5)
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
@pytest.mark.parametrize(
    "label, text",
    [
        ("empty", ""),
        ("whitespace_only", "  \n\t  "),
        ("punctuation_only", "...---!!!"),
        ("agent_only", "test-writer"),
        ("metadata_only", "test-writer / knowledge_system -- (unrouted) -- unclassified -- " + _TICKET),
    ],
)
def test_emit_knowledge_refuses_empty_or_metadata_only_text(shared_reference_layout, tmp_path, label, text):
    # covers: INF-700b-1-i
    # angle: boundary
    """Contentless text appends nothing, explains on stderr, exits 0 and writes one nothing-to-record attempt.

    Control row on the SAME project: a genuine learning that merely MENTIONS the agent name is still
    recorded (knowledge line + one ``recorded`` attempt). Wrong versions caught: no refusal at all; a
    whitespace check that lets metadata through; a refusal that fires on any text containing a metadata
    value; a refusal that records ``failed`` or nothing instead of ``nothing-to-record``.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    seeded = _seed_sink(proj)
    refused = _emit_knowledge(proj, tmp_path, text)
    assert refused.returncode == 0, refused
    assert proj["sink"].read_bytes() == seeded, f"{label}: contentless text must append nothing"
    assert refused.stderr.strip(), f"{label}: the refusal must give a reason on stderr"
    assert "usage:" not in refused.stderr.lower() and "required:" not in refused.stderr.lower()
    _assert_one_attempt(proj, "nothing-to-record", "test-writer")
    genuine = f"test-writer learned: {_LEARNING}"
    accepted = _emit_knowledge(proj, tmp_path, genuine)
    assert accepted.returncode == 0, accepted
    lines = proj["sink"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["text"] == genuine, lines
    assert [r["payload"]["outcome"] for r in _ledger(proj)] == ["nothing-to-record", "recorded"]


# ---------------------------------------------------------------------------
# the helper: it writes `recorded` itself (A2.4), fail open
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
def test_successful_helper_run_writes_one_recorded_attempt_and_refusal_writes_none(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-i
    # angle: seam
    """One helper run, no second agent command: one knowledge line AND one ``recorded`` attempt.

    The knowledge line is produced by the real helper; the attempt is written by the real deployed
    emit_event.py that the helper triggers (no ``--log``). A vocabulary rejection then adds NO knowledge
    line and NO ``recorded`` attempt (control: the first call did both).
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    result = _emit_knowledge(proj, tmp_path, _LEARNING)
    assert result.returncode == 0, result
    lines = proj["sink"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["event"] == "knowledge_captured", lines
    record = _assert_one_attempt(proj, "recorded", "test-writer")
    assert record["event_type"] == "capture_attempt"
    rejected = _emit_knowledge(proj, tmp_path, _LEARNING, entry_kind="not_a_real_kind")
    assert rejected.returncode == 0, rejected
    assert len(proj["sink"].read_text(encoding="utf-8").splitlines()) == 1, "a rejection adds no knowledge line"
    assert [r["payload"]["outcome"] for r in _ledger(proj)] == ["recorded"], "a rejection adds no attempt"


@pytest.mark.shared_layout_reader
def test_failed_sink_append_warns_and_records_one_failed_attempt(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-i
    # angle: failure
    """A declared sink that cannot be appended to is reported, not silently dropped (A2.4, A2.6).

    The declared sink path is a directory, so the append raises OSError on any uid (root included).
    Exit stays 0 (fail open); stderr names the sink; nothing is appended; telemetry is still writable,
    so the ledger holds exactly one ``failed`` attempt whose ``missing_target`` is the sink path and
    NO ``recorded`` attempt. A second run against a healthy sink is the control: it records normally.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    proj["sink"].mkdir()
    result = _emit_knowledge(proj, tmp_path, _LEARNING)
    assert result.returncode == 0, result
    assert str(proj["sink"]) in result.stderr, f"stderr must name the sink: {result.stderr!r}"
    assert proj["sink"].is_dir() and not list(proj["sink"].iterdir()), "nothing may be appended"
    record = _ledger(proj)
    assert len(record) == 1, f"exactly one attempt record expected, got {record!r}"
    assert record[0]["event_type"] == "capture_attempt", record
    assert record[0]["payload"]["outcome"] == "failed", record
    assert record[0]["payload"]["missing_target"] == str(proj["sink"]), record
    assert record[0]["agent_name"] == "test-writer", record
    proj["sink"].rmdir()
    healthy = _emit_knowledge(proj, tmp_path, _LEARNING)
    assert healthy.returncode == 0 and len(proj["sink"].read_text(encoding="utf-8").splitlines()) == 1
    assert [r["payload"]["outcome"] for r in _ledger(proj)] == ["failed", "recorded"]


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("breakage", ["script_missing", "script_exits_nonzero"])
def test_helper_fails_open_when_the_telemetry_write_fails(shared_reference_layout, tmp_path, breakage):
    # covers: INF-700b-1-i
    # angle: failure
    """If the deployed emit_event.py cannot run, the knowledge append stands, exit is 0, stderr warns."""
    proj = _project(tmp_path, shared_reference_layout, "live")
    event_script = proj["deployed"] / _EVENT_REL
    assert event_script.is_file(), f"the deployed layout has no {_EVENT_REL}"
    if breakage == "script_missing":
        event_script.unlink()
    else:
        event_script.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    result = _emit_knowledge(proj, tmp_path, _LEARNING)
    assert result.returncode == 0, result
    lines = proj["sink"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["text"] == _LEARNING, "the knowledge append must still succeed"
    stderr = result.stderr.lower()
    assert any(word in stderr for word in ("emit_event", "capture", "attempt", "telemetry")), (
        f"a warning naming the unrecorded attempt is required on stderr: {result.stderr!r}")
    assert _ledger(proj) == [], "no attempt can have been written"


# ---------------------------------------------------------------------------
# the four surfaces
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
def test_four_surfaces_carry_identical_no_learning_command(shared_reference_layout):
    # covers: INF-700b-1-i
    # angle: real_artifact
    """Read from the deployed bytes: the four commands are identical apart from --agent and --ticket."""
    shapes: dict[str, list[str]] = {}
    problems: list[str] = []
    problems.extend(_section_seven_pointer_problems(shared_reference_layout))
    for name in _SURFACE_NAMES:
        line = _event_line(_surface(shared_reference_layout, name))
        if line is None:
            problems.append(f"{name}: names no `emit_event.py --event capture_attempt ... nothing-to-record` command")
            continue
        if not line.endswith("|| true"):
            problems.append(f"{name}: the command must end in `|| true` (INF-500d-4-vi): {line!r}")
        tokens = shlex.split(line)
        for flag in ("--log", "--sink"):
            if flag in tokens:
                problems.append(f"{name}: carries {flag} (ADR-034 A1.2 / ADR-069)")
        kept: list[str] = []
        skip = False
        for tok in tokens:
            if skip:
                skip = False
            elif tok in ("--agent", "--ticket"):
                skip = True
            else:
                kept.append(tok)
        shapes[name] = kept
    if len({tuple(v) for v in shapes.values()}) > 1:
        problems.append(f"the surfaces differ beyond --agent/--ticket: {shapes}")
    assert not problems, "\n".join(problems)


@pytest.mark.shared_layout_reader
def test_sink_parity_still_passes_with_the_no_learning_wording(shared_reference_layout, tmp_path):
    # covers: INF-700b-1-i
    # angle: reachability
    """``check_sink_parity.py`` must still resolve all four emit surfaces on the deployed layout.

    The new no-learning wording must not put the word "emit" and ``knowledge_captured`` in one
    paragraph ahead of the helper paragraph. Gated on the new command being present, so it is red
    until the wording exists and then guards the wording (a plain parity pass is green today).
    """
    missing = [n for n in _SURFACE_NAMES if _event_line(_surface(shared_reference_layout, n)) is None]
    assert not missing, f"no-learning command absent from: {missing}"
    proj = _project(tmp_path, shared_reference_layout, "live")
    result = subprocess.run([sys.executable, "-B", str(_CHECKER), "--target-dir", str(proj["project"])],
                            capture_output=True, text=True, timeout=120, check=False, cwd=str(_REPO_ROOT))
    assert result.returncode == 0 and "Inspected 4 surfaces" in result.stdout, (result.stdout, result.stderr)
    assert "unparseable" not in result.stdout.lower()
