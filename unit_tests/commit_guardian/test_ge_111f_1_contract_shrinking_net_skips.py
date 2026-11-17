"""GE-111f-1: check-contract-shrinking nets moved skips and ignores new files.

A one-for-one replacement of an existing skip in a modified test file, and a
skip inside a brand-new test file, must not be reported as "pytest.skip added".
A skip added to an existing test that had none must still block.
"""

from __future__ import annotations

import importlib.util as _ilu
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_CANONICAL = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_contract_shrinking.py"
)

_PROD = (
    "diff --git a/src/app.py b/src/app.py\n"
    "--- a/src/app.py\n"
    "+++ b/src/app.py\n"
    "@@ -1,1 +1,2 @@\n"
    " x = 1\n"
    "+y = 2\n"
)

_REPLACED = (
    "diff --git a/unit_tests/test_live.py b/unit_tests/test_live.py\n"
    "--- a/unit_tests/test_live.py\n"
    "+++ b/unit_tests/test_live.py\n"
    "@@ -1,4 +1,4 @@\n"
    " def test_live():\n"
    '-    pytest.skip(f"live Neo4j not reachable: {exc}")\n'
    "+    pytest.skip(unreachable_reason(exc))\n"
    "     assert True\n"
)

_NEW_FILE = (
    "diff --git a/unit_tests/test_brand_new.py b/unit_tests/test_brand_new.py\n"
    "new file mode 100644\n"
    "index 0000000..1111111\n"
    "--- /dev/null\n"
    "+++ b/unit_tests/test_brand_new.py\n"
    "@@ -0,0 +1,3 @@\n"
    "+def test_new():\n"
    '+    pytest.skip("live service not reachable")\n'
    "+    assert True\n"
)

_ADDED_TO_EXISTING = (
    "diff --git a/unit_tests/test_old.py b/unit_tests/test_old.py\n"
    "--- a/unit_tests/test_old.py\n"
    "+++ b/unit_tests/test_old.py\n"
    "@@ -1,3 +1,4 @@\n"
    " def test_old():\n"
    '+    pytest.skip("now disabled")\n'
    "     assert True\n"
)


def _load():
    spec = _ilu.spec_from_file_location("check_cs_ge111f1", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_cs_ge111f1"] = mod
    spec.loader.exec_module(mod)
    return mod


def _skip_labels(diff: str) -> list[str]:
    mod = _load()
    return [lbl for lbl, _ in mod._scan_diff(diff).violations if "skip" in lbl]


def _run_hook(diff: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as fh:
        fh.write(diff)
        path = fh.name
    try:
        env = os.environ.copy()
        env["HOOK_TEST_DIFF"] = path
        return subprocess.run(
            [sys.executable, str(_CANONICAL)],
            env=env,
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(path)


class TestNetSkips(unittest.TestCase):
    def test_replaced_skip_one_for_one_is_not_flagged(self):
        # covers: GE-111f-1
        # angle: criterion
        """A skip replaced one-for-one (count unchanged) is not a weakening."""
        self.assertEqual(_skip_labels(_PROD + _REPLACED), [])
        result = _run_hook(_PROD + _REPLACED)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skip_in_brand_new_file_is_not_flagged(self):
        # covers: GE-111f-1
        # angle: criterion
        """A skip inside a newly added test file cannot weaken an existing test."""
        self.assertEqual(_skip_labels(_PROD + _NEW_FILE), [])
        result = _run_hook(_PROD + _NEW_FILE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skip_added_to_existing_test_still_blocks(self):
        # covers: GE-111f-1
        # angle: discrimination
        """Negative control: a net-new skip in an existing file still blocks."""
        self.assertEqual(_skip_labels(_PROD + _ADDED_TO_EXISTING), ["pytest.skip added"])
        result = _run_hook(_PROD + _ADDED_TO_EXISTING)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_two_added_one_removed_still_blocks(self):
        # covers: GE-111f-1
        # angle: boundary
        """Added count exceeding removed count (2 vs 1) is still a weakening."""
        diff = (
            "diff --git a/unit_tests/test_two.py b/unit_tests/test_two.py\n"
            "--- a/unit_tests/test_two.py\n"
            "+++ b/unit_tests/test_two.py\n"
            "@@ -1,4 +1,5 @@\n"
            " def test_two():\n"
            '-    pytest.skip("a")\n'
            '+    pytest.skip("b")\n'
            '+    pytest.skip("c")\n'
            "     assert True\n"
        )
        self.assertEqual(_skip_labels(_PROD + diff), ["pytest.skip added"])


if __name__ == "__main__":
    unittest.main()
