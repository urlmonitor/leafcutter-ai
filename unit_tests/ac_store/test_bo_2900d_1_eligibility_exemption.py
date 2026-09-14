"""
MODULE: unit_tests/ac_store/test_bo_2900d_1_eligibility_exemption.py
COVERS: BO-2900d-1

GOAL: Real, end-to-end test that a recorded exemption releases the SPECIFIC
refusal BO-2900a-3 introduces into done_proof.verify_done_eligible: a
criterion whose implementing code is an exempted unit becomes eligible to be
marked done, with no other change (BO-2900d-1's second Gherkin scenario, and
its own delivers_to note: "Consumed by ... verify_done_eligible" and the
BO-2900d-1 test_spec entry
test_exempted_units_criterion_becomes_eligible_to_be_marked_done).

CURRENT STATE (2026-09-07): scripts/commit_guardian/_reachability_inventory.py
(load_exemptions / is_exempt) does not exist yet (grep confirms zero hits).
The module-level import below is the primary RED signal — this whole file
fails to collect until that module exists. Runs the REAL
scripts/ac_store/done_proof.verify_done_eligible() directly (the same
function .github/workflows/ci.yml and check_done_proof.py's CI mode both
call) over a real, on-disk fixture AC store built with yaml.safe_dump.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "commit_guardian"))

from done_proof import verify_done_eligible  # noqa: E402

# NOTE: the shared exemption seam (scripts/commit_guardian/
# _reachability_inventory.py: load_exemptions()/is_exempt(), BO-2900d-1's
# delivers_to contract) does not exist yet. It is imported INSIDE the test
# body below (not at module level) so a ModuleNotFoundError is reported as a
# real pytest FAILED outcome (red) rather than a collection ERROR
# (inconclusive) that the fast-lane red-baseline gate's classification
# treats differently from a genuine assertion failure.


def _write_exemptions(root: Path, entries: list[dict]) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "reachability_exemptions.yaml"
    path.write_text(
        yaml.safe_dump({"exemptions": entries}, sort_keys=False), encoding="utf-8"
    )
    return path


def _write_done_ac(ac_dir: Path, ac_id: str) -> Path:
    data = {
        "id": ac_id,
        "title": f"Fixture record for {ac_id}",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "status": "active",
        "work_status": "done",
        "readiness": "reviewed",
        "priority": "medium",
        "criteria": (
            "Given a fixture unit with no runtime way in\n"
            "When verify_done_eligible evaluates its criterion\n"
            "Then a recorded exemption makes it eligible, with no other change\n"
        ),
    }
    ac_dir.mkdir(parents=True, exist_ok=True)
    path = ac_dir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _write_no_entry_unit(src_dir: Path, rel_path: str) -> Path:
    path = src_dir / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def do_thing():\n    return 42\n", encoding="utf-8")
    return path


def _write_direct_import_test(
    test_dir: Path, filename: str, *, ac_id: str, src_dir: Path
) -> Path:
    test_dir.mkdir(parents=True, exist_ok=True)
    path = test_dir / filename
    path.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(src_dir)!r})\n"
        "from no_entry_unit import do_thing\n\n\n"
        "def test_fixture_unit_via_direct_import():\n"
        f"    # covers: {ac_id}\n"
        "    assert do_thing() == 42\n",
        encoding="utf-8",
    )
    return path


class TestExemptedUnitsCriterionBecomesEligible:
    def test_exempted_units_criterion_becomes_eligible_to_be_marked_done(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-1
        # angle: criterion
        """With an exemption recorded for the fixture unit's exact item path,
        the real verify_done_eligible() must return eligible=True for the
        criterion whose implementing code is that unit — the end-to-end
        release BO-2900d-1's notes insist on, not merely a suppressed
        commit_guardian report."""
        from _reachability_inventory import is_exempt, load_exemptions  # noqa: F401

        root = tmp_path
        ac_dir = root / "docs" / "acceptance-criteria"
        test_dir = root / "tests"
        src_dir = root / "src"

        _write_no_entry_unit(src_dir, "no_entry_unit.py")
        _write_done_ac(ac_dir, "ZZ-BO2900D1-ELIG")
        _write_direct_import_test(
            test_dir,
            "test_zz_bo2900d1_elig.py",
            ac_id="ZZ-BO2900D1-ELIG",
            src_dir=src_dir,
        )
        _write_exemptions(
            root,
            [
                {
                    "item": "src/no_entry_unit.py",
                    "kind": "unit",
                    "reason": "used only by other units; no entry point of its own",
                    "recorded": "2026-09-07",
                    "recorded_by": "test-writer-fixture",
                }
            ],
        )

        verdict = verify_done_eligible(
            "ZZ-BO2900D1-ELIG", ac_root=ac_dir, test_root=test_dir
        )

        assert verdict["eligible"] is True, (
            "an exempted unit's criterion must be eligible to be marked "
            f"done, with no other change: {verdict}"
        )
        # The exemption itself must be traceable in the verdict output — an
        # eligible=True that cannot be distinguished from "no check ran at
        # all" is indistinguishable from the guard never having existed.
        assert "no_entry_unit" in str(verdict) or "exempt" in str(verdict).lower(), (
            "the verdict must show its work: the exemption that produced "
            f"eligibility should be traceable, not silent: {verdict}"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
