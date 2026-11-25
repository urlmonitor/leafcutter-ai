"""
MODULE: test_bo_700a_4
GOAL: Prove that a changelog entry written by scripts/changelog/emit_entry.py
    reads back, through yaml.safe_load, as exactly the text that was passed in,
    whatever characters that text holds (BO-700a-4).
BUSINESS CONTEXT: _yaml_value double-quoted special strings but escaped only
    '"'. A backslash ("C:\\data") then made the frontmatter unparseable, and a
    line break was folded to a space on read-back. DIAGraph pre-encoded values
    to work around it. These tests pin the read-back contract so no caller has
    to.
ARCHITECTURE: unittest; each test writes a real entry file into a temporary
    directory via emit_entry() and parses its frontmatter with yaml.safe_load.

====================================================================
DECISION HISTORY
====================================================================
- 2026-11-25 [test-writer/BO-700a-4]: Created the red baseline. (#TICKETLESS reason=quick-fix-ac-first)
====================================================================
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EMIT_ENTRY_PATH = _REPO_ROOT / "scripts" / "changelog" / "emit_entry.py"

_spec = importlib.util.spec_from_file_location("emit_entry_bo_700a_4", _EMIT_ENTRY_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load {_EMIT_ENTRY_PATH}"
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _payload(**overrides) -> dict:
    """Return a valid minimal payload with *overrides* applied."""
    payload = {
        "title": "Round trip entry",
        "date": "2026-11-25",
        "time": "10:00",
        "type": "manual",
        "components": ["changelog"],
        "summary": "Plain summary.",
        "description": "Plain description.",
    }
    payload.update(overrides)
    return payload


def _read_back(payload: dict) -> dict:
    """Write *payload* through emit_entry() and return its parsed frontmatter."""
    with tempfile.TemporaryDirectory() as tmp:
        written = _mod.emit_entry(payload, tmp)
        content = written.read_text(encoding="utf-8")
    assert content.startswith("---\n"), content
    block = content[len("---\n"):content.index("\n---\n", len("---\n"))]
    return yaml.safe_load(block)


class TestBO700a4FrontmatterRoundTrip(unittest.TestCase):
    """Every text field reads back exactly as written (BO-700a-4)."""

    def _assert_round_trip(self, **fields) -> None:
        payload = _payload(**fields)
        parsed = _read_back(payload)
        for key, value in fields.items():
            self.assertEqual(parsed[key], value, f"{key} did not round-trip")

    def test_backslash_round_trips(self):
        # covers: BO-700a-4
        # angle: criterion
        self._assert_round_trip(summary=r"Logs moved from C:\data\new to D:\tmp\x")

    def test_double_quote_round_trips(self):
        # covers: BO-700a-4
        # angle: criterion
        self._assert_round_trip(summary='The "deploy" step now quotes \\"its\\" args')

    def test_newline_round_trips(self):
        # covers: BO-700a-4
        # angle: criterion
        self._assert_round_trip(description="- BO-1 (core): first\n- BO-2 (core): second\n")

    def test_colon_round_trips(self):
        # covers: BO-700a-4
        # angle: criterion
        self._assert_round_trip(title="Fix: the writer", summary="key: value, and more: text")

    def test_mixed_round_trips(self):
        # covers: BO-700a-4
        # angle: boundary
        self._assert_round_trip(
            description='Path "C:\\data\\d": done # not a comment\n\tindented\r\nend\u2028sep\\n literal',
        )

    def test_list_items_round_trip(self):
        # covers: BO-700a-4
        # angle: boundary
        self._assert_round_trip(
            components=["changelog", "key: value", r"C:\data", 'say "hi"', "- dash", "# hash"],
        )

    def test_text_that_looks_typed_stays_text(self):
        # covers: BO-700a-4
        # angle: discrimination
        for text in ("true", "No", "null", "~", "123", "1.5", "2026-11-25", " padded ", "", "y"):
            with self.subTest(text=text):
                self._assert_round_trip(summary=text, components=[text])


if __name__ == "__main__":
    unittest.main()
