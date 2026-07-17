"""
MODULE: test_tkt_500f_8_i
GOAL: RED test stubs for TKT-500f-8-i.  Verifies that generate_ticket_from_ac.py
      correctly extracts source file paths named within prose-bullet list-form
      it_requirements into files_touched.

      TKT-500f-8 (already merged) introduced _build_files_touched which unions
      the structured-form it_requirements.reference_file_path with doc_links
      edit-surface paths.  TKT-500f-8-i extends this to the list-form it_requirements
      shape — a list of prose bullet strings.

      test_list_form_bullet_source_extracted (RED before implementation):
        Given a fixture AC whose it_requirements is a list of prose bullets, one
        of which reads "Modify scripts/goal_to_epic.py to ...", assert that
        files_touched contains "scripts/goal_to_epic.py".  Must fail before
        implementation because the current _build_files_touched function tests
        isinstance(it_req, dict) and skips the whole block when it_requirements is
        a list, so the path named in the prose bullet is never extracted.

      test_list_form_no_path_no_phantom (regression guard; GREEN before implementation):
        Given a fixture AC whose list-form it_requirements bullets name no source
        file path, assert no phantom path is invented in files_touched, and the
        doc_links paths ARE still present.  Passes before implementation because
        the current code ignores list-form entirely, returning only the correctly
        extracted doc_links paths.  Included as a regression guard against
        over-extraction bugs in the new list-form parser.

TICKET: TICKET-20260717-TKT-500f-8-i.md
COVERS: TKT-500f-8-i
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_files_touched  # noqa: E402


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestListFormItRequirementsFilesTouched(unittest.TestCase):
    """TKT-500f-8-i: list-form it_requirements prose bullets must be scanned for source paths."""

    def test_list_form_bullet_source_extracted(self):
        # covers: TKT-500f-8-i
        """Given an AC whose it_requirements is a list of prose bullets, one reading
        "Modify scripts/goal_to_epic.py to ...", assert files_touched contains
        "scripts/goal_to_epic.py" (the path named in the bullet's prose text).

        Must be RED before implementation: the current _build_files_touched function
        uses an isinstance(it_req, dict) guard to enter the it_requirements extraction
        block.  A list-form it_requirements is not a dict, so the block is skipped
        entirely and no path from the prose bullets ever reaches files_touched.

        After implementation the function (or a helper it calls) must scan each
        prose bullet for file-path tokens and add any matching paths to the union.
        """
        ac = {
            "title": "List-form extraction test fixture — TKT-500f-8-i",
            "level": "L3",
            "status": "active",
            "work_status": "todo",
            "it_requirements": [
                "Modify scripts/goal_to_epic.py to handle list-form it_requirements extraction",
                "Add a regex that detects file path tokens in prose bullet text",
            ],
            "doc_links": [
                {"path": "docs/reference/ac-schema.md", "relationship": "specifies"},
            ],
            "criteria": (
                "Given an AC whose it_requirements is a list of prose bullets\n"
                "And one bullet names scripts/goal_to_epic.py\n"
                "When a ticket is generated from that AC\n"
                "Then files_touched contains scripts/goal_to_epic.py."
            ),
        }

        actual_files = _build_files_touched(ac)

        self.assertIn(
            "scripts/goal_to_epic.py",
            actual_files,
            "files_touched must contain 'scripts/goal_to_epic.py' because it is "
            "named within a list-form it_requirements prose bullet.  "
            "Currently the function's isinstance(it_req, dict) guard skips the "
            "entire it_requirements block when it_requirements is a list, so the "
            "prose path is never extracted.  Implementation must extend "
            "_build_files_touched (or its helpers) to scan list-form bullets for "
            "file-path tokens and add them to the union.  "
            f"Got files_touched={actual_files!r}."
        )

    def test_list_form_no_path_no_phantom(self):
        # covers: TKT-500f-8-i
        """Given an AC whose it_requirements is a list of prose bullets that name NO
        source file path, assert that no phantom path is invented in files_touched,
        and the doc_links paths ARE still present.

        NOTE: This test may pass before implementation because the current code
        ignores list-form it_requirements entirely (isinstance(it_req, dict) guard
        fails) and returns only the doc_links paths, which already satisfies both
        assertions.  It is included as a regression guard: if the new list-form
        parser incorrectly extracts path-like tokens from ordinary prose (false
        positives such as "system/architecture" or "module structure"), this test
        will catch the over-extraction by verifying that no unexpected path appears
        in files_touched.
        See red_baseline note: 'passes immediately — may be under-specified'.
        """
        doc_link_path = "docs/reference/ac-schema.md"

        ac = {
            "title": "No-phantom test fixture — TKT-500f-8-i",
            "level": "L3",
            "status": "active",
            "work_status": "todo",
            "it_requirements": [
                "Update the system architecture to support list-form prose parsing",
                "Consider the overall module structure when implementing the change",
                "Ensure the helper integrates cleanly with the existing extraction flow",
            ],
            "doc_links": [
                {"path": doc_link_path, "relationship": "specifies"},
            ],
            "criteria": (
                "Given an AC with list-form bullets naming no file path\n"
                "When a ticket is generated from that AC\n"
                "Then no phantom source path is invented in files_touched\n"
                "And files_touched still contains the AC's doc_links paths."
            ),
        }

        actual_files = _build_files_touched(ac)

        # Assertion 1: the doc_links edit-surface path must be present.
        self.assertIn(
            doc_link_path,
            actual_files,
            f"files_touched must contain the doc_links path '{doc_link_path}' "
            "(relationship=specifies is an edit-surface relationship) even when "
            "it_requirements is a list containing no file path.  "
            f"Got files_touched={actual_files!r}."
        )

        # Assertion 2: no path outside the declared doc_links should appear.
        allowed_paths: set[str] = {doc_link_path}
        phantom_paths = [p for p in actual_files if p not in allowed_paths]
        self.assertEqual(
            phantom_paths,
            [],
            "No phantom source path may be invented when the list-form "
            "it_requirements bullets name no file path.  "
            f"Unexpected paths in files_touched: {phantom_paths}.  "
            f"Full files_touched={actual_files!r}."
        )


if __name__ == "__main__":
    unittest.main()
