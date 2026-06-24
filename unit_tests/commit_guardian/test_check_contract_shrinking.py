"""
MODULE: test_check_contract_shrinking
GOAL: Unit tests for _scan_diff() in check_contract_shrinking.py, specifically
    verifying the commit_guardian path exclusion (AC-3, AC-6).
BUSINESS CONTEXT: The _TEST_PATH_RE must exclude paths containing commit_guardian/
    so that changes to the hook scripts themselves are not treated as production
    code changes. Without this exclusion, staging check_contract_shrinking.py
    alongside a pytest.mark.xfail removal would trigger the hook's own block logic
    (false-positive self-referential detection).
ARCHITECTURE: Directly imports _scan_diff from the canonical template location.
    Tests use synthetic diffs containing commit_guardian/ paths alongside
    xfail/skip patterns to verify the exclusion fires correctly.
"""

import sys
import textwrap
import unittest
from pathlib import Path

# Import the module under test from the canonical tree.
_CANONICAL = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_contract_shrinking.py"
)

# Dynamically import the module from the canonical path
import importlib.util as _ilu

def _load_module():
    if _CANONICAL.exists():
        spec = _ilu.spec_from_file_location("check_contract_shrinking", _CANONICAL)
        mod = _ilu.module_from_spec(spec)
        # Must register in sys.modules BEFORE exec_module so @dataclass
        # can resolve the module's __dict__ via sys.modules[cls.__module__].
        sys.modules["check_contract_shrinking"] = mod
        spec.loader.exec_module(mod)
        return mod
    return None


_mod = _load_module()


class TestContractShrinkingExcludesCommitGuardianPaths(unittest.TestCase):
    """AC-6: commit_guardian/ paths are excluded from production file classification."""

    def test_contract_shrinking_excludes_commit_guardian_paths(self):
        # covers: UNKNOWN
        """AC-6: A diff modifying templates/scripts/commit_guardian/check_contract_shrinking.py
        alongside a +pytest.mark.xfail line must NOT be classified as contract-shrinking.

        The commit_guardian/ path should be excluded by _TEST_PATH_RE (or equivalent),
        so has_production_changes is False even though the file is a .py and has added lines."""
        if _mod is None:
            self.fail(
                "ImportError: check_contract_shrinking.py not found at canonical "
                f"path {_CANONICAL}. "
                "Ensure the canonical template file exists at templates/scripts/commit_guardian/."
            )

        if not hasattr(_mod, "_scan_diff"):
            self.fail(
                "AttributeError: _scan_diff not found in check_contract_shrinking module. "
                "The module must expose _scan_diff() as a public-for-testing function."
            )

        diff = textwrap.dedent("""\
            diff --git a/templates/scripts/commit_guardian/check_contract_shrinking.py b/templates/scripts/commit_guardian/check_contract_shrinking.py
            index abc..def 100644
            --- a/templates/scripts/commit_guardian/check_contract_shrinking.py
            +++ b/templates/scripts/commit_guardian/check_contract_shrinking.py
            @@ -36,6 +36,7 @@ _TEST_PATH_RE = re.compile(
                 r"(unit_tests/|tests/|test_[^/]+\\.py$|[^/]+_test\\.py$|conftest\\.py$",
            +    r"|commit_guardian/)",
                 re.IGNORECASE,
             )
            +@pytest.mark.xfail
            +def test_removed_weakening():
            +    pass
        """)

        result = _mod._scan_diff(diff)
        self.assertFalse(
            result.has_production_changes,
            msg=(
                "has_production_changes should be False for commit_guardian/ paths, "
                f"but got True. Production files detected: {result.production_files}"
            ),
        )

    def test_contract_shrinking_excludes_legacy_commit_guardian_path(self):
        # covers: UNKNOWN
        """AC-6 (legacy variant): templates/commit-guardian/ path also excluded."""
        if _mod is None:
            self.fail(
                "ImportError: check_contract_shrinking.py not found at either path."
            )
        if not hasattr(_mod, "_scan_diff"):
            self.fail("_scan_diff not found in check_contract_shrinking module.")

        diff = textwrap.dedent("""\
            diff --git a/templates/commit-guardian/check_contract_shrinking.py b/templates/commit-guardian/check_contract_shrinking.py
            index abc..def 100644
            --- a/templates/commit-guardian/check_contract_shrinking.py
            +++ b/templates/commit-guardian/check_contract_shrinking.py
            @@ -36,6 +36,7 @@ _TEST_PATH_RE = re.compile(
            +    r"|commit_guardian/)",
                 re.IGNORECASE,
             )
        """)

        result = _mod._scan_diff(diff)
        self.assertFalse(
            result.has_production_changes,
            msg=(
                "has_production_changes should be False for templates/commit-guardian/ paths. "
                f"Got production files: {result.production_files}"
            ),
        )

    def test_non_commit_guardian_py_still_detected_as_production(self):
        # covers: UNKNOWN
        """Sanity check: a real production .py file is still detected as production
        (the commit_guardian exclusion must not over-broad exclude everything)."""
        if _mod is None:
            self.fail("ImportError: check_contract_shrinking.py not found.")
        if not hasattr(_mod, "_scan_diff"):
            self.fail("_scan_diff not found in check_contract_shrinking module.")

        diff = textwrap.dedent("""\
            diff --git a/scripts/some_production_script.py b/scripts/some_production_script.py
            index abc..def 100644
            --- a/scripts/some_production_script.py
            +++ b/scripts/some_production_script.py
            @@ -1,3 +1,4 @@
             def existing_func():
            -    return 1
            +    return 2
        """)

        result = _mod._scan_diff(diff)
        self.assertTrue(
            result.has_production_changes,
            msg="scripts/some_production_script.py must still be detected as a production file.",
        )


if __name__ == "__main__":
    unittest.main()
