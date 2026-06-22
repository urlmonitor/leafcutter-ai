"""
MODULE: test_contract_shrinking
GOAL: Unit tests for check_contract_shrinking.py pre-commit hook.
BUSINESS CONTEXT: Verifies the contract-shrinking guard correctly detects
    test weakening concurrent with production code changes, while allowing
    legitimate commits (test-only changes, prod-only changes, empty diffs).
ARCHITECTURE: Tests invoke the hook module directly via subprocess simulation.
    Each test provides a synthetic git diff string and asserts exit code and
    output. The hook is not yet implemented (TDD red-baseline phase).
"""

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

# The hook script that will be created by python-coder (does not exist yet — tests are RED)
HOOK_SCRIPT = Path(__file__).parent.parent.parent / "templates" / "scripts" / "commit_guardian" / "check_contract_shrinking.py"


def run_hook_with_diff(diff_content: str) -> subprocess.CompletedProcess:
    """Run the hook script with a synthetic diff injected via stdin / env patch."""
    # The hook reads from `git diff --cached` via subprocess.
    # We test by patching: run the hook as a subprocess and inject the diff
    # via a temporary file referenced by an env var (HOOK_TEST_DIFF).
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
        f.write(diff_content)
        tmp_path = f.name
    try:
        env = os.environ.copy()
        env['HOOK_TEST_DIFF'] = tmp_path
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
        )
        return result
    finally:
        os.unlink(tmp_path)


class TestContractShrinkingHook(unittest.TestCase):

    def test_blocks_when_test_deleted_with_production_change(self):
        """Staged diff has both deleted test function and modified production .py file → hook exits 1."""
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
            -    def test_existing_func_returns_one(self):
            -        self.assertEqual(existing_func(), 1)
            -
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(result.returncode, 1, f"Hook should exit 1 but got {result.returncode}. Stdout: {result.stdout}")
        self.assertIn("BLOCKED", result.stdout + result.stderr)

    def test_blocks_when_xfail_added_with_production_change(self):
        """Staged diff adds pytest.mark.xfail to test + production change → exits 1."""
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
            @@ -4,6 +4,7 @@
             class TestCore(unittest.TestCase):
            +    @pytest.mark.xfail
                 def test_existing_func_returns_one(self):
                     self.assertEqual(existing_func(), 1)
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(result.returncode, 1, f"Hook should exit 1 but got {result.returncode}. Stdout: {result.stdout}")
        self.assertIn("BLOCKED", result.stdout + result.stderr)

    def test_blocks_when_skip_added_with_production_change(self):
        """Staged diff adds pytest.skip call + production change → exits 1."""
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
        self.assertEqual(result.returncode, 1, f"Hook should exit 1 but got {result.returncode}. Stdout: {result.stdout}")
        self.assertIn("BLOCKED", result.stdout + result.stderr)

    def test_passes_when_only_test_deleted_no_production_change(self):
        """Only test deletion staged (no production code changes) → exits 0."""
        diff = textwrap.dedent("""\
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,7 +5,3 @@
             class TestCore(unittest.TestCase):
            -    def test_existing_func_returns_one(self):
            -        self.assertEqual(existing_func(), 1)
            -
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(result.returncode, 0, f"Hook should exit 0 but got {result.returncode}. Stdout: {result.stdout}")

    def test_passes_when_only_production_change(self):
        """Only production file modified (no test modifications) → exits 0."""
        diff = textwrap.dedent("""\
            diff --git a/mymodule/core.py b/mymodule/core.py
            index abc..def 100644
            --- a/mymodule/core.py
            +++ b/mymodule/core.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(result.returncode, 0, f"Hook should exit 0 but got {result.returncode}. Stdout: {result.stdout}")

    def test_passes_when_empty_diff(self):
        """Nothing staged → exits 0."""
        result = run_hook_with_diff("")
        self.assertEqual(result.returncode, 0, f"Hook should exit 0 but got {result.returncode}. Stdout: {result.stdout}")

    def test_conftest_not_treated_as_production(self):
        """conftest.py change + test deletion → exits 0 (conftest is test infrastructure, not production code)."""
        diff = textwrap.dedent("""\
            diff --git a/conftest.py b/conftest.py
            index abc..def 100644
            --- a/conftest.py
            +++ b/conftest.py
            @@ -1,4 +1,5 @@
             import pytest
            +import os
            diff --git a/unit_tests/test_core.py b/unit_tests/test_core.py
            index abc..def 100644
            --- a/unit_tests/test_core.py
            +++ b/unit_tests/test_core.py
            @@ -5,7 +5,3 @@
             class TestCore(unittest.TestCase):
            -    def test_existing_func_returns_one(self):
            -        self.assertEqual(existing_func(), 1)
            -
        """)
        result = run_hook_with_diff(diff)
        self.assertEqual(result.returncode, 0, f"Hook should exit 0 but got {result.returncode}. Stdout: {result.stdout}")


if __name__ == "__main__":
    unittest.main()
