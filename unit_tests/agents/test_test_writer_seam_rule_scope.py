"""
MODULE: test_test_writer_seam_rule_scope
GOAL: Lock the SCOPING of "Rule 3 — Cross-layer seam test required" in
    templates/agents/test-writer.md.

    The defect these tests guard against: Rule 3 lives inside the
    "## Source-of-Truth Discipline" section, whose preamble scopes the whole
    section to test-REPAIR work ("These rules fire whenever you are repairing,
    updating, or rewriting tests for existing production code"). Under that
    scoping Rule 3 never fires on NEW work, which is precisely where the
    cross-layer seam goes untested. Ten catalogued production incidents trace
    to this — e.g. EPIC-ComputedQualityGates (41 green tests, 7 sign-offs,
    while all three real call sites still used the old
    _build_agents_map(assigned_agent) signature, so "the legacy path always
    ran"), and BO-1700 where run_checks() never invoked six helpers that were
    each unit-tested directly.

    These tests assert the STRUCTURE of the scoping, not the exact prose:
      1. the section preamble still scopes rules generally to repair work
         (so the fix was a carve-out, not a blanket rescope);
      2. the preamble carries a Rule-3 exception clause, positioned BEFORE the
         first "### Rule" heading so it actually governs section scope;
      3. Rule 3's own trigger sentence admits new work and no longer reads
         "the function under repair" as its only entry condition;
      4. Rule 3's substance survives — the integration-style seam test and the
         "mocking both sides is insufficient" clause;
      5. any section cross-reference inside Rule 3 resolves to a heading that
         actually exists in the file (guards a dangling forward-reference).

WHAT THESE TESTS DO NOT PROVE: this file reads a prompt template as text. It
    cannot prove an LLM obeys the rescoped rule at runtime. It proves the
    instruction's scope cannot be silently reverted to repair-only, and that
    the rule's substance cannot be deleted while the scope words remain.

TICKET: (none — direct fix on fix/test-angle-reachability-floor)
"""

from __future__ import annotations

import re
from pathlib import Path


class _RepoRootNotFound(RuntimeError):
    """Raised when no ancestor directory holds both templates/ and config/."""

    def __init__(self) -> None:
        super().__init__("repo root (dir containing templates/ and config/) not found")


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "templates").is_dir() and (candidate / "config").is_dir():
            return candidate
    raise _RepoRootNotFound


_ROOT = _repo_root()
_TEMPLATE = _ROOT / "templates" / "agents" / "test-writer.md"

_SECTION_HEADING = "## Source-of-Truth Discipline"
_RULE_HEADING_RE = re.compile(r"^###\s+Rule\s+(\d+)\b.*$", re.MULTILINE)

# Tokens that mark a scope as universal rather than repair-only. Any one of
# them, in a sentence that also names Rule 3, is an acceptable carve-out — the
# assertion is on the semantics (universal scope), not on one exact phrasing.
_UNIVERSAL_SCOPE_TOKENS = (
    "all work",
    "new and repair",
    "repair and new",
    "new work",
    "newly written",
    "newly-written",
    "not repair-only",
    "not repair only",
    "regardless of whether",
    "every ticket",
)

_EXCEPTION_TOKENS = ("except", "exception", "not repair-only", "not repair only", "regardless")


def _read() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")


def _discipline_section(text: str) -> str:
    """Text of '## Source-of-Truth Discipline' up to the next '## ' heading."""
    start = text.find(_SECTION_HEADING)
    assert start != -1, f"{_SECTION_HEADING!r} section not found in {_TEMPLATE}"
    rest = text[start + len(_SECTION_HEADING):]
    match = re.search(r"^##\s+(?!#)", rest, re.MULTILINE)
    end = match.start() if match else len(rest)
    return rest[:end]


def _preamble(section: str) -> str:
    """Section text before the first '### Rule N' heading."""
    match = _RULE_HEADING_RE.search(section)
    assert match, "no '### Rule N' headings found in the Source-of-Truth Discipline section"
    return section[: match.start()]


def _rule_body(section: str, number: int) -> str:
    """Body of '### Rule <number>' up to the next '### ' heading."""
    headings = list(_RULE_HEADING_RE.finditer(section))
    for idx, match in enumerate(headings):
        if int(match.group(1)) == number:
            end = headings[idx + 1].start() if idx + 1 < len(headings) else len(section)
            return section[match.start(): end]
    raise AssertionError(f"'### Rule {number}' heading not found")


def _contains_any(haystack: str, needles) -> bool:
    low = haystack.lower()
    return any(n in low for n in needles)


# ---------------------------------------------------------------------------
# 1. The other rules keep their repair-only scope (this was a carve-out, not a
#    blanket rescope of the whole section).
# ---------------------------------------------------------------------------

def test_section_preamble_still_scopes_general_rules_to_repair_work():
    # covers: UNKNOWN
    preamble = _preamble(_discipline_section(_read()))
    assert re.search(
        r"repairing,\s+updating,\s+or\s+rewriting\s+tests", preamble
    ), (
        "The Source-of-Truth Discipline preamble no longer scopes its general "
        "rules to test-repair work. Rules 1, 2, 4 and 5 are repair-only by "
        "design; only Rule 3 was meant to be widened. Restore the "
        "'repairing, updating, or rewriting tests' scope sentence."
    )


# ---------------------------------------------------------------------------
# 2. The preamble carves Rule 3 out of that repair-only scope, and does so
#    BEFORE the first rule heading so it governs the section.
# ---------------------------------------------------------------------------

def test_preamble_carves_rule_3_out_of_the_repair_only_scope():
    # covers: UNKNOWN
    section = _discipline_section(_read())
    preamble = _preamble(section)

    # Find the sentence(s) in the preamble that name Rule 3.
    sentences = re.split(r"(?<=[.!?])\s+", preamble)
    rule3_sentences = [s for s in sentences if re.search(r"\bRule\s*3\b", s)]
    assert rule3_sentences, (
        "The Source-of-Truth Discipline preamble does not mention Rule 3. "
        "Because the preamble scopes the section to test-repair work, Rule 3 "
        "(cross-layer seam test) never fires on NEW work unless the preamble "
        "explicitly carves it out. Add a scope-exception sentence naming Rule 3."
    )

    carve_out = [
        s for s in rule3_sentences
        if _contains_any(s, _UNIVERSAL_SCOPE_TOKENS) or _contains_any(s, _EXCEPTION_TOKENS)
    ]
    assert carve_out, (
        "The preamble mentions Rule 3 but does not declare it an exception to "
        "the repair-only scope. The sentence must mark Rule 3's scope as "
        "universal (e.g. 'fires on ALL work — new and repair alike') or as an "
        "explicit exception. Sentences found: " + repr(rule3_sentences)
    )

    assert any(_contains_any(s, _UNIVERSAL_SCOPE_TOKENS) for s in carve_out), (
        "The Rule 3 carve-out names an exception but never says what the wider "
        "scope IS. It must state that Rule 3 applies to new work as well as "
        "repair work. Sentences found: " + repr(carve_out)
    )


# ---------------------------------------------------------------------------
# 3. Rule 3's own trigger admits new code — it is no longer gated on "the
#    function under repair".
# ---------------------------------------------------------------------------

def test_rule_3_trigger_is_not_gated_on_repair_only():
    # covers: UNKNOWN
    body = _rule_body(_discipline_section(_read()), 3)

    assert not re.search(r"the function under repair sits at a layer boundary", body), (
        "Rule 3's trigger still reads 'the function under repair sits at a "
        "layer boundary'. That phrasing excludes newly-written code at a layer "
        "boundary — the case the rule most needs to cover. Reword the trigger "
        "so it covers new and repaired code alike."
    )

    assert _contains_any(body, _UNIVERSAL_SCOPE_TOKENS), (
        "Rule 3's body never states that it applies to new work. Even with the "
        "preamble carve-out, the rule text itself must read correctly for "
        "newly-written code (e.g. 'newly written or under repair')."
    )


def test_rule_3_trigger_still_enumerates_layer_boundaries():
    # covers: UNKNOWN
    body = _rule_body(_discipline_section(_read()), 3)
    assert "layer boundary" in body, "Rule 3 no longer names a layer boundary as its trigger"
    for seam in ("SQL", "ORM", "API handler", "frontend", "agent producer", "agent consumer"):
        assert seam in body, f"Rule 3's layer-boundary enumeration lost {seam!r}"


# ---------------------------------------------------------------------------
# 4. Rule 3's substance survives — the rescope must not have hollowed it out.
# ---------------------------------------------------------------------------

def test_rule_3_retains_integration_test_requirement_and_mocking_clause():
    # covers: UNKNOWN
    body = _rule_body(_discipline_section(_read()), 3)

    assert "integration-style test" in body, (
        "Rule 3 no longer requires an integration-style test."
    )
    assert re.search(
        r"pipes a representative\s+producer output directly into the consumer", body
    ) or re.search(
        r"pipes a representative producer output directly into the consumer",
        " ".join(body.split()),
    ), "Rule 3 no longer requires piping real producer output into the consumer."

    # The load-bearing clause: mocking both sides does not count as coverage.
    normalized = " ".join(body.split())
    assert (
        "mock both sides of the seam are insufficient as the sole coverage" in normalized
    ), (
        "Rule 3 lost the 'unit tests that mock both sides of the seam are "
        "insufficient as the sole coverage' clause. That clause is the whole "
        "point of the rule — widening its scope must not delete its substance."
    )


# ---------------------------------------------------------------------------
# 5. No dangling forward-reference from Rule 3 to a section that does not exist.
# ---------------------------------------------------------------------------

def test_rule_3_has_no_dangling_section_cross_reference():
    # covers: UNKNOWN
    text = _read()
    body = _rule_body(_discipline_section(text), 3)
    headings = {
        line.strip().lstrip("#").strip().lower()
        for line in text.splitlines()
        if line.strip().startswith("#")
    }
    for referenced in re.findall(r"`?#{2,3}\s+([A-Z][^`\n]*?)`", body):
        assert referenced.strip().lower() in headings, (
            f"Rule 3 cross-references a section {referenced.strip()!r} that has "
            "no matching heading in templates/agents/test-writer.md."
        )
    # Explicit guard for the known future section that does not exist yet.
    if "Required Test Angles" in body:
        assert "required test angles" in headings, (
            "Rule 3 references a 'Required Test Angles' section, but no such "
            "heading exists in templates/agents/test-writer.md. That section is "
            "a separate, later change — this edit must be self-contained."
        )


# ---------------------------------------------------------------------------
# 6. The skip-rule fallback must not re-introduce the pre-fix derivation.
#
#    When a code ticket arrives with an empty/absent '## Test Requirements'
#    block, the skip rule tells test-writer to derive the contract from the AC
#    itself. Deriving it from the Gherkin Then-clauses alone reproduces EXACTLY
#    the AC-literal-only shape that generate_ticket_from_ac.py's reachability
#    floor was added to eliminate — one test per Then clause, nothing that
#    invokes a production entry point. The two derivations must agree.
# ---------------------------------------------------------------------------

_SKIP_RULE_HEADING = "### Skip rule"


def _skip_rule_section(text: str) -> str:
    """Text of the '### Skip rule' subsection up to the next '## '/'### ' heading."""
    start = text.find(_SKIP_RULE_HEADING)
    assert start != -1, f"{_SKIP_RULE_HEADING!r} section not found in {_TEMPLATE}"
    rest = text[start + len(_SKIP_RULE_HEADING):]
    match = re.search(r"^#{2,3}\s+(?!#)", rest, re.MULTILINE)
    end = match.start() if match else len(rest)
    return rest[:end]


def test_skip_rule_fallback_requires_a_reachability_test():
    # covers: UNKNOWN
    section = _skip_rule_section(_read())
    normalized = " ".join(section.split())

    assert "Then-clauses" in normalized or "Then clauses" in normalized, (
        "The skip-rule fallback no longer mentions deriving the contract from "
        "the AC's Gherkin Then-clauses — re-check this test against the new "
        "wording before deleting it."
    )

    assert "production entry point" in normalized.lower(), (
        "The skip-rule fallback tells test-writer to derive the test contract "
        "from the AC's Gherkin Then-clauses, but never requires a test that "
        "invokes the PRODUCTION ENTRY POINT. That is the pre-fix derivation: "
        "one AC-literal test per Then clause and no reachability floor — the "
        "exact shape generate_ticket_from_ac.py was changed to stop emitting. "
        "A manually-derived contract must not be weaker than the generated one."
    )

    assert re.search(r"import\w*\b[^.]*\bdoes NOT satisfy", normalized, re.IGNORECASE), (
        "The skip-rule fallback requires a reachability test but does not say "
        "that importing the function and calling it directly fails to satisfy "
        "it. Without that clause the cheapest green is a direct-import test, "
        "which is what the floor exists to rule out."
    )
