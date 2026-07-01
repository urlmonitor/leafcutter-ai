"""
MODULE: test_check_ac_schema_index_exclusion
GOAL: Regression test asserting that docs/acceptance-criteria/index.yaml is
    excluded from the set returned by _get_staged_ac_paths(), preventing the
    component registry from being validated as an AC YAML file.
BUSINESS CONTEXT: index.yaml is the component registry (id/prefix/description/
    owner), not an acceptance-criterion file. Staging it previously caused
    check_ac_schema.py to reject it with "'id' is a required property" because
    the staged-path collector did not apply the same exclusion guard that
    _find_ac_files() already had. This test locks in the fix so the bug cannot
    regress.
ARCHITECTURE: Tests invoke _get_staged_ac_paths() directly via the HOOK_TEST_STAGED_FILES
    env-var seam so no real git process is needed. A second subprocess test
    verifies the CLI exit-code contract when index.yaml is the only staged file.
    All tests complete in < 5 seconds and require no network or DB access.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module import — mirrors the pattern in test_check_ac_schema_git_batch_perf.py
# ---------------------------------------------------------------------------
# File layout:  unit_tests/commit_guardian/test_check_ac_schema_index_exclusion.py
# Hook is at:   templates/scripts/commit_guardian/check_ac_schema.py
# parents[0] = unit_tests/commit_guardian/
# parents[1] = unit_tests/
# parents[2] = <repo-root>/
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_HOOK_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_HOOK_SCRIPT = _HOOK_DIR / "check_ac_schema.py"

if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

try:
    import check_ac_schema as _hook_mod
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except ImportError as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip the decorated test if check_ac_schema failed to import.

    Args:
        func: Test method to conditionally skip.

    Returns:
        Decorated test method, possibly wrapped in unittest.skip.
    """
    if not _IMPORT_OK:
        return unittest.skip(f"check_ac_schema not importable: {_IMPORT_ERROR}")(func)
    return func


# ---------------------------------------------------------------------------
# Component registry (index.yaml) content used across tests
# ---------------------------------------------------------------------------

_INDEX_YAML_CONTENT = """\
components:
  - id: ac-store
    prefix: ACS
    description: AC store and schema validation hooks
    owner: python-coder
  - id: finalize
    prefix: FIN
    description: Feature finalization pipeline
    owner: python-coder
"""


# ---------------------------------------------------------------------------
# Unit tests — _get_staged_ac_paths() internal function
# ---------------------------------------------------------------------------


class TestIndexYamlExcludedFromStagedPaths(unittest.TestCase):
    """_get_staged_ac_paths() must never return index.yaml regardless of env seam."""

    @_requires_import
    def test_index_yaml_excluded_via_test_seam(self) -> None:
        """index.yaml is excluded when HOOK_TEST_STAGED_FILES lists it directly.

        This exercises the HOOK_TEST_STAGED_FILES branch of _get_staged_ac_paths().
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True, exist_ok=True)

            index_path = ac_dir / "index.yaml"
            index_path.write_text(_INDEX_YAML_CONTENT, encoding="utf-8")

            env_before = os.environ.copy()
            os.environ["HOOK_TEST_STAGED_FILES"] = str(index_path)
            try:
                result = _hook_mod._get_staged_ac_paths(root)
            finally:
                # Restore environment whether or not the call raised.
                os.environ.clear()
                os.environ.update(env_before)

        self.assertEqual(
            result,
            [],
            msg=(
                "index.yaml must be excluded from staged paths but was returned: "
                f"{result}"
            ),
        )

    @_requires_import
    def test_index_yaml_excluded_alongside_real_ac_file(self) -> None:
        """index.yaml is excluded even when a real AC file is also staged.

        Verifies the exclusion is per-file, not a blanket no-op when index
        is the only entry.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True, exist_ok=True)

            index_path = ac_dir / "index.yaml"
            index_path.write_text(_INDEX_YAML_CONTENT, encoding="utf-8")

            real_ac = ac_dir / "ACS-001.yaml"
            real_ac.write_text(
                "id: ACS-001\ntitle: test\ncomponent: ac-store\nstatus: active\n"
                "criteria: |\n  Given X\n  When Y\n  Then Z\n",
                encoding="utf-8",
            )

            env_before = os.environ.copy()
            os.environ["HOOK_TEST_STAGED_FILES"] = (
                os.pathsep.join([str(index_path), str(real_ac)])
            )
            try:
                result = _hook_mod._get_staged_ac_paths(root)
            finally:
                os.environ.clear()
                os.environ.update(env_before)

        result_names = [p.name for p in result]
        self.assertNotIn(
            "index.yaml",
            result_names,
            msg="index.yaml must not appear in the staged paths list",
        )
        self.assertIn(
            "ACS-001.yaml",
            result_names,
            msg="ACS-001.yaml must still be included in the staged paths list",
        )

    @_requires_import
    def test_non_index_yaml_files_are_not_excluded(self) -> None:
        """Files whose name is not exactly 'index.yaml' are not excluded.

        Guards against an over-broad exclusion (e.g. any file containing
        'index' in its name).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True, exist_ok=True)

            real_ac = ac_dir / "ACS-index-001.yaml"
            real_ac.write_text(
                "id: ACS-index-001\ntitle: test\ncomponent: ac-store\nstatus: active\n"
                "criteria: |\n  Given X\n  When Y\n  Then Z\n",
                encoding="utf-8",
            )

            env_before = os.environ.copy()
            os.environ["HOOK_TEST_STAGED_FILES"] = str(real_ac)
            try:
                result = _hook_mod._get_staged_ac_paths(root)
            finally:
                os.environ.clear()
                os.environ.update(env_before)

        result_names = [p.name for p in result]
        self.assertIn(
            "ACS-index-001.yaml",
            result_names,
            msg="ACS-index-001.yaml must NOT be excluded — only 'index.yaml' is excluded",
        )


# ---------------------------------------------------------------------------
# CLI integration test — subprocess exit-code contract
# ---------------------------------------------------------------------------


class TestIndexYamlDoesNotBlockHook(unittest.TestCase):
    """Hook exits 0 when only index.yaml is staged (it should be skipped, not validated)."""

    def test_only_index_yaml_staged_exits_zero(self) -> None:
        """Staging index.yaml alone must produce exit code 0, not 1.

        Reproduces the original bug: without the fix, the hook would validate
        index.yaml as an AC file and exit 1 with "'id' is a required property"
        or "{'id': 'ac-store', ...} is not of type 'string'".
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True, exist_ok=True)

            index_path = ac_dir / "index.yaml"
            index_path.write_text(_INDEX_YAML_CONTENT, encoding="utf-8")

            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            env["HOOK_TEST_STAGED_FILES"] = str(index_path)
            # Suppress Phase 2 git calls — we are not testing that here.
            env["HOOK_NO_GIT"] = "1"
            # Unset HOOK_TEST_STAGED_FILES does not leak across this call.

            try:
                result = subprocess.run(
                    [sys.executable, str(_HOOK_SCRIPT)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (subprocess.SubprocessError, OSError) as exc:
                self.fail(f"Hook subprocess failed to launch: {exc}")

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Hook must exit 0 when only index.yaml is staged. "
                f"stderr: {result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
