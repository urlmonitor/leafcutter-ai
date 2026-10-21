"""
MODULE: _inf_400c_4_i_support
GOAL: Module-level constants and helpers for test_inf_400c_4_i.py, moved out so
    the test file stays under the file-size limit. No tests live here and
    nothing here runs at import time.
AC: INF-400c-4-i (source_ac)

The CHECK INTERFACE the helpers drive (scripts/ci/check_sink_parity.py) and
the two RED mechanisms are documented in test_inf_400c_4_i.py's docstring.
The caller must have this directory on sys.path (the test module inserts it
before importing this one), because ``_inf400c_harness`` is a sibling import.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from _inf400c_harness import deployed_root as _deployed_root

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_CHECK_SINK_PARITY = _WORKTREE_ROOT / "scripts" / "ci" / "check_sink_parity.py"

_QUERY_TIMEOUT_SECONDS = 30

_SURFACE_IDS: tuple[str, ...] = ("signoff", "product-owner", "business-analyst", "it-po")

# The pre-AC / defective destination every surface currently names verbatim.
_LEGACY_LITERAL_SENTENCE = "Append to `debugging/logs/agent_telemetry.jsonl`"

# Matches a resolution invocation naming both the harvester script and its
# side-effect-free query flag, wherever it appears in a surface's text.
_INVOCATION_PATTERN = re.compile(r"harvest_learnings\.py[^`\n]*--print-sink")

# Matches a literal backtick-quoted JSONL path under debugging/logs/ -- the
# pre-AC self-carried destination shape.
_LITERAL_PATTERN = re.compile(r"`(debugging/logs/[\w./-]+\.jsonl)`")

# INF-700b-1: the shipped surfaces run the deployed emit helper with no
# --sink. The revert targets the script name (one substitution site); the
# command pattern reads the rest of that command line the way an agent would.
_EMIT_HELPER_PATTERN = re.compile(r"emit_knowledge\.py")
_EMIT_COMMAND_PATTERN = re.compile(r"emit_knowledge\.py([^`\n]*)")
_EMIT_SINK_ARG_PATTERN = re.compile(r"--sink(?:=|\s+)(\S+)")
_EMIT_LITERAL_SINK_ARG = "--sink debugging/logs/agent_telemetry.jsonl"


def _surface_path(target_dir: Path, surface_id: str) -> Path:
    root = _deployed_root(target_dir)
    if surface_id == "signoff":
        return root / "skills" / "signoff" / "SKILL.md"
    return root / "agents" / f"{surface_id}.md"


def _declared_sink(target_dir: Path) -> str:
    config_path = _deployed_root(target_dir) / "config" / "knowledge_sink.json"
    assert config_path.is_file(), (
        f"Expected a build-time knowledge-sink declaration at {config_path} "
        "(AC INF-400c-4, already work_status: done as of INF-400c-4-v -- see "
        "build_knowledge_sink_declaration in scripts/build_phases.py). This "
        "file does not exist; the fixture build did not produce it."
    )
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return data["knowledge_emission_sink"]


def _deployed_harvester(target_dir: Path) -> Path:
    return _deployed_root(target_dir) / "scripts" / "knowledge" / "harvest_learnings.py"


def _deployed_emit_helper(target_dir: Path) -> Path:
    return _deployed_root(target_dir) / "scripts" / "knowledge" / "emit_knowledge.py"


def _run_sink_parity_check(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the (not-yet-written) sink-parity check as a REAL subprocess.

    See test_inf_400c_4_i.py's docstring for the CLI contract python-coder
    must implement scripts/ci/check_sink_parity.py to.
    """
    argv = [sys.executable, str(_CHECK_SINK_PARITY), "--target-dir", str(target_dir)]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=_QUERY_TIMEOUT_SECONDS,
        check=False,
    )


def _assert_check_script_exists() -> None:
    assert _CHECK_SINK_PARITY.is_file(), (
        f"{_CHECK_SINK_PARITY} does not exist yet -- the sink-parity check "
        "AC INF-400c-4-i requires has not been implemented. See this "
        "module's docstring ('CHECK INTERFACE THIS FILE FIXES') for the "
        "exact CLI contract python-coder must implement it to."
    )


def _revert_to_literal_telemetry_path(text: str) -> str:
    """Simulate a partial repoint: put a destination of its own back on the surface.

    Two surface forms exist, and each is reverted to the self-carried
    telemetry-stream destination the AC forbids:

    - a ``harvest_learnings.py --print-sink`` resolution invocation is replaced
      with the literal pre-AC telemetry-stream sentence;
    - an ``emit_knowledge.py`` invocation (INF-700b-1: the shipped form) gains
      ``--sink debugging/logs/agent_telemetry.jsonl``, so the surface now
      carries a destination of its own instead of letting the helper resolve
      the declared sink.

    Each caller must still assert the text changed (``_assert_revert_changed``):
    a revert that matches neither form is a silent no-op that would let the
    "check must block" tests pass without exercising any block.
    """
    reverted = _INVOCATION_PATTERN.sub(_LEGACY_LITERAL_SENTENCE, text)
    return _EMIT_HELPER_PATTERN.sub(rf"emit_knowledge.py {_EMIT_LITERAL_SINK_ARG}", reverted)


def _assert_revert_changed(original: str, reverted: str, surface_id: str) -> None:
    assert reverted != original, (
        f"Fixture defect: reverting surface {surface_id!r} changed nothing -- "
        "it matches neither a harvest_learnings.py --print-sink invocation "
        "nor an emit_knowledge.py invocation, so the 'check must block' "
        "assertion would pass without a self-carried destination ever being "
        "present. Teach _revert_to_literal_telemetry_path this surface form."
    )
    assert (
        _LEGACY_LITERAL_SENTENCE in reverted or _EMIT_LITERAL_SINK_ARG in reverted
    ), f"Surface {surface_id!r} was altered but carries no literal telemetry destination."


def _emit_command_args(surface_text: str) -> str | None:
    """Return the argument text of the first ``emit_knowledge.py`` command, or ``None``.

    Folds backslash-newline continuations, as a shell would, before reading
    the rest of the command line.
    """
    match = _EMIT_COMMAND_PATTERN.search(re.sub(r"\\\r?\n", " ", surface_text))
    return match.group(1) if match is not None else None


def _resolve_destination_as_agent_would(surface_text: str, target_dir: Path, cwd: Path) -> Path:
    """Determine where an agent following *surface_text* literally would append.

    Mirrors the same two-mechanism precedence the check itself must
    implement (see the test module docstring): a resolution invocation is
    executed for real when present; otherwise the literal path is taken
    at face value and resolved against *cwd* if relative -- which is
    exactly the CWD-dependent behaviour this AC exists to eliminate.

    Raises AssertionError if the surface contains neither mechanism.
    """
    invocation_match = _INVOCATION_PATTERN.search(surface_text)
    if invocation_match is not None:
        harvester = _deployed_harvester(target_dir)
        result = subprocess.run(
            [sys.executable, str(harvester), "--print-sink"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
        assert result.returncode == 0, (
            f"Resolution invocation failed from cwd={cwd}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        return Path(result.stdout.strip())

    emit_args = _emit_command_args(surface_text)
    if emit_args is not None:
        sink_arg = _EMIT_SINK_ARG_PATTERN.search(emit_args)
        if sink_arg is not None:
            # The agent runs the command as written: the helper writes to the
            # destination the surface itself carries.
            literal_path = Path(sink_arg.group(1))
            return literal_path if literal_path.is_absolute() else (cwd / literal_path)
        result = subprocess.run(
            [sys.executable, str(_deployed_emit_helper(target_dir)), "--print-sink"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
        assert result.returncode == 0, (
            f"emit_knowledge.py --print-sink failed from cwd={cwd}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        return Path(result.stdout.strip())

    literal_match = _LITERAL_PATTERN.search(surface_text)
    if literal_match is not None:
        literal_path = Path(literal_match.group(1))
        return literal_path if literal_path.is_absolute() else (cwd / literal_path)

    no_mechanism_message = (
        "Could not find any known resolution mechanism in the surface's "
        "append instruction: no `harvest_learnings.py --print-sink` "
        "invocation, no `emit_knowledge.py` invocation, and no literal "
        "`debugging/logs/*.jsonl` path."
    )
    raise AssertionError(no_mechanism_message)


def _perform_described_append(surface_text: str, target_dir: Path, cwd: Path, marker: str) -> Path:
    """Perform the append *surface_text* describes, standing at *cwd*.

    Real file I/O -- no mocking. Returns the resolved destination path.
    """
    destination = _resolve_destination_as_agent_would(surface_text, target_dir, cwd)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "knowledge_captured", "text": marker}) + "\n")
    return destination
