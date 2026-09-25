#!/usr/bin/env python3
"""
MODULE: _gtfa_constants
GOAL: Hold every module-level constant and the ``AcRecord`` type alias that the
    ticket generator's parts share, so that no two of them can drift into
    disagreeing copies of the same vocabulary.
BUSINESS CONTEXT: Several of these constants are mirrors of a source of truth
    that lives elsewhere — ``_TEST_ANGLES`` mirrors the ``test_spec[].angle``
    enum in ``config/ac_store_schema.json``, ``_SOURCE_CODE_EXTENSIONS`` is
    derived from ``_PROSE_PATH_EXTENSIONS``, and the phase orders mirror the
    dispatch order the build drive actually uses. A second copy of any of them
    inside a sibling module would be a silent fork of a gate's vocabulary.
ARCHITECTURE: Pure data. Imports nothing from the rest of the generator, so it
    can be imported first by every other sibling without an import cycle. The
    ``generate_ticket_from_ac`` shell re-exports all of these names, and the
    test suites read several of them off the shell
    (``_CANONICAL_PHASE_ORDER``, ``_FLOW_CHANGE_PHASE_ORDER``, ``_TEST_ANGLES``)
    — so the re-export is part of the contract, not a convenience.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
_DEFAULT_TICKETS_ROOT = "tickets/00_inbox"

#: The two angles this module EMITS on derived test descriptors. The wider
#: vocabulary is 5 core (criterion, reachability, seam, real_artifact, deployed)
#: plus 3 conditional (boundary, failure, discrimination) — see ``_TEST_ANGLES``
#: below — with must_block a modifier on reachability that this module neither
#: emits nor reads. The trigger table for the remaining angles is separate
#: work; do NOT infer it from these two constants.
TEST_ANGLE_CRITERION = "criterion"
TEST_ANGLE_REACHABILITY = "reachability"

#: The full angle vocabulary, MIRRORED from the ``test_spec[].angle`` enum in
#: config/ac_store_schema.json (which is the source of truth and the gate — the
#: check-ac-schema hook rejects anything else at authoring time). Kept as a local
#: copy so ticket generation never depends on locating the schema file in a
#: consumer layout; the two copies are pinned together by a set-equality test in
#: unit_tests/ac_store/test_derived_test_reachability_floor.py. Used ONLY to warn
#: on an unrecognised authored value — this module does not reject one.
#: 'discrimination' (TQ-500f-1) is the eighth member, added alongside the same
#: name in config/ac_store_schema.json and config/test_requirements.schema.json
#: in one change (the three lists are held in lockstep by
#: unit_tests/prompt_assembly/test_bp_1100g_1.py's three-way comparator).
_TEST_ANGLES = frozenset({
    TEST_ANGLE_CRITERION,
    TEST_ANGLE_REACHABILITY,
    "seam",
    "real_artifact",
    "deployed",
    "boundary",
    "failure",
    "discrimination",
})

#: Assertion text carried by every derived reachability-floor descriptor. It is
#: deliberately an instruction, not a stub: the AC authored no ``test_spec``, so
#: nothing in the store names the production entry point — the test author has
#: to resolve it. Deleting the entry instead is the phantom-done path.
_REACHABILITY_ASSERTS = (
    "REQUIRED — invoke the production entry point (CLI, hook, slash command, "
    "workflow dispatch, or main()) as a subprocess/dispatch and assert the new "
    "behaviour actually occurs. Do NOT satisfy this by importing the function "
    "directly. The AC authored no test_spec, so the entry point is not declared: "
    "resolve it before writing this test, and do not delete this entry."
)

#: doc_links relationships that represent a real edit surface (i.e. the linked
#: file is a file the implementing agent must modify or create). Paths with these
#: relationships enter ``files_touched``. Relationships not in this set (e.g.
#: ``describes``, ``related``) are informational only and must NOT enter
#: ``files_touched``.
_EDIT_SURFACE_RELATIONSHIPS: frozenset[str] = frozenset(
    {"constrains", "creates", "implements", "modifies", "specifies"}
)

#: Recognized file extensions for path detection in prose bullet strings.
#: Only tokens whose final component carries one of these suffixes are treated
#: as source file paths (TKT-500f-8-i path-detection rule).
_PROSE_PATH_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".md", ".yaml", ".yml", ".json", ".js", ".ts", ".sql",
    ".txt", ".toml", ".cfg", ".ini", ".html", ".css", ".sh",
})

#: Documentation and configuration file extensions excluded from source-code
#: detection.  Used to derive _SOURCE_CODE_EXTENSIONS from _PROSE_PATH_EXTENSIONS.
_DOC_CONFIG_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".cfg", ".ini",
})

#: Recognised source-code file extensions that signal a code-ticket for AC-gate
#: wiring.  Derived from _PROSE_PATH_EXTENSIONS (the prose-path-detection allowlist)
#: by removing documentation and configuration suffixes, then extended with common
#: non-Python and frontend source extensions, then explicitly excluding markup,
#: style, and shell files that must NOT gate AC validation (TKT-500f-14,
#: TKT-500f-14-ii).
#:
#: Excluded (not gating source): .html, .css, .sh — markup/style/shell.
#: Included beyond the derived set: .tsx, .jsx, .vue, .svelte (frontend framework);
#:   .go (Go), .rs (Rust), .mjs (ES module) — common non-Python source languages.
#:
#: DECISION HISTORY:
#:   TKT-500f-14 (prior): initial derivation from _PROSE_PATH_EXTENSIONS.
#:   TKT-500f-14-ii (2026-07-21): Added explicit exclusion of .html/.css/.sh
#:   (markup/style/shell are not gating source code) and added .go/.rs/.mjs so
#:   non-Python source files correctly trigger ac-validator/ac-fulfillment-gate.
_SOURCE_CODE_EXTENSIONS: frozenset[str] = (
    (
        (_PROSE_PATH_EXTENSIONS - _DOC_CONFIG_EXTENSIONS)
        | frozenset({".tsx", ".jsx", ".vue", ".svelte", ".go", ".rs", ".mjs"})
    )
    - frozenset({".html", ".css", ".sh"})
)

#: Known coder agents — any of these as the AC's assigned_agent signals a code
#: ticket regardless of files_touched content (TKT-500f-14).
_KNOWN_CODERS: frozenset[str] = frozenset({"python-coder", "frontend-coder", "sql-coder"})

#: Path prefixes that identify extension-less tokens as source paths.
#: A token that begins with one of these prefixes is included even when it
#: carries no recognized file extension (TKT-500f-8-i path-detection rule).
_KNOWN_PATH_PREFIXES: tuple[str, ...] = (
    "scripts/",
    "docs/",
    "templates/",
    "unit_tests/",
    "tests/",
    "leafcutter/",
    "alembic/",
)

#: Matches candidate path tokens in prose text.
#: Requires at least one ``/`` separator; admits the character set of typical
#: POSIX file paths (alphanumeric, ``_``, ``.``, ``-``, ``/``).  The pattern
#: is anchored so that each match begins and ends on a word character,
#: preventing trailing punctuation from being captured as part of the path.
#: The leading component allows a single OPTIONAL ``.`` so that dotfile-
#: prefixed paths (e.g. ``.github/workflows/ci.yml``) are captured intact
#: instead of having their leading dot excluded from the match (bonus defect
#: found alongside ACD-400b-6: a bare ``[A-Za-z0-9_]`` first-character class
#: made ``re.finditer`` start one character late, at ``g`` in
#: ``github/workflows/ci.yml``, silently dropping the dot).
_PROSE_PATH_TOKEN_RE: re.Pattern[str] = re.compile(
    r"\.?[A-Za-z0-9_][A-Za-z0-9_.\-]*/[A-Za-z0-9_./\-]*[A-Za-z0-9_]"
)

#: Canonical support agents always added to every generated ticket.
_CANONICAL_SUPPORT_AGENTS: list[str] = [
    "test-writer",
    "test-runner",
    "pr-reviewer",
    "commit",
    "pull-request",
]

#: Agents always set to not_needed unless the AC's assigned_agent is sql-coder.
_SQL_AGENTS: list[str] = ["sql-coder"]

#: Agents always set to not_needed in generated tickets.
_NOT_NEEDED_AGENTS: list[str] = [
    "documentation-expert",
]

#: Canonical phase order for agent map output.
#: user-surface-smoker (priority 11.5) sits between pr-reviewer (11) and ac-validator (11.5)
#: so that the observable-side-effect smoke check runs before AC coverage validation and
#: before commit. A ticket with user-surface-smoker: needed cannot reach done
#: with the smoke check unrun (BP-1100f-5).
#: documentation-verifier is placed immediately before commit (BO-2200d-2):
#: it is the last verification gate before the ticket is committed, so it
#: must follow pr-reviewer, ac-validator, and ac-fulfillment-gate.
_CANONICAL_PHASE_ORDER: list[str] = [
    "architect-review",
    "test-writer",
    "python-coder",
    "sql-coder",
    "frontend-coder",  # BO-2200d-2-i: must precede documentation-expert
    "test-runner",
    "documentation-expert",
    "pr-reviewer",
    "user-surface-smoker",  # priority 11.5 — observable-side-effect gate (BP-1100f-5)
    "ac-validator",
    "ac-fulfillment-gate",
    "documentation-verifier",
    "commit",
    "pull-request",
]

#: Phase order for flow-change pairs: documentation-expert is placed before
#: any coder (priority 4 → doc planning before implementation).
#: user-surface-smoker is included at priority 11.5 for consistency with
#: _CANONICAL_PHASE_ORDER so flow-change tickets also gate correctly.
#: documentation-verifier is placed immediately before commit (BO-2200d-2),
#: consistent with _CANONICAL_PHASE_ORDER.
_FLOW_CHANGE_PHASE_ORDER: list[str] = [
    "architect-review",
    "documentation-expert",
    "test-writer",
    "python-coder",
    "sql-coder",
    "frontend-coder",  # BO-2200d-2-i: consistent with _CANONICAL_PHASE_ORDER
    "test-runner",
    "pr-reviewer",
    "user-surface-smoker",  # priority 11.5 — observable-side-effect gate (BP-1100f-5)
    "ac-validator",
    "ac-fulfillment-gate",
    "documentation-verifier",
    "commit",
    "pull-request",
]

#: Default path of the agent registry relative to the repo root.
_DEFAULT_AGENT_REGISTRY = "config/agent_registry.json"

#: Default path of the guardrail gates config relative to the repo root.
_DEFAULT_GUARDRAIL_GATES = "config/guardrail_gates.yaml"

#: Default path of the location-keyed phase-deferral declaration (TKT-600b-1)
#: relative to the repo root.
_DEFAULT_PHASE_DEFERRAL = "config/phase_deferral.yaml"

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

AcRecord = dict[str, Any]
