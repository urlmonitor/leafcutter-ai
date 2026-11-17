"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_vi.py
GOAL: Regression guard for BP-100k-3-vi — a ``drift_gate_exemption_registry``
    entry on a manifest-RECORDED output excuses CHANGED CONTENT only. A recorded
    output that is absent from disk (MISSING) or whose path is now a directory
    (UNREADABLE) must still be reported, counted, and block the commit, even when
    the registry carries a grounded entry for that very key.
BUSINESS CONTEXT: PR #1013 let the registry excuse a drifted recorded key
    (``DIRECT-DRIFT: EXEMPT``). The lookup sits only in Pass 2's hash-mismatch
    branch, after the missing / unreadable checks. Nothing stops a refactor from
    moving it earlier, which would let an exemption hide the deletion BP-100n-1
    exists to report. This pins existing behaviour, so a GREEN first run is the
    expected outcome (a RED run is a production defect, never an assertion to
    weaken).

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test EXECUTES the real gate as a
    subprocess from a deployed-shaped layout with the registry supplied through
    ``HOOK_TEST_CONFIG`` and asserts on emitted lines, the RESULT line and the
    exit status. No source grep, no direct import of the scan function.
    "Unreadable" is an EMPTY DIRECTORY replacing the recorded file (uid
    independent; chmod 000 is readable by root). It is empty so Pass 1 reports
    no GAP lines. The uncomparable / drift_exempt columns are deliberately NOT
    asserted: that counting question is going to an ADR.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CG_TEMPLATES_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

_SUBPROCESS_TIMEOUT_SECONDS = 15

_RESULT_LINE_RE = re.compile(
    r"check-output-drift:\s*RESULT\s+"
    r"verified=(?P<verified>\d+)\s+uncomparable=\d+\s+exempt=\d+\s+gaps=(?P<gaps>\d+)\s+"
    r"drifted=(?P<drifted>\d+)\s+missing=(?P<missing>\d+)\s+unreadable=(?P<unreadable>\d+)",
    re.IGNORECASE,
)

_GROUND = "Hand-maintained consumer file; no build phase writes deterministic content to it."


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


class TestExemptionNeverExcusesAbsenceOrUnreadability(unittest.TestCase):
    """Three grounded recorded keys: drifted, missing, and now-a-directory."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        pkg_root = self.workspace / "leafcutter-ai"
        (pkg_root / "templates" / "agents").mkdir(parents=True)
        agents_dir = self.workspace / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        self.drifted_key = ".claude/agents/drifted.md"
        self.missing_key = ".claude/agents/missing.md"
        self.unreadable_key = ".claude/agents/unreadable.md"

        (agents_dir / "drifted.md").write_bytes(b"# drifted.md\nhand-edited since deploy\n")
        # missing.md is deliberately never created.
        # EMPTY directory in place of the recorded file: no Pass 1 GAP lines.
        (agents_dir / "unreadable.md").mkdir()

        recorded_hash = _sha256_bytes(b"# whatever build.py originally deployed\n")
        manifest = {
            "package_root": pkg_root.name,
            "output_mappings": {
                key: {
                    "template": f"templates/agents/{Path(key).name}",
                    "expected_output_hash": recorded_hash,
                }
                for key in (self.drifted_key, self.missing_key, self.unreadable_key)
            },
            "output_mappings_error": "",
            "output_mappings_skipped_sections": [],
        }
        (self.workspace / ".build_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        deployed_dir = self.workspace / ".leafcutter" / "scripts" / "commit_guardian"
        shutil.copytree(
            _CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__")
        )
        self.hook = deployed_dir / "check_output_drift.py"

        self.grounded = [
            {"path": key, "ground": _GROUND}
            for key in (self.drifted_key, self.missing_key, self.unreadable_key)
        ]
        self.code_grounded, self.out_grounded = self._run(self.grounded)
        self.code_empty, self.out_empty = self._run([])

    def _run(self, entries: list) -> tuple[int, str]:
        """Run the deployed gate with ``entries`` as the registry; return (rc, output)."""
        registry_path = self.workspace / "test_registry.json"
        registry_path.write_text(
            json.dumps({"drift_gate_exemption_registry": entries}), encoding="utf-8"
        )
        env = dict(os.environ)
        env["HOOK_TEST_CONFIG"] = str(registry_path)
        result = subprocess.run(
            [sys.executable, str(self.hook)],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            env=env,
        )
        return result.returncode, result.stdout + result.stderr

    def _fields(self, combined: str) -> dict[str, str]:
        """Return the named RESULT fields, failing if the gate emitted no RESULT line."""
        match = _RESULT_LINE_RE.search(combined)
        if match is None:
            self.fail(f"No RESULT summary line. Output:\n{combined}")
        return match.groupdict()

    def _assert_not_exempt(self, key: str, combined: str) -> None:
        for prefix in ("DIRECT-DRIFT: EXEMPT", "UNCOMPARABLE: EXEMPT"):
            self.assertNotIn(
                f"{prefix} {key}",
                combined,
                msg=f"{key} must never be reported exempt ({prefix}). Output:\n{combined}",
            )

    def test_bp_100k_3_vi_drifted_recorded_output_is_still_exempted_in_the_same_run(self) -> None:
        # covers: BP-100k-3-vi
        # angle: criterion
        """Positive control: the registry was read and honoured in the grounded run."""
        self.assertIn(
            f"DIRECT-DRIFT: EXEMPT {self.drifted_key} ground={_GROUND}",
            self.out_grounded.splitlines(),
            msg=f"A registry the gate ignored cannot pass. Output:\n{self.out_grounded}",
        )

    def test_bp_100k_3_vi_grounded_entry_does_not_excuse_a_missing_recorded_output(self) -> None:
        # covers: BP-100k-3-vi
        # angle: failure
        """A grounded entry on a deleted recorded output still yields MISSING."""
        self.assertIn(
            f"UNCOMPARABLE: MISSING {self.missing_key}",
            self.out_grounded,
            msg=f"Missing output must be reported. Output:\n{self.out_grounded}",
        )
        self.assertEqual(1, int(self._fields(self.out_grounded)["missing"]), msg=self.out_grounded)
        self._assert_not_exempt(self.missing_key, self.out_grounded)

    def test_bp_100k_3_vi_grounded_entry_does_not_excuse_an_unreadable_recorded_output(
        self,
    ) -> None:
        # covers: BP-100k-3-vi
        # angle: failure
        """A grounded entry on a path that became a directory still yields UNREADABLE."""
        self.assertIn(
            f"UNCOMPARABLE: UNREADABLE {self.unreadable_key}",
            self.out_grounded,
            msg=f"Unreadable output must be reported. Output:\n{self.out_grounded}",
        )
        self.assertEqual(
            1, int(self._fields(self.out_grounded)["unreadable"]), msg=self.out_grounded
        )
        self._assert_not_exempt(self.unreadable_key, self.out_grounded)

    def test_bp_100k_3_vi_run_with_grounded_missing_and_unreadable_keys_still_blocks(self) -> None:
        # covers: BP-100k-3-vi
        # angle: reachability
        """Every recorded key grounded, yet the run exits 1 (blocks)."""
        self.assertEqual(
            1,
            self.code_grounded,
            msg=f"Missing/unreadable must block despite grounds. Output:\n{self.out_grounded}",
        )

    def test_bp_100k_3_vi_missing_and_unreadable_counts_are_identical_with_an_empty_registry(
        self,
    ) -> None:
        # covers: BP-100k-3-vi
        # angle: discrimination
        """Registry content is the only variable; it must not change either count or exit."""
        grounded = self._fields(self.out_grounded)
        empty = self._fields(self.out_empty)
        self.assertEqual(1, int(empty["missing"]), msg=self.out_empty)
        self.assertEqual(1, int(empty["unreadable"]), msg=self.out_empty)
        self.assertEqual(empty["missing"], grounded["missing"], msg=self.out_grounded)
        self.assertEqual(empty["unreadable"], grounded["unreadable"], msg=self.out_grounded)
        self.assertEqual(1, self.code_empty, msg=self.out_empty)
        self.assertEqual(self.code_empty, self.code_grounded)


if __name__ == "__main__":
    unittest.main()
