"""
MODULE: test_command_reachability_guard
GOAL: Failing (RED) test baseline for BP-900g-1 / BP-900g-1-i — a real
    command-reference reachability GUARD, not merely the name-based workaround
    that BP-900g's workaround already applied to the real command templates.

TICKET: 06_bp900g1_command_reachability_guard
ACS: BP-900g-1, BP-900g-1-i

Remediation context
--------------------
BP-900g-1 was previously phantom-done: templates/commands/build-feature.md and
finalize-feature.md were switched to the name-based Workflow("build-feature")
form (real fix), and test_deploy_collision_guard.py pins that workaround. But
no build-time GUARD exists that would catch a *regression* back to the
non-resolving path form Workflow("scripts/workflows/build-feature.js") — a
form that does not resolve post-deploy because build_workflow_scripts()
deploys workflow .js files to <output_root>/workflows/ (reachable via the
.claude/workflows shim, per BP-811), never under scripts/workflows/.

This module specifies and pins the guard itself: a pure function that scans
deployed commands for Workflow(...)/Skill(...) handoff targets and resolves
each against the TRUE post-deploy layout.

Detector seam
-------------
The unit tests are written against a pure function with this signature (to be
added to scripts/build_phases.py by python-coder):

    def check_command_reachability(output_root: Path) -> list[dict]:
        '''Scan every deployed command under output_root/commands/*.md for
        Workflow(...) and Skill(...) handoff targets, resolve each against the
        real post-deploy layout rooted at output_root, and return one verdict
        dict per UNRESOLVABLE target.

        Extraction:
            For every *.md file directly under output_root/commands/, extract
            every Workflow("...") / Workflow('...') and Skill("...") /
            Skill('...') call's first string argument as a target.

        Resolution rules (a target resolves if EITHER applies):
            1. Name-form (registry): the target contains no "/" and is not a
               bare file path. It resolves if it matches a registered entry in
               the deployed registry:
                 - kind="workflow": stem of a *.js file directly under
                   output_root/workflows/ equals the target.
                 - kind="skill": a directory directly under output_root/skills/
                   is named exactly the target.
            2. Path-form: the target is resolved as a literal relative path
               against output_root, i.e. (output_root / target).exists().
               A path such as "scripts/workflows/build-feature.js" does NOT
               resolve via this rule because the real deployed artifact lives
               at output_root/workflows/build-feature.js, not
               output_root/scripts/workflows/build-feature.js.

        Args:
            output_root: Absolute path to the consolidated, ALREADY-DEPLOYED
                build output directory (e.g. <target>/.leafcutter), containing
                commands/*.md, workflows/*.js, and skills/*/ post-deploy.

        Returns:
            List of dicts, one per unresolvable target:
                {
                    "command": Path,               # the command .md file
                    "target":  str,                # the raw handoff target string
                    "kind":    "workflow" | "skill",
                    "reason":  str,                 # human-readable, must name
                                                     # the target and state that
                                                     # it does not resolve to a
                                                     # deployed artifact post-deploy
                }
            Empty list means every extracted reference resolves (build may
            proceed). This mirrors the "ok=true iff empty" contract already
            established by detect_deploy_collisions() (BP-100m) in this same
            module.
        '''

Wiring contract (build.py must honour, per BP-900g-1 Gherkin "When build.py
runs its command-reference reachability check, Then the build exits with a
non-zero status"):
    After the deploy phases run (post-deploy, mirroring how
    _check_deploy_collision_guard() runs against phase_mappings), build.py
    must call check_command_reachability(output_root) and, if the returned
    list is non-empty, print each entry's command/target/kind/reason to
    stderr and exit non-zero (sys.exit(1) or raise) BEFORE reporting overall
    build success. This is the COMMAND-SIDE analogue of BP-811 (the shim
    fix); this module and BP-900g-1/-1-i do not modify or re-parent BP-811.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — resolves to leafcutter-ai repo root, then scripts/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Lazy import of the (not-yet-existing) checker function.
#
# Wrapped in try/except so the test module imports cleanly and each test
# function surfaces its own failure rather than a single collection error.
# When check_command_reachability does not exist, _CHECK is None and every
# test raises ImportError explicitly via _require_checker() — that IS the
# red baseline.
# ---------------------------------------------------------------------------
try:
    from build_phases import check_command_reachability as _CHECK  # noqa: E402
except ImportError:
    _CHECK = None  # type: ignore[assignment]


class _CheckerMissing(ImportError):
    """Raised when check_command_reachability is not yet in build_phases."""

    def __init__(self) -> None:
        super().__init__(
            "check_command_reachability not found in build_phases — "
            "python-coder must implement this function (BP-900g-1 guardrail)"
        )


def _require_checker():
    """Return check_command_reachability or raise _CheckerMissing if absent."""
    if _CHECK is None:
        raise _CheckerMissing()
    return _CHECK


def _make_output_root(tmp_path: Path, command_filename: str, command_body: str,
                      registered_workflow_names: list[str] | None = None,
                      registered_skill_names: list[str] | None = None) -> Path:
    """Build a synthetic post-deploy output_root fixture.

    Creates output_root/commands/<command_filename> with the given body, plus
    output_root/workflows/<name>.js and output_root/skills/<name>/SKILL.md for
    every registered name, simulating the real post-deploy layout that
    build_commands()/build_workflow_scripts()/build_skills() produce.
    """
    output_root = tmp_path / "output_root"
    commands_dir = output_root / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / command_filename).write_text(command_body, encoding="utf-8")

    workflows_dir = output_root / "workflows"
    workflows_dir.mkdir(parents=True)
    for name in registered_workflow_names or []:
        (workflows_dir / f"{name}.js").write_text(
            f"// deployed workflow: {name}\n", encoding="utf-8"
        )

    skills_dir = output_root / "skills"
    skills_dir.mkdir(parents=True)
    for name in registered_skill_names or []:
        skill_subdir = skills_dir / name
        skill_subdir.mkdir(parents=True)
        (skill_subdir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    return output_root


# ===========================================================================
# AC BP-900g-1: path-form unresolvable target fails the build
# ===========================================================================

class TestPathFormUnresolvableTargetFailsBuild:
    """BP-900g-1: a path-form Workflow() reference that does not resolve
    post-deploy must be flagged, naming the command, the target, and the
    reason it does not resolve."""

    def test_ac_bp900g1_pathform_unresolvable_target_fails_build(self, tmp_path):
        # covers: BP-900g-1
        """
        Given a deployed command containing:
            Workflow("scripts/workflows/build-feature.js", { target: $ARGUMENTS })
        And the real deployed artifact for "build-feature" lives at
            output_root/workflows/build-feature.js
        (never at output_root/scripts/workflows/build-feature.js),
        check_command_reachability(output_root) must return a non-empty list
        naming this command, this exact unresolvable target string, kind
        "workflow", and a reason stating the target does not resolve to a
        deployed artifact post-deploy.

        This is the live regression fixture named in the ticket: BP-900g's
        workaround already switched the REAL templates/commands/build-feature.md
        to the name-based form, so this test pins the synthetic path-form
        regression the guard must catch if that workaround is ever reverted.

        What python-coder must implement: check_command_reachability() must
        extract the Workflow(...) target verbatim, treat any target containing
        "/" as path-form, and resolve path-form targets ONLY as a literal
        relative path against output_root — never by stripping a
        "scripts/workflows/" prefix or otherwise special-casing it into the
        name-form registry lookup.
        """
        check_command_reachability = _require_checker()

        command_filename = "build-feature.md"
        command_body = (
            "# Build feature\n\n"
            'Workflow("scripts/workflows/build-feature.js", { target: $ARGUMENTS })\n'
        )
        # The real artifact IS deployed — but at workflows/, not
        # scripts/workflows/ — so the path-form reference still does not
        # resolve to it.
        output_root = _make_output_root(
            tmp_path,
            command_filename,
            command_body,
            registered_workflow_names=["build-feature"],
        )

        verdicts = check_command_reachability(output_root)

        matching = [
            v for v in verdicts
            if v.get("target") == "scripts/workflows/build-feature.js"
        ]
        assert matching, (
            "Expected an unresolvable-target verdict for "
            "'scripts/workflows/build-feature.js'. "
            f"Got verdicts: {verdicts}. "
            "check_command_reachability() must flag path-form targets that do "
            "not exist relative to output_root, even when a same-named "
            "artifact is deployed elsewhere (output_root/workflows/)."
        )
        verdict = matching[0]
        assert verdict["command"] == output_root / "commands" / command_filename, (
            f"Verdict must name the command file, got {verdict['command']!r}"
        )
        assert verdict["kind"] == "workflow", (
            f"Expected kind='workflow', got {verdict.get('kind')!r}"
        )
        reason = verdict.get("reason", "")
        assert isinstance(reason, str) and reason, (
            "Verdict must include a non-empty 'reason' string"
        )
        assert "scripts/workflows/build-feature.js" in reason or "resolve" in reason.lower(), (
            f"Reason must reference the unresolvable target or explain the "
            f"resolution failure. Got: {reason!r}"
        )

    def test_ac_bp900g1_pathform_target_absent_entirely_also_fails(self, tmp_path):
        # covers: BP-900g-1
        """
        Sanity companion: a path-form target that resolves to NOTHING at all
        (no deployed artifact anywhere under output_root) must also be flagged
        — the guard is not merely checking "does the name exist somewhere",
        it is checking the literal path.

        What python-coder must implement: no special-casing of "typically
        missing" vs "deployed under a different name" — both are unresolvable
        path-form targets and must both appear in the returned list.
        """
        check_command_reachability = _require_checker()

        command_filename = "totally-broken.md"
        command_body = 'Workflow("scripts/workflows/does-not-exist.js")\n'
        output_root = _make_output_root(
            tmp_path, command_filename, command_body,
            registered_workflow_names=[],
        )

        verdicts = check_command_reachability(output_root)
        matching = [
            v for v in verdicts
            if v.get("target") == "scripts/workflows/does-not-exist.js"
        ]
        assert matching, (
            f"Expected an unresolvable verdict for a target with no deployed "
            f"artifact anywhere. Got: {verdicts}"
        )


# ===========================================================================
# AC BP-900g-1-i: name-form registry target passes
# ===========================================================================

class TestNameFormRegistryTargetPasses:
    """BP-900g-1-i: a name-based Workflow() reference that matches a
    registered deployed workflow must resolve — no unresolvable verdict for
    that target."""

    def test_ac_bp900g1i_nameform_registry_target_passes(self, tmp_path):
        # covers: BP-900g-1-i
        """
        Given a deployed command containing:
            Workflow("build-feature", { target: $ARGUMENTS })
        And "build-feature" is a registered entry in the deployed workflow
        registry (i.e. output_root/workflows/build-feature.js exists),
        check_command_reachability(output_root) must NOT include any verdict
        for the "build-feature" target — resolution-by-name via the registry
        is a valid, correct form (this is the fix BP-900g already applied to
        the real templates; the guard must not regress it back to a false
        failure).

        What python-coder must implement: name-form targets (no "/") are
        resolved by checking membership in the deployed registry (workflow
        .js stems under output_root/workflows/, or skill directory names
        under output_root/skills/) — not by requiring a literal file at
        output_root/<target> (which would incorrectly fail every valid
        name-form reference).
        """
        check_command_reachability = _require_checker()

        command_filename = "build-feature.md"
        command_body = (
            "# Build feature\n\n"
            'Workflow("build-feature", { target: $ARGUMENTS })\n'
        )
        output_root = _make_output_root(
            tmp_path,
            command_filename,
            command_body,
            registered_workflow_names=["build-feature"],
        )

        verdicts = check_command_reachability(output_root)

        matching = [v for v in verdicts if v.get("target") == "build-feature"]
        assert not matching, (
            f"Name-form target 'build-feature' is registered "
            f"(output_root/workflows/build-feature.js exists) and must "
            f"resolve. Got unexpected unresolvable verdict(s): {matching}"
        )

    def test_ac_bp900g1i_unregistered_nameform_target_still_fails(self, tmp_path):
        # covers: BP-900g-1-i
        """
        Companion negative case: a name-form target that is NOT registered
        (no matching workflow .js deployed) must still be flagged — the
        registry lookup must be a real membership check, not a rule that
        blanket-passes every extension-less string.

        What python-coder must implement: the name-form resolution path must
        actually consult the deployed registry contents, not just "target has
        no slash therefore pass".
        """
        check_command_reachability = _require_checker()

        command_filename = "some-command.md"
        command_body = 'Workflow("totally-unregistered-workflow-name")\n'
        output_root = _make_output_root(
            tmp_path, command_filename, command_body,
            registered_workflow_names=["build-feature"],  # a different name registered
        )

        verdicts = check_command_reachability(output_root)
        matching = [
            v for v in verdicts
            if v.get("target") == "totally-unregistered-workflow-name"
        ]
        assert matching, (
            "An unregistered name-form target must still be flagged as "
            f"unresolvable. Got verdicts: {verdicts}"
        )


# ===========================================================================
# Real-artifact behavioral round-trip: run the REAL build.py, then check
# reachability against the REAL deployed output (BP-1100f-2 mandate).
# ===========================================================================

class TestRealDeployedBuildFeatureCommandPassesReachability:
    """
    Runs the actual build.py against the real template tree into a temp
    target directory (with workflows enabled so the .js registry is
    populated), then calls check_command_reachability() against the REAL
    deployed output_root — not a hand-authored fixture.

    This is the real-effect round-trip: build.py is invoked for real, writes
    real files to a real (temporary) location, and the guard function reads
    those real files back and asserts on them.

    RED now: check_command_reachability does not exist (ImportError via
    _require_checker()).
    GREEN after: python-coder implements check_command_reachability() and it
    correctly reports zero unresolvable targets for the real, already-fixed
    templates/commands/build-feature.md (BP-900g's name-based workaround).
    """

    def test_real_deployed_build_feature_resolves_with_zero_findings(self, tmp_path):
        # covers: BP-900g-1
        # covers: BP-900g-1-i
        """
        End-to-end: run scripts/build.py for real (workflows enabled via a
        temp skills_config.json) into tmp_path, then run
        check_command_reachability() against the real deployed
        <target>/.leafcutter output. Assert:
          1. The real build actually deploys workflows/build-feature.js
             (sanity: the registry fixture we depend on is real, not assumed).
          2. check_command_reachability() returns zero verdicts naming
             "build-feature.md" as the offending command — the real template
             already uses the name-based Workflow("build-feature") form.

        If this ever regresses (someone reverts BP-900g's fix back to the
        path form in templates/commands/build-feature.md), this test starts
        failing WITHOUT any code change to build_phases.py — that is the
        guard doing its job on real, on-disk artifacts.
        """
        check_command_reachability = _require_checker()

        target_dir = tmp_path / "deploy_target"
        target_dir.mkdir()

        config_path = tmp_path / "skills_config.json"
        config_path.write_text(
            json.dumps({"workflows": {"enabled": True}}), encoding="utf-8"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "build.py"),
                "--target-dir",
                str(target_dir),
                "--config",
                str(config_path),
                "--self-description-enforcement",
                "warning",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )

        output_root = target_dir / ".leafcutter"
        deployed_workflow = output_root / "workflows" / "build-feature.js"
        deployed_command = output_root / "commands" / "build-feature.md"

        assert deployed_workflow.exists(), (
            "Sanity check failed: real build.py run (workflows enabled) did "
            f"not deploy {deployed_workflow}. build returncode={result.returncode}. "
            f"stdout (last 500 chars): {result.stdout[-500:]}\n"
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        assert deployed_command.exists(), (
            f"Expected real deployed command at {deployed_command}"
        )

        verdicts = check_command_reachability(output_root)
        offending = [
            v for v in verdicts
            if Path(v.get("command", "")).name == "build-feature.md"
        ]
        assert not offending, (
            "The real, already-deployed templates/commands/build-feature.md "
            "must resolve with zero reachability findings (BP-900g's "
            "name-based Workflow(\"build-feature\") fix is real and current). "
            f"Got offending verdict(s): {offending}\n"
            f"All verdicts: {verdicts}"
        )


# ===========================================================================
# Behavioral (not grep-only) proof that a non-empty verdict list represents
# a build-failing condition, per the AC's "ok=true iff empty" contract.
# ===========================================================================

class TestNonEmptyVerdictRepresentsBuildFailure:
    """
    Per BP-900g-1's delivers_to contract: "ok=true iff empty. Non-empty fails
    the build." This class exercises that contract directly against a
    deliberately broken (synthetic, but structurally real) post-deploy tree,
    distinct from the existing collision-guard workaround test in
    test_deploy_collision_guard.py.
    """

    def test_broken_deployed_tree_yields_ok_false(self, tmp_path):
        # covers: BP-900g-1
        """
        Given a post-deploy tree containing both an unresolvable path-form
        reference AND a resolvable name-form reference, the verdict list must
        contain exactly the unresolvable entry (ok = len(verdicts) == 0 is
        False) — proving the guard would abort the build, while the
        resolvable reference in the same command body is not incorrectly
        flagged.

        What python-coder must implement: check_command_reachability() must
        extract and resolve EVERY Workflow(...)/Skill(...) call in a command
        body independently — a resolvable reference elsewhere in the same
        file must not suppress or be conflated with an unresolvable one.
        """
        check_command_reachability = _require_checker()

        command_filename = "mixed-command.md"
        command_body = (
            "# Mixed command\n\n"
            'Workflow("build-feature", { target: $ARGUMENTS })\n\n'
            'Workflow("scripts/workflows/build-feature.js", { target: $ARGUMENTS })\n'
        )
        output_root = _make_output_root(
            tmp_path, command_filename, command_body,
            registered_workflow_names=["build-feature"],
        )

        verdicts = check_command_reachability(output_root)
        ok = len(verdicts) == 0
        assert ok is False, (
            "A tree containing an unresolvable path-form target must yield "
            f"ok=False (non-empty verdicts). Got verdicts: {verdicts}"
        )
        targets_flagged = {v.get("target") for v in verdicts}
        assert "scripts/workflows/build-feature.js" in targets_flagged, (
            f"The unresolvable path-form target must be flagged. "
            f"Flagged targets: {targets_flagged}"
        )
        assert "build-feature" not in targets_flagged, (
            "The resolvable name-form target in the SAME command body must "
            f"not be flagged. Flagged targets: {targets_flagged}"
        )
