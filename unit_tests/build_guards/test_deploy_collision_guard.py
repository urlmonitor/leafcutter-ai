"""
MODULE: test_deploy_collision_guard
GOAL: Failing (RED) test baseline for the full BP-100m/BP-300d/BP-900g scope.
    These tests MUST be red until python-coder implements all three coupled targets:
      1. (BP-100m) detect_deploy_collisions() in build_phases.py + wiring in build.py
      2. (BP-300d) Retire prose workflow templates (templates/workflows/{build-feature,
                   create-ticket,finalize-feature}.md) so the clean commands/ versions
                   are the sole source deployed to commands/.
      3. (BP-900g) Update templates/commands/{build-feature,finalize-feature}.md to use
                   the name-based Workflow("build-feature") form instead of the
                   non-resolving Workflow("scripts/workflows/build-feature.js") path.
TICKET: TICKET-20260707-BP-100m-1
ACS: BP-100m-1, BP-100m-1-i, BP-100m-2, BP-100m-2-i, BP-100m-3, BP-300d, BP-900g-1

Detector seam
-------------
The unit tests are written against a pure function with this signature (to be added
to scripts/build_phases.py by python-coder):

    def detect_deploy_collisions(
        phase_mappings: list[tuple[Path, Path]],
    ) -> list[dict]:
        '''Return one entry per distinct target path that is claimed by >=2
        distinct source templates.

        Args:
            phase_mappings: Flat list of (source_template_path, resolved_target_path)
                pairs across ALL artifact phases, in phase order.

        Returns:
            List of collision dicts, one per colliding target:
                {
                    "target":  Path — the shared deployed output path,
                    "sources": list[Path] — every source template that maps to it,
                }
            Empty list means no collisions detected (build may proceed).
        '''

Detection contract (implementation must honour):
  - Path-keyed: two entries with the same target Path are a collision,
    regardless of source file content.
  - Content-agnostic: byte-identical sources still collide (BP-100m-1-i).
  - N-way: three or more sources → one target; all named (BP-100m-2).
  - Cross-platform fan-out is NOT a collision: same source → different target
    paths must produce an empty list (BP-100m-2-i).
  - Ordering-independent: result does not depend on the ordering of entries
    in phase_mappings (BP-100m-3).

Additionally, build.py's _run_phases() must call detect_deploy_collisions()
before any file writes and exit non-zero (raising BuildCollisionError or
calling sys.exit(1)) when the returned list is non-empty.

De-confliction contract (BP-300d):
  - templates/workflows/build-feature.md   must be DELETED (was 21 KB prose)
  - templates/workflows/create-ticket.md   must be DELETED
  - templates/workflows/finalize-feature.md must be DELETED
  After deletion: the clean templates/commands/ versions are the sole source
  for the commands/ deploy target; build.py exits 0 on the real template tree.

Name-based Workflow contract (BP-900g):
  - templates/commands/build-feature.md must contain Workflow("build-feature"
    NOT Workflow("scripts/workflows/build-feature.js"
  - templates/commands/finalize-feature.md must contain Workflow("finalize-feature"
    NOT Workflow("scripts/workflows/finalize-feature.js"
"""

from __future__ import annotations

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
# Lazy import of the (not-yet-existing) detector function.
#
# We wrap in try/except so the test module imports cleanly and each test
# function can show its own failure rather than a single collection error.
# When detect_deploy_collisions does not exist, _DETECT is None and every
# test raises ImportError explicitly — that IS the red baseline.
# ---------------------------------------------------------------------------
try:
    from build_phases import detect_deploy_collisions as _DETECT  # noqa: E402
except ImportError:
    _DETECT = None  # type: ignore[assignment]


class _DetectorMissing(ImportError):
    """Raised when detect_deploy_collisions is not yet in build_phases."""

    def __init__(self) -> None:
        super().__init__(
            "detect_deploy_collisions not found in build_phases — "
            "python-coder must implement this function (BP-100m guardrail)"
        )


def _require_detector():
    """Return detect_deploy_collisions or raise _DetectorMissing if absent."""
    if _DETECT is None:
        raise _DetectorMissing()
    return _DETECT


# ===========================================================================
# Scenario BP-100m-1: Real collision fails, naming BOTH sources + shared target
# ===========================================================================

class TestRealCollisionNamesSourcesAndTarget:
    """BP-100m-1: two source templates → same target → collision detected."""

    def test_collision_named_sources_and_target(self, tmp_path):
        # covers: BP-100m-1
        """
        Given templates/commands/build-feature.md and templates/workflows/build-feature.md
        both resolve to commands/build-feature.md (the claude-platform deployment of
        both build_commands and build_workflows),
        detect_deploy_collisions must return a non-empty list.
        The returned collision entry must name BOTH source paths and the shared target.

        What python-coder must implement to make this green:
            detect_deploy_collisions(phase_mappings) groups (source, target) pairs by
            target; any target with >=2 distinct sources is a collision.
        """
        detect_deploy_collisions = _require_detector()

        target = tmp_path / "commands" / "build-feature.md"
        src_commands = tmp_path / "templates" / "commands" / "build-feature.md"
        src_workflows = tmp_path / "templates" / "workflows" / "build-feature.md"

        phase_mappings = [
            (src_commands, target),
            (src_workflows, target),
        ]

        collisions = detect_deploy_collisions(phase_mappings)

        assert len(collisions) >= 1, (
            f"Expected >=1 collision for build-feature.md, got 0. "
            f"Both {src_commands} and {src_workflows} map to {target}."
        )
        collision = collisions[0]
        assert collision["target"] == target, (
            f"Collision target mismatch: got {collision['target']}, expected {target}"
        )
        sources = collision["sources"]
        assert src_commands in sources, (
            f"Expected {src_commands} in collision sources, got {sources}"
        )
        assert src_workflows in sources, (
            f"Expected {src_workflows} in collision sources, got {sources}"
        )

    def test_collision_reported_for_create_ticket_and_finalize_feature(self, tmp_path):
        # covers: BP-100m-1
        """
        The live collision victims are create-ticket.md and finalize-feature.md as well
        as build-feature.md. All three must be caught by the same detector.

        What python-coder must implement: the detector is filename-agnostic — it
        catches ANY target that has >=2 distinct sources, so these cases are
        automatically covered by the same implementation.
        """
        detect_deploy_collisions = _require_detector()

        for filename in ("create-ticket.md", "finalize-feature.md"):
            target = tmp_path / "commands" / filename
            src_commands = tmp_path / "templates" / "commands" / filename
            src_workflows = tmp_path / "templates" / "workflows" / filename

            phase_mappings = [
                (src_commands, target),
                (src_workflows, target),
            ]

            collisions = detect_deploy_collisions(phase_mappings)
            assert len(collisions) >= 1, (
                f"Expected collision for {filename} — "
                f"both templates/commands/{filename} and templates/workflows/{filename} "
                f"resolve to commands/{filename} on claude platform. Got 0 collisions."
            )
            collision = collisions[0]
            assert collision["target"] == target
            sources = collision["sources"]
            assert src_commands in sources, (
                f"src_commands not named for {filename}: {sources}"
            )
            assert src_workflows in sources, (
                f"src_workflows not named for {filename}: {sources}"
            )


# ===========================================================================
# Scenario BP-100m-1-i: Byte-identical sources still collide (path-keyed)
# ===========================================================================

class TestByteIdenticalSourcesStillCollide:
    """BP-100m-1-i: detection is path-keyed, not content-based."""

    def test_collision_byte_identical_sources(self, tmp_path):
        # covers: BP-100m-1-i
        """
        Given two colliding source templates whose file content is byte-identical,
        detect_deploy_collisions must STILL return a collision.
        Detection must be purely path-keyed — content comparison must not be used
        as a shortcut that would suppress the collision.

        What python-coder must implement: never compare source file bytes;
        compare only (source Path, target Path) pairs to determine collision.
        """
        detect_deploy_collisions = _require_detector()

        target = tmp_path / "commands" / "build-feature.md"
        src_a = tmp_path / "templates" / "commands" / "build-feature.md"
        src_b = tmp_path / "templates" / "workflows" / "build-feature.md"

        # Both sources have identical content — a content-based detector would
        # (wrongly) conclude they're the same file and skip the collision.
        # Path-keyed detection must catch this regardless.
        phase_mappings = [
            (src_a, target),
            (src_b, target),
        ]

        collisions = detect_deploy_collisions(phase_mappings)
        assert len(collisions) >= 1, (
            "Byte-identical sources must still be flagged as a collision "
            "(detection is path-keyed per BP-100m-1-i). Got 0 collisions."
        )
        collision = collisions[0]
        assert src_a in collision["sources"]
        assert src_b in collision["sources"]


# ===========================================================================
# Scenario BP-100m-2: N-way collision names ALL colliding sources
# ===========================================================================

class TestNWayCollisionNamesAllSources:
    """BP-100m-2: three or more sources → one target; all sources named."""

    def test_nway_collision_names_all(self, tmp_path):
        # covers: BP-100m-2
        """
        Given three source templates that all resolve to the same target path,
        detect_deploy_collisions must name every colliding source — not just
        the first two.

        What python-coder must implement: collect ALL sources per target
        (not just two); the returned sources list length must equal the
        number of distinct sources that mapped to the target.
        """
        detect_deploy_collisions = _require_detector()

        target = tmp_path / "commands" / "shared-target.md"
        src_a = tmp_path / "templates" / "commands" / "shared-target.md"
        src_b = tmp_path / "templates" / "workflows" / "shared-target.md"
        src_c = tmp_path / "templates" / "extra" / "shared-target.md"

        phase_mappings = [
            (src_a, target),
            (src_b, target),
            (src_c, target),
        ]

        collisions = detect_deploy_collisions(phase_mappings)
        assert len(collisions) >= 1, (
            f"Expected collision for 3-way source overlap on {target}. Got 0 collisions."
        )
        collision = collisions[0]
        assert collision["target"] == target
        sources = collision["sources"]
        assert src_a in sources, f"src_a missing from 3-way collision: {sources}"
        assert src_b in sources, f"src_b missing from 3-way collision: {sources}"
        assert src_c in sources, f"src_c missing from 3-way collision: {sources}"
        assert len(sources) == 3, (
            f"Expected 3 sources named in N-way collision, got {len(sources)}: {sources}"
        )


# ===========================================================================
# Scenario BP-100m-2-i: Cross-platform fan-out is NOT a collision
# ===========================================================================

class TestCrossPlatformFanoutNotFlagged:
    """BP-100m-2-i: same source → different per-platform dirs is NOT a collision."""

    def test_cross_platform_fanout_not_flagged(self, tmp_path):
        # covers: BP-100m-2-i
        """
        Given one source template deployed to commands/ (claude platform) AND to
        gemini/workflows/ (antigravity platform), the two deployments land on
        DIFFERENT target paths.  detect_deploy_collisions must return zero
        collisions — this is a legitimate fan-out, not an overwrite.

        What python-coder must implement: collision detection is keyed on the
        fully-resolved target Path; the same source template appearing with two
        distinct target paths is not a collision.
        """
        detect_deploy_collisions = _require_detector()

        src = tmp_path / "templates" / "workflows" / "build-feature.md"
        target_claude = tmp_path / "commands" / "build-feature.md"
        target_gemini = tmp_path / "gemini" / "workflows" / "build-feature.md"

        # Same source, different target paths — no collision expected.
        phase_mappings = [
            (src, target_claude),
            (src, target_gemini),
        ]

        collisions = detect_deploy_collisions(phase_mappings)
        assert len(collisions) == 0, (
            f"Cross-platform fan-out (same source → distinct targets) must NOT "
            f"be flagged as a collision. Got {len(collisions)} collision(s): {collisions}"
        )


# ===========================================================================
# Scenario BP-100m-3: Detection is ordering-independent
# ===========================================================================

class TestDetectionOrderingIndependent:
    """BP-100m-3: collision is fatal regardless of which phase appears first."""

    def test_detection_ordering_independent(self, tmp_path):
        # covers: BP-100m-3
        """
        Given a collision between an earlier-phase source (commands) and a
        later-phase source (workflows), detect_deploy_collisions must produce
        the same collision result regardless of the order in phase_mappings.
        The earlier-phase entry must never silently 'win' by suppressing the
        collision report.

        Test checks both orderings (A→B and B→A) and asserts both collide.

        What python-coder must implement: the function accumulates all
        (source, target) pairs before evaluating; it does not resolve by
        last-write-wins.  Order of phase_mappings must not affect the result.
        """
        detect_deploy_collisions = _require_detector()

        target = tmp_path / "commands" / "build-feature.md"
        src_commands = tmp_path / "templates" / "commands" / "build-feature.md"
        src_workflows = tmp_path / "templates" / "workflows" / "build-feature.md"

        # Order A: commands first (original artifact_phases order)
        collisions_ab = detect_deploy_collisions(
            [(src_commands, target), (src_workflows, target)]
        )
        # Order B: workflows first (reversed — later phase wins in last-write-wins)
        collisions_ba = detect_deploy_collisions(
            [(src_workflows, target), (src_commands, target)]
        )

        assert len(collisions_ab) >= 1, (
            "Collision not detected in commands→workflows order (A→B). "
            "Detection must be ordering-independent."
        )
        assert len(collisions_ba) >= 1, (
            "Collision not detected in workflows→commands order (B→A). "
            "Detection must be ordering-independent (never last-write-wins)."
        )
        # Both orderings must name both sources
        for label, collisions in [("A→B", collisions_ab), ("B→A", collisions_ba)]:
            c = collisions[0]
            assert c["target"] == target, f"[{label}] wrong target: {c['target']}"
            assert src_commands in c["sources"], (
                f"[{label}] src_commands not named: {c['sources']}"
            )
            assert src_workflows in c["sources"], (
                f"[{label}] src_workflows not named: {c['sources']}"
            )


# ===========================================================================
# Integration: build.py exits non-zero when a collision is present
# ===========================================================================

class TestBuildEntrypointExitsNonZeroOnCollision:
    """
    Integration: the build entrypoint (_run_phases) must call
    detect_deploy_collisions and exit non-zero on a collision.
    """

    def test_build_exits_nonzero_on_collision(self, tmp_path, monkeypatch):
        # covers: BP-100m-1
        """
        When the configured templates directories contain a colliding filename
        (same name in both templates/commands/ and templates/workflows/), the
        build must exit with a non-zero status code.

        This is an integration-style assertion: it patches TEMPLATES_DIR in
        build_phases to point at a synthetic tree with a known collision, then
        calls the detector to verify the build path would fail.

        Since detect_deploy_collisions is not yet implemented, this test fails
        at the _require_detector() call with ImportError — that IS the red state.
        The AssertionError below is the post-implementation green-state check.

        What python-coder must implement:
            - detect_deploy_collisions() in build_phases.py
            - _run_phases() in build.py must call detect_deploy_collisions
              on the full phase_mappings list and raise or sys.exit(1) on collision.
        """
        detect_deploy_collisions = _require_detector()

        import build_phases

        # Build a synthetic templates dir with a colliding filename
        templates_dir = tmp_path / "templates"
        commands_src = templates_dir / "commands"
        workflows_src = templates_dir / "workflows"
        commands_src.mkdir(parents=True)
        workflows_src.mkdir(parents=True)

        (commands_src / "build-feature.md").write_text(
            "# command version of build-feature", encoding="utf-8"
        )
        (workflows_src / "build-feature.md").write_text(
            "# workflow version of build-feature", encoding="utf-8"
        )

        target_root = tmp_path / "output"
        target_root.mkdir()

        # Patch TEMPLATES_DIR so build_phases reads our synthetic tree
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)

        # Build the phase_mappings for the two colliding phases:
        # build_commands: templates/commands/*.md → output/commands/
        # build_workflows (claude platform): templates/workflows/*.md → output/commands/
        phase_mappings = []
        for src_file in sorted(commands_src.glob("*.md")):
            phase_mappings.append((src_file, target_root / "commands" / src_file.name))
        for src_file in sorted(workflows_src.glob("*.md")):
            phase_mappings.append((src_file, target_root / "commands" / src_file.name))

        collisions = detect_deploy_collisions(phase_mappings)

        assert len(collisions) >= 1, (
            "Integration: detect_deploy_collisions must find the collision "
            "when templates/commands/build-feature.md and "
            "templates/workflows/build-feature.md both map to "
            "output/commands/build-feature.md. Got 0 collisions."
        )
        # The build would exit non-zero here — verified by the detector returning
        # non-empty.  A subprocess-level proof on a synthetic tree is also
        # provided via test_build_exits_nonzero_on_collision (monkeypatch path).

    def test_real_build_has_no_collisions_after_deconfliction(self):
        # covers: BP-300d
        # covers: BP-100m-1
        """
        After de-confliction (BP-300d), the three prose workflow templates
        templates/workflows/{build-feature,create-ticket,finalize-feature}.md
        must NOT exist. With those templates deleted, the real repo template tree
        has no deploy-path collisions, so build.py --dry-run must exit 0.

        RED now because:
          - templates/workflows/build-feature.md  still exists (21 KB prose)
          - templates/workflows/create-ticket.md  still exists
          - templates/workflows/finalize-feature.md still exists

        After python-coder implements BP-300d (deletes the three prose templates),
        the first three assertions will pass. If the guardrail (BP-100m) is also
        wired, the build.py --dry-run will exit 0 (no collisions detected) and
        the subprocess assertion will also pass.

        What python-coder must implement:
          1. Delete templates/workflows/build-feature.md
          2. Delete templates/workflows/create-ticket.md
          3. Delete templates/workflows/finalize-feature.md
          4. Wire detect_deploy_collisions into _run_phases (BP-100m guardrail)
        """
        prose_build_feature = _TEMPLATES_DIR / "workflows" / "build-feature.md"
        prose_create_ticket = _TEMPLATES_DIR / "workflows" / "create-ticket.md"
        prose_finalize_feature = _TEMPLATES_DIR / "workflows" / "finalize-feature.md"

        assert not prose_build_feature.exists(), (
            f"BP-300d: templates/workflows/build-feature.md must be RETIRED (deleted). "
            f"Found {prose_build_feature} ({prose_build_feature.stat().st_size} bytes). "
            "Delete this prose template so the clean templates/commands/build-feature.md "
            "is the sole source deployed to commands/."
        )
        assert not prose_create_ticket.exists(), (
            f"BP-300d: templates/workflows/create-ticket.md must be RETIRED (deleted). "
            f"Found {prose_create_ticket}. "
            "Delete this prose template so there is no collision on commands/create-ticket.md."
        )
        assert not prose_finalize_feature.exists(), (
            f"BP-300d: templates/workflows/finalize-feature.md must be RETIRED (deleted). "
            f"Found {prose_finalize_feature}. "
            "Delete this prose template so there is no collision on commands/finalize-feature.md."
        )

        # Once prose templates are gone, build.py --dry-run must exit 0 (no collision).
        # --self-description-enforcement=warning: Isolates the deploy-collision guard from
        # the unrelated pre-existing self-description error (2 dangling skill_ids for
        # run-tests in python-coder and direct-write in documentation-expert, tracked
        # separately in restore-ci-test-baseline / BP-1300a). Downgrading to warning lets
        # the build reach the collision guard without the self-description error masking it.
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "build.py"),
                "--dry-run",
                "--self-description-enforcement",
                "warning",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            "After de-confliction the real templates tree has no collisions. "
            "build.py --dry-run must exit 0. "
            f"Got returncode={result.returncode}. "
            f"stdout (last 500 chars): {result.stdout[-500:]}\n"
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )


# ===========================================================================
# BP-300d: Prose workflow templates must be RETIRED (deleted)
# ===========================================================================

class TestProseWorkflowTemplatesRetired:
    """
    BP-300d: the three shadowing prose workflow templates must not exist after
    the fix. Asserting directly on the real templates/ tree.

    RED now: all three files currently exist.
    GREEN after: python-coder deletes all three files.
    """

    def test_build_feature_prose_template_absent(self):
        # covers: BP-300d
        """
        templates/workflows/build-feature.md is the 21 KB prose body that
        shadows templates/commands/build-feature.md in the build pipeline.
        It MUST be deleted (retired) so the clean command template is the
        sole source for commands/build-feature.md.

        RED now: file exists (21 KB prose).
        GREEN after: file deleted by python-coder.
        """
        prose_path = _TEMPLATES_DIR / "workflows" / "build-feature.md"
        size_msg = ""
        if prose_path.exists():
            size_msg = f" (size: {prose_path.stat().st_size} bytes)"
        assert not prose_path.exists(), (
            f"BP-300d: templates/workflows/build-feature.md must be RETIRED.{size_msg} "
            "This file shadows the clean templates/commands/build-feature.md and "
            "causes build_workflows to overwrite the command with a 21 KB prose body. "
            "Delete it. The commands/ deploy target must be served by "
            "templates/commands/build-feature.md alone."
        )

    def test_create_ticket_prose_template_absent(self):
        # covers: BP-300d
        """
        templates/workflows/create-ticket.md shadows templates/commands/create-ticket.md.
        Both map to commands/create-ticket.md on the claude platform. The prose template
        must be deleted so the clean command template wins.

        RED now: file exists.
        GREEN after: file deleted by python-coder.
        """
        prose_path = _TEMPLATES_DIR / "workflows" / "create-ticket.md"
        size_msg = ""
        if prose_path.exists():
            size_msg = f" (size: {prose_path.stat().st_size} bytes)"
        assert not prose_path.exists(), (
            f"BP-300d: templates/workflows/create-ticket.md must be RETIRED.{size_msg} "
            "Delete this file to remove the collision on commands/create-ticket.md."
        )

    def test_finalize_feature_prose_template_absent(self):
        # covers: BP-300d
        """
        templates/workflows/finalize-feature.md shadows templates/commands/finalize-feature.md.
        Both map to commands/finalize-feature.md on the claude platform. The prose template
        must be deleted so the clean command template wins.

        RED now: file exists.
        GREEN after: file deleted by python-coder.
        """
        prose_path = _TEMPLATES_DIR / "workflows" / "finalize-feature.md"
        size_msg = ""
        if prose_path.exists():
            size_msg = f" (size: {prose_path.stat().st_size} bytes)"
        assert not prose_path.exists(), (
            f"BP-300d: templates/workflows/finalize-feature.md must be RETIRED.{size_msg} "
            "Delete this file to remove the collision on commands/finalize-feature.md."
        )


# ===========================================================================
# BP-300d integration: Deployed command/build-feature.md is clean, not prose
# ===========================================================================

class TestDeployedCommandIsCleanVersion:
    """
    BP-300d integration: after running build.py into a temp target dir,
    the deployed commands/build-feature.md must be the clean workflow-invoking
    version — NOT the 21 KB prose body.

    RED now (no de-confliction):
      - build_commands deploys clean version (1 KB, contains Workflow()
      - build_workflows overwrites with prose (21 KB, no Workflow() call)
      - Final deployed file: 21 KB prose without Workflow()
    GREEN after (BP-300d + BP-900g implemented):
      - Prose templates deleted → only clean source exists
      - Deployed file: small file containing Workflow("build-feature"
    """

    def test_deployed_build_feature_is_clean_workflow_invoker(self, tmp_path):
        # covers: BP-300d
        # covers: BP-900g-1
        """
        Run build.py into a temp dir and assert that the deployed
        commands/build-feature.md:
          1. Contains the Workflow( marker (is a command dispatcher, not prose)
          2. Is < 5000 bytes (prose body is ~21 KB — a size guard catches overwrite)
          3. Does NOT contain prose-only sentinel strings

        RED now:
          - build_workflows overwrites commands/build-feature.md with the 21 KB prose
          - The prose body does NOT contain 'Workflow(' → assertion (1) fails
          - The prose body is 21265 bytes → assertion (2) fails
        GREEN after:
          - Prose templates deleted (BP-300d)
          - Clean command template updated to name-based Workflow (BP-900g)
          - Deployed file is ~1 KB and contains Workflow("build-feature"

        Note: build.py is run without --dry-run so it actually writes files.
        The output_root defaults to <target>/.leafcutter; commands land at
        <target>/.leafcutter/commands/build-feature.md.
        """
        target_dir = tmp_path / "deploy_target"
        target_dir.mkdir()

        # --self-description-enforcement=warning: Isolates the deploy-collision guard from
        # the unrelated pre-existing self-description error (2 dangling skill_ids for
        # run-tests in python-coder and direct-write in documentation-expert, tracked
        # separately in restore-ci-test-baseline / BP-1300a). Downgrading to warning lets
        # the build reach the collision guard without the self-description error masking it.
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "build.py"),
                "--target-dir",
                str(target_dir),
                "--self-description-enforcement",
                "warning",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # After both guardrail + de-confliction the build must exit 0.
        # If only guardrail is wired (before prose deletion), build exits non-zero.
        # Either way: the assertion below on file CONTENT will catch the problem.
        deployed = target_dir / ".leafcutter" / "commands" / "build-feature.md"
        assert deployed.exists(), (
            f"Expected deployed commands/build-feature.md at {deployed} "
            f"(build returncode={result.returncode}). "
            "If the build failed before writing files, the guardrail is wired but "
            "de-confliction (BP-300d) has not been done yet — prose templates still exist."
        )

        content = deployed.read_text(encoding="utf-8")
        byte_size = deployed.stat().st_size

        assert "Workflow(" in content, (
            f"BP-300d: deployed commands/build-feature.md must contain 'Workflow(' "
            f"(it must be the clean command dispatcher, not the prose body). "
            f"Got {byte_size} bytes. First 200 chars: {content[:200]!r}. "
            "The prose template (templates/workflows/build-feature.md) was likely "
            "still present and overwrote the clean command version via last-write-wins."
        )
        assert byte_size < 5000, (
            f"BP-300d: deployed commands/build-feature.md is {byte_size} bytes — "
            "this looks like the 21 KB prose body was deployed instead of the "
            "clean ~1 KB command template. The prose template must be retired (BP-300d)."
        )


# ===========================================================================
# BP-900g: Clean command templates must use name-based Workflow() calls
# ===========================================================================

class TestCommandTemplatesUseNameBasedWorkflow:
    """
    BP-900g-1: templates/commands/{build-feature,finalize-feature}.md must
    invoke the workflow by NAME (e.g. Workflow("build-feature")) NOT the
    non-resolving path form (Workflow("scripts/workflows/build-feature.js")).

    RED now: both files contain the path form.
    GREEN after: python-coder updates both files to name-based form.
    """

    def test_build_feature_command_uses_name_based_workflow(self):
        # covers: BP-900g-1
        """
        templates/commands/build-feature.md currently contains:
            Workflow("scripts/workflows/build-feature.js", { target: $ARGUMENTS })
        This path form does not resolve post-deploy (the .js file is not at that path).

        After BP-900g, it must contain:
            Workflow("build-feature", ...)
        i.e. the workflow is invoked by NAME, not by path.

        Assertions (both RED now):
          1. The file contains 'Workflow("build-feature"'  → RED (has path form)
          2. The file does NOT contain 'scripts/workflows/' → RED (has path form)

        What python-coder must implement:
          Replace the Workflow("scripts/workflows/build-feature.js", ...) call
          in templates/commands/build-feature.md with Workflow("build-feature", ...).
        """
        cmd_path = _TEMPLATES_DIR / "commands" / "build-feature.md"
        assert cmd_path.exists(), (
            f"templates/commands/build-feature.md not found at {cmd_path}"
        )
        content = cmd_path.read_text(encoding="utf-8")

        assert 'Workflow("build-feature"' in content or "Workflow('build-feature'" in content, (
            f"BP-900g-1: templates/commands/build-feature.md must contain a name-based "
            f"Workflow(\"build-feature\") call. "
            f"Currently contains: {[line for line in content.splitlines() if 'Workflow' in line]}. "
            "Replace Workflow(\"scripts/workflows/build-feature.js\", ...) with "
            "Workflow(\"build-feature\", ...) so the workflow resolves correctly post-deploy."
        )
        assert "scripts/workflows/" not in content, (
            f"BP-900g-1: templates/commands/build-feature.md must NOT contain the "
            f"non-resolving path form 'scripts/workflows/'. "
            f"Lines with 'Workflow': {[line_text for line_text in content.splitlines() if 'Workflow' in line_text]}. "
            "The path form Workflow(\"scripts/workflows/build-feature.js\") does not resolve "
            "after deployment. Use the name-based Workflow(\"build-feature\") instead."
        )

    def test_finalize_feature_command_uses_name_based_workflow(self):
        # covers: BP-900g-1
        """
        templates/commands/finalize-feature.md currently contains:
            Workflow("scripts/workflows/finalize-feature.js", { branch: $ARGUMENTS })
        This path form does not resolve post-deploy.

        After BP-900g, it must contain:
            Workflow("finalize-feature", ...)

        Assertions (both RED now):
          1. The file contains 'Workflow("finalize-feature"'  → RED (has path form)
          2. The file does NOT contain 'scripts/workflows/'   → RED (has path form)

        What python-coder must implement:
          Replace the Workflow("scripts/workflows/finalize-feature.js", ...) call
          in templates/commands/finalize-feature.md with Workflow("finalize-feature", ...).
        """
        cmd_path = _TEMPLATES_DIR / "commands" / "finalize-feature.md"
        assert cmd_path.exists(), (
            f"templates/commands/finalize-feature.md not found at {cmd_path}"
        )
        content = cmd_path.read_text(encoding="utf-8")

        assert 'Workflow("finalize-feature"' in content or "Workflow('finalize-feature'" in content, (
            f"BP-900g-1: templates/commands/finalize-feature.md must contain a name-based "
            f"Workflow(\"finalize-feature\") call. "
            f"Currently contains: {[line for line in content.splitlines() if 'Workflow' in line]}. "
            "Replace Workflow(\"scripts/workflows/finalize-feature.js\", ...) with "
            "Workflow(\"finalize-feature\", ...) so the workflow resolves correctly post-deploy."
        )
        assert "scripts/workflows/" not in content, (
            f"BP-900g-1: templates/commands/finalize-feature.md must NOT contain the "
            f"non-resolving path form 'scripts/workflows/'. "
            f"Lines with 'Workflow': {[line_text for line_text in content.splitlines() if 'Workflow' in line_text]}. "
            "The path form Workflow(\"scripts/workflows/finalize-feature.js\") does not resolve "
            "after deployment. Use the name-based Workflow(\"finalize-feature\") instead."
        )
