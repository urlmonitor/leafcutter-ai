"""
MODULE: unit_tests/commit_guardian/test_drift_exempt_recorded_key.py
GOAL: Pin the DIRECT-DRIFT: EXEMPT branch of check_output_drift.py's Pass 2 —
    a manifest-RECORDED output whose on-disk hash no longer matches, but whose
    key carries a valid ``drift_gate_exemption_registry`` entry, must be
    reported as ``DIRECT-DRIFT: EXEMPT <key> ground=<g>``, counted in the
    RESULT line's ``exempt`` field, and must NOT block (exit 0).
BUSINESS CONTEXT: Before this branch existed the exemption registry could only
    excuse an UNREGISTERED artifact (Pass 1's ``UNCOMPARABLE: EXEMPT``). A
    registered artifact that drifted was always a violation, with no way to
    declare it as not-build-determined. The widening is deliberate but narrow,
    and these tests exist to pin exactly how narrow: the suppression is keyed
    on the individual artifact and requires a non-blank ground, so it can
    never degrade into a blanket "ignore drift" switch. See
    check_output_drift.py's DRIFT-EXEMPT REPORTING docstring section and its
    2026-10-05 DECISION HISTORY entry.

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES the real,
    unmodified gate module as a subprocess against a synthesized
    manifest/deployed-output fixture, and asserts on the process's actual exit
    status and emitted RESULT / DIRECT-DRIFT lines — never a grep of the
    gate's source. test_drifted_and_unexempt_still_blocks is the control that
    proves each fixture is a genuine drift case before any exemption is
    applied, so a vacuous pass is not mistakable for a suppression.
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
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)\s+missing=(\d+)(?:\s+unreadable=(\d+))?",
    re.IGNORECASE,
)

_GROUND = "Hand-maintained consumer file; no build phase writes deterministic content to it."


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


class _DriftExemptFixture(unittest.TestCase):
    """Synthesizes a workspace with one clean and two drifted recorded outputs.

    Subclasses/tests vary only the exemption registry handed to the gate via
    ``HOOK_TEST_CONFIG``, so every assertion below differs from the control by
    exactly one variable: what the registry declares.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        pkg_root = self.workspace / "leafcutter-ai"
        (pkg_root / "templates" / "agents").mkdir(parents=True)
        agents_dir = self.workspace / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        clean_bytes = b"# clean.md\nmatches the manifest\n"
        (agents_dir / "clean.md").write_bytes(clean_bytes)
        (agents_dir / "declared.md").write_bytes(b"# declared.md\nhand-edited since deploy\n")
        (agents_dir / "undeclared.md").write_bytes(b"# undeclared.md\nhand-edited since deploy\n")

        self.clean_key = ".claude/agents/clean.md"
        self.declared_key = ".claude/agents/declared.md"
        self.undeclared_key = ".claude/agents/undeclared.md"
        # A hash of content that is NOT what is on disk -> genuine drift for
        # both declared.md and undeclared.md.
        stale_hash = _sha256_bytes(b"# whatever build.py originally deployed\n")

        manifest = {
            "package_root": pkg_root.name,
            "output_mappings": {
                self.clean_key: {
                    "template": "templates/agents/clean.md",
                    "expected_output_hash": _sha256_bytes(clean_bytes),
                },
                self.declared_key: {
                    "template": "templates/agents/declared.md",
                    "expected_output_hash": stale_hash,
                },
                self.undeclared_key: {
                    "template": "templates/agents/undeclared.md",
                    "expected_output_hash": stale_hash,
                },
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

    def _run_with_registry(self, entries: list | None) -> tuple[int, str]:
        """Execute the deployed gate with ``entries`` as its exemption registry.

        Args:
            entries: Raw registry entries, or None to leave HOOK_TEST_CONFIG
                unset so the gate reads its own colocated commit_guardian.json.

        Returns:
            (returncode, combined stdout+stderr) of the gate subprocess.
        """
        env = dict(os.environ)
        if entries is None:
            env.pop("HOOK_TEST_CONFIG", None)
        else:
            registry_path = self.workspace / "test_registry.json"
            registry_path.write_text(
                json.dumps({"drift_gate_exemption_registry": entries}), encoding="utf-8"
            )
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

    def _result_fields(self, combined: str) -> re.Match[str]:
        """Return the parsed RESULT summary line, failing if the gate emitted none.

        Uses ``self.fail`` rather than ``assertIsNotNone`` so the None case is
        narrowed away for the type checker as well as at runtime.
        """
        match = _RESULT_LINE_RE.search(combined)
        if match is None:
            self.fail(f"No RESULT summary line. Output:\n{combined}")
        return match


class TestRecordedKeyDriftExemption(_DriftExemptFixture):
    """The DIRECT-DRIFT: EXEMPT branch, and the limits on what it suppresses."""

    def test_drifted_and_unexempt_still_blocks(self) -> None:
        """Control: with an EMPTY registry both drifted outputs are violations.

        Proves the fixture is a genuine drift case, so a later exit 0 is
        evidence of suppression rather than of a vacuous fixture.
        """
        code, combined = self._run_with_registry([])
        self.assertEqual(1, code, msg=f"Drift with no exemption must exit 1. Output:\n{combined}")
        match = self._result_fields(combined)
        self.assertEqual(
            2, int(match.group(5)), msg=f"Both drifted outputs must count. Output:\n{combined}"
        )
        self.assertEqual(
            0, int(match.group(3)), msg=f"Nothing is exempt yet. Output:\n{combined}"
        )
        self.assertNotIn(
            "DIRECT-DRIFT: EXEMPT",
            combined,
            msg=f"No exemption was declared, so none may be reported. Output:\n{combined}",
        )

    def test_declared_key_is_reported_as_direct_drift_exempt(self) -> None:
        """A grounded entry on a RECORDED, drifted key moves it out of violations."""
        code, combined = self._run_with_registry(
            [{"path": self.declared_key, "ground": _GROUND}]
        )
        self.assertIn(
            f"DIRECT-DRIFT: EXEMPT {self.declared_key}",
            combined,
            msg=f"The exempted artifact must be individually named. Output:\n{combined}",
        )
        self.assertIn(
            f"ground={_GROUND}",
            combined,
            msg=f"The declared ground must be echoed verbatim. Output:\n{combined}",
        )
        match = self._result_fields(combined)
        self.assertEqual(
            1,
            int(match.group(3)),
            msg=f"declared.md must be counted in exempt. Output:\n{combined}",
        )
        self.assertEqual(
            1,
            int(match.group(5)),
            msg=(
                "Only undeclared.md may remain drifted — the exemption must "
                f"not absorb both. Output:\n{combined}"
            ),
        )
        self.assertEqual(
            0, int(match.group(4)), msg=f"gaps must stay 0. Output:\n{combined}"
        )

    def test_exemption_is_scoped_to_its_own_key(self) -> None:
        """Exempting one drifted key must leave a sibling key's drift blocking.

        This is the test that fails if the branch ever degrades into a blanket
        drift switch: undeclared.md is byte-identical in shape to declared.md
        and differs only in being absent from the registry.
        """
        code, combined = self._run_with_registry(
            [{"path": self.declared_key, "ground": _GROUND}]
        )
        self.assertEqual(
            1,
            code,
            msg=(
                "undeclared.md is still drifted, so the run must block even "
                f"though its sibling is exempt. Output:\n{combined}"
            ),
        )
        self.assertNotIn(
            f"DIRECT-DRIFT: EXEMPT {self.undeclared_key}",
            combined,
            msg=f"An unregistered key must never be reported exempt. Output:\n{combined}",
        )

    def test_both_keys_declared_yields_a_clean_exit(self) -> None:
        """With every drifted key grounded, the gate exits 0 and reports no drift."""
        code, combined = self._run_with_registry(
            [
                {"path": self.declared_key, "ground": _GROUND},
                {"path": self.undeclared_key, "ground": _GROUND},
            ]
        )
        self.assertEqual(
            0, code, msg=f"Fully declared drift must not block. Output:\n{combined}"
        )
        match = self._result_fields(combined)
        self.assertEqual(
            0, int(match.group(5)), msg=f"drifted must be 0. Output:\n{combined}"
        )
        self.assertEqual(
            2, int(match.group(3)), msg=f"Both keys must count as exempt. Output:\n{combined}"
        )
        self.assertEqual(
            0, int(match.group(6)), msg=f"missing must be 0. Output:\n{combined}"
        )
        self.assertEqual(
            3,
            int(match.group(1)),
            msg=(
                "All three recorded keys were hash-compared, so verified "
                f"must be 3. Output:\n{combined}"
            ),
        )

    def test_groundless_entry_cannot_suppress_drift(self) -> None:
        """A registry entry with a blank ground is rejected, so drift still blocks.

        Pins that Pass 2 consults the VALIDATED map, not the raw registry —
        otherwise a bare ``{"path": ...}`` would be a no-questions-asked
        drift bypass.
        """
        code, combined = self._run_with_registry(
            [
                {"path": self.declared_key, "ground": "   "},
                {"path": self.undeclared_key, "ground": _GROUND},
            ]
        )
        self.assertIn(
            f"REJECTED EXEMPTION ENTRY: {self.declared_key}",
            combined,
            msg=f"The groundless entry must be named as rejected. Output:\n{combined}",
        )
        self.assertEqual(
            1,
            code,
            msg=(
                "declared.md's exemption was rejected, so its drift must "
                f"still block. Output:\n{combined}"
            ),
        )
        match = self._result_fields(combined)
        self.assertEqual(
            1,
            int(match.group(5)),
            msg=f"declared.md must remain the one drifted artifact. Output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
