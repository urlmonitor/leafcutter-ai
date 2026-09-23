"""
MODULE: unit_tests/commit_guardian/test_done_proof_test_required_rationale_gate.py
GOAL: Failing (red) tests pinning the fix for the done-proof gate's missing
    test_required/test_rationale carve-out (reproduced on INF-700c-3).

DEFECT: check_staged_done_proofs (the static pre-commit `check-done-proof`
    hook) refuses ANY AC staged as work_status: done unless a `# covers:`
    tag exists somewhere in the tree -- with NO carve-out at all for an AC
    that declares test_required: false with a non-empty test_rationale (a
    docs/prompt-convention AC for which a covers-tagged test is structurally
    meaningless). verify_done_eligible (scripts/ac_store/done_proof.py,
    the ticket's declared fix target) has the identical gap: it always
    demands a linked test regardless of test_required. The two CI-layer
    functions (check_all_done_acs, check_changed_done_acs) already exempt on
    `test_required is False` ALONE -- ignoring test_rationale entirely, which
    means an AC with test_required: false and NO recorded reason is silently
    waved through today. This file pins the corrected CONJUNCTION contract:

        exempt from the covers-tag mandate  <=>  test_required is False
                                             AND  test_rationale is a
                                                  non-empty, non-whitespace
                                                  string.

    Both halves of the conjunction are pinned as a regression fence (missing
    or whitespace-only test_rationale must NOT exempt), and the true
    conjunction is pinned as the one new ACCEPT case.

REACHABILITY: TestPrecommitCliReachability drives the REAL production entry
    point -- `python check_done_proof.py --mode precommit` via subprocess,
    exactly as the deployed `check-done-proof` pre-commit hook invokes it
    (.pre-commit-config.yaml: `check_done_proof.py --test-root .`, default
    --mode is precommit) -- against a real, freshly `git init`'d + staged AC
    YAML fixture. It asserts the subprocess EXIT CODE, which is the literal
    verdict the hook consumes (`return 1 if violations else 0` in main()).
    This is deliberately NOT a call to check_staged_done_proofs() in-process:
    that would only prove the predicate, not that the deployed hook's own
    argv-parsing + git-staged-path resolution + exit-code wiring agree with
    it (BP-1100g-2's "seam" distinction).

ARCHITECTURE NOTE FOR THE IMPLEMENTER: the dispatch ticket names
    scripts/ac_store/done_proof.py as the only production file that should
    change. That fully covers TestVerifyDoneEligibleDirect and (once
    check_all_done_acs / check_changed_done_acs are taught to consult the
    same predicate) TestCheckAllDoneAcsRationaleConjunction /
    TestCheckChangedDoneAcsRationaleConjunction. It does NOT, on its own,
    cover TestPrecommitCliReachability: check_staged_done_proofs (the static
    pre-commit scanner) never calls verify_done_eligible at all today --
    confirmed by reproducing the exact INF-700c-3 failure message via this
    file's own manual spike -- so closing that path requires check_done_proof.py
    to also read test_required/test_rationale (ideally via a small shared
    predicate exported from done_proof.py, so done_proof.py remains the one
    place the RULE lives). Flagging this now rather than silently narrowing
    the fix to only the layer that already had partial support.

FIXTURES: every AC YAML fixture is produced via yaml.safe_dump (never a
    hand-typed literal) per the Fixture Authenticity Rule.

IMPORT WIRING: `done_proof` is imported FIRST from the REAL
    scripts/ac_store/ (the only location this module exists in this repo --
    templates/scripts/ac_store/ is a deploy-source stub with no .py files).
    `check_done_proof` is then imported from its real source location,
    templates/scripts/commit_guardian/ (this repo has no built
    scripts/commit_guardian/ copy to import from). Because `done_proof` is
    already in sys.modules by the time check_done_proof.py's own
    `from done_proof import verify_done_eligible` executes, Python reuses
    the cached REAL module rather than resolving check_done_proof.py's own
    (empty) sibling ac_store/ -- so check_all_done_acs/check_changed_done_acs
    exercise the real oracle, not a stub.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
_COMMIT_GUARDIAN_SRC_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_DONE_PROOF_SCRIPT = _COMMIT_GUARDIAN_SRC_DIR / "check_done_proof.py"

# Load the REAL done_proof module first so it lands in sys.modules before
# check_done_proof.py's own (dead-end, templates-relative) import runs.
sys.path.insert(0, str(_REAL_AC_STORE_DIR))
import done_proof  # noqa: E402
from done_proof import verify_done_eligible  # noqa: E402

sys.path.insert(0, str(_COMMIT_GUARDIAN_SRC_DIR))
import check_done_proof  # noqa: E402
from check_done_proof import check_all_done_acs  # noqa: E402
from check_done_proof import check_changed_done_acs  # noqa: E402

assert check_done_proof.verify_done_eligible is done_proof.verify_done_eligible, (
    "sanity: check_done_proof must resolve verify_done_eligible to the REAL "
    "scripts/ac_store/done_proof module, not a stub -- otherwise "
    "check_all_done_acs/check_changed_done_acs tests below would not be "
    "exercising the real oracle."
)


# ---------------------------------------------------------------------------
# Shared fixture helper (yaml.safe_dump -- Fixture Authenticity Rule)
# ---------------------------------------------------------------------------


def _ac_yaml_bytes(
    ac_id: str,
    *,
    test_required: bool | None = None,
    test_rationale: str | None = "__OMIT__",
) -> str:
    """Serialise a minimal, real AC record via yaml.safe_dump.

    Args:
        ac_id: AC identifier.
        test_required: When False/True, included verbatim. When None, the
            field is omitted (standard code AC with no explicit setting).
        test_rationale: When a string (including ""), included verbatim.
            The sentinel "__OMIT__" (default) omits the field entirely --
            distinct from "" so both "absent" and "empty string" can be
            fixtured independently.
    """
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": "done",
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    if test_required is not None:
        data["test_required"] = test_required
    if test_rationale != "__OMIT__":
        data["test_rationale"] = test_rationale
    return yaml.safe_dump(data, allow_unicode=True)


def _write_ac_yaml(root: Path, ac_id: str, **kwargs) -> Path:
    subdir = root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    path.write_text(_ac_yaml_bytes(ac_id, **kwargs), encoding="utf-8")
    return path


_REAL_RATIONALE = (
    "Pure prose documentation change; no covers-tagged test can meaningfully "
    "assert the correctness of explanatory prose."
)


# ---------------------------------------------------------------------------
# A. Reachability: the REAL `check-done-proof` pre-commit CLI, via subprocess
# ---------------------------------------------------------------------------


def _run_precommit_cli(ac_id: str, **ac_kwargs) -> subprocess.CompletedProcess:
    """Stage one done AC in a fresh temp git repo and invoke the real CLI.

    Runs `python check_done_proof.py --mode precommit --test-root <tmp>`
    with cwd=<tmp>, exactly mirroring how the deployed pre-commit hook
    resolves staged files and test root -- no in-process shortcut.
    """
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        subprocess.run(
            ["git", "-C", str(tmp), "init", "-q"],
            check=True,
            capture_output=True,
            text=True,
        )
        ac_root = tmp / "docs" / "acceptance-criteria"
        yaml_path = _write_ac_yaml(ac_root, ac_id, **ac_kwargs)
        rel_path = yaml_path.relative_to(tmp)
        subprocess.run(
            ["git", "-C", str(tmp), "add", str(rel_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return subprocess.run(
            [
                sys.executable,
                str(_CHECK_DONE_PROOF_SCRIPT),
                "--mode",
                "precommit",
                "--test-root",
                str(tmp),
            ],
            cwd=str(tmp),
            capture_output=True,
            text=True,
            timeout=30,
        )


class TestPrecommitCliReachability(unittest.TestCase):
    """Drives the real `check-done-proof` pre-commit CLI end to end.

    Reproduces the exact INF-700c-3 failure mode and pins its fix: a done
    AC with test_required: false AND a real test_rationale must exit 0
    (accepted) with no covers tag anywhere in the tree.
    """

    def test_ac_accept_test_required_false_with_real_rationale(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: reachability
        """The only new PASS: test_required: false + non-empty rationale."""
        proc = _run_precommit_cli(
            "RG-CLI-ACCEPT-001",
            test_required=False,
            test_rationale=_REAL_RATIONALE,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Expected the precommit CLI to ACCEPT a test_required:false AC "
            f"with a real test_rationale (no covers tag needed). "
            f"Got exit {proc.returncode}. stdout={proc.stdout!r}",
        )

    def test_ac_refuse_test_required_false_missing_rationale(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: reachability
        """Regression fence: test_required: false alone must NOT exempt."""
        proc = _run_precommit_cli(
            "RG-CLI-MISSING-001",
            test_required=False,
            test_rationale="__OMIT__",
        )
        self.assertEqual(
            proc.returncode,
            1,
            f"A test_required:false AC with NO test_rationale must still be "
            f"REFUSED by the precommit CLI. Got exit {proc.returncode}. "
            f"stdout={proc.stdout!r}",
        )

    def test_ac_refuse_test_required_false_whitespace_rationale(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: reachability
        """Regression fence: a whitespace-only rationale is not a rationale."""
        proc = _run_precommit_cli(
            "RG-CLI-WHITESPACE-001",
            test_required=False,
            test_rationale="   \n\t  ",
        )
        self.assertEqual(
            proc.returncode,
            1,
            f"A test_required:false AC with a whitespace-only test_rationale "
            f"must still be REFUSED. Got exit {proc.returncode}. "
            f"stdout={proc.stdout!r}",
        )

    def test_ac_refuse_test_required_true_no_tag(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: reachability
        """Regression fence: test_required: true is always enforced."""
        proc = _run_precommit_cli(
            "RG-CLI-REQUIRED-TRUE-001",
            test_required=True,
            test_rationale=_REAL_RATIONALE,
        )
        self.assertEqual(
            proc.returncode,
            1,
            f"A test_required:true AC must be REFUSED without a covers tag, "
            f"even with a test_rationale present. Got exit {proc.returncode}. "
            f"stdout={proc.stdout!r}",
        )


# ---------------------------------------------------------------------------
# B. verify_done_eligible direct (scripts/ac_store/done_proof.py -- the
#    ticket's declared fix target)
# ---------------------------------------------------------------------------


class TestVerifyDoneEligibleDirect(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_accepts_test_required_false_with_real_rationale(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: criterion
        """verify_done_eligible must exempt on the full conjunction."""
        ac_id = "RG-VDE-ACCEPT-001"
        _write_ac_yaml(
            self.ac_root, ac_id, test_required=False, test_rationale=_REAL_RATIONALE
        )
        result = verify_done_eligible(
            ac_id, ac_root=self.ac_root, test_root=self.test_root
        )
        self.assertTrue(
            result["eligible"],
            f"Expected eligible=True for test_required:false + real rationale "
            f"with no covers tag. Got {result!r}",
        )

    def test_refuses_test_required_true_no_tag(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: criterion
        """Regression fence: the pre-existing direct-tag mandate is untouched."""
        ac_id = "RG-VDE-REQUIRED-TRUE-001"
        _write_ac_yaml(
            self.ac_root, ac_id, test_required=True, test_rationale=_REAL_RATIONALE
        )
        result = verify_done_eligible(
            ac_id, ac_root=self.ac_root, test_root=self.test_root
        )
        self.assertFalse(result["eligible"])
        self.assertIn("no linked test found", result["reason"])


# ---------------------------------------------------------------------------
# C/D. CI-layer functions: extend the existing test_required-only exemption
#      with the test_rationale half of the conjunction.
# ---------------------------------------------------------------------------


class TestCheckAllDoneAcsRationaleConjunction(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_rationale_still_reported(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: failure
        """A test_required:false AC with NO rationale is a known-bad input
        that must still be blocked by check_all_done_acs, not silently
        exempted on test_required alone."""
        ac_id = "RG-ALL-MISSING-001"
        _write_ac_yaml(
            self.ac_root, ac_id, test_required=False, test_rationale="__OMIT__"
        )
        violations = check_all_done_acs(ac_root=self.ac_root, test_root=self.test_root)
        ids = [v["ac_id"] for v in violations]
        self.assertIn(ac_id, ids, f"Expected {ac_id} to be reported. Got {violations!r}")

    def test_whitespace_rationale_still_reported(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: boundary
        """A whitespace-only test_rationale is the empty-string edge of the
        rationale field's shape and must not satisfy the conjunction."""
        ac_id = "RG-ALL-WHITESPACE-001"
        _write_ac_yaml(
            self.ac_root, ac_id, test_required=False, test_rationale="   "
        )
        violations = check_all_done_acs(ac_root=self.ac_root, test_root=self.test_root)
        ids = [v["ac_id"] for v in violations]
        self.assertIn(ac_id, ids, f"Expected {ac_id} to be reported. Got {violations!r}")


class TestCheckChangedDoneAcsRationaleConjunction(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_rationale_still_reported(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: failure
        ac_id = "RG-CHANGED-MISSING-001"
        ac_path = _write_ac_yaml(
            self.ac_root, ac_id, test_required=False, test_rationale="__OMIT__"
        )
        violations = check_changed_done_acs(
            [ac_path], ac_root=self.ac_root, test_root=self.test_root
        )
        ids = [v["ac_id"] for v in violations]
        self.assertIn(ac_id, ids, f"Expected {ac_id} to be reported. Got {violations!r}")

    def test_whitespace_rationale_still_reported(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: boundary
        ac_id = "RG-CHANGED-WHITESPACE-001"
        ac_path = _write_ac_yaml(
            self.ac_root, ac_id, test_required=False, test_rationale="  \t"
        )
        violations = check_changed_done_acs(
            [ac_path], ac_root=self.ac_root, test_root=self.test_root
        )
        ids = [v["ac_id"] for v in violations]
        self.assertIn(ac_id, ids, f"Expected {ac_id} to be reported. Got {violations!r}")


if __name__ == "__main__":
    unittest.main()
