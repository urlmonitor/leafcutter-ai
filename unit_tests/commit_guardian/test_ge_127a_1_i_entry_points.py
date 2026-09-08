"""
MODULE: unit_tests/commit_guardian/test_ge_127a_1_i_entry_points.py
COVERS: GE-127a-1-i -- "A file whose length cannot be established is refused
    and named, never reported as within its permitted length"

SPLIT NOTICE: this file is one of three split from the original, oversized
    test_ge_127a_1_i.py (467 effective lines, over the ``check-file-size``
    gate's 400-line limit) per BrainCandy's explicit decision that test
    files stay in the gate's scope rather than being exempted. The original
    module docstring -- the full defect narrative, exercise strategy, and
    verdict vocabulary -- is preserved in full in the sibling file
    test_ge_127a_1_i_named_situations.py in this same directory. Shared
    fixtures live in ``_ge_127a_1_i_fixtures.py``. The three split files are:

        - test_ge_127a_1_i_named_situations.py (undecodable vs. unopenable)
        - test_ge_127a_1_i_verdict_floor.py (never-zero, distinguishable,
          paired-readable, deletion-out-of-scope)
        - test_ge_127a_1_i_entry_points.py (THIS FILE)

THIS FILE'S SEAM: the two descriptors that prove the INDETERMINATE verdict
    is not just correct in isolation but actually REACHES a real production
    entry point -- the registered ``run_hook.py`` wrapper every pre-commit
    entry delegates through, and the DEPLOYED copy of the script running in
    a cold process after a real ``build.py``. These two do not use the
    shared ``UnmeasurableFixtureTestCase`` scaffolding (each needs its own,
    differently-shaped setUp), so they are grouped together as the
    "verdict reaches a real caller" pair rather than split across the other
    two files' behavioural groupings.

VERDICT VOCABULARY, PINNED BY THE AC AND REUSED HERE UNCHANGED: an
    "INDETERMINATE: reason=<text>" line naming which of the two situations
    occurred ("not readable as text in the encoding the standard reads" vs.
    "cannot be opened at all"), with exit 2, alongside exit 0 for a clean
    run and exit 1 for a length that WAS measured and found over (the
    crossing case GE-127a-1 covers, or the ratchet case GE-127b-1 covers).

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127a-1-i.yaml
    and its parent GE-127a-1.yaml.

DECISION HISTORY
- 2026-09-07 [GE-127a-1-i/test-writer]: Initial authoring of all eight RED
    test stubs per GE-127a-1-i's test_spec. Verified RED via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127a_1_i.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failures.
- 2026-09-07 [GE-127a-1-i/test-writer]: Split out of test_ge_127a_1_i.py to
    satisfy the ``check-file-size`` gate. No test content changed; two of
    the original eight descriptors moved here verbatim.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127a_1_i_fixtures import (  # noqa: E402
    _BUILD_TIMEOUT_SECONDS,
    _INDETERMINATE_EXIT,
    _PYTHON,
    _SUBPROCESS_TIMEOUT_SECONDS,
    _UNDECODABLE_BYTES,
    _BUILD_PY,
    _commit_all,
    _content,
    _extract_indeterminate_reason,
    _init_repo,
    _run_check_via_hook,
    _stage_all,
)

# ---------------------------------------------------------------------------
# 7. Reachability -- the INDETERMINATE verdict reaches the hook wrapper
# ---------------------------------------------------------------------------


class TestIndeterminateVerdictReachesRegisteredHookOutput(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_repo(self.root)
        (self.root / "existing.py").write_text(_content(20), encoding="utf-8")
        _commit_all(self.root, "establish baseline covered file")

    def test_ge_127a_1_i_the_indeterminate_verdict_reaches_the_registered_hook_output_and_exit_status(self):
        # covers: GE-127a-1-i
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate through the registered
        run_hook.py wrapper (the real worktree-aware Python resolver every
        pre-commit entry delegates through) with an unmeasurable file
        staged, and assert the INDETERMINATE line and its named reason
        appear in the wrapper's own output stream and that the exit status
        is the commit outcome.

        RED TODAY: since check_file_size.py itself emits no INDETERMINATE
        verdict for this input (see the named-situations descriptors in the
        sibling test file), delegating through run_hook.py cannot produce
        one either -- confirmed by construction.
        """
        bad = self.root / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(self.root)

        result = _run_check_via_hook(self.root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            result.returncode,
            msg=(
                "The registered hook wrapper must surface the INDETERMINATE "
                f"exit code (2). stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(reason, msg=f"Expected an INDETERMINATE reason. Got: {combined!r}")


# ---------------------------------------------------------------------------
# 8. Deployed -- fails closed on an unmeasurable file in a cold process
# ---------------------------------------------------------------------------


class TestDeployedCopyFailsClosedOnUnmeasurableFile(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def test_ge_127a_1_i_the_deployed_copy_fails_closed_on_an_unmeasurable_file_in_a_cold_process(self):
        # covers: GE-127a-1-i
        # angle: deployed
        """After build.py, the DEPLOYED copy and every module it imports
        must load and run in a cold process. With an unmeasurable covered
        file staged, the deployed run must emit the INDETERMINATE verdict
        with its named reason and exit non-zero. Source-tree greenness
        cannot substitute: the hook runs from the deployed layout.

        RED TODAY: no such verdict exists in the source tree, so it cannot
        exist in the deployed copy either -- confirmed by construction.
        """
        build_result = subprocess.run(
            [_PYTHON, str(_BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        _init_repo(self.target)
        (self.target / "existing.py").write_text(_content(20), encoding="utf-8")
        _commit_all(self.target, "establish baseline covered file")

        bad = self.target / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(self.target)

        result = subprocess.run(
            [_PYTHON, str(deployed_check)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        combined = result.stdout + result.stderr
        self.assertNotIn("ModuleNotFoundError", combined, msg=f"Deployed copy crashed importing a dependency. Got: {combined!r}")
        self.assertEqual(
            _INDETERMINATE_EXIT,
            result.returncode,
            msg=(
                "Deployed copy with an unmeasurable file must exit "
                f"INDETERMINATE (2). stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(reason, msg=f"Expected an INDETERMINATE reason. Got: {combined!r}")


if __name__ == "__main__":
    unittest.main()
