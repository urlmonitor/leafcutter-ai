r"""
MODULE: unit_tests/portability/test_bo3900a_host_independent_path_classification.py
GOAL: Behavioral tests for BO-3900a — whether a path is absolute is decided
    by how it is spelled, not by the host it runs on, and the proof fails
    on a Linux runner against POSIX-only code (this repo's only CI runner
    is Linux; a Windows-only proof would prove nothing there).
BUSINESS CONTEXT: docs/known-issues/build-pipeline.md's KI-BP-20260907-0812
    already recorded the failure mode this file guards against: a fixture
    assembled from the HOST's own separator holds no backslash on a POSIX
    runner and passes regardless of what the code under test does. Every
    fixture below is a hand-typed literal, never a pathlib/os.sep round trip.
ARCHITECTURE: unit_tests/portability/_bo3900a_js_classifier.py extracts the
    REAL BO-3900 path-helper block out of build-feature.js's own source text
    and runs it via Node — never a Python reimplementation of the same
    rules. `process.platform` is forced to each of "linux" and "win32"
    INSIDE the Node subprocess to prove the result does not depend on it, by
    actually varying it, not by grepping the source for "platform".
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.portability import _bo3900a_js_classifier as jsc  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"

# The seven spellings named verbatim in BO-3900a.yaml's criteria — every one
# a hand-typed literal, never built from os.sep or pathlib.
_DRIVE_BACKSLASH = "C:\\Users\\Hendrik\\x.md"
_DRIVE_LOWER_FWD = "c:/Users/Hendrik/x.md"
_DRIVE_MIXED = "C:\\Users/Hendrik\\x.md"
_UNC = "\\\\fileserver\\share\\x.md"
_POSIX_ABS = "/home/henzeh/x.md"
_REL_BACKSLASH = "tickets\\00_inbox\\x.md"
_REL_FWD = "tickets/00_inbox/x.md"

_ABSOLUTE_SPELLINGS = (_DRIVE_BACKSLASH, _DRIVE_LOWER_FWD, _DRIVE_MIXED, _UNC, _POSIX_ABS)
_RELATIVE_SPELLINGS = (_REL_BACKSLASH, _REL_FWD)
_ALL_SEVEN = (*_ABSOLUTE_SPELLINGS, *_RELATIVE_SPELLINGS)

_ROOT = "C:/wt/epic"


class TestWindowsShapedPathsClassifyAbsoluteOnAPosixHost(unittest.TestCase):
    def test_windows_shaped_paths_classify_absolute_on_a_posix_host(self) -> None:
        # covers: BO-3900a
        # angle: criterion
        """Drive-letter, lowercase drive-letter, mixed-separator, and UNC
        spellings classify absolute, and both relative spellings classify
        relative — asserted with process.platform forced to "linux" inside
        the Node subprocess, so the result is proven independent of the
        actual host, not merely observed to be correct on this one.
        """
        results = jsc.classify_many(
            _BUILD_FEATURE_JS, list(_ALL_SEVEN), forced_platform="linux"
        )
        got = dict(zip(_ALL_SEVEN, results))
        for spelling in _ABSOLUTE_SPELLINGS:
            self.assertEqual(
                got[spelling], "absolute", f"{spelling!r} classified {got[spelling]!r}"
            )
        for spelling in _RELATIVE_SPELLINGS:
            self.assertEqual(
                got[spelling], "relative", f"{spelling!r} classified {got[spelling]!r}"
            )


class TestResolutionIdenticalUnderBothSimulatedHosts(unittest.TestCase):
    def test_resolution_result_is_identical_under_both_simulated_hosts(self) -> None:
        # covers: BO-3900a
        # angle: seam
        """Resolving all seven spellings against C:/wt/epic with
        process.platform forced to "linux" and, separately, to "win32"
        yields byte-identical strings — proven by actually toggling the
        value inside the Node subprocess, not by inspecting source text.
        """
        linux_results = jsc.resolve_many(
            _BUILD_FEATURE_JS, _ROOT, list(_ALL_SEVEN), forced_platform="linux"
        )
        windows_results = jsc.resolve_many(
            _BUILD_FEATURE_JS, _ROOT, list(_ALL_SEVEN), forced_platform="win32"
        )
        self.assertEqual(linux_results, windows_results)
        # And none of the seven is a refusal (all seven are recognised forms).
        self.assertTrue(all(r is not None for r in linux_results), linux_results)


class TestFixturesHoldLiteralDriveLettersAndBackslashesOnThisHost(unittest.TestCase):
    def test_windows_fixtures_hold_literal_drive_letters_and_backslashes_on_this_host(
        self,
    ) -> None:
        # covers: BO-3900a
        # angle: failure
        """Anti-vacuity guard (KI-BP-20260907-0812): the Windows-shaped
        fixture strings actually contain a drive letter followed by ':' and
        at least one literal backslash, on THIS running host — so a fixture
        that was accidentally assembled from the host's own separator (and
        so holds no backslash on a POSIX runner) fails loudly here instead
        of letting the other tests in this file pass vacuously.
        """
        for spelling in (_DRIVE_BACKSLASH, _DRIVE_MIXED, _REL_BACKSLASH):
            self.assertRegex(
                spelling,
                r"\\",
                f"{spelling!r} holds no literal backslash on this host",
            )
        for spelling in (_DRIVE_BACKSLASH, _DRIVE_LOWER_FWD, _DRIVE_MIXED):
            self.assertRegex(
                spelling,
                r"^[A-Za-z]:",
                f"{spelling!r} holds no literal drive letter + ':' ",
            )
        self.assertRegex(_UNC, r"^\\\\")


class TestHostIndependentClassificationReachableFromTopLevelBody(unittest.TestCase):
    def test_host_independent_classification_is_reachable_from_the_workflow_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900a
        # angle: reachability
        """The incident's Windows ticket path, driven through
        _workflow_engine_harness.py — the same harness the Linux CI runner
        uses — reaches the phase agent prompts unjoined.
        """
        from unit_tests._workflow_engine_harness import run_workflow_under_e2
        from unit_tests.workflows import _bo3900_fixtures as fx

        label_responses = fx.base_epic_label_responses(
            epic_path="EPIC-TruthfulProjectRecord",
            worktree_path=fx.WORKTREE_FWD,
            ticket_paths=[fx.TICKET_ABS_BACKSLASH],
        )
        result = run_workflow_under_e2(
            _BUILD_FEATURE_JS,
            label_responses=label_responses,
            args={"target": "EPIC-TruthfulProjectRecord"},
        )
        calls = [c for c in result.agent_calls if c.label == "ticket-planner"]
        self.assertTrue(calls, f"no ticket-planner call; stderr={result.stderr!r}")
        prompt = calls[0].prompt or ""
        drive_roots = re.findall(r"[A-Za-z]:[\\/]", prompt)
        self.assertLessEqual(len(drive_roots), 1, f"double drive root: {prompt!r}")
        self.assertIn("07_TICKET-20260909-UXP-700a-3.md", prompt)


if __name__ == "__main__":
    unittest.main()
