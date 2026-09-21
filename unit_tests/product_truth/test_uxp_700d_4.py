"""
MODULE: test_uxp_700d_4
GOAL: AC UXP-700d-4 -- "An artifact type whose whole population is example
    content is reported." Given a project whose record holds at least one
    artifact of a given type, when the record is checked, the check MUST:
      AC-1: state, for EACH artifact type, how many artifacts of that type
            belong to the project and how many belong to the example
            product;
      AC-2: report, BY NAME, any artifact type whose project count is zero
            while its example count is not (example-only);
      AC-3: never count an example artifact as satisfying that type for the
            project (the project/example split must be exhaustive and
            disjoint -- an example artifact can never leak into the project
            figure);
      AC-4: report a type whose project AND example counts are BOTH zero as
            EMPTY, not as example-only -- the both-zero case is a distinct
            outcome from the project-zero/example-nonzero case AC-2 names.
BUSINESS CONTEXT: This is the check that would have caught the CURRENT,
    VERIFIED state of the real, checked-in store (confirmed by direct
    execution against docs/product-truth/index.json, 2026-09-16): of the
    store's 3 artifact types, "mockups" (10/10) and "mock-data" (2/2) are
    ENTIRELY fern-and-fig (example) content -- zero project mockups, zero
    project mock-data exist anywhere in the record -- while "flows" is mixed
    (11 project, 3 example). A reader looking at a populated mockups/
    directory today would wrongly conclude the product is documented; this
    AC is the machine-readable check that surfaces that gap instead of
    hiding it. The both-zero clause (AC-4) exists because the obvious
    implementation (report "example-only" whenever project==0) would
    misclassify a genuinely EMPTY type -- one authored with nothing at all,
    project or example -- as example-only, which is a false claim that
    example content exists when it does not.
ARCHITECTURE: Builds directly on UXP-700d-1's product_ownership.py predicate
    (PROJECT_PRODUCT / is_example_artifact_id), per that AC's own
    delivers_to contract ("meant to be imported verbatim by ... UXP-700d-4
    for per-type population counts"). Confirmed by research (direct read of
    docs/product-truth/scripts/product_truth_outcome.py, 2026-09-16): that
    module already holds the sibling per-type check `_compute_empty_types`
    (UXP-700b-1) and is validate_product_truth.py's existing home for
    outcome-vocabulary bookkeeping -- the natural, minimal-diff home for this
    AC's own per-type project/example split rather than a new module or a
    growth of the already-ratcheted validate_product_truth.py itself. This
    test file pins the contract for TWO new pure functions there:
      compute_type_population(flows, mocks, mockups) -> dict[str, dict[str, int]]
          {"flows": {"project": int, "example": int}, "mock-data": {...},
           "mockups": {...}} -- one entry per docs/product-truth/scripts/
           product_truth_checks._ARTIFACT_TYPES member, project + example
           always summing to that type's total population (AC-1, AC-3).
      compute_example_only_types(type_population) -> list[str]
          Sorted artifact-type names whose "project" count is zero AND whose
          "example" count is NOT zero (AC-2). A type with both counts zero is
          excluded (AC-4) -- it belongs to the pre-existing `empty_types`
          vocabulary (_compute_empty_types) instead, never to this one.
    And ONE new field pair on validate_product_truth.py main()'s existing
    single machine-readable JSON stdout contract line (ADR-042; the same line
    UXP-700b-1/c-1-i extend) -- "the record is checked" from this AC's own
    Gherkin Given/When clause IS this checker run:
      "type_population": the dict compute_type_population returns.
      "example_only_types": the list compute_example_only_types returns.
    CONFIRMED RED (direct execution against the real, unmodified checker,
    2026-09-16): the current contract line carries no "type_population" and
    no "example_only_types" key at all -- see NOTE ON RED BASELINE below.

    completion_manifest.cross_layer_seam_answer:
      result: covered
      producing_side: "validate_product_truth.py main()'s stdout outcome
        payload -- the SAME producer UXP-700b-1's seam test already pins,
        now carrying this AC's two new keys"
      consuming_side: "a caller that reads payload['example_only_types'] /
        payload['type_population'] from the real CLI's real stdout (the
        TestReachability class below), not a hand-typed literal standing in
        for it"

REACHABILITY ENTRY-POINT RESOLUTION (per the test-writer skill's Step 1,
    checked in order against the real code, 2026-09-16 -- this AC's own
    test_spec authored no entry point, same unresolved state UXP-700d-1's
    own reachability row was in): (1) CLI script -- APPLIES.
    docs/product-truth/scripts/validate_product_truth.py already IS "the
    check" this AC's own Gherkin names ("When the record is checked, Then
    the check states...") -- it is a real script with `if __name__ ==
    "__main__":` guarding `main()`, and it already prints the single
    machine-readable JSON line (ADR-042) this AC's new fields extend. Wiring
    the new fields into a DIFFERENT script, or into a bare importable
    function with no CLI caller, would invent an entry point this AC's own
    wording does not describe and would duplicate work already resolved by
    UXP-700b-1's own reachability test. (2)-(4) pre-commit hook / slash
    command / workflow dispatch: none directly gate on this new field pair
    today (mirrors UXP-700b-1's own resolution -- gate-wiring is explicitly
    future/other-ticket scope); the checker's pre-existing pre-commit hook
    wiring (check-product-truth-validate) is a pure exit-code passthrough
    that does not read this field, so it is not the entry point THIS test
    needs to prove. (5) main(argv): not needed -- (1) already applies and is
    the strongest, most direct entry point available. RESOLVED to (1):
    `python docs/product-truth/scripts/validate_product_truth.py`, invoked
    via subprocess (never by importing and calling main() in-process) against
    the REAL, checked-in product-truth store, so the test proves the actual
    command line a human or CI would run.

    completion_manifest.reachability_entry_point_answer:
      result: resolved
      entry_point: "python docs/product-truth/scripts/validate_product_truth.py
        (CLI via subprocess, main() guarded by if __name__ == '__main__':) --
        the SAME entry point UXP-700b-1's own reachability test already
        resolved and proved; this test proves it again for this AC's two new
        stdout-contract fields."

NOTE ON RED BASELINE: compute_type_population and compute_example_only_types
    do not exist in product_truth_outcome.py yet, so every in-process test
    below fails on import with ImportError. The reachability (CLI subprocess)
    test does not fail on import -- the CLI itself still runs and exits 0 --
    but fails its own assertions because the real, unmodified checker's
    stdout contract line carries no "type_population" / "example_only_types"
    key yet (confirmed by direct execution above), so `payload["type_population"]`
    raises KeyError.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PRODUCT_TRUTH_DIR = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PRODUCT_TRUTH_DIR / "scripts"
_REAL_ENTRY_SCRIPT = _SCRIPTS_DIR / "validate_product_truth.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# NOT wrapped in try/except: compute_type_population / compute_example_only_types
# do not exist yet. This import failure IS the red baseline for every
# in-process test below (ImportError), which is the correct, honest red
# state per the test-writer skill.
import generate_product_truth as gpt  # noqa: E402
import product_ownership as po  # noqa: E402
import product_truth_outcome as pto  # noqa: E402
import validate_product_truth as vpt  # noqa: E402

# The artifact-type vocabulary this check must report over -- copied from the
# real store's own directory names (see product_truth_checks._ARTIFACT_TYPES,
# the same vocabulary _compute_empty_types already uses).
_ARTIFACT_TYPES = ("flows", "mock-data", "mockups")


def _load_real_populations() -> tuple[dict, dict, dict]:
    """Load the REAL, checked-in product-truth store's three artifact-type
    populations through the store's own single readers -- never a hand-typed
    literal standing in for them (Fixture Authenticity Rule). STORE/AC_STORE
    are left at their defaults (the real, on-disk docs/product-truth/), so
    this reads the actual repository record.
    """
    flows, _paths = gpt.load_flows()
    mocks = gpt.load_mocks()
    mockups = vpt.load_mockups()
    return flows, mocks, mockups


class TestExampleOnlyTypeReportedByName(unittest.TestCase):
    """AC-2 / AC-3: a type whose whole population is example content is
    reported BY NAME, and an example artifact is never counted toward the
    project figure."""

    def setUp(self) -> None:
        self.flows, self.mocks, self.mockups = _load_real_populations()

    def test_type_with_only_example_artifacts_is_reported_by_name(self) -> None:
        # covers: UXP-700d-4
        # angle: criterion
        # AC-2/AC-3: the real store's "mockups" and "mock-data" populations are
        # VERIFIED (2026-09-16, direct execution) to be entirely fern-and-fig --
        # zero project artifacts of either type exist anywhere in the record.
        # Both must be named by the check as example-only.
        self.assertTrue(self.mockups, "expected at least one mockup in the real store")
        self.assertTrue(
            all(po.is_example_artifact_id(mockup_id) for mockup_id in self.mockups),
            "test precondition drifted: the real store now has a project mockup -- "
            "update this test's fixture assumption rather than weakening the assertion",
        )

        type_population = pto.compute_type_population(self.flows, self.mocks, self.mockups)
        example_only = pto.compute_example_only_types(type_population)

        self.assertIn(
            "mockups",
            example_only,
            "a type (mockups) whose entire population is example content must be "
            f"reported by name as example-only; got example_only_types={example_only!r}",
        )
        # A type with real project artifacts (flows: 11 leafcutter journeys,
        # VERIFIED 2026-09-16) must NEVER be reported as example-only, even
        # though it also holds example content -- AC-3's disjointness.
        self.assertNotIn(
            "flows",
            example_only,
            "a type that holds AT LEAST ONE project artifact must not be reported "
            f"as example-only; got example_only_types={example_only!r}",
        )


class TestPerTypeCountsBothStated(unittest.TestCase):
    """AC-1: the check states, for each artifact type, both a project count
    and an example count, and they exhaustively partition that type's
    population (AC-3: no artifact -- project or example -- is dropped or
    double-counted)."""

    def setUp(self) -> None:
        self.flows, self.mocks, self.mockups = _load_real_populations()

    def test_per_type_project_and_example_counts_are_both_stated(self) -> None:
        # covers: UXP-700d-4
        # angle: criterion
        type_population = pto.compute_type_population(self.flows, self.mocks, self.mockups)

        self.assertEqual(
            set(type_population.keys()),
            set(_ARTIFACT_TYPES),
            "the report must carry an entry for every artifact type in the "
            f"store's own vocabulary; got keys={sorted(type_population.keys())!r}",
        )

        real_populations = {"flows": self.flows, "mock-data": self.mocks, "mockups": self.mockups}
        for artifact_type in _ARTIFACT_TYPES:
            entry = type_population[artifact_type]
            self.assertIn("project", entry, f"{artifact_type} entry missing a project count")
            self.assertIn("example", entry, f"{artifact_type} entry missing an example count")
            total_population = len(real_populations[artifact_type])
            self.assertEqual(
                entry["project"] + entry["example"],
                total_population,
                f"{artifact_type}: project ({entry['project']}) + example "
                f"({entry['example']}) must equal that type's real total population "
                f"({total_population}) -- AC-3, no artifact may be dropped or "
                "double-counted between the two figures",
            )
            # Independently re-derive the project figure straight from the
            # ownership predicate (never trusting compute_type_population's
            # own arithmetic alone) -- this is the AC-3 cross-check that an
            # example artifact was never folded into the project count.
            expected_project = sum(
                1 for artifact_id in real_populations[artifact_type] if not po.is_example_artifact_id(artifact_id)
            )
            self.assertEqual(
                entry["project"],
                expected_project,
                f"{artifact_type}: reported project count must match the count of ids "
                "whose product root is the project's own root, independently re-derived "
                "from product_ownership.is_example_artifact_id",
            )

        # Concrete, VERIFIED (2026-09-16) real-store figures for the mixed
        # type, so this test cannot pass on an implementation that reports
        # e.g. (0, 0) or a constant for every type.
        self.assertEqual(type_population["flows"]["project"], 11)
        self.assertEqual(type_population["flows"]["example"], 3)


class TestBothZeroTypeReportedEmptyNotExampleOnly(unittest.TestCase):
    """AC-4: a type for which both counts are zero is reported as empty
    rather than as example-only -- the boundary the "obvious" project==0
    implementation gets wrong."""

    def test_type_with_no_artifacts_at_all_is_reported_empty_not_example_only(self) -> None:
        # covers: UXP-700d-4
        # angle: boundary
        # A genuinely empty record: zero flows, zero mock-data, zero mockups --
        # every type's project AND example counts are both zero.
        type_population = pto.compute_type_population({}, {}, {})

        for artifact_type in _ARTIFACT_TYPES:
            entry = type_population[artifact_type]
            self.assertEqual(entry["project"], 0, f"{artifact_type}: expected zero project artifacts")
            self.assertEqual(entry["example"], 0, f"{artifact_type}: expected zero example artifacts")

        example_only = pto.compute_example_only_types(type_population)
        self.assertEqual(
            example_only,
            [],
            "a type whose project AND example counts are BOTH zero must NEVER be "
            f"reported as example-only; got example_only_types={example_only!r}",
        )

        # It belongs to the pre-existing empty_types vocabulary instead
        # (_compute_empty_types, UXP-700b-1) -- reusing the SAME "zero
        # population" figures this AC's own function computed, so the two
        # checks cannot silently disagree about which types are empty.
        empty_types = pto._compute_empty_types({}, {}, {})
        self.assertEqual(sorted(empty_types), sorted(_ARTIFACT_TYPES))
        self.assertEqual(
            set(example_only) & set(empty_types),
            set(),
            "the example-only set and the empty set must be disjoint -- a type is "
            "reported as exactly one of the two, never both",
        )


class TestExampleOnlyTypesReachableFromEntryPoint(unittest.TestCase):
    """Reachability: invoke the real validate_product_truth.py CLI as a
    subprocess against the real, checked-in store, and assert the new
    per-type fields land on its actual stdout contract line."""

    def test_uxp_700d_4_reachable_from_entry_point(self) -> None:
        # covers: UXP-700d-4
        # angle: reachability
        # Invokes the REAL CLI entry point via subprocess against the REAL,
        # checked-in product-truth store -- the same checker/store UXP-700b-1's
        # own reachability test already proves reachable, now asserting on
        # THIS AC's two new contract fields. Deliberately does NOT import
        # validate_product_truth/product_truth_outcome and call a function
        # directly -- that would only prove the pure functions, not that any
        # real caller (a human running the checker, or a future CI gate) can
        # reach this behaviour through the actual command line.
        result = subprocess.run(
            [sys.executable, str(_REAL_ENTRY_SCRIPT)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"the checker's fail-open exit-code contract must be preserved; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        json_lines = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
        self.assertTrue(json_lines, f"expected a JSON outcome line on stdout; stdout={result.stdout!r}")
        import json as _json

        payload = _json.loads(json_lines[-1])

        self.assertIn(
            "type_population",
            payload,
            f"the real CLI's stdout contract line must carry a 'type_population' key; "
            f"got keys={sorted(payload.keys())!r}",
        )
        self.assertIn(
            "example_only_types",
            payload,
            f"the real CLI's stdout contract line must carry an 'example_only_types' key; "
            f"got keys={sorted(payload.keys())!r}",
        )

        # Consumed in control flow (not merely observed as present): a real
        # caller branches on which types are example-only. VERIFIED
        # (2026-09-16) real-store fact: mockups are entirely fern-and-fig.
        self.assertIn(
            "mockups",
            payload["example_only_types"],
            "the real CLI must report 'mockups' as example-only against the real, "
            f"checked-in store; got example_only_types={payload['example_only_types']!r}",
        )
        mockups_entry = payload["type_population"]["mockups"]
        self.assertEqual(
            mockups_entry["project"],
            0,
            f"the real CLI must report zero project mockups; got {mockups_entry!r}",
        )
        self.assertGreater(
            mockups_entry["example"],
            0,
            f"the real CLI must report a nonzero example mockup count; got {mockups_entry!r}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
