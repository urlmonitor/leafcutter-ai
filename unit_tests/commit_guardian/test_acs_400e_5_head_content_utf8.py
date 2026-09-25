"""
MODULE: test_acs_400e_5_head_content_utf8
GOAL: Regression test for ACS-400e-5 -- "The governance hook reads an AC
    file's HEAD version as UTF-8, so non-ASCII text never looks changed".
BUG: `_load_head_content()` in scripts/commit_guardian/check_ac_governance.py
    runs `git show HEAD:<path>` via `subprocess.run(..., text=True)` with no
    `encoding`, so Python decodes git's UTF-8 output with the locale encoding
    (cp1252 on Windows). The staged copy is read with `encoding="utf-8"`. Any
    non-ASCII character in a protected field (e.g. an em dash in `criteria`)
    therefore differs between the two reads, and the hook falsely reports
    "criteria was modified but amended_by was not updated".
FIX: pass `encoding="utf-8"` to the hook's `subprocess.run(..., text=True)`
    calls.
ARCHITECTURE: Real end-to-end reproduction, mirroring
    test_acs_400e_4_head_lookup_posix_path: a real fixture git repo, a real AC
    YAML committed to HEAD, an open-field-only edit, and the real hook script
    invoked via subprocess. The hook subprocess inherits the host locale, so
    on a cp1252 host (Windows) the unfixed hook blocks and the fixed hook
    passes. On a UTF-8-locale host both pass (the bug cannot occur there).

# covers: ACS-400e-5
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
_HOOK_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_governance.py"
_SUBPROCESS_TIMEOUT_SECONDS = 30


def _git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Run a real `git` subprocess against a fixture repository.

    Args:
        args: Argument list appended after `git`.
        cwd: Working directory to run git in.

    Returns:
        The completed subprocess result; raises on failure so a broken
        fixture never masquerades as a test verdict.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env={**os.environ, "COMMIT_AGENT_MODE": "1"},
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _run_hook(ac_file: Path, root: Path, agent_id: str) -> subprocess.CompletedProcess:
    """Invoke the real hook script exactly as the pre-commit runner would.

    Args:
        ac_file: Absolute path to the AC YAML file to check.
        root: The fixture git repository root.
        agent_id: The committing agent identity.

    Returns:
        The completed subprocess result.
    """
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        cwd=str(root),
        env={
            **os.environ,
            "HOOK_ROOT": str(root),
            "HOOK_TEST_FILES": str(ac_file),
            "HOOK_AGENT_ID": agent_id,
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestHeadContentDecodedAsUtf8(unittest.TestCase):
    """ACS-400e-5: HEAD and staged copies of an AC file must be decoded the
    same way (UTF-8), so unchanged non-ASCII protected fields compare equal.
    """

    def test_open_field_edit_on_non_ascii_ac_is_not_blocked(self):
        # covers: ACS-400e-5
        # angle: reachability
        """Editing only `covered_by` on a committed AC whose `criteria`
        contains an em dash must pass (exit 0). The unfixed hook decodes the
        HEAD copy with the locale encoding, sees `criteria` as changed, and
        blocks with "criteria was modified".
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _git(["init", "-q"], root)
            _git(["config", "user.email", "fixture@example.invalid"], root)
            _git(["config", "user.name", "Fixture Author"], root)

            ac_file = (
                root / "docs" / "acceptance-criteria" / "acs-400-ac-governance"
                / "ACS-TEST-UTF8-001.yaml"
            )
            ac_file.parent.mkdir(parents=True, exist_ok=True)
            original = {
                "id": "ACS-TEST-UTF8-001",
                "title": "Existing AC whose criteria holds non-ASCII text",
                "criteria": "Given a baseline — with an em dash, Then nothing changes.",
                "origin_agent": "business-analyst-v3",
                "amended_by": ["business-analyst-v3"],
                "covered_by": [],
            }
            ac_file.write_text(
                yaml.safe_dump(original, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            _git(["add", "."], root)
            _git(["commit", "-q", "-m", "seed existing AC file"], root)

            modified = dict(original)
            modified["covered_by"] = ["ACS-TEST-UTF8-001-i"]
            ac_file.write_text(
                yaml.safe_dump(modified, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

            result = _run_hook(ac_file, root, agent_id="it-po")
            combined = result.stdout + result.stderr

            self.assertNotIn(
                "criteria was modified",
                combined,
                "An unchanged non-ASCII criteria field was reported as modified: "
                "the HEAD copy was decoded with a different encoding than the "
                f"staged copy. stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            self.assertEqual(
                result.returncode,
                0,
                "Expected exit 0: only the open field covered_by was edited. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
