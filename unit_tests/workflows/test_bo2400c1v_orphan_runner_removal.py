"""
MODULE: unit_tests/workflows/test_bo2400c1v_orphan_runner_removal.py
GOAL: Failing (RED) test baseline for BO-2400c-1-v — the orphaned second
    fast-lane runner (templates/workflows-js/fast-lane-build.js) must be
    removed from the package now that the caching layer it alone referenced
    is wired into the lane that actually runs (fast-lane-ship.js, per
    BO-2400c-1-iii), and after the removal nothing may resolve to it: no
    command routes to it, no build/deploy step ships it, and the modules it
    used to justify shipping (scripts/injection_builders.py) must remain
    deployed and executable via their real caller.

ARCHITECTURE (BP-1100f-2 / "deployed" + "reachability" angle mandate):
    Every test in this module runs the REAL scripts/build.py as a subprocess
    against the REAL package template tree, writing to a temporary target
    directory (tempfile-backed, never the source tree or the project root).
    Assertions are then made against the ACTUAL deployed artifacts on disk —
    never against a source-tree read, which is structurally blind to a
    deploy-manifest gap (a file can be deleted from templates/ and still be
    latent in a stale deployed copy, or vice versa be present in templates/
    and simply never wired into any deploy phase).

RED BASELINE (today, before python-coder's removal):
    - templates/workflows-js/fast-lane-build.js still exists on disk, so
      build_workflow_scripts() (globbing templates/workflows-js/*.js) still
      copies it to <target>/.leafcutter/workflows/fast-lane-build.js. Test 1
      and Test 3 assert its ABSENCE from that deployed directory and are
      therefore RED now.
    - Test 2 asserts that the checked-in orphan source file itself no longer
      exists (the AC's literal "it is removed from the package" clause) and
      is therefore RED now for the same reason.

GREEN (after python-coder's removal, per the AC's test_spec):
    - templates/workflows-js/fast-lane-build.js is deleted from the package.
    - The deployed workflows/ directory contains fast-lane-ship.js and does
      NOT contain fast-lane-build.js.
    - scripts/injection_builders.py is still deployed and its real
      ``assemble-bundle`` CLI subcommand still executes successfully — the
      prompt-caching capability the orphan used to be the sole reference to
      is preserved via its new (already-wired, per BO-2400c-1-iii) caller.
    - check_command_reachability() (the real BP-900g-1 guard) reports zero
      unresolvable targets for the real deployed command corpus, and a
      synthetic probe command naming the removed runner by its former
      registry name is flagged as unresolvable — proving nothing can
      dispatch to a file that no longer exists.
"""
# covers: BO-2400c-1-v

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_ORPHAN_SRC = _TEMPLATES_DIR / "workflows-js" / "fast-lane-build.js"
_LIVE_LANE_SRC = _TEMPLATES_DIR / "workflows-js" / "fast-lane-ship.js"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from build_phases import check_command_reachability as _CHECK_REACHABILITY
except ImportError:
    _CHECK_REACHABILITY = None  # type: ignore[assignment]


def _run_real_build(tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the real scripts/build.py against the real template tree.

    Writes to a fresh temporary target directory with the workflows feature
    explicitly enabled (a supported, schema-documented config toggle), so the
    deployed <target>/.leafcutter/workflows/ registry is populated exactly as
    it would be for a consumer who opts in.

    Args:
        tmp_path: pytest's per-test temporary directory fixture.

    Returns:
        A (completed_process, output_root) tuple, where output_root is the
        real deployed ``.leafcutter`` directory under the target.
    """
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
    return result, target_dir / ".leafcutter"


# ===========================================================================
# Test 1 (test_spec): deployed layout has no orphaned fast-lane runner
# angle: deployed
# ===========================================================================


def test_deployed_layout_has_no_orphaned_fast_lane_runner(tmp_path):
    # covers: BO-2400c-1-v
    # angle: deployed
    """After a real build, the deployed workflows/ directory contains the
    shipping lane (fast-lane-ship.js) and no second fast-lane runner.

    RED now: templates/workflows-js/fast-lane-build.js still exists, so the
    real build still deploys it to <output_root>/workflows/fast-lane-build.js.
    """
    result, output_root = _run_real_build(tmp_path)
    assert result.returncode == 0, (
        "Sanity check failed: a clean real build must exit 0 before this "
        f"test can assert on its deployed output. stdout (last 800): "
        f"{result.stdout[-800:]}\nstderr (last 800): {result.stderr[-800:]}"
    )

    deployed_workflows = output_root / "workflows"
    assert deployed_workflows.is_dir(), (
        f"Expected a deployed workflows directory at {deployed_workflows} "
        "(workflows.enabled=true was set for this build)."
    )

    deployed_live_lane = deployed_workflows / "fast-lane-ship.js"
    assert deployed_live_lane.exists(), (
        f"Expected the shipping lane to be deployed at {deployed_live_lane}. "
        "This is a sanity check that the deploy phase actually ran, "
        "independent of the orphan-removal assertion below."
    )

    deployed_orphan = deployed_workflows / "fast-lane-build.js"
    assert not deployed_orphan.exists(), (
        f"The orphaned second fast-lane runner is still deployed at "
        f"{deployed_orphan}. Per BO-2400c-1-v, now that fast-lane-ship.js "
        "consumes the prompt-caching layer (BO-2400c-1-iii), "
        "templates/workflows-js/fast-lane-build.js must be deleted from the "
        "package so no build/deploy step ships it in parallel with the lane "
        "that runs."
    )


# ===========================================================================
# Test 2 (test_spec): no command or workflow routes to the removed runner
# angle: reachability
# ===========================================================================


def test_no_command_or_workflow_routes_to_the_removed_runner(tmp_path):
    # covers: BO-2400c-1-v
    # angle: reachability
    """No command template, workflow registry entry, or deploy manifest
    resolves to the removed runner, so nothing can dispatch a file that no
    longer exists.

    Invokes the real production entry points: (1) scripts/build.py itself,
    via subprocess, to produce the real deployed command/workflow corpus, and
    (2) check_command_reachability() — the real BP-900g-1 guard whose
    non-empty result is what build.py's own control flow already treats as a
    build-failing condition (see
    unit_tests/build_guards/test_command_reachability_guard.py::
    TestBuildExitsNonZeroOnUnresolvableTarget). This test does not merely
    call the guard function in isolation: it also asserts that if some
    template still names the removed runner as a handoff target, the guard
    (the thing build.py's exit code is conditioned on) actually flags it —
    i.e. the removal is a *registry* absence, not just a source-tree absence.

    RED now: templates/workflows-js/fast-lane-build.js still exists on disk
    (the AC's literal "it is removed from the package" clause is not yet
    satisfied), so the first assertion below fails.
    """
    if _CHECK_REACHABILITY is None:
        pytest.fail(
            "check_command_reachability not importable from build_phases — "
            "this guard must already exist (BP-900g-1) for this test to run."
        )

    # (1) The orphan's own source file must be gone from the package. A file
    # that still exists in templates/ can always be reintroduced as a
    # dispatch target by a future edit; the AC's criterion is unconditional
    # removal, not merely "nothing currently points at it".
    assert not _ORPHAN_SRC.exists(), (
        f"The orphaned runner source still exists at {_ORPHAN_SRC}. Per "
        "BO-2400c-1-v this file must be removed from the package entirely, "
        "not merely left un-dispatched."
    )
    assert _LIVE_LANE_SRC.exists(), (
        f"Sanity check: the shipping lane must still exist at "
        f"{_LIVE_LANE_SRC} — this test is about removing the orphan, not "
        "the lane that runs."
    )

    # (2) Build the real deployed corpus and confirm the real reachability
    # guard reports zero unresolvable targets against it (nothing dangling).
    result, output_root = _run_real_build(tmp_path)
    assert result.returncode == 0, (
        "Sanity check failed: a clean real build must exit 0. "
        f"stdout (last 800): {result.stdout[-800:]}\n"
        f"stderr (last 800): {result.stderr[-800:]}"
    )
    verdicts = _CHECK_REACHABILITY(output_root, {"workflows": {"enabled": True}})
    dangling_fast_lane_build = [
        v for v in verdicts
        if "fast-lane-build" in str(v.get("target", ""))
    ]
    assert not dangling_fast_lane_build, (
        "The real deployed command corpus must contain no handoff target "
        f"naming the removed runner. Got: {dangling_fast_lane_build}"
    )

    # (3) Prove the removal is a genuine registry absence: a synthetic probe
    # command naming the former runner by its registry (name-form) identity
    # must be flagged as UNRESOLVABLE post-removal, because no
    # <output_root>/workflows/fast-lane-build.js exists to satisfy it. This
    # is the "nothing can dispatch a file that no longer exists" clause
    # exercised against the real, already-deployed registry rather than a
    # synthetic one.
    probe = output_root / "commands" / "zz-bo2400c1v-probe.md"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text(
        '# Probe\n\nWorkflow("fast-lane-build", { ac: $ARGUMENTS })\n',
        encoding="utf-8",
    )
    try:
        probe_verdicts = _CHECK_REACHABILITY(
            output_root, {"workflows": {"enabled": True}}
        )
    finally:
        probe.unlink(missing_ok=True)

    flagged = [v for v in probe_verdicts if v.get("target") == "fast-lane-build"]
    assert flagged, (
        "A probe command naming 'fast-lane-build' as a Workflow() target "
        "must be flagged as unresolvable once the orphan is removed and no "
        "output_root/workflows/fast-lane-build.js is deployed. Got no "
        f"matching verdict among: {probe_verdicts}"
    )


# ===========================================================================
# Test 3 (test_spec): injection_builders.py still deployed after removal
# angle: deployed
# ===========================================================================


def test_injection_builders_still_deployed_after_the_removal(tmp_path):
    # covers: BO-2400c-1-v
    # angle: deployed
    """The prompt-caching module is still present and executable in the
    deployed layout after the orphan is gone, so removing its former caller
    (fast-lane-build.js) did not remove its reason to ship.

    Runs the real build, then invokes the REAL deployed
    scripts/injection_builders.py's ``assemble-bundle`` CLI subcommand with
    real temporary layer files and asserts it actually executes and prints a
    bundle — not merely that the file exists on disk. Also asserts the
    orphan is absent from the deployed workflows directory, since this
    test's premise ("after the removal") does not hold until that is true.

    RED now: templates/workflows-js/fast-lane-build.js still exists, so the
    "orphan absent" assertion fails even though injection_builders.py is
    already (and independently) deployed today.
    """
    result, output_root = _run_real_build(tmp_path)
    assert result.returncode == 0, (
        "Sanity check failed: a clean real build must exit 0. "
        f"stdout (last 800): {result.stdout[-800:]}\n"
        f"stderr (last 800): {result.stderr[-800:]}"
    )

    deployed_workflow_orphan = output_root / "workflows" / "fast-lane-build.js"
    assert not deployed_workflow_orphan.exists(), (
        f"Precondition for this test ('after the removal') is not yet met: "
        f"{deployed_workflow_orphan} is still deployed. Remove "
        "templates/workflows-js/fast-lane-build.js before this test's "
        "injection_builders assertions can be meaningfully green."
    )

    deployed_injection_builders = output_root.parent / "scripts" / "injection_builders.py"
    assert deployed_injection_builders.exists(), (
        f"Expected scripts/injection_builders.py to still be deployed at "
        f"{deployed_injection_builders} after the orphan's removal — the "
        "AGENT_SUPPORT_SCRIPT_FILES deploy-manifest justification for this "
        "module must be re-pointed at fast-lane-ship.js (its real caller "
        "per BO-2400c-1-iii), not dropped along with the orphan."
    )

    # Exercise the REAL deployed copy's real CLI surface — not the source
    # tree — with real temporary layer files, and read its stdout back.
    arch_file = tmp_path / "architecture.txt"
    high_level_file = tmp_path / "high_level.txt"
    prior_tests_file = tmp_path / "prior_tests.txt"
    arch_file.write_text("ARCH LAYER CONTENT\n", encoding="utf-8")
    high_level_file.write_text("HIGH LEVEL LAYER CONTENT\n", encoding="utf-8")
    prior_tests_file.write_text("PRIOR TESTS LAYER CONTENT\n", encoding="utf-8")

    cli_result = subprocess.run(
        [
            sys.executable,
            str(deployed_injection_builders),
            "assemble-bundle",
            "--architecture",
            str(arch_file),
            "--high-level",
            str(high_level_file),
            "--prior-tests",
            str(prior_tests_file),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert cli_result.returncode == 0, (
        "The deployed scripts/injection_builders.py assemble-bundle CLI "
        f"must execute successfully. stdout: {cli_result.stdout[-500:]}\n"
        f"stderr: {cli_result.stderr[-500:]}"
    )
    assert "ARCH LAYER CONTENT" in cli_result.stdout, (
        "The deployed CLI's assembled bundle must include the architecture "
        f"layer content it was given. Got stdout: {cli_result.stdout[-500:]}"
    )
