"""
MODULE: test_handoff_signoff_completeness
GOAL: Assert that every agent-template section instructing its agent to hand
    work to a sibling via `(status: handoff)` also restates, IN THAT SAME
    SECTION, the full three-place atomic sign-off (frontmatter `agents:` map
    -> signed_off, AND the `## Sign-offs` checklist entry) -- not merely a
    substitution of one status tag for another.
BUSINESS CONTEXT: On 2026-09-14, python-coder took the Test Delegation
    handoff path while driving a real ticket. It set `python-coder:
    signed_off` in frontmatter and wrote a correct `(status: handoff)`
    comment, but left `- [ ] python-coder` unchecked in the Sign-offs
    checklist. The completion write correctly refused the ticket; the epic
    halted at batch 1 and four downstream tickets stayed blocked until the
    record was repaired by hand. Root cause: `## Test Delegation` step 2
    describes handoff purely as a status-tag substitution and never restates
    that the atomic three-place sign-off still applies in full. See
    AR-200a-2.
ARCHITECTURE: This is a pure prose-scanning test -- there is no production
    module to import. It parses every `templates/agents/*.md` file directly:
    strips YAML frontmatter, walks markdown headings to build a heading tree,
    and for every line matching the literal `(status: handoff)` instruction
    tag, resolves the SMALLEST enclosing section (from its own heading to the
    next heading of the same-or-shallower level) and inspects only that
    section's text -- never the whole file -- for the two required
    restatements. This section-scoping is the entire point: python-coder.md
    already has a *correct* three-place description elsewhere (its
    `## Sign-off` section, around line 632), so a whole-file substring search
    would give a false green. Mirrors the derive-both-sides-from-the-
    templates-themselves pattern in
    unit_tests/commit_guardian/test_agent_verification_consistency.py.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "templates" / "agents"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# The literal instruction tag an agent is told to emit when handing off.
# Deliberately requires the parentheses so it does not fire on prose that
# merely NAMES the tag in a list (e.g. retrospective-agent.md's
# "Status tags (`status: ok` / `status: blocker` / `status: handoff`)",
# where the parens wrap the whole list, not "status: handoff" alone).
HANDOFF_TAG_PATTERN = re.compile(r"\(status:\s*handoff\)", re.IGNORECASE)

# Markdown ATX heading: 1-6 leading '#' characters, a space, then the title.
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")

FRONTMATTER_DELIM = re.compile(r"^---\s*$")

# ---------------------------------------------------------------------------
# Frontmatter stripping
# ---------------------------------------------------------------------------


def _strip_frontmatter(raw_text: str) -> str:
    """Return the markdown body with any leading YAML frontmatter removed.

    Frontmatter is delimited by a line of exactly '---' at the very start of
    the file and a second such line closing it. Line 142 of python-coder.md
    (a `behavior:` field inside the YAML frontmatter) contains the literal
    substring "(status: handoff)" as *documentation of a field value*, not an
    instruction -- it must never be scanned as a candidate section.
    """
    lines = raw_text.splitlines()
    if lines and FRONTMATTER_DELIM.match(lines[0]):
        for idx in range(1, len(lines)):
            if FRONTMATTER_DELIM.match(lines[idx]):
                return "\n".join(lines[idx + 1 :])
    return raw_text


# ---------------------------------------------------------------------------
# Heading / section resolution
# ---------------------------------------------------------------------------


def _iter_headings(lines: list[str]):
    """Yield (line_index, level, title) for every markdown heading line."""
    for idx, line in enumerate(lines):
        match = HEADING_PATTERN.match(line)
        if match:
            yield idx, len(match.group(1)), match.group(2).strip()


def _section_for_line(
    headings: list[tuple[int, int, str]], target_idx: int
) -> tuple[int, int, str] | None:
    """Resolve the smallest enclosing section for a given body line index.

    A section runs from its own heading line to the next heading whose level
    is the same or shallower (e.g. a level-3 subsection under a level-2
    section ends at the next level-<=3 heading, which may itself be another
    level-3 sibling or the parent's own next level-2 sibling). This mirrors
    "from its markdown heading to the next heading of the same or higher
    level" from the ticket, matching how python-coder.md's `### Rule 2` /
    `### Rule 4`-style subsections in test-writer.md are scoped independently
    of their parent `##` section.

    Returns (start_idx, end_idx, heading_title), or None if the target line
    precedes every heading in the document (no enclosing section).
    """
    enclosing: tuple[int, int, int, str] | None = None
    for position, (heading_idx, level, title) in enumerate(headings):
        if heading_idx <= target_idx:
            enclosing = (position, heading_idx, level, title)
        else:
            break
    if enclosing is None:
        return None
    position, heading_idx, level, title = enclosing
    end_idx = None
    for next_heading_idx, next_level, _ in headings[position + 1 :]:
        if next_level <= level:
            end_idx = next_heading_idx
            break
    if end_idx is None:
        end_idx = 10**9  # sentinel: runs to end of file; clamped by caller
    return heading_idx, end_idx, title


def _find_handoff_sections(body_text: str) -> list[tuple[str, str]]:
    """Find every distinct section instructing emission of `(status: handoff)`.

    Returns a de-duplicated list of (heading_title, section_text) -- a
    section with multiple matching lines (e.g. Contract-Shrinkage Guard,
    which mentions the tag twice) is reported once, not once per line.
    """
    lines = body_text.splitlines()
    headings = list(_iter_headings(lines))
    seen_spans: set[tuple[int, int]] = set()
    sections: list[tuple[str, str]] = []

    for idx, line in enumerate(lines):
        if not HANDOFF_TAG_PATTERN.search(line):
            continue
        resolved = _section_for_line(headings, idx)
        if resolved is None:
            continue
        start_idx, end_idx, title = resolved
        clamped_end = min(end_idx, len(lines))
        span = (start_idx, clamped_end)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        sections.append((title, "\n".join(lines[start_idx:clamped_end])))

    return sections


# ---------------------------------------------------------------------------
# Section-content assertions
# ---------------------------------------------------------------------------


def _mentions_frontmatter_signoff(section_text: str) -> bool:
    """True if the section restates the frontmatter `agents:` map update."""
    return bool(re.search(r"frontmatter", section_text, re.IGNORECASE)) and bool(
        re.search(r"signed_off", section_text, re.IGNORECASE)
    )


def _mentions_signoffs_checklist(section_text: str) -> bool:
    """True if the section restates the `## Sign-offs` checklist entry."""
    checklist_phrase = re.search(
        r"sign-?offs?\s*(checklist|checkbox|entry|line)", section_text, re.IGNORECASE
    )
    heading_reference = re.search(r"##\s*sign-?offs?\b", section_text, re.IGNORECASE)
    return bool(checklist_phrase) or bool(heading_reference)


def _scan_all_templates() -> dict[Path, list[tuple[str, str]]]:
    """Scan every templates/agents/*.md for handoff-instructing sections.

    Returns a mapping of template path -> list of (heading_title,
    section_text) tuples found in that template. The set of paths is derived
    from the templates directory on disk, never hardcoded, so a newly added
    phase agent with an incomplete handoff instruction is caught without
    anyone editing this test.
    """
    results: dict[Path, list[tuple[str, str]]] = {}
    for template_path in sorted(AGENTS_DIR.glob("*.md")):
        raw_text = template_path.read_text(encoding="utf-8")
        body = _strip_frontmatter(raw_text)
        sections = _find_handoff_sections(body)
        if sections:
            results[template_path] = sections
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandoffInstructionRequiresFullAtomicSignoff(unittest.TestCase):
    """Every handoff-instructing section must restate the full atomic sign-off."""

    def setUp(self) -> None:
        self.assertTrue(
            AGENTS_DIR.is_dir(), f"Agent templates directory not found: {AGENTS_DIR}"
        )

    def test_handoff_instruction_requires_full_atomic_signoff(self) -> None:
        # covers: AR-200a-2
        # angle: criterion
        """AR-200a-2: an agent told to hand work onward is told to sign off
        completely, not partially.

        For every templates/agents/*.md, scan for any section instructing
        the agent to emit `(status: handoff)`. For each one found, assert
        that the SAME section also requires both (a) the frontmatter
        `agents:` map update to `signed_off`, and (b) the `## Sign-offs`
        checklist entry -- not merely a status-tag substitution. Both sides
        of the check are derived from the templates on disk, so a newly
        added phase agent with an incomplete handoff instruction fails
        immediately without anyone editing this test.
        """
        offending: list[str] = []
        per_template_sections = _scan_all_templates()

        for template_path, sections in per_template_sections.items():
            relative_path = template_path.relative_to(REPO_ROOT)
            for heading_title, section_text in sections:
                has_frontmatter = _mentions_frontmatter_signoff(section_text)
                has_checklist = _mentions_signoffs_checklist(section_text)
                if has_frontmatter and has_checklist:
                    continue
                missing = []
                if not has_frontmatter:
                    missing.append(
                        "frontmatter `agents:` map update to `signed_off`"
                    )
                if not has_checklist:
                    missing.append("`## Sign-offs` checklist entry")
                offending.append(
                    f"{relative_path} :: section '{heading_title}' instructs "
                    f"(status: handoff) but its own section text omits: "
                    f"{' AND '.join(missing)}"
                )

        self.assertEqual(
            offending,
            [],
            "Handoff-instructing sections must restate the full atomic "
            "sign-off (frontmatter update AND Sign-offs checklist entry) in "
            "the SAME section as the handoff instruction -- describing "
            "handoff as merely substituting one status tag for another lets "
            "an agent flip its frontmatter to signed_off while leaving its "
            "own Sign-offs checkbox unchecked (the exact defect observed "
            "2026-09-14 in python-coder's `## Test Delegation` step 2). "
            "Offending sections:\n" + "\n".join(offending),
        )


class TestScanFindsAtLeastOneHandoffInstruction(unittest.TestCase):
    """Non-vacuity guard for the scan above."""

    def test_scan_finds_at_least_one_handoff_instruction(self) -> None:
        # covers: AR-200a-2
        # angle: reachability
        """AR-200a-2 non-vacuity guard: the scan must actually locate at
        least one handoff-instructing section across the template set.

        Without this guard, a scanner whose pattern matches nothing would
        pass the rule test in
        TestHandoffInstructionRequiresFullAtomicSignoff trivially -- having
        examined zero templates -- exactly the silent-no-op failure this
        repository's own defences have hit three separate times (the
        feedback_categories.yaml path, the AC-validator bare-directory glob,
        and the stale merge-audit ref).
        """
        per_template_sections = _scan_all_templates()
        total_sections = sum(len(v) for v in per_template_sections.values())

        self.assertGreater(
            total_sections,
            0,
            "Scan located zero handoff-instructing sections across "
            f"{AGENTS_DIR} -- expected at least one real match (e.g. "
            "templates/agents/python-coder.md's `## Test Delegation` "
            "section, which instructs `(status: handoff)`). A pattern that "
            "matches nothing would pass the rule test vacuously; fix the "
            "detection pattern in _find_handoff_sections / "
            "HANDOFF_TAG_PATTERN before trusting a green result.",
        )


if __name__ == "__main__":
    unittest.main()
