"""
MODULE: unit_tests/commit_guardian/test_ge_127d_2_reachability_and_deployed.py
COVERS: GE-127d-2 -- reachability and deployed descriptors (split from
    test_ge_127d_2.py per this repo's own file-size gate).

GOAL: PRODUCTION ENTRY POINT (a REAL `git commit` through the registered
    `run_hook.py` -> `check_file_size.py` path) and DEPLOYED COPY (a REAL
    `build.py` deploy, reusing the shared fixture `_ge_127d_1_fixture.py`
    already provides per this ticket's own binding constraint: reuse an
    existing deployed-layout fixture rather than adding a new build.py
    invocation site) descriptors.

DECISION HISTORY
- 2026-09-22 [GE-127d-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_1_fixture as ge127d1fx  # noqa: E402 -- shared deployed-layout fixture (reused, not duplicated)
import _ge_127d_2_fixture as fx  # noqa: E402

_REAL_OVERSIZED_SOURCE = (
    ge127d1fx._REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_done_proof.py"
)


class TestQuotedLengthAndMeasuresStatementReachRegisteredHookOutput(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_ge_127d_2_the_quoted_length_and_its_measurement_statement_reach_the_registered_hook_output(self):
        # covers: GE-127d-2
        # angle: reachability
        """PRODUCTION ENTRY POINT: python .../run_hook.py .../check_file_size.py,
        mirrored here via a real, minimal single-hook `.pre-commit-config.yaml`
        plus a REAL ordinary `git commit` -- exactly as GE-127a-1's and
        GE-127d-1's own reachability descriptors do for their sibling gates.
        A quoted length or a Measures statement only a direct script call can
        see is inert -- the defect this whole record exists to close. The
        exit status must be the commit outcome itself (a refused commit
        creates no new commit object), not merely an advisory note.

        RED TODAY: no Measures line exists in the hook's own output.
        """
        fx.build_fixture_tree(self.root, line_limit=5)
        fx.write_precommit_config(self.root)
        fx.install_precommit(self.root)

        before_log = fx.git(["rev-list", "--count", "HEAD"], self.root)
        before_count = before_log.stdout.strip() if before_log.returncode == 0 else "0"

        content = fx.python_lines_with_docstring(counted_code_lines=8, docstring_body_lines=4)
        fx.write_and_stage(self.root, "oversized.py", content)
        result = fx.commit(self.root, "attempt an oversized commit")
        combined = fx.combined_output(result)

        self.assertNotEqual(
            0, result.returncode, msg=f"the registered hook path must refuse the commit. Got: {combined!r}"
        )
        after_log = fx.git(["rev-list", "--count", "HEAD"], self.root)
        after_count = after_log.stdout.strip() if after_log.returncode == 0 else "0"
        self.assertEqual(
            before_count,
            after_count,
            msg="a refused commit must not create a new commit object -- the exit status must be the real outcome.",
        )

        parsed = fx.parse_lines_and_limit(combined)
        self.assertIsNotNone(
            parsed, msg=f"the registered hook path's own output must quote Lines/Limit. Got: {combined!r}"
        )
        measures = fx.extract_measures_line(combined)
        self.assertIsNotNone(
            measures,
            msg=f"the registered hook path's own output must state what the length measures. Got: {combined!r}",
        )


class TestDeployedCopyQuotesLengthReproducibleFromDeployedPublishedRule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # Reuses the EXISTING deployed-layout fixture per this ticket's own
        # instruction, rather than adding a new build.py invocation site
        # (CLAUDE.md: do not add a test that spawns its own build.py).
        ge127d1fx.build_deployed_fixture_repo(self.root)
        fx.init_repo(self.root)

    def test_ge_127d_2_the_deployed_copy_quotes_a_length_reproducible_from_its_deployed_published_rule(self):
        # covers: GE-127d-2
        # angle: deployed
        """After a REAL `build.py` deploy, run the DEPLOYED check_file_size.py
        against a REAL, currently oversized TRACKED file's actual content
        (check_done_proof.py, ~663 counted lines against the real 400 limit)
        -- never a synthetic literal. A helper outside
        templates/scripts/commit_guardian/ with no scripts/build_phases.py
        deploy-map entry surfaces here as ModuleNotFoundError rather than
        passing. Applying the DEPLOYED published rule independently must
        arrive at exactly the length the deployed gate quotes.

        RED TODAY: no Measures line is deployed yet, so the independently
        -derived count (raw physical lines, no discard applied) diverges
        from the real, docstring-aware deployed quoted length.
        """
        deployed_script = self.root / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_script.exists(), msg=f"{deployed_script} was not deployed by build.py.")

        real_content = _REAL_OVERSIZED_SOURCE.read_text(encoding="utf-8")
        fx.write_and_stage(self.root, "real_oversized_file.py", real_content)

        result = fx.run([fx.PYTHON, str(deployed_script)], self.root)
        combined = fx.combined_output(result)

        self.assertNotIn(
            "ModuleNotFoundError", combined, msg=f"the deployed gate crashed importing a dependency. Got: {combined!r}"
        )
        self.assertNotEqual(0, result.returncode, msg=f"the real oversized file must be refused. Got: {combined!r}")

        parsed = fx.parse_lines_and_limit(combined)
        self.assertIsNotNone(parsed, msg=f"the deployed gate must quote Lines/Limit. Got: {combined!r}")
        quoted_length, _permitted = parsed

        categories = fx.parse_discard_categories(fx.extract_measures_line(combined))
        rederived = fx.independent_count_content_lines(real_content, categories)
        self.assertEqual(
            quoted_length,
            rederived,
            msg=(
                "applying the DEPLOYED published rule independently must arrive at exactly "
                f"the deployed gate's quoted length. quoted={quoted_length} rederived={rederived} "
                f"categories={categories!r}. Got: {combined!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
