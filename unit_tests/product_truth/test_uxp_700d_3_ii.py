"""
MODULE: test_uxp_700d_3_ii
GOAL: AC UXP-700d-3-ii -- "An example marker that disagrees with where the
    content lives is reported, naming both." ADR-044 sections 6-7 are this
    file's specification:
      AC-1 (mismatch): an artifact whose `example_product` differs from the
            product root it lives under is reported, naming the declared
            value and the root.
      AC-2 (undeclared): an artifact under the EXAMPLE_PRODUCT root carrying
            no `example_product` is reported as undeclared, naming the root
            -- but a root that is neither the project's own nor the example
            product's (e.g. the project's own `guardrails/` mock-data) is
            NEVER reported this way.
      AC-3 (project-declared): an `example_product` naming the project's own
            product (PROJECT_PRODUCT) is reported wherever it appears, even
            when there is no root to compare it against at all.
      AC-4 (AC root scope): an acceptance criterion is compared only against
            the product roots of its `implemented-by-step` doc_links; one
            with no such link is not reported for lacking a root.
      AC-5 (no new outcome): every finding reaches the checker's pre-existing
            `errors` list and outcome vocabulary (ADR-042) -- no new outcome
            value is introduced.
      AC-6 (ownership unchanged): ownership is still decided by location
            (product_ownership.product_of_artifact_id); the marker is never
            consulted to decide it.
BUSINESS CONTEXT: UXP-700d-3-i (merged, PR #835) registered the
    `example_product` schema key and backfilled every existing example
    artifact/criterion. This AC adds the cross-check ADR-044 section 5
    deliberately deferred until nothing was left unmarked. See that ADR's
    Context section for why a root that is neither `leafcutter` nor
    `fern-and-fig` (the real store's own `guardrails/frontend-ac-declarations`
    mock-data) MUST NOT be treated as an example root.
ARCHITECTURE: The pure verdict helpers
    (`example_product_findings`, `example_product_findings_for_ac`,
    `product_root_of_doc_link`) live in product_ownership.py beside the
    ownership predicate they cross-check (ADR-044 sec 7). The looping/
    message-formatting check itself
    (`product_truth_example_checks.check_example_product`) is a NEW sibling
    module -- validate_product_truth.py (399/400 content lines before this
    change) and product_truth_checks.py (396/400) both had no room left for
    it. `TestCheckerCliReportsMismatchedAndUndeclaredExamples` is the only subprocess test in
    this file; every other test calls `check_example_product` directly against
    small in-memory fixtures for speed, per this AC's own test_rationale
    ("a verdict helper that is never called from main() checks nothing" is
    exactly what the reachability test guards against).
NOTE ON RED BASELINE: before this ticket's implementation lands,
    product_truth_example_checks does not exist, so every direct test fails on
    import with ModuleNotFoundError; product_ownership.py carries none of
    example_product_findings / example_product_findings_for_ac /
    product_root_of_doc_link, so those attribute lookups (once the module
    import itself is made to succeed) would raise AttributeError; and the
    reachability test's subprocess run reports "checked-and-sound" (the check
    is never invoked) instead of "failed" with both findings named.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# NOT wrapped in try/except: product_truth_example_checks does not exist yet.
# This import failure IS the red baseline for every direct test in this file.
import product_truth_example_checks as ptec  # noqa: E402


def _flow(flow_id: str, *, example_product: str | None = None) -> dict:
    flow: dict = {
        "id": flow_id, "component": "fixture-product", "name": "n", "summary": "s",
        "kind": "user", "source": "mock", "status": "active", "readiness": "draft", "version": 1,
        "entities": [],
        "steps": [{"id": "step", "label": "step", "human": "the actor acts", "order": 1}],
        "branches": [],
    }
    if example_product is not None:
        flow["example_product"] = example_product
    return flow


def _mockup(mockup_id: str, *, example_product: str | None = None) -> dict:
    mockup: dict = {"id": mockup_id, "component": "fixture-product"}
    if example_product is not None:
        mockup["example_product"] = example_product
    return mockup


def _mock(mock_id: str, *, example_product: str | None = None) -> dict:
    mock: dict = {"id": mock_id, "component": "fixture-product"}
    if example_product is not None:
        mock["example_product"] = example_product
    return mock


class TestMismatchedDeclarationIsReportedNamingBothValues(unittest.TestCase):
    """AC-1 (mismatch): declared example_product != the product root the
    artifact actually lives under is reported, naming both."""

    def test_declaration_disagreeing_with_the_product_root_is_reported(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: failure
        flows = {"leafcutter/x": _flow("leafcutter/x", example_product="fern-and-fig")}
        errors: list[str] = []

        ptec.check_example_product(flows, {}, {}, {}, errors)

        self.assertEqual(len(errors), 1, f"expected exactly one finding, got {errors!r}")
        message = errors[0]
        self.assertTrue(message.startswith("[example]"), message)
        self.assertIn("leafcutter/x", message, "must name the artifact")
        self.assertIn("fern-and-fig", message, "must name the declared value")
        self.assertIn("leafcutter", message, "must name the product root it disagrees with")


class TestUndeclaredExampleArtifactIsReported(unittest.TestCase):
    """AC-2 (undeclared): an artifact under the EXAMPLE_PRODUCT root with no
    example_product is reported, naming the root."""

    def test_undeclared_example_artifact_is_reported(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        mockups = {"fern-and-fig/y": _mockup("fern-and-fig/y")}
        errors: list[str] = []

        ptec.check_example_product({}, {}, mockups, {}, errors)

        self.assertEqual(len(errors), 1, f"expected exactly one finding, got {errors!r}")
        message = errors[0]
        self.assertIn("fern-and-fig/y", message)
        self.assertIn("fern-and-fig", message)
        self.assertIn("undeclared", message.lower())


class TestGuardrailsLikeRootIsNeverReportedAsUndeclared(unittest.TestCase):
    """AC-2's own boundary: a root that is neither the project's own nor the
    example product's (the real store's `guardrails/` dataset) must NEVER be
    reported as undeclared, even though it too carries no example_product."""

    def test_non_example_non_project_root_is_never_reported_as_undeclared(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        mocks = {"guardrails/frontend-ac-declarations": _mock("guardrails/frontend-ac-declarations")}
        errors: list[str] = []

        ptec.check_example_product({}, mocks, {}, {}, errors)

        self.assertEqual(
            errors, [],
            "the project's own guardrails/ dataset must not be reported as undeclared example content",
        )


class TestProjectsOwnProductNamedAnywhereIsReported(unittest.TestCase):
    """AC-3 (project-declared): example_product naming the project's own
    product is reported wherever it appears -- including when it matches the
    artifact's own root (so it is not caught by the mismatch rule at all)."""

    def test_example_product_naming_the_project_is_reported_even_when_it_matches_its_own_root(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        flows = {"leafcutter/w": _flow("leafcutter/w", example_product="leafcutter")}
        errors: list[str] = []

        ptec.check_example_product(flows, {}, {}, {}, errors)

        self.assertEqual(len(errors), 1, f"expected exactly one finding, got {errors!r}")
        self.assertIn("leafcutter/w", errors[0])
        self.assertIn("leafcutter", errors[0])

    def test_example_product_naming_the_project_is_reported_even_without_any_root_to_compare(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        ac_records = {"AC-PROJECT-DECLARED": {"example_product": "leafcutter", "doc_links": []}}
        errors: list[str] = []

        ptec.check_example_product({}, {}, {}, ac_records, errors)

        self.assertEqual(len(errors), 1, f"expected exactly one finding, got {errors!r}")
        self.assertIn("AC-PROJECT-DECLARED", errors[0])
        self.assertIn("leafcutter", errors[0])


class TestAcWithNoImplementedByStepLinkIsNotReportedForLackingARoot(unittest.TestCase):
    """AC-4's boundary clause: an AC with no implemented-by-step doc_link has
    no root to compare against, and the absence of a root MUST NOT itself be
    reported."""

    def test_ac_with_no_implemented_by_step_link_is_not_reported_for_lacking_a_root(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        ac_records = {
            "AC-NO-LINK": {"doc_links": [{"path": "docs/some/doc.md", "relationship": "context"}]},
            "AC-NO-LINKS-AT-ALL": {"doc_links": []},
        }
        errors: list[str] = []

        ptec.check_example_product({}, {}, {}, ac_records, errors)

        self.assertEqual(errors, [])

    def test_ac_link_with_a_non_implemented_by_step_relationship_is_not_consulted(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        # Mirrors UXP-614's real doc_links shape: a project AC may cite an
        # example screen for context/relatedness without being compared
        # against its root.
        ac_records = {
            "AC-RELATED-ONLY": {
                "doc_links": [
                    {
                        "path": "docs/product-truth/mockups/fern-and-fig/cart.mockup.json",
                        "relationship": "related",
                    }
                ]
            }
        }
        errors: list[str] = []

        ptec.check_example_product({}, {}, {}, ac_records, errors)

        self.assertEqual(errors, [])


class TestAcComparedAgainstItsImplementedByStepRoot(unittest.TestCase):
    """AC-4's main clause: an AC IS compared against the root of every
    implemented-by-step link it carries."""

    def test_ac_declaring_the_matching_example_product_is_not_reported(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: real_artifact
        ac_records = {
            "AC-COMPLIANT": {
                "example_product": "fern-and-fig",
                "doc_links": [
                    {
                        "path": "docs/product-truth/flows/fern-and-fig/x.flow.json",
                        "relationship": "implemented-by-step",
                    }
                ],
            }
        }
        errors: list[str] = []

        ptec.check_example_product({}, {}, {}, ac_records, errors)

        self.assertEqual(errors, [])

    def test_ac_with_implemented_by_step_link_into_the_example_root_and_no_declaration_is_reported(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: boundary
        # The exact shape a mis-spelled doc_links relationship on a real,
        # project-owned AC could accidentally produce (see this ticket's own
        # fix to UXP-515.yaml) -- regression coverage for that class of bug.
        ac_records = {
            "AC-UNDECLARED-VIA-LINK": {
                "doc_links": [
                    {
                        "path": "docs/product-truth/mockups/fern-and-fig/x.mockup.json",
                        "relationship": "implemented-by-step",
                    }
                ],
            }
        }
        errors: list[str] = []

        ptec.check_example_product({}, {}, {}, ac_records, errors)

        self.assertEqual(len(errors), 1, f"expected exactly one finding, got {errors!r}")
        self.assertIn("AC-UNDECLARED-VIA-LINK", errors[0])
        self.assertIn("fern-and-fig", errors[0])


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _install_and_check(tmp: Path) -> subprocess.CompletedProcess:
    """Author one MISMATCHED journey and one UNDECLARED screen, derive the
    index with the real generator CLI, then run the real checker CLI -- the
    path an installed project takes."""
    pt = tmp / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    (pt / "mock-data").mkdir(parents=True)
    (pt / "classifier").mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    (tmp / "docs" / "acceptance-criteria").mkdir(parents=True)

    mismatched_flow = _flow("fixture-product/journey", example_product="fern-and-fig")
    _write_json(pt / "flows" / "fixture-product" / "journey.flow.json", mismatched_flow)

    undeclared_mockup = {
        "id": "fern-and-fig/screen", "component": "fixture-product", "screen": "screen",
        "title": "t", "summary": "s", "entities": [], "source": "mock", "renders": None,
        "status": "active", "readiness": "draft", "version": 1, "provenance": [],
    }
    _write_json(pt / "mockups" / "fern-and-fig" / "screen.mockup.json", undeclared_mockup)

    _write_json(pt / "index.json", {
        "artifacts": [{
            "id": "fixture-product/journey", "type": "flow", "component": "fixture-product",
            "path": "flows/fixture-product/journey.flow.json", "status": "active",
            "readiness": "draft", "version": 1,
        }],
        "entity_registry": [],
    })

    subprocess.run([sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                    capture_output=True, text=True, timeout=60, check=True)
    return subprocess.run([sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
                          capture_output=True, text=True, timeout=60)


class TestCheckerCliReportsMismatchedAndUndeclaredExamples(unittest.TestCase):
    def test_uxp_700d_3_reachable_from_entry_point(self) -> None:
        # covers: UXP-700d-3-ii
        # angle: reachability
        # Entry point: validate_product_truth.py's own CLI, run as a
        # subprocess over a temp store holding a mismatched journey AND an
        # undeclared screen -- both must be reported, and the pure verdict
        # helper must actually be reachable from main(), not merely defined.
        with tempfile.TemporaryDirectory() as tmp:
            result = _install_and_check(Path(tmp))

        self.assertEqual(
            result.returncode, 1,
            f"a real example_product finding must fail the commit gate; stderr={result.stderr!r}",
        )
        self.assertIn("[example]", result.stderr, f"stderr={result.stderr!r}")
        self.assertIn("fixture-product/journey", result.stderr)
        self.assertIn("fern-and-fig/screen", result.stderr)
        self.assertIn("fern-and-fig", result.stderr)

        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(
            payload["outcome"], "failed",
            "the pre-existing outcome vocabulary must carry this finding -- no new outcome value",
        )


if __name__ == "__main__":
    unittest.main()
