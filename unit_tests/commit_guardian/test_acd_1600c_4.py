"""
MODULE: unit_tests/commit_guardian/test_acd_1600c_4.py
AC: ACD-1600c-4 — the single `declared_files` read seam. This file carries
    the ONE commit_guardian-targeted test_spec entry; the ac_store-targeted
    entries live in unit_tests/ac_store/test_acd_1600c_4.py (same AC, split
    by target_dir per the AC's own test_spec).

GOAL: TDD red-baseline for the LOAD-BEARING enforcement point: the
    check-ac-schema commit hook's manual fallback branch (jsonschema
    genuinely unavailable) AND scripts/ac_store/validate_ac_schema.py must
    both reject a malformed `declared_files` entry (unknown `state` value,
    or a missing `path` key) — per ACD-1600c-4's it_requirements, this
    semantic rule must be implemented ONCE, in the seam, and invoked by
    BOTH enforcement points so neither can silently diverge.

WHY RED TODAY. Today, `validate_manually()` (the hook's manual-fallback
    path) and `validate_ac_schema.py`'s manual/schema-skipped path have no
    knowledge of `declared_files` at all — confirmed live at test-writer
    time: forcing jsonschema unavailable and validating a record whose
    declared_files entry has state: "bogus_state" (or a missing path key)
    currently exits 0 on BOTH paths (a WRONG accept). This is the correct
    RED state: the hook and the validator do not yet enforce the AC's own
    semantic rule when jsonschema is absent.
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
    run_validate_ac_schema,
    write_ac_yaml,
)


class TestMalformedDeclaredFilesRejectedByHookFallbackAndValidator(unittest.TestCase):
    """test_malformed_declared_files_rejected_by_hook_fallback_and_validator"""

    def test_malformed_declared_files_rejected_by_hook_fallback_and_validator(self) -> None:
        # covers: ACD-1600c-4
        # angle: seam
        """A record with an unknown `state` value, and a sibling record
        missing `path`, are BOTH rejected (non-zero exit) by check_ac_schema
        with jsonschema forced unavailable (the manual-fallback branch) AND
        by validate_ac_schema.py under the same forced-unavailable condition
        — the two enforcement points must agree, per ACD-1600c-4's
        "implemented once, in the seam, invoked by both" requirement.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)
            unknown_state_path = write_ac_yaml(
                store,
                "ZDF-101",
                declared_files=[{"path": "scripts/ac_store/scan_ac_store.py", "state": "bogus_state"}],
            )
            missing_path_path = write_ac_yaml(
                store,
                "ZDF-102",
                declared_files=[{"state": "existing"}],
            )
            init_git_index(root)
            git_add_all(root)
            env = force_jsonschema_unavailable_env(root)

            hook_result = run_hook_against_real_index(root, extra_env=env)
            validator_result = run_validate_ac_schema(
                unknown_state_path, missing_path_path, extra_env=env
            )

        self.assertNotEqual(
            hook_result.returncode,
            0,
            msg=(
                "check_ac_schema.py's manual-fallback branch (jsonschema forced "
                "unavailable) must reject an entry with an unknown `state` "
                f"value and one missing `path`. stderr: {hook_result.stderr}"
            ),
        )
        self.assertIn("ZDF-101", hook_result.stderr)
        self.assertIn("ZDF-102", hook_result.stderr)

        self.assertNotEqual(
            validator_result.returncode,
            0,
            msg=(
                "validate_ac_schema.py must reject the same two malformed "
                f"records under the same forced-unavailable condition. "
                f"stderr: {validator_result.stderr}"
            ),
        )
        self.assertIn("ZDF-101", validator_result.stderr)
        self.assertIn("ZDF-102", validator_result.stderr)


if __name__ == "__main__":
    unittest.main()
