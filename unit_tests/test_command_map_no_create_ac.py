"""
Tests that the c1-001-command-map architecture diagram no longer references
the old /create-ac command that was renamed to /plan-feature.

AC reference: ACD-1402
Symptom: The diagram at docs/architecture/diagrams/c1-001-command-map.md
still contains "/create-ac" at lines 65, 154, 159, and 216 after the
command was renamed to "/plan-feature".
Root cause: The diagram was not updated when the skill/command was renamed.

These tests MUST FAIL (red) until every "/create-ac" occurrence in the
diagram is replaced with "/plan-feature" (and the surrounding prose is
updated accordingly).
"""

import os
import unittest

# Resolve the diagram path relative to this test file so the test works
# regardless of which directory the test runner is invoked from.
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_COMMAND_MAP_MD = os.path.join(
    _REPO_ROOT,
    "docs",
    "architecture",
    "diagrams",
    "c1-001-command-map.md",
)


class TestCommandMapNamingAfterRename(unittest.TestCase):
    """c1-001-command-map.md must not reference the obsolete /create-ac command."""

    @classmethod
    def setUpClass(cls):
        with open(_COMMAND_MAP_MD, "r", encoding="utf-8") as fh:
            cls.content = fh.read()

    def test_no_create_ac_command_in_diagram(self):
        # covers: ACD-1402
        """The string '/create-ac' must not appear anywhere in c1-001-command-map.md.

        The command was renamed from /create-ac to /plan-feature. Any remaining
        occurrence of '/create-ac' in the diagram indicates the file was not
        updated after the rename. All references (mermaid node labels,
        command-description tables, cross-stage handoff table) must use
        '/plan-feature' instead.

        To make this test green: replace every '/create-ac' occurrence in
        docs/architecture/diagrams/c1-001-command-map.md with '/plan-feature'
        and update surrounding prose as appropriate.
        """
        occurrences = [
            lineno + 1
            for lineno, line in enumerate(self.content.splitlines())
            if "/create-ac" in line
        ]
        self.assertEqual(
            occurrences,
            [],
            f"'/create-ac' still appears in c1-001-command-map.md at line(s): "
            f"{occurrences}. The command was renamed to '/plan-feature'; update "
            f"every occurrence in the mermaid diagram, command-description table, "
            f"and cross-stage handoff table.",
        )

    def test_plan_feature_command_present_in_diagram(self):
        # covers: ACD-1402
        """The string '/plan-feature' must appear at least once in c1-001-command-map.md.

        After the rename, the diagram must include '/plan-feature' as the
        replacement for the removed '/create-ac' command. This positive check
        guards against a fix that merely deletes the old name without adding
        the new one.

        To make this test green: ensure '/plan-feature' appears in the
        requirements section of the mermaid diagram and in the command
        description and cross-stage handoff tables.
        """
        self.assertIn(
            "/plan-feature",
            self.content,
            "'/plan-feature' does not appear anywhere in c1-001-command-map.md. "
            "The renamed command must be present in the diagram to replace "
            "the removed '/create-ac' references.",
        )


if __name__ == "__main__":
    unittest.main()
