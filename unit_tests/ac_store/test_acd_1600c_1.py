"""
MODULE: test_acd_1600c_1
GOAL: Red-first specification of the implementation-readiness completeness gate
    in scripts/ac_store/scan_ac_store.py (ACD-1600c-1).
BUSINESS CONTEXT: An AC with no declared files or no test contract must be flagged
    NOT implementation-ready and held back for enrichment, using reasons drawn from
    the store's single hold-reason list. ADR-026 rules 3-4: advisory first, and
    schema_version < 2 records are reported but never held.
ARCHITECTURE: INTERFACE CONTRACT python-coder must satisfy (importable from
    scan_ac_store; the logic may live in a helper module and be re-exported):

      HOLD_REASONS                          tuple[str, ...] -- the single list; holds
                                            at least the two owned values
      HOLD_REASON_MISSING_FILE_TARGETS      == "missing file targets"
      HOLD_REASON_MISSING_TEST_CONTRACT     == "missing test contract"
      implementation_readiness_reasons(ac)  -> list[str]; ordered: file targets, then
                                            test contract, then the record's own
                                            `hold_reason` value (when set), unchanged.
                                            File targets read ONLY through
                                            declared_files.get_declared_files.
                                            Test contract present iff `test_spec` is a
                                            non-empty list OR `test_required` is False.
      is_held_back(ac, *, enforce=False)    -> bool; True iff reasons non-empty AND
                                            (enforce OR int(schema_version, default 1) >= 2)
      CLI --json output gains key `not_implementation_ready`: list of
          {"ac_id", "reasons", "held_back"}; held-back ACs are absent from `ready`.
      CLI flag --enforce-impl-readiness turns enforce on (default off = advisory).
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
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
_SCAN = _SCRIPTS_DIR / "scan_ac_store.py"
sys.path.insert(0, str(_SCRIPTS_DIR))

import scan_ac_store as gate  # noqa: E402

_TEST_SPEC = [{"name": "test_x", "target_dir": "unit_tests/x/", "framework": "unittest", "type": "unit"}]
_FILES = [{"path": "scripts/foo.py", "state": "existing"}]
_NONOWNED = ("test design pending", "reference file pending", "file finding undecided")


def _ac(ac_id: str, **extra) -> dict:
    rec = {
        "id": ac_id, "level": "L2", "status": "active", "readiness": "approved",
        "work_status": "todo", "title": ac_id, "priority": "medium",
        "estimated_complexity": "S", "depends_on": [],
    }
    rec.update(extra)
    return rec


def _complete(ac_id: str, **extra) -> dict:
    return _ac(ac_id, declared_files=_FILES, test_spec=_TEST_SPEC, **extra)


def _scan(records: list[dict], *flags: str) -> dict:
    """Write records with the real serializer and run the real CLI."""
    with tempfile.TemporaryDirectory() as tmp:
        for rec in records:
            (Path(tmp) / f"{rec['id']}.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(_SCAN), "--json", "--ac-root", tmp, *flags],
            capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT),
        )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestImplementationReadinessGate(unittest.TestCase):
    def test_ac_missing_file_targets_flagged_not_ready(self):
        """No declared files => 'missing file targets', even if prose names paths."""
        # covers: ACD-1600c-1
        # angle: criterion
        ac = _ac(
            "T-100a-1", test_spec=_TEST_SPEC,
            it_requirements=["Change scripts/foo.py"],
            doc_links=[{"path": "scripts/foo.py", "relationship": "modifies", "status": "exists"}],
            reference_file_path="scripts/foo.py",
        )
        self.assertEqual(gate.implementation_readiness_reasons(ac), ["missing file targets"])

    def test_ac_missing_test_contract_flagged_not_ready(self):
        """Neither test_spec nor test_required: false => 'missing test contract'."""
        # covers: ACD-1600c-1
        # angle: criterion
        ac = _ac("T-100a-2", declared_files=_FILES)
        self.assertEqual(gate.implementation_readiness_reasons(ac), ["missing test contract"])
        # controls: explicit test_required: false, and a full contract, are not flagged
        self.assertEqual(
            gate.implementation_readiness_reasons(_ac("T-100a-3", declared_files=_FILES, test_required=False)), [])
        self.assertEqual(gate.implementation_readiness_reasons(_complete("T-100a-4")), [])
        # test_required: true alone is NOT a contract
        self.assertEqual(
            gate.implementation_readiness_reasons(_ac("T-100a-7", declared_files=_FILES, test_required=True)),
            ["missing test contract"])

    def test_flag_names_which_of_two_is_missing(self):
        """Names exactly the missing one(s); both when both absent."""
        # covers: ACD-1600c-1
        # angle: criterion
        self.assertEqual(
            gate.implementation_readiness_reasons(_ac("T-100a-5")),
            ["missing file targets", "missing test contract"])
        self.assertEqual(
            gate.implementation_readiness_reasons(_ac("T-100a-6", test_spec=_TEST_SPEC)),
            ["missing file targets"])
        self.assertEqual(
            gate.implementation_readiness_reasons(_ac("T-100a-8", declared_files=_FILES)),
            ["missing test contract"])

    def test_flagged_ac_held_back_from_dispatch_set(self):
        """In enforce mode a flagged AC leaves `ready` and is reported held (CLI)."""
        # covers: ACD-1600c-1
        # angle: criterion
        out = _scan([_complete("T-200a-1"), _ac("T-200a-2")], "--enforce-impl-readiness")
        self.assertEqual([r["ac_id"] for r in out["ready"]], ["T-200a-1"])
        flagged = {r["ac_id"]: r for r in out["not_implementation_ready"]}
        self.assertEqual(set(flagged), {"T-200a-2"})
        self.assertTrue(flagged["T-200a-2"]["held_back"])
        self.assertEqual(flagged["T-200a-2"]["reasons"], ["missing file targets", "missing test contract"])
        # schema_version >= 2 is held even without the enforce flag
        out2 = _scan([_ac("T-200a-3", schema_version=2), _complete("T-200a-4")])
        self.assertEqual([r["ac_id"] for r in out2["ready"]], ["T-200a-4"])

    def test_flag_reasons_drawn_from_single_hold_reason_list(self):
        """Emitted reasons are HOLD_REASONS values; non-owned reasons pass through unchanged."""
        # covers: ACD-1600c-1
        # angle: discrimination
        # Wrong version caught: a gate that folds every hold into one of its two owned reasons.
        for reason in (gate.HOLD_REASON_MISSING_FILE_TARGETS, gate.HOLD_REASON_MISSING_TEST_CONTRACT):
            self.assertIn(reason, gate.HOLD_REASONS)
        self.assertEqual(len(set(gate.HOLD_REASONS)), len(gate.HOLD_REASONS))
        for other in _NONOWNED:
            ac = _complete("T-300a-1", hold_reason=other)
            self.assertEqual(gate.implementation_readiness_reasons(ac), [other])
            both = _ac("T-300a-2", hold_reason=other)
            self.assertEqual(
                gate.implementation_readiness_reasons(both),
                ["missing file targets", "missing test contract", other])
        for r in gate.implementation_readiness_reasons(_ac("T-300a-3")):
            self.assertIn(r, gate.HOLD_REASONS)

    def test_declared_list_never_flagged_missing_file_targets(self):
        """>=1 declared file is never 'missing file targets', whatever prose says."""
        # covers: ACD-1600c-1
        # angle: boundary
        one = {"path": "a.py", "state": "to_be_created"}
        for extra in ({}, {"it_requirements": []}, {"it_requirements": ["no file paths here"]},
                      {"doc_links": []}):
            ac = _ac("T-400a-1", declared_files=[one], test_spec=_TEST_SPEC, **extra)
            self.assertNotIn("missing file targets", gate.implementation_readiness_reasons(ac))
        # control: absent field is flagged exactly once
        reasons = gate.implementation_readiness_reasons(_ac("T-400a-2", test_spec=_TEST_SPEC))
        self.assertEqual(reasons.count("missing file targets"), 1)

    def test_legacy_record_reported_not_held_in_advisory_mode(self):
        """ADR-026 rules 3-4: no schema_version + no declared_files => reported, still dispatchable."""
        # covers: ACD-1600c-1
        # angle: boundary
        legacy = _ac("T-500a-1", test_spec=_TEST_SPEC)
        self.assertFalse(gate.is_held_back(legacy, enforce=False))
        self.assertTrue(gate.is_held_back(legacy, enforce=True))
        self.assertTrue(gate.is_held_back(_ac("T-500a-2", test_spec=_TEST_SPEC, schema_version=2), enforce=False))
        self.assertFalse(gate.is_held_back(_complete("T-500a-3", schema_version=2), enforce=True))
        out = _scan([legacy, _complete("T-500a-4")])
        self.assertEqual(sorted(r["ac_id"] for r in out["ready"]), ["T-500a-1", "T-500a-4"])
        self.assertEqual(
            [(r["ac_id"], r["reasons"], r["held_back"]) for r in out["not_implementation_ready"]],
            [("T-500a-1", ["missing file targets"], False)])

    def test_acd_1600c_1_reachable_from_entry_point(self):
        """Reachability: the CLI subprocess reports the flag and the hold decision."""
        # covers: ACD-1600c-1
        # angle: reachability
        out = _scan([_ac("T-600a-1", hold_reason="test design pending", declared_files=_FILES,
                         test_spec=_TEST_SPEC)], "--enforce-impl-readiness")
        self.assertEqual(out["ready"], [])
        self.assertEqual(out["not_implementation_ready"],
                         [{"ac_id": "T-600a-1", "reasons": ["test design pending"], "held_back": True}])


if __name__ == "__main__":
    unittest.main()
