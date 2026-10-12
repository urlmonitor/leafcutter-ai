"""
MODULE: unit_tests/commit_guardian/test_bo_2900b_1.py
COVERS: BO-2900b-1

GOAL: Behavioral, REAL-ENTRY-POINT tests for "A registered capability that no
automation runs is reported and refuses the change" (the forward direction of
the reachability guard: registered capability -> automation invocation).

CURRENT STATE (2026-09-25, test-writer): scripts/commit_guardian/
check_reachability.py (no `--mode precommit`/`--mode ci` CLI at all) and
registered_capabilities()/collected_invocations() on
_reachability_inventory.py do not exist yet in this worktree (confirmed
directly via `ls` right after a fresh `python scripts/build.py --target-dir
.`, and via grep for either new name -- zero hits), and neither
commit_guardian.json's hooks_manifest nor .github/workflows/ci.yml names
`check_reachability` anywhere. These tests are RED for that reason -- there
is no reachability guard to run yet, not because a fixture is malformed.

ENTRY POINT / DECLARED CLI CONTRACT: see _bo_2900b_1_fixtures.py's module
docstring for the full --surface/--automation override contract this file
hands to python-coder. Tests 1-4 call check_reachability.main([...]) as a
direct Python call (matching this AC's own test_spec verbatim); test 5 is
the REQUIRED reachability test and invokes the SAME CLI as a genuine
subprocess (never importing the function directly), per the Reachability
Entry-Point Resolution procedure's step 1 (CLI script) -- mirroring exactly
how check_done_proof.py's own CLI is invoked from
.github/workflows/ci.yml:228 and registered in commit_guardian.json's
hooks_manifest.

FIXTURES: every scenario targets a FIXTURE command surface (a real, on-disk,
importable .py file -- never a hand-typed in-memory literal) rather than the
real, evolving scripts/build_orchestration/fast_lane.py, so the verdict is
deterministic. Per this AC's own notes, the decisive test is
test_inventory_comes_from_the_built_parser_not_the_source_text: it can only
pass on an implementation that genuinely builds the parser (a
source-scanning implementation gets the ghost capability and the
loop-registered capability wrong in opposite directions).

CROSS-LAYER SEAM (test-writer skill Rule 3): the unit under test sits at a
script -> hook boundary (a command-surface script's own built argparse
parser, feeding a commit-guardian hook's inventory reader). Test 3 pipes a
REAL, unmocked fixture surface module's REAL built argparse parser
(`build_parser()`, the same mechanism fast_lane.py's own
`_build_cli_parser()` uses) into the REAL consumer
(check_reachability.py's registered_capabilities()/main(), invoked for real
-- no mocking on either side) and asserts on the consumer's observable
output. Test 5 additionally exercises this same seam end-to-end through a
real subprocess dispatch of the deployed CLI.

FILE SPLIT (2026-09-25, test-writer, re-dispatched from python-coder's
handoff): this file originally also carried three REWORK tests (the
exemption-registry seam tests and the CI-job continue-on-error test), which
pushed it past check-file-size's 400-line .py limit. Those three now live in
the sibling file test_bo_2900b_1_exemptions.py -- same COVERS id, same
shared fixture module (_bo_2900b_1_fixtures.py), split purely to satisfy the
line-count gate. This file keeps the original five tests (the forward
Gherkin scenario, the called-capabilities-are-silent counterpart, the
built-parser-not-source-text seam test, the no-bypass-flag-named test, and
the required subprocess reachability test) unchanged.
"""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900b_1_fixtures import (  # noqa: E402
    fixture_tmp_dir,
    run_check_reachability,
    write_fixture_automation_calls_claim_only,
    write_fixture_automation_calls_three,
    write_fixture_surface_basic,
    write_fixture_surface_conditional,
)

# ---------------------------------------------------------------------------
# Module import (will fail with ModuleNotFoundError until python-coder
# implements BO-2900b-1 -- this IS the expected RED state).
# ---------------------------------------------------------------------------

try:
    import scripts.commit_guardian.check_reachability as check_reachability  # type: ignore[import]
    _IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    check_reachability = None  # type: ignore[assignment]
    _IMPORT_OK = False


def _call_main(argv: list[str]) -> tuple[int, str, str]:
    """Call check_reachability.main(argv) directly, capturing stdout/stderr.

    Args:
        argv: Argument list, exactly as a real CLI invocation would receive.

    Returns:
        (return_code, stdout_text, stderr_text).
    """
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = check_reachability.main(argv)
    return rc, out.getvalue(), err.getvalue()


class TestUncalledRegisteredCapabilityIsReportedAndRefused(unittest.TestCase):
    """The forward Gherkin scenario, literally: report is registered, no
    automation invokes it, claim/release/mark-done are -- report alone must
    be named and the run must refuse (non-zero exit)."""

    def test_uncalled_registered_capability_is_reported_and_the_check_exits_nonzero(
        self,
    ) -> None:
        # covers: BO-2900b-1
        # angle: failure
        """A fixture surface registering claim/release/mark-done/report, with
        automation invoking only the first three, must be reported (naming
        `report` and the surface it is registered on) and the run must exit
        non-zero -- refused, never a passing advisory note."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. Implement "
                "scripts/commit_guardian/check_reachability.py (templates/"
                "scripts/commit_guardian/check_reachability.py is the "
                "canonical source; build.py deploys it) with a main(argv) "
                "entry point per BO-2900b-1."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_basic(src_dir)
            automation_path = write_fixture_automation_calls_three(automation_dir)

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        self.assertNotEqual(
            rc,
            0,
            msg=(
                "an uncalled registered capability ('report') must REFUSE "
                f"the change (non-zero exit). Got rc={rc}\ncombined "
                f"output:\n{combined}"
            ),
        )
        self.assertIn(
            "report",
            combined,
            msg=(
                "the refusal must name the uncalled capability ('report'):"
                f"\n{combined}"
            ),
        )
        self.assertTrue(
            "fixture_surface_basic" in combined or str(surface_path) in combined,
            msg=(
                "the refusal must name the surface the capability is "
                f"registered on:\n{combined}"
            ),
        )


class TestCalledCapabilitiesAreNotReportedInTheSameRun(unittest.TestCase):
    """claim, release, and mark-done -- all actually invoked -- must never
    appear as findings in the same run that reports report."""

    def test_called_capabilities_are_not_reported_in_the_same_run(self) -> None:
        # covers: BO-2900b-1
        # angle: criterion
        """Same fixture as the uncalled-capability scenario: claim, release
        and mark-done appear nowhere in the run's output, so a
        report-everything implementation fails alongside the positive
        assertion above."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. Implement "
                "scripts/commit_guardian/check_reachability.py first."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_basic(src_dir)
            automation_path = write_fixture_automation_calls_three(automation_dir)

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        for called_capability in ("claim", "release", "mark-done"):
            self.assertNotIn(
                called_capability,
                combined,
                msg=(
                    f"'{called_capability}' IS invoked by the fixture "
                    "automation and must never be reported as an uncalled "
                    f"capability finding:\n{combined}"
                ),
            )


class TestInventoryComesFromTheBuiltParserNotTheSourceText(unittest.TestCase):
    """A capability mentioned in source but never registered (a false
    condition at build time) must be invisible; a capability registered only
    through a loop over a table must still be found."""

    def test_inventory_comes_from_the_built_parser_not_the_source_text(self) -> None:
        # covers: BO-2900b-1
        # angle: real_artifact
        """A fixture surface whose source contains `sub.add_parser("ghost")`
        inside a branch that is False at build time, and which registers a
        capability through a loop over a table, is inventoried by running
        the real check: `ghost` must be absent from the findings, and the
        loop-registered `table-driven` capability (invoked by no automation
        here) must be present. This is the decisive test: a source-text
        regex scan gets both wrong in opposite directions -- it would find
        `ghost` (present as text, never registered) and miss `table-driven`
        (registered, but never appearing as a literal `add_parser(...)`
        call)."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. Implement "
                "scripts/commit_guardian/check_reachability.py first, and "
                "ensure registered_capabilities() reads the BUILT argparse "
                "parser's _SubParsersAction choices -- never a source-text "
                "regex scan of `add_parser(`."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_conditional(src_dir)
            automation_path = write_fixture_automation_calls_claim_only(automation_dir)

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        self.assertNotIn(
            "ghost",
            combined,
            msg=(
                "'ghost' is only source TEXT behind a branch that is False "
                "at build time -- it must never be registered, and must "
                f"never appear in the findings:\n{combined}"
            ),
        )
        self.assertIn(
            "table-driven",
            combined,
            msg=(
                "'table-driven' is registered through a loop over a table "
                "(never a literal add_parser(...) call) and is never "
                "invoked by the fixture automation -- a source-scanning "
                "implementation would miss it entirely; it must be "
                f"reported:\n{combined}"
            ),
        )
        self.assertNotEqual(
            rc,
            0,
            msg=(
                "an uncalled registered capability ('table-driven') must "
                f"refuse the change. Got rc={rc}\ncombined output:\n{combined}"
            ),
        )


class TestFailureOutputDoesNotNameASkipOrBypassFlag(unittest.TestCase):
    """The blocking gate must never document its own off switch."""

    def test_failure_output_does_not_name_a_skip_or_bypass_flag(self) -> None:
        # covers: BO-2900b-1
        # angle: failure
        """The text emitted on a refusing run must contain neither 'SKIP='
        nor '--no-verify' -- per BO-2900e-1's final clause / BO-2900b-1-i,
        the gate never advertises how to bypass itself."""
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import "
                "scripts.commit_guardian.check_reachability. Implement "
                "scripts/commit_guardian/check_reachability.py first."
            )
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_basic(src_dir)
            automation_path = write_fixture_automation_calls_three(automation_dir)

            rc, out, err = _call_main(
                [
                    "--mode",
                    "precommit",
                    "--surface",
                    f"{surface_path}:build_parser",
                    "--automation",
                    str(automation_path),
                ]
            )
            combined = out + err

        self.assertNotEqual(
            rc,
            0,
            msg=f"expected a refusing run to assert against. Got rc={rc}\n{combined}",
        )
        self.assertNotIn(
            "SKIP=",
            combined,
            msg=f"the refusal must never name its own skip mechanism:\n{combined}",
        )
        self.assertNotIn(
            "--no-verify",
            combined,
            msg=f"the refusal must never name its own bypass flag:\n{combined}",
        )


class TestReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability test: the real deployed CLI, invoked as a
    genuine subprocess (never main() imported and called directly), must
    exhibit the same refusal behaviour end to end."""

    def test_bo_2900b_1_reachable_from_entry_point(self) -> None:
        # covers: BO-2900b-1
        # angle: reachability
        """Invokes the REAL deployed scripts/commit_guardian/check_reachability.py
        CLI via subprocess (mirroring exactly how check_done_proof.py's CLI is
        registered in commit_guardian.json's hooks_manifest and invoked from
        .github/workflows/ci.yml:228) over the same uncalled-capability
        fixture as the first test, and asserts the refusal actually occurs
        through the real entry point -- not merely that main() behaves
        correctly when imported and called directly."""
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            surface_path = write_fixture_surface_basic(src_dir)
            automation_path = write_fixture_automation_calls_three(automation_dir)

            result = run_check_reachability(
                mode="precommit",
                surfaces=[f"{surface_path}:build_parser"],
                automation_scripts=[str(automation_path)],
            )
            combined = result.stdout + result.stderr

        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                "the real deployed CLI, invoked as a genuine subprocess, "
                "must refuse (non-zero exit) when a registered capability "
                f"('report') is never invoked. Got "
                f"returncode={result.returncode}\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )
        self.assertIn(
            "report",
            combined,
            msg=(
                "the subprocess-invoked CLI's refusal must name the "
                f"uncalled capability ('report'):\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
