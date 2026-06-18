"""
MODULE: test_build_precommit
GOAL: Unit tests for hook script referential integrity check in build_precommit.py.
BUSINESS CONTEXT: Ensures that build_precommit_config() emits a WARNING for every
    registered hook whose .py script is absent at the canonical cg_dir path, and
    remains silent when all scripts are present. Covers AC-1, AC-2, AC-4, AC-5.
ARCHITECTURE: Tests directly invoke the helper function _check_hook_script_integrity()
    which will be extracted from the integrity-check loop in build_precommit_config().
    This helper takes (hooks: list[dict], cg_dir: Path) and emits _log.warning for
    any missing scripts.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# The module under test — may not exist yet (TDD red-baseline phase).
# _check_hook_script_integrity is the helper function to be implemented.
try:
    import scripts.build_precommit as _bpm
    _IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    _bpm = None
    _IMPORT_OK = False


def _make_hook_entry(script_name: str) -> dict:
    """Build a synthetic hook dict referencing the given script filename."""
    return {
        "id": f"check-{script_name.replace('.py', '')}",
        "name": f"Check {script_name}",
        "entry": (
            f"python {{{{config.output_root}}}}/scripts/commit_guardian/run_hook.py"
            f" {{{{config.output_root}}}}/scripts/commit_guardian/{script_name}"
        ),
        "language": "system",
        "stages": ["pre-commit"],
        "pass_filenames": False,
    }


class TestHookScriptIntegrityCheckWarnOnMissing(unittest.TestCase):
    """AC-4: Missing hook script triggers a warning, build does not raise."""

    def test_hook_script_integrity_check_warns_on_missing(self):
        # covers: UNKNOWN
        """AC-4: Given a hooks_manifest referencing check_missing.py and a cg_dir
        that does NOT contain it, the integrity check emits a warning and does not raise."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.build_precommit. "
                "Implement the module (AC-1) so tests can import it."
            )
        if not hasattr(_bpm, "_check_hook_script_integrity"):
            self.fail(
                "AttributeError: scripts.build_precommit does not expose "
                "_check_hook_script_integrity(). "
                "Extract the integrity-check loop as this helper function (AC-1, AC-4)."
            )

        with tempfile.TemporaryDirectory() as tmp:
            cg_dir = Path(tmp)
            # check_missing.py is NOT present in cg_dir
            # (run_hook.py is present — but the referenced script is absent)
            (cg_dir / "run_hook.py").write_text("# run hook", encoding="utf-8")

            hooks = [_make_hook_entry("check_missing.py")]

            with patch.object(_bpm, "_log") as mock_log:
                _bpm._check_hook_script_integrity(hooks, cg_dir)

            mock_log.warning.assert_called()
            all_warning_args = " ".join(
                str(call) for call in mock_log.warning.call_args_list
            )
            self.assertIn("check_missing.py", all_warning_args,
                          "Warning must mention the missing script filename.")


class TestHookScriptIntegrityCheckSilentWhenAllPresent(unittest.TestCase):
    """AC-5: No warning when all hook scripts are present at cg_dir."""

    def test_hook_script_integrity_check_silent_when_all_present(self):
        # covers: UNKNOWN
        """AC-5: Given a cg_dir that contains all referenced scripts,
        no integrity-check warning is emitted."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.build_precommit. "
                "Implement the module (AC-1) so tests can import it."
            )
        if not hasattr(_bpm, "_check_hook_script_integrity"):
            self.fail(
                "AttributeError: scripts.build_precommit does not expose "
                "_check_hook_script_integrity(). "
                "Extract the integrity-check loop as this helper function (AC-1, AC-5)."
            )

        with tempfile.TemporaryDirectory() as tmp:
            cg_dir = Path(tmp)
            # Both run_hook.py AND check_present.py are present
            (cg_dir / "run_hook.py").write_text("# run hook", encoding="utf-8")
            (cg_dir / "check_present.py").write_text("# hook script", encoding="utf-8")

            hooks = [_make_hook_entry("check_present.py")]

            with patch.object(_bpm, "_log") as mock_log:
                _bpm._check_hook_script_integrity(hooks, cg_dir)

            # No warning should mention check_present.py (it exists)
            for call in mock_log.warning.call_args_list:
                self.assertNotIn(
                    "check_present.py", str(call),
                    "No integrity warning should be emitted when the script is present.",
                )


if __name__ == "__main__":
    unittest.main()
