"""
MODULE: test_bo_1700c_1_iii_ordering_guard
GOAL: Red tests for the self-healing hook's ordering guard (BO-1700c-1-iii, A14).
BUSINESS CONTEXT: Only stage canaries (precommit-canary-*) may be registered before
    ensure-precommit-config. Any other hook before it makes the hook exit 1 naming it.

====================================================================
DECISION HISTORY
====================================================================
- 2026-10-22 [EPIC-WorkspaceMakerHardening/09]: Initial red tests. The pure function
  is loaded lazily so a missing symbol fails each test, not collection.
====================================================================
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO / "templates" / "scripts" / "commit_guardian"
SCRIPT = SCRIPT_DIR / "ensure_precommit_config.py"
MANIFEST = SCRIPT_DIR / "commit_guardian.json"
CANARIES = ["precommit-canary-pre-commit", "precommit-canary-commit-msg"]
HEAL = "ensure-precommit-config"


def _load_module():
    spec = importlib.util.spec_from_file_location("_epc_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest_text(ids):
    return json.dumps({"hooks_manifest": {"hooks": [{"id": i} for i in ids]}})


class _Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.script_dir = root / "scripts"
        self.script_dir.mkdir()
        self.script = self.script_dir / "ensure_precommit_config.py"
        shutil.copy(SCRIPT, self.script)
        self.worktree = root / "wt"
        self.worktree.mkdir()
        (self.worktree / ".pre-commit-config.yaml").write_text("repos: []\n")

    def run_hook(self, manifest_text):
        (self.script_dir / "commit_guardian.json").write_text(manifest_text)
        return subprocess.run(
            [sys.executable, str(self.script)],
            cwd=self.worktree, capture_output=True, text=True, timeout=30,
        )


class TestOrderingGuard(_Harness):
    def test_only_stage_canaries_before_self_heal_is_accepted(self):
        # covers: BO-1700c-1-iii
        # angle: boundary
        """Canaries-only prefix is accepted, in the function, subprocess and real manifest."""
        mod = _load_module()
        self.assertIsNone(mod.ordering_violation(CANARIES + [HEAL, "check-secrets"]))
        self.assertIsNone(mod.ordering_violation([HEAL, "check-secrets"]))
        real = json.loads(MANIFEST.read_text(encoding="utf-8"))
        ids = [h["id"] for h in real["hooks_manifest"]["hooks"]]
        self.assertIsNone(mod.ordering_violation(ids))
        proc = self.run_hook(_manifest_text(CANARIES + [HEAL, "check-secrets"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_non_canary_hook_before_self_heal_fails_closed_naming_it(self):
        # covers: BO-1700c-1-iii
        # angle: failure
        """A non-canary hook before the heal exits 1 and is named, wherever it sits."""
        mod = _load_module()
        for ids in (
            [CANARIES[0], "check-secrets", HEAL],
            ["check-secrets"] + CANARIES + [HEAL],
        ):
            msg = mod.ordering_violation(ids)
            self.assertIsNotNone(msg)
            self.assertIn("check-secrets", msg)
        # A look-alike prefix is not a stage canary.
        self.assertIn("precommit-canaryX", mod.ordering_violation(["precommit-canaryX", HEAL]) or "")
        proc = self.run_hook(_manifest_text([CANARIES[0], "check-secrets", HEAL]))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("check-secrets", proc.stderr)

    def test_missing_heal_or_unreadable_manifest_fails_closed(self):
        # covers: BO-1700c-1-iii
        # angle: failure
        """No heal entry, or invalid JSON, exits 1 with a reason on stderr."""
        mod = _load_module()
        self.assertIsNotNone(mod.ordering_violation(CANARIES + ["check-secrets"]))
        for text in (_manifest_text(CANARIES + ["check-secrets"]), "{not json"):
            proc = self.run_hook(text)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertTrue(proc.stderr.strip(), "expected a reason on stderr")


if __name__ == "__main__":
    unittest.main()
