"""
MODULE: unit_tests/portability/ge_120e_1/test_ge_120e_1_boundary_and_seam.py
AC: GE-120e-1 — "A check that works out its own change set works out the
    author's change, not everything the staged tree happens to hold"
GOAL: The boundary and seam tests of the GE-120e-1 suite: on an ordinary
    commit the derived change set equals the full staged diff byte for byte
    (test C), and both self-deriving checks take their change set from the
    ONE shared module, proven by poisoning it and watching both degrade
    (test D).
CONTRACT: see the module docstring of ``_support.py`` in this package
    ("CONTRACT ASSUMED") for the shape of the shared module under test and
    why every fixture is a real linked checkout of this repository.

DECISION HISTORY:
- 2026-11-17 [isolate-ge120e1-test-d, GE-120e-1-iii]: Test D no longer
  writes into the repository. It used to replace the REAL
  templates/scripts/commit_guardian/_authored_change.py with its stub and put
  the original back in a finally block, which a SIGKILL, an OOM kill or a
  crashed xdist worker never reaches, and under ``pytest -n`` other tests
  could load the stub meanwhile. It now copies commit_guardian/ into a private
  temporary directory laid out like a deployed install, with
  scripts/frontmatter_path_resolver.py beside it because
  frontmatter_validators.py looks for it there first
  (make_private_guardian_copy), poisons the copy and runs
  the COPIED checks (run_both_checks): each check imports _authored_change as
  a sibling, and Python puts the running script's own directory first on
  sys.path, so the copied checks load the copied, poisoned module. The copy is
  real files, not symlinks, because Python resolves a symlinked script to its
  target directory. Assertions, name and covers tag are unchanged.
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/portability/test_ge_120e_1.py when that file was split; the
  classes now declare their setUpClass attributes for the type checker.
"""
# @ac-tag: GE-120e-1

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import ClassVar

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    new_checkout, unlink_checkout,
)
from unit_tests.portability.ge_120e_1._support import (
    _CHECK_CONTRACT_SHRINKING,
    _CHECK_DOC_FRONTMATTER,
    _COMMIT_GUARDIAN_TEMPLATES,
    _REPO_ROOT,
    _SHARED_MODULE_MISSING_MSG,
    _SHARED_MODULE_OK,
    NoAuthorMergeTestCase,
    _run,
    _run_git,
    get_authored_change,
)

# Test D's always-raising replacement for the shared module. GE-120e-1-iii's
# isolation tests look for its message text to know the stub is in place.
POISONED_SOURCE = (
    "def get_authored_change(cwd=None):\n"
    "    raise RuntimeError('GE-120e-1 test-injected failure')\n"
)
SEAM_COPY_PREFIX = "ge120e1-seam-guardian-"
# frontmatter_validators.py imports this top-level module; its locator looks
# for it next to commit_guardian/ first (the deployed layout) and only then
# walks up to a project root, which a copy under the temp dir does not have.
_FRONTMATTER_PATH_RESOLVER = _REPO_ROOT / "scripts" / "frontmatter_path_resolver.py"


def make_private_guardian_copy() -> Path:
    """Copy the checks out of the repository; return the copied commit_guardian/.

    Laid out like a deployed install, ``<mkdtemp>/scripts/commit_guardian/``
    beside ``<mkdtemp>/scripts/frontmatter_path_resolver.py``, under
    ``tempfile``'s directory (so it honours TMPDIR). Real files only: a
    symlinked check would be resolved back to the repository and import the
    real module. Remove it with remove_private_guardian_copy().
    """
    copy_root = Path(tempfile.mkdtemp(prefix=SEAM_COPY_PREFIX))
    guardian_copy = copy_root / "scripts" / "commit_guardian"
    try:
        shutil.copytree(
            _COMMIT_GUARDIAN_TEMPLATES, guardian_copy, symlinks=False,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy2(_FRONTMATTER_PATH_RESOLVER, guardian_copy.parent / _FRONTMATTER_PATH_RESOLVER.name)
    except (OSError, shutil.Error):
        shutil.rmtree(copy_root, ignore_errors=True)
        raise
    return guardian_copy


def remove_private_guardian_copy(guardian_copy: Path) -> None:
    """Remove the temporary directory make_private_guardian_copy() created."""
    shutil.rmtree(guardian_copy.parents[1], ignore_errors=True)


def run_both_checks(
    guardian_dir: Path, cwd: Path,
) -> tuple[subprocess.CompletedProcess, subprocess.CompletedProcess]:
    """Run check_contract_shrinking.py and check_doc_frontmatter.py from *guardian_dir* in *cwd*.

    PYTHONDONTWRITEBYTECODE keeps the run from writing ``__pycache__`` next
    to the checks, so running them from the repository writes nothing there.
    """
    no_bytecode = {"PYTHONDONTWRITEBYTECODE": "1"}
    contract_shrinking = _run(
        ["python3", str(guardian_dir / _CHECK_CONTRACT_SHRINKING.name)], cwd=cwd, extra_env=no_bytecode,
    )
    doc_frontmatter = _run(
        ["python3", str(guardian_dir / _CHECK_DOC_FRONTMATTER.name)], cwd=cwd, extra_env=no_bytecode,
    )
    return contract_shrinking, doc_frontmatter


# ---------------------------------------------------------------------------
# Test C — angle: boundary
# ---------------------------------------------------------------------------
class TestOrdinaryCommitChangeSetEqualsFullStagedDiff(unittest.TestCase):
    """AC (Implementation Notes) "NO BEHAVIOUR CHANGE ON THE ORDINARY
    COMMIT": with exactly one state to compare against (no merge in
    progress — the one/many boundary this AC narrows around), the derived
    change set must equal today's `git diff --cached` output byte for byte —
    the narrowing must cost nothing on the common path."""

    root: ClassVar[Path]
    staged_rel: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        suffix = uuid.uuid4().hex[:10]
        cls.root = Path(tempfile.gettempdir()) / f"ge120e1-ordinary-boundary-{suffix}"
        new_checkout(_REPO_ROOT, cls.root)
        # Identity comes from _GIT_ENV_OVERRIDES, never `git config` — see
        # KI-TQ-012 there. Writing it here would escape into the real repo.
        cls.staged_rel = "_ge120e1_probe_ordinary.py"
        (cls.root / cls.staged_rel).write_text("def probe():\n    return 42\n", encoding="utf-8")
        _run_git(["add", cls.staged_rel], cwd=cls.root)
        # Deliberately left staged, uncommitted — the exact state a
        # pre-commit hook inspects.

    @classmethod
    def tearDownClass(cls) -> None:
        unlink_checkout(_REPO_ROOT, ["--force", str(cls.root)], check=False)

    def test_ge120e1_ordinary_commit_change_set_equals_full_staged_diff(self) -> None:
        # covers: GE-120e-1
        # angle: boundary
        """RED via the shared-module import gate."""
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        expected_diff = _run_git(["diff", "--cached"], cwd=self.root).stdout
        expected_name_status_raw = _run_git(["diff", "--cached", "--name-status"], cwd=self.root).stdout
        expected_name_status: dict[str, str] = {}
        for line in expected_name_status_raw.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                expected_name_status[parts[-1]] = parts[0]

        authored = get_authored_change(cwd=self.root)
        self.assertFalse(
            authored.could_not_check,
            "get_authored_change() reported could_not_check on an "
            f"ordinary, non-merge staged commit — this is the common path "
            f"and must never fail here (error={authored.error!r}).",
        )
        self.assertEqual(
            expected_diff, authored.diff_text,
            "On an ordinary (single-state) commit, the shared derivation's "
            "diff_text must equal `git diff --cached` byte for byte — "
            "this is the regression budget for every other manifest check.",
        )
        self.assertEqual(
            expected_name_status, dict(authored.name_status),
            "On an ordinary (single-state) commit, the shared derivation's "
            "name_status must equal `git diff --cached --name-status` "
            "parsed identically.",
        )


# ---------------------------------------------------------------------------
# Test D — angle: seam
# ---------------------------------------------------------------------------
class TestBothSelfDerivingChecksInspectTheSameAuthoredSet(NoAuthorMergeTestCase):
    """AC-5: every check that works out its own change set takes it from
    ONE shared source. Proven behaviorally (not by grep): the shared module
    (in a private copy of the checks), when it cannot compute the
    derivation, must degrade BOTH real consumers identically to a could-not-check outcome — proving they
    depend on the same single point rather than two independent private
    implementations that merely happen to agree today."""

    def test_ge120e1_both_self_deriving_checks_inspect_the_same_authored_set(self) -> None:
        # covers: GE-120e-1
        # angle: seam
        """RED via the shared-module import gate. Once implemented: pipe the
        REAL shared module's output into BOTH REAL consumers on the SAME
        fixture, then poison the ONE shared module file (replace its
        contents with something that unconditionally raises) and assert
        BOTH consumers — not just one — degrade to a could-not-check
        outcome. If only one consumer is affected, they are not actually
        sharing one source. The poisoned file and the consumers run are a
        private copy of commit_guardian/ outside the repository
        (GE-120e-1-iii), so a killed run leaves the real hook intact.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        # GE-120e-1-iii: poison a private copy, never the repository's own
        # file — a killed run must not leave the real hook broken.
        guardian_copy = make_private_guardian_copy()
        try:
            (guardian_copy / "_authored_change.py").write_text(POISONED_SOURCE, encoding="utf-8")

            contract_shrinking, doc_frontmatter = run_both_checks(guardian_copy, self.fixture.root)

            cs_combined = contract_shrinking.stdout + contract_shrinking.stderr
            df_combined = doc_frontmatter.stdout + doc_frontmatter.stderr

            self.assertNotIn(
                self.fixture.baddoc_rel, cs_combined,
                "With the shared source poisoned, check_contract_shrinking.py "
                "must not fall back to widening its scan to the carried-in "
                f"content. Output: {cs_combined!r}",
            )
            self.assertNotIn(
                self.fixture.baddoc_rel, df_combined,
                "With the shared source poisoned, check_doc_frontmatter.py "
                "must not fall back to widening its scan to the carried-in "
                f"content either — proving it depends on the SAME shared "
                f"source as check_contract_shrinking.py. Output: {df_combined!r}",
            )
            self.assertTrue(
                "could_not_check" in cs_combined.lower() or "could not" in cs_combined.lower(),
                "check_contract_shrinking.py must report a could-not-check "
                f"outcome when the shared derivation raises. Output: {cs_combined!r}",
            )
            self.assertTrue(
                "could_not_check" in df_combined.lower() or "could not" in df_combined.lower(),
                "check_doc_frontmatter.py must ALSO report a could-not-check "
                f"outcome from the SAME poisoned shared source. Output: {df_combined!r}",
            )
        finally:
            remove_private_guardian_copy(guardian_copy)


if __name__ == "__main__":
    unittest.main()
