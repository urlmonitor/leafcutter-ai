"""
MODULE: unit_tests/ac_store/test_bo_2500a_7.py
GOAL: RED test stubs for BO-2500a-7 -- "A proof run that did not finish is
reported as unfinished, never as a list of tests that failed."

=== Diagnosed defect ===

``_run_pytest_and_parse`` (scripts/ac_store/done_proof.py, ~line 1231) runs the
linked-test pytest subprocess and returns whatever ``_parse_pytest_verbose_output``
extracts from ``proc.stdout`` -- with NO check that the subprocess actually ran to
completion. It never inspects ``proc.returncode``, and never compares the number of
result lines it parsed against the number of linked tests it was asked to run.

Downstream, both eligibility composers (``verify_done_eligible``'s leaf path and
``_verify_composite_eligible``) feed that dict straight into ``_classify_outcomes``,
which treats ANY linked test whose nodeid is absent from the dict as non-passing
(``_describe_non_passing`` labels it "not run"). So a run that was killed by the
machine (OOM, scheduler contention, anything short of pytest's own
``subprocess.TimeoutExpired``) produces exactly the same shape of output as a run
that completed and genuinely found those tests failing -- an operator (or an
automated done-proof gate) cannot tell the two apart. The existing
``_PYTEST_TIMEOUT_SENTINEL`` only covers the ``TimeoutExpired`` exception path; a
subprocess that is killed outright returns a normal (non-exception) ``CompletedProcess``
with partial stdout and a nonzero/negative returncode, and that path is entirely
unguarded today.

=== Fixture note -- what is simulated and what is real (read before editing) ===

Test 1 (the positive case) patches ``done_proof.subprocess.run`` at the narrowest
possible seam -- the subprocess boundary itself -- to return a ``CompletedProcess``
whose ``stdout`` contains a result line for only ONE of the two real, on-disk,
covers-tagged test functions actually present in ``test_root``, and whose
``returncode`` is negative (``-9``), the POSIX convention for "killed by SIGKILL"
(the real-world manifestation of "the machine was simply busy and the subprocess
was killed", per the ticket's KI-TQ-20260914-1050 citation). This is a SIMULATION
of a genuinely early-ending subprocess: it is not itself a real killed pytest
process, because reliably producing a real kill with partial stdout inside a
deterministic sub-5-second unit test is not practical. What IS real: the AC store
record, the two on-disk test files with genuine covers tags, and the fact that
``_run_pytest_and_parse``/``verify_done_eligible`` receive exactly the kind of
(stdout, returncode) pair a genuinely-killed subprocess produces -- a completed
(non-exception) process object whose stdout stops mid-way through the expected
result lines. The parsing and classification logic downstream of that boundary is
exercised for real; only the OS-level act of killing a process is stood in for.

Test 2 (the control) uses NO mocking at all: two real, on-disk test files -- one
whose body genuinely passes and one whose body genuinely fails -- are run through
the REAL ``_run_pytest_and_parse``/``verify_done_eligible`` call chain, with a real
pytest subprocess allowed to run to completion. This proves the fix required by
Test 1 cannot be satisfied by unconditionally reporting "did not finish": a run
that DOES finish, with a real failure in it, must still name that failure.

=== Fixture authenticity mandate (BO-2500a dogfood, carried forward) ===

AC YAML fixtures are written with ``yaml.safe_dump`` (never hand-typed YAML
strings). Test-file fixtures are real ``.py`` files with genuine test bodies
written to disk via ``Path.write_text``.

=== Verification-run note ===

Run with ``AC_ENFORCE_STRICT=1``. BO-2500a-7 is ``work_status: todo``, so without
the override the ``pytest_ac_enforcement`` plugin (loaded process-wide by this
repo's own ``pytest.ini``) downgrades a genuinely FAILING assertion in these very
tests to XFAIL, which would exit 0 and hide the red baseline this file exists to
capture.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# This import already succeeds today (verify_done_eligible pre-dates this AC) --
# the RED signal for this file comes from the ASSERTIONS below, not from an
# ImportError, since the defect is a missing behaviour inside an existing
# function rather than an absent symbol.
from done_proof import verify_done_eligible  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers (mirrors unit_tests/ac_store/test_bo2500a_done_proof.py)
# ---------------------------------------------------------------------------


def _write_ac(ac_root: Path, ac_id: str) -> Path:
    """Write a minimal active AC record using yaml.safe_dump (never hand-typed)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict[str, object] = {
        "id": ac_id,
        "title": f"Synthetic AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _fake_killed_process(stdout: str) -> Mock:
    """A CompletedProcess-shaped stand-in for a subprocess killed mid-run.

    Real machine-kill / OOM-kill terminations do NOT raise
    ``subprocess.TimeoutExpired`` -- ``subprocess.run`` returns normally with a
    negative returncode (the POSIX "terminated by signal N" convention;
    ``-9`` == SIGKILL) and whatever partial stdout the child had already
    flushed. That is exactly what this Mock reproduces.
    """
    proc = Mock()
    proc.stdout = stdout
    proc.stderr = ""
    proc.returncode = -9
    return proc


# ---------------------------------------------------------------------------
# BO-2500a-7-a -- a truncated run must not be reported as named failing tests
# ---------------------------------------------------------------------------


class TestTruncatedRunReportedAsUnfinished(unittest.TestCase):
    """A run that ends before every linked test reports must say so -- not
    name the never-reported test as non-passing."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-TEST-UNIT-TRUNC1"
        _write_ac(self.ac_root, self.ac_id)
        # Two REAL, on-disk, covers-tagged test functions in one file. Both
        # would genuinely pass if pytest ran them to completion -- the point
        # of this fixture is that the SECOND one's result line is never
        # produced because the run ends early, not that it would have failed.
        self.test_file = _write_test_file(
            self.test_root,
            "test_linked_pair.py",
            f"""\
            def test_alpha():
                # covers: {self.ac_id}
                pass  # would genuinely pass

            def test_beta():
                # covers: {self.ac_id}
                pass  # would genuinely pass -- but its result line is NEVER emitted
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bo_2500a_7_a_truncated_run_is_reported_as_unfinished_not_as_failing_tests(
        self,
    ) -> None:
        # covers: BO-2500a-7
        # angle: failure
        """A run truncated before reporting every linked test must say the run
        did not finish, and must NOT name the unreported test as non-passing.

        Only ``test_alpha``'s PASSED line is present in the simulated stdout --
        ``test_beta`` never printed a result line at all, exactly as it would
        not if the subprocess were killed between the two. Today's code has no
        concept of "the run did not finish": it silently treats test_beta's
        absence from the parsed dict as equivalent to test_beta having failed
        (``_classify_outcomes`` -> ``_describe_non_passing`` -> "linked test not
        run: <path>::test_beta"), which is indistinguishable from a real
        failure. This assertion is expected to be RED against current code.
        """
        alpha_nodeid = f"{self.test_file}::test_alpha PASSED"
        truncated_stdout = alpha_nodeid + "\n"  # test_beta's line never arrives

        with patch(
            "done_proof.subprocess.run",
            return_value=_fake_killed_process(truncated_stdout),
        ):
            verdict = verify_done_eligible(
                self.ac_id, ac_root=self.ac_root, test_root=self.test_root
            )

        self.assertFalse(
            verdict["eligible"],
            "A truncated run must never be reported as eligible for done.",
        )

        reason = verdict.get("reason", "")

        # --- The positive half of the AC: the verdict must SAY it did not finish.
        self.assertTrue(
            any(
                phrase in reason.lower()
                for phrase in (
                    "did not finish",
                    "did not complete",
                    "run did not",
                    "truncated",
                    "unfinished",
                )
            ),
            "The reason must say the run did not finish -- an operator reading "
            "it must be able to tell this apart from a completed run that found "
            f"real failures, without inspecting code. Got reason={reason!r}.",
        )

        # --- The negative half of the AC: must NOT name test_beta as non-passing
        # on the strength of a result it never received.
        bare_not_run_phrase = f"linked test not run: {self.test_file}::test_beta"
        self.assertNotIn(
            bare_not_run_phrase,
            reason,
            "The reason must not name the never-reported test as a specific "
            f"non-passing outcome. Got reason={reason!r}.",
        )
        failing_tests = verdict.get("failing_tests", [])
        self.assertFalse(
            any("test_beta" in nid for nid in failing_tests),
            "test_beta must not be named in failing_tests -- its result was "
            f"never received, so it cannot be reported as non-passing. Got "
            f"failing_tests={failing_tests!r}.",
        )


# ---------------------------------------------------------------------------
# BO-2500a-7-a control -- a completed run with real failures must still name them
# ---------------------------------------------------------------------------


class TestCompletedRunWithRealFailuresStillNamesThem(unittest.TestCase):
    """The control: a run that finishes, with a genuine failure in it, must
    still name that failure -- proves the fix cannot just suppress reporting."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-TEST-UNIT-CTRL1"
        _write_ac(self.ac_root, self.ac_id)
        # Two REAL test functions: one genuinely passes, one genuinely fails.
        # No mocking anywhere in this test -- a real pytest subprocess runs
        # both to completion.
        self.test_file = _write_test_file(
            self.test_root,
            "test_completed_run_with_failure.py",
            f"""\
            def test_gamma_passes():
                # covers: {self.ac_id}
                pass  # genuinely passes

            def test_delta_fails():
                # covers: {self.ac_id}
                assert False, "intentional failure -- this test genuinely fails"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bo_2500a_7_a_completed_run_with_real_failures_still_names_them(
        self,
    ) -> None:
        # covers: BO-2500a-7
        # angle: criterion
        """A completed run with a real failure must still name it in the reason
        and in failing_tests -- this must remain true after the fix above.

        Without this control, a "fix" that returns 'run did not finish'
        unconditionally (or whenever anything is even slightly ambiguous)
        would satisfy the first test while breaking the actual purpose of the
        gate: catching real failures. No mocking of subprocess.run here -- a
        real pytest subprocess is allowed to run test_gamma_passes and
        test_delta_fails to completion.
        """
        verdict = verify_done_eligible(
            self.ac_id, ac_root=self.ac_root, test_root=self.test_root
        )

        self.assertFalse(
            verdict["eligible"],
            "An AC with a genuinely failing covers test must not be eligible.",
        )

        reason = verdict.get("reason", "")
        self.assertIn(
            "test_delta_fails",
            reason,
            "The completed run's genuine failure must be named in the reason -- "
            f"got reason={reason!r}.",
        )
        # Must NOT be reported as an unfinished/truncated run -- it completed.
        self.assertFalse(
            any(
                phrase in reason.lower()
                for phrase in (
                    "did not finish",
                    "did not complete",
                    "run did not",
                    "truncated",
                    "unfinished",
                )
            ),
            "A completed run must not be described as unfinished/truncated -- "
            f"got reason={reason!r}.",
        )

        failing_tests = verdict.get("failing_tests", [])
        self.assertTrue(
            any("test_delta_fails" in nid for nid in failing_tests),
            f"test_delta_fails must be named in failing_tests. Got "
            f"failing_tests={failing_tests!r}.",
        )
        passing_tests = verdict.get("passing_tests", [])
        self.assertTrue(
            any("test_gamma_passes" in nid for nid in passing_tests),
            "The genuinely passing test must still be reported as passing -- "
            f"proves both tests actually ran to completion. Got "
            f"passing_tests={passing_tests!r}.",
        )


if __name__ == "__main__":
    unittest.main()
