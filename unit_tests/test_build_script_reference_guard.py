"""
MODULE: test_build_script_reference_guard
GOAL: Unit tests for AC BP-900b-2 — the guard that cross-checks extracted
    script references against the deployable script manifest.

The guard function (to be implemented by python-coder) must:
  1. Accept a set of extracted script references and a set of deployed scripts.
  2. Mark every reference that matches a deployed script path as resolved.
  3. Mark every reference that does NOT match a deployed script path as broken.
  4. Return a list (or set) of broken references — zero or more items.

The guard must be importable from build_phases as cross_check_script_references,
and a helper get_deployable_scripts must also be importable from build_phases.

Until those functions exist these tests will fail with ImportError or
AttributeError, which is the intended RED state for test-writer hand-off.

AC coverage:
  - AC BP-900b-2: all three sub-criteria (resolved, broken, broken-list) are
    exercised by tests below.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


def _import_cross_check():
    """Lazily import cross_check_script_references from build_phases.

    This deferred import ensures each test fails individually with
    ImportError rather than blocking collection entirely.
    """
    from build_phases import cross_check_script_references  # type: ignore[attr-defined]
    return cross_check_script_references


def _import_get_deployable():
    """Lazily import get_deployable_scripts from build_phases."""
    from build_phases import get_deployable_scripts  # type: ignore[attr-defined]
    return get_deployable_scripts


class TestCrossCheckScriptReferencesBasic(unittest.TestCase):
    """AC BP-900b-2 — core contract: resolved vs broken classification."""

    def test_ac_bp900b2_matching_reference_is_resolved(self):
        # covers: UNKNOWN
        """AC BP-900b-2: every reference that matches a deployed script is marked resolved.

        Given extracted refs contain "scripts/ac_store/ac_prioritizer.py"
        And the deployable manifest contains "scripts/ac_store/ac_prioritizer.py"
        Then that reference must NOT appear in the broken list.
        """
        cross_check_script_references = _import_cross_check()

        refs = {"scripts/ac_store/ac_prioritizer.py"}
        deployed = {"scripts/ac_store/ac_prioritizer.py"}

        result = cross_check_script_references(refs=refs, deployed=deployed)

        # The broken list must be empty — the reference was resolved.
        broken = result.get("broken") if isinstance(result, dict) else result
        self.assertEqual(
            set(broken),
            set(),
            "A reference that matches a deployed script must not appear in broken list",
        )

    def test_ac_bp900b2_non_matching_reference_is_broken(self):
        # covers: UNKNOWN
        """AC BP-900b-2: every reference that does NOT match a deployed script is marked broken.

        Given extracted refs contain "scripts/missing_tool.py"
        And the deployable manifest does NOT contain "scripts/missing_tool.py"
        Then "scripts/missing_tool.py" must appear in the broken list.
        """
        cross_check_script_references = _import_cross_check()

        refs = {"scripts/missing_tool.py"}
        deployed = set()

        result = cross_check_script_references(refs=refs, deployed=deployed)

        broken = result.get("broken") if isinstance(result, dict) else result
        self.assertIn(
            "scripts/missing_tool.py",
            set(broken),
            "A reference absent from the deployed manifest must appear in the broken list",
        )

    def test_ac_bp900b2_guard_produces_broken_list(self):
        # covers: UNKNOWN
        """AC BP-900b-2: the guard produces a list of zero or more broken references.

        Given a mix of matching and non-matching references
        Then the return value contains a broken-reference iterable
        And only the non-matching references appear in it
        And the return value is not None.
        """
        cross_check_script_references = _import_cross_check()

        refs = {
            "scripts/ac_store/ac_prioritizer.py",    # deployed → resolved
            "scripts/goal_to_epic.py",               # deployed → resolved
            "scripts/unknown_script.py",             # not deployed → broken
            "scripts/another_missing.py",            # not deployed → broken
        }
        deployed = {
            "scripts/ac_store/ac_prioritizer.py",
            "scripts/goal_to_epic.py",
        }

        result = cross_check_script_references(refs=refs, deployed=deployed)

        self.assertIsNotNone(result, "guard must return a non-None result")

        broken = result.get("broken") if isinstance(result, dict) else result
        broken_set = set(broken)

        self.assertIn(
            "scripts/unknown_script.py",
            broken_set,
            "non-deployed script must appear in broken list",
        )
        self.assertIn(
            "scripts/another_missing.py",
            broken_set,
            "second non-deployed script must appear in broken list",
        )
        self.assertNotIn(
            "scripts/ac_store/ac_prioritizer.py",
            broken_set,
            "deployed script must NOT appear in broken list",
        )
        self.assertNotIn(
            "scripts/goal_to_epic.py",
            broken_set,
            "second deployed script must NOT appear in broken list",
        )

    def test_ac_bp900b2_empty_refs_produces_empty_broken_list(self):
        # covers: UNKNOWN
        """AC BP-900b-2: zero references → zero broken references.

        Given extracted refs is the empty set
        Then the broken list must also be empty.
        """
        cross_check_script_references = _import_cross_check()

        result = cross_check_script_references(refs=set(), deployed=set())

        broken = result.get("broken") if isinstance(result, dict) else result
        self.assertEqual(
            set(broken),
            set(),
            "empty refs must produce empty broken list",
        )

    def test_ac_bp900b2_all_refs_deployed_zero_broken(self):
        # covers: UNKNOWN
        """AC BP-900b-2: when all references are deployed, broken list is empty.

        Given all extracted refs are present in the deployable manifest
        Then the guard produces zero broken references.
        """
        cross_check_script_references = _import_cross_check()

        refs = {
            "scripts/ac_store/ac_prioritizer.py",
            "scripts/ac_store/generate_ticket_from_ac.py",
            "scripts/goal_to_epic.py",
        }
        deployed = refs.copy()

        result = cross_check_script_references(refs=refs, deployed=deployed)

        broken = result.get("broken") if isinstance(result, dict) else result
        self.assertEqual(
            set(broken),
            set(),
            "when all refs are deployed the broken list must be empty",
        )


class TestCrossCheckScriptReferencesWithDeployManifest(unittest.TestCase):
    """AC BP-900b-2 — deployable manifest derivation from the target directory.

    Verifies that get_deployable_scripts() returns the correct set of scripts
    that build.py will deploy:
      - scripts from build_ac_store_scripts (→ scripts/ac_store/*.py)
      - scripts from build_standalone_scripts (→ scripts/goal_to_epic.py etc.)
      - scripts from build_feedback (→ scripts/feedback/*.py)

    The function inspects what has actually been placed in
    {target}/.leafcutter/scripts/ and {target}/scripts/ by the build phases.
    """

    def test_ac_bp900b2_deployable_manifest_includes_ac_store_scripts(self):
        # covers: UNKNOWN
        """AC BP-900b-2: the deployable manifest includes ac_store scripts.

        The guard compares against scripts that build.py will deploy.
        The deployed set must include the ac_store scripts when they exist
        in {target}/.leafcutter/scripts/ac_store/ or {target}/scripts/ac_store/.
        """
        get_deployable_scripts = _import_get_deployable()

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            # Simulate deployed ac_store scripts (canonical .leafcutter/ location)
            ac_store_dir = target / ".leafcutter" / "scripts" / "ac_store"
            ac_store_dir.mkdir(parents=True)
            (ac_store_dir / "ac_prioritizer.py").write_text("# stub", encoding="utf-8")
            (ac_store_dir / "generate_ticket_from_ac.py").write_text("# stub", encoding="utf-8")

            deployed = get_deployable_scripts(target)

        self.assertIn(
            "scripts/ac_store/ac_prioritizer.py",
            deployed,
            "deployable manifest must include scripts/ac_store/ac_prioritizer.py",
        )
        self.assertIn(
            "scripts/ac_store/generate_ticket_from_ac.py",
            deployed,
            "deployable manifest must include scripts/ac_store/generate_ticket_from_ac.py",
        )

    def test_ac_bp900b2_deployable_manifest_includes_standalone_scripts(self):
        # covers: UNKNOWN
        """AC BP-900b-2: the deployable manifest includes standalone scripts.

        The guard must recognise scripts deployed by build_standalone_scripts
        (e.g. scripts/goal_to_epic.py) as part of the deployable manifest.
        """
        get_deployable_scripts = _import_get_deployable()

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            # Simulate standalone scripts at target/scripts/ (shim location)
            scripts_dir = target / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "goal_to_epic.py").write_text("# stub", encoding="utf-8")
            (scripts_dir / "build_ac_mode_detection.py").write_text("# stub", encoding="utf-8")

            deployed = get_deployable_scripts(target)

        self.assertIn(
            "scripts/goal_to_epic.py",
            deployed,
            "deployable manifest must include scripts/goal_to_epic.py",
        )

    def test_ac_bp900b2_deployable_manifest_empty_when_no_scripts(self):
        # covers: UNKNOWN
        """AC BP-900b-2: when target has no deployed scripts, manifest is empty.

        Given a target directory with no scripts deployed
        Then get_deployable_scripts returns an empty set (or collection).
        """
        get_deployable_scripts = _import_get_deployable()

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            deployed = get_deployable_scripts(target)

        self.assertEqual(
            len(deployed),
            0,
            "no scripts deployed → empty deployable manifest",
        )


class TestCrossCheckScriptReferencesReturnShape(unittest.TestCase):
    """Verify the return value shape of cross_check_script_references."""

    def test_ac_bp900b2_return_value_is_not_none(self):
        # covers: UNKNOWN
        """AC BP-900b-2: guard always returns a non-None value."""
        cross_check_script_references = _import_cross_check()

        result = cross_check_script_references(
            refs={"scripts/anything.py"},
            deployed=set(),
        )
        self.assertIsNotNone(result)

    def test_ac_bp900b2_broken_references_iterable(self):
        # covers: UNKNOWN
        """AC BP-900b-2: the broken references result is iterable (list or set)."""
        cross_check_script_references = _import_cross_check()

        result = cross_check_script_references(
            refs={"scripts/missing.py"},
            deployed=set(),
        )
        broken = result.get("broken") if isinstance(result, dict) else result
        # Must be iterable — not None, not a non-iterable scalar.
        try:
            _ = iter(broken)
        except TypeError:
            self.fail(
                "broken references result must be iterable (list or set), "
                f"got: {type(broken)}"
            )


if __name__ == "__main__":
    unittest.main()
