"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_3_i.py
COVERS: BP-1100g-3-i

GOAL: Negative-control regression test proving the `# angle: <kind>` tag axis
    (added by BP-1100g-3) never changes the verdict of the DEPLOYED CI gate --
    `python scripts/commit_guardian/check_done_proof.py --mode ci-changed` --
    the one place a leaked tag would actually flip a real merge decision.

BUSINESS CONTEXT: see unit_tests/ac_store/test_bp_1100g_3_i.py's module
    docstring for the full negative-control rationale (angle axis is filtered
    out before it ever reaches `verify_done_eligible`, which this CLI calls).
    This file adds the one test_spec entry that must run through the real,
    deployed subprocess entry point rather than an in-process function call --
    `check_changed_done_acs` unit tests already exist
    (unit_tests/commit_guardian/test_done_proof_ci_changed_scope.py) and
    exercise the function directly; this test is the reachability angle that
    confirms the SAME invariance holds when invoked exactly as CI invokes it.

=== A GREEN FIRST RUN IS THE EXPECTED, CORRECT RESULT ===

    See the sibling ac_store test file's module docstring. This ticket adds
    no production code (n_location_rule: "0"); a RED result here would name a
    real leak of the angle axis into the CI gate's merge decision, not a
    test-authoring defect.

FIXTURE AUTHENTICITY: the AC YAML fixture is written with yaml.safe_dump.
    The changed-AC-yaml detection is exercised through a REAL git repository
    (git init + two real commits) rather than a mocked `git diff` -- this is
    the actual mechanism `_get_changed_ac_yaml_paths` uses in production, and
    a mock would not catch a tag leaking into the diff-scoping step itself.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_PYTHON_EXE = sys.executable

_ANGLE_LINE_RE = re.compile(r"^[ \t]*#\s*angle:.*\n", re.MULTILINE)


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in *cwd* and raise on failure (fixture setup only)."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


class TestCiChangedGateVerdictUnaffectedByAngleTag(unittest.TestCase):
    """test_spec: test_bp_1100g_3_i_enforcement_unchanged_through_the_deployed_gate
    (angle: reachability)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self._tmp.name)
        _run_git(["init", "-q"], self.repo_dir)
        _run_git(["config", "user.email", "test-writer@example.com"], self.repo_dir)
        _run_git(["config", "user.name", "BP-1100g-3-i test fixture"], self.repo_dir)

        self.ac_root = self.repo_dir / "docs" / "acceptance-criteria"
        self.test_root = self.repo_dir / "tests"
        self.ac_root.mkdir(parents=True)
        self.test_root.mkdir(parents=True)

        # Base commit -- the repo exists, but the gated AC yaml does not yet.
        (self.repo_dir / ".gitkeep").write_text("", encoding="utf-8")
        _run_git(["add", "-A"], self.repo_dir)
        _run_git(["commit", "-q", "-m", "base"], self.repo_dir)
        self.base_sha = _run_git(["rev-parse", "HEAD"], self.repo_dir).stdout.strip()

        self.ac_id = "ZZ-1100g-3-i-gate"
        component_dir = self.ac_root / "test-component"
        component_dir.mkdir(parents=True)
        (component_dir / f"{self.ac_id}.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": self.ac_id,
                    "title": "synthetic BP-1100g-3-i CI-gate fixture AC",
                    "component": "build-orchestration",
                    "status": "active",
                    "work_status": "done",
                    "test_required": True,
                    "covered_by": [],
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        self.test_file = self.test_root / "test_gate.py"
        self.test_file.write_text(
            textwrap.dedent(
                f"""\
                def test_covers_gate():
                    # covers: {self.ac_id}
                    # angle: criterion
                    assert False, "intentional failure -- the gate must catch this"
                """
            ),
            encoding="utf-8",
        )

        # Second commit -- the gated AC yaml (and its test) now exist, so
        # `git diff <base>...HEAD` reports the AC yaml as changed.
        _run_git(["add", "-A"], self.repo_dir)
        _run_git(["commit", "-q", "-m", "add gated ac"], self.repo_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_gate(self) -> subprocess.CompletedProcess:
        """Invoke the REAL production CLI entry point as a subprocess."""
        return subprocess.run(
            [
                _PYTHON_EXE,
                str(_COMMIT_GUARDIAN_DIR / "check_done_proof.py"),
                "--mode", "ci-changed",
                "--base", self.base_sha,
                "--ac-root", str(self.ac_root),
                "--test-root", str(self.test_root),
            ],
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_bp_1100g_3_i_enforcement_unchanged_through_the_deployed_gate(
        self,
    ) -> None:
        # covers: BP-1100g-3-i
        # angle: reachability
        """PRODUCTION ENTRY POINT: run
        `python scripts/commit_guardian/check_done_proof.py --mode ci-changed
        --base <ref>` as a real subprocess over a fixture store and test
        tree, once with the angle tag present and once with it physically
        removed from the test file on disk, and assert byte-identical
        verdicts (stdout + exit code) -- the CI gate is where a leaked tag
        would actually change a merge decision."""
        with_angle = self._run_gate()

        # Strip the '# angle:' line from the REAL file on disk. No new git
        # commit is needed: --test-root is scanned LIVE from the filesystem
        # by verify_done_eligible, not from git state, so this mutation is
        # visible to the next invocation without touching the diff scope.
        original = self.test_file.read_text(encoding="utf-8")
        stripped = _ANGLE_LINE_RE.sub("", original)
        self.assertNotEqual(
            original, stripped, "fixture must actually carry an angle tag"
        )
        self.test_file.write_text(stripped, encoding="utf-8")

        without_angle = self._run_gate()

        self.assertEqual(
            with_angle.returncode,
            without_angle.returncode,
            f"exit code must be identical with/without the angle tag. "
            f"with={with_angle.returncode!r} stdout={with_angle.stdout!r} "
            f"without={without_angle.returncode!r} stdout={without_angle.stdout!r}",
        )
        self.assertEqual(
            with_angle.stdout,
            without_angle.stdout,
            "the gate's printed verdict must be byte-identical with/without "
            "the angle tag -- a leaked tag would show up here first",
        )

        # Sanity: the fixture is a real violation (failing covers-tagged test
        # on a done AC), so the comparison above is not vacuously true on an
        # always-empty, always-passing verdict.
        self.assertEqual(
            with_angle.returncode,
            1,
            f"expected the gate to block on the failing covers-tagged test; "
            f"stdout={with_angle.stdout!r} stderr={with_angle.stderr!r}",
        )
        self.assertIn(self.ac_id, with_angle.stdout)


if __name__ == "__main__":
    unittest.main()
