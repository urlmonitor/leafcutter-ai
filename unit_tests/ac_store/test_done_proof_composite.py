"""
MODULE: unit_tests/ac_store/test_done_proof_composite.py
GOAL: RED test stubs for BO-2500a-6 / BO-2500a-6-i — a done COMPOSITE AC (has
    children / non-empty covered_by) must derive its proof-of-done from its
    covered children instead of being required to carry its own direct
    "# covers:" test, while a done LEAF AC (no children) must still require
    one.

VERIFIED LIVE DEFECT (BO-2500a-6): on PR #414 the required CI gate
    "Proof-of-done coverage check (BO-2500b)" failed with
    "[check-done-proof] ACD-400a: no linked test found for ACD-400a" after the
    PR merely appended a new child id to that done L1's `covered_by` list.
    `done_proof.verify_done_eligible()` has NO concept of composite vs leaf at
    all today — it unconditionally requires a direct `# covers: <ac_id>` tag
    for every done AC it is asked to evaluate, so touching a done composite's
    YAML at all (even a field that carries no test-linkage information, like
    appending to `covered_by`) trips the required merge gate.

=== Interface contract under test (to be implemented by python-coder) ===

  File of record: scripts/ac_store/done_proof.py

    verify_done_eligible(ac_id: str, *, ac_root: Path, test_root: Path) -> dict

  Today `_build_ac_status_map()` (done_proof.py) only extracts `id` and
  `status` from each AC YAML, so `verify_done_eligible()` has no visibility
  into `covered_by` at all. To satisfy this AC, the composite/leaf
  distinction must be made DATA-DRIVEN from each AC's own `covered_by` field
  (never a hard-coded AC-id allowlist):

    * COMPOSITE (non-empty `covered_by`): `verify_done_eligible` must NOT
      require a direct linked test for the composite itself. It is
      satisfied when every id in `covered_by` is itself covered by a
      passing test (or is itself a satisfied composite).
    * LEAF (empty/absent `covered_by`): the existing direct-linked-test
      requirement is unchanged — a leaf with no passing covers-tagged test
      must still be ineligible.

  This exact behaviour is also exercised through the real CI-changed
  wrapper this AC's -i edge case targets:

    scripts/commit_guardian/check_done_proof.py (source: templates/scripts/
    commit_guardian/check_done_proof.py; deployed as a sibling of the real
    scripts/ac_store/done_proof.py via build.py's install_shims/ADR-016)

    check_changed_done_acs(changed_yaml_paths, *, ac_root, test_root) -> list[dict]

  is the function `check_done_proof.py --mode ci-changed` (invoked from
  .github/workflows/ci.yml) delegates to for every done AC whose YAML path
  appears in the PR diff. It calls `verify_done_eligible` per changed done
  AC and reports a violation whenever `eligible` is False — so the fix must
  live in `verify_done_eligible` (or a helper it calls) in done_proof.py,
  not be special-cased in the wrapper.

=== Why verify_done_eligible is exercised directly for AC-6 (tests 1 & 2) ===

  The Implementation Notes name scripts/ac_store/done_proof.py as the file
  of record and require the composite/leaf distinction to "live in this
  module's done-eligibility logic" — i.e. in verify_done_eligible itself.
  Calling it directly is the most direct behavioral exercise of that logic
  and needs no git fixture repo: it takes ac_root/test_root as explicit
  Path arguments, so a real on-disk fixture store + real on-disk pytest
  files fully exercise the real classification and subprocess-pytest code
  paths with zero mocking.

=== Why check_changed_done_acs is exercised for AC-6-i (test 3) ===

  BO-2500a-6-i is specifically about the CI-changed *gate* not tripping on
  a non-coverage edit — the exact PR #414 shape. That guarantee is only
  fully proven by running the actual CI-changed wrapper function
  (check_changed_done_acs), not just the oracle it calls, because the
  wrapper is what decides *which* done ACs get evaluated in a given diff
  (only those whose YAML path is in changed_yaml_paths — see
  unit_tests/commit_guardian/test_done_proof_ci_changed_scope.py) and is
  literally the function `--mode ci-changed` calls per changed done AC.

  This repo's OWN commit_guardian hooks are only materialized in
  scripts/commit_guardian/ once `python scripts/build.py --target-dir .`
  has run (ADR-016 self-hosting: scripts/commit_guardian/ is a build-time
  symlink into .leafcutter/scripts/, sourced from templates/scripts/
  commit_guardian/). In this raw source tree scripts/commit_guardian/ does
  not exist, so check_done_proof.py is imported directly from its
  templates/ source location instead of running the full build. Its
  sibling `ac_store/` under templates/ is an intentional stub
  (.gitkeep only — see check_done_proof.py's own module docstring), so its
  internal `from done_proof import verify_done_eligible` would fail to
  resolve to the REAL implementation if resolved fresh. To route it to the
  real scripts/ac_store/done_proof.py without a git-diff fixture repo or a
  build.py run, this file imports the real `done_proof` module FIRST (so
  Python caches it in sys.modules under the bare name "done_proof"); the
  subsequent `import check_done_proof` then resolves its internal
  `from done_proof import verify_done_eligible` against that sys.modules
  cache rather than re-searching sys.path — so check_changed_done_acs runs
  against the real, patchable done_proof.verify_done_eligible exactly as it
  does in the deployed/CI topology. `git diff` parsing itself
  (_get_changed_ac_yaml_paths) is orthogonal to this defect (it only
  decides which paths are handed to check_changed_done_acs) so a git
  fixture repo would add complexity without adding assurance here.

=== Fixture authenticity mandate ===

  All AC YAML fixtures are written with yaml.safe_dump (never a hand-typed
  YAML string). All covers-tagged test fixtures are real .py files with
  genuine bodies that actually pass under pytest (no mocking of pass/fail
  signals; the real done_proof pytest-subprocess path is exercised).

=== Red baseline ===

  test_done_composite_with_covered_children_passes and
  test_noncoverage_edit_of_done_composite_does_not_trip_check are RED until
  python-coder makes the composite/leaf distinction data-driven in
  done_proof.py. test_done_leaf_without_test_still_fails is the
  anti-over-broadening regression guard — it already holds under the
  current (buggy) implementation, since the current bug is that composites
  are wrongly treated as leaves, not that leaves are under-enforced; it
  must keep passing after the fix.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — see "Why check_changed_done_acs is exercised" above for
# why `done_proof` must be imported (and cached in sys.modules) BEFORE
# `check_done_proof` is imported from its templates/ source location.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
_TEMPLATES_COMMIT_GUARDIAN_DIR = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
)

sys.path.insert(0, str(_REAL_AC_STORE_DIR))
from done_proof import verify_done_eligible  # noqa: E402

sys.path.insert(0, str(_TEMPLATES_COMMIT_GUARDIAN_DIR))
# By the time this import executes, sys.modules["done_proof"] already holds
# the REAL scripts/ac_store/done_proof module (imported above), so
# check_done_proof's own `from done_proof import verify_done_eligible` binds
# to that real, patchable implementation rather than the templates/ stub
# sibling ac_store/ (.gitkeep only).
from check_done_proof import check_changed_done_acs  # noqa: E402

_PYTHON_EXE = sys.executable


# ---------------------------------------------------------------------------
# Shared fixture helpers (yaml.safe_dump mandate)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    status: str = "active",
    work_status: str = "done",
    level: str = "L2",
    covered_by: list[str] | None = None,
) -> Path:
    """Write a real AC YAML via yaml.safe_dump (never a hand-typed literal).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC.
        status: AC lifecycle status ("active", "deprecated", ...).
        work_status: AC work status ("todo", "done", ...).
        level: Flight level string ("L0"..."L3") — cosmetic for this test,
            but kept realistic (composites in the real store are L0/L1).
        covered_by: List of child AC ids. A non-empty list makes this AC a
            COMPOSITE per the Implementation Notes' data-driven definition;
            an empty list (the default) makes it a LEAF.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": status,
        "work_status": work_status,
        "readiness": "reviewed",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": covered_by or [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a real Python test file to *test_root* using textwrap.dedent.

    Args:
        test_root: Directory to place the test file.
        filename: Filename (e.g. "test_my_feature.py").
        content: Python source; leading whitespace is dedented automatically.

    Returns:
        Path to the written test file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test 1 — BO-2500a-6: a done composite with covered children passes
# ---------------------------------------------------------------------------


class TestDoneCompositeWithCoveredChildrenPasses(unittest.TestCase):
    """BO-2500a-6: a done composite AC is satisfied by its covered children —
    it must NOT be failed for lacking a direct linked test of its own."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

        self.composite_id = "BO-TEST-COMPOSITE-1"
        self.child_a_id = "BO-TEST-COMPOSITE-1-CHILD-A"
        self.child_b_id = "BO-TEST-COMPOSITE-1-CHILD-B"

        # The composite itself: L1-shaped, done, non-empty covered_by, and
        # crucially NO direct covers-tagged test anywhere for its own id —
        # exactly the ACD-400a shape from the verified live defect.
        _write_ac(
            self.ac_root,
            self.composite_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[self.child_a_id, self.child_b_id],
        )
        # Its children: done, leaf-shaped (empty covered_by), each covered
        # by a genuinely passing test.
        _write_ac(
            self.ac_root,
            self.child_a_id,
            status="active",
            work_status="done",
            level="L2",
        )
        _write_ac(
            self.ac_root,
            self.child_b_id,
            status="active",
            work_status="done",
            level="L2",
        )
        _write_test_file(
            self.test_root,
            "test_composite_children_coverage.py",
            f"""\
            def test_covers_child_a():
                # covers: {self.child_a_id}
                pass  # genuinely passes

            def test_covers_child_b():
                # covers: {self.child_b_id}
                pass  # genuinely passes
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_done_composite_with_covered_children_passes(self) -> None:
        # covers: BO-2500a-6
        """A done composite whose children are each covered by a passing test
        must be eligible=True even though it has no direct linked test.

        RED today: verify_done_eligible has no concept of composite/leaf and
        unconditionally requires `self.composite_id` to have its own
        '# covers:' tag, so it returns eligible=False with reason
        "no linked test found for BO-TEST-COMPOSITE-1" — reproducing the
        live ACD-400a failure verbatim (only the id differs).

        To make this green, verify_done_eligible must read the composite's
        own `covered_by` field from ac_root, recognise it as non-empty, and
        derive eligibility from whether every id in `covered_by` is covered
        by a passing test (i.e. NOT require a direct linked test for the
        composite id itself).
        """
        verdict = verify_done_eligible(
            self.composite_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(
            verdict["eligible"],
            "A done composite AC whose children are each covered by a "
            "passing test must be eligible for done, even with no direct "
            f"linked test of its own. Got verdict: {verdict}",
        )
        self.assertEqual(
            verdict.get("reason", ""),
            "",
            "The reason must be empty when the composite is eligible via "
            f"its covered children. Got verdict: {verdict}",
        )

    def test_composite_check_via_ci_changed_wrapper_reports_no_violation(
        self,
    ) -> None:
        # covers: BO-2500a-6
        """The real CI-changed wrapper (check_changed_done_acs) must not
        report a violation for the composite either — this is the function
        `--mode ci-changed` (the required CI gate) actually calls per
        changed done AC, so the AC is only truly satisfied once the wrapper
        (not just the raw oracle) agrees.
        """
        composite_yaml_path = (
            self.ac_root / "test-component" / f"{self.composite_id}.yaml"
        )

        violations = check_changed_done_acs(
            [composite_yaml_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        violation_ids = [v["ac_id"] for v in violations]
        self.assertNotIn(
            self.composite_id,
            violation_ids,
            "check_changed_done_acs must NOT report the composite as a "
            "violation when its children are each covered by a passing "
            f"test. Got violations: {violations}",
        )


# ---------------------------------------------------------------------------
# Test 2 — BO-2500a-6: a done leaf without its own test still fails
# (anti-over-broadening guard)
# ---------------------------------------------------------------------------


class TestDoneLeafWithoutTestStillFails(unittest.TestCase):
    """BO-2500a-6: the composite exemption must NOT weaken the leaf path — a
    done leaf AC (empty covered_by) with no covers-tagged test must still be
    ineligible."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.leaf_id = "BO-TEST-LEAF-NOTEST-1"
        # A LEAF: done, empty covered_by, and NO covers-tagged test anywhere.
        _write_ac(
            self.ac_root,
            self.leaf_id,
            status="active",
            work_status="done",
            level="L2",
            covered_by=[],
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_done_leaf_without_test_still_fails(self) -> None:
        # covers: BO-2500a-6
        """A done LEAF AC (no children, empty covered_by) with no covers-
        tagged test of its own must remain eligible=False.

        This is the anti-over-broadening guard named in the ticket: whatever
        composite-exemption logic python-coder adds for BO-2500a-6 must be
        gated strictly on a non-empty `covered_by` (data-driven, never a
        hard-coded AC-id allowlist per the Implementation Notes) so this
        leaf path is left exactly as strict as it is today.
        """
        verdict = verify_done_eligible(
            self.leaf_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "A done LEAF AC with no covers-tagged test must remain "
            f"ineligible for done. Got verdict: {verdict}",
        )
        self.assertIn(
            self.leaf_id,
            verdict.get("reason", ""),
            "The ineligibility reason must name the leaf AC id so the "
            f"failure is diagnosable. Got verdict: {verdict}",
        )

    def test_leaf_check_via_ci_changed_wrapper_still_reports_violation(
        self,
    ) -> None:
        # covers: BO-2500a-6
        """The real CI-changed wrapper must still flag an untested leaf as a
        violation — the composite exemption must not leak into the wrapper
        path either.
        """
        leaf_yaml_path = self.ac_root / "test-component" / f"{self.leaf_id}.yaml"

        violations = check_changed_done_acs(
            [leaf_yaml_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        violation_ids = [v["ac_id"] for v in violations]
        self.assertIn(
            self.leaf_id,
            violation_ids,
            "check_changed_done_acs must still report a done leaf AC with "
            f"no covers-tagged test as a violation. Got violations: {violations}",
        )


# ---------------------------------------------------------------------------
# Test 3 — BO-2500a-6-i: a non-coverage edit to a done composite (adding a
# child id to covered_by) must not trip the CI-changed gate
# ---------------------------------------------------------------------------


class TestNoncoverageEditOfDoneCompositeDoesNotTripCheck(unittest.TestCase):
    """BO-2500a-6-i: reproduces the live PR #414 / ACD-400a shape — editing
    only `covered_by` on an already-done composite must not trip the
    required CI-changed proof-of-done gate."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

        self.composite_id = "ACD-TEST-400a"
        self.existing_child_id = "ACD-TEST-400a-1"
        self.newly_added_child_id = "ACD-TEST-400a-2"

        # Pre-edit state: composite already done, already has ONE covered
        # child (mirrors ACD-400a's pre-PR-414 covered_by: [ACD-400a-1]).
        # Then the PR-under-test appends a second child id — a pure
        # covered_by edit, exactly like PR #414's diff on ACD-400a.
        _write_ac(
            self.ac_root,
            self.composite_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[self.existing_child_id, self.newly_added_child_id],
        )
        _write_ac(
            self.ac_root,
            self.existing_child_id,
            status="active",
            work_status="done",
            level="L2",
        )
        # The newly-added child is itself done and covered by a passing
        # test — a real change adds the child's own test alongside the
        # covered_by edit, it does not merely reference an untested id.
        _write_ac(
            self.ac_root,
            self.newly_added_child_id,
            status="active",
            work_status="done",
            level="L2",
        )
        _write_test_file(
            self.test_root,
            "test_acd_400a_children_coverage.py",
            f"""\
            def test_covers_existing_child():
                # covers: {self.existing_child_id}
                pass  # genuinely passes

            def test_covers_newly_added_child():
                # covers: {self.newly_added_child_id}
                pass  # genuinely passes
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_noncoverage_edit_of_done_composite_does_not_trip_check(self) -> None:
        # covers: BO-2500a-6-i
        """Only the composite's YAML path is in the PR diff (changed_yaml_
        paths) — exactly like PR #414, which touched only ACD-400a.yaml, not
        any child yaml or test file. Running check_changed_done_acs (the
        function `--mode ci-changed`, the required CI gate, actually calls)
        with only that one changed path reproduces the live failure mode.

        RED today: verify_done_eligible still requires a direct linked test
        for `self.composite_id` itself, so check_changed_done_acs reports
        {{"ac_id": "ACD-TEST-400a", "reason": "no linked test found for
        ACD-TEST-400a"}} — the exact shape of the live PR #414 failure
        "[check-done-proof] ACD-400a: no linked test found for ACD-400a".

        To make this green, the composite exemption from BO-2500a-6 must
        also hold when only the composite's own YAML (not its children's)
        appears in the diff — i.e. the fix must live in verify_done_eligible
        itself (or a helper it calls), not be scoped to "only check
        composites whose children also changed".
        """
        composite_yaml_path = (
            self.ac_root / "test-component" / f"{self.composite_id}.yaml"
        )

        # Only the composite's own yaml is "changed" — mirrors PR #414's
        # diff, which touched only the parent's covered_by field.
        violations = check_changed_done_acs(
            [composite_yaml_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        violation_ids = [v["ac_id"] for v in violations]
        self.assertNotIn(
            self.composite_id,
            violation_ids,
            "check_changed_done_acs must NOT report a violation for a done "
            "composite whose covered_by gained a new (itself-covered) child "
            "id — this is the exact PR #414 / ACD-400a live-failure shape. "
            f"Got violations: {violations}",
        )


# ---------------------------------------------------------------------------
# Test 4 — BO-2500a-6 remediation M-1: fail-closed edge-case regression guards
# ---------------------------------------------------------------------------


class TestCompositeFailClosedEdgeCases(unittest.TestCase):
    """BO-2500a-6 remediation M-1: locks in fail-closed behaviour for
    malformed/edge-case ``covered_by`` shapes that the composite path was
    hand-verified against but previously had no regression test for — a
    self-reference, a two-node cycle, a genuinely uncovered child, a nested
    composite, and (M-2) a legacy ``covered_by`` holding test-file paths."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_covered_by_self_reference_is_not_eligible(self) -> None:
        # covers: BO-2500a-6
        """An AC whose ``covered_by`` lists its own id must not be eligible.

        A self-reference can never be genuinely "covered" — it resolves to
        zero real leaf descendants once the cycle guard in
        ``_resolve_all_child_ids`` prevents it from expanding itself, so the
        composite path must fail closed with "no coverable children"
        rather than looping or (worse) treating the self-id as its own
        satisfied leaf.
        """
        self_ref_id = "BO-TEST-SELFREF-1"
        _write_ac(
            self.ac_root,
            self_ref_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[self_ref_id],
        )

        verdict = verify_done_eligible(
            self_ref_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "A covered_by self-reference must not be eligible for done — "
            f"it can never resolve to a real covered leaf. Got: {verdict}",
        )

    def test_covered_by_two_node_cycle_is_not_eligible_and_terminates(self) -> None:
        # covers: BO-2500a-6
        """A two-node ``covered_by`` cycle (A -> B -> A) must not be eligible
        and must terminate (no infinite recursion).

        The test itself is the termination proof: if the cycle guard in
        ``_resolve_all_child_ids`` were broken, this call would recurse
        forever and the test process would hang/timeout rather than return
        a verdict.
        """
        a_id = "BO-TEST-CYCLE-A"
        b_id = "BO-TEST-CYCLE-B"
        _write_ac(
            self.ac_root,
            a_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[b_id],
        )
        _write_ac(
            self.ac_root,
            b_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[a_id],
        )

        verdict = verify_done_eligible(
            a_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            f"A two-node covered_by cycle must not be eligible. Got: {verdict}",
        )

    def test_composite_with_genuinely_uncovered_child_is_not_eligible(self) -> None:
        # covers: BO-2500a-6
        """A composite whose real child has zero linked tests must not be eligible.

        This is the no-false-pass guard for the ordinary (non-cyclic,
        non-legacy) composite path: an actual AC-id child that nobody has
        written a covers-tagged test for must block the parent's
        eligibility, naming the uncovered child in the reason.
        """
        composite_id = "BO-TEST-UNCOV-PARENT"
        child_id = "BO-TEST-UNCOV-CHILD"
        _write_ac(
            self.ac_root,
            composite_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[child_id],
        )
        _write_ac(
            self.ac_root,
            child_id,
            status="active",
            work_status="done",
            level="L2",
            covered_by=[],
        )
        # Deliberately no test file anywhere — child_id has zero linked tests.

        verdict = verify_done_eligible(
            composite_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            f"A composite with a genuinely uncovered child must not be eligible. Got: {verdict}",
        )
        self.assertIn(
            child_id,
            verdict.get("reason", ""),
            f"The reason must name the uncovered child id. Got: {verdict}",
        )

    def test_nested_composite_with_covered_grandchildren_is_eligible(self) -> None:
        # covers: BO-2500a-6
        """A nested composite (child is itself a composite) whose grandchildren
        are covered by passing tests must be eligible.

        Chosen semantics and reasoning: an intermediate composite child is
        transparent structural grouping, not a leaf requiring its own direct
        test. ``_resolve_all_child_ids`` is documented to expand a
        non-leaf child recursively down to real leaf descendants — matching
        how the AC store actually nests L1 composites over L2/L3 leaves via
        multi-level ``covered_by`` chains. Requiring every intermediate
        composite level to *also* carry its own direct covers-tagged test
        would defeat the whole point of the composite exemption (composites
        are proved by their leaves, at any depth) and would regress every
        multi-level composite in the store back to the pre-BO-2500a-6
        false-failure mode. So: eligible=True is correct here, derived
        transitively from the two real leaf grandchildren's passing tests.
        """
        top_id = "BO-TEST-NESTED-TOP"
        mid_id = "BO-TEST-NESTED-MID"
        leaf_a_id = "BO-TEST-NESTED-LEAF-A"
        leaf_b_id = "BO-TEST-NESTED-LEAF-B"
        _write_ac(
            self.ac_root,
            top_id,
            status="active",
            work_status="done",
            level="L0",
            covered_by=[mid_id],
        )
        _write_ac(
            self.ac_root,
            mid_id,
            status="active",
            work_status="done",
            level="L1",
            covered_by=[leaf_a_id, leaf_b_id],
        )
        _write_ac(
            self.ac_root,
            leaf_a_id,
            status="active",
            work_status="done",
            level="L2",
            covered_by=[],
        )
        _write_ac(
            self.ac_root,
            leaf_b_id,
            status="active",
            work_status="done",
            level="L2",
            covered_by=[],
        )
        _write_test_file(
            self.test_root,
            "test_nested_composite_grandchildren.py",
            f"""\
            def test_covers_nested_leaf_a():
                # covers: {leaf_a_id}
                pass  # genuinely passes

            def test_covers_nested_leaf_b():
                # covers: {leaf_b_id}
                pass  # genuinely passes
            """,
        )

        verdict = verify_done_eligible(
            top_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(
            verdict["eligible"],
            "A nested composite whose grandchildren are each covered by a "
            f"passing test must be eligible. Got: {verdict}",
        )
        self.assertEqual(verdict.get("reason", ""), "")

    def test_legacy_covered_by_test_file_paths_treated_as_leaf(self) -> None:
        # covers: BO-2500a-6
        """BO-2500a-6 remediation M-2: a legacy ``covered_by`` holding test-file
        paths (predating the child-id convention) must be classified as a
        LEAF, not misdiagnosed as a composite with "uncovered children".

        ~410 done ACs in the real store have this shape (e.g.
        ``covered_by: ['tests/test_skill_registry.py']``). None of those
        entries resolve to a real AC record, so the AC must fall back to the
        original leaf message rather than the misleading composite one.
        """
        legacy_id = "BO-TEST-LEGACY-PATH-AC"
        _write_ac(
            self.ac_root,
            legacy_id,
            status="active",
            work_status="done",
            level="L2",
            covered_by=["tests/test_skill_registry.py"],
        )
        # Deliberately no covers-tagged test anywhere for legacy_id.

        verdict = verify_done_eligible(
            legacy_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(verdict["eligible"])
        self.assertEqual(
            verdict.get("reason", ""),
            f"no linked test found for {legacy_id}",
            "A covered_by whose entries are all unresolvable (legacy "
            "test-file paths) must fall back to the original leaf message, "
            f"not a misleading 'uncovered children' composite message. Got: {verdict}",
        )
        self.assertNotIn(
            "uncovered children",
            verdict.get("reason", ""),
            "The legacy test-file-path shape must not be misdiagnosed as a "
            f"composite with uncovered children. Got: {verdict}",
        )


if __name__ == "__main__":
    unittest.main()
