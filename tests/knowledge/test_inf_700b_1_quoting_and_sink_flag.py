"""
MODULE: test_inf_700b_1_quoting_and_sink_flag
GOAL: RED behavioural tests for the two defects the second review of AC INF-700b-1
    found after the first test-writer pass.
AC: INF-700b-1 (source_ac); ADR-034 Amendment 1; ADR-069.

DEFECT 1 -- SHELL QUOTING (pr-reviewer H-1). The capture command in the DEPLOYED
    signoff section 7 and the product-owner S9 block passes ``--text "<learning>"``
    in double quotes, so a learning holding a backtick, ``$(...)``, ``$VAR`` or a
    double quote is expanded or broken by the shell before the helper sees it. The
    first-pass tests passed argv straight to ``subprocess`` with no shell, so they
    could not see it. Here the command is extracted from the deployed text, filled
    EXACTLY as that text instructs, and run through a REAL ``bash -c``. The fixed
    template states a single-quote rule (embedded ``'`` written ``'\\''``); that rule
    is encoded below, and the test fails with a clear message if the text states none.

DEFECT 2 -- SINK-PARITY MECHANISM (test-runner regression). ``check_sink_parity.py``
    only knows ``harvest_learnings.py --print-sink`` or a literal
    ``debugging/logs/*.jsonl``, so it calls the new surfaces unparseable. The fix adds
    a third mechanism: an ``emit_knowledge.py`` invocation with no ``--sink`` is
    resolved by running the deployed ``emit_knowledge.py --print-sink`` (a NEW
    read-only flag). The flag does not exist yet, so these are red.

REAL-ARTIFACT NOTE: prompt text is read from the DEPLOYED shared layout; the helper and
    the checker run as fresh subprocesses against a private COPY of the deployed tree,
    with the deployed ``knowledge_sink.json`` round-tripped through ``json``.
"""
# @ac-tag: INF-700b-1

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from tests.knowledge.test_inf_700b_1_emit_helper import (
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
_LEARNING = "uses `foo()` and $(echo PWNED) and $HOME and it's \"quoted\""
_SINGLE_QUOTE_RULE = "'\\''"
_FILL = {"<agent>": "test-writer", "<component>": "knowledge_system", "<kind>": "unclassified",
         "<destination>": "'(unrouted)'", "<ticket>": "tickets/TICKET-probe.md"}
_SURFACES = ("signoff section 7", "product-owner")


def _surface_text(layout: Path, name: str) -> str:
    if name == "signoff section 7":
        return _section_seven(layout)
    return _emission_block(layout, "agents/product-owner.md")


def _raw_command(section: str) -> str | None:
    """The raw (unsplit) shell line of the ``emit_knowledge.py ... --text`` command, or ``None``."""
    for snippet in _candidate_snippets(section):
        if "emit_knowledge.py" in snippet and "--text" in snippet:
            joined = re.sub(r"\\\r?\n", " ", snippet)
            return next(line.strip() for line in joined.splitlines() if "emit_knowledge.py" in line)
    return None


def _states_single_quote_rule(section: str) -> bool:
    return _SINGLE_QUOTE_RULE in section and re.search(r"single[- ]quot", section, re.IGNORECASE) is not None


def _fill_learning(line: str, learning: str) -> str:
    """Fill ``<learning>`` the way the surrounding quote characters instruct, nothing smarter."""
    at = line.index("<learning>")
    before, after = line[at - 1], line[at + len("<learning>")]
    if before == "'" and after == "'":
        return line.replace("<learning>", learning.replace("'", _SINGLE_QUOTE_RULE))
    return line.replace("<learning>", learning)


def _bind_for_shell(line: str, helper: Path, learning: str) -> str:
    cmd = _fill_learning(line, learning)
    cmd = re.sub(r"\S*emit_knowledge\.py", shlex.quote(str(helper)), cmd, count=1)
    cmd = re.sub(r"^python3?\b", shlex.quote(sys.executable) + " -B", cmd)
    for placeholder, value in _FILL.items():
        cmd = cmd.replace(placeholder, value)
    return cmd


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("surface", _SURFACES)
def test_capture_command_survives_a_real_shell_byte_for_byte(shared_reference_layout, tmp_path, surface):
    # covers: INF-700b-1
    # angle: discrimination
    """Run the deployed capture command through ``bash -c`` with shell metacharacters in the learning.

    Must be green only when the deployed text states a single-quote rule (embedded ``'`` as
    ``'\\''``) AND following it records the learning byte for byte. Wrong versions caught: the
    current double-quoted ``--text "<learning>"`` (backticks and ``$(...)`` expand); a template
    with no quoting rule at all; single quotes without the ``'\\''`` escape (the ``it's`` breaks it).
    """
    section = _surface_text(shared_reference_layout, surface)
    line = _raw_command(section)
    assert line is not None, f"{surface}: deployed text names no `emit_knowledge.py ... --text` command"
    proj = _project(tmp_path, shared_reference_layout, "live")
    cmd = _bind_for_shell(line, proj["deployed"] / _HELPER_REL, _LEARNING)
    before = _snapshot(proj["world"])
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=str(proj["project"]),
                            timeout=60, check=False)
    recorded = [json.loads(x)["text"] for x in (proj["sink"].read_text(encoding="utf-8").splitlines()
                                                if proj["sink"].exists() else [])]
    problems = []
    if not _states_single_quote_rule(section):
        problems.append("the deployed text states no quoting rule (expected single quotes, "
                        "embedded ' written as '\\'')")
    if recorded != [_LEARNING]:
        problems.append(f"recorded text {recorded!r} != the learning {_LEARNING!r}; "
                        f"shell stderr={result.stderr!r} (cmd={cmd!r})")
    created = {p for p in _snapshot(proj["world"]) - before}
    if any(Path(p).name == "PWNED" for p in created) or (proj["project"] / "PWNED").exists():
        problems.append("a file named PWNED appeared: a substitution executed")
    if recorded and "$(echo PWNED)" not in recorded[0]:
        problems.append("$(echo PWNED) never reached the helper literally: the shell executed it")
    assert not problems, f"{surface}: " + " | ".join(problems)


def _stderr_is_parser_error(text: str) -> bool:
    return any(word in text.lower() for word in ("unrecognized arguments", "required:", "usage:"))


@pytest.mark.shared_layout_reader
def test_print_sink_on_a_live_declaration_matches_the_harvester_byte_for_byte(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: seam
    """``emit_knowledge.py --print-sink`` prints the absolute declared sink, exit 0, creating nothing."""
    proj = _project(tmp_path, shared_reference_layout, "live")
    before = _snapshot(proj["world"])
    emit = _run([sys.executable, "-B", str(proj["deployed"] / _HELPER_REL), "--print-sink"], proj["cwd"], tmp_path)
    harvest = _run([sys.executable, "-B", str(proj["deployed"] / "scripts" / "knowledge" / "harvest_learnings.py"),
                    "--print-sink"], proj["cwd"], tmp_path)
    assert harvest.returncode == 0 and harvest.stdout.strip() == str(proj["sink"]), "control: harvester resolves the sink"
    assert emit.returncode == 0, f"stdout={emit.stdout!r} stderr={emit.stderr!r}"
    assert Path(emit.stdout.strip()).is_absolute() and emit.stdout.strip() == str(proj["sink"])
    assert emit.stdout == harvest.stdout, f"{emit.stdout!r} != {harvest.stdout!r}"
    assert not (_snapshot(proj["world"]) - before), "--print-sink is read-only: it must create nothing"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("case, reason_words", [
    ("absent", ("absent", "declaration", "knowledge_sink")),
    ("stale", ("stale", "no longer exists")),
    ("unusable", ("operational_log_root", "not directly under", "usable")),
])
def test_print_sink_refuses_an_unusable_declaration_and_creates_nothing(shared_reference_layout, tmp_path,
                                                                        case, reason_words):
    # covers: INF-700b-1
    # angle: failure
    """No usable declaration: non-zero exit, a reason on stderr, empty stdout, nothing created."""
    proj = _project(tmp_path, shared_reference_layout, case)
    before = _snapshot(proj["world"])
    result = _run([sys.executable, "-B", str(proj["deployed"] / _HELPER_REL), "--print-sink"], proj["cwd"], tmp_path)
    assert result.returncode != 0, f"must exit non-zero, stdout={result.stdout!r}"
    assert not _stderr_is_parser_error(result.stderr), f"parser error, not a refusal: {result.stderr!r}"
    assert any(w in result.stderr.lower() for w in reason_words), f"no reason ({case}): {result.stderr!r}"
    assert result.stdout.strip() == "", f"no sink may be printed on refusal: {result.stdout!r}"
    created = _snapshot(proj["world"]) - before
    assert not created, f"a refused --print-sink must create nothing, but created {sorted(created)}"


@pytest.mark.shared_layout_reader
def test_print_sink_with_a_missing_log_dir_prints_the_sink_and_creates_nothing(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: boundary
    """A live root whose log directory is missing: the flag still only reports, it never mkdirs."""
    proj = _project(tmp_path, shared_reference_layout, "missing_log_dir")
    before = _snapshot(proj["world"])
    result = _run([sys.executable, "-B", str(proj["deployed"] / _HELPER_REL), "--print-sink"], proj["cwd"], tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.strip() == str(proj["sink"])
    assert not (_snapshot(proj["world"]) - before), "--print-sink must not create the log directory"


def _parity(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-B", str(_CHECKER), "--target-dir", str(target)],
                          capture_output=True, text=True, timeout=120, check=False, cwd=str(_REPO_ROOT))


@pytest.mark.shared_layout_reader
def test_sink_parity_checker_resolves_emit_surfaces_and_refuses_a_self_carried_sink(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: reachability
    """Run ``check_sink_parity.py`` for real on the deployed layout, then on one with ``--sink <literal>``.

    Control row: the untouched deployed copy must pass with four surfaces inspected (today the checker
    calls the emit surfaces unparseable). Negative row: the SAME copy with one surface's command carrying
    ``--sink <literal>`` must be refused as a self-carried destination, naming that surface and the path,
    while the other three still pass. Wrong version caught: an implementation that resolves every emit
    surface via ``--print-sink`` and ignores a restated ``--sink``.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    control = _parity(proj["project"])
    assert control.returncode == 0 and "Inspected 4 surfaces" in control.stdout, (
        f"control: unmodified layout must pass, got {control.returncode}: {control.stdout!r} {control.stderr!r}")
    literal = str(tmp_path / "elsewhere" / "own_sink.jsonl")
    text = proj["deployed"] / "agents" / "product-owner.md"
    original = text.read_text(encoding="utf-8")
    assert "emit_knowledge.py " in original
    text.write_text(original.replace("emit_knowledge.py ", f"emit_knowledge.py --sink {literal} ", 1), encoding="utf-8")
    result = _parity(proj["project"])
    failing = [ln for ln in result.stdout.splitlines() if ln.startswith("FAIL ")]
    assert result.returncode == 1, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert [ln.split(":")[0] for ln in failing] == ["FAIL product-owner"], f"only product-owner may fail: {failing}"
    assert "destination of its own" in failing[0] and literal in failing[0], f"not a self-carried refusal: {failing[0]!r}"


@pytest.mark.shared_layout_reader
def test_an_abbreviated_sink_flag_is_refused_by_the_helper_and_writes_nothing(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: boundary
    """``--sin /x`` must be an argparse error: abbreviations would let a surface carry a sink the checker misses.

    Wrong version caught: an ArgumentParser without ``allow_abbrev=False`` (``--sin`` resolves to ``--sink``,
    the event is appended to ``/x`` and the run exits 0).
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    elsewhere = tmp_path / "elsewhere" / "abbrev_sink.jsonl"
    before = _snapshot(proj["world"])
    argv = [sys.executable, "-B", str(proj["deployed"] / _HELPER_REL), "--agent", "test-writer",
            "--component", "knowledge_system", "--destination", "(unrouted)", "--entry-kind", "unclassified",
            "--text", "x", "--sin", str(elsewhere)]
    result = _run(argv, proj["cwd"], tmp_path)
    assert result.returncode != 0, f"abbreviation accepted: stdout={result.stdout!r} stderr={result.stderr!r}"
    assert _stderr_is_parser_error(result.stderr), f"not an argparse refusal: {result.stderr!r}"
    assert not elsewhere.exists() and not (_snapshot(proj["world"]) - before), "a refused run must write nothing"


def _carrying_surface(proj: dict[str, Path], literal: str, shape: str) -> None:
    """Rewrite the deployed product-owner emission block so its command carries ``--sink`` in *shape*."""
    path = proj["deployed"] / "agents" / "product-owner.md"
    text = path.read_text(encoding="utf-8")
    fence = text.rfind("```bash", 0, text.index("emit_knowledge.py"))
    assert fence != -1 and "--agent product-owner" in text, "precondition: the deployed block's shape changed"
    if shape == "prose_first":
        text = text[:fence] + "The emit_knowledge.py helper does the write.\n   " + text[fence:]
        text = text.replace("emit_knowledge.py --agent", f"emit_knowledge.py --sink {literal} --agent", 1)
    elif shape == "prose_first_equals":
        text = text[:fence] + "The emit_knowledge.py helper does the write.\n   " + text[fence:]
        text = text.replace("emit_knowledge.py --agent", f"emit_knowledge.py --sink={literal} --agent", 1)
    elif shape == "with_harvester":
        text = text[:fence] + "Check it with `python3 harvest_learnings.py --print-sink`.\n   " + text[fence:]
        text = text.replace("emit_knowledge.py --agent", f"emit_knowledge.py --sink {literal} --agent", 1)
    else:
        # Anchor on the emit_knowledge.py command line: the block also carries an emit_event.py line
        # with its own ``--agent product-owner``, which comes first.
        text = text.replace("emit_knowledge.py --agent product-owner",
                            f"emit_knowledge.py --agent product-owner\n   --sink {literal}", 1)
    _assert_sink_lands_in_emit_knowledge(text, literal)
    path.write_text(text, encoding="utf-8")


def _assert_sink_lands_in_emit_knowledge(text: str, literal: str) -> None:
    """Fail loudly if the injected ``--sink`` is not inside an emit_knowledge.py invocation.

    The nearest preceding command word before the injection must be ``emit_knowledge.py``, with no
    fence boundary between them, so a template change that moves lines cannot silently test another command.
    """
    at = text.find(literal)
    assert at != -1, "precondition: the injected sink literal is absent"
    head = text[:at]
    start = head.rfind("emit_knowledge.py")
    assert start != -1, "the injected --sink has no emit_knowledge.py before it"
    between = head[start:]
    assert "```" not in between and "emit_event.py" not in between, (
        f"the injected --sink is not inside an emit_knowledge.py command: {between!r}")
    assert head.rfind("emit_event.py") < start, "the injected --sink landed in an emit_event.py command"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("shape, angle_note", [
    ("prose_first", "an earlier prose mention hides the command"),
    ("prose_first_equals", "the --sink=<value> spelling after an earlier prose mention"),
    ("with_harvester", "the harvester mechanism must not mask a self-carried emit sink"),
    ("wrapped_no_backslash", "a command wrapped without a backslash"),
])
def test_checker_refuses_a_self_carried_sink_whatever_the_surface_shape(shared_reference_layout, tmp_path,
                                                                        shape, angle_note):
    # covers: INF-700b-1
    # angle: discrimination
    """Run ``check_sink_parity.py`` for real on a private copy whose surface carries ``--sink <literal>``.

    Each shape is one the first-mention, one-line, harvester-first scan misses. Must be refused naming
    product-owner and the literal, with the other three surfaces passing.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    literal = str(tmp_path / "elsewhere" / f"{shape}.jsonl")
    _carrying_surface(proj, literal, shape)
    result = _parity(proj["project"])
    failing = [ln for ln in result.stdout.splitlines() if ln.startswith("FAIL ")]
    assert result.returncode == 1, f"{angle_note}: passed. stdout={result.stdout!r} stderr={result.stderr!r}"
    assert [ln.split(":")[0] for ln in failing] == ["FAIL product-owner"], f"{angle_note}: {failing}"
    assert "destination of its own" in failing[0] and literal in failing[0], f"{angle_note}: {failing[0]!r}"


@pytest.mark.shared_layout_reader
def test_checker_exits_2_when_the_deployed_emit_helper_is_missing(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: failure
    """A surface that uses the emit mechanism but a deployed tree without ``emit_knowledge.py``: exit 2, named."""
    proj = _project(tmp_path, shared_reference_layout, "live")
    (proj["deployed"] / _HELPER_REL).unlink()
    result = _parity(proj["project"])
    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "emit_knowledge.py" in result.stderr and "incomplete" in result.stderr, result.stderr
