"""
MODULE: test_precommit_canary
GOAL: TDD red-baseline tests for scripts/commit_guardian/precommit_canary.py
BUSINESS CONTEXT: The canary hook prints exactly "PRECOMMIT_CANARY_OK" to stdout
    and exits 0.  Its manifest entry in commit_guardian.json must have
    stages: ["manual"], always_run: true, pass_filenames: false.
    All tests are RED until both the script and the manifest entry are implemented.
ARCHITECTURE: Direct-invocation tests run precommit_canary.py as a subprocess.
    Manifest tests read scripts/commit_guardian/commit_guardian.json directly and
    assert the presence and correctness of the canary entry.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/02]: Initial TDD red-baseline.
  precommit_canary.py does not exist yet; commit_guardian.json has no
  canary entry.  All tests are expected to fail RED until both are created.
====================================================================
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CANARY_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "precommit_canary.py"
_GUARDIAN_JSON = _REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"

# Expected output from the canary script (no trailing whitespace, LF newline)
EXPECTED_CANARY_OUTPUT = "PRECOMMIT_CANARY_OK\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_guardian_json() -> dict:
    """Load commit_guardian.json and return the parsed dict.

    Returns:
        Parsed JSON dict.

    Raises:
        FileNotFoundError: If commit_guardian.json does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    return json.loads(_GUARDIAN_JSON.read_text(encoding="utf-8"))


def _find_canary_hook_entry(hooks: list) -> dict | None:
    """Search the hooks list for the precommit-canary entry.

    Looks for a hook whose ``id`` contains 'canary' or 'precommit-canary'.

    Args:
        hooks: List of hook dicts from commit_guardian.json hooks_manifest.hooks.

    Returns:
        The matching hook dict, or ``None`` if not found.
    """
    for hook in hooks:
        hook_id = hook.get("id", "")
        if "canary" in hook_id:
            return hook
    return None


# ---------------------------------------------------------------------------
# Tests — direct invocation
# ---------------------------------------------------------------------------


class TestDirectInvocationEmitsCanaryOk(unittest.TestCase):
    """Running precommit_canary.py directly must emit exactly PRECOMMIT_CANARY_OK."""

    def test_direct_invocation_emits_canary_ok(self):
        # covers: UNKNOWN
        """Executing precommit_canary.py with no arguments must:
          - Print exactly "PRECOMMIT_CANARY_OK\\n" to stdout (nothing more, nothing less).
          - Exit with code 0.

        The script does not yet exist, so this test fails RED with a non-zero
        exit code and an error in stderr.
        """
        result = subprocess.run(
            [sys.executable, str(_CANARY_SCRIPT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"Expected exit 0 from precommit_canary.py, got {result.returncode}.\n"
                f"Script path: {_CANARY_SCRIPT}\n"
                f"stdout: {result.stdout!r}\n"
                f"stderr: {result.stderr!r}\n"
                "Implement precommit_canary.py that prints PRECOMMIT_CANARY_OK and exits 0."
            ),
        )
        self.assertEqual(
            result.stdout,
            EXPECTED_CANARY_OUTPUT,
            msg=(
                f"Expected stdout to be exactly {EXPECTED_CANARY_OUTPUT!r}.\n"
                f"Got: {result.stdout!r}\n"
                "The canary must print exactly PRECOMMIT_CANARY_OK followed by a newline "
                "and nothing else."
            ),
        )
        self.assertEqual(
            result.stderr,
            "",
            msg=(
                f"Expected empty stderr from canary. Got: {result.stderr!r}\n"
                "The canary must not write to stderr."
            ),
        )


# ---------------------------------------------------------------------------
# Tests — hook manifest in commit_guardian.json
# ---------------------------------------------------------------------------


class TestHookManifestStages(unittest.TestCase):
    """The canary entry in commit_guardian.json must have stages: [manual]."""

    def test_hook_manifest_stages(self):
        # covers: UNKNOWN
        """The hook manifest entry for the canary must have stages: ["manual"].

        A 'manual' stage means pre-commit only runs the hook when explicitly
        invoked with --hook-stage manual, not on every commit.  This is what
        allows verify_precommit_active.py to trigger it on demand.

        The entry does not yet exist in commit_guardian.json — this test fails
        RED with a self.fail() until the entry is added.
        """
        data = _load_guardian_json()
        hooks = data.get("hooks_manifest", {}).get("hooks", [])
        entry = _find_canary_hook_entry(hooks)
        if entry is None:
            self.fail(
                "No canary hook entry found in commit_guardian.json "
                "hooks_manifest.hooks (looked for id containing 'canary'). "
                "Add the precommit-canary entry with stages: [manual], "
                "always_run: true, pass_filenames: false."
            )
        stages = entry.get("stages", [])
        self.assertEqual(
            stages,
            ["manual"],
            msg=(
                f"Expected stages: [\"manual\"] for the canary hook entry. "
                f"Got: {stages!r}. "
                f"Full entry: {entry}"
            ),
        )


class TestHookManifestAlwaysRun(unittest.TestCase):
    """The canary entry must have always_run: true."""

    def test_hook_manifest_always_run(self):
        # covers: UNKNOWN
        """The hook manifest entry for the canary must have always_run: true.

        always_run: true means the hook runs even when no files are staged.
        This is required because the canary is a detection probe, not a
        file-content validator.

        Fails RED until the entry is added to commit_guardian.json.
        """
        data = _load_guardian_json()
        hooks = data.get("hooks_manifest", {}).get("hooks", [])
        entry = _find_canary_hook_entry(hooks)
        if entry is None:
            self.fail(
                "No canary hook entry found in commit_guardian.json "
                "hooks_manifest.hooks (looked for id containing 'canary'). "
                "Add the precommit-canary entry with stages: [manual], "
                "always_run: true, pass_filenames: false."
            )
        self.assertTrue(
            entry.get("always_run"),
            msg=(
                f"Expected always_run: true for the canary hook entry. "
                f"Got: {entry.get('always_run')!r}. "
                f"Full entry: {entry}"
            ),
        )


class TestHookManifestPassFilenames(unittest.TestCase):
    """The canary entry must have pass_filenames: false."""

    def test_hook_manifest_pass_filenames(self):
        # covers: UNKNOWN
        """The hook manifest entry for the canary must have pass_filenames: false.

        pass_filenames: false means pre-commit does not append staged file paths
        as CLI arguments when it runs the hook.  The canary is a fixed-output
        probe and does not process any files.

        Fails RED until the entry is added to commit_guardian.json.
        """
        data = _load_guardian_json()
        hooks = data.get("hooks_manifest", {}).get("hooks", [])
        entry = _find_canary_hook_entry(hooks)
        if entry is None:
            self.fail(
                "No canary hook entry found in commit_guardian.json "
                "hooks_manifest.hooks (looked for id containing 'canary'). "
                "Add the precommit-canary entry with stages: [manual], "
                "always_run: true, pass_filenames: false."
            )
        self.assertFalse(
            entry.get("pass_filenames", True),
            msg=(
                f"Expected pass_filenames: false for the canary hook entry. "
                f"Got: {entry.get('pass_filenames')!r}. "
                f"Full entry: {entry}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
