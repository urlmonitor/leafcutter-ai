"""
MODULE: test_inf_400c_5
GOAL: RED test stubs for AC INF-400c-5 -- one declared entry_kind vocabulary
    shared by the classifier (route-knowledge/SKILL.md's 16-value
    ``target_surface`` taxonomy) and the harvester (harvest_learnings.py's
    ``_KNOWN_ENTRY_KINDS``), enforced at the point an event is emitted.
AC: INF-400c-5 (source_ac)

CONTRACT ASSUMED BY THESE TESTS (none of this exists yet -- authored here
per this AC's Gherkin, since INF-400c-5 is the ticket that must create it):

  - ``config/entry_kind_vocabulary.json`` -- the single declared vocabulary,
    read by both the classifier documentation and the harvester. Shape:
    ``{"members": {"<canonical-entry-kind>": {...routing metadata...}, ...}}``.
    This mirrors the existing ``config/knowledge_sink.json`` declaration
    pattern already used by ``harvest_learnings.py`` (INF-400c-4).

  - ``scripts/knowledge/emit_knowledge.py`` -- a new, self-contained CLI
    script (stdlib only, no project imports -- same convention as
    ``harvest_learnings.py`` and
    ``templates/skills/agent-telemetry/scripts/emit_event.py``) that the
    four shipped emit sites (signoff SKILL.md Section 7, and the
    product-owner/business-analyst/it-po v3 templates) call instead of
    hand-writing a ``knowledge_captured`` JSON line. It validates
    ``--entry-kind`` against the declared vocabulary before appending to
    the sink named by ``--sink``.

    CLI surface assumed:
        python scripts/knowledge/emit_knowledge.py \
            --agent AGENT --component COMPONENT --destination PATH \
            --entry-kind KIND --text TEXT [--ticket TICKET] \
            --sink SINK_PATH [--vocabulary VOCAB_PATH]

    Exit code 0 in both the accepted and the rejected case (best-effort,
    non-fatal to the calling agent -- see INF-400c-5-iii). On acceptance,
    exactly one JSON line is appended to ``--sink`` with the required
    ``(timestamp, agent, component, destination, entry_kind)`` fields
    ``harvest_learnings.py`` already keys its idempotency digest on, plus
    ``text`` (and ``ticket`` when supplied).

WHAT IS EXPECTED TO BE RED AND WHY: neither ``config/entry_kind_vocabulary
.json`` nor ``scripts/knowledge/emit_knowledge.py`` exists in this worktree
at authoring time (confirmed by directory listing). Every test below must
fail with FileNotFoundError (missing config) or a non-zero/`No such file`
subprocess result (missing script) until python-coder creates both.
"""
# @ac-tag: INF-400c-5

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VOCAB_CONFIG = _REPO_ROOT / "config" / "entry_kind_vocabulary.json"
_EMIT_SCRIPT = _REPO_ROOT / "scripts" / "knowledge" / "emit_knowledge.py"
_HARVESTER_SCRIPT = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"
_ROUTE_KNOWLEDGE_SKILL = _REPO_ROOT / "templates" / "skills" / "route-knowledge" / "SKILL.md"

_TIMEOUT_SECONDS = 30


def _load_vocabulary_members() -> set[str]:
    """Read the real declared vocabulary config and return its member set.

    Raises FileNotFoundError / json.JSONDecodeError until INF-400c-5 lands
    -- that failure IS the red signal for tests that depend on this helper.
    """
    data = json.loads(_VOCAB_CONFIG.read_text(encoding="utf-8"))
    return set(data["members"].keys())


def _load_classifier_target_surfaces() -> set[str]:
    """Extract every ``target_surface`` value from the REAL route-knowledge
    SKILL.md taxonomy table (real artifact -- never a hand-typed literal).

    The taxonomy table rows look like:
        | `memory-user` | `memory/feedback_*.md` (...) | ... |
    """
    text = _ROUTE_KNOWLEDGE_SKILL.read_text(encoding="utf-8")
    # Restrict to the taxonomy table body: rows of the form "| `value` | ..."
    # where the first cell is a single backtick-quoted token with no spaces.
    values = set(re.findall(r"^\|\s*`([a-zA-Z0-9.-]+)`\s*\|", text, flags=re.MULTILINE))
    # Exclude values that are not part of the target_surface vocabulary
    # itself (e.g. a routed status value like `duplicate` or `unknown`
    # that appears in an example JSON payload rather than the taxonomy
    # table). This AC's Given clause names the taxonomy as 16 members;
    # if the real file's count ever drifts this test still runs -- it
    # compares against whatever the real file states, not a hardcoded 16.
    return values - {"duplicate", "unknown"}


def _run_emit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_EMIT_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def _run_harvester(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_HARVESTER_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def test_a_single_declared_vocabulary_config_exists_and_is_non_empty(tmp_path: Path) -> None:
    # covers: INF-400c-5
    # angle: criterion
    """Then a single declared vocabulary exists in one named location.

    Must be implemented as config/entry_kind_vocabulary.json with a
    non-empty "members" mapping -- this test is RED (FileNotFoundError)
    until that file is authored.
    """
    members = _load_vocabulary_members()
    assert isinstance(members, set)
    assert len(members) > 0, "the declared vocabulary must have at least one member"


def test_every_real_classifier_target_surface_value_is_a_vocabulary_member() -> None:
    # covers: INF-400c-5
    # angle: seam
    """Then every value the classifier can return is a member of that
    vocabulary.

    Pipes the REAL route-knowledge/SKILL.md taxonomy table (producer) into
    the REAL declared vocabulary config (consumer side of the reconciliation)
    and asserts every classifier-emitted value is routable -- not a
    hand-typed guess at what the 16 values are.
    """
    classifier_values = _load_classifier_target_surfaces()
    assert len(classifier_values) > 0, (
        "sanity: the real SKILL.md taxonomy table must have yielded some values"
    )
    vocabulary_members = _load_vocabulary_members()
    missing = classifier_values - vocabulary_members
    assert not missing, (
        f"classifier target_surface values with no vocabulary member: {sorted(missing)}"
    )


def test_every_vocabulary_member_has_a_harvester_routing_rule() -> None:
    # covers: INF-400c-5
    # angle: seam
    """Then every member of that vocabulary has a routing rule in the
    harvester, so the set of labels the classifier can produce and the set
    of kinds the harvester can route are the same set.

    Reads the REAL harvest_learnings.py source for its routable entry_kind
    set and compares it against the REAL vocabulary config -- both real
    artifacts, no mocking of either side of the seam.
    """
    vocabulary_members = _load_vocabulary_members()
    harvester_source = _HARVESTER_SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r"_KNOWN_ENTRY_KINDS:\s*frozenset\[str\]\s*=\s*frozenset\(\s*\{(.*?)\}\s*\)",
        harvester_source,
        flags=re.DOTALL,
    )
    assert match, "expected to find _KNOWN_ENTRY_KINDS in harvest_learnings.py"
    harvester_kinds = set(re.findall(r'"([a-zA-Z0-9-]+)"', match.group(1)))
    assert harvester_kinds == vocabulary_members, (
        "harvester's routable set must equal the declared vocabulary, not a "
        f"separately hand-maintained copy; harvester={sorted(harvester_kinds)} "
        f"vocabulary={sorted(vocabulary_members)}"
    )


def test_emit_knowledge_cli_writes_a_valid_event_for_a_vocabulary_member(tmp_path: Path) -> None:
    # covers: INF-400c-5
    # angle: reachability
    """When the emission helper is invoked via its real CLI entry point
    (the production surface the four shipped emit sites are meant to call)
    with an entry_kind that IS a member of the vocabulary, the event is
    written to the sink and its result is later consumed by the real
    harvester CLI -- not merely imported and called as a function.
    """
    members = _load_vocabulary_members()
    assert members, "sanity: need at least one real vocabulary member to test with"
    valid_kind = sorted(members)[0]

    sink_path = tmp_path / "knowledge_emissions.jsonl"
    dest_path = tmp_path / "captured_learning.md"

    emit_result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(dest_path),
        "--entry-kind", valid_kind,
        "--text", "A real learning body, distinct from any placeholder string.",
        "--sink", str(sink_path),
    )
    assert emit_result.returncode == 0, (
        f"CLI must exit 0 on acceptance; stderr={emit_result.stderr!r}"
    )
    assert sink_path.exists(), "an accepted emission must be written to the sink"
    lines = [ln for ln in sink_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["entry_kind"] == valid_kind
    for field in ("timestamp", "agent", "component", "destination", "entry_kind"):
        assert field in event, f"missing required digest field {field!r}"

    # Consumption in control flow: the REAL harvester CLI must be able to
    # drain this exact event and actually write the destination file.
    harvester_result = _run_harvester(
        "--sink", str(sink_path),
        "--state", str(tmp_path / "state.json"),
    )
    assert harvester_result.returncode == 0, (
        f"harvester must drain a valid, vocabulary-member event cleanly; "
        f"stdout={harvester_result.stdout!r} stderr={harvester_result.stderr!r}"
    )
    assert dest_path.exists(), "the harvester must have written the routed destination file"
    assert "A real learning body" in dest_path.read_text(encoding="utf-8")


def test_emit_knowledge_cli_rejects_out_of_vocabulary_entry_kind_and_writes_nothing(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-5
    # angle: failure
    """And an event whose entry_kind is outside the vocabulary is never
    written to the knowledge-emission sink.
    """
    sink_path = tmp_path / "knowledge_emissions.jsonl"
    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", "definitely-not-a-real-entry-kind",
        "--text", "This must never be persisted.",
        "--sink", str(sink_path),
    )
    assert not sink_path.exists() or sink_path.read_text(encoding="utf-8").strip() == "", (
        "an out-of-vocabulary entry_kind must never be written to the sink"
    )
    # The helper's own failure-handling contract (INF-400c-5-iii) requires
    # this to be non-fatal to the caller -- asserted more fully there, but
    # a crash here would also invalidate this AC's "never written" clause.
    assert result.returncode == 0
