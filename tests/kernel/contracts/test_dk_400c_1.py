"""
MODULE: tests.kernel.contracts.test_dk_400c_1
GOAL: Prove the two goal-decomposition payload schemas follow ADR-067 section 4 and that the
    committed schema files are exactly what the catalog exports (AC DK-400c-1).
BUSINESS CONTEXT: The host's proposal and the kernel's request travel as registered payloads; a
    schema that drifts from the ADR (or a committed file that drifts from the catalog) lets the
    host answer in a shape the conversion cannot read.
ARCHITECTURE: validate_payload on payloads round-tripped through json.dumps; the committed
    kernel/schemas files compared with export_json_schemas output from a temporary directory.
    RED until the catalog carries the ADR-067 shapes.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.contracts import schema_ids as sid
from kernel.contracts.schema_catalog import (
    SCHEMA_CATALOG,
    PayloadValidationError,
    export_json_schemas,
    validate_payload,
)
from tests.kernel.split.support_400c import PROPOSED

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "kernel" / "schemas"
IDS = (sid.GOAL_DECOMPOSITION_REQUEST, sid.GOAL_DECOMPOSITION)
REQUEST: dict[str, Any] = {"split_id": "dcp-0123456789abcdef", "subject_kind": "goal",
                           "subject_text": "How should A and B work?",
                           "allowed_capabilities": ["decision", "research"],
                           "min_parts": 2, "max_parts": 5}


def _wire(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the payload as it arrives over the wire (through the real JSON serializer)."""
    return json.loads(json.dumps(payload))


def _rejected(schema_id: str, payload: dict[str, Any]) -> bool:
    """Return True when validate_payload refuses the payload."""
    try:
        validate_payload(schema_id, _wire(payload))
    except PayloadValidationError:
        return True
    return False


class TestGoalDecompositionSchemas(unittest.TestCase):
    """Both ids are registered, validate the ADR-067 shapes and are exported unchanged."""

    def test_goal_decomposition_schemas_registered_and_exported(self) -> None:
        # covers: DK-400c-1
        # angle: real_artifact
        """Both ids validate; committed files equal export_json_schemas output."""
        for schema_id in IDS:
            self.assertIn(schema_id, SCHEMA_CATALOG)
            self.assertIn(schema_id, sid.KNOWN_SCHEMA_IDS)
        # Request: all three subject kinds, as ADR-067 pins the fields.
        for kind in ("goal", "research_request", "decision_question"):
            validate_payload(sid.GOAL_DECOMPOSITION_REQUEST, _wire({**REQUEST, "subject_kind": kind}))
        # Proposal: the host's parts, a null and a worded one-question suggestion.
        for rewording in (None, "Which store should the categories use?"):
            validate_payload(sid.GOAL_DECOMPOSITION,
                             _wire({"parts": PROPOSED, "one_question_rewording": rewording}))
        # Boundary: zero parts and more than five parts are legal proposals (DK-400c-1-i).
        validate_payload(sid.GOAL_DECOMPOSITION, _wire({"parts": [], "one_question_rewording": None}))
        six = [{**PROPOSED[0], "id": f"q{i}"} for i in range(6)]
        validate_payload(sid.GOAL_DECOMPOSITION, _wire({"parts": six, "one_question_rewording": None}))
        # Committed files equal what the catalog exports.
        with tempfile.TemporaryDirectory() as tmp:
            export_json_schemas(Path(tmp))
            for schema_id in IDS:
                name = f"{schema_id}.schema.json"
                self.assertEqual((SCHEMAS_DIR / name).read_text(encoding="utf-8"),
                                 (Path(tmp) / name).read_text(encoding="utf-8"), name)

    def test_old_and_malformed_shapes_are_rejected(self) -> None:
        # covers: DK-400c-1
        # angle: discrimination
        """The DK-400a-1 placeholder shape and each broken field go red, with a control row."""
        old = {"parts": [{"title": "Storage", "quote": "the storage format"}]}
        self.assertTrue(_rejected(sid.GOAL_DECOMPOSITION, old))  # old {title, quote} shape
        good = {"parts": PROPOSED, "one_question_rewording": None}
        self.assertFalse(_rejected(sid.GOAL_DECOMPOSITION, good))  # control row
        for field, value in (("child_capability", "retrieve"), ("covers", None), ("id", None)):
            broken = {"parts": [{**PROPOSED[0], field: value}], "one_question_rewording": None}
            with self.subTest(field=field):
                self.assertTrue(_rejected(sid.GOAL_DECOMPOSITION, broken))
        extra = {"parts": [{**PROPOSED[0], "review": "approved"}], "one_question_rewording": None}
        self.assertTrue(_rejected(sid.GOAL_DECOMPOSITION, extra))  # host may not set kernel fields
        self.assertFalse(_rejected(sid.GOAL_DECOMPOSITION_REQUEST, REQUEST))  # control row
        self.assertTrue(_rejected(sid.GOAL_DECOMPOSITION_REQUEST,
                                  {**REQUEST, "allowed_capabilities": ["decision", "x"]}))
        self.assertTrue(_rejected(sid.GOAL_DECOMPOSITION_REQUEST, {**REQUEST, "min_parts": 1}))
        self.assertTrue(_rejected(sid.GOAL_DECOMPOSITION_REQUEST,
                                  {k: v for k, v in REQUEST.items() if k != "split_id"}))
