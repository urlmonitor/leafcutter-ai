"""
MODULE: test_bo_2200c_5
GOAL: RED test stubs for BO-2200c-5 — the Agent Contracts block is the single
      source both the writer reads and the verifier asserts.

These tests verify the 'single source of truth' invariant required by BO-2200c-5:
  1. The generated doc-required ticket contains EXACTLY ONE '## Agent Contracts'
     block — not zero (missing), not two or more (duplicated/parallel).
  2. No secondary parallel required-docs section exists anywhere in the ticket body
     that could drift from the Agent Contracts block.
  3. The block uses the EXACT line shapes that both documentation-expert Contract-Aware
     Mode and documentation-verifier parse: '## Agent Contracts' / '### documentation-expert'
     / '- [ ] AC-N:' — any deviation breaks both consumers.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-5.yaml

Why these tests may be RED before implementation:
  If the implementation accidentally emits '## Agent Contracts' once per trigger
  condition (once for documentation-expert AND once for delivers_to), there would be
  TWO headings. The 'both triggers' test catches that regression directly.
  If the format diverges from the exact parser-expected strings, the Contract-Aware
  Mode simulation test returns zero items (RED).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import (  # noqa: E402
    _build_ticket_body,
    _build_agent_contracts_section,
)

# ---------------------------------------------------------------------------
# Exact line shapes that both consumers parse (copied verbatim from the AC
# constraint text so they serve as a literal specification, not a paraphrase).
# ---------------------------------------------------------------------------

_EXACT_H2_HEADING = "## Agent Contracts"
_EXACT_H3_SUBHEADING = "### documentation-expert"
_AC_CHECKBOX_REGEX = re.compile(r"^- \[ \] AC-\d+:", re.MULTILINE)

# Prohibited alternative sections that would create a second required-docs list
# alongside the Agent Contracts block, violating the n_location_rule='1' constraint.
_PROHIBITED_PARALLEL_SECTIONS = [
    "## Documentation Requirements",
    "## Required Documentation",
    "## Documentation Checklist",
    "## Doc Requirements",
    "## Documentation Needed",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_doc_required_ac() -> dict:
    """Return a minimal doc-required AC dict.

    Uses documentation_triggers and doc_links so that documentation-expert is
    triggered when the agents_map includes it as 'needed'.

    IMPORTANT: criteria text deliberately avoids the literal strings
    '## Agent Contracts' and '### documentation-expert' to prevent false
    positives in assertIn() / regex checks on the body.
    """
    return {
        "id": "BO-2200C5-UNIT",
        "title": "Single-source Agent Contracts block fixture",
        "component": "build-orchestration",
        "assigned_agent": "python-coder",
        "estimated_complexity": "M",
        "documentation_triggers": ["reference-doc"],
        "criteria": (
            "Given a generated ticket that requires documentation,\n"
            "When the generator builds the ticket body,\n"
            "Then the ticket has exactly one block declaring documentation requirements,\n"
            "And there is no second separately maintained list of what must be documented."
        ),
        "doc_links": [
            {
                "path": "docs/reference/single-source.md",
                "relationship": "describes",
                "status": "exists",
            }
        ],
    }


def _make_doc_agents_map() -> dict:
    """Pre-computed agents map that includes documentation-expert as needed."""
    return {
        "architect-review": "needed",
        "test-writer": "needed",
        "python-coder": "needed",
        "test-runner": "needed",
        "documentation-expert": "needed",
        "pr-reviewer": "needed",
        "commit": "needed",
        "pull-request": "needed",
    }


# ---------------------------------------------------------------------------
# TestGeneratorEmitsSingleAgentContractsBlock
# BO-2200c-5
# ---------------------------------------------------------------------------


class TestGeneratorEmitsSingleAgentContractsBlock(unittest.TestCase):
    """BO-2200c-5: A generated doc-required ticket contains exactly one
    '## Agent Contracts' documentation-expert block and no second required-docs list.

    RED before implementation if the generator either:
    - Does not emit the block (count == 0), OR
    - Emits the block more than once (count > 1 — one per trigger condition), OR
    - Emits a prohibited parallel section alongside the block.
    """

    def test_generator_emits_single_agent_contracts_block(self) -> None:
        # covers: BO-2200c-5
        """A generated doc-required ticket must contain EXACTLY ONE '## Agent Contracts'
        section heading.

        The single-source guarantee (n_location_rule='1') means the block is emitted
        once — never zero (missing) and never two or more (duplicated).

        0 occurrences means the block is absent — BO-2200c-1's emission rule is not met.
        2+ occurrences means the block is duplicated — BO-2200c-5's single-source rule is
        violated and the two copies can drift from each other.

        Implementation requirement: _build_ticket_body must emit the '## Agent Contracts'
        heading exactly once, regardless of how many trigger conditions are active.
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C5-UNIT", agents_map=agents_map)

        occurrences = re.findall(
            r"^## Agent Contracts\s*$", body, re.MULTILINE
        )
        self.assertEqual(
            len(occurrences),
            1,
            f"Expected EXACTLY ONE '## Agent Contracts' heading on its own line, "
            f"but found {len(occurrences)}.\n\n"
            f"n_location_rule='1' requires the block to appear in exactly one location.\n"
            f"0 = block missing (BO-2200c-1 not satisfied); 2+ = block duplicated "
            f"(BO-2200c-5 single-source guarantee violated).\n\n"
            f"Fix: ensure _build_agent_contracts_section emits the '## Agent Contracts' "
            f"heading ONCE at the start of the returned block, and that _build_ticket_body "
            f"only appends the section once.\n\n"
            f"Actual body:\n{body}",
        )

    def test_no_second_required_docs_list_in_generated_ticket(self) -> None:
        # covers: BO-2200c-5
        """No parallel required-docs section must appear alongside '## Agent Contracts'.

        Any section named '## Documentation Requirements', '## Required Documentation',
        etc. would create a second source of documentation requirements that can drift
        from the Agent Contracts block, violating the single-source guarantee.

        This test guards against future regressions where a coder adds such a section.
        It will fail RED if any of the prohibited headings appear in the generated body.
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C5-UNIT", agents_map=agents_map)

        for heading in _PROHIBITED_PARALLEL_SECTIONS:
            found = bool(
                re.search(
                    r"^" + re.escape(heading) + r"\s*$",
                    body,
                    re.MULTILINE,
                )
            )
            self.assertFalse(
                found,
                f"Found prohibited parallel required-docs section '{heading}' "
                f"in the generated ticket body.\n\n"
                f"Documentation requirements must appear ONLY in "
                f"'## Agent Contracts / ### documentation-expert'. A second section "
                f"creates a drift risk and violates BO-2200c-5's single-source guarantee.\n\n"
                f"Actual body:\n{body}",
            )

    def test_single_block_when_both_triggers_active(self) -> None:
        # covers: BO-2200c-5
        """Still EXACTLY ONE '## Agent Contracts' heading when both trigger conditions
        are active simultaneously: documentation-expert needed AND delivers_to / expects_from
        are non-null.

        This is the most direct RED scenario: if the implementation emits the heading
        once per trigger condition (once for doc_expert_needed and once for delivers_to),
        there would be TWO '## Agent Contracts' headings — violating n_location_rule='1'.

        Both conditions must contribute SUBSECTIONS within the SAME block, never
        triggering an additional heading.

        RED before fix if _build_agent_contracts_section accidentally repeats the
        '## Agent Contracts' line when both doc_expert_needed AND delivers_to are true.
        """
        ac_with_both_triggers = {
            "id": "BO-2200C5-BOTH",
            "title": "Both trigger conditions active simultaneously",
            "component": "build-orchestration",
            "assigned_agent": "python-coder",
            "estimated_complexity": "M",
            "documentation_triggers": ["reference-doc"],
            "delivers_to": {
                "agent": "documentation-verifier",
                "contract": (
                    "The block is both the verifier checklist and the writer brief."
                ),
            },
            "expects_from": {
                "ac_id": "BO-2200c-1",
                "contract": "The block whose single-source role this establishes.",
            },
            "criteria": (
                "Given an AC with both documentation and cross-agent contract fields,\n"
                "When the generator builds the ticket body,\n"
                "Then the ticket has exactly one block declaring all contracts."
            ),
            "doc_links": [
                {
                    "path": "docs/reference/both-triggers.md",
                    "relationship": "describes",
                    "status": "exists",
                }
            ],
        }
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(
            ac_with_both_triggers, "BO-2200C5-BOTH", agents_map=agents_map
        )

        occurrences = re.findall(r"^## Agent Contracts\s*$", body, re.MULTILINE)
        self.assertEqual(
            len(occurrences),
            1,
            f"Expected EXACTLY ONE '## Agent Contracts' heading even when BOTH "
            f"documentation-expert (needed) AND delivers_to/expects_from are active.\n\n"
            f"Found {len(occurrences)} occurrence(s).\n\n"
            f"Both trigger conditions must add SUBSECTIONS within the same block, "
            f"not emit the H2 heading multiple times.\n\n"
            f"Fix: ensure the '## Agent Contracts' heading is the first line of "
            f"_build_agent_contracts_section's output exactly once, regardless of how "
            f"many subsections are added below it.\n\n"
            f"Actual body:\n{body}",
        )


# ---------------------------------------------------------------------------
# TestBlockLineShapeMatchesBothReaderContracts
# BO-2200c-5
# ---------------------------------------------------------------------------


class TestBlockLineShapeMatchesBothReaderContracts(unittest.TestCase):
    """BO-2200c-5: The emitted block uses the literal '## Agent Contracts' /
    '### documentation-expert' / '- [ ] AC-N:' shape that documentation-expert
    Contract-Aware Mode and documentation-verifier both parse.

    RED before implementation if the block uses a variant format (e.g., different
    casing, different hash count, or a different checkbox pattern).
    """

    def test_block_line_shape_matches_both_reader_contracts(self) -> None:
        # covers: BO-2200c-5
        """The Agent Contracts block must use the EXACT line shape that both consumers
        expect at runtime.

        Consumer 1 — documentation-expert Contract-Aware Mode (in documentation-expert.md):
          Keys on:
          - '## Agent Contracts'       (two hashes, exact)
          - '### documentation-expert' (three hashes, lowercase, exact)
          - '- [ ] AC-N:'              (checkbox with integer N)

        Consumer 2 — documentation-verifier:
          Also reads the same '- [ ] AC-N:' checklist to assert documentation was
          produced and to check items off (flip to '- [x] AC-N:').

        Both consumers MUST parse the IDENTICAL source — the single block serves as
        the writer's brief AND the verifier's checklist, keeping them in lockstep.

        Any format variation (e.g., '## Agents Contracts', '### Documentation Expert',
        '- [ ] AC N:' without the colon, or '* AC-1:') breaks both parsers and is RED.
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C5-UNIT", agents_map=agents_map)

        # Shape 1: EXACT H2 heading on its own line (two hashes, exact casing)
        self.assertTrue(
            bool(re.search(r"^## Agent Contracts\s*$", body, re.MULTILINE)),
            f"Expected EXACT heading '## Agent Contracts' (two hashes, exact casing) "
            f"on its own line, but it was not found.\n\n"
            f"This is the anchor that both documentation-expert Contract-Aware Mode and "
            f"documentation-verifier search for. Any variation breaks both parsers.\n\n"
            f"Actual body (first 800 chars):\n{body[:800]}",
        )

        # Shape 2: EXACT H3 subheading on its own line (three hashes, lowercase)
        self.assertTrue(
            bool(re.search(r"^### documentation-expert\s*$", body, re.MULTILINE)),
            f"Expected EXACT subheading '### documentation-expert' (three hashes, "
            f"lowercase with hyphen) on its own line, but it was not found.\n\n"
            f"documentation-expert Contract-Aware Mode reads this exact string to "
            f"locate its brief. Case variation or different formatting breaks the parser.\n\n"
            f"Actual body (first 800 chars):\n{body[:800]}",
        )

        # Shape 3: At least one '- [ ] AC-N:' checkbox line (exact format)
        ac_n_matches = _AC_CHECKBOX_REGEX.findall(body)
        self.assertGreater(
            len(ac_n_matches),
            0,
            f"Expected at least one '- [ ] AC-N:' checkbox line (where N is a positive "
            f"integer), but none were found.\n\n"
            f"Both consumers require this exact pattern:\n"
            f"  - documentation-expert reads it as a contract item to fulfill.\n"
            f"  - documentation-verifier reads it as a checklist item to assert against.\n\n"
            f"The format must be EXACTLY '- [ ] AC-<integer>:' with square brackets, "
            f"a space inside the brackets, and a colon after the integer.\n\n"
            f"Actual body (first 800 chars):\n{body[:800]}",
        )

    def test_contract_aware_mode_parser_can_extract_items(self) -> None:
        # covers: BO-2200c-5
        """A simulation of documentation-expert Contract-Aware Mode successfully
        extracts at least one AC item from the generated Agent Contracts block.

        This test encodes the EXACT parsing algorithm that documentation-expert uses:
          1. Find the '## Agent Contracts' section (content up to the next H2).
          2. Within that, find the '### documentation-expert' subsection.
          3. Extract all '- [ ] AC-N:' lines as contract items.

        If the generated block format deviates from this algorithm's expectations,
        the parser returns zero items and the test fails RED.

        The test is RED before the fix if:
        - The block is absent ('## Agent Contracts' section not found), OR
        - The subsection is missing ('### documentation-expert' not within the block), OR
        - The checkbox lines use a different format (not '- [ ] AC-N:'), OR
        - The subsection appears OUTSIDE the Agent Contracts block (wrong nesting).
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C5-UNIT", agents_map=agents_map)

        # Step 1: Extract the Agent Contracts section content (up to next H2 or end)
        agent_contracts_match = re.search(
            r"^## Agent Contracts\s*\n(.+?)(?=^## |\Z)",
            body,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(
            agent_contracts_match,
            f"Contract-Aware Mode parser: '## Agent Contracts' section not found.\n\n"
            f"The section must start with '## Agent Contracts' on its own line, followed "
            f"by content up to the next '## ' heading or end of string.\n\n"
            f"Actual body:\n{body}",
        )

        contracts_content = agent_contracts_match.group(1)

        # Step 2: Find '### documentation-expert' subsection within the block
        doc_expert_match = re.search(
            r"^### documentation-expert\s*\n(.+?)(?=^### |\Z)",
            contracts_content,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(
            doc_expert_match,
            f"Contract-Aware Mode parser: '### documentation-expert' not found "
            f"within the '## Agent Contracts' section.\n\n"
            f"The subsection must appear INSIDE '## Agent Contracts' so that both "
            f"documentation-expert and documentation-verifier can parse it from the "
            f"same block.\n\n"
            f"Agent Contracts section content:\n{contracts_content}",
        )

        doc_expert_content = doc_expert_match.group(1)

        # Step 3: Extract '- [ ] AC-N:' lines from the subsection
        checkbox_items = re.findall(
            r"^- \[ \] AC-\d+:.*$", doc_expert_content, re.MULTILINE
        )
        self.assertGreater(
            len(checkbox_items),
            0,
            f"Contract-Aware Mode parser found '## Agent Contracts / ### documentation-expert' "
            f"but extracted ZERO '- [ ] AC-N:' items from the subsection.\n\n"
            f"Both documentation-expert (brief) and documentation-verifier (checklist) "
            f"require at least one '- [ ] AC-N:' item in the subsection to function.\n\n"
            f"documentation-expert section content:\n{doc_expert_content}",
        )

    def test_ac_n_format_is_checkable_by_verifier(self) -> None:
        # covers: BO-2200c-5
        """The '- [ ] AC-N:' format must be the exact checkable format that allows
        documentation-verifier to flip items to '- [x] AC-N:' when validated.

        documentation-verifier checks off items by flipping '- [ ]' to '- [x]'.
        The SINGLE SOURCE guarantee means the verifier reads from the SAME block
        that documentation-expert populated — so the format must support this flip.

        This test asserts that:
        1. The checkbox format is '- [ ]' (space inside brackets — checkable format).
        2. It is NOT '- [x]' (already checked — verifier cannot check what's done).
        3. The AC-N numbering uses a hyphen: 'AC-<integer>' not 'AC <integer>'.

        RED before fix if the format uses a non-checkable variant (e.g., '* AC-1:',
        '- [x] AC-1:' pre-checked, or '- [] AC-1:' with no space inside brackets).
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        section = _build_agent_contracts_section(ac, "BO-2200C5-UNIT", agents_map)

        # The section must contain at least one unchecked '- [ ] AC-N:' line.
        unchecked_pattern = re.compile(r"^- \[ \] AC-\d+:", re.MULTILINE)
        unchecked = unchecked_pattern.findall(section)
        self.assertGreater(
            len(unchecked),
            0,
            f"Expected at least one unchecked '- [ ] AC-N:' line in the "
            f"Agent Contracts section.\n\n"
            f"This format is the one documentation-verifier flips to '- [x] AC-N:' "
            f"when it asserts documentation was produced.\n\n"
            f"Section:\n{section}",
        )

        # There must be NO pre-checked '- [x] AC-N:' items — the block is emitted
        # unchecked by the generator; only the agents themselves check items off.
        prechecked_pattern = re.compile(r"^- \[x\] AC-\d+:", re.MULTILINE)
        prechecked = prechecked_pattern.findall(section)
        self.assertEqual(
            len(prechecked),
            0,
            f"Found {len(prechecked)} pre-checked '- [x] AC-N:' item(s) in the "
            f"generated Agent Contracts section.\n\n"
            f"The generator must emit UNCHECKED items only — the checkboxes are flipped "
            f"by the agents (documentation-expert, documentation-verifier) at runtime, "
            f"not pre-checked at generation time.\n\n"
            f"Section:\n{section}",
        )

        # The numbering must use the hyphen form 'AC-<integer>', not 'AC <integer>'
        # (the hyphen separates 'AC' from the number in the parser-expected format).
        for item in unchecked:
            self.assertIn(
                "AC-",
                item,
                f"Expected 'AC-' (with hyphen) in the checkbox item '{item}', "
                f"but the hyphen is missing.\n\n"
                f"The Contract-Aware Mode parser keys on 'AC-' to identify globally-"
                f"numbered contract items. Items without the hyphen are not recognized.",
            )


# ---------------------------------------------------------------------------
# TestListFormDeliversToDoesNotBreakSingleSource
# BO-2200c-5 regression — list-form delivers_to crashes _build_agent_contracts_section
# ---------------------------------------------------------------------------


class TestListFormDeliversToDoesNotBreakSingleSource(unittest.TestCase):
    """BO-2200c-5 regression: when delivers_to is a LIST (as BA/IT-PO v3 authors
    emit it), _build_agent_contracts_section must NOT crash with AttributeError.

    Current state (RED before fix):
        'list' object has no attribute 'get'

    Root cause: _build_agent_contracts_section calls delivers_to.get("agent", "")
    which assumes a dict. BA/IT-PO v3 can emit delivers_to as a list of dicts
    (e.g. [{"agent": "doc-verifier", "contract": "..."}]) instead of a bare dict.
    The code was written assuming the dict form; list-form ACs crash the generator.

    Fix (python-coder): iterate list-or-dict in _build_agent_contracts_section
    so that BOTH forms produce a valid single ## Agent Contracts block.

    Single-source connection: if the crash occurs, the Agent Contracts block is
    never emitted → the single-source guarantee is violated (documentation-expert
    and documentation-verifier have no shared block to read from).

    MEMORY reference: build-ac generator crashes on list-form delivers_to
    (feedback_build_ac_generator_delivers_to_list_crash.md):
    'generate_ticket_from_ac.py `_build_agent_contracts_section` does
    delivers_to.get()/expects_from.get() assuming dicts, but BA/IT-PO v3 emit
    them as LISTS → AttributeError ... Fix: iterate list-or-dict in that fn +
    regression test.'
    """

    def test_list_form_delivers_to_does_not_crash_section_builder(self) -> None:
        # covers: BO-2200c-5
        """_build_agent_contracts_section must not raise AttributeError when
        delivers_to is a list rather than a dict.

        RED before fix: 'list' object has no attribute 'get' at line
          agent_name = delivers_to.get("agent", "")

        After fix: the function iterates over the list entries and emits a
        '### Delivers To' subsection within the SINGLE '## Agent Contracts' block.
        """
        ac_with_list_delivers_to = {
            "id": "BO-2200C5-LIST-DT",
            "title": "Test list-form delivers_to handling",
            "component": "build-orchestration",
            "documentation_triggers": ["reference-doc"],
            "delivers_to": [
                {
                    "agent": "documentation-verifier",
                    "contract": (
                        "The block is the verifier checklist and the writer brief."
                    ),
                }
            ],
            "doc_links": [],
            "criteria": (
                "Given an AC with list-form delivers_to,\n"
                "When the generator builds the Agent Contracts section,\n"
                "Then the section is emitted without crashing."
            ),
        }
        agents_map = _make_doc_agents_map()

        # Before the fix this raises:
        #   AttributeError: 'list' object has no attribute 'get'
        # at _build_agent_contracts_section line:
        #   agent_name = delivers_to.get("agent", "")
        try:
            section = _build_agent_contracts_section(
                ac_with_list_delivers_to, "BO-2200C5-LIST-DT", agents_map
            )
        except AttributeError as exc:
            self.fail(
                f"_build_agent_contracts_section raised AttributeError when "
                f"delivers_to is a list: {exc}\n\n"
                f"This is the list-form bug: the code calls delivers_to.get('agent', '') "
                f"which assumes a dict. BA/IT-PO v3 emits delivers_to as a list of dicts.\n\n"
                f"Fix: in _build_agent_contracts_section, handle delivers_to as either "
                f"a dict OR a list of dicts — iterate the list and render each entry "
                f"as a '- **Agent:** ...' / '- **Contract:** ...' pair under '### Delivers To'."
            )

        # After fix: exactly ONE '## Agent Contracts' heading in the output.
        occurrences = section.count("## Agent Contracts")
        self.assertEqual(
            occurrences,
            1,
            f"Expected EXACTLY ONE '## Agent Contracts' heading in the section "
            f"when delivers_to is a list, but found {occurrences}.\n\n"
            f"Single-source guarantee: even when delivers_to is a list (multi-entry), "
            f"the block must use one heading and emit subsections within it.\n\n"
            f"Actual section:\n{section}",
        )

    def test_single_block_when_delivers_to_is_list_and_doc_expert_needed(self) -> None:
        # covers: BO-2200c-5
        """The FULL _build_ticket_body call must not crash and must produce exactly
        ONE '## Agent Contracts' block when delivers_to is a list AND documentation-expert
        is in the agents map as 'needed'.

        This is the end-to-end version of the list-form regression test. The
        single-source guarantee requires the block to always be emitted correctly
        regardless of the delivers_to format — dict or list.

        RED before fix: _build_ticket_body calls _build_agent_contracts_section which
        crashes with AttributeError when delivers_to is a list.
        """
        ac_with_list_delivers_to = {
            "id": "BO-2200C5-BOTH-LIST",
            "title": "End-to-end: list-form delivers_to + doc expert needed",
            "component": "build-orchestration",
            "assigned_agent": "python-coder",
            "estimated_complexity": "M",
            "documentation_triggers": ["reference-doc"],
            "delivers_to": [
                {
                    "agent": "documentation-verifier",
                    "contract": "Single-source verifier contract.",
                }
            ],
            "doc_links": [],
            "criteria": (
                "Given an AC with list-form delivers_to and doc expert needed,\n"
                "When the ticket generator runs,\n"
                "Then the ticket body contains exactly one Agent Contracts block."
            ),
        }
        agents_map = _make_doc_agents_map()

        try:
            body = _build_ticket_body(
                ac_with_list_delivers_to, "BO-2200C5-BOTH-LIST", agents_map=agents_map
            )
        except AttributeError as exc:
            self.fail(
                f"_build_ticket_body raised AttributeError when delivers_to is a list: {exc}\n\n"
                f"The list-form bug in _build_agent_contracts_section propagates up to "
                f"_build_ticket_body, preventing ticket generation entirely.\n\n"
                f"Fix: handle list-or-dict form for delivers_to in "
                f"_build_agent_contracts_section."
            )

        # Single-source: exactly ONE '## Agent Contracts' heading.
        occurrences = re.findall(r"^## Agent Contracts\s*$", body, re.MULTILINE)
        self.assertEqual(
            len(occurrences),
            1,
            f"Expected EXACTLY ONE '## Agent Contracts' heading even with list-form "
            f"delivers_to and documentation-expert needed.\n"
            f"Found {len(occurrences)} occurrence(s).\n"
            f"Actual body:\n{body}",
        )

    def test_list_form_expects_from_does_not_crash_section_builder(self) -> None:
        # covers: BO-2200c-5
        """_build_agent_contracts_section must not raise AttributeError when
        expects_from is a list rather than a dict.

        The same list-form bug affects expects_from as well as delivers_to:
            upstream_ac_id = expects_from.get("ac_id", "")
        raises AttributeError when expects_from is a list.

        RED before fix: AttributeError on expects_from.get("ac_id", "").
        After fix: the function iterates list entries and emits '### Expects From'.
        """
        ac_with_list_expects_from = {
            "id": "BO-2200C5-LIST-EF",
            "title": "Test list-form expects_from handling",
            "component": "build-orchestration",
            "documentation_triggers": ["reference-doc"],
            "expects_from": [
                {
                    "ac_id": "BO-2200c-1",
                    "contract": "The block whose single-source role this establishes.",
                }
            ],
            "doc_links": [],
            "criteria": (
                "Given an AC with list-form expects_from,\n"
                "When the generator builds the Agent Contracts section,\n"
                "Then the section is emitted without crashing."
            ),
        }
        agents_map = _make_doc_agents_map()

        try:
            section = _build_agent_contracts_section(
                ac_with_list_expects_from, "BO-2200C5-LIST-EF", agents_map
            )
        except AttributeError as exc:
            self.fail(
                f"_build_agent_contracts_section raised AttributeError when "
                f"expects_from is a list: {exc}\n\n"
                f"The same list-form bug affects expects_from: the code calls "
                f"expects_from.get('ac_id', '') which assumes a dict.\n\n"
                f"Fix: handle expects_from as either a dict OR a list of dicts — "
                f"iterate the list and render each entry under '### Expects From'."
            )

        # After fix: the section must exist and have exactly ONE heading.
        self.assertEqual(
            section.count("## Agent Contracts"),
            1,
            f"Expected exactly ONE '## Agent Contracts' heading; got "
            f"{section.count('## Agent Contracts')}.\n"
            f"Actual section:\n{section}",
        )


if __name__ == "__main__":
    unittest.main()
