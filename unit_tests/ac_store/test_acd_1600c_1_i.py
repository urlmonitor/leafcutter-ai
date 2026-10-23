"""
MODULE: test_acd_1600c_1_i
GOAL: Red-first real-AC edge case for the implementation-readiness gate
    (ACD-1600c-1-i): two real records with no file targets, ACD-300c-1 and TQ-200a-1,
    are flagged 'missing file targets' and held back from dispatch.
BUSINESS CONTEXT: ACD-300c-3 and TQ-200a-1 are the empirically observed ACs where the
    coder had no file targets and had to guess. The verdict must be data-driven on the
    declared-files seam, never keyed on these ids or on what their it_requirements/doc_links
    say. ACD-300c-3 gained declared_files in EPIC-RightJobRightAgentFollowUps, so the
    fixture's precondition failed loudly as the AC intends, and the fixture was re-pointed
    to its sibling ACD-300c-1 (same /plan-feature gate family, still no declared_files).
    The criterion test's name follows the AC's test_spec, which now pins acd300c1.
ARCHITECTURE: The two real YAMLs are loaded, normalised (only readiness -> approved
    and depends_on -> [] so the scan's own filters admit them), re-serialised with
    yaml.safe_dump into a temp store, and the REAL scripts/ac_store/scan_ac_store.py
    CLI is run on it. Both records read as schema_version < 2, so held-back
    assertions run with --enforce-impl-readiness (ACD-1600c-1 migration
    requirement); the gate contract is pinned in test_acd_1600c_1.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCAN = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"
_STORE = _REPO_ROOT / "docs" / "acceptance-criteria"
_IDS = ("ACD-300c-1", "TQ-200a-1")  # ACD-300c-3 now declares files (see module docstring)


def _real_record(ac_id: str) -> dict:
    hits = list(_STORE.rglob(f"{ac_id}.yaml"))
    assert len(hits) == 1, hits
    rec = yaml.safe_load(hits[0].read_text(encoding="utf-8"))
    # precondition asserted, not assumed: a later declaration fails the fixture loudly
    assert "declared_files" not in rec, f"{ac_id} now declares files; fixture is stale"
    rec["readiness"] = "approved"  # admit through the scan's approved-only filter
    rec["depends_on"] = []  # parents are not in the temp store
    return rec


def _scan_copy(*flags: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        for ac_id in _IDS:
            (Path(tmp) / f"{ac_id}.yaml").write_text(yaml.safe_dump(_real_record(ac_id)), encoding="utf-8")
        # control: a record that declares files + contract is dispatchable
        ctrl = {"id": "CTRL-100a-1", "level": "L2", "status": "active", "readiness": "approved",
                "work_status": "todo", "title": "control", "priority": "medium",
                "estimated_complexity": "S", "depends_on": [],
                "declared_files": [{"path": "scripts/foo.py", "state": "existing"}],
                "test_spec": [{"name": "test_x", "target_dir": "unit_tests/x/",
                               "framework": "unittest", "type": "unit"}]}
        (Path(tmp) / "CTRL-100a-1.yaml").write_text(yaml.safe_dump(ctrl), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(_SCAN), "--json", "--ac-root", tmp, *flags],
                              capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestRealAcsMissingFileTargets(unittest.TestCase):
    def test_acd300c1_and_tq200a1_flagged_missing_file_targets(self):
        """Each real AC is flagged with the reason 'missing file targets'."""
        # covers: ACD-1600c-1-i
        # angle: criterion
        out = _scan_copy("--enforce-impl-readiness")
        flagged = {r["ac_id"]: r for r in out["not_implementation_ready"]}
        self.assertEqual(set(flagged), set(_IDS))  # control absent: exact set
        for ac_id in _IDS:
            self.assertIn("missing file targets", flagged[ac_id]["reasons"])
            self.assertTrue(flagged[ac_id]["held_back"])

    def test_missing_file_target_acs_not_in_dispatch_set(self):
        """Neither flagged AC is in `ready`; the control (declared files) still is."""
        # covers: ACD-1600c-1-i
        # angle: failure
        out = _scan_copy("--enforce-impl-readiness")
        self.assertEqual([r["ac_id"] for r in out["ready"]], ["CTRL-100a-1"])
        # advisory default: v1 records are reported but remain dispatchable
        adv = _scan_copy()
        self.assertEqual(sorted(r["ac_id"] for r in adv["ready"]), sorted((*_IDS, "CTRL-100a-1")))
        self.assertEqual({r["ac_id"] for r in adv["not_implementation_ready"]}, set(_IDS))


if __name__ == "__main__":
    unittest.main()
