"""
MODULE: test_inf_400c_5_iii
GOAL: RED test stubs for AC INF-400c-5-iii -- a rejected entry_kind is
    reported to the agent and does not fail the agent's run.
AC: INF-400c-5-iii (source_ac)
DEPENDS ON: INF-400c-5 (see test_inf_400c_5.py's module docstring for the
    full assumed contract of ``config/entry_kind_vocabulary.json`` and the
    ``scripts/knowledge/emit_knowledge.py`` CLI).

CONTRACT ASSUMED HERE, ADDITIONALLY: on rejection, ``emit_knowledge.py``
prints (to stdout or stderr) a message naming the rejected entry_kind and
listing candidate canonical members, and it appends one line to a SEPARATE
rejection-count sink named by ``--rejection-log PATH`` (default: does not
create the file at all when nothing is ever rejected -- see the AC's own
it_requirements: "A rejection that is only logged and not counted
reproduces the silent-loss failure ... the count must be observable"). This
mirrors the existing dual-stream precedent in this codebase (operational
telemetry stream vs. knowledge-emission sink, INF-400c-4-iii) rather than
overloading the one JSONL the harvester already parses as
``knowledge_captured`` events.

WHAT IS EXPECTED TO BE RED AND WHY: ``scripts/knowledge/emit_knowledge.py``
does not exist yet in this worktree, so every test below fails at
subprocess-invocation time (script not found / non-zero from a shebang-less
missing file) until python-coder authors it.
"""
# @ac-tag: INF-400c-5-iii

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EMIT_SCRIPT = _REPO_ROOT / "scripts" / "knowledge" / "emit_knowledge.py"
_VOCAB_CONFIG = _REPO_ROOT / "config" / "entry_kind_vocabulary.json"

_TIMEOUT_SECONDS = 30

# The exact rejected value from the AC's own Given clause.
_REJECTED_KIND = "component-decomposition-and-operational-note"


def _run_emit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_EMIT_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def test_rejection_message_names_the_rejected_value(tmp_path: Path) -> None:
    # covers: INF-400c-5-iii
    # angle: criterion
    """Then the helper declines to write the event and returns a message
    that names the rejected value.

    Uses the AC's own Given-clause example entry_kind verbatim.
    """
    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", _REJECTED_KIND,
        "--text", "A real learning that should still be rejected on entry_kind.",
        "--sink", str(tmp_path / "knowledge_emissions.jsonl"),
    )
    combined_output = result.stdout + result.stderr
    assert _REJECTED_KIND in combined_output, (
        f"rejection message must name the rejected value {_REJECTED_KIND!r}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_rejection_message_lists_canonical_members_as_candidates(tmp_path: Path) -> None:
    # covers: INF-400c-5-iii
    # angle: criterion
    """... and lists the canonical members whose routing destination matches
    the destination the agent supplied.

    Does not pin an exact matching algorithm (that is the coder's
    reconciliation work); asserts the observable outward contract -- the
    message must surface at least one REAL vocabulary member as a
    candidate, not an empty or fabricated list.
    """
    vocab = json.loads(_VOCAB_CONFIG.read_text(encoding="utf-8"))
    members = set(vocab["members"].keys())
    assert members, "sanity: need at least one real vocabulary member"

    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", _REJECTED_KIND,
        "--text", "A real learning that should still be rejected on entry_kind.",
        "--sink", str(tmp_path / "knowledge_emissions.jsonl"),
    )
    combined_output = result.stdout + result.stderr
    named_candidates = {m for m in members if m in combined_output}
    assert named_candidates, (
        "rejection message must list at least one real canonical vocabulary "
        f"member as a candidate; output={combined_output!r}"
    )
    assert _REJECTED_KIND not in named_candidates, (
        "the rejected value itself is out-of-vocabulary and must never be "
        "offered back as one of its own candidates"
    )


def test_no_partial_or_placeholder_record_is_appended_to_the_sink(tmp_path: Path) -> None:
    # covers: INF-400c-5-iii
    # angle: real_artifact
    """And no partial or placeholder record is appended to the
    knowledge-emission sink.
    """
    sink_path = tmp_path / "knowledge_emissions.jsonl"
    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", _REJECTED_KIND,
        "--text", "A real learning that should still be rejected on entry_kind.",
        "--sink", str(sink_path),
    )
    # A missing/broken emit_knowledge.py would ALSO leave the sink untouched
    # (it never runs at all), which would make the assertion below pass
    # vacuously before the helper exists. Require the real, well-formed CLI
    # contract (exit 0, per INF-400c-5-iii) so this test is genuinely RED
    # until the script exists and behaves correctly, not just absent.
    assert result.returncode == 0, (
        f"expected the real emit_knowledge.py CLI to run and exit 0; "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert not sink_path.exists() or sink_path.read_text(encoding="utf-8").strip() == "", (
        "a rejected emission must leave the sink untouched -- no partial or "
        "placeholder line"
    )


def test_helper_exits_without_error_so_the_agent_completes(tmp_path: Path) -> None:
    # covers: INF-400c-5-iii
    # angle: failure
    """And the helper exits without error, so the agent completes and
    returns its primary output unaffected.
    """
    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", _REJECTED_KIND,
        "--text", "A real learning that should still be rejected on entry_kind.",
        "--sink", str(tmp_path / "knowledge_emissions.jsonl"),
    )
    assert result.returncode == 0, (
        f"a rejection must be non-fatal to the calling agent; "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )


def test_a_rejection_is_counted_distinctly_from_a_run_that_emitted_nothing(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-5-iii
    # angle: boundary
    """And the rejection is counted, so a run that rejected one or more
    emissions can be distinguished from a run that emitted nothing.

    Boundary between "zero rejections" (no observable trace at all) and
    "one or more rejections" (an observable, growing trace) -- exercised via
    a dedicated ``--rejection-log`` sink, kept separate from the
    knowledge-emission sink per the module docstring's dual-stream
    rationale.
    """
    rejection_log = tmp_path / "knowledge_rejections.jsonl"
    sink_path = tmp_path / "knowledge_emissions.jsonl"

    # A run that emits nothing rejected must leave no trace at all.
    assert not rejection_log.exists()

    _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", _REJECTED_KIND,
        "--text", "First rejected emission.",
        "--sink", str(sink_path),
        "--rejection-log", str(rejection_log),
    )
    assert rejection_log.exists(), (
        "a run that rejected at least one emission must leave an observable "
        "trace distinguishing it from a run that emitted nothing"
    )
    first_count = len(
        [ln for ln in rejection_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    )
    assert first_count == 1

    _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", _REJECTED_KIND,
        "--text", "Second rejected emission.",
        "--sink", str(sink_path),
        "--rejection-log", str(rejection_log),
    )
    second_count = len(
        [ln for ln in rejection_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    )
    assert second_count == first_count + 1, (
        "each rejection must increment the observable count by exactly one"
    )
