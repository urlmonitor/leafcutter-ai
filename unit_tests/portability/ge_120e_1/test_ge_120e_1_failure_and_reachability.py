"""
MODULE: unit_tests/portability/ge_120e_1/test_ge_120e_1_failure_and_reachability.py
AC: GE-120e-1 — "A check that works out its own change set works out the
    author's change, not everything the staged tree happens to hold"
GOAL: The failure and reachability tests of the GE-120e-1 suite: a git
    failure in the merge-scoping derivation is a could-not-check outcome,
    never a widening to the whole staged tree (test E, a real fake-git shim
    on PATH), and the shared-derivation behaviour is reachable from the
    DEPLOYED copy of the checks, not only from templates/ (test F).
CONTRACT: see the module docstring of ``_support.py`` in this package
    ("CONTRACT ASSUMED") for the shape of the shared module under test and
    why every fixture is a real linked checkout of this repository.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/portability/test_ge_120e_1.py when that file was split; the
  classes now declare their setUpClass attributes for the type checker.
"""
# @ac-tag: GE-120e-1

from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import ClassVar

from unit_tests.portability.ge_120e_1._support import (
    _BUILD_PHASES_OK,
    _CHECK_CONTRACT_SHRINKING,
    _CHECK_DOC_FRONTMATTER,
    _SHARED_MODULE_MISSING_MSG,
    _SHARED_MODULE_OK,
    NoAuthorMergeTestCase,
    _run,
    _write_fake_git_shim,
    build_commit_guardian,
)


# ---------------------------------------------------------------------------
# Test E — angle: failure
# ---------------------------------------------------------------------------
class TestGitFailureDoesNotWidenToTheWholeStagedTree(NoAuthorMergeTestCase):
    """Implementation Notes: "A git failure must NOT degrade to using the
    whole staged tree ... A derivation that cannot be computed is a
    could-not-check outcome, not a wider change set." Proven with a REAL
    fake-git shim on PATH that fails the specific git call the merge-scoping
    derivation needs — not a mocked-out git module."""

    shim_dir: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.shim_dir = Path(tempfile.gettempdir()) / f"ge120e1-fakegit-{uuid.uuid4().hex[:10]}"
        _write_fake_git_shim(cls.shim_dir)

    def test_ge120e1_git_failure_does_not_widen_to_the_whole_staged_tree(self) -> None:
        # covers: GE-120e-1
        # angle: failure
        """RED both via the shared-module import gate AND (independently)
        against the CURRENT per-check implementations, which are documented
        (verbatim in their own docstrings, read at authoring time) to fall
        back to the unscoped diff when the merge-parent-side git call
        fails — precisely the anti-pattern this test forbids.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        poisoned_path = f"{self.shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"

        contract_shrinking = _run(
            ["python3", str(_CHECK_CONTRACT_SHRINKING)],
            cwd=self.fixture.root,
            extra_env={"PATH": poisoned_path},
        )
        doc_frontmatter = _run(
            ["python3", str(_CHECK_DOC_FRONTMATTER)],
            cwd=self.fixture.root,
            extra_env={"PATH": poisoned_path},
        )

        cs_combined = contract_shrinking.stdout + contract_shrinking.stderr
        df_combined = doc_frontmatter.stdout + doc_frontmatter.stderr

        self.assertNotIn(
            self.fixture.baddoc_rel, cs_combined,
            "When the git call needed to resolve the merge-parent side "
            "fails, check_contract_shrinking.py must NOT widen to the "
            f"unscoped staged diff. Output: {cs_combined!r}",
        )
        self.assertNotIn(
            self.fixture.baddoc_rel, df_combined,
            "When the git call needed to resolve the merge-parent side "
            "fails, check_doc_frontmatter.py must NOT widen to the unscoped "
            f"staged diff either. Output: {df_combined!r}",
        )
        self.assertTrue(
            "could_not_check" in cs_combined.lower() or "could not" in cs_combined.lower(),
            f"check_contract_shrinking.py must report a could-not-check "
            f"outcome on git failure, not a silent pass or a widened scan. "
            f"Output: {cs_combined!r}",
        )
        self.assertTrue(
            "could_not_check" in df_combined.lower() or "could not" in df_combined.lower(),
            f"check_doc_frontmatter.py must report a could-not-check outcome "
            f"on git failure, not a silent pass or a widened scan. "
            f"Output: {df_combined!r}",
        )


# ---------------------------------------------------------------------------
# Test F — angle: reachability (REQUIRED by test_spec)
# ---------------------------------------------------------------------------
class TestReachableFromDeployedEntryPoint(NoAuthorMergeTestCase):
    """REQUIRED reachability angle: invoke the DEPLOYED copy of the checks
    (per ADR-001 template/deployed parity) as real subprocesses, and assert
    the shared-derivation behaviour is reachable there too — not only from
    templates/scripts/commit_guardian/ source."""

    deployed_ok: ClassVar[bool]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.deployed_ok = False
        if _BUILD_PHASES_OK:
            written = build_commit_guardian(
                cls.fixture.root,
                {
                    "output_root": ".leafcutter",
                    "agents_dir": ".claude/agents",
                    "skills_dir": ".claude/skills",
                },
                dry_run=False,
                force=True,
            )
            cls.deployed_ok = written > 0 and (
                cls.fixture.root / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
            ).exists() and (
                cls.fixture.root / "scripts" / "commit_guardian" / "_authored_change.py"
            ).exists()

    def test_ge_120e_1_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-1
        # angle: reachability
        """Runs the DEPLOYED (`scripts/commit_guardian/`, not
        `templates/scripts/commit_guardian/`) copy of check_doc_frontmatter.py
        as a real subprocess against the same no-author merge fixture, and
        asserts it exits clean without naming the carried-in doc. Importing
        the check's functions directly would not exercise this at all, and
        would not catch a fix that lands only in templates/ without a
        build.py run.
        """
        if not _BUILD_PHASES_OK:
            self.fail(
                "scripts.build_phases.build_commit_guardian could not be "
                "imported — cannot deploy the commit_guardian scripts into "
                "the fixture worktree to test the deployed entry point."
            )
        if not self.deployed_ok:
            self.fail(
                "build_commit_guardian() did not produce a deployed "
                f"{self.fixture.root}/scripts/commit_guardian/ layout "
                "including _authored_change.py — cannot exercise the "
                "deployed entry point for this AC's shared module."
            )

        deployed_check = (
            self.fixture.root / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
        )
        result = _run(["python3", str(deployed_check)], cwd=self.fixture.root)
        self.assertEqual(
            0, result.returncode,
            "The DEPLOYED check_doc_frontmatter.py must exit clean on a "
            f"merge with no authored content. stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            self.fixture.baddoc_rel, combined,
            f"The deployed check must not name the carried-in doc. Output: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
