"""
MODULE: unit_tests/commit_guardian/test_ge_118d_deployed.py
COVERS: GE-118d -- "A document's path-bearing frontmatter entries are
    resolved whichever of the two accepted shapes they use"

GOAL: The DEPLOYED-LAYOUT and PRODUCTION-ENTRY-POINT half of GE-118d's suite.
    Split out of unit_tests/commit_guardian/test_ge_118d.py (which now keeps
    the failure / criterion / real_artifact angles) purely so both files stay
    inside the 400-content-line file-size ratchet -- this is a move, not a
    rewrite: every class, test, assertion and `# covers:` tag below is
    verbatim the one that file already carried. Shared fixture helpers now
    live in the sibling module `_ge_118d_fixtures.py`; see that module and
    test_ge_118d.py's own docstring for the full defect description, the
    resolver's contract, and the RED-baseline record.

WHY THESE TWO BELONG TOGETHER: both invoke the guard through its REAL
    production entry point (``python run_hook.py check_doc_frontmatter.py
    <files...>``, mirroring pre-commit's own invocation) rather than importing
    a validator function -- one against a REAL, FRESH `python scripts/build.py
    --target-dir <tmp>` deployment, one against the SOURCE tree.

LOAD-BEARING, DO NOT "SIMPLIFY": Test 1 builds into a temp directory OUTSIDE
    this repository. A source-tree import -- or a target inside this repo --
    is the self-hosting mask that let a missing deploy-manifest entry stay
    green and reopened GE-118c. The resolver must be present in BOTH
    deploy-manifest locations (`deploy_scripts` in build_workflow_tools(),
    scripts/build_phases_workflows.py; and the tuple inside
    _manifest_workflow_tool_scripts(), scripts/build_phases_knowledge.py), and
    this test's temp build is what exercises that. The division of labour
    between the deployed arm and the source-tree arm mirrors the module
    docstring of test_ge_127c_1_deployed_reachability.py.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ._ge_118d_fixtures import (
    _BUILD_PY,
    _BUILD_TIMEOUT_SECONDS,
    _SUBPROCESS_TIMEOUT_SECONDS,
    _four_entry_doc_frontmatter,
    _init_repo,
    _run_hook_against_source,
    _write,
    _write_four_entry_targets,
    PYTHON,
)


# ---------------------------------------------------------------------------
# Test 1 -- angle: deployed
# ---------------------------------------------------------------------------


class TestGe118dDeployedGuardAcceptsBareAndLabelledEntries(unittest.TestCase):
    """AC GE-118d: after a REAL build.py deploy into a temp target OUTSIDE
    this repository, the deployed guard must accept a document whose
    related_docs holds one bare and one labelled entry, and whose
    related_code / architecture_diagrams each hold one labelled entry, when
    every named path exists."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ge118d_build_")
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

        build_result = subprocess.run(
            [PYTHON, str(_BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        if build_result.returncode != 0:
            self.fail(
                "build.py itself failed while deploying into the temp target "
                "(this is test SETUP, not the behaviour under test).\n"
                f"stdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
            )

        _init_repo(self.target)

        self.deployed_run_hook = self.target / "scripts" / "commit_guardian" / "run_hook.py"
        self.deployed_check_doc_frontmatter = (
            self.target / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
        )
        self.assertTrue(
            self.deployed_run_hook.exists(),
            msg=f"build.py did not deploy {self.deployed_run_hook}",
        )
        self.assertTrue(
            self.deployed_check_doc_frontmatter.exists(),
            msg=f"build.py did not deploy {self.deployed_check_doc_frontmatter}",
        )

    def test_ge_118d_deployed_guard_accepts_bare_and_labelled_entries_in_all_three_fields(
        self,
    ) -> None:
        # covers: GE-118d
        # angle: deployed
        """PRODUCTION LAYOUT AND ENTRY POINT. Build into a temp target OUTSIDE
        this repository, then run the deployed hook as a subprocess against a
        document whose related_docs holds one bare and one labelled entry and
        whose related_code and architecture_diagrams each hold one labelled
        entry, every named path existing. Assert exit zero, no path error for
        any of the four entries, and no ModuleNotFoundError or traceback on
        either stream.

        FAILS TODAY: validate_paths() crashes with
        `TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'`
        on the first labelled (dict) entry it encounters -- the deployed
        run_hook.py wrapper surfaces this as a non-zero exit with a traceback
        on stderr. What must be implemented to make this green: the resolver
        module scripts/frontmatter_path_resolver.py, wired into
        validate_paths(), AND present in BOTH deploy-manifest locations this
        test's temp build exercises (a source-tree run would be blind to a
        forgotten manifest entry -- see this test's own module docstring).
        """
        _write_four_entry_targets(self.target)
        doc_rel = "docs/ge118d_temp_deployed_doc.md"
        _write(
            self.target / doc_rel,
            _four_entry_doc_frontmatter(title="GE-118d deployed-guard fixture"),
        )

        result = subprocess.run(
            [
                PYTHON,
                str(self.deployed_run_hook),
                str(self.deployed_check_doc_frontmatter),
                doc_rel,
            ],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        combined = result.stdout + result.stderr

        self.assertNotIn(
            "ModuleNotFoundError",
            combined,
            msg=(
                "GE-118d: the deployed guard crashed importing a dependency -- "
                f"likely a missing deploy-manifest entry.\n{combined}"
            ),
        )
        self.assertNotIn(
            "Traceback",
            combined,
            msg=f"GE-118d: the deployed guard raised uncaught.\n{combined}",
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "GE-118d RED: expected the deployed guard to accept bare + "
                "labelled entries in all three fields.\n"
                f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
            ),
        )
        for field in ("related_docs", "related_code", "architecture_diagrams"):
            self.assertNotIn(
                f"Broken path in '{field}'",
                combined,
                msg=(
                    f"GE-118d: unexpected broken-path error for '{field}' "
                    f"even though every named path exists.\n{combined}"
                ),
            )


# ---------------------------------------------------------------------------
# Test 5 -- angle: reachability
# ---------------------------------------------------------------------------


class TestGe118dReachableFromEntryPoint(unittest.TestCase):
    """AC GE-118d reachability: the fix must be reachable through the REAL
    production entry point, not only via a direct function import."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ge118d_reachability_")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        _init_repo(self.repo)

    def test_ge_118d_reachable_from_entry_point(self) -> None:
        # covers: GE-118d
        # angle: reachability
        """REQUIRED -- invoke the production entry point (CLI, hook, slash
        command, workflow dispatch, or main()) as a subprocess/dispatch and
        assert the new behaviour actually occurs. Do NOT satisfy this by
        importing the function directly. The AC authored no test_spec entry
        point, so it is resolved here per BP-1100g-2's decision procedure:

        Step 1 bullet 2 ("Pre-commit hook") applies -- check-doc-frontmatter
        is registered in commit_guardian.json's hooks_manifest and invoked
        by pre-commit via its own runner wrapper, run_hook.py. This test
        reproduces that exact invocation
        (``python run_hook.py check_doc_frontmatter.py <files...>``),
        mirroring the established precedent in
        test_ge_118c_doc_types_deployed_resolution.py (same guard) and
        test_ge_127c_1_deployed_reachability.py (same repo, same pattern) --
        never a direct call to validate_paths() or the new resolver.

        FAILS TODAY: identical crash reason to tests 1/2/4 -- the hook raises
        an uncaught TypeError on the first labelled (dict) entry, so exit is
        non-zero and the new accept-both-shapes behaviour never occurs.
        """
        _write_four_entry_targets(self.repo)
        doc_rel = "docs/ge118d_temp_reachability_doc.md"
        _write(
            self.repo / doc_rel,
            _four_entry_doc_frontmatter(title="GE-118d reachability fixture"),
        )

        result = _run_hook_against_source(self.repo, [doc_rel])
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "GE-118d RED: the real production entry point (run_hook.py "
                "check_doc_frontmatter.py, mirroring pre-commit's own "
                "invocation) must accept bare + labelled entries end to end.\n"
                f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
            ),
        )
        self.assertNotIn("ModuleNotFoundError", combined, msg=combined)
        self.assertNotIn("Traceback", combined, msg=combined)


if __name__ == "__main__":
    unittest.main()
