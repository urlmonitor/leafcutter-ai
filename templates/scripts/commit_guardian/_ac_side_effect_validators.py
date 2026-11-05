"""
MODULE: scripts/commit_guardian/_ac_side_effect_validators.py
GOAL: Hold the declares_side_effect derivation and its commit-time validator,
    moved verbatim out of _ac_schema_validators.py (ACD-200b-2).
BUSINESS CONTEXT: BO-2900g-2 / BO-2900g-2-i / BO-2900g-2-ii. The value that
    routes a ticket's user-surface-smoker phase must be DERIVED from the AC's
    own Then clause, never authored by opinion; a disagreement is reported by
    record id rather than silently resolved.
ARCHITECTURE: Pure-function helpers, stdlib only, no I/O. Sibling of
    _ac_schema_validators.py, which re-exports ``derive_declares_side_effect``
    and ``validate_declares_side_effect`` so every existing import keeps working.
    Deploys with the directory (the build copies every .py in
    templates/scripts/commit_guardian/).

DECISION HISTORY:
  - 2026-10-21 [python-coder/ACD-200b-2]: Created by moving the block verbatim
    to repay the file-size ratchet on _ac_schema_validators.py. The BO-2900g-2-ii
    rationale for the patterns below is unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# declares_side_effect derivation (BO-2900g-2 / BO-2900g-2-i)
# ---------------------------------------------------------------------------

# Matches the FIRST Gherkin "Then" clause (line-start, case-insensitive); the
# derivation reads everything from that point to the end of the criteria text
# so a trailing "And" continuation of the Then clause is considered too — the
# same reasoning check_ac_schema's other Gherkin-aware helpers already use.
_THEN_CLAUSE_START_RE = re.compile(r"\bThen\b", re.IGNORECASE)

# A "Because" clause states WHY a criterion exists. It routinely describes effects
# belonging to OTHER work — "the same file is deployed to consumer projects" — so
# reading it as something this record asserts is a category error (BO-2900g-2-ii).
# It is stripped before the durable-effect search.
#
# CASE-SENSITIVE ON PURPOSE. Gherkin keywords are capitalised at line start; a
# wrapped line beginning with a lowercase "because" is mid-sentence prose. An
# earlier case-insensitive version of this pattern swallowed the rest of
# BP-1500d-3's Then clause — including a genuine "leaves the record file written
# to disk" — because one of its wrapped lines happens to start with "because".
# Measured: case-sensitive flips exactly one record (the false positive it was
# written for) and breaks no authored value; case-insensitive flipped two.
_BECAUSE_CLAUSE_RE = re.compile(
    r"^[ \t]*Because\b.*?(?=^[ \t]*(?:Given|When|Then)\b|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Nouns whose being written outlives the run. BO-2900g-2-ii: the discriminator
# for a durable effect is the OBJECT written, not the verb — "a record file is
# written" persists, "before any test is written" is a human authoring a test
# later, and neither the verb nor its tense tells them apart.
_DURABLE_OBJECT = (
    r"(?:file|files|record|records|artifact|artifacts|entry|entries|"
    r"document|documents|index|manifest|AC|criterion|ticket|log)"
)

# Destinations that are observable but NOT durable: they are gone when the
# terminal closes, so a write to one is not the "file that exists and can be
# read back afterwards" BO-2900g-2 asks for.
_TRANSIENT_DESTINATION = (
    r"(?:the\s+|either\s+)?(?:error|output|standard)\s+(?:stream|output)|"
    r"either\s+stream|both\s+streams|stdout|stderr|the\s+terminal|"
    r"the\s+console|screen"
)

# Durable, observable-outside-the-process effect phrases. Deliberately narrow
# and phrase-based (not single common words like "created" or "recorded" in
# isolation) so the derivation marks a STRICT subset of the store rather than
# "everything that ever writes anything" — a derivation that marks everything
# is indistinguishable from one that marks nothing one gate later (BO-2900g-2
# constraints). Calibrated against the real on-disk store at authoring time:
# ~3.6% of records with a Then clause matched (114 of 3148).
# The two object-aware forms below (BO-2900g-2-ii): rationale in DECISION HISTORY.
_DURABLE_EFFECT_RE = re.compile(
    r"written to disk|written to a file|"
    # (a) a durable noun governs the verb directly: "a record file is written"
    rf"\b{_DURABLE_OBJECT}\s+(?:is|are)\s+written\b|"
    # (b) the write names a destination, and that destination is not a stream
    rf"\b(?:is|are)\s+written\s+(?:to|into|under)\s+(?!{_TRANSIENT_DESTINATION})|"
    r"writes? (?:a|the|an) (?:file|record)|persist(?:ed|s)?\b|"
    r"saved to disk|\bis saved\b|\bare saved\b|"
    r"saves? (?:a|the|an) (?:file|record)|record is persisted|"
    r"created on disk|removed from disk|deletes? (?:a|the|an)? ?file|"
    r"state-changing command|leaves the system in a different state|"
    r"changes? the system.s state|commits? (?:a|the) (?:change|transaction)|"
    r"pushed to|deployed to|updates? the (?:database|store)|"
    r"a file is written|a record is persisted",
    re.IGNORECASE,
)


def derive_declares_side_effect(data: dict[str, Any]) -> bool:
    """Derive whether an AC's own criteria assert a durable, observable effect.

    BO-2900g-2: the declaration that routes a ticket's ``user-surface-smoker``
    phase agent must be DERIVED from the record's own Then clause — a file
    written, a record persisted, a state-changing command — never authored by
    opinion. Only Gherkin ``Then`` clauses (and anything trailing them within
    the same scenario, e.g. a following ``And``) are examined; a durable-effect
    phrase appearing only in a ``Given`` clause does not count, because the
    Given describes pre-existing state, not what this AC's own work does.

    ``Because`` clauses are stripped before the search: they state why a
    criterion exists, not what it asserts, and routinely cite effects owned by
    other work (BO-2900g-2-ii).

    KNOWN GAP, DELIBERATELY NOT FIXED HERE (BO-2900g-2-ii). The paragraph above
    is the intent; it is not quite the behaviour. The search runs from the FIRST
    ``Then`` to the END of the criteria, so on a multi-scenario record every
    LATER scenario's ``Given`` and ``When`` is searched as well. A durable-effect
    phrase in a later Given therefore still counts, which the paragraph above
    says it should not.

    Bounding each scenario on a line-initial ``Given`` was implemented and
    measured while narrowing the pattern, then reverted and left to its own
    change. It moves three more records into disagreement with their authored
    value — BO-2400c-1-v, UXP-612 and UXP-614 — and at least two of those are
    arguable rather than clear: UXP-612 and UXP-614 do produce a real file, and
    only ever say so in a ``When``. Bundling it would have made this change
    breach its own acceptance criterion that the number of disagreeing records
    must not rise, and would have decided two judgement calls inside a change
    about a regular expression.

    Args:
        data: Parsed AC YAML content.

    Returns:
        True when the criteria's Then clause asserts a durable, observable
        effect; False when criteria are absent, contain no Then clause, or
        the Then clause asserts only a returned value / in-memory result.
    """
    criteria = data.get("criteria")
    if not criteria or not isinstance(criteria, str):
        return False
    # Rationale is not assertion: a Because clause explains why the criterion
    # exists and often cites effects owned by other work (BO-2900g-2-ii).
    asserted = _BECAUSE_CLAUSE_RE.sub("", criteria)
    match = _THEN_CLAUSE_START_RE.search(asserted)
    if match is None:
        return False
    then_onward = asserted[match.start():]
    return bool(_DURABLE_EFFECT_RE.search(then_onward))


def validate_declares_side_effect(path: Path, data: dict[str, Any]) -> list[str]:
    """Validate that ``declares_side_effect`` matches what the criteria derive.

    Runs on staged files only (forward ratchet — the existing store is not
    retroactively validated, same posture as ``validate_test_contract``).

    Two failure shapes, both required by BO-2900g-2's "never silently
    overwritten, never silently ignored" constraint:

    - The Then clause asserts a durable effect but ``declares_side_effect``
      is absent/null/false — the record must gain the declaration.
    - ``declares_side_effect`` is explicitly authored and DISAGREES with the
      derived value in either direction — the disagreement is reported by
      record id rather than silently resolved either way.

    Args:
        path: Filesystem path to the AC file (for error messages).
        data: Parsed AC YAML content.

    Returns:
        List of error message strings; empty when the declaration matches
        the derivation (including the common case where both are False/absent).
    """
    derived = derive_declares_side_effect(data)
    authored = data.get("declares_side_effect")

    if authored is None:
        if derived:
            return [
                f"{path}: criteria assert a durable, observable effect (a file "
                f"written, a record persisted, a state-changing command) but "
                f"declares_side_effect is not set — add declares_side_effect: "
                f"true. This value must be DERIVED from the AC's own Then "
                f"clause, not authored by opinion (BO-2900g-2)."
            ]
        return []

    if bool(authored) != derived:
        return [
            f"{path}: declares_side_effect is authored as {authored!r} but this "
            f"AC's own Then clause derives {derived!r} — the two disagree. "
            f"Fix the authored value or the criteria text; a derived value must "
            f"never be silently overwritten and a disagreement must never be "
            f"silently ignored (BO-2900g-2)."
        ]
    return []
