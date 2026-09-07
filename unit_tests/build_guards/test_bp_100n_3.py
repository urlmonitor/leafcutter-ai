"""
MODULE: unit_tests/build_guards/test_bp_100n_3.py
GOAL: BP-100n-3 -- the bidirectional manifest/output equality guard added by
    BP-100k-2 (``unit_tests/build_guards/test_bp_100k_2.py``) must exercise
    EVERY platform the build's own platform set declares -- never a fixed
    subset chosen inside the guard's own fixture.
BUSINESS CONTEXT: ``test_bp_100k_2.py`` pins ``"antigravity": False`` in two
    places (its ``_deploy_agents_and_write_manifest`` helper, ~line 231, and
    ``TestOutputMappingCoversEveryDeployPhaseOutput``
    .test_output_mapping_covers_every_deploy_phase_output, ~line 444). This
    excludes the ENTIRE ``gemini/agents`` (and, in the second location,
    ``gemini/workflows``) output family from the equality assertion the AC
    depends on. A guard that proves equality only for the platforms it chose
    to enable proves nothing about the rest -- and the omission is invisible
    in that guard's own green result.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100n-3.yaml.
DO NOT EDIT ``test_bp_100k_2.py``: fixing the pin is python-coder's job. This
    module IMPORTS test_bp_100k_2.py's real, unedited fixture helpers (never
    a hand-typed guess at its hardcoded literal) and runs them for real, so
    every assertion here is coupled to the ACTUAL pinned artifact rather than
    a static description of it -- per the standing rule in CLAUDE.md ("Gate /
    Workflow ACs -- Verify Behaviorally, Not by Grep").
ARCHITECTURE / EXERCISE STRATEGY:
    ``_load_bp100k2_module()`` below loads ``test_bp_100k_2.py`` itself, by
    file path, as a fresh module -- the exact same "no bare-name sys.modules
    reuse" discipline that module already uses internally for
    ``build_phases``/``build_helpers``/``config_loader`` (see its own
    ``_load_fresh_module`` docstring), because ``build_phases.py`` resolves
    its own package root from ``Path(__file__).resolve().parent.parent`` at
    import time. Every test below then calls that module's REAL
    ``_build_synthetic_full_package``, ``_load_pkg_modules``, ``_load_manifest``,
    and ``_deploy_agents_and_write_manifest`` helpers directly -- the exact
    functions the AC's doc_links name as the guard under repair -- and
    inspects the resulting on-disk artifacts and manifest, never the guard's
    source text.
RED BASELINE (captured 2026-08-25, before any production-code change): every
    test below fails because ``_deploy_agents_and_write_manifest`` pins
    ``antigravity: False`` (and ``cursor: False``) internally regardless of
    what the build's own declared/default platform set says, so the
    antigravity (and cursor) output families are never exercised by the
    guard's manifest no matter what this test declares or produces on disk
    independently.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_BP_100K_2_PATH = Path(__file__).resolve().parent / "test_bp_100k_2.py"

_UNIQUE_COUNTER = [0]


def _load_bp100k2_module() -> types.ModuleType:
    """Load ``test_bp_100k_2.py`` fresh, by file path, under a unique name.

    Never reused across tests via a shared ``sys.modules`` bare-name entry:
    each call gets its own fully independent module object (and therefore
    its own independent ``_UNIQUE_COUNTER`` for ITS internal
    ``_load_fresh_module`` calls), matching the isolation discipline that
    module already applies to ``build_phases``/``build_helpers``.

    Returns:
        The freshly executed ``test_bp_100k_2`` module object.
    """
    _UNIQUE_COUNTER[0] += 1
    unique_name = f"_bp100k8_test_bp_100k_2_{_UNIQUE_COUNTER[0]}"
    spec = importlib.util.spec_from_file_location(unique_name, _TEST_BP_100K_2_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load a module spec for {_TEST_BP_100K_2_PATH} — "
            "the fixture file is missing or unimportable, which must fail "
            "loudly rather than crash later with a confusing TypeError."
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Descriptor 1: the guard exercises every platform the build can emit.
# ---------------------------------------------------------------------------


class TestGuardExercisesEveryPlatformTheBuildCanEmit(unittest.TestCase):
    """AC BP-100n-3: exercised platform set == the build's own declared set."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_guard_exercises_every_platform_the_build_can_emit(self) -> None:
        # covers: BP-100n-3
        # --- Oracle: what platforms does the BUILD ITSELF activate for the
        # agents family when the operator supplies no override at all?
        # Determined BEHAVIORALLY against a second, independent synthetic
        # package -- never by reading a literal out of build_phases.py.
        oracle_workspace = self.workspace / "oracle"
        oracle_workspace.mkdir()
        oracle_pkg_root = self.bp2._build_synthetic_full_package(oracle_workspace)
        _, oracle_build_phases, oracle_config_loader = self.bp2._load_pkg_modules(
            oracle_pkg_root
        )
        oracle_config = oracle_config_loader.load_config(None, oracle_workspace)
        oracle_output_root = oracle_workspace / oracle_config.get(
            "output_root", ".leafcutter"
        )
        oracle_build_phases.build_agents(
            oracle_output_root, oracle_config, dry_run=False, force=True
        )
        declared_agent_platforms = {
            platform
            for platform, subdir in (("claude", "agents"), ("antigravity", "gemini/agents"))
            if (oracle_output_root / subdir).is_dir()
            and any((oracle_output_root / subdir).glob("*.md"))
        }
        self.assertEqual(
            declared_agent_platforms,
            {"claude", "antigravity"},
            msg=(
                "setup sanity: the build's own default must activate both "
                "claude and antigravity for the agents family when no "
                f"override is supplied. Got {declared_agent_platforms!r}"
            ),
        )

        # --- Now run the REAL, currently-pinned guard fixture (imported,
        # never edited) and check which of those SAME platforms its own
        # manifest actually covers.
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        manifest = self.bp2._load_manifest(self.pkg_root)
        output_mappings = manifest.get("output_mappings", {})
        exercised = {
            platform
            for platform, prefix in (
                ("claude", ".claude/agents/"),
                ("antigravity", ".gemini/agents/"),
            )
            if any(key.startswith(prefix) for key in output_mappings)
        }

        self.assertEqual(
            declared_agent_platforms,
            exercised,
            msg=(
                f"The equality guard's own manifest covers {sorted(exercised)} "
                f"but the build itself activates {sorted(declared_agent_platforms)} "
                "for the agents family. A platform the build emits by default "
                "must not be silently excluded from the guard's coverage by a "
                "fixed choice inside the guard's own fixture (BP-100n-3)."
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 2: no platform is withheld by a choice inside the guard.
# ---------------------------------------------------------------------------


class TestNoPlatformIsWithheldByAChoiceInsideTheGuard(unittest.TestCase):
    """AC BP-100n-3: nothing but the build's own config may exclude a platform."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_no_platform_is_withheld_by_a_choice_inside_the_guard(self) -> None:
        # covers: BP-100n-3
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        manifest = self.bp2._load_manifest(self.pkg_root)
        output_mappings = manifest.get("output_mappings", {})

        exercised = {
            platform
            for platform, prefix in (
                ("claude", ".claude/agents/"),
                ("antigravity", ".gemini/agents/"),
            )
            if any(key.startswith(prefix) for key in output_mappings)
        }
        # The build is CAPABLE of emitting an agents family for both claude
        # and antigravity (see build_phases._agents_pdirs). Nothing here
        # declares either platform off -- so nothing should be missing.
        missing = {"claude", "antigravity"} - exercised

        self.assertEqual(
            missing,
            set(),
            msg=(
                f"Platform(s) {sorted(missing)} are missing from the "
                "equality guard's exercised set even though the build is "
                "capable of emitting their agents family and nothing here "
                "declared them off. A platform may only be excluded by the "
                "build's own configuration, never by a fixed choice made "
                f"inside the guard (BP-100n-3). output_mappings sample: "
                f"{sorted(output_mappings.keys())[:5]}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 3 (decisive): a newly emittable platform is covered without
# editing the guard.
# ---------------------------------------------------------------------------


class TestANewlyEmittablePlatformIsCoveredWithoutEditingTheGuard(unittest.TestCase):
    """AC BP-100n-3 decisive descriptor.

    Extending the build's declared platform set by one (claude-only ->
    claude+antigravity) must be reflected in the guard's exercised set
    WITHOUT any change to the guard's own code -- proving coverage is read
    from the build's platform set, not enumerated as a guard-local literal.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_a_newly_emittable_platform_is_covered_without_editing_the_guard(
        self,
    ) -> None:
        # covers: BP-100n-3
        # --- "Before": a platform set with only claude active. ---
        before_workspace = self.workspace / "before"
        before_workspace.mkdir()
        before_pkg_root = self.bp2._build_synthetic_full_package(before_workspace)
        _, before_build_phases, before_config_loader = self.bp2._load_pkg_modules(
            before_pkg_root
        )
        before_config = before_config_loader.load_config(None, before_workspace)
        before_config["platforms"] = {
            "claude": True, "antigravity": False, "cursor": False,
            "copilot": False, "cline": False,
        }
        before_output_root = before_workspace / before_config.get(
            "output_root", ".leafcutter"
        )
        before_build_phases.build_agents(
            before_output_root, before_config, dry_run=False, force=True
        )
        before_active = {
            p for p, sub in (("claude", "agents"), ("antigravity", "gemini/agents"))
            if (before_output_root / sub).is_dir()
            and any((before_output_root / sub).glob("*.md"))
        }
        self.assertEqual(
            before_active, {"claude"},
            msg=f"setup sanity: 'before' oracle must activate only claude, got {before_active}",
        )

        # --- "After": the build's platform set EXTENDED BY ONE (antigravity
        # now also declared active) -- a real, independently-verified fact,
        # never assumed.
        after_workspace = self.workspace / "after"
        after_workspace.mkdir()
        after_pkg_root = self.bp2._build_synthetic_full_package(after_workspace)
        _, after_build_phases, after_config_loader = self.bp2._load_pkg_modules(
            after_pkg_root
        )
        after_config = after_config_loader.load_config(None, after_workspace)
        after_config["platforms"] = {
            "claude": True, "antigravity": True, "cursor": False,
            "copilot": False, "cline": False,
        }
        after_output_root = after_workspace / after_config.get(
            "output_root", ".leafcutter"
        )
        after_build_phases.build_agents(
            after_output_root, after_config, dry_run=False, force=True
        )
        after_active = {
            p for p, sub in (("claude", "agents"), ("antigravity", "gemini/agents"))
            if (after_output_root / sub).is_dir()
            and any((after_output_root / sub).glob("*.md"))
        }
        self.assertEqual(
            after_active, {"claude", "antigravity"},
            msg=(
                "setup sanity: the 'after' oracle must show the platform "
                f"set genuinely extended by one, got {after_active}"
            ),
        )

        # --- The guard itself, run WITHOUT any edit between "before" and
        # "after" (it is the same imported, unedited function both times):
        # its own exercised set must track this real extension. Today it
        # cannot, because it hardcodes antigravity off internally regardless
        # of what any caller's platform set actually contains.
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        manifest = self.bp2._load_manifest(self.pkg_root)
        output_mappings = manifest.get("output_mappings", {})
        guard_exercised = {
            platform
            for platform, prefix in (
                ("claude", ".claude/agents/"),
                ("antigravity", ".gemini/agents/"),
            )
            if any(key.startswith(prefix) for key in output_mappings)
        }

        self.assertEqual(
            guard_exercised,
            after_active,
            msg=(
                "antigravity became emittable (the build's own platform set "
                f"was extended by one, verified as {sorted(after_active)}), "
                "but the guard's exercised set is "
                f"{sorted(guard_exercised)} -- the extension is not "
                "reflected without editing the guard itself. Only a guard "
                "reading the build's own platform set can cover a newly "
                "emittable platform for free (BP-100n-3)."
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 4: an unexercisable platform is named and the run fails.
# ---------------------------------------------------------------------------


class TestUnexercisablePlatformIsNamedAndTheRunFails(unittest.TestCase):
    """AC BP-100n-3: "I could not exercise this platform" must never mean
    silent success -- it must be a NAMED, failing condition."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_unexercisable_platform_is_named_and_the_run_fails(self) -> None:
        # covers: BP-100n-3
        """
        Pre-create the antigravity output directory the deploy would need
        to write into, and make it unwritable -- a real, on-disk
        obstruction to actually exercising that platform in this
        environment. A guard that reads the build's own (antigravity-
        active-by-default) platform set and genuinely tries to exercise
        every platform it names would hit this obstruction and must raise,
        naming "antigravity" and stating it is unverified.

        Today's guard fixture never even attempts to write there (its
        internal override pins antigravity off before any such attempt),
        so it raises nothing at all -- proving the obstruction is invisible
        to it, which is exactly the silent-success failure mode this AC
        forbids.
        """
        output_root = self.workspace / ".leafcutter"
        blocked_dir = output_root / "gemini" / "agents"
        blocked_dir.mkdir(parents=True)
        blocked_dir.chmod(0o000)
        try:
            with self.assertRaises(Exception) as ctx:
                self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
            message = str(ctx.exception).lower()
            self.assertIn("antigravity", message)
            self.assertIn("unverified", message)
        finally:
            blocked_dir.chmod(0o755)


# ---------------------------------------------------------------------------
# Descriptor 5: an output family of an unexercised platform is never counted
# as covered.
# ---------------------------------------------------------------------------


class TestOutputFamilyOfAnUnexercisedPlatformIsNotCountedAsCovered(
    unittest.TestCase
):
    """AC BP-100n-3: a real, on-disk family the guard didn't exercise must
    not be silently absent from what the equality assertion claims to have
    verified."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.bp2 = _load_bp100k2_module()
        self.pkg_root = self.bp2._build_synthetic_full_package(self.workspace)

    def test_output_family_of_an_unexercised_platform_is_not_counted_as_covered(
        self,
    ) -> None:
        # covers: BP-100n-3
        build_helpers_mod, build_phases_mod, config_loader_mod = (
            self.bp2._load_pkg_modules(self.pkg_root)
        )
        config = config_loader_mod.load_config(None, self.workspace)
        config["platforms"] = {
            "claude": True, "antigravity": True, "cursor": False,
            "copilot": False, "cline": False,
        }
        output_root = self.workspace / config.get("output_root", ".leafcutter")

        # Produce the antigravity family for REAL, directly on the same
        # output_root the pinned guard fixture will use next.
        build_phases_mod.build_agents(output_root, config, dry_run=False, force=True)
        antigravity_family = output_root / "gemini" / "agents"
        self.assertTrue(
            antigravity_family.is_dir() and any(antigravity_family.glob("*.md")),
            f"setup sanity: expected a real antigravity agents family at {antigravity_family}",
        )

        # Now run the REAL, currently-pinned guard fixture (imported,
        # never edited) against the SAME workspace/output_root. It
        # recomputes output_mappings from its own hardcoded platforms
        # override, which excludes antigravity regardless of what is
        # already, physically, on disk.
        self.bp2._deploy_agents_and_write_manifest(self.workspace, self.pkg_root)
        manifest = self.bp2._load_manifest(self.pkg_root)
        output_mappings = manifest.get("output_mappings", {})
        antigravity_covered = any(
            key.startswith(".gemini/agents/") for key in output_mappings
        )

        self.assertTrue(
            antigravity_covered,
            msg=(
                f"A real, on-disk antigravity output family exists at "
                f"{antigravity_family}, yet the equality guard's own "
                "manifest has zero .gemini/agents/ entries -- an output "
                "family produced under a platform the guard did not "
                "exercise must not be silently absent from what the "
                "equality assertion claims to have verified (BP-100n-3). "
                f"output_mappings sample: {sorted(output_mappings.keys())[:5]}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
