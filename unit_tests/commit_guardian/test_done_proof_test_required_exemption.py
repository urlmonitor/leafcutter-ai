"""
MODULE: unit_tests/commit_guardian/test_done_proof_test_required_exemption.py
GOAL: Behavioral tests for the test_required:false exemption in check_done_proof.py.
    Done ACs with test_required explicitly False must be silently exempted from the
    covers-tag mandate in check_changed_done_acs, check_all_done_acs, AND
    check_staged_done_proofs (the pre-commit mode) — all three must agree.
BUSINESS CONTEXT: Documentation ACs and prompt-convention ACs (e.g. BO-2400a-6,
    BO-2400b-4, BO-2500a-4) legitimately have test_required: false because no
    covers-tagged test can meaningfully verify prose documentation. Requiring a
    covers test for these ACs causes the CI done-proof gate to flag them as
    violations even though the AC type structurally cannot satisfy the mandate.
    The fix exempts test_required: false ACs from verify_done_eligible (CI
    modes) and from the covers-tag scan (pre-commit mode) so the gate remains
    meaningful for code ACs while passing for docs ACs in EVERY mode. Before
    this fix, check_staged_done_proofs had no such exemption, so a docs-only
    AC (test_required: false) passed the CI-authoritative check but was
    blocked at pre-commit — the asymmetry this test file's third class closes.
ARCHITECTURE: Tests import from scripts/commit_guardian/check_done_proof.py
    (deployed layout; tests/imports wiring follows the same pattern as
    test_bo2500b_done_proof_hook.py).  All AC YAML fixtures are written with
    yaml.safe_dump (BO-2500c mandate) so YAML round-trip fidelity is guaranteed.
    Covers test fixtures are real .py files.  No mocking of pass/fail signals.

    Three test classes:
        TestCheckChangedDoneAcsExemption   — tests check_changed_done_acs()
        TestCheckAllDoneAcsExemption       — tests check_all_done_acs()
        TestCheckStagedDoneProofsExemption — tests check_staged_done_proofs()
"""
from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as test_bo2500b_done_proof_hook.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
sys.path.insert(0, str(_AC_STORE_DIR))

from check_done_proof import check_all_done_acs  # noqa: E402
from check_done_proof import check_changed_done_acs  # noqa: E402
from check_done_proof import check_staged_done_proofs  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers (yaml.safe_dump — BO-2500c mandate)
# ---------------------------------------------------------------------------


def _write_done_ac(
    ac_root: Path,
    ac_id: str,
    *,
    test_required: bool | None = None,
    test_rationale: str | None = None,
) -> Path:
    """Write a minimal done AC YAML using yaml.safe_dump (mandate-compliant).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC (e.g. "BO-DOCS-EXEMPT-001").
        test_required: When ``False``, ``test_required: false`` is included in
            the YAML.  When ``True``, ``test_required: true`` is included.
            When ``None`` (default), the field is omitted entirely — this
            represents the standard code AC that has no explicit setting.
        test_rationale: When a non-``None`` string, ``test_rationale`` is
            included in the YAML verbatim (BO-2500a-1-ii: the conjunction's
            second half — a ``test_required: false`` AC is only waived when
            this is also a non-empty, non-whitespace string). Omitted
            entirely when ``None`` (default).

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic done AC {ac_id}",
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
    if test_rationale is not None:
        data["test_rationale"] = test_rationale
    # Mandate: use yaml.safe_dump, not a hand-typed YAML literal (BO-2500c).
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestCheckChangedDoneAcsExemption — check_changed_done_acs
# ---------------------------------------------------------------------------


class TestCheckChangedDoneAcsExemption(unittest.TestCase):
    """test_required: false exemption for check_changed_done_acs().

    A done AC with test_required explicitly False must NOT be reported even when
    no covers-tagged test exists.  A done AC with test_required absent or True
    must still be reported when no covers test exists.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_done_ac_with_test_required_false_is_not_reported(self) -> None:
        # covers: BO-2500a-3
        """A done AC with test_required: false must NOT appear in violations.

        Documentation ACs and prompt-convention ACs carry test_required: false
        because a covers-tagged test cannot meaningfully cover prose output.
        The done-proof gate must silently skip them — calling verify_done_eligible
        on a docs AC would always produce a violation (no test can be written for
        "the how-to explains X"), so the gate must exempt them entirely.

        The fixture writes a done AC with test_required: false and no covers test
        anywhere in test_root.  check_changed_done_acs must return [] (no violations).

        yaml.safe_dump serialises False as the YAML scalar 'false'; yaml.safe_load
        deserialises 'false' back to Python False.  The check
        ``data.get("test_required") is False`` must be True, triggering the exemption.

        BO-2500a-1-ii: the exemption is now the CONJUNCTION of
        ``test_required: false`` AND a non-empty ``test_rationale`` — a
        ``test_required: false`` AC with no recorded reason is no longer
        waived on its own. This fixture gained a real ``test_rationale`` so
        it still exercises the intended "docs AC, no covers tag needed"
        accept path under the corrected rule, rather than the now-closed
        "no reason required" gap the fixture originally (and incompletely)
        pinned.
        """
        ac_id = "BO-DOCS-EXEMPT-CHANGED-001"
        ac_path = _write_done_ac(
            self.ac_root,
            ac_id,
            test_required=False,
            test_rationale=(
                "Pure prose documentation change; no covers-tagged test can "
                "meaningfully assert the correctness of explanatory prose."
            ),
        )
        # test_root is intentionally empty — no covers tag exists

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            f"A done AC with test_required: false must NOT be reported by "
            f"check_changed_done_acs even when no covers test exists. "
            f"Got violations: {violations}",
        )

    def test_done_ac_with_test_required_true_is_still_reported(self) -> None:
        # covers: BO-2500a-3
        """A done AC with test_required: true must still be reported when no covers test.

        The exemption applies ONLY when test_required is exactly the Python boolean
        False.  When test_required is True (or absent), enforcement is unchanged —
        a done AC without a covers test must still produce a violation.
        """
        ac_id = "BO-CODE-ENFORCED-CHANGED-001"
        ac_path = _write_done_ac(self.ac_root, ac_id, test_required=True)
        # test_root is intentionally empty — no covers tag

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            f"A done AC with test_required: true must still be reported when no "
            f"covers test exists — the exemption applies only to test_required: false. "
            f"Got violations: {violations}",
        )

    def test_done_ac_with_test_required_absent_is_still_reported(self) -> None:
        # covers: BO-2500a-3
        """A done AC with test_required absent (standard code AC) must be reported.

        When test_required is not present in the YAML (the common case for code ACs),
        data.get("test_required") returns None.  None is not False, so the exemption
        does NOT apply — standard enforcement proceeds.
        """
        ac_id = "BO-CODE-NO-REQUIRED-CHANGED-001"
        ac_path = _write_done_ac(self.ac_root, ac_id, test_required=None)
        # test_root is intentionally empty — no covers tag

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            f"A done AC with test_required absent must still be enforced. "
            f"The exemption applies only when test_required is exactly False. "
            f"Got violations: {violations}",
        )


# ---------------------------------------------------------------------------
# TestCheckAllDoneAcsExemption — check_all_done_acs
# ---------------------------------------------------------------------------


class TestCheckAllDoneAcsExemption(unittest.TestCase):
    """test_required: false exemption for check_all_done_acs().

    A done AC with test_required explicitly False must NOT be reported even when
    no covers-tagged test exists.  A done AC with test_required absent or True
    must still be reported when no covers test exists.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_done_ac_with_test_required_false_is_not_reported(self) -> None:
        # covers: BO-2500a-3
        """A done AC with test_required: false must NOT appear in check_all_done_acs.

        Mirrors the check_changed_done_acs exemption test: the full-store CI scan
        must also silently skip ACs with test_required: false.  This is the path
        the required 'Proof-of-done coverage check' CI job takes when the done-proof
        gate runs across the whole branch.

        BO-2500a-1-ii: the exemption is now the CONJUNCTION of
        ``test_required: false`` AND a non-empty ``test_rationale`` — a
        ``test_required: false`` AC with no recorded reason is no longer
        waived on its own. This fixture gained a real ``test_rationale`` so
        it still exercises the intended "docs AC, no covers tag needed"
        accept path under the corrected rule, rather than the now-closed
        "no reason required" gap the fixture originally (and incompletely)
        pinned.
        """
        ac_id = "BO-DOCS-EXEMPT-ALL-001"
        _write_done_ac(
            self.ac_root,
            ac_id,
            test_required=False,
            test_rationale=(
                "Pure prose documentation change; no covers-tagged test can "
                "meaningfully assert the correctness of explanatory prose."
            ),
        )
        # test_root is intentionally empty — no covers tag

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            f"A done AC with test_required: false must NOT be reported by "
            f"check_all_done_acs even when no covers test exists. "
            f"Got violations: {violations}",
        )

    def test_done_ac_with_test_required_true_is_still_reported(self) -> None:
        # covers: BO-2500a-3
        """A done AC with test_required: true must still be reported by check_all_done_acs.

        The exemption applies ONLY to the exact Python boolean False.  test_required: true
        is a code AC explicitly flagged as test-required; enforcement must proceed
        unchanged when no covers test is found.
        """
        ac_id = "BO-CODE-ENFORCED-ALL-001"
        _write_done_ac(self.ac_root, ac_id, test_required=True)
        # test_root is intentionally empty — no covers tag

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            f"A done AC with test_required: true must still be enforced by "
            f"check_all_done_acs. The exemption only applies to test_required: false. "
            f"Got violations: {violations}",
        )


# ---------------------------------------------------------------------------
# TestCheckStagedDoneProofsExemption — check_staged_done_proofs (pre-commit mode)
# ---------------------------------------------------------------------------


class TestCheckStagedDoneProofsExemption(unittest.TestCase):
    """test_required: false exemption for check_staged_done_proofs() (pre-commit mode).

    Closes the asymmetry between the CI-authoritative functions (which already
    exempt test_required: false ACs) and the pre-commit static scan (which, prior
    to this fix, had no such exemption and blocked every documentation-only AC).

    A done AC with test_required explicitly False must NOT be reported even when
    no covers-tagged test exists anywhere under test_root. A done AC with
    test_required True (or absent) must still be reported when no covers test
    exists, and must NOT be reported when a covers tag IS present — the ordinary,
    unexempted path must remain intact.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_done_ac_with_test_required_false_and_no_covers_tag_passes(self) -> None:
        # covers: BO-2500a-3
        """A staged done AC with test_required: false must NOT be a violation,
        even when no covers tag exists anywhere under test_root.

        This is the case that was previously mis-handled: check_staged_done_proofs
        had no test_required exemption, so a documentation AC (test_required: false)
        passed check_all_done_acs / check_changed_done_acs in CI but was blocked at
        pre-commit with "no covers tag found" — exactly the asymmetry this test
        guards against. Confirmed RED against the unmodified guard (before this fix,
        the AC appeared in violations because no covers-tag exemption existed).
        """
        ac_id = "BO-DOCS-EXEMPT-STAGED-001"
        ac_path = _write_done_ac(self.ac_root, ac_id, test_required=False)
        # test_root is intentionally empty — no covers tag exists anywhere

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            f"A staged done AC with test_required: false must NOT be reported by "
            f"check_staged_done_proofs even when no covers tag exists. "
            f"Got violations: {violations}",
        )

    def test_done_ac_with_test_required_true_and_no_covers_tag_still_fails(self) -> None:
        # covers: BO-2500a-3
        """A staged done AC with test_required: true must still be reported when
        no covers tag exists — the exemption must NOT weaken enforcement for ACs
        that genuinely require a test.

        This is the safety-property test: a blanket exemption (or one that keys
        on "no tag found" rather than the AC's own test_required field) would
        silently retire the guard for every AC, not just documentation ones.
        Confirmed this was ALREADY red/enforced before this fix (the pre-existing
        behavior for test_required: true was correct; only the False case was
        broken), so this test's purpose is to pin that correctness in place going
        forward, not to catch a new defect.
        """
        ac_id = "BO-CODE-ENFORCED-STAGED-001"
        ac_path = _write_done_ac(self.ac_root, ac_id, test_required=True)
        # test_root is intentionally empty — no covers tag

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            f"A staged done AC with test_required: true must still be reported by "
            f"check_staged_done_proofs when no covers tag exists — the exemption "
            f"applies only to test_required: false. Got violations: {violations}",
        )

    def test_done_ac_with_test_required_true_and_covers_tag_present_passes(self) -> None:
        # covers: BO-2500a-3
        """A staged done AC with test_required: true AND a present covers tag
        must NOT be reported — the ordinary, unexempted success path must
        continue to work unchanged after adding the test_required: false
        exemption alongside it.
        """
        ac_id = "BO-CODE-COVERED-STAGED-001"
        ac_path = _write_done_ac(self.ac_root, ac_id, test_required=True)
        covers_test_path = self.test_root / "test_covers_present_staged.py"
        covers_test_path.write_text(
            f"def test_something():\n    # covers: {ac_id}\n    pass\n",
            encoding="utf-8",
        )

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            f"A staged done AC with test_required: true and a present covers tag "
            f"must NOT be reported. Got violations: {violations}",
        )


if __name__ == "__main__":
    unittest.main()
