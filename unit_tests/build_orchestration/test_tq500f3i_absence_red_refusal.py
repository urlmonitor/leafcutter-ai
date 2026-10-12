"""
MODULE: unit_tests/build_orchestration/test_tq500f3i_absence_red_refusal.py
GOAL: RED test stubs for TQ-500f-3-i -- the ONE existing verify_red_baseline
    reader (scripts/build_orchestration/fast_lane.py +
    _fl_red_baseline_support.py) must refuse an absence-only red
    (ImportError/AttributeError/ModuleNotFoundError raised before any code
    under test ran) for a covering test whose AC test_spec entry declares
    ``must_catch`` (non-empty) OR ``angle: discrimination``.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-i.yaml

=== Pinned interface contract under test (NOT yet implemented) ===

    verify_red_baseline(
        *, ac_ids: list[str], test_root: Path, base_ref: str | None = None,
        ac_root: Path,
    ) -> dict

Return dict gains an additive ``"refused"`` key: a list of
``{"nodeid": str, "ac_id": str, "kind": "absence", "message": str}`` entries
-- one per declared (must_catch or angle:discrimination) covering test whose
ONLY red was an absence red. When ``refused`` is non-empty, ``gate_passed``
is False with reason ``"declared_test_refused_absence_only_red"`` (a
DISTINCT, stable token; the exact wording is this file's own proposed
contract -- any distinct, stable reason value satisfies TQ-500f-3-i's
criteria, but the assertions below pin this specific one so the tests are
checkable rather than "any string"). This holds even when other newly-added
covering tests in the same batch are properly red (fail-closed, must_block).

The CURRENT on-disk verify_red_baseline has signature
``(*, ac_ids, test_root, base_ref=None)`` -- no ``ac_root`` parameter exists
yet, so EVERY test below that calls it directly is expected to fail with
``TypeError: verify_red_baseline() got an unexpected keyword argument
'ac_root'`` -- a genuine RED state (BO-2400a-3-ii's sibling file established
this exact "extraneous new kwarg -> TypeError" pattern for signature
extensions in this module). The CLI end-to-end test (test 4) similarly
fails because the ``verify_red_baseline`` subcommand has no ``--ac-root``
flag yet (see scripts/build_orchestration/_fl_cli.py).

WRONG-VERSION DISCRIMINATION (the angle this file itself proves against):
a reader that "accepts every red as before" passes T1 -- caught by test 1
and test 5. A reader that "refuses every import-error red" wrongly refuses
T3 -- caught by test 2 and test 6 (the control). A reader that "classifies
from the AC's criteria wording" is caught by test 4's wording-mutation
assertion. A reader that "trusts a self-reported red_baseline kind label"
is caught implicitly -- no such label exists anywhere in these fixtures'
inputs, so a reader that requires one cannot pass any test here.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

from fast_lane import verify_red_baseline  # noqa: E402

import unit_tests.build_orchestration._tq500f3i_fixtures as fx  # noqa: E402

REFUSAL_REASON = "declared_test_refused_absence_only_red"
REACH_THE_CODE_PHRASE = "must fail by reaching the code"


class _Tq500f3iCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.ac_root = self.tmp_root / "ac_store"

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestT1RefusedAndReportNamesIt(_Tq500f3iCase):
    def test_red_baseline_refuses_absence_only_red_for_must_catch_test(self) -> None:
        # covers: TQ-500f-3-i
        # angle: criterion
        """T1 (must_catch declared, only red is a function-level ImportError)
        is refused as red evidence; the report names T1, its kind ('absence'),
        and states a test naming wrong versions to catch must fail by
        reaching the code.
        """
        ac_id = "TQ-FIX-3I-001"
        fx.write_ac_yaml(self.ac_root, ac_id, fx.t1_t2_t3_test_spec())
        work_dir, base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        verdict = verify_red_baseline(
            ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
        )

        refused = verdict.get("refused")
        self.assertIsNotNone(
            refused,
            f"verify_red_baseline's return dict must carry a 'refused' key "
            f"once ac_root-aware absence-refusal is implemented; got {verdict!r}.",
        )
        t1_entry = fx.find_by_name(refused, fx.T1_NAME)
        self.assertIsNotNone(
            t1_entry,
            f"T1 ({fx.T1_NAME}) must appear in 'refused' -- it declares "
            f"must_catch and its only red is an absence red; refused={refused!r}.",
        )
        if t1_entry is not None:
            self.assertEqual(t1_entry.get("ac_id"), ac_id)
            self.assertEqual(
                t1_entry.get("kind"),
                "absence",
                f"T1's refused entry must report kind='absence'; got {t1_entry!r}.",
            )
            message = str(t1_entry.get("message", "")).lower()
            self.assertIn(
                REACH_THE_CODE_PHRASE,
                message,
                "T1's refused entry must state that a test naming wrong "
                f"versions to catch must fail by reaching the code; got {t1_entry!r}.",
            )
        self.assertNotIn(
            fx.T1_NAME,
            fx.names(verdict.get("red")),
            "T1 must NOT also appear in 'red' -- it is refused, not accepted, "
            f"as red evidence; red={verdict.get('red')!r}.",
        )


class TestT2AndT3AcceptedControl(_Tq500f3iCase):
    def test_red_baseline_accepts_assertion_red_and_undeclared_absence_red(self) -> None:
        # covers: TQ-500f-3-i
        # angle: boundary
        """T2 (declared, AssertionError) and T3 (undeclared, ImportError) are
        both accepted as red evidence -- the control against a reader that
        refuses EVERY import-error red rather than only a DECLARED one.
        """
        ac_id = "TQ-FIX-3I-002"
        fx.write_ac_yaml(self.ac_root, ac_id, fx.t1_t2_t3_test_spec())
        work_dir, base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        verdict = verify_red_baseline(
            ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
        )

        self.assertIn(
            fx.T2_NAME,
            fx.names(verdict.get("red")),
            f"T2 (assertion red, declared must_catch) must be accepted in "
            f"'red'; got red={verdict.get('red')!r}.",
        )
        self.assertIn(
            fx.T3_NAME,
            fx.names(verdict.get("red")),
            "T3 (absence red, UNDECLARED -- no must_catch, no "
            "angle:discrimination) must still be accepted in 'red': absence "
            "red stays valid for a test that declares no wrong version to "
            f"catch; got red={verdict.get('red')!r}.",
        )
        refused_names = fx.names(verdict.get("refused"))
        self.assertNotIn(
            fx.T2_NAME, refused_names, f"T2 must never be refused; refused={verdict.get('refused')!r}."
        )
        self.assertNotIn(
            fx.T3_NAME, refused_names, f"T3 must never be refused; refused={verdict.get('refused')!r}."
        )


class TestDiscriminationAngleWithoutMustCatch(_Tq500f3iCase):
    def test_discrimination_angle_without_must_catch_is_treated_as_declared(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """An entry with angle: discrimination and NO must_catch, whose only
        red is an absence red, is refused exactly as a must_catch-declared
        entry is -- the two declaration routes (must_catch OR
        angle:discrimination) are equivalent triggers for refusal.
        """
        ac_id = "TQ-FIX-3I-003"
        func_name = "test_discrim_absence_only"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": func_name, "angle": "discrimination"}]
        )
        work_dir, base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_discrim.py",
            f"""\
            def {func_name}():
                # covers: {ac_id}
                from doesnotexist_discrim_target_mod import discrim_target
                discrim_target()
            """,
        )

        verdict = verify_red_baseline(
            ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
        )

        refused_entry = fx.find_by_name(verdict.get("refused"), func_name)
        self.assertIsNotNone(
            refused_entry,
            f"angle:discrimination (no must_catch) with only absence red must "
            f"be refused exactly as a must_catch-declared entry is; "
            f"verdict={verdict!r}.",
        )
        if refused_entry is not None:
            self.assertEqual(refused_entry.get("kind"), "absence")
        self.assertNotIn(func_name, fx.names(verdict.get("red")))


class TestCliEndToEnd(_Tq500f3iCase):
    def test_verify_red_baseline_cli_refuses_absence_only_red_end_to_end(self) -> None:
        # covers: TQ-500f-3-i
        # angle: reachability
        # surface_invoked: python scripts/build_orchestration/fast_lane.py verify_red_baseline (CLI)
        """Real subprocess CLI invocation, real temp git repo, real temp AC
        store: the JSON on stdout names T1 as refused. Adding 'bug fix of
        existing refresh' wording to the AC's criteria prose does not change
        T3's verdict -- the decision never reads requirement wording.
        """
        ac_id = "TQ-FIX-3I-004"
        fx.write_ac_yaml(
            self.ac_root,
            ac_id,
            fx.t1_t2_t3_test_spec(),
            criteria="This is a bug fix of existing refresh behaviour.",
        )
        work_dir, base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        proc = subprocess.run(
            [
                sys.executable,
                str(fx.GATE_SCRIPT),
                "verify_red_baseline",
                "--ac-ids",
                ac_id,
                "--test-root",
                str(test_root),
                "--base-ref",
                base_sha,
                "--ac-root",
                str(self.ac_root),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        try:
            verdict = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                "verify_red_baseline CLI subprocess must print a parseable "
                f"JSON verdict once --ac-root is wired: {exc}. "
                f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
            )
            return

        refused = verdict.get("refused")
        t1_entry = fx.find_by_name(refused, fx.T1_NAME)
        self.assertIsNotNone(
            t1_entry,
            f"CLI verdict must name T1 as refused; verdict={verdict!r}.",
        )
        self.assertIn(
            fx.T3_NAME,
            fx.names(verdict.get("red")),
            "T3's verdict must be unaffected by the 'bug fix of existing "
            f"refresh' wording added to the AC's criteria prose; verdict={verdict!r}.",
        )
        self.assertFalse(
            verdict.get("gate_passed"),
            f"gate_passed must be False -- T1 was refused; verdict={verdict!r}.",
        )
        self.assertEqual(proc.returncode, 1)


class TestGateFailClosed(_Tq500f3iCase):
    def test_red_baseline_gate_fails_when_any_declared_test_is_absence_only(self) -> None:
        # covers: TQ-500f-3-i
        # angle: criterion
        """T1+T2+T3 together: gate_passed is False with the refusal reason
        and T1 listed as refused, even though T2 and T3 are properly red
        (fail closed -- a refused declared test cannot ride on its siblings).
        """
        ac_id = "TQ-FIX-3I-005"
        fx.write_ac_yaml(self.ac_root, ac_id, fx.t1_t2_t3_test_spec())
        work_dir, base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        verdict = verify_red_baseline(
            ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
        )

        self.assertFalse(
            verdict.get("gate_passed"),
            f"gate_passed must be False: T1 is refused even though T2/T3 are "
            f"properly red (fail closed); verdict={verdict!r}.",
        )
        self.assertEqual(verdict.get("reason"), REFUSAL_REASON)
        self.assertIsNotNone(fx.find_by_name(verdict.get("refused"), fx.T1_NAME))
        self.assertIn(fx.T2_NAME, fx.names(verdict.get("red")))
        self.assertIn(fx.T3_NAME, fx.names(verdict.get("red")))


class TestGatePassesControl(_Tq500f3iCase):
    def test_red_baseline_gate_passes_for_assertion_and_undeclared_absence_only(self) -> None:
        # covers: TQ-500f-3-i
        # angle: boundary
        """Control: with only T2+T3 (no absence-only DECLARED test in the
        batch), gate_passed is True and nothing is refused.
        """
        ac_id = "TQ-FIX-3I-006"
        fx.write_ac_yaml(self.ac_root, ac_id, fx.t1_t2_t3_test_spec())
        work_dir, base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(
            test_root, ac_id, include={fx.T2_NAME, fx.T3_NAME}
        )

        verdict = verify_red_baseline(
            ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
        )

        self.assertTrue(
            verdict.get("gate_passed") is True,
            f"gate_passed must be True: no absence-only DECLARED test is "
            f"present in this batch; verdict={verdict!r}.",
        )
        self.assertEqual(verdict.get("refused"), [])
        self.assertIsNone(verdict.get("reason"))


if __name__ == "__main__":
    unittest.main()
