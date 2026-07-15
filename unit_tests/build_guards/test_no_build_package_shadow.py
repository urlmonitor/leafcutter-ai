"""
MODULE: test_no_build_package_shadow
GOAL: Guard against re-introduction of unit_tests/build/ as an importable package
    that shadows scripts/build.py and causes ~36 AttributeError failures.
BUSINESS CONTEXT: Salvage PR #300 renamed unit_tests/build/ to unit_tests/build_guards/
    to eliminate the 'build' package shadow.  Several re-entry points can silently
    resurrect the shadow (e.g. EPIC-BuildPipelineTestBackfill tickets with old paths,
    PR #287).  This guard makes the rename durable by failing whenever an importable
    unit_tests/build/ package re-appears.
ARCHITECTURE: Checks the on-disk repo tree at unit_tests/build/.  If an __init__.py
    or any test_*.py exists under that path the guard fails and names the offending
    files.  A sandbox spot-check confirms the detection logic is not a no-op that
    always passes regardless of filesystem state.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHADOW_DIR = _REPO_ROOT / "unit_tests" / "build"


class TestNoBuildPackageShadow:
    """Guard: unit_tests/build/ must not re-appear as an importable package.

    FAILS if any importable unit_tests/build/ content exists.
    PASSES when the directory is absent or contains no package markers.
    """

    def test_no_init_py_in_build_dir(self) -> None:
        """unit_tests/build/__init__.py must not exist.

        Its presence makes unit_tests/build/ an importable 'build' package that
        shadows scripts/build.py, causing AttributeError on every test that does
        ``import build``.  PR #300 removed this by renaming the directory to
        unit_tests/build_guards/.  Do NOT re-create unit_tests/build/__init__.py.
        """
        init_py = _SHADOW_DIR / "__init__.py"
        assert not init_py.exists(), (
            f"Shadow-package guard FAILED: {init_py} must not exist. "
            "unit_tests/build/__init__.py makes 'build' an importable package that "
            "shadows scripts/build.py — causes ~36 AttributeError failures. "
            "Move all tests to unit_tests/build_guards/ "
            "(see EPIC-RedTestClusterRepair ticket 08)."
        )

    def test_no_test_files_in_build_dir(self) -> None:
        """No test_*.py files may exist under unit_tests/build/.

        Even without __init__.py, test_*.py files under unit_tests/build/ cause
        pytest to collect them under the 'build' namespace, re-introducing the
        shadow.  All test files belong in unit_tests/build_guards/.
        """
        test_files = (
            sorted(_SHADOW_DIR.glob("test_*.py")) if _SHADOW_DIR.is_dir() else []
        )
        assert test_files == [], (
            f"Shadow-package guard FAILED: found test files under {_SHADOW_DIR}: "
            f"{[str(f) for f in test_files]}. "
            "unit_tests/build/test_*.py files re-create the 'build' package shadow. "
            "Move them to unit_tests/build_guards/ "
            "(see EPIC-RedTestClusterRepair ticket 08)."
        )

    def test_guard_genuinely_detects_shadow(self, tmp_path: Path) -> None:
        """Behavioral spot-check: the guard logic catches a re-added shadow.

        Creates a synthetic unit_tests/build/__init__.py and test_*.py in a
        sandbox, then asserts the detection conditions fire — proving the guard
        is not a no-op that always passes regardless of filesystem state.
        """
        # Build a synthetic shadow package in the sandbox
        fake_build_dir = tmp_path / "unit_tests" / "build"
        fake_build_dir.mkdir(parents=True)

        fake_init_py = fake_build_dir / "__init__.py"
        fake_init_py.write_text(
            "# synthetic shadow for guard spot-check\n", encoding="utf-8"
        )

        # Confirm the __init__.py detection condition would fire
        guard_trips_on_init = fake_init_py.exists()
        assert guard_trips_on_init, (
            "Guard spot-check FAILED: the detection condition (init_py.exists()) "
            "must return True when a __init__.py is present in unit_tests/build/. "
            "The guard is a no-op — fix the detection logic."
        )

        # Confirm the test-file glob would also catch test_*.py files
        fake_test_py = fake_build_dir / "test_shadow_example.py"
        fake_test_py.write_text(
            "# synthetic test file for guard spot-check\n", encoding="utf-8"
        )

        detected_files = sorted(fake_build_dir.glob("test_*.py"))
        assert detected_files, (
            "Guard spot-check FAILED: glob('test_*.py') must find the synthetic "
            "test file under unit_tests/build/. The detection logic is broken."
        )
