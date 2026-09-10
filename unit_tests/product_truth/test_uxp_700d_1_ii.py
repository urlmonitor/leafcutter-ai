"""
MODULE: test_uxp_700d_1_ii
GOAL: AC UXP-700d-1-ii -- "A project's own artifact is never set aside as an
    example." A journey authored by the project itself, describing the
    project's own product, stored under the project's own product root, must
    (AC-1) be returned when the project's own record is enumerated, (AC-2) be
    ABSENT when the example product is asked for by name, and (AC-3) leave
    the stated count of artifacts set aside as example content UNCHANGED.
    This is the paired acceptable-input control for UXP-700d-1: a predicate
    that classifies every artifact as example content satisfies UXP-700d-1
    and UXP-700d-1-i completely while emptying the project's own record --
    this record is what makes that failure mode falsifiable (see the AC's own
    test_rationale).
BUSINESS CONTEXT / CONTRACT REUSE (load-bearing -- read before changing
    anything below): unit_tests/product_truth/test_uxp_700d_1.py already
    exists on disk (staged ahead of this file, from the sibling UXP-700d-1
    ticket's own test-writer phase) and pins the REAL contract this AC's
    predicate must be delivered through:
        docs/product-truth/scripts/product_ownership.py, holding
          PROJECT_PRODUCT: str = "leafcutter"
          product_of_artifact_id(artifact_id) -> str
          is_example_artifact_id(artifact_id) -> bool
          own_record_artifacts(artifacts) -> list[dict]
          artifacts_for_product(artifacts, product) -> list[dict]
          main(argv) -- CLI: no args prints the project's own record (one id
            per stdout line); --product <name> prints that product's
            artifacts by name.
    This file deliberately does NOT invent a second, competing shape (e.g. a
    new derived index.json field) -- UXP-700d-1 delivers this predicate to
    UXP-700d-2/-3/-4 as a single reusable module per its own delivers_to
    contract, and python-coder must satisfy both this ticket and UXP-700d-1
    with ONE implementation. Reusing the sibling's already-pinned contract is
    the only way this ticket's tests and UXP-700d-1's tests agree on what
    "done" looks like.
ARCHITECTURE: Same two fixture styles test_uxp_700d_1.py already establishes:
      - TestProjectOwnedJourneyAcceptableInput calls the pure
        product_ownership functions in-process against the REAL, checked-in
        docs/product-truth/index.json (Fixture Authenticity Rule -- never a
        hand-typed literal standing in for it).
      - test_uxp_700d_1_ii_reachable_from_entry_point subprocesses the REAL
        product_ownership.py CLI against the real, checked-in store.
    "A journey authored by the project itself" (the AC's Given clause) is
    satisfied two ways in this file, deliberately: (1) an artifact that
    ALREADY exists in the real store under the project's own root
    ("leafcutter/ac-lifecycle") -- proving the predicate handles today's real
    data, not just a contrived case; and (2) one freshly-appended synthetic
    "leafcutter/..." artifact layered on top of the real list -- proving the
    "not counted among the example set-aside" clause for an artifact that is
    genuinely NEW, matching the AC's own framing ("a journey authored ... " is
    forward-looking, closer to "added" than "already present").
NOTE ON RED BASELINE: docs/product-truth/scripts/product_ownership.py does
    not exist yet (confirmed: test_uxp_700d_1.py's own note, and this file's
    own import below), so every test in this file fails on import with
    ModuleNotFoundError -- the same, correct, honest red state
    test_uxp_700d_1.py documents for the same reason.

AC-N MAPPING (this ticket's top-level ## Acceptance Criteria checklist -- no
    ## AC Coverage table and no ### test-writer subsection exist in this
    ticket body [only "### Expects From"], so per the Contract-Aware Mode
    global-AC-list fallback this note is the record of the mapping):
    AC-1 (that journey is returned)                    -> test_projects_own_journey_is_returned_by_the_projects_record
    AC-2 (absent when example asked for by name)        -> test_projects_own_journey_is_returned_by_the_projects_record,
                                                            test_uxp_700d_1_ii_reachable_from_entry_point
    AC-3 (not counted among example set-aside content)  -> test_projects_own_journey_is_not_counted_as_example_content
    All three ACs are additionally exercised end-to-end through the real CLI
    entry point by test_uxp_700d_1_ii_reachable_from_entry_point.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PRODUCT_TRUTH_DIR = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PRODUCT_TRUTH_DIR / "scripts"
_REAL_INDEX_PATH = _PRODUCT_TRUTH_DIR / "index.json"
_REAL_ENTRY_SCRIPT = _SCRIPTS_DIR / "product_ownership.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# NOT wrapped in try/except: the module does not exist yet (see
# test_uxp_700d_1.py's own identical note). This import failure IS the red
# baseline for every test in this file (ModuleNotFoundError) -- the correct,
# honest red state per the test-writer skill.
import product_ownership as po  # noqa: E402

# Both product roots the real, checked-in store already uses today -- not
# synthetic test placeholders (see test_uxp_700d_1.py's BUSINESS CONTEXT).
_KNOWN_OWN_JOURNEY_ID = "leafcutter/ac-lifecycle"
_EXAMPLE_PRODUCT = "fern-and-fig"


def _load_real_index_artifacts() -> list[dict]:
    """Load the REAL, checked-in index.json artifacts[] list.

    Fixture Authenticity Rule: this is the actual on-disk artifact the
    product-truth generator wrote, read verbatim -- never a hand-typed
    literal standing in for it. Mirrors test_uxp_700d_1.py's own helper of
    the same name exactly, so both files' fixtures cannot silently drift
    apart from each other.
    """
    with _REAL_INDEX_PATH.open(encoding="utf-8") as f:
        index = json.load(f)
    return index["artifacts"]


class TestProjectOwnedJourneyAcceptableInput(unittest.TestCase):
    """The paired acceptable-input control for UXP-700d-1 (UXP-700d-1-ii)."""

    def setUp(self) -> None:
        self.artifacts = _load_real_index_artifacts()

    def test_projects_own_journey_is_returned_by_the_projects_record(self) -> None:
        # covers: UXP-700d-1-ii
        # angle: criterion
        # AC-1: a journey under the project's own product root is returned
        # when the project's own record is enumerated.
        # AC-2: that same journey is absent when the example product is
        # asked for by name.
        own_record = po.own_record_artifacts(self.artifacts)
        own_ids = {artifact["id"] for artifact in own_record}
        self.assertIn(
            _KNOWN_OWN_JOURNEY_ID,
            own_ids,
            f"a journey authored under the project's own product root must be "
            f"returned when the project's own record is enumerated. own_ids={sorted(own_ids)!r}",
        )

        example_by_name = po.artifacts_for_product(self.artifacts, _EXAMPLE_PRODUCT)
        example_ids = {artifact["id"] for artifact in example_by_name}
        self.assertNotIn(
            _KNOWN_OWN_JOURNEY_ID,
            example_ids,
            "the project's own journey must be absent when the example product "
            f"is asked for by name. example_ids={sorted(example_ids)!r}",
        )

    def test_projects_own_journey_is_not_counted_as_example_content(self) -> None:
        # covers: UXP-700d-1-ii
        # angle: boundary
        # AC-3: the stated count of artifacts set aside as example content is
        # UNCHANGED by adding a project-owned journey -- the paired,
        # opposite-direction control to UXP-700d-1-i's "count rises by one
        # when an EXAMPLE artifact is added".
        #
        # Guards against a vacuous pass: asserts the example count is
        # non-zero BEFORE the addition, so an implementation that always
        # reports zero example artifacts (or is otherwise a no-op) cannot
        # slide through on 0 == 0.
        artifacts_before = copy.deepcopy(self.artifacts)
        example_count_before = len(po.artifacts_for_product(artifacts_before, _EXAMPLE_PRODUCT))
        self.assertGreater(
            example_count_before,
            0,
            "sanity baseline: the real store must already contain example "
            "artifacts, or this test cannot prove the count stays unchanged.",
        )

        new_own_journey = {
            "id": "leafcutter/synthetic-added-journey-for-uxp-700d-1-ii",
            "type": "flow",
            "component": "ux-prototyping",
            "status": "active",
            "readiness": "draft",
            "version": 1,
        }
        artifacts_after = artifacts_before + [new_own_journey]
        example_count_after = len(po.artifacts_for_product(artifacts_after, _EXAMPLE_PRODUCT))

        self.assertEqual(
            example_count_after,
            example_count_before,
            "the count of artifacts set aside as example content must be "
            f"unchanged by adding a project-owned journey. before="
            f"{example_count_before} after={example_count_after}",
        )

        own_ids_after = {artifact["id"] for artifact in po.own_record_artifacts(artifacts_after)}
        self.assertIn(
            new_own_journey["id"],
            own_ids_after,
            "the newly added project-owned journey must itself be recognised "
            f"as part of the project's own record. own_ids_after={sorted(own_ids_after)!r}",
        )

    def test_uxp_700d_1_ii_reachable_from_entry_point(self) -> None:
        # covers: UXP-700d-1-ii
        # angle: reachability
        # REQUIRED: invoke the real production entry point as a subprocess
        # and assert the new behaviour actually occurs. Do NOT satisfy this
        # by importing product_ownership and calling its functions directly
        # (that is what the two tests above already do, deliberately, for
        # the criterion/boundary angles).
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python docs/product-truth/scripts/product_ownership.py
        #     [--product <name>] (CLI via subprocess; main(argv) -- Reachability
        #     Entry-Point Resolution Step 1, category 5). Copied through from the
        #     sibling UXP-700d-1 ticket's own test-writer resolution (see
        #     unit_tests/product_truth/test_uxp_700d_1.py's REACHABILITY
        #     ENTRY-POINT RESOLUTION note): this ticket exercises the same real
        #     module's same CLI, so re-deriving a second entry point for the
        #     same production surface would only risk disagreeing with the
        #     sibling's own resolution, not add information.
        """Runs the REAL product_ownership.py CLI (no fixture-specific
        patching -- exercises the actual, checked-in docs/product-truth/
        store) and asserts the project's own journey is present in the
        own-record output and absent from the example-product-by-name output.
        """
        own_record_run = subprocess.run(
            [sys.executable, str(_REAL_ENTRY_SCRIPT)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            own_record_run.returncode,
            0,
            f"own-record CLI run failed: stdout={own_record_run.stdout!r} "
            f"stderr={own_record_run.stderr!r}",
        )
        own_ids = [line.strip() for line in own_record_run.stdout.splitlines() if line.strip()]
        self.assertIn(
            _KNOWN_OWN_JOURNEY_ID,
            own_ids,
            f"the project's own journey must be returned by the real CLI's "
            f"own-record enumeration. own_ids={own_ids!r}",
        )

        by_name_run = subprocess.run(
            [sys.executable, str(_REAL_ENTRY_SCRIPT), "--product", _EXAMPLE_PRODUCT],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            by_name_run.returncode,
            0,
            f"by-name CLI run failed: stdout={by_name_run.stdout!r} "
            f"stderr={by_name_run.stderr!r}",
        )
        fern_ids = [line.strip() for line in by_name_run.stdout.splitlines() if line.strip()]
        self.assertNotIn(
            _KNOWN_OWN_JOURNEY_ID,
            fern_ids,
            "the project's own journey must be absent from the real CLI's "
            f"example-product-by-name output. fern_ids={fern_ids!r}",
        )


if __name__ == "__main__":
    unittest.main()
