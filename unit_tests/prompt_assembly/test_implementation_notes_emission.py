"""
Tests for Implementation Notes emission and thin dispatch.

Verifies:
- generate_ticket_from_ac.py emits ## Implementation Notes from it_requirements (BO-2000c-1)
- generator omits the section when it_requirements is absent (BO-2000c-1-i)
- build-ticket.js dispatch string instructs the agent to read the ticket (BO-2000c-4)
- reference_pattern globs in it_requirements are resolved to concrete paths (BO-2000c-3)
- unresolvable reference_pattern globs raise an authoring error (BO-2000c-3-i)

These are test-FIRST stubs: they import a function signature that does not
yet exist (_build_ticket_body accepting it_requirements with pattern resolution)
and assert behaviours not yet implemented. Tests must be RED on first run.

Covers: BO-2000c-1, BO-2000c-1-i, BO-2000c-2, BO-2000c-3, BO-2000c-3-i, BO-2000c-4
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
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


class TestReferencePatternResolution(unittest.TestCase):
    """AC-3 (BO-2000c-3 / BO-2000c-3-i): reference_pattern globs must be resolved, not emitted raw."""

    def _make_ac_with_pattern(self, reference_pattern: str) -> dict:
        """Build a minimal AC whose it_requirements carries a reference_pattern glob."""
        return {
            "id": "BO-2000c-3",
            "title": "Reference-pattern resolution",
            "criteria": (
                "Given an AC whose it_requirements names a reference file via a "
                "reference pattern, the generator resolves it to a concrete path."
            ),
            "assigned_agent": "python-coder",
            "component": "build_orchestration",
            "estimated_complexity": "M",
            "it_requirements": {
                "reference_pattern": reference_pattern,
                "n_location_rule": "Resolve before emitting.",
            },
        }

    def test_ac3_reference_pattern_resolves_to_paths(self):
        # covers: BO-2000c-3
        """BO-2000c-3: A glob reference_pattern that resolves to one file must appear
        as the concrete resolved path in Implementation Notes — not as the raw
        wildcard pattern string.

        To make this test green, _build_ticket_body (or the helper it calls) must:
        - Detect the 'reference_pattern' key in it_requirements.
        - Expand the glob against the repo root (or an absolute path).
        - Replace the raw pattern with the resolved concrete path.
        - Raise ValueError when the pattern resolves to zero or multiple files
          (covered by test_ac3i_unresolvable_pattern_errors).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a single file that the glob will match.
            target_filename = "resolved_ref_module.py"
            target_file = os.path.join(tmpdir, target_filename)
            try:
                with open(target_file, "w", encoding="utf-8") as fh:
                    fh.write("# placeholder for glob resolution test\n")
            except OSError as exc:
                self.skipTest(f"Could not create temp file for glob test: {exc}")

            # The glob pattern contains a wildcard — the raw pattern and the
            # resolved concrete path are therefore distinguishable.
            glob_pattern = os.path.join(tmpdir, "resolved_ref_*.py")
            ac = self._make_ac_with_pattern(glob_pattern)

            body = _build_ticket_body(ac, "BO-2000c-3")

            # The raw glob pattern (which contains '*') must NOT appear verbatim.
            self.assertNotIn(
                "resolved_ref_*.py",
                body,
                "The Implementation Notes must NOT emit the raw glob wildcard pattern. "
                "The reference_pattern must be resolved to a concrete file path before "
                "being written into the ticket body.",
            )
            # The resolved concrete filename MUST appear.
            self.assertIn(
                target_filename,
                body,
                "The Implementation Notes must contain the concrete resolved filename "
                f"'{target_filename}' after glob resolution. "
                f"Pattern used: {glob_pattern!r}",
            )

    def test_ac3i_unresolvable_pattern_errors(self):
        # covers: BO-2000c-3-i
        """BO-2000c-3-i: A reference_pattern that matches no file must raise an
        authoring error naming the AC id and the unresolvable pattern — it must
        NOT silently emit the raw pattern into the ticket body.

        To make this test green, _build_ticket_body (or the helper it calls) must:
        - Detect the 'reference_pattern' key in it_requirements.
        - Attempt glob expansion; detect zero matches.
        - Raise ValueError (or a subclass) whose message includes the AC id and
          the unresolvable pattern string.
        - Never silently emit the broken/raw pattern into the ticket body.
        """
        # A pattern that is guaranteed to match no file.
        no_match_pattern = "/tmp/this_path_does_not_exist_xyz_leafcutter_test/*.py"
        ac = self._make_ac_with_pattern(no_match_pattern)
        ac["id"] = "BO-2000c-3-i"  # ensure the AC id appears in the error message

        with self.assertRaises(ValueError) as ctx:
            _build_ticket_body(ac, "BO-2000c-3-i")

        err_msg = str(ctx.exception)
        # The error must name the AC id so the author knows which AC is broken.
        self.assertIn(
            "BO-2000c-3-i",
            err_msg,
            "The authoring error must name the AC id to help the author locate the "
            "broken reference_pattern. Error was: {!r}".format(err_msg),
        )
        # The error must name the unresolvable pattern itself.
        self.assertIn(
            "this_path_does_not_exist_xyz_leafcutter_test",
            err_msg,
            "The authoring error must include the unresolvable pattern string so "
            "the author knows what to fix. Error was: {!r}".format(err_msg),
        )


if __name__ == "__main__":
    unittest.main()
