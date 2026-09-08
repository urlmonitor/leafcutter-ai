"""
MODULE: unit_tests/commit_guardian/test_bo_2900d_1_reachability_exemption.py
COVERS: BO-2900d-1

GOAL: Behavioral, REAL-ENTRY-POINT tests for "Code with no way in passes only
on a recorded exemption carrying a reason, never by convention".

CURRENT STATE (2026-09-07): Neither the exemption registry
(config/reachability_exemptions.yaml), nor its shared loading seam
(scripts/commit_guardian/_reachability_inventory.py: load_exemptions() /
is_exempt()), nor the underlying "unit with no way in" refusal branch of
verify_done_eligible (BO-2900a-3's refusal_cause: 'no_entry_point_reaches_code')
exist yet in this worktree. Confirmed by grep: zero hits for
'reachability_exemptions', '_reachability_inventory', or
'no_entry_point_reaches_code' anywhere under scripts/. These tests are
therefore RED for the correct reason: check_done_proof.py's CI-mode run
currently reports zero violations for every fixture below regardless of
exemption state, because there is no reachability check to exempt anything
FROM yet.

The module-level import below is the primary, robust RED signal (collection
error) — the delivers_to contract this AC promises
(scripts/commit_guardian/_reachability_inventory.py: load_exemptions(),
is_exempt()) does not exist, so importing it fails before any test body runs.
The behavioral assertions inside each test body encode the actual target
behavior the coder must satisfy once that module exists.

ENTRY POINT: the REAL deployed scripts/commit_guardian/check_done_proof.py
CLI, run via subprocess with --mode ci, exactly as it is invoked from
.github/workflows/ci.yml:228 and registered as the commit_guardian.json
"check-done-proof" hook (CI-authoritative backstop mode) — never imported
and called directly, and never a hand-rolled reachability scanner.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "commit_guardian")
)

from _bo_2900d_fixtures import (  # noqa: E402
    init_fixture_project,
    run_check_done_proof,
    write_direct_import_test,
    write_done_ac,
    write_exemptions,
    write_no_entry_unit,
)

# Matches ONLY the real per-AC finding line check_done_proof.py prints —
# ``print(f"[check-done-proof] {v['ac_id']}: {v['reason']}")`` — never the
# BO-2900d-2 exemption-inventory lines, which have a different shape
# (``[check-done-proof] exemption in force: ...`` / ``[check-done-proof]
# exemptions in force: N``): those have a space, not a colon, immediately
# after the leading word, so they cannot match ``\S+:``.
_FINDING_LINE_RE = re.compile(r"^\[check-done-proof\] \S+: .*$", re.MULTILINE)


def _finding_lines(combined: str) -> str:
    """Return only the guard's real per-AC finding lines from `combined`.

    BO-2900d-2 mandates that the exemption inventory (item + reason for
    every recorded exemption) is printed on every run, refusing or clean.
    That inventory necessarily mentions an exempted unit's path — so a test
    that greps the WHOLE combined output for the exempted unit's name is
    testing the wrong thing: BO-2900d-1 only promises the unit is not
    reported as a *finding*, not that it is absent from the output text
    entirely. Isolating the finding-shaped lines lets a test tell "reported
    as a violation" apart from "named in the exemption inventory".
    """
    return "\n".join(m.group(0) for m in _FINDING_LINE_RE.finditer(combined))

# NOTE: the shared exemption seam (scripts/commit_guardian/
# _reachability_inventory.py: load_exemptions()/is_exempt(), BO-2900d-1's
# delivers_to contract) does not exist yet. It is imported INSIDE
# TestSharedSeamContractShape's test body below (not at module level) so a
# ModuleNotFoundError there is reported as a real pytest FAILED outcome
# (red) rather than a collection ERROR (inconclusive) that would mask the
# other three behavioral tests in this file from the fast-lane red-baseline
# gate's red/green classification.


class TestUnitWithNoWayInAndNoExemptionIsReportedAndRefused:
    def test_unit_with_no_way_in_and_no_exemption_is_reported_and_refused(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-1
        # angle: failure
        """A fixture unit with no runtime way in, proven only by a test that
        imports it directly, and NO recorded exemption, must be reported by
        the real guard and the change refused (non-zero exit naming the
        unit)."""
        root = init_fixture_project(tmp_path)
        ac_dir = root / "docs" / "acceptance-criteria"
        write_no_entry_unit(root / "src", "no_entry_unit.py")
        write_done_ac(ac_dir, "ZZ-BO2900D1-1")
        write_direct_import_test(
            root / "tests",
            "test_zz_bo2900d1_1.py",
            ac_id="ZZ-BO2900D1-1",
            module_name="no_entry_unit",
            src_dir_for_import=root / "src",
        )
        write_exemptions(root, [])  # explicit: no exemption recorded

        result = run_check_done_proof(
            root, ac_root=ac_dir, test_root=root / "tests"
        )
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "a unit with no runtime way in and no recorded exemption must "
            f"be REFUSED (non-zero exit). Got exit={result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "no_entry_unit" in combined, (
            "the refusal must name the offending unit so the finding is "
            f"discoverable:\n{combined}"
        )


class TestRecordedExemptionSuppressesAndAnnounces:
    def test_recorded_exemption_suppresses_the_finding_and_is_announced_in_the_output(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-1
        # angle: reachability
        """The identical fixture unit, this time with an exemption recorded
        for its exact item path, must NOT be reported as a finding — and the
        accepted exemption (item + reason) must be announced in the guard's
        output rather than passing silently."""
        root = init_fixture_project(tmp_path)
        ac_dir = root / "docs" / "acceptance-criteria"
        write_no_entry_unit(root / "src", "no_entry_unit.py")
        write_done_ac(ac_dir, "ZZ-BO2900D1-2")
        write_direct_import_test(
            root / "tests",
            "test_zz_bo2900d1_2.py",
            ac_id="ZZ-BO2900D1-2",
            module_name="no_entry_unit",
            src_dir_for_import=root / "src",
        )
        exempt_reason = "used only by other units; entry point deliberately omitted"
        write_exemptions(
            root,
            [
                {
                    "item": "src/no_entry_unit.py",
                    "kind": "unit",
                    "reason": exempt_reason,
                    "recorded": "2026-09-07",
                    "recorded_by": "test-writer-fixture",
                }
            ],
        )

        result = run_check_done_proof(
            root, ac_root=ac_dir, test_root=root / "tests"
        )
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            "an exempted unit must not cause a refusal. Got "
            f"exit={result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "src/no_entry_unit.py" in combined, (
            "the accepted exemption must announce the exact item it covers, "
            f"not pass silently:\n{combined}"
        )
        assert exempt_reason in combined, (
            "the accepted exemption must announce its stated reason, "
            f"not pass silently:\n{combined}"
        )


class TestSiblingMatchingNameExtensionAndFolderIsStillReported:
    def test_sibling_matching_name_extension_and_folder_is_still_reported(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-2900d-1
        # angle: failure
        """A second unit sharing the exempted unit's file name, extension,
        and containing folder NAME, at a different exact item path with no
        exemption of its own, must still be reported — matching is exact and
        item-scoped; nothing else may confer a pass."""
        root = init_fixture_project(tmp_path)
        ac_dir = root / "docs" / "acceptance-criteria"

        # Exempted unit.
        write_no_entry_unit(root / "src", "module_a/helpers/no_entry_unit.py")
        write_done_ac(ac_dir, "ZZ-BO2900D1-3A")
        write_direct_import_test(
            root / "tests",
            "test_zz_bo2900d1_3a.py",
            ac_id="ZZ-BO2900D1-3A",
            module_name="no_entry_unit",
            src_dir_for_import=root / "src" / "module_a" / "helpers",
        )

        # Sibling: same filename, extension, and folder NAME ("helpers"),
        # different exact repo-relative item — deliberately NOT exempted.
        write_no_entry_unit(root / "src", "module_b/helpers/no_entry_unit.py")
        write_done_ac(ac_dir, "ZZ-BO2900D1-3B")
        write_direct_import_test(
            root / "tests",
            "test_zz_bo2900d1_3b.py",
            ac_id="ZZ-BO2900D1-3B",
            module_name="no_entry_unit",
            src_dir_for_import=root / "src" / "module_b" / "helpers",
        )

        write_exemptions(
            root,
            [
                {
                    "item": "src/module_a/helpers/no_entry_unit.py",
                    "kind": "unit",
                    "reason": "recorded exemption for module_a only",
                    "recorded": "2026-09-07",
                    "recorded_by": "test-writer-fixture",
                }
            ],
        )

        result = run_check_done_proof(
            root, ac_root=ac_dir, test_root=root / "tests"
        )
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "a look-alike sibling with no exemption of its own must still "
            f"be refused. Got exit={result.returncode}\nstdout:\n"
            f"{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "module_b" in combined, (
            "the unexempted sibling (module_b) must be named in the "
            f"refusal:\n{combined}"
        )
        finding_lines = _finding_lines(combined)
        assert "module_a" not in finding_lines, (
            "the exempted unit (module_a) must not itself be reported as a "
            "finding (checked the guard's finding lines only — "
            "'[check-done-proof] <ac_id>: <reason>' — not the BO-2900d-2 "
            f"exemption inventory, which is required to name it):\n"
            f"finding lines:\n{finding_lines!r}\nfull output:\n{combined}"
        )


# Sanity: the shared seam's two functions must exist as *callables* once the
# import above succeeds, per BO-2900d-1's delivers_to contract.
class TestSharedSeamContractShape:
    def test_load_exemptions_and_is_exempt_are_callable(self, tmp_path: Path) -> None:
        # covers: BO-2900d-1
        # angle: criterion
        """load_exemptions() -> list[dict] and is_exempt(item, exemptions) are
        the exact two functions BO-2900d-1's delivers_to contract promises;
        assert their basic call shape directly on the unit."""
        from _reachability_inventory import is_exempt, load_exemptions

        root = init_fixture_project(tmp_path)
        registry_path = root / "config" / "reachability_exemptions.yaml"
        write_exemptions(
            root,
            [
                {
                    "item": "src/foo.py",
                    "kind": "unit",
                    "reason": "only used internally",
                    "recorded": "2026-09-07",
                    "recorded_by": "test-writer-fixture",
                }
            ],
        )
        exemptions = load_exemptions(registry_path)
        assert isinstance(exemptions, list)
        assert len(exemptions) == 1
        assert exemptions[0]["item"] == "src/foo.py"
        assert is_exempt("src/foo.py", exemptions) is True
        assert is_exempt("src/bar.py", exemptions) is False


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
