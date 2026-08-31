"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_3_deployed.py
COVERS: BP-1100g-3

GOAL: RED test stub for the "reachability" leg of BP-1100g-3's test_spec --
    the second tag axis (which kind of proof a test was written to give) must
    be collected through the DEPLOYED copy of scripts/ac_store/done_proof.py,
    not only through a source-tree import.

WHY THE DEPLOYED COPY, SPECIFICALLY: done_proof.py backs a deployed
    pre-commit hook (check_done_proof.py) and a CI gate. On 2026-07-22 this
    exact module shipped with a missing scripts/build_phases.py
    build_ac_store deploy_map entry, so the DEPLOYED hook raised
    ModuleNotFoundError while every source-tree test stayed green. Importing
    done_proof from scripts/ac_store/ (the source tree) is structurally
    blind to that class of gap -- it sits right next to whatever new sibling
    module the fix might add, so a missing deploy_map registration for that
    sibling would never surface. This test instead imports the DEPLOYED
    copy at .leafcutter/scripts/ac_store/done_proof.py, in a FRESH
    subprocess whose sys.path is restricted to only that directory, so a
    missing deploy_map entry surfaces as the same ModuleNotFoundError a real
    deployed hook run would hit.

    Per the established convention for this class of test in this repo (see
    unit_tests/ac_store/test_bo_2900g_3.py's
    TestDeployedAcSchemaGateRejectsARetiredKind and
    unit_tests/build_orchestration/test_bo2400e_3_durable_write.py's
    TestDurableWriterPresentInDeployedLayout), the already-deployed copy
    present in this worktree's .leafcutter/ is used directly -- ASSERTED to
    exist, never skipped, never re-built inside the test. A missing deployed
    module is the exact failure this test exists to catch, not a reason to
    skip. (python-coder's own post_write_commands for this ticket already
    run `python scripts/build.py --target-dir .` before test-runner
    re-verifies, so the deployed copy is current by the time this test is
    expected to go green.)

WHY THIS DOES NOT DRIVE check_done_proof.py's OWN CLI VERDICT: BP-1100g-3-i
    (the falsifiability sibling of this AC) makes it a hard boundary that
    the new angle axis must never enter _classify_outcomes or
    verify_done_eligible -- i.e. it must stay INVISIBLE to
    check_done_proof.py's eligible/ineligible verdict by design. A test that
    only asserted the CLI's exit code could therefore never observe whether
    the angle axis was actually collected; it would pass identically whether
    or not python-coder had implemented anything at all. The only genuine
    way to observe "the deployed hook path collects them" is to call the
    deployed scanner's own new collection entry point directly and read its
    return value -- which is what this test does.

=== Interface contract under test ===

  See unit_tests/ac_store/test_bp_1100g_3.py's module docstring for the full
  collect_test_tag_records(test_root) -> list[dict] contract. This file only
  adds the deployed-layout exercise of that same function.

=== Red baseline ===

  RED today with a subprocess ModuleNotFoundError / AttributeError-shaped
  failure inside the child process (surfaced here as a non-zero exit code
  and the child's stderr in the assertion message), because
  collect_test_tag_records does not exist yet in the deployed
  .leafcutter/scripts/ac_store/done_proof.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEPLOYED_AC_STORE_DIR = _REPO_ROOT / ".leafcutter" / "scripts" / "ac_store"
_DEPLOYED_DONE_PROOF = _DEPLOYED_AC_STORE_DIR / "done_proof.py"


class TestSecondAxisCollectedThroughTheDeployedDoneProofHook(unittest.TestCase):
    def test_bp_1100g_3_second_axis_is_collected_through_the_deployed_done_proof_hook(
        self,
    ) -> None:
        # covers: BP-1100g-3
        """PRODUCTION ENTRY POINT: run against a real on-disk test tree
        carrying both tag axes, via a fresh subprocess importing the
        DEPLOYED done_proof.py (not the source tree) -- assert the deployed
        scanner collects both axes for the same test function."""
        self.assertTrue(
            _DEPLOYED_DONE_PROOF.is_file(),
            f"deployed done_proof.py not found at {_DEPLOYED_DONE_PROOF} -- run "
            "`python scripts/build.py --target-dir .` first; a missing "
            "deployed module is a failure, not a reason to skip",
        )

        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            (test_root / "test_deployed_probe.py").write_text(
                textwrap.dedent(
                    '''\
                    def test_probe_function():
                        # covers: ZZ-1100g-3-deployed-probe
                        # angle: reachability
                        assert True
                    '''
                ),
                encoding="utf-8",
            )

            driver = test_root / "_driver.py"
            driver.write_text(
                textwrap.dedent(
                    f'''\
                    import json
                    import sys
                    from pathlib import Path

                    sys.path.insert(0, {str(_DEPLOYED_AC_STORE_DIR)!r})
                    from done_proof import collect_test_tag_records

                    records = collect_test_tag_records(Path({str(test_root)!r}))
                    print(json.dumps(records, default=str))
                    '''
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(driver)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(
                result.returncode,
                0,
                "importing collect_test_tag_records from the DEPLOYED "
                "done_proof.py and running it against a real on-disk test "
                "tree must succeed in a fresh subprocess whose sys.path is "
                "restricted to the deployed ac_store directory. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )

            records = json.loads(result.stdout)

        by_function = {r["function"]: r for r in records}
        self.assertIn(
            "test_probe_function",
            by_function,
            f"deployed scanner did not produce a record for the probe function: {records}",
        )
        probe = by_function["test_probe_function"]
        self.assertEqual(probe["covers"], ["ZZ-1100g-3-deployed-probe"])
        self.assertEqual(probe["angles"], ["reachability"])


if __name__ == "__main__":
    unittest.main()
