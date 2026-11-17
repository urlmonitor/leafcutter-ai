"""
MODULE: test_acd_1600c_1_text_output
GOAL: Red-first spec for the HUMAN-TEXT (no --json) rendering of the
    implementation-readiness report from scripts/ac_store/scan_ac_store.py.
BUSINESS CONTEXT: ACD-1600c-1 -- "the flag names which of the two is missing".
    _print_human ignores the not_implementation_ready list, so a held AC silently
    vanishes from text output and advisory reasons are never shown.
ARCHITECTURE: OUTPUT CONTRACT python-coder must satisfy (text mode, real CLI):
    * A section whose header line contains "NOT IMPLEMENTATION-READY" (case-insens.)
      is printed whenever the flagged list is non-empty; each flagged AC gets a line
      containing its ac_id, every reason verbatim, and the word "held" when
      held_back is True or "reported" (and NOT "held") when advisory/legacy.
    * Ready ACs keep their existing READY/BLOCKED lines; held ACs stay out of READY.
    * No flagged ACs => no such section (text output unchanged).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCAN = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"
_TEST_SPEC = [{"name": "test_x", "target_dir": "unit_tests/x/", "framework": "unittest", "type": "unit"}]
_FILES = [{"path": "scripts/foo.py", "state": "existing"}]


def _ac(ac_id: str, **extra) -> dict:
    rec = {"id": ac_id, "level": "L2", "status": "active", "readiness": "approved",
           "work_status": "todo", "title": ac_id, "priority": "medium",
           "estimated_complexity": "S", "depends_on": []}
    rec.update(extra)
    return rec


def _scan_text(records: list[dict], *flags: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        for rec in records:
            (Path(tmp) / f"{rec['id']}.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(_SCAN), "--ac-root", tmp, *flags],
            capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT),
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _section(out: str) -> str:
    lines = out.splitlines()
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "not implementation-ready" in low or "not-implementation-ready" in low:
            return "\n".join(lines[i:])
    return ""


class TestTextOutputShowsReadinessFlags(unittest.TestCase):
    def test_text_advisory_flag_reported_not_held(self):
        """Legacy AC missing file targets appears in the section: named reason, 'reported', not 'held'."""
        # covers: ACD-1600c-1
        # angle: criterion
        out = _scan_text([_ac("T-700a-1", test_spec=_TEST_SPEC),
                          _ac("T-700a-2", declared_files=_FILES, test_spec=_TEST_SPEC)])
        sec = _section(out)
        self.assertNotEqual(sec, "", out)
        line = next((ln for ln in sec.splitlines() if "T-700a-1" in ln), "")
        self.assertIn("missing file targets", line)
        self.assertIn("reported", line.lower())
        self.assertNotIn("held", line.lower())
        self.assertNotIn("T-700a-2", sec)  # control: complete AC not flagged

    def test_text_enforced_flag_named_held_with_both_reasons(self):
        """With --enforce-impl-readiness the held AC is named held with every reason; absent from READY."""
        # covers: ACD-1600c-1
        # angle: criterion
        out = _scan_text([_ac("T-700b-1"), _ac("T-700b-2", declared_files=_FILES, test_spec=_TEST_SPEC)],
                         "--enforce-impl-readiness")
        line = next((ln for ln in _section(out).splitlines() if "T-700b-1" in ln), "")
        self.assertIn("missing file targets", line)
        self.assertIn("missing test contract", line)
        self.assertIn("held", line.lower())
        ready = out.split("BLOCKED")[0]
        self.assertNotIn("T-700b-1", ready)
        self.assertIn("T-700b-2", ready)

    def test_text_no_flag_no_section(self):
        """Control: all-ready store prints no readiness section; READY line unchanged."""
        # covers: ACD-1600c-1
        # angle: boundary
        out = _scan_text([_ac("T-700c-1", declared_files=_FILES, test_spec=_TEST_SPEC)])
        self.assertEqual(_section(out), "")
        self.assertIn("READY (1):", out)
