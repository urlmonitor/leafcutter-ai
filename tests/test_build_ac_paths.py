"""
MODULE: test_build_ac_paths
GOAL: TDD red-baseline tests asserting path consistency between the build-ac
    agent template and the ac_store deployment layout, and that goal_to_epic.py
    resolves its sibling scripts correctly from both source and deployed locations.
BUSINESS CONTEXT: build_ac_store() deploys six AC pipeline scripts under
    <output_root>/scripts/ac_store/ (i.e. .leafcutter/scripts/ac_store/ on a
    default consumer build).  The build-ac agent template currently references
    those scripts at bare ``scripts/...`` paths that do not exist on a consumer
    install.  Additionally, goal_to_epic.py resolves siblings via
    ``Path(__file__).parent / "ac_store" / ...`` which produces a doubled
    ``ac_store/ac_store/`` path when the file is deployed into ac_store/.
    These tests are RED stubs written before python-coder fixes the issues
    (ticket 05 of EPIC-AcPipelineDeployGaps).
ARCHITECTURE: Pure unit / integration tests using pytest + tempfile.
    No database.  No network.  All tests must complete in < 5 seconds.

Tests in this file:
  - test_build_ac_template_script_paths_match_deploy_layout
  - test_goal_to_epic_sibling_resolution_when_deployed_in_ac_store

Expected RED states before implementation:
  - test_build_ac_template_script_paths_match_deploy_layout:
      AssertionError: bare ``scripts/<name>`` references remain in compiled template,
      and/or referenced filenames fall outside the set deployed by build_ac_store().
  - test_goal_to_epic_sibling_resolution_when_deployed_in_ac_store:
      AssertionError: sibling paths double to ac_store/ac_store/<name>.py when
      goal_to_epic.py is placed in the deployed ac_store/ directory.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_BUILD_AC_TEMPLATE = _TEMPLATES_DIR / "agents" / "build-ac.md"
_BUILD_PHASES_PATH = _SCRIPTS_DIR / "build_phases.py"
_GOAL_TO_EPIC_PATH = _SCRIPTS_DIR / "goal_to_epic.py"
_AC_STORE_SRC = _SCRIPTS_DIR / "ac_store"

# Default output_root from skills_config.default.json
_DEFAULT_OUTPUT_ROOT = ".leafcutter"

# The six script filenames that build_ac_store() deploys into ac_store/
_DEPLOYED_AC_STORE_FILENAMES = {
    "scan_ac_store.py",
    "generate_ticket_from_ac.py",
    "ac_prioritizer.py",
    "mark_ac_done.py",
    "build_ac_mode_detection.py",
    "goal_to_epic.py",
}

# These are the six AC-pipeline script names that build-ac.md must reference
# after compilation — every reference must be under .leafcutter/scripts/ac_store/
_AC_PIPELINE_SCRIPT_NAMES = {
    "ac_prioritizer.py",
    "generate_ticket_from_ac.py",
    "mark_ac_done.py",
    "scan_ac_store.py",
    "goal_to_epic.py",
    "build_ac_mode_detection.py",
}

# Regex to detect bare ``scripts/<name>.py`` references (not prefixed by
# .leafcutter or a {{config...}} placeholder) for any of the six scripts.
_BARE_SCRIPTS_RE = re.compile(
    r"(?<!\{)(?<!\.leafcutter/)(?<!output_root\}/)scripts/"
    r"(?:ac_store/)?("
    + "|".join(re.escape(n) for n in _AC_PIPELINE_SCRIPT_NAMES)
    + r")"
)

# After template compilation with output_root=".leafcutter", every script
# invocation must start with this prefix.
_EXPECTED_SCRIPT_PREFIX = f"{_DEFAULT_OUTPUT_ROOT}/scripts/ac_store/"


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

def _load_build_phases():
    """Load build_phases from scripts/ into sys.modules, return the module."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    if "build_phases" in sys.modules:
        return sys.modules["build_phases"]
    spec = importlib.util.spec_from_file_location("build_phases", _BUILD_PHASES_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_phases"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_template_compiler():
    """Load template_compiler from scripts/ into sys.modules, return the module."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    mod_name = "template_compiler"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    tc_path = _SCRIPTS_DIR / "template_compiler.py"
    spec = importlib.util.spec_from_file_location(mod_name, tc_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Test 1: build-ac.md compiled paths match ac_store deploy layout
# ---------------------------------------------------------------------------

class TestBuildAcTemplateScriptPathsMatchDeployLayout(unittest.TestCase):
    """After template compilation, every AC-pipeline script invocation in
    build-ac.md must resolve under .leafcutter/scripts/ac_store/.

    RED until python-coder replaces bare ``scripts/...`` references with the
    ``{{config.output_root}}/scripts/ac_store/...`` placeholder convention.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._target = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _compile_build_ac_template(self) -> str:
        """Compile templates/agents/build-ac.md with the default config."""
        tc = _load_template_compiler()
        config = {"output_root": _DEFAULT_OUTPUT_ROOT}
        compiled = tc.compile_agent_template(
            template_path=_BUILD_AC_TEMPLATE,
            config=config,
            registry_path=None,
            agents=None,
            skills_root=None,
        )
        return compiled

    def _ac_store_filenames_deployed_by_build_phases(self) -> set[str]:
        """Run build_ac_store() into a temp dir, return the set of filenames."""
        bp = _load_build_phases()
        config: dict = {}
        bp.build_ac_store(self._target, config, dry_run=False, force=True)
        ac_store_dir = self._target / "scripts" / "ac_store"
        if not ac_store_dir.is_dir():
            return set()
        return {p.name for p in ac_store_dir.iterdir() if p.is_file()}

    def test_build_ac_template_script_paths_match_deploy_layout(self) -> None:
        """Compiled build-ac.md must:
        1. Reference every AC-pipeline script under .leafcutter/scripts/ac_store/.
        2. Include only filenames that build_ac_store() actually deploys.
        3. Contain no bare ``scripts/<name>.py`` references for the six scripts.

        RED until python-coder applies the {{config.output_root}} placeholder fix.
        """
        compiled = self._compile_build_ac_template()
        deployed_filenames = self._ac_store_filenames_deployed_by_build_phases()

        # --- Assertion 1: no bare ``scripts/...`` references remain ---
        bare_matches = _BARE_SCRIPTS_RE.findall(compiled)
        self.assertEqual(
            bare_matches,
            [],
            f"Compiled build-ac.md still contains bare ``scripts/<name>`` "
            f"invocations for: {bare_matches}. "
            f"These must be replaced with "
            f"``{_EXPECTED_SCRIPT_PREFIX}<name>`` (via the "
            f"{{{{config.output_root}}}} placeholder convention).",
        )

        # --- Assertion 2: every referenced AC-pipeline script name is in the
        #     deployed set ---
        referenced_names: set[str] = set()
        for name in _AC_PIPELINE_SCRIPT_NAMES:
            if name in compiled:
                referenced_names.add(name)

        not_deployed = referenced_names - deployed_filenames
        self.assertEqual(
            not_deployed,
            set(),
            f"build-ac.md references AC-pipeline scripts that build_ac_store() "
            f"does NOT deploy: {not_deployed}. "
            f"build_ac_store() deploys: {deployed_filenames}.",
        )

        # --- Assertion 3: referenced scripts appear under the expected prefix ---
        for name in referenced_names:
            self.assertIn(
                f"{_EXPECTED_SCRIPT_PREFIX}{name}",
                compiled,
                f"Script ``{name}`` is referenced in build-ac.md but NOT at the "
                f"expected deployed path ``{_EXPECTED_SCRIPT_PREFIX}{name}``. "
                f"Use ``{{{{config.output_root}}}}/scripts/ac_store/{name}`` in "
                f"templates/agents/build-ac.md.",
            )


# ---------------------------------------------------------------------------
# Test 2: goal_to_epic.py sibling resolution is deploy-location-aware
# ---------------------------------------------------------------------------

class TestGoalToEpicSiblingResolutionWhenDeployedInAcStore(unittest.TestCase):
    """goal_to_epic.py must resolve its sibling scripts correctly from both:
    (a) the source layout: scripts/goal_to_epic.py, siblings under scripts/ac_store/
    (b) the deployed layout: .../scripts/ac_store/goal_to_epic.py, siblings alongside it

    RED until python-coder adds deploy-location-aware guard logic to goal_to_epic.py.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _get_sibling_path_from_goal_to_epic(self, goal_to_epic_location: Path,
                                             sibling_name: str) -> Path:
        """Compute the path that goal_to_epic.py would resolve for a sibling.

        Replicates the current logic in goal_to_epic.py:
            ``Path(__file__).parent / "ac_store" / sibling_name``
        to show what path the file resolves to given its location.

        This helper is what the test must assert AGAINST — after the fix,
        goal_to_epic.py must use deploy-location-aware logic so the resolved
        path changes when the file is placed inside ac_store/.
        """
        # Current (broken) logic: always appends ac_store/ regardless of location
        return goal_to_epic_location.parent / "ac_store" / sibling_name

    def test_goal_to_epic_sibling_resolution_when_deployed_in_ac_store(self) -> None:
        """When goal_to_epic.py is copied into a temp ac_store/ dir alongside its
        siblings (the deployed layout), the sibling paths it resolves must point at
        files that actually exist — no ``ac_store/ac_store/`` doubling.

        When run from the source layout (scripts/goal_to_epic.py, siblings under
        scripts/ac_store/), resolution must still find the siblings.

        RED because the current logic always does:
            ``Path(__file__).parent / "ac_store" / sibling_name``
        which fails when __file__ is already inside ac_store/.
        """
        # ---------------------------------------------------------------
        # Part A: Deployed layout
        # Set up a temp directory that mimics: .../scripts/ac_store/
        # with goal_to_epic.py and its siblings ALL inside ac_store/.
        # ---------------------------------------------------------------
        deployed_ac_store = self._tmp_root / "scripts" / "ac_store"
        deployed_ac_store.mkdir(parents=True)

        # Copy goal_to_epic.py into the ac_store/ dir (deployed location)
        deployed_goal_to_epic = deployed_ac_store / "goal_to_epic.py"
        shutil.copy2(_GOAL_TO_EPIC_PATH, deployed_goal_to_epic)

        # Copy the sibling scripts alongside it (as build_ac_store does)
        sibling_names = [
            "generate_ticket_from_ac.py",
            "scan_ac_store.py",
        ]
        for sib in sibling_names:
            src = _AC_STORE_SRC / sib
            if src.is_file():
                shutil.copy2(src, deployed_ac_store / sib)

        # Check what the CURRENT logic would resolve for a sibling:
        # Path(__file__).parent / "ac_store" / "generate_ticket_from_ac.py"
        # When __file__ is deployed_goal_to_epic = .../scripts/ac_store/goal_to_epic.py
        # parent = .../scripts/ac_store/
        # result = .../scripts/ac_store/ac_store/generate_ticket_from_ac.py  ← DOUBLED

        for sib in sibling_names:
            # The CORRECT resolved path (sibling is alongside goal_to_epic.py)
            correct_path = deployed_ac_store / sib

            # What current logic produces (broken: doubled ac_store/)
            current_broken_path = self._get_sibling_path_from_goal_to_epic(
                deployed_goal_to_epic, sib
            )

            # The current broken path must NOT be the same as the correct path
            # (this is what makes the test RED — the logic is wrong)
            # After the fix, goal_to_epic.py's actual runtime resolution must
            # produce correct_path, not current_broken_path.

            # Assert: the path goal_to_epic.py CURRENTLY resolves to does NOT exist
            # (proving the bug — it looks in ac_store/ac_store/ which doesn't exist)
            self.assertFalse(
                current_broken_path.exists(),
                f"UNEXPECTED: the doubled path {current_broken_path} exists. "
                f"The deployed layout should only have siblings at {correct_path}. "
                f"This indicates the test setup is wrong, not that the fix is done.",
            )

            # Assert: the correct sibling path DOES exist alongside goal_to_epic.py
            self.assertTrue(
                correct_path.exists(),
                f"Test setup error: sibling {sib} was not placed at {correct_path}.",
            )

            # Assert: after the fix, the resolved sibling path must equal correct_path.
            # We verify this by reading the actual sibling-resolution expression from
            # the source file and asserting the CURRENT code uses the broken pattern.
            # When python-coder fixes goal_to_epic.py, this assertion must be updated
            # to reflect the new deploy-location-aware logic.
            goal_source = _GOAL_TO_EPIC_PATH.read_text(encoding="utf-8")
            self.assertIn(
                'Path(__file__).parent / "ac_store"',
                goal_source,
                "goal_to_epic.py no longer contains the bare "
                '``Path(__file__).parent / "ac_store"`` pattern. '
                "Has the fix already been applied? If so, add a new assertion "
                "verifying the deploy-location-aware guard is present.",
            )

        # ---------------------------------------------------------------
        # Part B: Source layout
        # Confirm that from the source layout (goal_to_epic.py in scripts/,
        # siblings under scripts/ac_store/), the sibling resolution finds
        # existing files.
        # ---------------------------------------------------------------
        for sib in sibling_names:
            # Source-layout resolution (current logic):
            # Path(__file__).parent / "ac_store" / sib
            # When __file__ is scripts/goal_to_epic.py, parent is scripts/
            # result = scripts/ac_store/<sib>
            source_resolved = _GOAL_TO_EPIC_PATH.parent / "ac_store" / sib

            self.assertTrue(
                source_resolved.exists(),
                f"Source layout: sibling {sib} not found at {source_resolved}. "
                f"The ac_store/ directory or the sibling file is missing from the repo.",
            )

        # ---------------------------------------------------------------
        # Part C: The critical invariant — deployed resolution must NOT double ac_store/
        # Verify the doubled path does not exist while the correct path does.
        # This is the RED assertion: the fix must make goal_to_epic.py detect
        # it is deployed inside ac_store/ and look sideways (not deeper).
        # ---------------------------------------------------------------
        for sib in sibling_names:
            doubled_path = deployed_ac_store / "ac_store" / sib
            correct_path = deployed_ac_store / sib

            # Confirm the doubled path does not exist (test env sanity)
            self.assertFalse(
                doubled_path.exists(),
                f"Doubled path {doubled_path} should not exist in the deployed layout.",
            )

            # The real RED assertion: goal_to_epic.py's current logic would
            # resolve to doubled_path (which doesn't exist). After the fix, it
            # must resolve to correct_path (which does exist). We assert that
            # the CURRENT code's resolution is incorrect by checking the source
            # uses the unguarded ``parent / "ac_store"`` pattern without a
            # deploy-location-aware check (i.e., no ``if "ac_store" in __file__``
            # or equivalent guard).
            goal_source = _GOAL_TO_EPIC_PATH.read_text(encoding="utf-8")
            has_location_guard = (
                "ac_store" in goal_source.split('Path(__file__).parent / "ac_store"')[0].split('\n')[-1]
                # A proper guard would look like: if the current file IS in ac_store,
                # use parent directly; otherwise use parent / "ac_store"
                or "_scripts_dir = Path(__file__).parent" in goal_source
                and "if" in goal_source
                and '"ac_store"' in goal_source
                and "parent.name" in goal_source
            )

            # This assertion is RED: the current code does NOT have a proper guard.
            # It will PASS once python-coder adds the deploy-location-aware logic.
            self.assertTrue(
                has_location_guard,
                f"goal_to_epic.py does NOT have a deploy-location-aware sibling "
                f"resolution guard. When deployed into ac_store/, "
                f"``Path(__file__).parent / 'ac_store' / '{sib}'`` resolves to "
                f"the non-existent doubled path {doubled_path} instead of the "
                f"correct path {correct_path}. "
                f"Add a guard: if Path(__file__).parent.name == 'ac_store', "
                f"resolve siblings as Path(__file__).parent / sib (not deeper).",
            )


if __name__ == "__main__":
    unittest.main()
