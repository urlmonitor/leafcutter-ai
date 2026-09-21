"""
MODULE: test_uxp_700d_3_i
GOAL: AC UXP-700d-3-i -- "Every piece of example content carries its own example
    marker, and the project's own record carries none." A reader holding only
    one artifact's file content -- no index, no loader that already knows the
    path -- MUST be able to tell:
      AC-1: an example artifact (a fern-and-fig journey, screen, or dataset)
            declares its product via a top-level `example_product` key whose
            value is the product-root slug (`fern-and-fig`), in its OWN
            content;
      AC-2: the same key is accepted (optional, never required) by the flow,
            mockup, and mock-data schemas, and documented for acceptance
            criteria;
      AC-3: a project-owned artifact or criterion, read the same way, carries
            no `example_product` key at all -- not even an empty or null one;
      AC-4: the older `product:` field on example acceptance criteria is
            replaced by `example_product:`, so the fact has one spelling, and
            the count of example criteria set aside from the work queue
            (scripts/ac_store/scan_ac_store.py's `set_aside_count`) is
            unchanged by the rename.
BUSINESS CONTEXT: ADR-044 <docs/architecture/adrs/
    ADR-044-example-content-self-declares-its-product.md> sections 1-5 (the
    key's name, value, absence rule, schema registration, and backfill) is
    this test file's specification. UXP-700d-3-ii (a separate AC, a separate
    ticket) owns the disagreement-reporting checker (ADR-044 sections 6-7)
    and is NOT covered here -- that AC's own test file
    (unit_tests/product_truth/test_uxp_700d_3_ii.py, not yet authored) owns
    the `failure` and `reachability` angles. This file owns only the two
    angles UXP-700d-3-i's own test_spec authored: `real_artifact` and
    `boundary`, plus one additional seam test guarding the AC's own closing
    clause (the set-aside count must be unchanged by the rename).
ARCHITECTURE: No new production module. This AC only widens three existing
    JSON schemas (docs/product-truth/schemas/{flow,mockup,mock-data}.schema.json)
    to accept an optional `example_product` property, backfills the key onto
    the 3 fern-and-fig flows + 10 mockups + 1 mock-data dataset, and renames
    the AC-level `product:` field to `example_product:` on the 18 example AC
    YAML files (read by scripts/ac_store/scan_ac_store.py's
    `_is_example_content`, which is updated in lockstep). Every artifact this
    file reads is the REAL, checked-in file (Fixture Authenticity Rule) --
    there is nothing to mock, because the whole point of AC-1/AC-3 is what a
    reader holding the real file sees.
NOTE ON RED BASELINE: before this ticket's implementation lands, none of the
    checked-in fern-and-fig artifacts carries `example_product`, so
    TestExampleArtifactDeclaresItsProductInItsOwnContent fails on all three
    assertEqual calls (actual: None). The three schemas do not yet register
    `example_product` in `properties`, so TestProjectOwnedArtifactCarriesNo
    ExampleDeclaration's schema assertions fail too. scan_ac_store.py still
    reads `product`, so TestSetAsideCountUnchangedByTheRename's independent
    recount (which calls `_is_example_content` against `example_product:`-less
    records) mismatches the CLI's reported count (computed from the
    not-yet-renamed `product:` field) -- both currently non-zero-but-different
    numbers, not a trivial 0-vs-0 pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PRODUCT_TRUTH_DIR = _REPO_ROOT / "docs" / "product-truth"
_AC_STORE_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_SCAN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"

_EXAMPLE_JOURNEY = _PRODUCT_TRUTH_DIR / "flows" / "fern-and-fig" / "customer-buys-a-plant.flow.json"
_EXAMPLE_SCREEN = _PRODUCT_TRUTH_DIR / "mockups" / "fern-and-fig" / "plant-listing.mockup.json"
_EXAMPLE_DATASET = _PRODUCT_TRUTH_DIR / "mock-data" / "fern-and-fig" / "catalog.mock.json"

_OWN_JOURNEY = _PRODUCT_TRUTH_DIR / "flows" / "leafcutter" / "ac-lifecycle.flow.json"
_OWN_CRITERION = (
    _AC_STORE_ROOT / "ux-prototyping" / "UXP-700-truthful-project-record" / "UXP-700d-1.yaml"
)

_FLOW_SCHEMA = _PRODUCT_TRUTH_DIR / "schemas" / "flow.schema.json"
_MOCKUP_SCHEMA = _PRODUCT_TRUTH_DIR / "schemas" / "mockup.schema.json"
_MOCK_DATA_SCHEMA = _PRODUCT_TRUTH_DIR / "schemas" / "mock-data.schema.json"

_SCAN_MODULE_DIR = _SCAN_SCRIPT.parent
if str(_SCAN_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_SCAN_MODULE_DIR))

import scan_ac_store as sas  # noqa: E402


def _read_json(path: Path) -> dict:
    """Read *path* as JSON, verbatim -- the artifact's own on-disk content."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class TestExampleArtifactDeclaresItsProductInItsOwnContent(unittest.TestCase):
    """AC-1: a checked-in fern-and-fig journey, screen, and dataset each carry
    `example_product: fern-and-fig` in their own file content -- readable by
    a person or agent holding only that one file, nothing else."""

    def test_example_artifact_declares_its_example_product_in_its_own_content(self) -> None:
        # covers: UXP-700d-3-i
        # angle: real_artifact
        journey = _read_json(_EXAMPLE_JOURNEY)
        screen = _read_json(_EXAMPLE_SCREEN)
        dataset = _read_json(_EXAMPLE_DATASET)

        self.assertEqual(
            journey.get("example_product"),
            "fern-and-fig",
            f"{_EXAMPLE_JOURNEY} must declare example_product: fern-and-fig in its own content",
        )
        self.assertEqual(
            screen.get("example_product"),
            "fern-and-fig",
            f"{_EXAMPLE_SCREEN} must declare example_product: fern-and-fig in its own content",
        )
        self.assertEqual(
            dataset.get("example_product"),
            "fern-and-fig",
            f"{_EXAMPLE_DATASET} must declare example_product: fern-and-fig in its own content",
        )


class TestProjectOwnedArtifactCarriesNoExampleDeclaration(unittest.TestCase):
    """AC-3: a project-owned artifact and criterion, read the same way, carry
    no `example_product` key at all -- not even an empty or null one -- and
    AC-2: the three schemas accept the key without requiring it."""

    def test_project_owned_artifact_carries_no_example_declaration(self) -> None:
        # covers: UXP-700d-3-i
        # angle: boundary
        # A raw text scan for the KEY spelling (JSON `"example_product"` /
        # YAML `example_product:`), not dict.get(...) is None, so a
        # present-but-null or present-but-empty key -- which ADR-044 sec 3
        # also prohibits on the project's own record -- is caught, not just a
        # missing key. Matching the key spelling (not the bare word) avoids a
        # false positive from prose or test names that merely mention "example
        # product" (e.g. UXP-700d-1.yaml's own
        # test_example_product_remains_enumerable_by_name).
        own_journey_text = _OWN_JOURNEY.read_text(encoding="utf-8")
        self.assertNotIn(
            '"example_product"',
            own_journey_text,
            f"{_OWN_JOURNEY} is the project's own record and must carry no example_product key",
        )

        own_criterion_text = _OWN_CRITERION.read_text(encoding="utf-8")
        self.assertNotIn(
            "example_product:",
            own_criterion_text,
            f"{_OWN_CRITERION} is a project-owned criterion and must carry no example_product key",
        )

        for schema_path in (_FLOW_SCHEMA, _MOCKUP_SCHEMA, _MOCK_DATA_SCHEMA):
            schema = _read_json(schema_path)
            self.assertIn(
                "example_product",
                schema.get("properties", {}),
                f"{schema_path} must register example_product as an accepted property",
            )
            self.assertNotIn(
                "example_product",
                schema.get("required", []),
                f"{schema_path} must not require example_product -- project artifacts omit it",
            )


class TestSetAsideCountUnchangedByTheRename(unittest.TestCase):
    """AC-4 (closing clause): the count of example criteria set aside from the
    work queue is unchanged by the product: -> example_product: rename.

    Rather than hard-coding a figure (measured 2026-09-17 against the real
    store, with the default --level leaf --work-status todo filters: 3 -- far
    fewer than the 18 raw AC files carrying the marker, because most are not
    yet readiness: approved), this recomputes the expected count from
    scan_ac_store's OWN filter predicates and compares it against the CLI's
    own reported figure. The two are computed two different ways (a live
    subprocess vs. a direct module recount) but must agree; a mismatch is
    exactly the signature of a rename that missed a file.
    """

    def test_set_aside_count_matches_independent_recount_after_the_rename(self) -> None:
        # covers: UXP-700d-3-i
        # angle: seam
        result = subprocess.run(
            [sys.executable, str(_SCAN_SCRIPT), "--json"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"scan_ac_store CLI failed: stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        reported = json.loads(result.stdout)["set_aside_count"]

        recount = 0
        for path in sas._walk_ac_yamls(_AC_STORE_ROOT):  # noqa: SLF001 -- same-repo internal reuse
            record = sas._load_ac(path)  # noqa: SLF001
            if record is None:
                continue
            if not sas._is_leaf(record):  # noqa: SLF001
                continue
            if not sas._matches_work_status(record, "todo"):  # noqa: SLF001
                continue
            if not sas._is_active(record):  # noqa: SLF001
                continue
            if not sas._is_approved(record):  # noqa: SLF001
                continue
            if sas._is_example_content(record):  # noqa: SLF001
                recount += 1

        self.assertEqual(
            reported,
            recount,
            "scan_ac_store's reported set_aside_count must match an independent recount "
            "using the module's own filters -- a mismatch means some example AC still "
            "carries the old product: field instead of example_product:",
        )
        self.assertGreater(recount, 0, "expected at least one example AC to be set aside")


if __name__ == "__main__":
    unittest.main()
