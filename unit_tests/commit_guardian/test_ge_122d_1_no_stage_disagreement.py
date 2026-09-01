"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1_no_stage_disagreement.py
GOAL: Cover GE-122d-1's ``test_no_stage_reports_clean_while_another_reports_contested``
    descriptor: over one real, on-disk collection holding a genuine duplicate
    identifier, the authoring-time stage and the commit-time stage must
    never disagree on whether the current change set is BLOCKED, across
    both the "collision committed, nothing staged" direction and the
    "collision staged" direction.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: GE-122d-1's own amended_by history records that the two
    prior attempts at this test were BOTH structurally incapable of
    failing:
      - Attempt 1 compared ``run_uniqueness_pass``'s own return value to
        itself -- neither stage's real entry point was ever invoked, so no
        fixture could ever produce a disagreement.
      - Attempt 2 (in the sibling module, test_ge_122d_1_single_rule_change.py)
        ran the commit-time CLI with ``cwd`` set to a NON-GIT tempdir, so
        ``_get_staged_paths()`` returned ``None`` and the CLI took its
        fail-open whole-collection fallback -- a code path that only
        exists OUTSIDE a git repository, the opposite of how both stages
        are actually invoked in production.
    The record also names the exact measurement that settles this AC:
    "running BOTH stages against a single root that has a real collision
    and nothing staged, and comparing their exit codes" -- and separately
    warns that "disagreeing the other way is still disagreeing": a fix that
    swings the authoring stage from clean-when-commit-blocks to
    blocking-when-commit-passes is caught by the SAME comparison, run in
    the opposite direction (collision staged).
ARCHITECTURE: Builds one real git repository under ``tempfile``, scaffolds
    all four namespaces GE-122 tracks (docs/acceptance-criteria/<comp>/,
    docs/architecture/adrs/, docs/architecture/diagrams/, tickets/ with a
    real ticket_lifecycle.json) so no namespace is left unresolvable --
    an unscaffolded fixture would make this test vacuous in a NEW way, by
    tripping the authoring hook's "every namespace unresolvable at once"
    escape hatch and reporting a fail-open non-block regardless of the
    fixture under test. Commits a genuine AC-identifier collision (two real
    YAML files both declaring ``id: MATRIX-1``) so the collision exists on
    disk, not as a hand-typed verdict literal. Both real entry points are
    then invoked as actual subprocesses against a scratch copy of the
    deployed-shaped layout (``hooks/`` sibling to
    ``scripts/commit_guardian/``, copied from ``templates/`` -- the same
    deployed shape ``check_identifier_uniqueness_authoring.py``'s own
    ARCHITECTURE note documents for the Claude Code deploy target):
      - the commit-time stage via ``python check_identifier_uniqueness.py``
        (its own documented CLI usage);
      - the authoring-time stage via ``python
        check_identifier_uniqueness_authoring.py`` fed the real PostToolUse
        JSON payload shape on stdin (``{"tool_input": {"file_path": ...}}``)
        -- its own real runner-invocation shape, never an in-process call to
        ``evaluate_identifier_uniqueness``.
    Both subprocesses are invoked with ``cwd`` set to the fixture repo root.
    This is load-bearing, not incidental: ``_get_staged_paths()`` (shared by
    both stages) shells out to ``git diff --cached --name-only`` with NO
    explicit ``cwd`` of its own, so it resolves the staged set from the
    calling PROCESS's actual working directory -- a real PostToolUse
    invocation runs with its cwd inside the edited project for exactly this
    reason. Omitting it here would silently make both stages read an
    unrelated (or non-existent) git context.

DOC_LINKS:
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/hooks/check_identifier_uniqueness_authoring.py
  - unit_tests/commit_guardian/test_ge_122d_1_single_rule_change.py

DECISION HISTORY:
  - 2026-09-01 [test-writer/GE-122d-1]: Rewritten from scratch. The prior
    version (self-comparison of one ``run_uniqueness_pass`` return value)
    is documented above and in this AC's own amended_by history as
    structurally incapable of failing. Verified both directions RED against
    two independent reintroductions of previously-shipped defects before
    confirming GREEN against the current (fixed) hook -- see the sign-off
    comment for the exact mutation diffs and captured red output.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUTHORING_SRC = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"
_SHARED_SRC_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

_SUBPROCESS_TIMEOUT_SECONDS = 30


def _deploy_scratch_layout(scratch_root: Path) -> tuple[Path, Path]:
    """Copy the real templates into a scratch dir shaped like the deployed
    layout (``hooks/`` sibling to ``scripts/commit_guardian/``).

    Args:
        scratch_root: Directory to build the scratch deploy tree under.

    Returns:
        (commit_stage_script_path, authoring_hook_script_path)
    """
    scripts_dir = scratch_root / "scripts" / "commit_guardian"
    scripts_dir.mkdir(parents=True)
    for src in _SHARED_SRC_DIR.glob("*.py"):
        shutil.copy2(src, scripts_dir / src.name)

    hooks_dir = scratch_root / "hooks"
    hooks_dir.mkdir(parents=True)
    authoring_dst = hooks_dir / _AUTHORING_SRC.name
    shutil.copy2(_AUTHORING_SRC, authoring_dst)

    return scripts_dir / "check_identifier_uniqueness.py", authoring_dst


def _build_scaffolded_repo_with_collision(root: Path) -> Path:
    """Build a real git repository scaffolding all four GE-122 namespaces,
    with one genuine, on-disk AC-identifier collision, committed.

    Args:
        root: Directory to initialize the git repository in.

    Returns:
        The path to one of the two colliding AC YAML files (used as the
        PostToolUse payload's ``tool_input.file_path``).
    """
    ac_dir = root / "docs" / "acceptance-criteria" / "fixture-component"
    ac_dir.mkdir(parents=True)
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True)
    (root / "tickets").mkdir(parents=True)
    (root / "tickets" / "ticket_lifecycle.json").write_text(json.dumps({"folders": []}), encoding="utf-8")

    claimant_a = ac_dir / "MATRIX-1a.yaml"
    claimant_b = ac_dir / "MATRIX-1b.yaml"
    claimant_a.write_text("id: MATRIX-1\ntitle: claimant a\n", encoding="utf-8")
    claimant_b.write_text("id: MATRIX-1\ntitle: claimant b\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=root, check=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS)
    subprocess.run(
        ["git", "config", "user.email", "test-writer@example.com"],
        cwd=root,
        check=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    subprocess.run(
        ["git", "config", "user.name", "test-writer"], cwd=root, check=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS)
    subprocess.run(
        ["git", "commit", "-q", "-m", "genuine duplicate id, committed"],
        cwd=root,
        check=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    return claimant_a


def _run_commit_stage(commit_script: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the REAL commit-time CLI entry point as a subprocess.

    Args:
        commit_script: Path to the (scratch-deployed) check_identifier_uniqueness.py.
        cwd: Directory to run it from -- must be the fixture repo root, since
            ``_get_staged_paths`` shells out to git with no explicit cwd.

    Returns:
        The completed subprocess result.
    """
    return subprocess.run(
        [sys.executable, str(commit_script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _run_authoring_stage(authoring_script: Path, cwd: Path, edited_file: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the REAL authoring-time hook as a subprocess, fed the real
    PostToolUse JSON payload shape on stdin.

    Args:
        authoring_script: Path to the (scratch-deployed)
            check_identifier_uniqueness_authoring.py.
        cwd: Directory to run it from -- must be the fixture repo root, for
            the same ``_get_staged_paths`` reason as the commit stage.
        edited_file: The file path to report as ``tool_input.file_path`` --
            this is what a real Edit/Write PostToolUse invocation supplies.

    Returns:
        The completed subprocess result.
    """
    payload = json.dumps({"tool_input": {"file_path": str(edited_file)}})
    return subprocess.run(
        [sys.executable, str(authoring_script)],
        cwd=cwd,
        input=payload,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


class TestNoStageDisagreesOnBlockingVerdict(unittest.TestCase):
    def setUp(self) -> None:
        self._scratch_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch_tmp.cleanup)
        scratch_root = Path(self._scratch_tmp.name)
        self.commit_script, self.authoring_script = _deploy_scratch_layout(scratch_root / "deploy")

        self._fixture_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._fixture_tmp.cleanup)
        self.fixture_root = Path(self._fixture_tmp.name)
        self.claimant_a = _build_scaffolded_repo_with_collision(self.fixture_root)

    def test_no_stage_reports_clean_while_another_reports_contested(self) -> None:
        # covers: GE-122d-1
        # angle: reachability
        # NAME RETAINED DELIBERATELY from the version of this test that the
        # contract-shrinking guard saw deleted. The old test asserted this exact
        # property and could not fail -- both sides of its comparison came from a
        # single run_uniqueness_pass return value, so it never invoked either
        # stage. The property is unchanged and is now genuinely checked, by two
        # real subprocesses against one shared root; keeping the name preserves
        # the contract rather than retiring it under a new one. The staged
        # direction is covered by the sibling below, because the disagreement
        # this criterion forbids has bitten in BOTH directions.
        #
        # Nothing is staged beyond the initial commit -- the collision is a
        # pre-existing, unattributed backlog item, not part of the current
        # change set, so BOTH real stages must report a non-blocking verdict.
        commit_result = _run_commit_stage(self.commit_script, self.fixture_root)
        authoring_result = _run_authoring_stage(self.authoring_script, self.fixture_root, self.claimant_a)

        commit_blocked = commit_result.returncode != 0
        authoring_blocked = authoring_result.returncode == 2

        self.assertEqual(commit_result.returncode, 0, f"commit stage stderr:\n{commit_result.stderr}")
        self.assertEqual(authoring_result.returncode, 0, f"authoring stage stderr:\n{authoring_result.stderr}")
        self.assertEqual(
            commit_blocked,
            authoring_blocked,
            "The two real stages disagreed on whether an unattributed, "
            f"committed-only collision blocks: commit exit={commit_result.returncode} "
            f"authoring exit={authoring_result.returncode}",
        )

    def test_both_stages_block_when_collision_is_staged(self) -> None:
        # covers: GE-122d-1
        # angle: reachability
        # Stage one of the two colliding files -- the collision now has a
        # claimant in the current change set, so BOTH real stages must
        # report a BLOCKING verdict (commit exit 1; authoring exit 2 -- the
        # two stages use different exit-code conventions for "block", which
        # is exactly why this test compares normalized verdicts, not raw
        # integers).
        self.claimant_a.write_text("id: MATRIX-1\ntitle: claimant a (edited)\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", str(self.claimant_a)],
            cwd=self.fixture_root,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

        commit_result = _run_commit_stage(self.commit_script, self.fixture_root)
        authoring_result = _run_authoring_stage(self.authoring_script, self.fixture_root, self.claimant_a)

        commit_blocked = commit_result.returncode != 0
        authoring_blocked = authoring_result.returncode == 2

        self.assertEqual(commit_result.returncode, 1, f"commit stage stderr:\n{commit_result.stderr}")
        self.assertEqual(authoring_result.returncode, 2, f"authoring stage stderr:\n{authoring_result.stderr}")
        self.assertEqual(
            commit_blocked,
            authoring_blocked,
            "The two real stages disagreed on whether a STAGED collision "
            f"blocks: commit exit={commit_result.returncode} "
            f"authoring exit={authoring_result.returncode}",
        )


if __name__ == "__main__":
    unittest.main()
