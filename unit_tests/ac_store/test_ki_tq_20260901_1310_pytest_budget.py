"""
MODULE: unit_tests/ac_store/test_ki_tq_20260901_1310_pytest_budget.py
GOAL: Failing test stubs for KI-TQ-20260901-1310 (docs/known-issues/testing-quality.md) --
    the red-baseline / done-proof gate's ``_run_pytest_and_parse`` hardcodes
    ``timeout=60`` for the whole pytest subprocess call.  Pytest COLLECTION alone in
    this repository measures ~30-33s before any test body runs, so the real budget is
    under 30s -- not enough to fit even one ``build.py`` subprocess call (~9.5s), let
    alone the ~142s a real subprocess-level AC (BP-900g-8-ii, PR #694) legitimately
    needs across 5 tests.  The gate is fail-closed on timeout (a bare ``{}`` cannot
    fake a pass) -- that part is correct and this file does not relax it. The actual
    defect is upstream of fail-closed: the budget is so tight that the CHEAPEST way to
    pass the gate is to delete the subprocess-level proof an AC's own criteria require,
    and the operator-facing refusal ("linked test not run") reads exactly like the
    tests are missing rather than like the gate ran out of time.

=== What this file pins (KI's own fix direction, two parts) ===

1. Collection must not be charged against the budget: the computed timeout must be
   generous enough to fit a real subprocess-heavy test file, and must grow with the
   number of files under verification rather than handing back one fixed number that
   quietly erodes as an AC's test file grows.
2. A timeout must become a DISTINGUISHABLE, recorded outcome -- ``verify_done_eligible``'s
   ``reason`` string must name the budget and the command, not merely say a linked test
   "not run" (today's wording, indistinguishable from "the test file does not exist").

=== Pinned interface additions (NOT yet implemented; every import/attr below is
    expected to raise until python-coder lands the fix) ===

    scripts/ac_store/done_proof.py:
        _run_pytest_and_parse(test_files: list[Path]) -> dict[str, str]
            -- already exists, but must (a) no longer pass a bare ``timeout=60`` to
               ``subprocess.run`` and (b) honour the env var named below.

    Env var: ``LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS`` -- optional override.
        When set to a value ``float()`` can parse and that is > 0, it is used verbatim
        as the ``timeout=`` kwarg.  When absent, empty, or not parseable as a positive
        float, the computed default budget is used instead (never a crash, never 0).

=== Fixture note ===

No real pytest subprocess is ever spawned by this file -- ``subprocess.run`` is mocked
at ``done_proof.subprocess.run`` throughout, so every test here completes in well under
a second despite reasoning about multi-hundred-second budgets. Where a written test
file is needed to exercise the covers-tag scan + eligibility path (tests 3-4), it is
a real, on-disk ``.py`` file under ``tmp_path`` -- never a hand-typed in-memory literal
standing in for one -- per the Fixture Authenticity Rule (test-writer.md 2h.2).

=== Verification-run note ===

Run with ``AC_ENFORCE_STRICT=1`` if this file is ever collected inside the repo's own
pytest.ini rootdir alongside ``pytest_ac_enforcement`` -- it is not itself covering a
not-done AC (no AC id exists for this KI; every tag below is ``UNKNOWN``), but the
outer verification run for this whole drive uses the strict flag project-wide.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from done_proof import _run_pytest_and_parse, verify_done_eligible  # noqa: E402

# The KI's own measured numbers (docs/known-issues/testing-quality.md,
# KI-TQ-20260901-1310): collection alone costs ~30-33s repo-wide; PR #694's real
# subprocess-heavy AC needed ~142s of actual test execution in ONE file. A budget
# that cannot clear base-collection + that real cost cannot fit the coverage the
# AC's own criteria require.
_MEASURED_COLLECTION_FLOOR_SECONDS = 30
_MEASURED_REAL_SUBPROCESS_AC_SECONDS = 142
_MINIMUM_VIABLE_SINGLE_FILE_BUDGET = (
    _MEASURED_COLLECTION_FLOOR_SECONDS + _MEASURED_REAL_SUBPROCESS_AC_SECONDS
)  # 172 -- today's hardcoded 60 is not even a quarter of this.

_ENV_OVERRIDE_VAR = "LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS"


# ---------------------------------------------------------------------------
# Fixture helpers -- real on-disk AC YAML (yaml.safe_dump) + real test files.
# ---------------------------------------------------------------------------


def _write_ac(ac_root: Path, ac_id: str) -> Path:
    """Write a minimal active AC record with ``yaml.safe_dump`` (never hand-typed)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict[str, object] = {
        "id": ac_id,
        "title": f"Synthetic AC {ac_id}",
        "component": "ac-store",
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


def _fake_completed_process(stdout: str = "") -> Mock:
    proc = Mock()
    proc.stdout = stdout
    proc.stderr = ""
    proc.returncode = 0
    return proc


class _ClearEnvOverride:
    """Context manager guaranteeing the override var is absent, restored after."""

    def __enter__(self) -> "_ClearEnvOverride":
        import os

        self._had = _ENV_OVERRIDE_VAR in os.environ
        self._old = os.environ.pop(_ENV_OVERRIDE_VAR, None)
        return self

    def __exit__(self, *exc) -> None:
        import os

        if self._had:
            os.environ[_ENV_OVERRIDE_VAR] = self._old  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Bullet 1 -- the budget accommodates a subprocess-level test file.
# ---------------------------------------------------------------------------


class TestBudgetAccommodatesSubprocessLevelProof(unittest.TestCase):
    """The computed timeout must clear collection + a real subprocess-heavy AC."""

    def test_default_budget_is_generous_enough_for_a_real_subprocess_heavy_ac(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        """Today's hardcoded 60s cannot clear 30s collection + 142s real test time.

        Asserts on the COMPUTED budget (the ``timeout=`` kwarg actually handed to
        ``subprocess.run``) rather than actually sleeping 142s -- a test that burns
        two real minutes to prove a timeout is a bad trade. ``subprocess.run`` is
        mocked so the assertion is on the number chosen, not on a real pytest run.
        """
        with _ClearEnvOverride():
            with patch(
                "done_proof.subprocess.run", return_value=_fake_completed_process()
            ) as mock_run:
                _run_pytest_and_parse([Path("fake_subprocess_heavy_test.py")])

        self.assertTrue(mock_run.called, "subprocess.run must actually be invoked.")
        _, kwargs = mock_run.call_args
        self.assertIn(
            "timeout",
            kwargs,
            "subprocess.run must be called with an explicit timeout= kwarg.",
        )
        self.assertGreaterEqual(
            kwargs["timeout"],
            _MINIMUM_VIABLE_SINGLE_FILE_BUDGET,
            "The computed budget for a single test file must clear the measured "
            f"collection floor ({_MEASURED_COLLECTION_FLOOR_SECONDS}s) plus a real "
            f"subprocess-heavy AC's test time ({_MEASURED_REAL_SUBPROCESS_AC_SECONDS}s) "
            f"-- got timeout={kwargs['timeout']!r}, hardcoded 60s clears neither.",
        )


# ---------------------------------------------------------------------------
# Bullet 2 -- collection overhead is a base allowance, not deducted per-test.
# ---------------------------------------------------------------------------


class TestCollectionOverheadHasADedicatedBaseAllowance(unittest.TestCase):
    """More test files must not shrink the effective per-file execution budget."""

    def _captured_timeout(self, file_count: int) -> float:
        files = [Path(f"fake_test_{i}.py") for i in range(file_count)]
        with _ClearEnvOverride():
            with patch(
                "done_proof.subprocess.run", return_value=_fake_completed_process()
            ) as mock_run:
                _run_pytest_and_parse(files)
        _, kwargs = mock_run.call_args
        return kwargs["timeout"]

    def test_budget_grows_with_file_count_instead_of_a_single_fixed_ceiling(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        """A base collection allowance plus a per-file component must both exist.

        If the whole 60s (or any replacement) were one fixed number applied
        regardless of how many linked test files exist, a 10-file AC would get the
        exact same wall-clock allowance as a 1-file AC -- which is precisely the
        "budget scales with the repo, not the AC" defect the KI names, just moved
        from collection time to execution time.  This asserts the total genuinely
        grows, proving a per-file (or per-test) component exists on top of any flat
        base.
        """
        one_file_budget = self._captured_timeout(1)
        ten_file_budget = self._captured_timeout(10)

        self.assertGreater(
            ten_file_budget,
            one_file_budget,
            "Ten linked test files must receive a larger budget than one -- "
            f"got one_file={one_file_budget!r}, ten_file={ten_file_budget!r}. "
            "A flat constant applied to every input reintroduces the same "
            "repo-scale-not-AC-scale defect the KI describes.",
        )


# ---------------------------------------------------------------------------
# Bullet 3 -- negative control: a genuine timeout still fails closed.
# ---------------------------------------------------------------------------


class TestTimeoutStillFailsClosed(unittest.TestCase):
    """A timeout must never be mistakeable for a pass, however it is reported.

    NOTE ON THIS TEST'S RED/GREEN STATUS (KI-TQ-010 negative-control doctrine,
    the same knowledge base this fix lives in): the fail-closed half of this
    assertion is ALREADY true against today's code -- ``_run_pytest_and_parse``
    already returns ``{}`` on timeout and that already makes ``eligible`` False.
    A negative control that is correct-by-construction has no natural red
    phase; per KI-TQ-010's own prescribed remedy this test instead demonstrates
    its discriminating power directly, in the same body, by first proving the
    positive case IS load-bearing (a linked test genuinely reported PASSED DOES
    flip ``eligible`` True) before proving the timeout case is NOT (otherwise the
    "eligible is False" assertion below would be checking a return value the
    production code could never make True in the first place, which would make
    it vacuous rather than a real constraint).
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.ac_root = self.tmp_root / "ac-store"
        self.test_root = self.tmp_root / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_timeout_fails_closed_with_no_passing_tests(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        ac_id = "KITQ-BUDGET-NEGCTRL-1"
        _write_ac(self.ac_root, ac_id)
        test_file = _write_test_file(
            self.test_root,
            "test_negctrl.py",
            f"""\
            def test_negctrl():
                # covers: {ac_id}
                assert True
            """,
        )

        # --- Positive control: prove the mapping is load-bearing at all. ---
        passing_nodeid = f"{test_file}::test_negctrl PASSED"
        with patch(
            "done_proof.subprocess.run",
            return_value=_fake_completed_process(stdout=passing_nodeid + "\n"),
        ):
            positive_result = verify_done_eligible(
                ac_id, ac_root=self.ac_root, test_root=self.test_root
            )
        self.assertTrue(
            positive_result["eligible"],
            "Sanity check failed: a genuinely PASSED linked test must make the "
            f"AC eligible, otherwise the negative assertion below is vacuous. "
            f"Got {positive_result!r}.",
        )

        # --- Negative control: a timeout must NOT produce the same verdict. ---
        with patch(
            "done_proof.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=999),
        ):
            timeout_result = verify_done_eligible(
                ac_id, ac_root=self.ac_root, test_root=self.test_root
            )

        self.assertFalse(
            timeout_result["eligible"],
            "A pytest timeout must never be indistinguishable from a pass -- "
            f"got eligible={timeout_result['eligible']!r}.",
        )
        self.assertEqual(
            timeout_result["passing_tests"],
            [],
            "No test may be recorded as passing when the run never completed; "
            f"got {timeout_result['passing_tests']!r}.",
        )


# ---------------------------------------------------------------------------
# Bullet 4 -- a timeout is reported distinguishably from "test not run".
# ---------------------------------------------------------------------------


class TestTimeoutIsReportedDistinguishably(unittest.TestCase):
    """The operator-facing reason must name the budget and the command."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.ac_root = self.tmp_root / "ac-store"
        self.test_root = self.tmp_root / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_timeout_reason_names_the_budget_and_command_not_bare_not_run(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        """Today's wording is indistinguishable from "the tests do not exist".

        Today, ``_describe_non_passing`` falls back to the literal word "not run"
        for any nodeid absent from ``pytest_results`` -- which is exactly what a
        timeout produces (an empty dict), and exactly the same string a genuinely
        missing/never-collected test produces.  An operator reading "linked test
        not run: <path>::<func>" cannot tell "the gate ran out of time" from "the
        test was never written".  This asserts the reason emitted on a genuine
        timeout is not that ambiguous bare phrase and instead names the budget
        (a number of seconds) and the command (pytest) that could not complete.
        """
        ac_id = "KITQ-BUDGET-DISTINGUISH-1"
        _write_ac(self.ac_root, ac_id)
        test_file = _write_test_file(
            self.test_root,
            "test_distinguish.py",
            f"""\
            def test_distinguish():
                # covers: {ac_id}
                assert True
            """,
        )
        budget_used = 172.0
        with patch(
            "done_proof.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=[sys.executable, "-m", "pytest", str(test_file)],
                timeout=budget_used,
            ),
        ):
            result = verify_done_eligible(
                ac_id, ac_root=self.ac_root, test_root=self.test_root
            )

        self.assertFalse(result["eligible"])
        reason = result["reason"]
        bare_not_run_phrase = f"linked test not run: {test_file}::test_distinguish"
        self.assertNotEqual(
            reason.strip(),
            bare_not_run_phrase,
            "The timeout reason must not be the bare 'not run' phrase -- that "
            "wording is indistinguishable from a test that was never written. "
            f"Got reason={reason!r}.",
        )
        self.assertTrue(
            any(
                token in reason.lower()
                for token in ("budget", "timed out", "timeout", "could not verify")
            ),
            "The reason must name that verification could not complete within its "
            f"time budget (one of: budget/timed out/timeout/could not verify). "
            f"Got reason={reason!r}.",
        )
        self.assertIn(
            "pytest",
            reason.lower(),
            f"The reason must name the command (pytest) that could not finish. "
            f"Got reason={reason!r}.",
        )
        self.assertTrue(
            any(char.isdigit() for char in reason),
            "The reason must name the budget as a number of seconds so an "
            f"operator can see what limit was hit. Got reason={reason!r}.",
        )


# ---------------------------------------------------------------------------
# Bullet 5 -- env-var override: honoured when valid, safe fallback otherwise.
# ---------------------------------------------------------------------------


class TestBudgetEnvOverride(unittest.TestCase):
    """A configurable escape hatch must be honoured -- and never crash or zero out."""

    def _captured_timeout(self) -> float:
        with patch(
            "done_proof.subprocess.run", return_value=_fake_completed_process()
        ) as mock_run:
            _run_pytest_and_parse([Path("fake_test.py")])
        _, kwargs = mock_run.call_args
        return kwargs["timeout"]

    def test_env_override_is_honoured_when_valid(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        """``LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS`` overrides the default."""
        import os

        old = os.environ.get(_ENV_OVERRIDE_VAR)
        os.environ[_ENV_OVERRIDE_VAR] = "500"
        try:
            timeout_used = self._captured_timeout()
        finally:
            if old is None:
                os.environ.pop(_ENV_OVERRIDE_VAR, None)
            else:
                os.environ[_ENV_OVERRIDE_VAR] = old

        self.assertEqual(
            timeout_used,
            500.0,
            f"An explicit env override of 500 must be honoured verbatim; "
            f"got timeout={timeout_used!r}.",
        )

    def test_env_override_falls_back_to_default_when_absent_or_garbage(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        """An absent or non-numeric override must not crash or silently zero out."""
        with _ClearEnvOverride():
            default_timeout = self._captured_timeout()

        import os

        old = os.environ.get(_ENV_OVERRIDE_VAR)
        os.environ[_ENV_OVERRIDE_VAR] = "not-a-number"
        try:
            garbage_timeout = self._captured_timeout()
        finally:
            if old is None:
                os.environ.pop(_ENV_OVERRIDE_VAR, None)
            else:
                os.environ[_ENV_OVERRIDE_VAR] = old

        self.assertGreater(
            default_timeout,
            0,
            f"The default (no override) budget must be a positive number of "
            f"seconds, never zero or crashing; got {default_timeout!r}.",
        )
        self.assertGreater(
            default_timeout,
            60,
            "The fallback default must be the NEW computed budget, not the old "
            f"hardcoded 60s this KI is about -- got default={default_timeout!r}. "
            "(If this equals 60, the env-var plumbing may exist but nothing "
            "upstream of it has actually raised the default yet.)",
        )
        self.assertEqual(
            garbage_timeout,
            default_timeout,
            "A non-numeric override value must fall back to the same computed "
            f"default, not crash and not silently go to zero. Got "
            f"garbage={garbage_timeout!r}, default={default_timeout!r}.",
        )


if __name__ == "__main__":
    unittest.main()
