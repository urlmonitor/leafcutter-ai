"""
MODULE: tests.kernel.contracts.test_schema_catalog
GOAL: Test the 12-id payload catalog: valid/invalid fixtures per id, JSON Schema agreement,
    committed schema files, and semantic reference checks.
BUSINESS CONTEXT: External boundaries (TaskInput payloads, host and human submissions) accept
    only registered, validated payloads; fixtures prove both directions for every id.
ARCHITECTURE: Fixtures live in tests/kernel/fixtures/{valid,invalid}/<schema_id>/*.json and are
    discovered from disk so a new schema id without fixtures fails the coverage test.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kernel.contracts import schema_ids as sid
from kernel.contracts.schema_catalog import (
    SCHEMA_CATALOG,
    PayloadValidationError,
    SemanticContext,
    SemanticValidationError,
    UnknownSchemaError,
    export_json_schemas,
    json_schema_for,
    render_json_schema,
    semantic_violations,
    validate_payload,
    validate_semantics,
)
from tests.kernel.helpers import FIXTURES_DIR, make_evidence

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "kernel" / "schemas"


def _fixtures(kind: str) -> list[tuple[str, Path]]:
    return [(d.name, f) for d in sorted((FIXTURES_DIR / kind).iterdir())
            for f in sorted(d.glob("*.json"))]


class TestCatalog(unittest.TestCase):
    """Catalog completeness and fixtures."""

    def test_catalog_keys_equal_known_ids(self) -> None:
        self.assertEqual(set(SCHEMA_CATALOG), set(sid.KNOWN_SCHEMA_IDS))
        self.assertEqual(len(SCHEMA_CATALOG), 12)

    def test_every_schema_id_has_valid_and_invalid_fixtures(self) -> None:
        for kind in ("valid", "invalid"):
            covered = {name for name, _ in _fixtures(kind)}
            self.assertEqual(covered, set(SCHEMA_CATALOG), kind)

    def test_valid_fixtures_validate_and_match_json_schema(self) -> None:
        for schema_id, path in _fixtures("valid"):
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(fixture=path.name, schema=schema_id):
                validate_payload(schema_id, data)
                Draft202012Validator(json_schema_for(schema_id)).validate(data)

    def test_invalid_fixtures_are_rejected(self) -> None:
        for schema_id, path in _fixtures("invalid"):
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(fixture=path.name, schema=schema_id), \
                    self.assertRaises(PayloadValidationError):
                validate_payload(schema_id, data)

    def test_unknown_schema_id(self) -> None:
        with self.assertRaises(UnknownSchemaError):
            validate_payload("leafcutter.nope.v1", {})
        with self.assertRaises(UnknownSchemaError):
            json_schema_for("leafcutter.nope.v1")

    def test_payload_models_reject_unknown_fields(self) -> None:
        with self.assertRaises(PayloadValidationError):
            validate_payload(sid.GOAL_REQUEST, {"goal": "x", "extra": 1})


class TestSchemaExport(unittest.TestCase):
    """Committed JSON Schemas must match the models."""

    def test_committed_files_match_models(self) -> None:
        for schema_id in SCHEMA_CATALOG:
            committed = (SCHEMAS_DIR / f"{schema_id}.schema.json").read_text(encoding="utf-8")
            self.assertEqual(json.loads(committed), json_schema_for(schema_id), schema_id)

    def test_no_stray_schema_files(self) -> None:
        names = {p.name for p in SCHEMAS_DIR.glob("*.json")}
        self.assertEqual(names, {f"{i}.schema.json" for i in SCHEMA_CATALOG})

    def test_export_writes_deterministic_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            written = export_json_schemas(Path(tmp))
            self.assertEqual(len(written), 12)
            for path in written:
                self.assertEqual(path.read_text(encoding="utf-8"),
                                 render_json_schema(path.name.removesuffix(".schema.json")))

    def test_schema_declares_id_and_dialect(self) -> None:
        schema = json_schema_for(sid.OPTIONS)
        self.assertEqual(schema["$id"], sid.OPTIONS)
        self.assertIn("2020-12", schema["$schema"])


class TestSemantics(unittest.TestCase):
    """Reference checks run after structural validation."""

    def test_cited_evidence_must_exist(self) -> None:
        ev = make_evidence()
        payload = validate_payload(sid.DECISION_REPORT, {
            "status": "needs_evidence", "supporting_evidence_ids": [ev.id, "ev-ffffffffffffffff"]})
        ctx = SemanticContext(known_evidence_ids=frozenset({ev.id}))
        self.assertEqual(len(semantic_violations(sid.DECISION_REPORT, payload, ctx)), 1)
        with self.assertRaises(SemanticValidationError) as raised:
            validate_semantics(sid.DECISION_REPORT, payload, ctx)
        self.assertIn("ev-ffffffffffffffff", str(raised.exception))

    def test_selected_option_must_have_been_supplied(self) -> None:
        payload = validate_payload(sid.DECISION_REPORT, {
            "status": "resolved", "selected_option_id": "opt-x"})
        bad = SemanticContext(supplied_option_ids=frozenset({"opt-a"}))
        good = SemanticContext(supplied_option_ids=frozenset({"opt-x"}))
        self.assertTrue(semantic_violations(sid.DECISION_REPORT, payload, bad))
        self.assertEqual(semantic_violations(sid.DECISION_REPORT, payload, good), [])

    def test_human_choice_must_be_offered(self) -> None:
        payload = validate_payload(sid.HUMAN_ANSWER, {"choice_id": "maybe"})
        self.assertTrue(semantic_violations(
            sid.HUMAN_ANSWER, payload, SemanticContext(offered_choice_ids=frozenset({"yes"}))))
        self.assertEqual(semantic_violations(
            sid.HUMAN_ANSWER, payload, SemanticContext(offered_choice_ids=frozenset({"maybe"}))),
            [])

    def test_inline_bundle_evidence_counts_as_known(self) -> None:
        data = json.loads((FIXTURES_DIR / "valid" / sid.EVIDENCE_BUNDLE / "valid_basic.json")
                          .read_text(encoding="utf-8"))
        payload = validate_payload(sid.EVIDENCE_BUNDLE, data)
        self.assertEqual(semantic_violations(sid.EVIDENCE_BUNDLE, payload, SemanticContext()),
                         [])
        data["evidence_ids"].append("ev-eeeeeeeeeeeeeeee")
        again = validate_payload(sid.EVIDENCE_BUNDLE, data)
        self.assertEqual(len(semantic_violations(sid.EVIDENCE_BUNDLE, again, SemanticContext())),
                         1)


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Fixtures are discovered from disk (not listed) so adding a
#   schema id without fixtures fails test_every_schema_id_has_valid_and_invalid_fixtures.
#   (#KernelBootstrapV0/P1)
# ====================================================================
