"""
MODULE: test_emit_entry
GOAL: Unit tests for leafcutter/scripts/changelog/emit_entry.py.
BUSINESS CONTEXT: Verifies that the changelog entry write helper correctly
    enforces required fields, validates the type enum, generates canonical
    filenames, handles collision avoidance, and writes well-formed YAML
    frontmatter. These tests are the acceptance gate for the refactored
    changelog write path described in ADR-019.
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile.TemporaryDirectory
    for filesystem isolation. No database, no network, no project-tree writes.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: resolve emit_entry module without relying on installed package
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EMIT_ENTRY_PATH = _REPO_ROOT / "scripts" / "changelog" / "emit_entry.py"

spec = importlib.util.spec_from_file_location("emit_entry", _EMIT_ENTRY_PATH)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)

emit_entry = _mod.emit_entry
validate_payload = _mod.validate_payload
slugify = _mod.slugify
generate_filename = _mod.generate_filename


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _base_payload(**overrides) -> dict:
    """Return a valid minimal payload with optional field overrides."""
    payload = {
        "title": "Test Entry Title",
        "date": "2026-05-13",
        "time": "10:00",
        "type": "manual",
        "components": ["infrastructure"],
        "summary": "A test change for changelog verification.",
        "description": "A test changelog entry.",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmitEntryHappyPath(unittest.TestCase):
    """Scenario 1: emit_entry creates a file with correct filename and frontmatter."""

    def test_emit_entry_happy_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            written = emit_entry(payload, tmpdir)

            # File was created
            self.assertTrue(written.exists(), f"Expected file at {written} to exist")

            # Filename matches YYYY-MM-DD-HHMM-slug.md pattern
            self.assertEqual(written.name, "2026-05-13-1000-test-entry-title.md")

            # File content contains YAML frontmatter
            content = written.read_text(encoding="utf-8")
            self.assertIn("---", content)
            self.assertIn("title:", content)
            self.assertIn("date:", content)
            self.assertIn("time:", content)
            self.assertIn("type:", content)
            self.assertIn("components:", content)
            self.assertIn("description:", content)

            # Ends with body section
            self.assertIn("## Entry", content)

            # CHANGELOG.md is not touched (not in tmpdir)
            changelog_path = Path(tmpdir) / "CHANGELOG.md"
            self.assertFalse(
                changelog_path.exists(),
                "emit_entry must not create or modify CHANGELOG.md"
            )


class TestEmitEntryMissingRequiredField(unittest.TestCase):
    """Scenario 4: missing required field raises ValueError before any write."""

    def test_emit_entry_missing_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            del payload["title"]
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("title", str(ctx.exception))

    def test_emit_entry_missing_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            del payload["date"]
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("date", str(ctx.exception))

    def test_emit_entry_missing_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            del payload["description"]
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("description", str(ctx.exception))

    def test_emit_entry_no_file_written_on_validation_failure(self):
        """ValueError must be raised before any file is written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            del payload["type"]
            with self.assertRaises(ValueError):
                emit_entry(payload, tmpdir)
            # No files should exist in tmpdir
            written_files = list(Path(tmpdir).iterdir())
            self.assertEqual(
                written_files, [],
                "No files should be written when validation fails"
            )


class TestEmitEntrySlugFilename(unittest.TestCase):
    """Scenario 7: filename slug is canonical (lowercase-hyphenated)."""

    def test_emit_entry_slug_filename(self):
        """Title 'My Epic: Deploy v2 (hotfix)' → slug 'my-epic-deploy-v2-hotfix'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(title="My Epic: Deploy v2 (hotfix)")
            written = emit_entry(payload, tmpdir)
            self.assertEqual(written.name, "2026-05-13-1000-my-epic-deploy-v2-hotfix.md")

    def test_slugify_lowercases(self):
        self.assertEqual(slugify("UPPER CASE"), "upper-case")

    def test_slugify_collapses_consecutive_hyphens(self):
        self.assertEqual(slugify("a  --  b"), "a-b")

    def test_slugify_strips_leading_trailing_hyphens(self):
        self.assertEqual(slugify("--leading-trailing--"), "leading-trailing")

    def test_slugify_replaces_non_alphanumeric(self):
        self.assertEqual(slugify("hello: world! (test)"), "hello-world-test")

    def test_filename_includes_date_and_time(self):
        """Date and time from payload drive the filename prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(date="2026-01-15", time="09:30", title="fix")
            written = emit_entry(payload, tmpdir)
            self.assertTrue(
                written.name.startswith("2026-01-15-0930-"),
                f"Expected filename starting with '2026-01-15-0930-', got '{written.name}'"
            )


class TestEmitEntryEpicCompletionType(unittest.TestCase):
    """Scenario 3/5: type=epic_completion requires epic field."""

    def test_epic_completion_with_epic_field(self):
        """Valid epic_completion entry carries epic field in frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(
                type="epic_completion",
                epic="EPIC-MyFeature",
                title="EPIC-MyFeature complete",
            )
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("type:", content)
            self.assertIn("epic_completion", content)
            self.assertIn("epic:", content)
            self.assertIn("EPIC-MyFeature", content)

    def test_epic_completion_missing_epic_raises(self):
        """Missing epic field with type=epic_completion raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(type="epic_completion")
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("epic", str(ctx.exception).lower())

    def test_manual_type_does_not_require_epic(self):
        """type=manual does not require an epic field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(type="manual")
            # Should not raise
            written = emit_entry(payload, tmpdir)
            self.assertTrue(written.exists())


class TestEmitEntryTicketCompletionType(unittest.TestCase):
    """ticket_completion (build-single-ticket Call site 3) mirrors epic_completion."""

    def test_ticket_completion_with_ticket_field(self):
        """Valid ticket_completion entry carries the ticket field in frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(
                type="ticket_completion",
                ticket="TICKET-20260514-Example_Single_Ticket",
                title="TICKET-20260514-Example_Single_Ticket complete",
            )
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("type:", content)
            self.assertIn("ticket_completion", content)
            self.assertIn("ticket:", content)
            self.assertIn("TICKET-20260514-Example_Single_Ticket", content)

    def test_ticket_completion_missing_ticket_raises(self):
        """Missing ticket field with type=ticket_completion raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(type="ticket_completion")
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("ticket", str(ctx.exception).lower())

    def test_epic_completion_does_not_require_ticket_field(self):
        """type=epic_completion still only requires its own epic field, not ticket."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(type="epic_completion", epic="EPIC-Test")
            # Should not raise — ticket requirement is type-specific, not global.
            written = emit_entry(payload, tmpdir)
            self.assertTrue(written.exists())


class TestEmitEntryUnknownType(unittest.TestCase):
    """Scenario 6: unknown type value raises ValueError."""

    def test_unknown_type_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(type="unknown_value")
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("unknown_value", str(ctx.exception))

    def test_all_valid_types_accepted(self):
        """Each valid type value should not raise."""
        valid_types = [
            "epic_completion",
            "ticket_completion",
            "deploy_tag",
            "manual",
            "rollback",
        ]
        for entry_type in valid_types:
            with tempfile.TemporaryDirectory() as tmpdir:
                payload = _base_payload(type=entry_type)
                if entry_type == "epic_completion":
                    payload["epic"] = "EPIC-Test"
                    payload["title"] = "EPIC-Test complete"
                elif entry_type == "ticket_completion":
                    payload["ticket"] = "TICKET-Test"
                    payload["title"] = "TICKET-Test complete"
                # Should not raise
                written = emit_entry(payload, tmpdir)
                self.assertTrue(written.exists(), f"File not written for type={entry_type}")


class TestEmitEntryCollisionAvoidance(unittest.TestCase):
    """Scenario: second entry at same timestamp gets -2 suffix."""

    def test_emit_entry_collision_avoidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            first = emit_entry(payload, tmpdir)
            second = emit_entry(payload, tmpdir)

            self.assertNotEqual(first, second, "Collision should produce a different path")
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

            # First file has no suffix; second has -2
            self.assertEqual(first.name, "2026-05-13-1000-test-entry-title.md")
            self.assertEqual(second.name, "2026-05-13-1000-test-entry-title-2.md")

    def test_emit_entry_triple_collision(self):
        """Third entry at same timestamp gets -3 suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            first = emit_entry(payload, tmpdir)
            second = emit_entry(payload, tmpdir)
            third = emit_entry(payload, tmpdir)

            self.assertEqual(first.name, "2026-05-13-1000-test-entry-title.md")
            self.assertEqual(second.name, "2026-05-13-1000-test-entry-title-2.md")
            self.assertEqual(third.name, "2026-05-13-1000-test-entry-title-3.md")


class TestEmitEntryChangelogFolderCreation(unittest.TestCase):
    """Scenario 8: changelog_folder is created if it does not exist."""

    def test_emit_entry_creates_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_subdir = Path(tmpdir) / "changelogs" / "nested"
            self.assertFalse(new_subdir.exists())
            payload = _base_payload()
            written = emit_entry(payload, new_subdir)
            self.assertTrue(new_subdir.exists(), "emit_entry should create the output dir")
            self.assertTrue(written.exists())


class TestEmitEntrySummaryField(unittest.TestCase):
    """Scenario 1: summary is a required field."""

    def test_summary_required(self):
        """Missing summary field raises ValueError naming 'summary'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            del payload["summary"]
            with self.assertRaises(ValueError) as ctx:
                emit_entry(payload, tmpdir)
            self.assertIn("summary", str(ctx.exception))

    def test_summary_written_to_frontmatter(self):
        """summary field appears in the written frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(summary="Improved strategy pipeline speed by 30%.")
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("summary:", content)
            self.assertIn("Improved strategy pipeline speed", content)


class TestEmitEntryOptionalArrays(unittest.TestCase):
    """Scenario 2: adrs and diagrams serialize as YAML lists in frontmatter."""

    def test_adrs_serialized_as_yaml_list(self):
        """adrs list appears in frontmatter with YAML list syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(adrs=["ADR-019"])
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("adrs:", content)
            self.assertIn("  - ADR-019", content)

    def test_diagrams_serialized_as_yaml_list(self):
        """diagrams list appears in frontmatter with YAML list syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(diagrams=["docs/architecture/pipeline.md"])
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("diagrams:", content)
            self.assertIn("  - docs/architecture/pipeline.md", content)

    def test_adrs_and_diagrams_both_present(self):
        """Both adrs and diagrams can be present together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(
                adrs=["ADR-019", "ADR-020"],
                diagrams=["docs/architecture/pipeline.md"],
            )
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("adrs:", content)
            self.assertIn("  - ADR-019", content)
            self.assertIn("  - ADR-020", content)
            self.assertIn("diagrams:", content)
            self.assertIn("  - docs/architecture/pipeline.md", content)

    def test_adrs_and_diagrams_optional(self):
        """Payload without adrs or diagrams still writes successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertNotIn("adrs:", content)
            self.assertNotIn("diagrams:", content)
            self.assertNotIn("pr:", content)


if __name__ == "__main__":
    unittest.main()
