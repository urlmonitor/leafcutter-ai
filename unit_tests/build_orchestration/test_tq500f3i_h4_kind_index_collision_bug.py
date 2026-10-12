"""
MODULE: unit_tests/build_orchestration/test_tq500f3i_h4_kind_index_collision_bug.py
GOAL: RED regression tests for pr-reviewer finding H-4 against
    scripts/ac_store/_done_proof_kind_support.py's ``_index_kind_plugin_output``
    / ``_load_kind_map``.

THE BUG: the H-1 fix (``_kind_plugin.py``, a real pytest plugin recording
    each test's FINAL raised exception TYPE) is correct in what it records,
    but ``_index_kind_plugin_output`` indexes those recordings by
    ``(file_basename, bare_func_name)`` ONLY -- neither the enclosing class
    nor the full directory path is part of the key. Two real, everyday
    shapes collide on that same key and silently cross-attribute one test's
    exception type to a DIFFERENT test:

        (a) two classes in ONE file share a method name --
            ``TestAbsence::test_shared_name`` (ImportError) and
            ``TestAssertion::test_shared_name`` (AssertionError) both index
            to ``(file.py, "test_shared_name")``.

        (b) two files sharing a basename in different package directories
            (this repo already requires ``__init__.py`` per directory for
            exactly this reason -- distinct, non-colliding module identity)
            share a function name -- ``pkg_a/test_x.py::test_shared_func``
            and ``pkg_b/test_x.py::test_shared_func`` both index to
            ``("test_x.py", "test_shared_func")``.

    Investigation while reproducing this finding also surfaced that the SAME
    (file_basename, func_name)-only ambiguity affects an EARLIER, pre-existing
    seam: ``done_proof._find_nodeid_for_test`` -- the covers-tag-to-nodeid
    mapping used BEFORE kind classification even runs -- collapses both
    colliding tags onto ONE physical pytest nodeid, so the OTHER test
    silently vanishes from the verdict entirely rather than merely reading a
    swapped kind.

USER DECISION (option A, this AC's scope): the tag->nodeid collapse in
    ``done_proof._find_nodeid_for_test`` is PRE-EXISTING, and ``done_proof.py``
    already sits over the file-size ratchet -- proper per-test disambiguation
    there (full identity: directory + class path + function name, not
    basename + bare name) is DEFERRED to a separate AC. THIS PR's scope is
    narrower: the reader must FAIL CLOSED rather than guess whenever ANY
    (file_basename, func_name) collision is present ANYWHERE in the
    newly-added batch -- gate_passed=False, reason="ambiguous_test_identity"
    -- rather than silently reporting a wrong kind, a wrong acceptance, or a
    wrong refusal for either colliding test. This is a coarser, batch-wide
    safety net (test (d) below pins that the ambiguity need not even involve
    a DECLARED test to trip it), not the full per-test fix.

THE PINNED FIX these tests target (this AC's scope only):
    * (a)/(b): a real (file_basename, func_name) collision anywhere in the
      batch -> gate_passed=False, reason="ambiguous_test_identity". The
      verdict must never list the absence-red test as accepted (ordinary)
      red, and must never confidently report a wrong kind (e.g. "assertion")
      for what is really the absence test.
    * (d): the ambiguity need not touch a declared test at all -- an
      UNRELATED, undeclared colliding pair elsewhere in the same batch still
      trips the fail-closed path for a SEPARATE declared absence-only test
      whose own identity is perfectly unique. Ambiguity anywhere in the
      batch is not silently ignored just because it doesn't touch the
      declared test being evaluated.
    * (e) CONTROL: with NO collision anywhere in the batch, behaviour is
      byte-identical to the rest of the TQ-500f-3-i suite -- refusal still
      works by full identity (reusing the existing T1/T2/T3 fixture).
    * (c) CONTROL (kept unchanged from the first cut of this file): when a
      kind is genuinely undetermined at the ``_run_pytest_and_parse_with_kind``
      seam (not a same-key collision, just a missing entry), the EXISTING
      H-1 fail-closed contract (``declared_test_kind_undetermined``) already
      holds without corrupting a resolved sibling -- this is a DIFFERENT
      reason token from "ambiguous_test_identity" (a missing entry is not
      the same fact as a same-key collision) and is deliberately left as
      the already-passing control it is.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-i.yaml
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_MODULE_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

from fast_lane import verify_red_baseline  # noqa: E402

import unit_tests.build_orchestration._tq500f3i_fixtures as fx  # noqa: E402

REFUSAL_REASON = "declared_test_refused_absence_only_red"
UNDETERMINED_REASON = "declared_test_kind_undetermined"
AMBIGUOUS_IDENTITY_REASON = "ambiguous_test_identity"


class _H4Case(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.ac_root = self.tmp_root / "ac_store"

    def tearDown(self) -> None:
        self._tmp.cleanup()


def _assert_no_wrong_kind_for_shared_name(verdict: dict, shared_name: str) -> None:
    """No entry anywhere in the verdict may confidently classify *shared_name*
    at all -- neither accepted as ordinary red nor refused as absence. The
    whole point of failing closed on a collision is that NEITHER claim is
    trustworthy.
    """
    assert shared_name not in fx.names(verdict.get("red")), (
        f"A colliding name must never be silently accepted as ordinary red "
        f"evidence; verdict={verdict!r}."
    )
    assert shared_name not in fx.names(verdict.get("refused")), (
        f"A colliding name must never be silently refused either -- a "
        f"refusal is itself a confident 'this one is absence' claim the "
        f"reader cannot actually back with a disambiguated identity; "
        f"verdict={verdict!r}."
    )


class TestH4aSharedMethodNameAcrossClasses(_H4Case):
    def test_h4a_shared_method_name_in_two_classes_fails_closed(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """TestAbsence.test_shared_name (declared, function-level absence)
        and TestAssertion.test_shared_name (an ordinary assertion failure)
        live in the SAME file with the SAME bare method name -- a real
        (file_basename, func_name) collision. This PR's scope: fail closed
        with 'ambiguous_test_identity' rather than guess either test's kind.
        """
        ac_id = "TQ-H4A-001"
        shared_name = "test_shared_name"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": shared_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_shared_method_name.py",
            f"""\
            class TestAbsence:
                def {shared_name}(self):
                    # covers: {ac_id}
                    from doesnotexist_h4a_mod import thing
                    thing()


            class TestAssertion:
                def {shared_name}(self):
                    # covers: {ac_id}
                    assert False, "ordinary assertion failure, not an absence"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            f"A same-file, same-method-name collision must fail the gate "
            f"closed; verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            AMBIGUOUS_IDENTITY_REASON,
            f"The reason must name the identity ambiguity, not any other "
            f"reason; verdict={verdict!r}.",
        )
        _assert_no_wrong_kind_for_shared_name(verdict, shared_name)


class TestH4bSharedBasenameAcrossPackageDirs(_H4Case):
    def test_h4b_shared_basename_and_func_name_across_package_dirs_fails_closed(
        self,
    ) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """pkg_a/test_shared_basename.py::test_shared_func (declared,
        function-level absence) and pkg_b/test_shared_basename.py::
        test_shared_func (an ordinary assertion failure) share BOTH the file
        basename AND the function name across two real, __init__.py-package
        directories (this repo's own convention for giving same-basename
        files distinct module identity) -- a real (file_basename, func_name)
        collision. Fails closed with 'ambiguous_test_identity'.
        """
        ac_id = "TQ-H4B-001"
        func_name = "test_shared_func"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": func_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(test_root / "pkg_a" / "__init__.py", "")
        fx.write(test_root / "pkg_b" / "__init__.py", "")
        fx.write(
            test_root / "pkg_a" / "test_shared_basename.py",
            f"""\
            def {func_name}():
                # covers: {ac_id}
                from doesnotexist_h4b_mod import thing
                thing()
            """,
        )
        fx.write(
            test_root / "pkg_b" / "test_shared_basename.py",
            f"""\
            def {func_name}():
                # covers: {ac_id}
                assert False, "ordinary assertion failure, not an absence"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            f"A same-basename, same-function-name collision across two "
            f"package dirs must fail the gate closed; verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            AMBIGUOUS_IDENTITY_REASON,
            f"The reason must name the identity ambiguity, not any other "
            f"reason; verdict={verdict!r}.",
        )
        _assert_no_wrong_kind_for_shared_name(verdict, func_name)


class TestH4cAmbiguousKindNeverGuessesAndNeverCorruptsSiblings(_H4Case):
    def test_h4c_genuinely_ambiguous_kind_fails_closed_without_corrupting_sibling(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """CONTROL (kept as-is): when one declared entry's kind is genuinely
        unresolvable (driven in directly at the _run_pytest_and_parse_with_kind
        seam -- a MISSING entry, not a same-key collision), the gate fails
        closed with 'declared_test_kind_undetermined' for THAT entry -- and,
        critically, a SIBLING declared entry whose kind WAS resolved
        correctly must still be classified correctly, not swept into the
        same undetermined/failure state (the batch-wide collapse H-1 already
        fixed once must not reappear here). Already passes today.
        """
        ac_id = "TQ-H4C-001"
        resolvable_name = "test_resolvable_assertion"
        ambiguous_name = "test_ambiguous_kind"
        fx.write_ac_yaml(
            self.ac_root,
            ac_id,
            [
                {"name": resolvable_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]},
                {"name": ambiguous_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]},
            ],
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_resolvable.py",
            f"""\
            def {resolvable_name}():
                # covers: {ac_id}
                assert False, "resolvable ordinary assertion"
            """,
        )
        fx.write(
            test_root / "test_ambiguous.py",
            f"""\
            def {ambiguous_name}():
                # covers: {ac_id}
                assert False
            """,
        )
        resolvable_nodeid = f"{test_root / 'test_resolvable.py'}::{resolvable_name}"
        ambiguous_nodeid = f"{test_root / 'test_ambiguous.py'}::{ambiguous_name}"

        with patch(
            "fast_lane._run_pytest_and_parse_with_kind",
            return_value=(
                {resolvable_nodeid: "FAILED", ambiguous_nodeid: "FAILED"},
                {resolvable_nodeid: "assertion"},  # ambiguous_nodeid deliberately absent
            ),
        ):
            verdict = verify_red_baseline(
                ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
            )

        self.assertFalse(
            verdict.get("gate_passed"),
            f"An undetermined-kind declared entry must fail the gate "
            f"closed; verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            UNDETERMINED_REASON,
            f"The reason must name the undetermined kind, never a generic "
            f"or misleading reason, and never the DIFFERENT "
            f"'ambiguous_test_identity' reason -- a missing kind entry is "
            f"not the same fact as a same-key collision; verdict={verdict!r}.",
        )
        self.assertIn(
            resolvable_name,
            fx.names(verdict.get("red")),
            f"The SIBLING declared entry, whose kind WAS resolved "
            f"('assertion'), must still be classified and kept in 'red' -- "
            f"the other entry's ambiguity must not corrupt it (no "
            f"batch-wide collapse); verdict={verdict!r}.",
        )
        self.assertNotIn(
            ambiguous_name,
            fx.names(verdict.get("green_at_baseline")),
            f"The undetermined-kind entry must never be reported as green; "
            f"verdict={verdict!r}.",
        )


class TestH4dCollisionElsewhereInBatchStillTripsFailClosed(_H4Case):
    def test_h4d_unrelated_undeclared_collision_elsewhere_still_fails_closed(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """A declared absence-only test (test_declared_unique) whose own
        identity is perfectly unique sits in the SAME batch as an UNRELATED,
        UNDECLARED pair (TestX.test_shared_undeclared / TestY.test_shared_
        undeclared) that collides on (file_basename, func_name). Ambiguity
        ANYWHERE in the batch is not ignored just because it doesn't touch
        the declared test -- the gate still fails closed with
        'ambiguous_test_identity', and the otherwise-legitimate declared
        absence must NOT be silently accepted as a red-baseline pass.
        """
        ac_id = "TQ-H4D-001"
        unique_name = "test_declared_unique"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": unique_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_declared_unique.py",
            f"""\
            def {unique_name}():
                # covers: {ac_id}
                from doesnotexist_h4d_mod import thing
                thing()
            """,
        )
        fx.write(
            test_root / "test_unrelated_collision.py",
            f"""\
            class TestX:
                def test_shared_undeclared(self):
                    # covers: {ac_id}
                    assert False, "unrelated ordinary assertion, class X"


            class TestY:
                def test_shared_undeclared(self):
                    # covers: {ac_id}
                    assert False, "unrelated ordinary assertion, class Y"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            f"Ambiguity anywhere in the batch -- even in an UNDECLARED, "
            f"unrelated pair -- must fail the gate closed; verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            AMBIGUOUS_IDENTITY_REASON,
            f"verdict={verdict!r}.",
        )
        self.assertNotIn(
            unique_name,
            fx.names(verdict.get("red")),
            f"The otherwise-legitimate declared-unique absence test must "
            f"NOT be silently accepted as ordinary red evidence while "
            f"unrelated ambiguity elsewhere in the batch is ignored; "
            f"verdict={verdict!r}.",
        )


class TestH4eNoCollisionControl(_H4Case):
    def test_h4e_no_collision_anywhere_behaviour_is_unchanged(self) -> None:
        # covers: TQ-500f-3-i
        # angle: boundary
        """CONTROL: reuses the existing T1/T2/T3 fixture (no identity
        collision anywhere) -- refusal still works by full identity exactly
        as the rest of the TQ-500f-3-i suite already proves. The new
        batch-wide ambiguity check must never fire when nothing is actually
        ambiguous.
        """
        ac_id = "TQ-H4E-001"
        fx.write_ac_yaml(self.ac_root, ac_id, fx.t1_t2_t3_test_spec())
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(verdict.get("gate_passed"))
        self.assertEqual(
            verdict.get("reason"),
            REFUSAL_REASON,
            f"With no identity collision anywhere in the batch, the "
            f"ordinary T1-refused verdict must be unchanged -- never "
            f"'ambiguous_test_identity'; verdict={verdict!r}.",
        )
        self.assertIsNotNone(fx.find_by_name(verdict.get("refused"), fx.T1_NAME))
        self.assertIn(fx.T2_NAME, fx.names(verdict.get("red")))
        self.assertIn(fx.T3_NAME, fx.names(verdict.get("red")))


if __name__ == "__main__":
    unittest.main()
