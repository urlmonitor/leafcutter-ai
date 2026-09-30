"""
MODULE: unit_tests/commit_guardian/test_acd_1600c_4_ii.py
AC: ACD-1600c-4-ii — the "no declared files" named state and the refused
    empty-list state. This file carries the two commit_guardian-targeted
    test_spec entries; the ac_store-targeted entries live in
    unit_tests/ac_store/test_acd_1600c_4_ii.py.

GOAL: TDD red-baseline proving:
    1. L (no declared_files key) is accepted (exit 0) by check_ac_schema in
       BOTH branches (jsonschema available and forced unavailable) and by
       validate_ac_schema.py — absence of `declared_files` must never be a
       validation violation (ADR-026 safety rule 4).
    2. E (declared_files: [] — an explicit empty list) is refused
       (non-zero exit) by the hook's manual fallback and by
       validate_ac_schema.py, naming E and stating that a requirement with
       no files to declare leaves the list out rather than declaring it
       empty.

WHY RED TODAY (Test 2) / NOTED GREEN TODAY (Test 1). Test 2 is red today
    because nothing in validate_manually() or validate_ac_schema.py's
    schema-skipped path knows to refuse an empty declared_files list —
    confirmed live at test-writer time: it currently exits 0 (a WRONG
    accept). Test 1 (L accepted) is a KNOWN, DOCUMENTED PASS-IMMEDIATELY
    case: an AC record that simply has no declared_files key already
    validates cleanly today, with or without this feature, because there is
    nothing to reject — ADR-026 safety rule 4 ("absence is never a
    violation") holds trivially before the feature exists too. This is
    flagged with `note: "passes immediately — may be under-specified"` in
    the red_baseline per the test-writer skill's Outcome Handling table,
    rather than forcing an artificial failure into a test whose own
    test_spec description is scoped to L alone.
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


class TestRecordWithoutListAcceptedByHookAndValidator(unittest.TestCase):
    """test_record_without_list_accepted_by_hook_and_validator"""

    def test_record_without_list_accepted_by_hook_and_validator(self) -> None:
        # covers: ACD-1600c-4-ii
        # angle: criterion
        """L is accepted (exit 0) by check_ac_schema in both branches
        (jsonschema available and forced unavailable) and by
        validate_ac_schema.py.

        NOTE (see module docstring): this is a documented pass-immediately
        case. L has no declared_files key at all, and "absence is never a
        violation" already holds today, independent of whether this AC's
        feature exists. Recorded in red_baseline with
        note: "passes immediately — may be under-specified" rather than
        forced into artificial failure.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)
            l_path = write_ac_yaml(store, "ZDF-501")  # L: no declared_files key.
            init_git_index(root)
            git_add_all(root)

            jsonschema_available_run = run_hook_against_real_index(root)
            env = force_jsonschema_unavailable_env(root)
            jsonschema_unavailable_run = run_hook_against_real_index(root, extra_env=env)
            validator_run = run_validate_ac_schema(l_path)

        self.assertEqual(jsonschema_available_run.returncode, 0, msg=jsonschema_available_run.stderr)
        self.assertEqual(jsonschema_unavailable_run.returncode, 0, msg=jsonschema_unavailable_run.stderr)
        self.assertEqual(validator_run.returncode, 0, msg=validator_run.stderr)


class TestEmptyListRefusedWithLeaveItOutMessage(unittest.TestCase):
    """test_empty_list_refused_with_leave_it_out_message"""

    def test_empty_list_refused_with_leave_it_out_message(self) -> None:
        # covers: ACD-1600c-4-ii
        # angle: failure
        """E is refused (non-zero exit) by the hook's manual fallback and by
        validate_ac_schema.py with a message naming E and stating the list
        is left out rather than declared empty.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)
            e_path = write_ac_yaml(store, "ZDF-502", declared_files=[])
            init_git_index(root)
            git_add_all(root)
            env = force_jsonschema_unavailable_env(root)

            hook_result = run_hook_against_real_index(root, extra_env=env)
            validator_result = run_validate_ac_schema(e_path, extra_env=env)

        for label, result in (("hook manual fallback", hook_result), ("validator", validator_result)):
            self.assertNotEqual(
                result.returncode,
                0,
                msg=f"{label} must refuse E (empty declared_files). stderr: {result.stderr}",
            )
            self.assertIn("ZDF-502", result.stderr, msg=f"{label} must name E.")
            self.assertIn(
                "leaves the list out",
                result.stderr,
                msg=f"{label} must state the record leaves the list out rather "
                f"than declaring it empty. stderr: {result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
