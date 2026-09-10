"""
MODULE: test_uxp_700b_2_i
GOAL: Pin the contract for "a check whose precondition is absent" in the product-truth
    record's checker (docs/product-truth/scripts/validate_product_truth.py):
      AC-1: the check is listed in the report with a stated reason for not executing
            (never silently omitted, never a crash).
      AC-2: an unexecuted check contributes ZERO to any stated examined figure.
      AC-3: the reported outcome for a run carrying an unexecuted check is never the
            same outcome reported for a run that was checked and found sound.
BUSINESS CONTEXT: AC UXP-700b-2-i, depends_on UXP-700b-2 (per-check examined figures,
    still work_status: todo at the time this test was authored) and doc_links GE-120
    ("green means it was checked"). This is GE-120's rule applied one level down to the
    project record's OWN checker, per UXP-700b's notes. UXP-700b-2's own per-check
    figure plumbing has not landed, so per the architect-review comment on this ticket,
    this test pins a SMALL, self-contained addition (record_check_executed /
    record_check_not_executed / build_examined_total / report_outcome / run_checks) in
    validate_product_truth.py rather than inventing a parallel report envelope that
    would conflict with whatever UXP-700b-2 eventually builds.
ARCHITECTURE: The concrete, currently-real "precondition absent" case this repo has is
    the classifier eval check: `_check_eval` reads STORE/classifier/eval.jsonl
    unconditionally via `_read_text`, which re-raises OSError (crashing the entire
    validator run) when the file is absent -- exactly the "vacuous or crashing, never
    visibly skipped" defect GE-120 exists to forbid. `_make_zero_artifact_store` builds
    a minimal, otherwise-valid, zero-flow/zero-mock/zero-mockup product-truth store
    (mirroring the "empty store still validates cleanly" baseline UXP-700b's own notes
    record) WITHOUT classifier/eval.jsonl, so the eval check's precondition is absent
    and every other check finds nothing to complain about.
    test_unexecuted_check_is_listed_with_a_reason calls the new run_checks() directly
    against that fixture (angle: failure -- known-bad/absent input; the run must not
    crash and the check must be visibly listed with a reason).
    test_unexecuted_check_adds_nothing_to_examined_figures is a pure unit test of
    build_examined_total() with synthetic check entries -- no filesystem at all
    (angle: boundary).
    test_ac3_outcome_not_reported_as_sound_when_check_unexecuted is a pure unit test of
    report_outcome() -- the AC-3 clause has no dedicated test_spec entry in the AC
    store, so this test is added under the Contract-Aware Mode AC-mapping rule
    (angle: criterion -- it proves AC-3's Then-clause directly on the unit).
    test_uxp_700b_2_i_reachable_from_entry_point invokes the REAL CLI entry point
    (docs/product-truth/scripts/validate_product_truth.py, main() guarded by
    `if __name__ == "__main__":` with argparse) as a subprocess against a copied
    fixture store, per the Reachability Entry-Point Resolution procedure's CLI-script
    branch (angle: reachability).

NOTE ON RED BASELINE: none of run_checks / record_check_executed /
    record_check_not_executed / build_examined_total / report_outcome exist yet in
    validate_product_truth.py, so tests A-C fail with AttributeError on arrival. Test D
    (reachability) fails today for a DIFFERENT, equally real reason: the current
    `_check_eval` re-raises OSError when classifier/eval.jsonl is absent, so the
    unmodified script crashes with a non-zero exit and a traceback instead of listing
    the check as not-executed -- a genuine, currently-reproducible red failure, not an
    import error.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import the
# validator (and, transitively, the generator it imports helpers from) directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PRODUCT_TRUTH_DIR = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PRODUCT_TRUTH_DIR / "scripts"
_SCHEMAS_DIR = _PRODUCT_TRUTH_DIR / "schemas"
_REAL_VALIDATOR_SCRIPT = _SCRIPTS_DIR / "validate_product_truth.py"
_REAL_GENERATOR_SCRIPT = _SCRIPTS_DIR / "generate_product_truth.py"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402

_SCHEMA_FILES = (
    "flow.schema.json",
    "mock-data.schema.json",
    "mockup.schema.json",
    "classifier-eval.schema.json",
)


def _make_zero_artifact_store(tmp: Path, *, with_eval_file: bool) -> Path:
    """Build a minimal, otherwise-valid product-truth store holding zero artifacts.

    Layout mirrors test_uxp_700a_2_i's zero-artifact generator fixture, extended with
    the pieces validate_product_truth.py additionally needs: a real schemas/ dir
    (jsonschema is a hard dependency) and a classifier/ dir. When with_eval_file is
    False, classifier/eval.jsonl is deliberately ABSENT -- the eval check's
    precondition is then absent, which is the scenario this AC is about. When True,
    an empty (zero-row) eval.jsonl is written so the check executes normally.

    Returns the product-truth store root (the directory validate_product_truth.py and
    generate_product_truth.py both call STORE).
    """
    store = tmp / "product-truth"
    (store / "flows").mkdir(parents=True)
    (store / "mock-data").mkdir(parents=True)
    (store / "mockups").mkdir(parents=True)
    (store / "classifier").mkdir(parents=True)
    (store / "schemas").mkdir(parents=True)
    for schema_name in _SCHEMA_FILES:
        (store / "schemas" / schema_name).write_bytes((_SCHEMAS_DIR / schema_name).read_bytes())
    (tmp / "acceptance-criteria").mkdir(parents=True)

    index = {
        "artifacts": [],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {},
        "by_ac": {},
    }
    (store / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    if with_eval_file:
        (store / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    # else: classifier/eval.jsonl is left absent -- the precondition-absent case.

    return store


class TestUnexecutedCheckListedWithReason(unittest.TestCase):
    """AC-1: a check whose precondition is absent is listed with a stated reason."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)
        self.store = _make_zero_artifact_store(self.tmp, with_eval_file=False)
        self._orig = (vpt.STORE, vpt.AC_STORE, gpt.STORE, gpt.AC_STORE)
        ac_store = self.tmp / "acceptance-criteria"
        vpt.STORE, vpt.AC_STORE = self.store, ac_store
        gpt.STORE, gpt.AC_STORE = self.store, ac_store

    def tearDown(self) -> None:
        vpt.STORE, vpt.AC_STORE, gpt.STORE, gpt.AC_STORE = self._orig
        self._tmp_dir.cleanup()

    def test_unexecuted_check_is_listed_with_a_reason(self) -> None:
        # covers: UXP-700b-2-i
        # angle: failure
        """A check whose precondition is absent appears in the report with a stated
        reason rather than being omitted (or crashing the whole run).

        Implementation requirement: validate_product_truth.py must expose
        run_checks() -> dict with a "checks" list; when classifier/eval.jsonl is
        absent, the "eval" check's precondition is absent, so it does not read the
        file (no crash) and instead appends an entry with executed=False and a
        non-empty "reason" string -- not a silently-omitted check, not a raised
        exception.
        """
        report = vpt.run_checks()

        eval_entries = [c for c in report["checks"] if c.get("name") == "eval"]
        self.assertEqual(
            len(eval_entries),
            1,
            f"expected exactly one 'eval' check entry in the report, got: {report['checks']!r}",
        )
        entry = eval_entries[0]
        self.assertFalse(
            entry.get("executed"),
            "classifier/eval.jsonl is absent -- the eval check's precondition is absent, "
            f"so it must be listed with executed=False, got entry: {entry!r}",
        )
        self.assertTrue(
            isinstance(entry.get("reason"), str) and entry["reason"].strip(),
            f"a not-executed check must carry a non-empty stated reason, got entry: {entry!r}",
        )


class TestUnexecutedCheckExaminedFigures(unittest.TestCase):
    """AC-2: an unexecuted check contributes no records to any stated examined figure."""

    def test_unexecuted_check_adds_nothing_to_examined_figures(self) -> None:
        # covers: UXP-700b-2-i
        # angle: boundary
        """The examined total is the same whether or not the unexecutable check is
        present -- a pure unit test of build_examined_total(), no filesystem.

        Implementation requirement: validate_product_truth.py must expose
        record_check_executed(checks, name, examined), record_check_not_executed(checks,
        name, reason), and build_examined_total(checks) -> int, and the not-executed
        entry's contribution to the total must be exactly zero regardless of what other
        executed checks already contributed.
        """
        checks: list[dict] = []
        vpt.record_check_executed(checks, "flows", 5)
        vpt.record_check_executed(checks, "mocks", 3)
        total_before = vpt.build_examined_total(checks)
        self.assertEqual(total_before, 8, f"sanity check on the two executed entries failed: {checks!r}")

        vpt.record_check_not_executed(checks, "eval", "classifier/eval.jsonl not found")
        total_after = vpt.build_examined_total(checks)

        self.assertEqual(
            total_after,
            total_before,
            "an unexecuted check must contribute zero to the examined total -- "
            f"before={total_before}, after adding the unexecuted check={total_after}",
        )


class TestOutcomeVocabularyGuard(unittest.TestCase):
    """AC-3: the reported outcome is never the checked-and-sound outcome while any
    check is listed as not executed.

    No test_spec entry in the AC store targets AC-3 directly (the store only carries
    test_spec entries for AC-1 and AC-2); this test is added per the Contract-Aware
    Mode AC-mapping rule so every checkbox AC in the ticket has at least one test.
    """

    def test_ac3_outcome_not_reported_as_sound_when_check_unexecuted(self) -> None:
        # covers: UXP-700b-2-i
        # angle: criterion
        """report_outcome() must not return the checked-and-sound outcome for a checks
        list that includes any not-executed entry, even with zero errors.

        Implementation requirement: validate_product_truth.py must expose
        report_outcome(checks, has_errors=False) -> str, returning a fixed
        "checked-and-sound" sentinel only when every check executed and there are no
        errors, and a DIFFERENT sentinel whenever any check is listed as not executed.
        """
        sound_checks: list[dict] = []
        vpt.record_check_executed(sound_checks, "flows", 5)
        sound_outcome = vpt.report_outcome(sound_checks, has_errors=False)
        self.assertEqual(
            sound_outcome,
            "checked-and-sound",
            f"a fully-executed, error-free checks list must report the sound outcome, got {sound_outcome!r}",
        )

        degraded_checks = list(sound_checks)
        vpt.record_check_not_executed(degraded_checks, "eval", "classifier/eval.jsonl not found")
        degraded_outcome = vpt.report_outcome(degraded_checks, has_errors=False)

        self.assertNotEqual(
            degraded_outcome,
            "checked-and-sound",
            "the outcome for a run carrying a not-executed check must not be the same "
            "outcome as a run that was checked and found sound (AC-3), even with zero errors",
        )


class TestReachability(unittest.TestCase):
    """angle: reachability -- the real CLI entry point must surface the same guarantee."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_uxp_700b_2_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700b-2-i
        # angle: reachability
        """Invokes the real CLI entry point (subprocess) and asserts the behaviour.

        Entry point resolution (Reachability Entry-Point Resolution, step 1 -- CLI
        script): validate_product_truth.py exposes a main() guarded by
        `if __name__ == "__main__":` with argparse, invoked in production as
        `python docs/product-truth/scripts/validate_product_truth.py`. This test
        copies both that real script and its real generate_product_truth.py sibling
        (verbatim bytes, read from disk -- validate_product_truth.py imports helpers
        from generate_product_truth at module load) into a fixture store shaped like
        the real one, then runs the validator as a subprocess with real argv against a
        store whose classifier/eval.jsonl is absent. Importing validate_product_truth
        and calling run_checks() directly (as the boundary tests above do) does NOT
        satisfy this angle on its own -- this test exists to prove the behaviour
        survives main()'s CLI-argument-parsing and logging path, which a direct call
        bypasses, and specifically that the process does not crash (today it does:
        _check_eval currently re-raises OSError on a missing eval.jsonl).
        """
        store = _make_zero_artifact_store(self.tmp, with_eval_file=False)
        scripts_dir = store / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "validate_product_truth.py").write_bytes(_REAL_VALIDATOR_SCRIPT.read_bytes())
        (scripts_dir / "generate_product_truth.py").write_bytes(_REAL_GENERATOR_SCRIPT.read_bytes())
        # build.py deploys scripts/ as a whole "*.py" glob, and validate/generate
        # import sibling modules (product_truth_checks, product_truth_index_checks,
        # product_truth_derivations). Copy the whole set so this fixture matches
        # what a real install actually contains.
        for _sibling in sorted(_SCRIPTS_DIR.glob("*.py")):
            (scripts_dir / _sibling.name).write_bytes(_sibling.read_bytes())

        result = subprocess.run(
            [sys.executable, str(scripts_dir / "validate_product_truth.py")],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(
            result.returncode,
            0,
            "the validator must not crash when a check's precondition (classifier/"
            f"eval.jsonl) is absent -- it must fail open and list the check as not "
            f"executed instead.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        combined_output = result.stdout + result.stderr
        self.assertTrue(
            any(marker in combined_output for marker in ("SKIPPED", "not executed", "did not execute")),
            "expected the not-executed eval check to be surfaced with a visible marker "
            f"and a reason in the CLI output; got:\n{combined_output}",
        )
        self.assertIn(
            "eval",
            combined_output,
            f"the surfaced not-executed marker must name the 'eval' check; got:\n{combined_output}",
        )
        self.assertNotIn(
            "eval + index + derived data valid",
            combined_output,
            "the clean-pass success message (which claims eval was validated) must NOT "
            f"be printed while the eval check is listed as not executed; got:\n{combined_output}",
        )


if __name__ == "__main__":
    unittest.main()
