"""
MODULE: unit_tests/commit_guardian/test_ge_124e_1.py
GOAL: GE-124e-1 -- the reverse (UI declaration) gate selects only screen criteria that
      are already finished, and records every other criterion with a distinct outcome.

Contract the implementation (templates/scripts/commit_guardian/check_ui_ac_declared.py)
must satisfy:

  select_criteria(index: dict[str, dict]) -> dict with keys
      "selected":  list of AC ids (change_target includes 'ui' AND work_status == 'done')
      "outcomes":  {ac_id: {"outcome": <str>, "reason": <str|None>}} for EVERY record
      "passed":    list of AC ids passed -- selection alone passes nothing, so this
                   stays empty at selection time
  OUTCOME_SELECTED / OUTCOME_SKIP / OUTCOME_OUT_OF_SCOPE: three pairwise-distinct
      outcome constants; the skip reason for a UI criterion not done is 'not-done'.
  CLI: python check_ui_ac_declared.py --mode ci|ci-changed --base REF --ac-root DIR --json
      prints a JSON report with the same keys as select_criteria on stdout.
  change_target may be a scalar OR a list (schema anyOf string|array).

Red until python-coder creates the gate script.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_GATE_SCRIPT = _TEMPLATE_DIR / "check_ui_ac_declared.py"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
for _p in (str(_AC_STORE_DIR), str(_TEMPLATE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _gate():
    """Import the gate module (ImportError until the script exists)."""
    return importlib.import_module("check_ui_ac_declared")


def _record(ac_id: str, change_target, work_status: str) -> dict:
    return {
        "id": ac_id,
        "title": f"title of {ac_id}",
        "component": "guardrail-engine",
        "level": "L2",
        "status": "active",
        "work_status": work_status,
        "change_target": change_target,
        "criteria": "Given x\nWhen y\nThen z\n",
    }


def _mixed_index() -> dict:
    recs = [
        _record("UXP-607-2", "ui", "done"),
        _record("MIX-100-1", ["ui", "code"], "done"),
        _record("COD-100-1", ["code"], "done"),
        _record("KM-ADM-003", "ui", "todo"),
        _record("GE-111f", "code", "todo"),
    ]
    return {r["id"]: r for r in recs}


def _write_store(root: Path, index: dict) -> None:
    """Write each record with the project's real serializer (yaml.safe_dump)."""
    root.mkdir(parents=True, exist_ok=True)
    for ac_id, rec in index.items():
        with open(root / f"{ac_id}.yaml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(rec, fh, sort_keys=False)


class TestReverseGateSelection(unittest.TestCase):
    def test_ge_124e_1_done_ui_criterion_is_selected(self):
        # covers: GE-124e-1
        # angle: criterion
        """AC-1: UXP-607-2 is selected (scalar AND list change_target forms)."""
        result = _gate().select_criteria(_mixed_index())
        self.assertIn("UXP-607-2", result["selected"])
        self.assertIn("MIX-100-1", result["selected"], "list-form change_target dropped")
        # Exact count: a list-only-code record and non-done/non-ui records are excluded.
        self.assertEqual(sorted(result["selected"]), ["MIX-100-1", "UXP-607-2"])

    def test_ge_124e_1_in_progress_ui_criterion_is_skipped_with_a_reason_not_passed(self):
        # covers: GE-124e-1
        # angle: criterion
        """AC-3: KM-ADM-003 not selected; outcome skip, reason 'not-done'; not passed."""
        gate = _gate()
        result = gate.select_criteria(_mixed_index())
        self.assertNotIn("KM-ADM-003", result["selected"])
        entry = result["outcomes"]["KM-ADM-003"]
        self.assertEqual(entry["outcome"], gate.OUTCOME_SKIP)
        self.assertEqual(entry["reason"], "not-done")
        self.assertNotIn("KM-ADM-003", result["passed"])
        self.assertEqual(result["passed"], [])

    def test_ge_124e_1_non_ui_criterion_is_out_of_scope_distinct_from_skipped_and_passed(self):
        # covers: GE-124e-1
        # angle: boundary
        """AC-4/AC-5: GE-111f is out of scope, a third outcome distinct from skip/pass."""
        gate = _gate()
        result = gate.select_criteria(_mixed_index())
        self.assertNotIn("GE-111f", result["selected"])
        self.assertNotIn("GE-111f", result["passed"])
        out = result["outcomes"]
        self.assertEqual(out["GE-111f"]["outcome"], gate.OUTCOME_OUT_OF_SCOPE)
        # list-form change_target with no 'ui' is also out of scope, even when done.
        self.assertEqual(out["COD-100-1"]["outcome"], gate.OUTCOME_OUT_OF_SCOPE)
        # every record recorded, none dropped
        self.assertEqual(sorted(out), sorted(_mixed_index()))
        values = {
            gate.OUTCOME_SELECTED,
            gate.OUTCOME_SKIP,
            gate.OUTCOME_OUT_OF_SCOPE,
        }
        self.assertEqual(len(values), 3, "outcome values must be pairwise distinct")
        self.assertEqual(out["KM-ADM-003"]["outcome"], gate.OUTCOME_SKIP)
        self.assertEqual(out["UXP-607-2"]["outcome"], gate.OUTCOME_SELECTED)


class TestReverseGateReachability(unittest.TestCase):
    def _run(self, store: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        return subprocess.run(
            [
                sys.executable,
                str(_GATE_SCRIPT),
                "--mode", "ci",
                "--base", "origin/main",
                "--ac-root", str(store),
                "--json",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

    def test_ge_124e_1_gate_is_reached_from_its_real_ci_entry_point_over_a_real_store(self):
        # covers: GE-124e-1
        # angle: reachability
        """Run the gate as CI does, over an on-disk store; flip a record; re-run."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "acceptance-criteria"
            index = _mixed_index()
            _write_store(store, index)

            first = self._run(store)
            self.assertEqual(first.returncode, 0, first.stderr)
            report = json.loads(first.stdout)
            self.assertEqual(sorted(report["selected"]), ["MIX-100-1", "UXP-607-2"])
            self.assertEqual(report["outcomes"]["KM-ADM-003"]["outcome"], "skip")
            self.assertEqual(report["outcomes"]["KM-ADM-003"]["reason"], "not-done")

            # Flip KM-ADM-003 to done on disk (bump mtime so no cache can mask it).
            index["KM-ADM-003"]["work_status"] = "done"
            _write_store(store, {"KM-ADM-003": index["KM-ADM-003"]})
            path = store / "KM-ADM-003.yaml"
            st = path.stat()
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

            second = self._run(store)
            self.assertEqual(second.returncode, 0, second.stderr)
            report2 = json.loads(second.stdout)
            self.assertEqual(
                sorted(report2["selected"]), ["KM-ADM-003", "MIX-100-1", "UXP-607-2"]
            )

    def test_ge_124e_1_unreadable_store_blocks_in_ci(self):
        # covers: GE-124e-1
        # angle: failure
        """A missing store produced no evidence: CI mode must exit non-zero."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp) / "does-not-exist")
            # Exactly 1 (the gate's own refusal), not 2 (interpreter: script not found).
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("check-ui-ac-declared", result.stderr)


if __name__ == "__main__":
    unittest.main()
