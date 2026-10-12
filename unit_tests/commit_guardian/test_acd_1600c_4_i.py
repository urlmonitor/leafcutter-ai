"""
MODULE: unit_tests/commit_guardian/test_acd_1600c_4_i.py
AC: ACD-1600c-4-i — existence-vs-marker rule, LOAD-BEARING enforcement point.
    This file carries the one commit_guardian-targeted test_spec entry; the
    ac_store-targeted entries live in unit_tests/ac_store/test_acd_1600c_4_i.py.

GOAL: TDD red-baseline proving the check-ac-schema hook's manual-fallback
    branch (jsonschema forced unavailable) refuses R on the nowhere.py entry
    (non-zero exit) and exits 0 once it is re-marked, with the done_proof.py
    report still printed — the same existence-vs-marker rule
    unit_tests/ac_store/test_acd_1600c_4_i.py exercises at the seam level,
    here exercised through the REAL commit-time entry point with a REAL
    temporary git index.

WHY RED TODAY. check_ac_schema.py has no existence-vs-marker knowledge of
    `declared_files` at all yet (the field is not even schema-recognised),
    so today the hook rejects R for "Additional properties are not allowed"
    regardless of which entry is inconsistent — a real, behaviour-absent red
    reason, not an import failure.
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
    write_real_file,
)

_DECLARED = [
    {"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"},
    {"path": "scripts/ac_store/declared_files.py", "state": "to_be_created"},
    {"path": "scripts/ac_store/nowhere.py", "state": "existing"},
    {"path": "scripts/ac_store/done_proof.py", "state": "to_be_created"},
]


class TestRefusalBlocksCommitInHookManualFallback(unittest.TestCase):
    """test_refusal_blocks_commit_in_hook_manual_fallback"""

    def test_refusal_blocks_commit_in_hook_manual_fallback(self) -> None:
        # covers: ACD-1600c-4-i
        # angle: seam
        """check_ac_schema.py with jsonschema forced unavailable refuses R
        (non-zero exit) on the nowhere.py entry and exits 0 once it is
        re-marked, with the done_proof.py report still printed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)
            write_real_file(root, "scripts/ac_store/scan_ac_store.py")
            write_real_file(root, "scripts/ac_store/done_proof.py")

            ac_path = write_ac_yaml(store, "ZDF-204", declared_files=_DECLARED, work_status="todo")
            init_git_index(root)
            git_add_all(root)
            env = force_jsonschema_unavailable_env(root)

            first_run = run_hook_against_real_index(root, extra_env=env)

            # Re-mark nowhere.py to_be_created and re-stage.
            remarked = [dict(e) for e in _DECLARED]
            for entry in remarked:
                if entry["path"] == "scripts/ac_store/nowhere.py":
                    entry["state"] = "to_be_created"
            write_ac_yaml(store, "ZDF-204", declared_files=remarked, work_status="todo")
            # write_ac_yaml re-derives the path deterministically from ac_id/subdir.
            self.assertEqual(ac_path, store / "ac-driven-dev" / "ZDF-204.yaml")
            git_add_all(root)

            second_run = run_hook_against_real_index(root, extra_env=env)

        self.assertNotEqual(
            first_run.returncode,
            0,
            msg=(
                "First run must refuse R on the nowhere.py entry. "
                f"stderr: {first_run.stderr}"
            ),
        )
        self.assertIn("scripts/ac_store/nowhere.py", first_run.stderr)

        self.assertEqual(
            second_run.returncode,
            0,
            msg=(
                "After re-marking nowhere.py to_be_created, R must be "
                f"accepted. stderr: {second_run.stderr}"
            ),
        )
        self.assertIn(
            "scripts/ac_store/done_proof.py",
            second_run.combined,
            msg="The done_proof.py report must still be printed even though "
            "the run now exits 0.",
        )


if __name__ == "__main__":
    unittest.main()
