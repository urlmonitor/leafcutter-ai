"""
MODULE: test_validate_ac
GOAL: Regression tests for is_package_surface_ac classification in
    scripts/ac_store/validate_ac.py.  Covers the kebab scalar fix (build-pipeline)
    and the components-list fallback (build_pipeline in graph-id list).
BUSINESS CONTEXT: build-pipeline ACs carry the KEBAB scalar component field
    (``component: build-pipeline``), which was previously NOT matched by
    PACKAGE_SURFACE_COMPONENTS (the set only contained the underscore form
    ``build_pipeline``).  This caused the BO-2000d structured-spec gate to be
    silently inert for every build-pipeline python-coder AC, observed live on
    BP-1100f-4 and BP-1100f-5.
ARCHITECTURE: Unit tests for the pure classification function; no I/O.
    Exercises is_package_surface_ac directly with synthetic dicts.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VALIDATE_AC_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_VALIDATE_AC_DIR))

from validate_ac import is_package_surface_ac  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ac(**kwargs) -> dict:
    """Return a minimal AC dict with fields from kwargs."""
    return dict(kwargs)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestKebabComponentMatchesBuildPipeline(unittest.TestCase):
    """Regression: component: "build-pipeline" (kebab) must match.

    Before the fix PACKAGE_SURFACE_COMPONENTS only contained the underscore
    form ``build_pipeline``.  ACs with the kebab scalar were silently excluded
    and the BO-2000d gate was inert for all BP-* tickets.
    """

    def test_kebab_component_python_coder_is_true(self) -> None:
        """component: build-pipeline + assigned_agent: python-coder → True."""
        ac = _make_ac(
            id="BP-1100f-4",
            component="build-pipeline",
            assigned_agent="python-coder",
        )
        self.assertTrue(
            is_package_surface_ac(ac),
            "is_package_surface_ac must return True for component='build-pipeline' "
            "with assigned_agent='python-coder'. This is the regression case — "
            "the kebab spelling was absent from PACKAGE_SURFACE_COMPONENTS before the fix.",
        )

    def test_underscore_component_python_coder_still_true(self) -> None:
        """component: build_pipeline (underscore, pre-existing) still matches."""
        ac = _make_ac(
            id="BO-999a-1",
            component="build_pipeline",
            assigned_agent="python-coder",
        )
        self.assertTrue(
            is_package_surface_ac(ac),
            "is_package_surface_ac must still return True for component='build_pipeline' "
            "(underscore form) — the pre-existing behaviour must not regress.",
        )

    def test_build_orchestration_component_python_coder_is_true(self) -> None:
        """component: build-orchestration + python-coder → True (unchanged)."""
        ac = _make_ac(
            id="BO-1a-1",
            component="build-orchestration",
            assigned_agent="python-coder",
        )
        self.assertTrue(
            is_package_surface_ac(ac),
            "component='build-orchestration' must still match (pre-existing behaviour).",
        )


class TestComponentsListFallback(unittest.TestCase):
    """New: components list (graph ids) provides a secondary match path.

    When the scalar ``component`` field is absent or non-matching, any entry
    in the ``components`` list that is in PACKAGE_SURFACE_COMPONENTS must
    be sufficient to classify the AC as package-surface, given python-coder.
    """

    def test_components_list_build_pipeline_python_coder_is_true(self) -> None:
        """components: [build_pipeline] (list) + python-coder, no scalar → True."""
        ac = _make_ac(
            id="BP-999b-1",
            assigned_agent="python-coder",
            components=["build_pipeline"],
            # No scalar 'component' field
        )
        self.assertTrue(
            is_package_surface_ac(ac),
            "is_package_surface_ac must return True when assigned_agent='python-coder' "
            "and 'build_pipeline' appears in the components list, even when the scalar "
            "component field is absent.",
        )

    def test_components_list_kebab_build_pipeline_python_coder_is_true(self) -> None:
        """components: [build-pipeline] (kebab in list) + python-coder → True."""
        ac = _make_ac(
            id="BP-999b-2",
            assigned_agent="python-coder",
            components=["build-pipeline"],
        )
        self.assertTrue(
            is_package_surface_ac(ac),
            "is_package_surface_ac must return True when 'build-pipeline' appears in "
            "the components list with assigned_agent='python-coder'.",
        )

    def test_components_list_non_package_component_python_coder_is_false(self) -> None:
        """components list with non-package components + python-coder → False."""
        ac = _make_ac(
            id="DOC-1a-1",
            assigned_agent="python-coder",
            components=["documentation", "agent_templates"],
        )
        self.assertFalse(
            is_package_surface_ac(ac),
            "is_package_surface_ac must return False when the components list "
            "contains no package-surface component, even with python-coder.",
        )

    def test_scalar_component_wins_when_both_present(self) -> None:
        """scalar component non-matching + matching components list → True (list wins)."""
        ac = _make_ac(
            id="BP-999c-1",
            assigned_agent="python-coder",
            component="documentation",  # non-matching scalar
            components=["build_pipeline"],  # matching list
        )
        self.assertTrue(
            is_package_surface_ac(ac),
            "When the scalar component does not match but the components list "
            "contains a package-surface component, must return True.",
        )


class TestNonPackageComponentOrNonCoderReturnsFalse(unittest.TestCase):
    """Unchanged behaviour: non-package component or non-python-coder → False."""

    def test_non_package_component_python_coder_is_false(self) -> None:
        """component: 'documentation' + python-coder → False."""
        ac = _make_ac(
            id="DOC-2a-1",
            component="documentation",
            assigned_agent="python-coder",
        )
        self.assertFalse(
            is_package_surface_ac(ac),
            "A non-package-surface component with python-coder must return False.",
        )

    def test_non_python_coder_agent_build_pipeline_is_false(self) -> None:
        """component: build-pipeline + documentation-expert → False."""
        ac = _make_ac(
            id="DOC-3a-1",
            component="build-pipeline",
            assigned_agent="documentation-expert",
        )
        self.assertFalse(
            is_package_surface_ac(ac),
            "assigned_agent != 'python-coder' must return False regardless of component.",
        )

    def test_non_python_coder_with_components_list_is_false(self) -> None:
        """components: [build_pipeline] + documentation-expert → False."""
        ac = _make_ac(
            id="DOC-4a-1",
            assigned_agent="documentation-expert",
            components=["build_pipeline"],
        )
        self.assertFalse(
            is_package_surface_ac(ac),
            "assigned_agent != 'python-coder' must return False even when the "
            "components list contains a package-surface component.",
        )

    def test_empty_ac_is_false(self) -> None:
        """Empty dict → False (no assigned_agent, no component)."""
        self.assertFalse(
            is_package_surface_ac({}),
            "An empty dict must return False.",
        )


if __name__ == "__main__":
    unittest.main()
