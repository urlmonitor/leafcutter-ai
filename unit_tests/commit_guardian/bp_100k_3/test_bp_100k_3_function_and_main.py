"""
MODULE: unit_tests/commit_guardian/bp_100k_3/test_bp_100k_3_function_and_main.py
GOAL: The BP-100k-3 regression that check_output_drift() the FUNCTION and
    main() the hook entry point apply the identical contract to the
    identical tree: given an unrecorded, undeclared output, both signal it
    as a gap, both emit the RESULT line, and both reach the same verdict.
CONTRACT: the output and exit-code contract both entry points are held to is
    stated in the module docstring of ``_support.py`` in this package.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/commit_guardian/test_bp_100k_3.py when that file was split; the
  class takes its workspace and synthetic package from
  SyntheticPackageTestCase.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr

from unit_tests.commit_guardian.bp_100k_3._support import (
    _RESULT_LINE_RE,
    SyntheticPackageTestCase,
    _deploy_commit_guardian_dir,
    _run_hook,
    _sha256_bytes,
    _write_manifest,
)


# ---------------------------------------------------------------------------
# Regression: check_output_drift() the FUNCTION and main() must agree.
#
# Adversarial review (2026-08-25) found that main() reimplemented the whole
# scan+report+verdict sequence inline and never called the module-level
# check_output_drift() function at all. That left check_output_drift() still
# carrying the OLDER, permissive contract described in the r1 DECISION
# HISTORY entry ("legacy 0/1 contract preserved for direct callers"): it
# returned 0 and printed no RESULT line even when the tree held an
# unrecorded, undeclared output. A caller that imports and invokes
# check_output_drift() directly — this module's own docstring names
# unit_tests/build_guards/test_bp100_drift_docs_compile.py as exactly such a
# caller — got a silent clean verdict on a gap the real pre-commit hook
# (main()) would have blocked. Two contracts in one module is how the next
# drift-gate regression hides: whichever code path a caller happens to take
# decides whether drift is caught at all.
# ---------------------------------------------------------------------------


class TestFunctionAndMainAgreeOnAnUnrecordedArtifact(SyntheticPackageTestCase):
    """check_output_drift() (the function) and main() (the hook entry point)
    must apply the identical contract to the identical tree: given an
    unrecorded, undeclared output, BOTH must signal it (never return/exit 0)
    and BOTH must emit the RESULT summary line."""

    def setUp(self) -> None:
        super().setUp()

        agents_dir = self.workspace / ".claude" / "agents"

        recorded_content = b"# recorded output\nmatches the manifest\n"
        self.recorded = agents_dir / "recorded.md"
        self.recorded.write_bytes(recorded_content)
        recorded_key = self.recorded.relative_to(self.workspace).as_posix()

        # Never registered in output_mappings and never declared exempt — the
        # unrecorded artifact both entry points must signal as a GAP.
        self.unrecorded = agents_dir / "unrecorded_new_output.md"
        self.unrecorded.write_bytes(b"# unrecorded output\nnever registered\n")
        self.unrecorded_key = self.unrecorded.relative_to(self.workspace).as_posix()

        _write_manifest(
            self.pkg_root,
            {},
            {
                recorded_key: {
                    "template": "templates/agents/recorded.md",
                    "expected_output_hash": _sha256_bytes(recorded_content),
                }
            },
        )

        self.deployed_dir = _deploy_commit_guardian_dir(self.workspace)
        self.hook = self.deployed_dir / "check_output_drift.py"
        self.manifest_path = self.workspace / ".build_manifest.json"

    def _import_deployed_module(self):
        """Load the deployed check_output_drift.py as a fresh module object.

        Uses importlib.util (never a plain ``import``) so this test drives
        the SAME on-disk deployed copy ``_run_hook`` executes as a subprocess
        — never a hand-typed re-implementation — while still getting a fresh
        module object per test (a sys.modules-cached import would let one
        test's module state leak into another's).
        """
        spec = importlib.util.spec_from_file_location(
            "check_output_drift_function_contract_probe", self.hook
        )
        module = importlib.util.module_from_spec(spec)
        guardian_dir = self.hook.parent
        if str(guardian_dir) not in sys.path:
            sys.path.insert(0, str(guardian_dir))
        spec.loader.exec_module(module)
        return module

    def test_function_signals_the_gap_and_emits_the_result_line(self) -> None:
        # covers: BP-100k-3
        module = self._import_deployed_module()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = module.check_output_drift(
                output_dirs=[self.workspace / ".claude" / "agents"],
                manifest_path=self.manifest_path,
                repo_root=self.workspace,
            )
        combined = stderr.getvalue()

        self.assertNotEqual(
            0,
            result,
            msg=(
                "check_output_drift() the FUNCTION returned 0 (clean) on a "
                f"tree with an unrecorded, undeclared output "
                f"({self.unrecorded_key}). A direct caller of this function "
                "must never see a clean verdict the pre-commit hook itself "
                f"would block. Output:\n{combined}"
            ),
        )
        self.assertIn(
            f"UNCOMPARABLE: GAP {self.unrecorded_key}",
            combined,
            msg=(
                "check_output_drift() the FUNCTION did not report the "
                f"unrecorded output as a coverage gap. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "check_output_drift() the FUNCTION printed no RESULT summary "
                f"line. Output:\n{combined}"
            ),
        )

    def test_main_signals_the_same_gap_and_emits_the_result_line(self) -> None:
        # covers: BP-100k-3
        result = _run_hook(self.hook, self.workspace, exemption_config=None)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "check-output-drift's main() exited 0 (clean) on a tree with "
                f"an unrecorded, undeclared output ({self.unrecorded_key}). "
                f"Output:\n{combined}"
            ),
        )
        self.assertIn(
            f"UNCOMPARABLE: GAP {self.unrecorded_key}",
            combined,
            msg=f"main() did not report the unrecorded output as a coverage gap. Output:\n{combined}",
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=f"main() printed no RESULT summary line. Output:\n{combined}",
        )

    def test_function_and_main_reach_the_identical_verdict(self) -> None:
        # covers: BP-100k-3
        module = self._import_deployed_module()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            function_result = module.check_output_drift(
                output_dirs=[self.workspace / ".claude" / "agents"],
                manifest_path=self.manifest_path,
                repo_root=self.workspace,
            )

        main_result = _run_hook(self.hook, self.workspace, exemption_config=None)

        # Both entry points scan the identical tree, so they must reach the
        # identical tri-state verdict (0 clean / 1 drift / 2 gap) — not
        # merely "both non-zero". A bare both-non-zero check would stay green
        # even if a future change reintroduced two contracts that happened to
        # both fail, for different reasons, on this particular fixture.
        self.assertEqual(
            function_result,
            main_result.returncode,
            msg=(
                "check_output_drift() the FUNCTION and main() disagreed on "
                f"the exit verdict for the identical tree: "
                f"function={function_result} main={main_result.returncode}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
