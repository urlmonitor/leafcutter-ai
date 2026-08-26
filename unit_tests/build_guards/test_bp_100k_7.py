"""
MODULE: unit_tests/build_guards/test_bp_100k_7.py
GOAL: BP-100k-7 -- ``check_command_reachability``'s skip decision for
    name-form workflow handoff targets must be taken from the DECLARED
    ``config["workflows"]["enabled"]`` value, and from nothing else -- never
    inferred from whether ``output_root/workflows/`` happens to exist on
    disk.
BUSINESS CONTEXT: scripts/build_phases.py (around lines 408-409, 467-475)
    currently computes ``workflows_deployed = (output_root / "workflows")
    .is_dir()`` and skips every name-form ``Workflow(...)`` reference when
    ``not workflows_deployed``, justifying the skip in its own log message as
    "workflows.enabled is off" -- a claim it never verifies, because it never
    reads the declared config value. The two states this conflates are
    opposite in meaning:
      (a) workflows deliberately disabled -> skipping is correct.
      (b) workflows ENABLED but the build failed to deploy them -> every
          command referencing a workflow by name is now unreachable, and
          this is exactly the failure the guard exists to catch.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100k-7.yaml.
DETECTOR SEAM: These tests call ``check_command_reachability(output_root,
    config)`` -- a signature EXTENSION python-coder must add (today's
    function accepts only ``output_root``). Calling with the extended
    signature against today's one-argument function raises ``TypeError``,
    which is a valid, meaningful RED state: it names exactly the missing
    capability (the guard does not yet accept a declared config to read),
    not an accidental typo or import error in this test file.
RED BASELINE (captured 2026-08-25, before any production-code change):
    Every test below fails with
    ``TypeError: check_command_reachability() takes 1 positional argument
    but 2 were given`` -- the guard does not yet accept the declared
    configuration it must read from.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import check_command_reachability  # noqa: E402

# The exact name-form Workflow() reference every shipped command template
# would carry -- registered nowhere on disk in these fixtures, so its
# reachability outcome depends ENTIRELY on the declared config value, not on
# any incidental filesystem state.
_NAME_FORM_TARGET = "build-feature"
_NAME_FORM_COMMAND_BODY = (
    "# Build feature\n\n"
    f'Workflow("{_NAME_FORM_TARGET}", {{ target: $ARGUMENTS }})\n'
)


def _make_output_root(
    base: Path,
    *,
    command_body: str = _NAME_FORM_COMMAND_BODY,
    command_filename: str = "probe.md",
    workflows_dir_present: bool = False,
    registered_workflow_names: list[str] | None = None,
) -> Path:
    """Build a synthetic post-deploy ``output_root`` fixture.

    Mirrors the real post-deploy layout ``check_command_reachability``
    scans: a ``commands/*.md`` file carrying a handoff target, and
    (optionally) a ``workflows/*.js`` registry -- present or absent
    independently of any config, so config and filesystem can be varied
    orthogonally by each test.

    Args:
        base: A fresh directory to build the fixture inside.
        command_body: Raw text for the single deployed command file.
        command_filename: Name of the deployed command file.
        workflows_dir_present: Whether ``output_root/workflows/`` exists at
            all -- simulating either "workflows deploy phase ran and wrote
            something" (True, with names) or "the workflows deploy phase
            never ran / produced nothing" (False), independent of whether
            the capability is declared enabled.
        registered_workflow_names: Stems to register as deployed ``*.js``
            files under ``output_root/workflows/`` when present.

    Returns:
        The synthetic ``output_root`` path.
    """
    output_root = base / "output_root"
    commands_dir = output_root / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / command_filename).write_text(command_body, encoding="utf-8")

    if workflows_dir_present:
        workflows_dir = output_root / "workflows"
        workflows_dir.mkdir(parents=True)
        for name in registered_workflow_names or []:
            (workflows_dir / f"{name}.js").write_text(
                f"// deployed workflow: {name}\n", encoding="utf-8"
            )

    return output_root


# ---------------------------------------------------------------------------
# Descriptor 1: enabled but output absent -> report + fail (the case the
# guard exists for).
# ---------------------------------------------------------------------------


class TestEnabledButOutputAbsentReportsUnreachableAndFails(unittest.TestCase):
    """AC BP-100k-7: capability declared enabled, output absent -> reported."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_enabled_but_output_absent_reports_unreachable_and_fails(self) -> None:
        # covers: BP-100k-7
        """
        The declared configuration says workflows ARE enabled, yet no
        ``workflows/`` output exists at all (the build failed to deploy
        them, or the phase never ran). Every name-form reference to a
        workflow must be reported as unreachable -- this is the precise
        combination the guard exists to catch, per the AC's second Given/
        When/Then clause.
        """
        output_root = _make_output_root(self.base, workflows_dir_present=False)
        config = {"workflows": {"enabled": True}}

        verdicts = check_command_reachability(output_root, config)

        flagged = {v.get("target") for v in verdicts}
        self.assertIn(
            _NAME_FORM_TARGET,
            flagged,
            msg=(
                f"workflows.enabled=True but no workflows were deployed -- "
                f"every reference to {_NAME_FORM_TARGET!r} must be reported "
                f"as unreachable. Got verdicts: {verdicts}"
            ),
        )
        matching = [v for v in verdicts if v.get("target") == _NAME_FORM_TARGET]
        self.assertEqual(
            matching[0].get("kind"),
            "workflow",
            msg=f"Expected kind='workflow', got {matching[0]!r}",
        )


# ---------------------------------------------------------------------------
# Descriptor 2: disabled -> skip, with a stated reason.
# ---------------------------------------------------------------------------


class TestDisabledCapabilityIsSkippedWithAStatedReason(unittest.TestCase):
    """AC BP-100k-7: capability declared disabled -> skipped, reason stated."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_disabled_capability_is_skipped_with_a_stated_reason(self) -> None:
        # covers: BP-100k-7
        """
        The declared configuration says workflows are disabled. The
        name-form reference must be skipped (not reported), AND the
        guard's emitted output must state that the skip was authorised by
        the declared configuration value -- never a silent skip that is
        indistinguishable from a check that ran and passed.
        """
        output_root = _make_output_root(self.base, workflows_dir_present=False)
        config = {"workflows": {"enabled": False}}

        with self.assertLogs("build_phases", level="WARNING") as captured:
            verdicts = check_command_reachability(output_root, config)

        flagged = {v.get("target") for v in verdicts}
        self.assertNotIn(
            _NAME_FORM_TARGET,
            flagged,
            msg=(
                "workflows.enabled=False must skip the name-form reference "
                f"rather than report it. Got verdicts: {verdicts}"
            ),
        )
        combined_log = "\n".join(captured.output).lower()
        self.assertIn(
            _NAME_FORM_TARGET.lower(),
            combined_log,
            msg=(
                "The skip must name the target it skipped. "
                f"Log output: {captured.output}"
            ),
        )
        self.assertTrue(
            any(
                keyword in combined_log
                for keyword in ("config", "declar", "disab")
            ),
            msg=(
                "The stated reason must attribute the skip to the declared "
                f"configuration value. Log output: {captured.output}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 3 (decisive): skip decision is a function of the declaration
# ONLY -- constant across filesystem presence, and DOES change when the
# declaration itself changes.
# ---------------------------------------------------------------------------


class TestSkipDecisionDoesNotChangeWhenOnlyOutputPresenceChanges(unittest.TestCase):
    """AC BP-100k-7 decisive descriptor.

    Holding the declared config value constant, adding or removing
    ``output_root/workflows/`` must not change the skip verdict. Flipping
    the declared value (filesystem held constant) must.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_skip_decision_does_not_change_when_only_the_output_presence_changes(
        self,
    ) -> None:
        # covers: BP-100k-7
        # --- Hold config constant at enabled=True; vary the filesystem. ---
        # A declaration of "enabled" must ALWAYS cause the guard to check
        # reachability against the real registry, regardless of whether the
        # workflows directory happens to exist or what it happens to
        # contain -- the decision must never depend on this presence.
        for idx, workflows_present in enumerate((False, True)):
            output_root = _make_output_root(
                self.base / f"enabled_{idx}",
                workflows_dir_present=workflows_present,
                # Deliberately register a DIFFERENT workflow so the target
                # under test is never accidentally satisfied by presence.
                registered_workflow_names=["some-other-workflow"]
                if workflows_present
                else None,
            )
            config = {"workflows": {"enabled": True}}
            verdicts = check_command_reachability(output_root, config)
            flagged = {v.get("target") for v in verdicts}
            self.assertIn(
                _NAME_FORM_TARGET,
                flagged,
                msg=(
                    "With workflows.enabled=True held constant, the skip "
                    f"decision must not depend on whether workflows/ "
                    f"exists on disk (workflows_dir_present={workflows_present}). "
                    f"Got verdicts: {verdicts}"
                ),
            )

        # --- Hold config constant at enabled=False; vary the filesystem. ---
        # A declaration of "disabled" must ALWAYS skip, regardless of
        # filesystem presence.
        for idx, workflows_present in enumerate((False, True)):
            output_root = _make_output_root(
                self.base / f"disabled_{idx}",
                workflows_dir_present=workflows_present,
                registered_workflow_names=["some-other-workflow"]
                if workflows_present
                else None,
            )
            config = {"workflows": {"enabled": False}}
            verdicts = check_command_reachability(output_root, config)
            flagged = {v.get("target") for v in verdicts}
            self.assertNotIn(
                _NAME_FORM_TARGET,
                flagged,
                msg=(
                    "With workflows.enabled=False held constant, the skip "
                    f"decision must not depend on filesystem presence "
                    f"(workflows_dir_present={workflows_present}). "
                    f"Got verdicts: {verdicts}"
                ),
            )

        # --- Now flip the declaration, filesystem held constant (absent).
        # The decision MUST change: this proves the decision is taken from
        # the declaration, not merely insensitive to everything.
        output_root_absent = _make_output_root(
            self.base / "flip_absent", workflows_dir_present=False
        )
        enabled_verdicts = check_command_reachability(
            output_root_absent, {"workflows": {"enabled": True}}
        )
        disabled_verdicts = check_command_reachability(
            output_root_absent, {"workflows": {"enabled": False}}
        )
        self.assertIn(
            _NAME_FORM_TARGET,
            {v.get("target") for v in enabled_verdicts},
            msg="Flipping to enabled=True (filesystem unchanged) must report the target.",
        )
        self.assertNotIn(
            _NAME_FORM_TARGET,
            {v.get("target") for v in disabled_verdicts},
            msg="Flipping to enabled=False (filesystem unchanged) must skip the target.",
        )


# ---------------------------------------------------------------------------
# Descriptor 4: unreadable/malformed declaration -> reported, not treated as
# off.
# ---------------------------------------------------------------------------


class TestUnreadableDeclarationIsReportedRatherThanTreatedAsOff(unittest.TestCase):
    """AC BP-100k-7: a value that cannot be read is a reported condition."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_unreadable_declaration_is_reported_rather_than_treated_as_off(
        self,
    ) -> None:
        # covers: BP-100k-7
        """
        ``config["workflows"]`` is malformed (not a dict, so ``.get(...)``
        on it is meaningless) rather than absent. This must not silently
        collapse to "off" -- the guard must report that it could not
        establish whether the capability is enabled, distinct from both
        the "enabled" and "disabled" verdict shapes above.
        """
        output_root = _make_output_root(self.base, workflows_dir_present=False)
        malformed_config = {"workflows": ["not", "a", "dict"]}

        verdicts = check_command_reachability(output_root, malformed_config)

        self.assertTrue(
            verdicts,
            msg=(
                "A malformed workflows declaration must not silently mean "
                f"'off' with zero verdicts. Got: {verdicts}"
            ),
        )
        reasons = " ".join(str(v.get("reason", "")) for v in verdicts).lower()
        self.assertTrue(
            any(
                keyword in reasons
                for keyword in (
                    "cannot", "could not", "unable", "malformed",
                    "unreadable", "invalid",
                )
            ),
            msg=(
                "The reported condition must explain that the declared "
                f"value could not be read. Verdicts: {verdicts}"
            ),
        )


# ---------------------------------------------------------------------------
# Descriptor 5: every skip the guard performs names its reason.
# ---------------------------------------------------------------------------


class TestEverySkipTheGuardPerformsNamesItsReason(unittest.TestCase):
    """AC BP-100k-7: no skipped check may be indistinguishable from a pass."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_every_skip_the_guard_performs_names_its_reason(self) -> None:
        # covers: BP-100k-7
        """
        Two distinct commands, each with a distinct name-form workflow
        target, are skipped in the same run (workflows declared disabled).
        Each skip must independently carry a stated reason in the guard's
        emitted output -- one skip must never be silently absorbed into
        (or hidden behind) another.
        """
        output_root = self.base / "output_root"
        commands_dir = output_root / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "alpha.md").write_text(
            '# Alpha\n\nWorkflow("alpha-workflow", { target: $ARGUMENTS })\n',
            encoding="utf-8",
        )
        (commands_dir / "beta.md").write_text(
            '# Beta\n\nWorkflow("beta-workflow", { target: $ARGUMENTS })\n',
            encoding="utf-8",
        )
        config = {"workflows": {"enabled": False}}

        with self.assertLogs("build_phases", level="WARNING") as captured:
            verdicts = check_command_reachability(output_root, config)

        self.assertEqual(
            verdicts,
            [],
            msg=f"Both targets must be skipped (disabled), not reported. Got: {verdicts}",
        )
        combined = "\n".join(captured.output)
        self.assertIn(
            "alpha-workflow",
            combined,
            msg=f"The skip of 'alpha-workflow' must name its own reason. Log: {captured.output}",
        )
        self.assertIn(
            "beta-workflow",
            combined,
            msg=f"The skip of 'beta-workflow' must name its own reason. Log: {captured.output}",
        )


if __name__ == "__main__":
    unittest.main()
