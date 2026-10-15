"""
MODULE: test_generate_product_truth_check_mode
GOAL: Pin the --check CLI contract of generate_product_truth.py: compute
    everything, write nothing, exit non-zero if and only if a derived file would
    change, and name the stale file so a caller can act on the failure.
ARCHITECTURE: Copies the real scripts directory into a temp store and runs the
    real script as a subprocess (the production entry point). The store is
    settled by a real write-mode run, then made stale by editing an AC.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS_SRC = _REPO / "docs" / "product-truth" / "scripts"


def _flow() -> dict:
    return {
        "id": "leafcutter/test-flow",
        "component": "leafcutter",
        "kind": "user",
        "source": "real",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [{"id": "step-a", "label": "Step A", "order": 1, "implements": ["ACD-001"]}],
        "branches": [],
    }


class _CheckModeBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.pt = self.root / "docs" / "product-truth"
        shutil.copytree(_SCRIPTS_SRC, self.pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        flow_dir = self.pt / "flows" / "leafcutter"
        flow_dir.mkdir(parents=True)
        self.flow_path = flow_dir / "test-flow.flow.json"
        self.flow_path.write_text(json.dumps(_flow(), indent=2) + "\n", encoding="utf-8")
        (self.pt / "mock-data").mkdir()
        (self.pt / "index.json").write_text(
            json.dumps({"artifacts": [], "entity_registry": []}, indent=2) + "\n", encoding="utf-8"
        )
        self.ac_dir = self.root / "docs" / "acceptance-criteria" / "leafcutter"
        self.ac_dir.mkdir(parents=True)
        self.ac_path = self.ac_dir / "ACD-001.yaml"
        self.ac_path.write_text(
            yaml.safe_dump({"id": "ACD-001", "work_status": "not_started", "title": "t"}), encoding="utf-8"
        )
        # Settle the store with a real write-mode run.
        settled = self._run([], "2026-01-01")
        self.assertEqual(settled.returncode, 0, settled.stdout + settled.stderr)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, args: list[str], now: str = "2026-01-01") -> subprocess.CompletedProcess:
        script = self.pt / "scripts" / "generate_product_truth.py"
        return subprocess.run(
            [sys.executable, str(script), "--now", now, *args],
            capture_output=True, text=True, timeout=120,
        )

    def _make_stale(self) -> None:
        text = self.ac_path.read_text(encoding="utf-8").replace("work_status: not_started", "work_status: done")
        self.ac_path.write_text(text, encoding="utf-8")

    def _snapshot(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in sorted(self.root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }


class TestCheckMode(_CheckModeBase):
    def test_check_exits_non_zero_when_a_derived_file_would_change(self) -> None:
        # covers: UXP-513
        # angle: criterion
        """With a stale derived file present, --check exits non-zero."""
        self._make_stale()
        result = self._run(["--check", "--now", "2026-06-15"])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_check_exits_zero_when_nothing_would_change(self) -> None:
        # covers: UXP-513
        # angle: boundary
        """With derived data current, --check exits zero (the only-if arm)."""
        result = self._run(["--check", "--now", "2026-06-15"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("up to date", result.stdout + result.stderr)

    def test_check_writes_nothing_even_when_it_reports_a_change(self) -> None:
        # covers: UXP-513
        # angle: real_artifact
        """Every file in the store is byte-identical after a failing --check run."""
        self._make_stale()
        before = self._snapshot()
        result = self._run(["--check", "--now", "2026-06-15"])
        self.assertNotEqual(result.returncode, 0, "precondition: check must report the change")
        self.assertEqual(before, self._snapshot(), "--check mutated the store")

    def test_check_names_which_derived_file_would_change(self) -> None:
        # covers: UXP-513
        # angle: failure
        """The --check output names the stale file so a caller can act on it."""
        self._make_stale()
        result = self._run(["--check", "--now", "2026-06-15"])
        self.assertNotEqual(result.returncode, 0)
        out = result.stdout + result.stderr
        self.assertIn("test-flow.flow.json", out, "stale flow file must be named")


if __name__ == "__main__":
    unittest.main(verbosity=2)
