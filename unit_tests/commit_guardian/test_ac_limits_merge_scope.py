"""
MODULE: test_ac_limits_merge_scope
GOAL: During a merge, the AC tree-limit gate must judge only what the merge
    itself introduces — files whose result differs from BOTH parents — and not
    every AC file the incoming branch happens to carry.
BUSINESS CONTEXT: A merge stages the entire incoming branch, so a plain
    ``git diff --cached`` names every AC file the other side ever touched.
    Observed live: merging origin/main into a feature branch was blocked
    because two AC trees on main (KM-KGS-100e with 8 L2 children, TKT-500b
    with 6) exceed the cap. The merging branch neither authored nor modified
    either file — the merge result was byte-identical to main for both — yet
    it could not commit. The merge author cannot restructure another team's AC
    tree, so the only escape is SKIP=check-ac-tree-limits, and a gate that
    people routinely bypass stops catching the violations it exists for.
ARCHITECTURE: Drives ``_get_staged_ac_paths()`` against a REAL temporary git
    repository with a genuine merge conflict, rather than mocking git — the
    behaviour under test is precisely how the hook interrogates git during a
    merge, so a mocked git would test the mock. Asserts both directions: a
    file taken verbatim from one side is out of scope, while a file the merge
    actually resolved is in scope. Do NOT edit check_ac_limits.py from here.
"""

from __future__ import annotations

import importlib.util as _ilu
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TEMPLATE_DIR = (
    Path(__file__).parent.parent.parent / "templates" / "scripts" / "commit_guardian"
)
_CANONICAL = _TEMPLATE_DIR / "check_ac_limits.py"

# The parent-covered_by gate reads its staged set the same way and had the same
# merge blind spot, so it is held to the same contract here.
_CANONICAL_COVERED_BY = _TEMPLATE_DIR / "check_ac_parent_covered_by.py"
_CANONICAL_SCHEMA = _TEMPLATE_DIR / "check_ac_schema.py"
_CANONICAL_DONE_PROOF = _TEMPLATE_DIR / "check_done_proof.py"
_CANONICAL_CONTRACT_SHRINKING = _TEMPLATE_DIR / "check_contract_shrinking.py"

_AC_DIR = "docs/acceptance-criteria/demo"


def _load_module():
    """Load the AC-limits hook from its canonical template path.

    Returns:
        The loaded module, or None when the canonical file is absent.
    """
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_ac_limits_mergescope", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_ac_limits_mergescope"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_covered_by_module():
    """Load the parent-covered_by hook from its canonical template path.

    Returns:
        The loaded module, or None when the canonical file is absent.
    """
    if not _CANONICAL_COVERED_BY.exists():
        return None
    spec = _ilu.spec_from_file_location(
        "check_ac_parent_covered_by_mergescope", _CANONICAL_COVERED_BY
    )
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_ac_parent_covered_by_mergescope"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_schema_module():
    """Load the AC-schema hook from its canonical template path.

    Returns:
        The loaded module, or None when the canonical file is absent or its
        sibling helper modules cannot be imported.
    """
    if not _CANONICAL_SCHEMA.exists():
        return None
    # The schema hook imports sibling helpers (_ac_schema_validators) that are
    # only resolvable with its own directory on sys.path.
    sys.path.insert(0, str(_TEMPLATE_DIR))
    try:
        spec = _ilu.spec_from_file_location(
            "check_ac_schema_mergescope", _CANONICAL_SCHEMA
        )
        mod = _ilu.module_from_spec(spec)
        sys.modules["check_ac_schema_mergescope"] = mod
        spec.loader.exec_module(mod)
        return mod
    except (ImportError, AttributeError):
        return None


def _load_done_proof_module():
    """Load the done-proof hook from its canonical template path.

    Returns:
        The loaded module, or None when it cannot be imported.
    """
    if not _CANONICAL_DONE_PROOF.exists():
        return None
    sys.path.insert(0, str(_TEMPLATE_DIR))
    try:
        spec = _ilu.spec_from_file_location(
            "check_done_proof_mergescope", _CANONICAL_DONE_PROOF
        )
        mod = _ilu.module_from_spec(spec)
        sys.modules["check_done_proof_mergescope"] = mod
        spec.loader.exec_module(mod)
        return mod
    except (ImportError, AttributeError):
        return None


def _load_contract_shrinking_module():
    """Load the contract-shrinking hook from its canonical template path.

    Returns:
        The loaded module, or None when it cannot be imported.
    """
    if not _CANONICAL_CONTRACT_SHRINKING.exists():
        return None
    sys.path.insert(0, str(_TEMPLATE_DIR))
    try:
        spec = _ilu.spec_from_file_location(
            "check_contract_shrinking_mergescope", _CANONICAL_CONTRACT_SHRINKING
        )
        mod = _ilu.module_from_spec(spec)
        sys.modules["check_contract_shrinking_mergescope"] = mod
        spec.loader.exec_module(mod)
        return mod
    except (ImportError, AttributeError):
        return None


_mod = _load_module()
_mod_covered_by = _load_covered_by_module()
_mod_schema = _load_schema_module()
_mod_done_proof = _load_done_proof_module()
_mod_shrink = _load_contract_shrinking_module()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command inside *repo*.

    Args:
        repo: Repository working directory.
        *args: Arguments passed to git.

    Returns:
        The completed process.
    """
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _write_ac(repo: Path, name: str, body: str) -> None:
    """Write an AC YAML file inside the demo AC directory.

    Args:
        repo: Repository working directory.
        name: File stem (without .yaml).
        body: File contents.
    """
    target = repo / _AC_DIR
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{name}.yaml").write_text(body, encoding="utf-8")


@unittest.skipUnless(_mod is not None, f"hook not found at {_CANONICAL}")
class TestMergeScoping(unittest.TestCase):
    """A merge is judged on what it introduces, not on what it inherits."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")

        # Base commit, shared by both sides.
        _write_ac(self.repo, "BASE", "id: BASE\nlevel: L1\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base")

        # Branch side: edits SHARED and adds its own file.
        _git(self.repo, "checkout", "-q", "-b", "feature")
        _write_ac(self.repo, "SHARED", "id: SHARED\nlevel: L1\nowner: feature\n")
        _write_ac(self.repo, "MINE", "id: MINE\nlevel: L1\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "feature work")

        # Main side: edits SHARED differently (forces a conflict) and adds
        # THEIRS, which the feature branch never touches.
        _git(self.repo, "checkout", "-q", "main")
        _write_ac(self.repo, "SHARED", "id: SHARED\nlevel: L1\nowner: main\n")
        _write_ac(self.repo, "THEIRS", "id: THEIRS\nlevel: L1\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "main work")

        _git(self.repo, "checkout", "-q", "feature")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _staged_ac_paths_in_repo(self) -> list[str]:
        """Call the hook's path collector with the temp repo as cwd.

        Returns:
            The list of AC paths the hook considers in scope.
        """
        original = os.getcwd()
        os.chdir(self.repo)
        try:
            return _mod._get_staged_ac_paths()
        finally:
            os.chdir(original)

    def test_merge_excludes_files_taken_verbatim_from_either_side(self) -> None:
        # covers: ACS-100c-1
        """Only the conflict-resolved file is in scope during a merge.

        THEIRS comes verbatim from main and MINE verbatim from the branch —
        each was already gated when committed on its own side. SHARED is the
        one the merge actually decided, so it is the one to judge.
        """
        merge = _git(self.repo, "merge", "main", "--no-commit", "--no-ff")
        self.assertNotEqual(
            merge.returncode, 0, "expected a conflicting merge for this fixture"
        )
        # Resolve the conflict so the file is staged with merge-specific content.
        _write_ac(self.repo, "SHARED", "id: SHARED\nlevel: L1\nowner: resolved\n")
        _git(self.repo, "add", f"{_AC_DIR}/SHARED.yaml")

        paths = self._staged_ac_paths_in_repo()
        names = {Path(p).name for p in paths}

        self.assertIn(
            "SHARED.yaml",
            names,
            "The conflict-resolved file is introduced by the merge and MUST be "
            f"judged. Got: {sorted(names)}",
        )
        self.assertNotIn(
            "THEIRS.yaml",
            names,
            "A file taken verbatim from the incoming branch was already gated "
            "on that branch and must NOT be re-judged by the merge author. "
            f"Got: {sorted(names)}",
        )

    def test_non_merge_commit_scope_is_unchanged(self) -> None:
        # covers: ACS-100c-1
        """Outside a merge, every staged AC file is still judged.

        Guards against fixing the merge case by narrowing the gate everywhere.
        """
        _write_ac(self.repo, "NEWONE", "id: NEWONE\nlevel: L1\n")
        _git(self.repo, "add", "-A")

        paths = self._staged_ac_paths_in_repo()
        names = {Path(p).name for p in paths}

        self.assertIn(
            "NEWONE.yaml",
            names,
            "A normal (non-merge) commit must still have all staged AC files "
            f"in scope. Got: {sorted(names)}",
        )


@unittest.skipUnless(
    _mod_covered_by is not None, f"hook not found at {_CANONICAL_COVERED_BY}"
)
class TestCoveredByMergeScoping(TestMergeScoping):
    """The parent-covered_by gate obeys the same merge-scoping contract.

    Inherits the fixture and both assertions from TestMergeScoping, re-pointed
    at the other hook: the two gates collect their staged set identically and
    shared the same blind spot, so they must not drift apart.
    """

    def _staged_ac_paths_in_repo(self) -> list[str]:
        """Call the covered_by hook's path collector with the temp repo as cwd.

        Returns:
            The list of AC paths that hook considers in scope.
        """
        original = os.getcwd()
        os.chdir(self.repo)
        try:
            return _mod_covered_by._get_staged_ac_paths()
        finally:
            os.chdir(original)


@unittest.skipUnless(_mod_schema is not None, f"hook not found at {_CANONICAL_SCHEMA}")
class TestSchemaMergeScoping(TestMergeScoping):
    """The AC-schema gate obeys the same merge-scoping contract.

    Its collector returns Paths (not strings) and takes a root argument, so
    only the call differs; the fixture and both assertions are inherited.
    """

    def _staged_ac_paths_in_repo(self) -> list[str]:
        """Call the schema hook's path collector with the temp repo as cwd.

        Returns:
            The list of AC paths that hook considers in scope, as strings.
        """
        original = os.getcwd()
        os.chdir(self.repo)
        try:
            return [str(p) for p in _mod_schema._get_staged_ac_paths(self.repo)]
        finally:
            os.chdir(original)


@unittest.skipUnless(
    _mod_done_proof is not None, f"hook not found at {_CANONICAL_DONE_PROOF}"
)
class TestDoneProofMergeScoping(TestMergeScoping):
    """The done-proof PRE-COMMIT presence check obeys the same contract.

    Scoping this path does not weaken the phantom-done guarantee: it feeds only
    the fast staged-only tag-presence check. The authoritative whole-store
    sweep is check_all_done_acs, which walks every done AC in ac_root and never
    consults the staged set.
    """

    def _staged_ac_paths_in_repo(self) -> list[str]:
        """Call the done-proof collector with the temp repo as cwd.

        Returns:
            The list of AC paths that hook considers in scope, as strings.
        """
        original = os.getcwd()
        os.chdir(self.repo)
        try:
            return [
                str(p)
                for p in _mod_done_proof._get_staged_ac_yaml_paths(self.repo)
            ]
        finally:
            os.chdir(original)


@unittest.skipUnless(
    _mod_shrink is not None, f"hook not found at {_CANONICAL_CONTRACT_SHRINKING}"
)
class TestContractShrinkingMergeScoping(TestMergeScoping):
    """The contract-shrinking (TDD) guard obeys the same merge-scoping contract.

    This gate was the last of the family still unscoped: it reads the staged
    diff as TEXT rather than as a path list, so it did not share the collector
    the other four fixed. A merge therefore showed it every test the incoming
    branch had ever deleted or skipped, and it blocked the merge on them.
    """

    def _staged_ac_paths_in_repo(self) -> list[str]:
        """Report the paths this hook's diff will actually cover.

        Mirrors ``_get_staged_diff``: a None from ``_merge_scoped_paths`` means
        "not a merge — scan everything staged", so the equivalent path set is
        the full staged list. Returning the sentinel instead would make the
        inherited non-merge assertion test nothing.

        Returns:
            The list of paths in scope for the diff scan.
        """
        original = os.getcwd()
        os.chdir(self.repo)
        try:
            scoped = _mod_shrink._merge_scoped_paths()
        finally:
            os.chdir(original)
        if scoped is None:
            return _git(self.repo, "diff", "--cached", "--name-only").stdout.split()
        return scoped


@unittest.skipUnless(
    _mod_shrink is not None, f"hook not found at {_CANONICAL_CONTRACT_SHRINKING}"
)
class TestContractShrinkingMergeBehaviour(unittest.TestCase):
    """End-to-end: the guard blocks the author's own weakening, not the merge's.

    Path-scoping alone is not proof — the scoped list has to actually change the
    verdict. These drive the real scan over a real repository and assert on the
    exit code, so a scoping helper that were computed and then ignored would
    fail here.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")

        (self.repo / "unit_tests").mkdir()
        (self.repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (self.repo / "unit_tests" / "test_app.py").write_text(
            "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
            encoding="utf-8",
        )
        (self.repo / "shared.txt").write_text("base\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base")

        # Feature side: an innocuous edit, and a conflicting edit to shared.txt.
        _git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "shared.txt").write_text("feature\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "feature work")

        # Main side: deletes a test AND changes production code — exactly what
        # the guard exists to block when an AUTHOR does it. Here it is already
        # committed on main, so a merge only inherits it.
        _git(self.repo, "checkout", "-q", "main")
        (self.repo / "app.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        (self.repo / "unit_tests" / "test_app.py").write_text(
            "def test_one():\n    assert True\n", encoding="utf-8"
        )
        (self.repo / "shared.txt").write_text("main\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "main work")
        _git(self.repo, "checkout", "-q", "feature")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _scan(self) -> bool:
        """Run the real diff-fetch + scan in the temp repo.

        Returns:
            True when the guard would BLOCK the commit.
        """
        original = os.getcwd()
        os.chdir(self.repo)
        try:
            diff = _mod_shrink._get_staged_diff()
            return bool(_mod_shrink._scan_diff(diff).is_contract_shrinking)
        finally:
            os.chdir(original)

    def test_merge_does_not_block_on_weakening_inherited_from_main(self) -> None:
        # covers: ACS-100c-1
        """A merge is not blocked by a test main deleted on its own branch."""
        merge = _git(self.repo, "merge", "main", "--no-commit", "--no-ff")
        self.assertNotEqual(
            merge.returncode, 0, "expected a conflicting merge for this fixture"
        )
        (self.repo / "shared.txt").write_text("resolved\n", encoding="utf-8")
        _git(self.repo, "add", "shared.txt")

        self.assertFalse(
            self._scan(),
            "The deleted test and the production edit both came verbatim from "
            "main, where they were already gated. Blocking the merge author for "
            "them makes merging impossible and teaches people to use SKIP=.",
        )

    def test_author_weakening_a_test_is_still_blocked_outside_a_merge(self) -> None:
        # covers: ACS-100c-1
        """The guard still fires on the author's own weakening.

        The discriminating case: identical content to the merge above, staged as
        an ordinary commit. If scoping had simply disabled the gate, this would
        pass and the guard would be dead.
        """
        (self.repo / "app.py").write_text("def f():\n    return 3\n", encoding="utf-8")
        (self.repo / "unit_tests" / "test_app.py").write_text(
            "def test_one():\n    assert True\n", encoding="utf-8"
        )
        _git(self.repo, "add", "-A")

        self.assertTrue(
            self._scan(),
            "Deleting a test while changing production code in a NORMAL commit "
            "is exactly what this guard exists to block.",
        )

    def test_weakening_introduced_by_the_conflict_resolution_is_blocked(self) -> None:
        # covers: ACS-100c-1
        """Resolving a conflict by weakening a test is the author's own act.

        Content that differs from BOTH parents is authored by the merge, so it
        stays in scope — this is what keeps merge-scoping from being a loophole.
        """
        merge = _git(self.repo, "merge", "main", "--no-commit", "--no-ff")
        self.assertNotEqual(merge.returncode, 0)
        (self.repo / "shared.txt").write_text("resolved\n", encoding="utf-8")
        # The merge author now weakens a test and edits production code itself.
        (self.repo / "app.py").write_text("def f():\n    return 99\n", encoding="utf-8")
        (self.repo / "unit_tests" / "test_app.py").write_text(
            "import pytest\n\n\ndef test_one():\n    pytest.skip('later')\n",
            encoding="utf-8",
        )
        _git(self.repo, "add", "-A")

        self.assertTrue(
            self._scan(),
            "A pytest.skip added by the MERGE differs from both parents, so it "
            "must remain in scope. Otherwise merge-scoping is a way to smuggle "
            "test weakening past the guard.",
        )


if __name__ == "__main__":
    unittest.main()
