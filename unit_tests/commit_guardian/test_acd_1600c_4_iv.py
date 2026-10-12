"""
MODULE: unit_tests/commit_guardian/test_acd_1600c_4_iv.py
AC: ACD-1600c-4-iv — F (finished) is never refused at commit time when its
    declared existing file has since been deleted by other work; U
    (unfinished) is refused exactly as ACD-1600c-4-i already requires. This
    file carries the two commit_guardian-targeted test_spec entries; the
    ac_store-targeted entries (the store-wide report section) live in
    unit_tests/ac_store/test_acd_1600c_4_iv.py.

GOAL: TDD red-baseline proving the LOAD-BEARING check-ac-schema hook (both
    branches) and validate_ac_schema.py:
    1. Accept F (work_status: done) unchanged when only its notes are
       edited, even though its declared "existing" file
       (scripts/ac_store/legacy_helper.py) does not exist on disk — no
       output line names F or legacy_helper.py.
    2. Refuse U (work_status: todo, same declaration) with exactly one
       message naming U and legacy_helper.py as neither present nor marked
       to be created — exactly as any unfinished record.

WHY RED TODAY. `declared_files` is not yet schema-recognised at all, so
    today BOTH F and U are rejected uniformly for "Additional properties are
    not allowed" — F is wrongly refused (must never be), and U's refusal
    message does not yet say what ACD-1600c-4-i/-iv require. Both are
    genuine, behaviour-absent red reasons.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_AC_STORE_TEST_DIR = Path(__file__).resolve().parent.parent / "ac_store"
sys.path.insert(0, str(_AC_STORE_TEST_DIR))

from _declared_files_fixtures import (  # noqa: E402
    copy_real_schema_into,
    force_jsonschema_unavailable_env,
    git_add_all,
    git_commit_all,
    init_git_index,
    init_repo_root,
    run_hook_against_real_index,
    run_validate_ac_schema,
    write_ac_yaml,
)

_LEGACY_HELPER = "scripts/ac_store/legacy_helper.py"


class TestFinishedRecordAbsentExistingEntryAcceptedByHook(unittest.TestCase):
    """test_finished_record_absent_existing_entry_accepted_by_hook"""

    def test_finished_record_absent_existing_entry_accepted_by_hook(self) -> None:
        # covers: ACD-1600c-4-iv
        # angle: boundary
        """A change editing only F's notes passes check_ac_schema (exit 0)
        in both branches and validate_ac_schema, and no output line names F
        or legacy_helper.py. legacy_helper.py is never created on disk,
        simulating "later, unrelated work has deleted" it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)
            copy_real_schema_into(root)
            write_ac_yaml(
                store,
                "ZDF-701",
                declared_files=[{"path": _LEGACY_HELPER, "state": "existing"}],
                work_status="done",
                notes="original notes",
            )
            init_git_index(root)
            git_commit_all(root, "baseline: F exists at HEAD")

            # Edit only F's notes; re-stage.
            f_path = write_ac_yaml(
                store,
                "ZDF-701",
                declared_files=[{"path": _LEGACY_HELPER, "state": "existing"}],
                work_status="done",
                notes="edited notes only",
            )
            git_add_all(root)

            jsonschema_available_run = run_hook_against_real_index(root)
            env = force_jsonschema_unavailable_env(root)
            jsonschema_unavailable_run = run_hook_against_real_index(root, extra_env=env)
            validator_run = run_validate_ac_schema(f_path, extra_env=env)

        for label, result in (
            ("jsonschema-available hook", jsonschema_available_run),
            ("jsonschema-unavailable hook", jsonschema_unavailable_run),
            ("validator", validator_run),
        ):
            self.assertEqual(result.returncode, 0, msg=f"{label} must accept F. stderr: {result.stderr}")
            # legacy_helper.py's absence must never be reported for F, in any
            # form — a refusal, a warning, or a "declared existing, now
            # absent" note — regardless of the surface. The validator's own
            # ordinary success line legitimately names the FILE PATH it just
            # validated (e.g. "OK: .../ZDF-701.yaml is valid."), which is not
            # a report about legacy_helper.py, so only that path string is
            # asserted absent here, on both stdout and stderr.
            self.assertNotIn(_LEGACY_HELPER, result.stdout)
            self.assertNotIn(_LEGACY_HELPER, result.stderr)
        # The hooks themselves must be entirely silent on success — no line
        # anywhere names F by id.
        self.assertNotIn("ZDF-701", jsonschema_available_run.combined)
        self.assertNotIn("ZDF-701", jsonschema_unavailable_run.combined)


class TestUnfinishedRecordAbsentExistingEntryRefusedOnce(unittest.TestCase):
    """test_unfinished_record_absent_existing_entry_refused_once"""

    def test_unfinished_record_absent_existing_entry_refused_once(self) -> None:
        # covers: ACD-1600c-4-iv
        # angle: failure
        """A change editing U is refused (non-zero exit) with exactly one
        message naming U and legacy_helper.py as neither present nor marked
        to be created.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = init_repo_root(root)
            copy_real_schema_into(root)
            write_ac_yaml(
                store,
                "ZDF-702",
                declared_files=[{"path": _LEGACY_HELPER, "state": "existing"}],
                work_status="todo",
            )
            init_git_index(root)
            git_add_all(root)
            env = force_jsonschema_unavailable_env(root)

            result = run_hook_against_real_index(root, extra_env=env)

        self.assertNotEqual(result.returncode, 0, msg=f"U must be refused. stderr: {result.stderr}")
        occurrences = result.stderr.count(_LEGACY_HELPER)
        self.assertEqual(
            occurrences,
            1,
            msg=f"Expected exactly one message naming legacy_helper.py, got "
            f"{occurrences}. stderr: {result.stderr}",
        )
        self.assertIn("ZDF-702", result.stderr)
        self.assertIn("neither present nor marked to be created", result.stderr)


if __name__ == "__main__":
    unittest.main()
