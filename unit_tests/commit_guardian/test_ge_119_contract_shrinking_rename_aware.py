"""
MODULE: test_ge_119_contract_shrinking_rename_aware
GOAL: Red tests for GE-119 — the contract-shrinking guard must distinguish an
    EDITED test (removed `-def test_x` paired with a re-added `+def test_x` for
    the SAME name, anywhere in the diff) from a genuinely DELETED test (a name
    that is removed with no matching addition). Likewise "test file deleted"
    must fire only on an actual deletion (`+++ /dev/null`), not merely because
    a test file appears on the `--- a/` side of an ordinary modification.
BUSINESS CONTEXT: _scan_diff() currently runs each weakening regex as a bare
    finditer over the whole diff and appends one violation per match — it never
    pairs a removal with its corresponding addition. Any body-edit to an
    existing test (which git renders as a `-def test_x` / `+def test_x` pair,
    often in the same hunk) is misreported as "test function deleted", blocking
    routine merges/refactors and training the team to bypass the gate with
    SKIP=check-contract-shrinking. See GE-119 and
    docs/acceptance-criteria/guardrail-engine/GE-119.yaml.
ARCHITECTURE: Loads check_contract_shrinking.py from its canonical template
    path (same pattern as test_check_contract_shrinking.py) and drives
    _scan_diff() directly for precision on cases 1-5. Case 1 (via _scan_diff)
    is paired with an end-to-end subprocess run of main() using HOOK_TEST_DIFF
    (same pattern as test_contract_shrinking.py) so the test cannot pass
    against dead code — it exercises the real CLI entrypoint and exit code.
    Cases 1 and 4 are RED against the current bare-finditer implementation;
    the fix (name-pairing removed vs. re-added test names; /dev/null-gated
    file-deletion pattern) is a later phase. Do NOT edit
    check_contract_shrinking.py from this test file.
"""

from __future__ import annotations

import importlib.util as _ilu
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Import the module under test from the canonical tree (mirrors
# test_check_contract_shrinking.py's loading convention).
_CANONICAL = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_contract_shrinking.py"
)


def _load_module():
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_contract_shrinking_ge119", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    # Must register in sys.modules BEFORE exec_module so @dataclass can
    # resolve the module's __dict__ via sys.modules[cls.__module__].
    sys.modules["check_contract_shrinking_ge119"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def run_hook_with_diff(diff_content: str) -> subprocess.CompletedProcess:
    """Run the real hook script end-to-end via HOOK_TEST_DIFF (no mocking)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(diff_content)
        tmp_path = f.name
    try:
        env = os.environ.copy()
        env["HOOK_TEST_DIFF"] = tmp_path
        return subprocess.run(
            [sys.executable, str(_CANONICAL)],
            env=env,
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(tmp_path)


def _require_module():
    if _mod is None:
        raise AssertionError(
            f"ImportError: check_contract_shrinking.py not found at canonical path {_CANONICAL}."
        )
    if not hasattr(_mod, "_scan_diff"):
        raise AssertionError(
            "AttributeError: _scan_diff not found in check_contract_shrinking module."
        )


class TestGE119EditedTestNotReportedAsDeleted(unittest.TestCase):
    """AC: an edited test body (removed + re-added same name) is not a deletion."""

    def test_ac_ge119_edited_test_body_not_flagged_as_deleted(self):
        # covers: GE-119
        """RED (case 1): a production .py change plus a hunk containing both
        `-    def test_foo(self):` and `+    def test_foo(self):` for the SAME
        test name must produce NO "test function deleted" violation, and the
        overall scan must NOT be classified as contract-shrinking (assuming no
        other weakening patterns fire).

        Currently FAILS: _scan_diff() matches `^-\\s*def test_` with a bare
        finditer and never checks whether the same name was re-added, so this
        reports a spurious "test function deleted" violation.
        """
        _require_module()

        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,8 +5,9 @@
             class TestCore(unittest.TestCase):
            -    def test_foo(self):
            -        self.assertEqual(existing_func(), 1)
            +    def test_foo(self):
            +        # reformatted body, same assertion, still exists
            +        self.assertEqual(existing_func(), 2)
        """)

        result = _mod._scan_diff(diff)

        deleted_test_violations = [
            (label, ctx) for label, ctx in result.violations if label == "test function deleted"
        ]
        self.assertEqual(
            deleted_test_violations,
            [],
            msg=(
                "test_foo was removed and re-added under the same name in the same "
                f"diff, so it must not be reported as deleted. Got: {deleted_test_violations}"
            ),
        )
        self.assertFalse(
            result.is_contract_shrinking,
            msg="An edited (not deleted) test alongside a production change must not block the commit.",
        )

    def test_ac_ge119_edited_test_body_end_to_end_allows_commit(self):
        # covers: GE-119
        """RED (case 1, end-to-end): same scenario as above but driven through
        the real CLI entrypoint (main()) via HOOK_TEST_DIFF, so this cannot
        pass against dead code. Expect exit code 0 (commit allowed).

        Currently FAILS: the hook exits 1 ("BLOCKED") because the bare-finditer
        scan misreports the edited test as deleted.
        """
        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,8 +5,9 @@
             class TestCore(unittest.TestCase):
            -    def test_foo(self):
            -        self.assertEqual(existing_func(), 1)
            +    def test_foo(self):
            +        # reformatted body, same assertion, still exists
            +        self.assertEqual(existing_func(), 2)
        """)

        result = run_hook_with_diff(diff)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Editing an existing test's body (remove+re-add same name) must ALLOW "
                f"the commit. Got exit {result.returncode}. Stdout: {result.stdout}"
            ),
        )


class TestGE119GenuineDeletionStillBlocks(unittest.TestCase):
    """AC: a real deletion (name removed, never re-added) still blocks."""

    def test_ac_ge119_genuine_test_deletion_still_flagged(self):
        # covers: GE-119
        """A production change plus `-    def test_gone(self):` with no matching
        `+    def test_gone` anywhere in the diff must still report "test
        function deleted" and the scan must be classified as contract-shrinking.
        This must PASS both before and after the fix.
        """
        _require_module()

        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,7 +5,3 @@
             class TestCore(unittest.TestCase):
            -    def test_gone(self):
            -        self.assertEqual(existing_func(), 1)
            -
        """)

        result = _mod._scan_diff(diff)

        deleted_test_violations = [
            (label, ctx) for label, ctx in result.violations if label == "test function deleted"
        ]
        self.assertTrue(
            deleted_test_violations,
            msg="A genuinely deleted test (never re-added) must still be reported as deleted.",
        )
        self.assertTrue(
            result.is_contract_shrinking,
            msg="Genuine test deletion alongside a production change must still block the commit.",
        )

    def test_ac_ge119_genuine_test_deletion_end_to_end_blocks(self):
        # covers: GE-119
        """Same scenario driven end-to-end through main() — must exit 1."""
        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,7 +5,3 @@
             class TestCore(unittest.TestCase):
            -    def test_gone(self):
            -        self.assertEqual(existing_func(), 1)
            -
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(
            result.returncode,
            1,
            msg=f"Genuine test deletion must BLOCK the commit. Got exit {result.returncode}.",
        )
        self.assertIn("BLOCKED", result.stdout + result.stderr)


class TestGE119PartialReAdditionNamesOnlyTheSurvivor(unittest.TestCase):
    """AC: of two removed tests, only the one never re-added is reported."""

    def test_ac_ge119_partial_readdition_reports_only_ungone_test(self):
        # covers: GE-119
        """Two tests are removed (`test_a`, `test_b`); only `test_a` is
        re-added under the same name. The violation(s) reported for "test
        function deleted" must name test_b and must NOT name test_a.
        """
        _require_module()

        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,12 +5,9 @@
             class TestCore(unittest.TestCase):
            -    def test_a(self):
            -        self.assertEqual(existing_func(), 1)
            -
            -    def test_b(self):
            -        self.assertEqual(existing_func(), 1)
            +    def test_a(self):
            +        # reformatted, still exists
            +        self.assertEqual(existing_func(), 2)
        """)

        result = _mod._scan_diff(diff)

        deleted_test_violations = [
            (label, ctx) for label, ctx in result.violations if label == "test function deleted"
        ]
        reported_text = " ".join(ctx for _label, ctx in deleted_test_violations)

        self.assertIn(
            "test_b",
            reported_text,
            msg=f"test_b was removed with no re-addition and must be reported. Got: {deleted_test_violations}",
        )
        self.assertNotIn(
            "test_a",
            reported_text,
            msg=f"test_a was re-added under the same name and must NOT be reported. Got: {deleted_test_violations}",
        )


class TestGE119TestFileDeletedOnlyOnRealDeletion(unittest.TestCase):
    """AC: "test file deleted" fires only on an actual /dev/null deletion."""

    def test_ac_ge119_modified_test_file_not_flagged_as_file_deleted(self):
        # covers: GE-119
        """RED (case 4): a diff that merely MODIFIES a top-level test file
        (`--- a/test_thing.py` / `+++ b/test_thing.py`, no /dev/null) plus a
        production change must NOT report "test file deleted".

        Currently FAILS: `_WEAKENING_PATTERNS` matches `^--- a/(test_...)`
        unconditionally, regardless of whether the file was actually deleted
        (`+++ /dev/null`) or merely modified.
        """
        _require_module()

        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/test_thing.py b/test_thing.py
            index abc..def 100644
            --- a/test_thing.py
            +++ b/test_thing.py
            @@ -1,3 +1,4 @@
             def test_unrelated():
                 assert True
            +    # a harmless comment added
        """)

        result = _mod._scan_diff(diff)

        file_deleted_violations = [
            (label, ctx) for label, ctx in result.violations if label == "test file deleted"
        ]
        self.assertEqual(
            file_deleted_violations,
            [],
            msg=(
                "test_thing.py was only MODIFIED (+++ b/test_thing.py, not /dev/null), "
                f"so 'test file deleted' must not fire. Got: {file_deleted_violations}"
            ),
        )

    def test_ac_ge119_real_test_file_deletion_still_flagged(self):
        # covers: GE-119
        """A genuine file deletion (`+++ /dev/null`) must still report "test
        file deleted" and block the commit. Must PASS both before and after
        the fix.
        """
        _require_module()

        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/test_thing.py b/test_thing.py
            deleted file mode 100644
            index abc..0000000
            --- a/test_thing.py
            +++ /dev/null
            @@ -1,3 +0,0 @@
            -def test_unrelated():
            -    assert True
            -
        """)

        result = _mod._scan_diff(diff)

        file_deleted_violations = [
            (label, ctx) for label, ctx in result.violations if label == "test file deleted"
        ]
        self.assertTrue(
            file_deleted_violations,
            msg=f"A real file deletion (+++ /dev/null) must still be reported. Got: {result.violations}",
        )
        self.assertTrue(
            result.is_contract_shrinking,
            msg="Genuine test file deletion alongside a production change must still block the commit.",
        )


class TestGE119OtherWeakeningPatternsUnaffected(unittest.TestCase):
    """AC: the fix must not over-correct into permissiveness for the other
    weakening patterns (pytest.skip, pytest.mark.xfail, @unittest.skip,
    @unittest.expectedFailure)."""

    def test_ac_ge119_other_weakening_patterns_still_block(self):
        # covers: GE-119
        """A diff exercising pytest.skip, pytest.mark.xfail, @unittest.skip,
        and @unittest.expectedFailure (none of which involve any test being
        removed/re-added) must still be flagged and still block the commit.
        Must PASS both before and after the fix.
        """
        _require_module()

        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -4,10 +4,15 @@
             class TestCore(unittest.TestCase):
            +    @unittest.skip("flaky")
                 def test_existing_func_returns_one(self):
            +        pytest.skip("temporarily skipped")
                     self.assertEqual(existing_func(), 1)
            +
            +    @pytest.mark.xfail
            +    def test_known_broken(self):
            +        pass
            +
            +    @unittest.expectedFailure
            +    def test_also_known_broken(self):
            +        pass
        """)

        result = _mod._scan_diff(diff)

        labels_found = {label for label, _ctx in result.violations}
        for expected_label in (
            "pytest.skip added",
            "pytest.mark.xfail added",
            "@unittest.skip added",
            "@unittest.expectedFailure added",
        ):
            self.assertIn(
                expected_label,
                labels_found,
                msg=f"Expected weakening pattern {expected_label!r} to still fire. Got: {labels_found}",
            )
        self.assertTrue(
            result.is_contract_shrinking,
            msg="These weakening patterns alongside a production change must still block the commit.",
        )

    def test_ac_ge119_other_weakening_patterns_end_to_end_blocks(self):
        # covers: GE-119
        """Same scenario driven end-to-end through main() — must exit 1."""
        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -4,5 +4,6 @@
             class TestCore(unittest.TestCase):
                 def test_existing_func_returns_one(self):
            +        pytest.skip("temporarily skipped")
                     self.assertEqual(existing_func(), 1)
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(
            result.returncode,
            1,
            msg=f"pytest.skip addition must still BLOCK the commit. Got exit {result.returncode}.",
        )
        self.assertIn("BLOCKED", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
