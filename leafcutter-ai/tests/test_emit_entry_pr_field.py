"""
MODULE: test_emit_entry_pr_field
GOAL: Unit tests for the optional `pr` field in emit_entry.py.
BUSINESS CONTEXT: The pr field provides PR traceability in changelog entries.
    It was introduced in emit_entry.py's optional_order alongside summary/adrs/
    diagrams. These tests are the acceptance gate for that field, split from
    test_emit_entry.py to satisfy the 400-line file-size budget.
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile.TemporaryDirectory
    for filesystem isolation. No database, no network, no project-tree writes.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
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

class TestEmitEntryPrField(unittest.TestCase):
    """pr is an optional scalar string field for PR traceability."""

    def test_pr_serialized_as_scalar(self):
        """pr appears in the frontmatter as a single scalar value, not a list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(pr="https://github.com/org/repo/pull/123")
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("pr:", content)
            self.assertIn("https://github.com/org/repo/pull/123", content)
            # Must not be rendered as a YAML list (no '  - ' prefix line).
            self.assertNotIn("  - https://github.com/org/repo/pull/123", content)

    def test_pr_omitted_when_absent(self):
        """Payload without pr does not emit a pr field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload()
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertNotIn("pr:", content)

    def test_pr_alongside_adrs_and_diagrams(self):
        """pr, adrs, and diagrams can coexist in the same frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = _base_payload(
                pr="https://github.com/org/repo/pull/85",
                adrs=["ADR-019"],
                diagrams=["docs/architecture/pipeline.md"],
            )
            written = emit_entry(payload, tmpdir)
            content = written.read_text(encoding="utf-8")
            self.assertIn("pr:", content)
            self.assertIn("https://github.com/org/repo/pull/85", content)
            self.assertIn("adrs:", content)
            self.assertIn("  - ADR-019", content)
            self.assertIn("diagrams:", content)
            self.assertIn("  - docs/architecture/pipeline.md", content)


if __name__ == "__main__":
    unittest.main()
