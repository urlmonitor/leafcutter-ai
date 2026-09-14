"""
MODULE: test_uxp_700d_1
GOAL: AC UXP-700d-1 -- "Example artifacts live under their own product root and never
    appear in a project's own record." A predicate that decides, for the
    product-truth store (docs/product-truth/{flows,mock-data,mockups}/<product>/...),
    which artifacts belong to the project's own record and which belong to an
    example product (fern-and-fig), MUST:
      AC-1: never return an example artifact when the project's own record is
            enumerated;
      AC-2: still return the example product's artifacts when that product is
            asked for BY NAME (separation, not deletion -- ADR-022);
      AC-3: decide ownership from the product-root path/id segment an artifact
            lives under, never from anything inside its content, so an artifact
            cannot be moved between products by an edit to its content.
BUSINESS CONTEXT: Every artifact id in docs/product-truth/index.json is already
    shaped `<product>/<name>` (e.g. "fern-and-fig/customer-buys-a-plant",
    "leafcutter/ac-lifecycle") -- the product root is the first path segment of
    the id (and the second segment of the on-disk `path`, e.g.
    "flows/fern-and-fig/customer-buys-a-plant.flow.json"). "leafcutter" is the
    project's own product root (mirrors the pre-existing convention in
    scripts/ac_store/scan_ac_store.py's `_PROJECT_PRODUCT`); every other product
    root -- today only "fern-and-fig" -- is example content. VERIFIED against the
    real, checked-in index.json (2026-09-09): 11 leafcutter flows + 3 fern-and-fig
    flows, 1 fern-and-fig mock_data (zero leafcutter), 9 fern-and-fig mockups
    (zero leafcutter). Per the AC's delivers_to contract this predicate is meant
    to be reused verbatim by UXP-700d-2 (work store) and UXP-700d-4 (per-type
    population counts) -- it MUST be a single, pure, importable function, not a
    re-derivation each caller repeats.
ARCHITECTURE: No production module implements this predicate yet (confirmed by
    research: grep across scripts/ and docs/product-truth/scripts/ found no
    product-root ownership helper for the product-truth store -- only the
    unrelated, CONTENT-based `_is_example_content` in scan_ac_store.py, which
    decides from an AC's `product:` YAML field and is explicitly the wrong shape
    for this AC's ownership-by-location clause). This test file pins the
    contract for a NEW small module, docs/product-truth/scripts/product_ownership.py,
    holding:
      PROJECT_PRODUCT: str                          -- "leafcutter"
      product_of_artifact_id(artifact_id) -> str    -- pure: id -> product root
      is_example_artifact_id(artifact_id) -> bool    -- product root != PROJECT_PRODUCT
      own_record_artifacts(artifacts) -> list[dict]  -- filters index artifacts[]
      artifacts_for_product(artifacts, product) -> list[dict]
      main(argv) -- a CLI: with no args, prints the project's own record (one id
        per stdout line); with --product <name>, prints that product's artifacts
        by name. This is the reachability angle's real entry point -- the AC
        authored no test_spec entry point, so one had to be resolved (see the
        REACHABILITY ENTRY-POINT RESOLUTION note below) rather than reusing
        generate_product_truth.py / validate_product_truth.py's existing CLIs,
        whose own enumeration behaviour is explicitly out of this AC's scope
        (UXP-700d-4 is the ticket that wires per-type reporting into a checker).

    TestOwnRecordExcludesExamples / TestExampleProductByName exercise the pure
    functions directly against the REAL, checked-in docs/product-truth/index.json
    (never a hand-typed literal -- Fixture Authenticity Rule) -- covers the
    criterion angle for AC-1 and AC-2.
    TestOwnershipDecidedByRootNotContent (angle: seam) takes REAL artifact
    records from that same real index.json, and pipes copies that differ ONLY in
    non-id content (or ONLY in id) into the real predicate, proving the decision
    tracks the id/path segment and is blind to content -- AC-3.
    TestUxp700d1ReachableFromEntryPoint (angle: reachability) runs the real
    product_ownership.py CLI as a subprocess against the real store.

REACHABILITY ENTRY-POINT RESOLUTION (recorded per the test-writer skill's
    procedure): the AC's test_spec authored no entry point for the reachability
    row ("the entry point is not declared: resolve it before writing this
    test"). Checked in order against the real code: (1) CLI script -- no
    existing script exposes this predicate as its behaviour today (checked
    generate_product_truth.py and validate_product_truth.py: both have real
    main()/argparse CLIs, but neither's current behaviour is gated on this
    predicate, and wiring it into either would either duplicate UXP-700d-4's own
    scope (per-type reporting) or invent an untracked side-effect on a script
    this ticket does not own). (2)-(4) pre-commit hook / slash command / workflow
    dispatch: none apply -- this is a pure library predicate, not a repo-quality
    gate, prompt-facing command, or workflow step. (5) main(argv): applies, and
    is the entry point the module ITSELF must expose for this AC's own
    "enumerated" / "asked for by name" clauses to have any caller at all --
    resolved to a small CLI on the new module (`python
    docs/product-truth/scripts/product_ownership.py` and `... --product
    fern-and-fig`), invoked via subprocess (not by importing and calling main()
    in-process) so the test proves the actual command line a human or CI would
    run. See this ticket's sign-off comment for the completion_manifest.
    reachability_entry_point_answer record.

NOTE ON RED BASELINE: docs/product-truth/scripts/product_ownership.py does not
    exist yet, so every test below fails on import with ModuleNotFoundError, and
    the reachability test additionally fails because the script path does not
    exist (subprocess non-zero exit / FileNotFoundError-shaped failure).
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

# NOT wrapped in try/except: the module does not exist yet. This import
# failure IS the red baseline for every test in this file (ModuleNotFoundError),
# which is the correct, honest red state per the test-writer skill.
import product_ownership as po  # noqa: E402


def _load_real_index_artifacts() -> list[dict]:
    """Load the REAL, checked-in index.json artifacts[] list.

    Fixture Authenticity Rule: this is the actual on-disk artifact the
    product-truth generator wrote, read verbatim -- never a hand-typed literal
    standing in for it.
    """
    with _REAL_INDEX_PATH.open(encoding="utf-8") as f:
        index = json.load(f)
    return index["artifacts"]


class TestOwnRecordExcludesExamples(unittest.TestCase):
    """AC-1: none of the example product's artifacts is returned."""

    def setUp(self) -> None:
        self.artifacts = _load_real_index_artifacts()

    def test_projects_own_record_excludes_every_example_artifact(self) -> None:
        # covers: UXP-700d-1
        # angle: criterion
        # AC-1: none of the example product's artifacts is returned.
        own_record = po.own_record_artifacts(self.artifacts)
        self.assertTrue(own_record, "expected at least one project-owned artifact in the real store")
        example_ids = [a["id"] for a in own_record if a["id"].split("/", 1)[0] == "fern-and-fig"]
        self.assertEqual(
            example_ids,
            [],
            f"the project's own record must contain zero fern-and-fig artifacts, found: {example_ids}",
        )
        # Every id returned must genuinely be under the project's own root.
        for artifact in own_record:
            self.assertEqual(artifact["id"].split("/", 1)[0], po.PROJECT_PRODUCT)


class TestExampleProductByName(unittest.TestCase):
    """AC-2: the example product's artifacts are still returned when asked for by name."""

    def setUp(self) -> None:
        self.artifacts = _load_real_index_artifacts()

    def test_example_product_remains_enumerable_by_name(self) -> None:
        # covers: UXP-700d-1
        # angle: criterion
        # AC-2: asking for the example product by name still returns its
        # journeys, datasets and screens -- separation is not achieved by
        # deletion (ADR-022).
        fern_artifacts = po.artifacts_for_product(self.artifacts, "fern-and-fig")
        fern_ids = {a["id"] for a in fern_artifacts}
        # Known real members from the checked-in store, spanning all three
        # artifact types, so this cannot pass by only keeping flows.
        self.assertIn("fern-and-fig/customer-buys-a-plant", fern_ids)
        self.assertIn("fern-and-fig/catalog", fern_ids)
        self.assertIn("fern-and-fig/plant-listing", fern_ids)
        for artifact in fern_artifacts:
            self.assertEqual(artifact["id"].split("/", 1)[0], "fern-and-fig")


class TestOwnershipDecidedByRootNotContent(unittest.TestCase):
    """AC-3: ownership is decided by product root, never by content."""

    def setUp(self) -> None:
        self.artifacts = _load_real_index_artifacts()
        by_id = {a["id"]: a for a in self.artifacts}
        # Real producer output (the checked-in index.json), one project-owned
        # record and one example record -- piped into the real consumer below.
        self.real_own_artifact = by_id["leafcutter/ac-lifecycle"]
        self.real_example_artifact = by_id["fern-and-fig/customer-buys-a-plant"]

    def test_ownership_is_decided_by_product_root_not_by_content(self) -> None:
        # covers: UXP-700d-1
        # angle: seam
        # AC-3: editing an example artifact's content does not move it into the
        # project's record, and editing a project artifact's content does not
        # move it out -- because ownership is decided by the id/path's
        # product-root segment, never by anything inside the record.
        self.assertFalse(po.is_example_artifact_id(self.real_own_artifact["id"]))
        self.assertTrue(po.is_example_artifact_id(self.real_example_artifact["id"]))

        # Mutate every piece of CONTENT on copies -- title, summary, tags,
        # component, entities -- while leaving the id (the product-root
        # segment) untouched. Classification must not move.
        mutated_own = copy.deepcopy(self.real_own_artifact)
        mutated_own["title"] = "Buy plants at the example shop"
        mutated_own["summary"] = "This looks exactly like fern-and-fig content now"
        mutated_own["component"] = "fern-and-fig-lookalike"
        mutated_own["tags"] = ["fern-and-fig", "plant", "checkout"]
        self.assertFalse(
            po.is_example_artifact_id(mutated_own["id"]),
            "rewriting an owned artifact's content to look like example content must not "
            "move it out of the project's record -- only its id/path decides ownership",
        )

        mutated_example = copy.deepcopy(self.real_example_artifact)
        mutated_example["title"] = "How ACs are built (leafcutter internals)"
        mutated_example["summary"] = "This looks exactly like project content now"
        mutated_example["component"] = "ac-driven-dev"
        mutated_example["tags"] = ["leafcutter", "internal", "tooling"]
        self.assertTrue(
            po.is_example_artifact_id(mutated_example["id"]),
            "rewriting an example artifact's content to look like project content must not "
            "move it into the project's record -- only its id/path decides ownership",
        )

        # The converse: two records with IDENTICAL content but DIFFERENT
        # product-root ids must be classified differently. This is the part a
        # hardcoded name-list (rather than a real root-derived predicate) would
        # fail, since a name list has no notion of "same content, different
        # root" at all -- it only ever sees the id it was told about.
        shared_content = {
            "type": "flow",
            "title": "Identical content, different roots",
            "summary": "same summary",
            "component": "ux-prototyping",
        }
        as_own = {**shared_content, "id": "leafcutter/synthetic-twin"}
        as_example = {**shared_content, "id": "fern-and-fig/synthetic-twin"}
        self.assertFalse(po.is_example_artifact_id(as_own["id"]))
        self.assertTrue(po.is_example_artifact_id(as_example["id"]))


class TestUxp700d1ReachableFromEntryPoint(unittest.TestCase):
    """Reachability: invoke the real product_ownership.py CLI as a subprocess."""

    def test_uxp_700d_1_reachable_from_entry_point(self) -> None:
        # covers: UXP-700d-1
        # angle: reachability
        # Invokes the REAL CLI entry point via subprocess against the REAL,
        # checked-in product-truth store. Deliberately does NOT import
        # product_ownership and call a function directly -- that would only
        # prove the predicate, not that any real caller can reach it.
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
            f"own-record CLI run failed: stdout={own_record_run.stdout!r} stderr={own_record_run.stderr!r}",
        )
        own_ids = [line.strip() for line in own_record_run.stdout.splitlines() if line.strip()]
        self.assertTrue(own_ids, "expected the CLI to print at least one project-owned artifact id")
        self.assertTrue(
            all(not artifact_id.startswith("fern-and-fig/") for artifact_id in own_ids),
            f"CLI's own-record output must contain no fern-and-fig ids, got: {own_ids}",
        )
        self.assertTrue(
            all(artifact_id.startswith("leafcutter/") for artifact_id in own_ids),
            f"CLI's own-record output must contain only leafcutter ids, got: {own_ids}",
        )

        by_name_run = subprocess.run(
            [sys.executable, str(_REAL_ENTRY_SCRIPT), "--product", "fern-and-fig"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            by_name_run.returncode,
            0,
            f"by-name CLI run failed: stdout={by_name_run.stdout!r} stderr={by_name_run.stderr!r}",
        )
        fern_ids = [line.strip() for line in by_name_run.stdout.splitlines() if line.strip()]
        self.assertIn("fern-and-fig/customer-buys-a-plant", fern_ids)
        self.assertTrue(
            all(artifact_id.startswith("fern-and-fig/") for artifact_id in fern_ids),
            f"CLI's by-name output must contain only fern-and-fig ids, got: {fern_ids}",
        )


if __name__ == "__main__":
    unittest.main()
