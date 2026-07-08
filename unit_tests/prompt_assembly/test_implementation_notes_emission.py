"""
Tests for Implementation Notes emission and thin dispatch.

Verifies:
- generate_ticket_from_ac.py emits ## Implementation Notes from it_requirements (BO-2000c-1)
- generator omits the section when it_requirements is absent (BO-2000c-1-i)
- build-ticket.js dispatch string instructs the agent to read the ticket (BO-2000c-3/-3-i/-4)

These are test-FIRST stubs: they import a function signature that does not
yet exist (_build_ticket_body accepting it_requirements) and assert behaviours
not yet implemented. Tests must be RED on first run.

Covers: BO-2000c-1, BO-2000c-1-i, BO-2000c-2, BO-2000c-3, BO-2000c-3-i, BO-2000c-4
"""
from __future__ import annotations

import os
import re
import sys
import unittest

# ---------------------------------------------------------------------------
# Path bootstrap — make scripts/ importable
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.ac_store.generate_ticket_from_ac import _build_ticket_body  # noqa: E402

_BUILD_TICKET_JS = os.path.join(
    _REPO_ROOT, "templates", "workflows-js", "build-ticket.js"
)

# ---------------------------------------------------------------------------
# Minimal AC fixture helpers
# ---------------------------------------------------------------------------


def _make_ac(with_it_requirements: bool = True) -> dict:
    """Build a minimal AC record for testing."""
    ac: dict = {
        "id": "BO-2000c-1",
        "title": "Emit Implementation Notes",
        "criteria": "Given an AC with it_requirements, the generator emits the section.",
        "assigned_agent": "python-coder",
        "component": "ticket_creation_pipeline",
        "estimated_complexity": "M",
    }
    if with_it_requirements:
        ac["it_requirements"] = {
            "config_schema_fragment": "implementation_notes:\n  key: value",
            "reference_file": "docs/architecture/components/build-ticket-workflow-dispatch.md",
            "n_location_rule": "Emit once per ticket; place before ## Sign-offs.",
            "required_skills": ["signoff", "building-epics"],
            "post_write_commands": ["python scripts/build.py --validate"],
        }
    return ac


class TestGeneratorEmitsImplementationNotes(unittest.TestCase):
    """AC-1 (BO-2000c-1): when it_requirements is present, ## Implementation Notes is emitted."""

    def test_generator_emits_implementation_notes_when_it_requirements_present(self):
        # covers: BO-2000c-1
        # covers: BO-2000c-2
        """The generated ticket body must contain ## Implementation Notes reproducing it_requirements verbatim."""
        ac = _make_ac(with_it_requirements=True)
        body = _build_ticket_body(ac, "BO-2000c-1")

        self.assertIn(
            "## Implementation Notes",
            body,
            "Expected '## Implementation Notes' section in ticket body when "
            "AC record carries it_requirements.",
        )
        # Verify verbatim reproduction of the config_schema_fragment field
        self.assertIn(
            "implementation_notes:",
            body,
            "config_schema_fragment must appear verbatim in ## Implementation Notes.",
        )
        # Verify the reference_file path is present
        self.assertIn(
            "build-ticket-workflow-dispatch.md",
            body,
            "reference_file path must appear verbatim in ## Implementation Notes.",
        )


class TestGeneratorOmitsSectionWhenAbsent(unittest.TestCase):
    """AC-2 (BO-2000c-1-i): when it_requirements is absent, section is omitted."""

    def test_generator_omits_section_when_absent(self):
        # covers: BO-2000c-1-i
        """The generated ticket body must NOT contain ## Implementation Notes when it_requirements is absent."""
        ac = _make_ac(with_it_requirements=False)
        body = _build_ticket_body(ac, "BO-2000c-1-i")

        self.assertNotIn(
            "## Implementation Notes",
            body,
            "## Implementation Notes must NOT appear when AC has no it_requirements.",
        )


class TestDispatchPromptInstructsReadTicketAndStaysThin(unittest.TestCase):
    """AC-4 (BO-2000c-3/-3-i/-4): build-ticket.js dispatch instructs read-ticket and stays thin."""

    def _read_build_ticket_js(self) -> str:
        try:
            with open(_BUILD_TICKET_JS, encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            self.skipTest(f"build-ticket.js not readable: {exc}")
            return ""

    def test_dispatch_prompt_instructs_read_ticket_and_stays_thin(self):
        # covers: BO-2000c-3
        # covers: BO-2000c-3-i
        # covers: BO-2000c-4
        """The phase dispatch string must instruct the agent to read the ticket before starting."""
        js_source = self._read_build_ticket_js()

        # Find the phase dispatch line — it contains "Execute your phase"
        dispatch_pattern = re.compile(
            r"You are the.*?phase agent for ticket.*?Execute your phase.*?",
            re.DOTALL,
        )
        dispatch_match = dispatch_pattern.search(js_source)

        self.assertIsNotNone(
            dispatch_match,
            "Could not locate the phase dispatch string in build-ticket.js. "
            "Expected a string containing 'You are the ... phase agent for ticket ... Execute your phase'.",
        )

        # The dispatch string must instruct the agent to read the ticket
        # Acceptable phrase: "Read the ticket before starting" (case-insensitive)
        dispatch_excerpt = js_source[
            max(0, js_source.find("Execute your phase") - 200):
            js_source.find("Execute your phase") + 400
        ]
        self.assertRegex(
            dispatch_excerpt,
            re.compile(r"read the ticket", re.IGNORECASE),
            "The phase dispatch string must instruct the agent to 'Read the ticket' "
            "before executing its phase. Current dispatch lacks this instruction.",
        )

        # Verify it remains thin: must not inline the full spec beyond
        # phase name, ticket_path, and files_touched
        # The dispatch should NOT contain keywords like 'it_requirements' or
        # large implementation spec blocks.
        self.assertNotIn(
            "it_requirements",
            dispatch_excerpt,
            "The dispatch string must NOT inline it_requirements (spec must travel via ticket body).",
        )


if __name__ == "__main__":
    unittest.main()
