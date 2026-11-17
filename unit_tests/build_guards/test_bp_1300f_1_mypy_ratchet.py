"""
MODULE: unit_tests/build_guards/test_bp_1300f_1_mypy_ratchet.py
COVERS: BP-1300f-1-i, BP-1300f-1-ii, BP-1300f-1-iii, BP-1300f-1-iv -- the error
    half of the mypy ratchet: line-insensitive matching, inherited errors not
    charged, removals counted, renames compared with their old path, new files.
GOAL: Behavioural proof. Every integration test builds a real git repository with
    a base commit and a head commit (see _bp1300f_ratchet_fixture.py) and runs the
    real scripts/ci/mypy_ratchet.py with the real mypy, then reads its exit code and
    output. The one unit test feeds real mypy output lines to the comparison.
"""

from __future__ import annotations

import importlib
import unittest

from unit_tests.build_guards._bp1300f_ratchet_fixture import RatchetRepoCase

RETURN_ERR = "def f() -> str:\n    return 1\n"
ASSIGN_ERR = "def g() -> None:\n    y: int = \"s\"\n    print(y)\n"
TWO_ERRORS = "# version 1\n" + RETURN_ERR + "\n\n" + ASSIGN_ERR
FIVE_COMMENTS = "".join(f"# note {n}\n" for n in range(1, 6))
PADDING = "".join(f"CONSTANT_{n} = {n}\n" for n in range(8))


class TestLineInsensitiveMatching(RatchetRepoCase):
    """BP-1300f-1-i."""

    def test_bp_1300f_1_i_shifted_old_error_is_not_new(self):
        # covers: BP-1300f-1-i
        self.commit_base({"scripts/svc.py": RETURN_ERR})
        self.commit_head({"scripts/svc.py": FIVE_COMMENTS + RETURN_ERR})
        counts = self.assert_passed(self.ratchet())
        self.assertEqual((counts["new"], counts["existing"]), (0, 1))

    def test_bp_1300f_1_i_genuinely_new_error_fails_naming_line_code_and_remedy(self):
        # covers: BP-1300f-1-i
        # covers: BP-1300f-1
        # The rule end to end through the real module: the inherited error at line 2
        # is not charged, the added one at line 12 fails the run.
        self.commit_base({"scripts/svc.py": RETURN_ERR})
        filler = "\n\ndef h() -> None:\n    a = 1\n    b = a\n    print(b)\n\n\n"
        head = RETURN_ERR + filler + "def g() -> None:\n    y: int = \"s\"\n"
        self.assertEqual(head.splitlines()[11].strip(), 'y: int = "s"')  # line 12
        self.commit_head({"scripts/svc.py": head})
        run = self.ratchet()
        counts = self.assert_failed(run)
        self.assertEqual((counts["new"], counts["existing"]), (1, 1))
        named = self.lines_with(run.out, "scripts/svc.py:12:", "[assignment]")
        self.assertEqual(len(named), 1, run.out)
        self.assertIn("Incompatible types in assignment", named[0])
        self.assertTrue(self.lines_with(run.out, "remedy", "type: ignore"), run.out)
        self.assertFalse(self.lines_with(run.out, "scripts/svc.py:2:", "new error"), run.out)

    def test_bp_1300f_1_i_extra_copy_of_an_existing_error_is_new(self):
        # covers: BP-1300f-1-i
        self.commit_base({"scripts/svc.py": RETURN_ERR})
        self.commit_head({"scripts/svc.py": RETURN_ERR + "\n\ndef f2() -> str:\n    return 1\n"})
        run = self.ratchet()
        counts = self.assert_failed(run)
        self.assertEqual((counts["new"], counts["existing"]), (1, 1))
        named = self.lines_with(run.out, "scripts/svc.py:2,6:", "[return-value]")
        self.assertEqual(len(named), 1, run.out)
        self.assertIn("base already had 1", named[0])

    def test_bp_1300f_1_i_line_number_inside_a_message_is_not_identity(self):
        # covers: BP-1300f-1-i
        ratchet = importlib.import_module("scripts.ci.mypy_ratchet")
        wanted = {"scripts/svc.py"}
        base = ratchet.parse_mypy_output(
            'scripts/svc.py:4: error: Name "h" already defined on line 1  [no-redef]\n', wanted)
        head = ratchet.parse_mypy_output(
            'scripts/svc.py:9: error: Name "h" already defined on line 6  [no-redef]\n'
            'scripts/svc.py:9: note: a note line is never an error\n'
            'scripts/other.py:3: error: Followed module, not inspected  [misc]\n', wanted)
        same = ratchet.compare_errors(head, base)
        self.assertEqual((same.new, same.untouched, same.removed), ([], 1, 0))
        renamed = ratchet.parse_mypy_output(
            'scripts/svc.py:9: error: Name "k" already defined on line 6  [no-redef]\n', wanted)
        differs = ratchet.compare_errors(renamed, base)
        self.assertEqual((len(differs.new), differs.untouched, differs.removed), (1, 0, 1))


class TestInheritedErrorsAreNotCharged(RatchetRepoCase):
    """BP-1300f-1-ii."""

    def setUp(self) -> None:
        super().setUp()
        self.commit_base({"scripts/svc.py": TWO_ERRORS, "scripts/other.py": RETURN_ERR})

    def test_bp_1300f_1_ii_existing_errors_in_a_touched_file_are_not_charged(self):
        # covers: BP-1300f-1-ii
        self.commit_head({"scripts/svc.py": TWO_ERRORS.replace("# version 1", "# version 2")})
        run = self.ratchet()
        counts = self.assert_passed(run)
        self.assertEqual((counts["files"], counts["new"], counts["existing"]), (1, 0, 2))
        self.assertNotIn("scripts/other.py", run.out)

    def test_bp_1300f_1_ii_removed_error_passes_and_is_counted(self):
        # covers: BP-1300f-1-ii
        fixed = TWO_ERRORS.replace('y: int = "s"', "y: int = 1")
        self.commit_head({"scripts/svc.py": fixed})
        counts = self.assert_passed(self.ratchet())
        self.assertEqual((counts["new"], counts["existing"], counts["removed"]), (0, 1, 1))

    def test_bp_1300f_1_ii_removal_does_not_pay_for_an_addition(self):
        # covers: BP-1300f-1-ii
        swapped = TWO_ERRORS.replace('y: int = "s"', "y: int = len(5)")
        self.commit_head({"scripts/svc.py": swapped})
        run = self.ratchet()
        counts = self.assert_failed(run)
        self.assertEqual((counts["new"], counts["removed"]), (1, 1))
        self.assertEqual(len(self.lines_with(run.out, "scripts/svc.py:", "[arg-type]")), 1, run.out)


class TestRenamedFiles(RatchetRepoCase):
    """BP-1300f-1-iii."""

    def setUp(self) -> None:
        super().setUp()
        self.commit_base({"scripts/old_name.py": PADDING + TWO_ERRORS})

    def test_bp_1300f_1_iii_renamed_file_keeps_its_old_errors_uncharged(self):
        # covers: BP-1300f-1-iii
        edited = PADDING + TWO_ERRORS.replace("# version 1", "# version 2")
        self.commit_head({"scripts/new_name.py": edited},
                         renames={"scripts/old_name.py": "scripts/new_name.py"})
        counts = self.assert_passed(self.ratchet())
        self.assertEqual((counts["files"], counts["new"], counts["existing"]), (1, 0, 2))

    def test_bp_1300f_1_iii_renamed_file_with_an_added_error_fails_naming_the_new_path(self):
        # covers: BP-1300f-1-iii
        grown = PADDING + TWO_ERRORS + "\n\ndef k() -> int:\n    return \"k\"\n"
        added_line = len(grown.splitlines())
        self.commit_head({"scripts/new_name.py": grown},
                         renames={"scripts/old_name.py": "scripts/new_name.py"})
        run = self.ratchet()
        counts = self.assert_failed(run)
        self.assertEqual((counts["new"], counts["existing"]), (1, 2))
        named = self.lines_with(run.out, f"scripts/new_name.py:{added_line}:", "[return-value]")
        self.assertEqual(len(named), 1, run.out)
        self.assertFalse(self.lines_with(run.out, "scripts/old_name.py", "new error"), run.out)


class TestNewFiles(RatchetRepoCase):
    """BP-1300f-1-iv."""

    def setUp(self) -> None:
        super().setUp()
        self.commit_base({"scripts/keep.py": "KEEP = 1\n"})

    def test_bp_1300f_1_iv_new_file_with_an_error_fails(self):
        # covers: BP-1300f-1-iv
        self.commit_head({"scripts/fresh.py": RETURN_ERR})
        run = self.ratchet()
        counts = self.assert_failed(run)
        self.assertEqual((counts["files"], counts["new"]), (1, 1))
        self.assertEqual(len(self.lines_with(run.out, "scripts/fresh.py:2:", "[return-value]")), 1, run.out)

    def test_bp_1300f_1_iv_clean_new_file_passes(self):
        # covers: BP-1300f-1-iv
        self.commit_head({"scripts/fresh.py": "def f() -> str:\n    return \"ok\"\n"})
        counts = self.assert_passed(self.ratchet())
        self.assertEqual((counts["files"], counts["new"]), (1, 0))


if __name__ == "__main__":
    unittest.main()
