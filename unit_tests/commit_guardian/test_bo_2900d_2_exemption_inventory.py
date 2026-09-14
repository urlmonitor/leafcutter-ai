"""
MODULE: unit_tests/commit_guardian/test_bo_2900d_2_exemption_inventory.py
COVERS: BO-2900d-2

GOAL: Behavioral, REAL-ENTRY-POINT tests for "Every exemption in force is
listed with its reason on every run, so the set can be reviewed and
counted".

CURRENT STATE (2026-09-07): scripts/commit_guardian/check_done_proof.py's
main() (the real "reachability guard" entry point — invoked exactly this way
from .github/workflows/ci.yml:228 and registered as the commit_guardian.json
"check-done-proof" hook) currently does:

    if not violations:
        return 0

on a CLEAN run — it prints NOTHING AT ALL when there are no violations. This
is the exact defect this AC exists to close (see its own notes: "The natural
implementation prints exemptions only when explaining a suppressed finding
... nobody ever sees the whole list"). Confirmed by reading
templates/scripts/commit_guardian/check_done_proof.py:668-673 directly: the
clean-run branch returns before any print statement is reached. So on every
test below that expects a listing on a clean run, stdout is today empty —
guaranteed, real RED, not a guess.

Also confirmed: no `_reachability_inventory` module exists yet (BO-2900d-1's
own shared seam, which this AC's own expects_from names as its dependency),
so even the refusing-run test (which finds SOME output today, from an
unrelated "no linked test" finding) cannot show an exemption listing.

ENTRY POINT: the REAL deployed scripts/commit_guardian/check_done_proof.py
CLI, run via subprocess with --mode ci — never imported and called directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900d_fixtures import (  # noqa: E402
    init_fixture_project,
    run_check_done_proof,
    write_exemptions,
)


def _seven_exemptions() -> list[dict]:
    return [
        {
            "item": f"src/helper_{i}.py",
            "kind": "unit",
            "reason": f"used only internally by module {i}",
            "recorded": "2026-09-07",
            "recorded_by": "test-writer-fixture",
        }
        for i in range(1, 8)
    ]


class TestCleanRunWithSevenExemptionsListsAllSevenAndTheTotal:
    def test_clean_run_with_seven_exemptions_lists_all_seven_and_the_total(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-2
        # angle: reachability
        """On a clean run (zero findings — an empty AC store, so
        check_all_done_acs trivially reports zero violations) with seven
        recorded exemptions, the real guard's output must still list all
        seven items with their reasons and state a total of 7 — even though
        nothing in the change under check touched any of them."""
        root = init_fixture_project(tmp_path)
        ac_dir = root / "docs" / "acceptance-criteria"  # empty: zero done ACs
        test_dir = root / "tests"  # empty: zero covers-tagged tests
        exemptions = _seven_exemptions()
        write_exemptions(root, exemptions)

        result = run_check_done_proof(root, ac_root=ac_dir, test_root=test_dir)
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            "a run touching no exempted unit and finding nothing must still "
            f"exit clean. Got exit={result.returncode}\nstdout:\n"
            f"{result.stdout}\nstderr:\n{result.stderr}"
        )
        for entry in exemptions:
            assert entry["item"] in combined, (
                f"exemption {entry['item']} must be listed on every run, "
                f"including a clean one:\n{combined}"
            )
            assert entry["reason"] in combined, (
                f"exemption {entry['item']}'s reason must be listed "
                f"alongside it:\n{combined}"
            )
        assert "7" in combined, (
            "the total number of exemptions in force (7) must be stated "
            f"as its own value in the output:\n{combined}"
        )


class TestRecordingAnEighthExemptionChangesTheNextRunsTotalToEight:
    def test_recording_an_eighth_exemption_changes_the_next_runs_total_to_eight(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-2
        # angle: boundary
        """Appending an eighth exemption to the fixture registry and
        re-running must change the emitted total to 8 — the count is derived
        from the registry read, not a fixed string, and must track the
        registry across the one-more-than-baseline boundary."""
        root = init_fixture_project(tmp_path)
        ac_dir = root / "docs" / "acceptance-criteria"
        test_dir = root / "tests"
        exemptions = _seven_exemptions()
        write_exemptions(root, exemptions)

        first_result = run_check_done_proof(root, ac_root=ac_dir, test_root=test_dir)
        assert "7" in (first_result.stdout + first_result.stderr)

        eighth = {
            "item": "src/helper_8.py",
            "kind": "unit",
            "reason": "used only internally by module 8",
            "recorded": "2026-09-07",
            "recorded_by": "test-writer-fixture",
        }
        write_exemptions(root, [*exemptions, eighth])

        second_result = run_check_done_proof(root, ac_root=ac_dir, test_root=test_dir)
        combined = second_result.stdout + second_result.stderr

        assert second_result.returncode == 0
        assert eighth["item"] in combined, (
            f"the newly recorded eighth exemption must appear on the next "
            f"run:\n{combined}"
        )
        assert "8" in combined, (
            f"the stated total must change from 7 to 8 on the next run "
            f"after the registry changes:\n{combined}"
        )


class TestListingIsPresentOnARefusingRunAsWellAsACleanOne:
    def test_listing_is_present_on_a_refusing_run_as_well_as_a_clean_one(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-2
        # angle: reachability
        """A run that DOES produce a finding (a done AC with no covering
        test at all, tripping check_done_proof's existing 'no linked test
        found' violation) must show BOTH that finding AND the full exemption
        listing — the two output sections are independent; a finding must
        never suppress the inventory."""
        root = init_fixture_project(tmp_path)
        ac_dir = root / "docs" / "acceptance-criteria"
        test_dir = root / "tests"
        test_dir.mkdir(parents=True, exist_ok=True)

        # A "done" AC with zero covering tests anywhere: an unconditional,
        # unrelated finding via the EXISTING (already-implemented)
        # no-linked-test-found rule in verify_done_eligible.
        import yaml

        ac_dir.mkdir(parents=True, exist_ok=True)
        (ac_dir / "ZZ-BO2900D2-REFUSE.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ZZ-BO2900D2-REFUSE",
                    "title": "Fixture record with no covering test",
                    "component": "build-orchestration",
                    "components": ["build_orchestration"],
                    "status": "active",
                    "work_status": "done",
                    "readiness": "reviewed",
                    "priority": "medium",
                    "criteria": "Given a fixture\nWhen evaluated\nThen it has no covering test\n",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        exemptions = _seven_exemptions()
        write_exemptions(root, exemptions)

        result = run_check_done_proof(root, ac_root=ac_dir, test_root=test_dir)
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "a done AC with no covering test must still be refused:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "ZZ-BO2900D2-REFUSE" in combined, (
            f"the unrelated finding must still be reported:\n{combined}"
        )
        for entry in exemptions:
            assert entry["item"] in combined, (
                f"the exemption listing must appear even on a refusing "
                f"run — a finding must never suppress the inventory: "
                f"{combined}"
            )
        assert "7" in combined, (
            f"the stated total must appear on the refusing run too:\n{combined}"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
