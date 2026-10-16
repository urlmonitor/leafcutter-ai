"""
MODULE: test_acd_1700b_1_map_errors
GOAL: Red-first spec: assignment_quality.py never passes silently on a bad map.
BUSINESS CONTEXT: ACD-1700b-1 -- module promises "never a silent pass" and the CLI
    "always exits 0" (advisory, ADR-026).
ARCHITECTURE: OUTPUT CONTRACT python-coder must satisfy (real CLI, --map <temp file>):
    * Map problem => stdout JSON (single-surface verdict OR split payload) carries a
      top-level string field `map_error` naming the problem (missing/unreadable file,
      invalid YAML, no `entries` list, empty list, or an entry missing `glob`/`craft`).
      For a bad entry the message names the entry (index like "entries[1]" or "#1")
      AND the missing key ("glob" / "craft").
    * Single-surface: `verdict` == "map_error" (never "unresolved") and `held` False.
      Split payload: `split_required` False and `held` False.
    * Exit code stays 0, no traceback on stderr.
    * With a valid map the `map_error` key is ABSENT (existing output unchanged).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI = _REPO_ROOT / "scripts" / "ac_store" / "assignment_quality.py"


def _run(map_text, surfaces=("scripts/x.py",)):
    with tempfile.TemporaryDirectory() as tmp:
        mp = Path(tmp) / "map.yaml"
        if map_text is not None:
            mp.write_text(map_text, encoding="utf-8")
        cmd = [sys.executable, str(_CLI), "--ac-id", "T-1", "--assigned-agent", "python-coder", "--map", str(mp)]
        for s in surfaces:
            cmd += ["--surface", s]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT))
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = {}
    return proc, payload


class TestMapErrorsAreExplicit(unittest.TestCase):
    def _assert_map_error(self, proc, payload, *needles):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIsInstance(payload.get("map_error"), str, payload)
        for n in needles:
            self.assertIn(n, payload["map_error"])
        self.assertEqual(payload.get("verdict"), "map_error")
        self.assertIs(payload.get("held"), False)

    def test_no_entries_key_is_map_error_not_unresolved(self):
        """Map with no `entries` list => map_error (not 'unresolved')."""
        # covers: ACD-1700b-1
        # angle: failure
        proc, payload = _run(yaml.safe_dump({"other": 1}))
        self._assert_map_error(proc, payload, "entries")

    def test_empty_entries_is_map_error(self):
        """Empty entries list => map_error."""
        # covers: ACD-1700b-1
        # angle: boundary
        proc, payload = _run(yaml.safe_dump({"entries": []}))
        self._assert_map_error(proc, payload, "entries")

    def test_missing_map_file_is_map_error_exit_zero(self):
        """Missing map file => map_error naming the file, exit 0, no traceback."""
        # covers: ACD-1700b-1
        # angle: failure
        proc, payload = _run(None)
        self._assert_map_error(proc, payload, "map.yaml")

    def test_invalid_yaml_is_map_error_exit_zero(self):
        """Unparseable YAML => map_error, exit 0."""
        # covers: ACD-1700b-1
        # angle: failure
        proc, payload = _run("entries: [unclosed\n  - {glob")
        self._assert_map_error(proc, payload)

    def test_entry_missing_glob_or_craft_names_entry(self):
        """Entry lacking glob/craft => map_error naming entry index and key (no KeyError traceback)."""
        # covers: ACD-1700b-1
        # angle: failure
        good = {"glob": "unit_tests/**", "craft": "python-coder"}
        proc, payload = _run(yaml.safe_dump({"entries": [good, {"craft": "python-coder"}]}))
        self._assert_map_error(proc, payload, "glob")
        self.assertRegex(payload["map_error"], r"entries\[1\]|#1")
        proc, payload = _run(yaml.safe_dump({"entries": [{"glob": "scripts/**"}, good]}))
        self._assert_map_error(proc, payload, "craft")
        self.assertRegex(payload["map_error"], r"entries\[0\]|#0")

    def test_split_payload_also_reports_map_error(self):
        """Multi-surface (split) path reports map_error, split_required False, held False."""
        # covers: ACD-1700b-1
        # angle: failure
        proc, payload = _run(yaml.safe_dump({"entries": []}), surfaces=("a.py", "b.css"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsInstance(payload.get("map_error"), str, payload)
        self.assertIs(payload.get("split_required"), False)
        self.assertIs(payload.get("held"), False)

    def test_valid_map_has_no_map_error_key(self):
        """Control: valid map => no `map_error` key and normal verdict (catches an always-error impl)."""
        # covers: ACD-1700b-1
        # angle: discrimination
        proc, payload = _run(yaml.safe_dump({"entries": [{"glob": "scripts/**", "craft": "python-coder"}]}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("map_error", payload)
        self.assertEqual(payload.get("verdict"), "match")
