"""Verify written records before a staged generation can be published.

Writers send a content fingerprint with every record and read back only the record key and the
stored fingerprint; rows without a fingerprint keep the older field-by-field comparison.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import NoReturn

logger = logging.getLogger(__name__)


def _reject(message: str) -> NoReturn:
    """Raise the one verification failure type with a fixed, content-free message."""
    raise ValueError(message)


def native_value(value):
    """Compare driver temporal values with their source-native equivalents."""
    if hasattr(value, "to_native"):
        value = value.to_native()
    if isinstance(value, list):
        return ("list", tuple(native_value(item) for item in value))
    return (type(value).__name__, value)


def fingerprint(payload_json_text: str) -> str:
    """Return the SHA-256 hex digest of the canonical serialization of one payload.

    Args:
        payload_json_text: JSON text of a node or relationship payload.

    Returns:
        A digest that ignores key order and whitespace of the input text.
    """
    canonical = json.dumps(json.loads(payload_json_text), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stored_fingerprint(row: dict) -> str | None:
    """Read the fingerprint from a read-back row, including the older ``props`` row shape."""
    if "fingerprint" in row:
        return row["fingerprint"]
    return (row.get("props") or {}).get("fingerprint")


def _describe(row: dict) -> str:
    """Name the failing record by identity and kind (nodes) or by key (relationships)."""
    if "canonical_id" in row:
        return f"node {row['canonical_id']} ({row.get('kind')})"
    return f"relationship {row['key']}"


def _verify_fingerprints(expected: list[dict], actual: list[dict]) -> None:
    """Reject the first missing or changed record, naming it and both fingerprints."""
    observed = {row["key"]: _stored_fingerprint(row) for row in actual}
    for row in expected:
        if row["key"] not in observed:
            message = f"{_describe(row)} is missing from the store after the write"
            logger.error(message)
            raise ValueError(message)
        if observed[row["key"]] != row["fingerprint"]:
            message = (
                f"{_describe(row)}: fingerprint mismatch: expected {row['fingerprint']} "
                f"stored {observed[row['key']]}"
            )
            logger.error(message)
            raise ValueError(message)


def verify_rows(expected: list[dict], actual: list[dict]) -> None:
    """Reject missing, duplicated or changed records without logging source contents.

    Args:
        expected: Rows as written; those carrying ``fingerprint`` are checked by fingerprint.
        actual: Rows read back from the store.

    Raises:
        ValueError: Naming the failing record and, for a changed one, both fingerprints.
    """
    if expected and all("fingerprint" in row for row in expected):
        _verify_fingerprints(expected, actual)
        return
    observed = {row["key"]: row["props"] for row in actual}
    if len(actual) != len(expected) or len(observed) != len(expected):
        _reject("native property readback count mismatch")
    for row in expected:
        found = observed.get(row["key"])
        if found is None:
            _reject("native property readback identity mismatch")
        for field, value in row.items():
            if native_value(found.get(field)) != native_value(value):
                _reject("native property readback mismatch: " + field)
