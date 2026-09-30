"""
MODULE: unit_tests/commit_guardian/test_acd_1600c_4_iii.py
AC: ACD-1600c-4-iii — "A declared path outside the repository, or inside a
    copy the build regenerates, is refused". This file carries the
    commit-time, real-hook proof for review finding H-1: a leading-'./'
    spelling of a regenerated-copy path must not escape the LOAD-BEARING
    check_ac_schema.py hook, exactly as the exact-spelling case already
    doesn't.

GOAL: TDD red-baseline proving that check_ac_schema.py's manual-fallback
    branch (jsonschema forced unavailable) refuses R when its ONLY
    declared_files entry is './.claude/agents/test-writer.md' — a
    leading-'./' spelling of a path this repository's own build regenerates
    from templates/agents/test-writer.md (confirmed via `git check-ignore`;
    see unit_tests/ac_store/test_acd_1600c_4_iii.py's module docstring for
    the same real-artifact confirmation) — with the refusal message naming
    templates/agents/test-writer.md as the file to declare instead.

WHY RED TODAY (H-1). scripts/ac_store/declared_files.py's
    `_regenerated_copy_error` matches a regenerated root with a raw
    `path.startswith(prefix)` and no normalisation: './.claude/agents/...'
    does not start with '.claude/agents/', so today's real (buggy)
    implementation returns NO refusal for this entry — the commit hook
    exits 0 and lets the bad declaration through. This is a real,
    behaviour-present red reason (the seam is implemented but wrong), not
    an import failure.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_AC_STORE_TEST_DIR = Path(__file__).resolve().parent.parent / "ac_store"
sys.path.insert(0, str(_AC_STORE_TEST_DIR))

from _declared_files_fixtures import (  # noqa: E402
    force_jsonschema_unavailable_env,
    git_add_all,
    init_git_index,
    init_repo_root,
    run_hook_against_real_index,
    write_ac_yaml,
)

_DECLARED = [{"path": "./.claude/agents/test-writer.md", "state": "to_be_created"}]


class TestDotSlashRegeneratedCopyRefusedAtCommitTime(unittest.TestCase):
    """test_dot_slash_regenerated_copy_refused_at_commit_time"""

    def test_dot_slash_regenerated_copy_refused_at_commit_time(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: discrimination
        """check_ac_schema.py (manual-fallback branch) must refuse R
        (non-zero exit) when its declared_files entry is
        './.claude/agents/test-writer.md' -- naming
        templates/agents/test-writer.md as the file to declare instead --
        exactly as it already does for the un-prefixed spelling. Red today
        against the named plausible wrong version: the real, shipped
        `_regenerated_copy_error`'s un-normalised `startswith` match.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)

            write_ac_yaml(store, "ZDF-301", declared_files=_DECLARED, work_status="todo")
            init_git_index(root)
            git_add_all(root)
            env = force_jsonschema_unavailable_env(root)

            result = run_hook_against_real_index(root, extra_env=env)

        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                "H-1 bypass: check_ac_schema.py must refuse "
                "'./.claude/agents/test-writer.md' as a regenerated copy "
                f"just like the unprefixed spelling. stderr: {result.stderr}"
            ),
        )
        self.assertIn("ZDF-301", result.stderr)
        self.assertIn("./.claude/agents/test-writer.md", result.stderr)
        self.assertIn("templates/agents/test-writer.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
